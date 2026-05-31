# IDM Heatpump Docker Test Script for Windows (PowerShell)
# Tests the integration against a real IDM heat pump via Home Assistant in Docker.
# READ-ONLY - no writes to the heat pump.
#
# Usage:
#   .\run_docker_test.ps1              # Full test
#   .\run_docker_test.ps1 -Test smoke  # Smoke test only
#   .\run_docker_test.ps1 -Test logs   # Show logs
#   .\run_docker_test.ps1 -Test clean  # Remove container

[CmdletBinding()]
param(
    [ValidateSet("all", "smoke", "start", "stop", "restart", "logs", "status", "clean", "test", "install")]
    [string]$Test = "all",

    [string]$IdmIp = "192.168.178.103",
    [int]$IdmPort = 502,
    [int]$IdmSlaveId = 1,
    [int]$HaPort = 8123,
    [string]$HaToken = ""
)

$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$ComposeFile = Join-Path $ScriptDir "docker-compose.yml"
$ContainerName = "homeassistant-idm-test"
$HaUrl = "http://localhost:${HaPort}"

function Write-Info($msg)    { Write-Host "[$([char]0x1b)[34mINFO$([char]0x1b)[0m]    $msg" }
function Write-Ok($msg)      { Write-Host "[$([char]0x1b)[32mOK$([char]0x1b)[0m]      $msg" }
function Write-Warn($msg)    { Write-Host "[$([char]0x1b)[33mWARN$([char]0x1b)[0m]    $msg" }
function Write-Err($msg)     { Write-Host "[$([char]0x1b)[31mERROR$([char]0x1b)[0m]    $msg" }
function Write-Step($msg)    { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Header($msg)  {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host " $msg" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

# ============================================================================
# Container Lifecycle
# ============================================================================

function Test-ContainerExists {
    docker ps -a --format "{{.Names}}" 2>$null | Select-String -Pattern "^$ContainerName$" -Quiet
}

function Test-ContainerRunning {
    docker ps --format "{{.Names}}" 2>$null | Select-String -Pattern "^$ContainerName$" -Quiet
}

function Start-HAContainer {
    Write-Header "STARTING HOME ASSISTANT"

    if (-not (Test-Path $ComposeFile)) {
        Write-Err "docker-compose.yml not found at $ComposeFile"
        return $false
    }

    if (-not (Test-Path "$ProjectRoot\custom_components\idm_heatpump")) {
        Write-Err "Integration not found at $ProjectRoot\custom_components\idm_heatpump"
        return $false
    }

    if (Test-ContainerRunning) {
        Write-Info "Container already running"
        return $true
    }

    if (Test-ContainerExists) {
        Write-Info "Starting existing container..."
        docker compose -f $ComposeFile start 2>$null
    } else {
        Write-Info "Pulling latest HA image..."
        docker compose -f $ComposeFile pull 2>$null
        Write-Info "Creating and starting container..."
        docker compose -f $ComposeFile up -d 2>$null
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to start container"
        return $false
    }

    Write-Ok "Container started"
    return $true
}

function Wait-HAReady {
    Write-Header "WAITING FOR HOME ASSISTANT"

    $maxWait = 180
    $elapsed = 0

    while ($elapsed -lt $maxWait) {
        try {
            $response = Invoke-WebRequest -Uri "$HaUrl/api/" -TimeoutSec 5 -ErrorAction Stop
            Write-Ok "HA is responding after ${elapsed}s"
            return $true
        } catch {}

        Write-Host -NoNewline "`r[INFO]    Waiting... ${elapsed}s / ${maxWait}s"
        Start-Sleep -Seconds 5
        $elapsed += 5
    }

    Write-Host ""
    Write-Err "HA did not respond within ${maxWait}s"
    Write-Info "Last 30 log lines:"
    docker logs --tail 30 $ContainerName 2>&1
    return $false
}

function Stop-HAContainer {
    Write-Header "STOPPING CONTAINER"
    docker compose -f $ComposeFile down 2>$null
    Write-Ok "Stopped"
}

function Remove-Everything {
    Write-Header "CLEANING UP"
    docker compose -f $ComposeFile down -v 2>$null
    Write-Ok "Container and volume removed"
}

# ============================================================================
# Tests
# ============================================================================

function Test-IntegrationLoaded {
    Write-Header "TEST 1: Integration Loaded"

    $logs = docker logs $ContainerName 2>&1 | Out-String

    $found = $false
    if ($logs -match "Setting up IDM Heatpump") {
        Write-Ok "Integration setup initiated"
        $found = $true
    } elseif ($logs -match "idm_heatpump") {
        Write-Ok "Integration referenced in logs"
        $found = $true
    } else {
        Write-Warn "Integration not found in logs (may still be loading)"
    }

    if ($logs -match "Connected to $IdmIp") {
        Write-Ok "Modbus connection established"
    }

    return $found
}

function Test-NoCriticalErrors {
    Write-Header "TEST 2: No Critical Errors"

    $logs = docker logs $ContainerName 2>&1 | Out-String

    # Check for known code bugs
    $badPatterns = @(
        "TypeError.*entity_category"
        "TypeError.*_number"
        "ImportError.*idm_heatpump"
        "ModuleNotFoundError.*idm"
    )

    $foundErrors = $false
    foreach ($pattern in $badPatterns) {
        if ($logs -match $pattern) {
            Write-Err "Found: $pattern"
            $foundErrors = $true
        }
    }

    # Check IDM-specific errors
    $idmErrors = $logs -split "`n" | Where-Object {
        $_ -match "idm" -and $_ -match "error|exception|traceback" -and $_ -notmatch "ConfigEntryNotReady"
    } | Select-Object -Last 10

    if ($idmErrors) {
        Write-Warn "IDM-related errors:"
        $idmErrors | ForEach-Object { Write-Host "  $_" }
    }

    if (-not $foundErrors) {
        Write-Ok "No critical code errors"
    }

    return -not $foundErrors
}

function Test-ModbusConnection {
    Write-Header "TEST 3: Direct Modbus TCP"

    $script = @"
import socket, struct, sys
host = '$IdmIp'
port = $IdmPort
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((host, port))
    req = struct.pack('>HHHBBHH', 1, 0, 6, 1, 4, 1000, 2)
    s.send(req)
    resp = s.recv(256)
    s.close()
    if len(resp) >= 9:
        byte_count = resp[8]
        if byte_count >= 4:
            raw = resp[9:13]
            val = struct.unpack('<f', struct.pack('<HH', struct.unpack('>H', raw[0:2])[0], struct.unpack('>H', raw[2:4])[0]))[0]
            print(f'  Connected to {host}:{port}')
            print(f'  Outdoor temperature: {val:.1f} C')
            sys.exit(0)
    print('  Unexpected response')
    sys.exit(1)
except socket.timeout:
    print(f'  Connection timed out to {host}:{port}')
    sys.exit(1)
except Exception as e:
    print(f'  Connection failed: {e}')
    sys.exit(1)
"@

    $result = python -c $script 2>&1
    $result | ForEach-Object { Write-Host $_ }

    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Direct Modbus connection successful"
        return $true
    } else {
        Write-Warn "Direct Modbus test failed"
        return $false
    }
}

function Test-EntitiesAvailable {
    Write-Header "TEST 4: Entities via HA API"

    if (-not $HaToken) {
        Write-Warn "No HA_TOKEN set, skipping API test"
        Write-Info "Open $HaUrl in browser and add the integration manually:"
        Write-Info "  Settings > Devices & Services > Add Integration > 'IDM Heatpump'"
        Write-Info "  Host: $IdmIp, Port: $IdmPort, Slave ID: $IdmSlaveId"
        return $true
    }

    $headers = @{ "Authorization" = "Bearer $HaToken" }

    try {
        $states = Invoke-RestMethod -Uri "$HaUrl/api/states" -Headers $headers -TimeoutSec 10
        $idmEntities = $states | Where-Object {
            $_.entity_id -match "^sensor\.idm|^binary_sensor\.idm|^number\.idm|^select\.idm|^switch\.idm"
        }

        $total = ($idmEntities | Measure-Object).Count
        $available = ($idmEntities | Where-Object {
            $_.state -notin @("unavailable", "unknown")
        } | Measure-Object).Count

        Write-Ok "Found $total IDM entities ($available available)"

        # Show first 10 sensor values
        $idmEntities | Where-Object {
            $_.entity_id -match "^sensor\.idm" -and $_.state -notin @("unavailable", "unknown")
        } | Select-Object -First 10 | ForEach-Object {
            $unit = ""
            if ($_.attributes.unit_of_measurement) { $unit = " $($_.attributes.unit_of_measurement)" }
            Write-Info "  $($_.entity_id): $($_.state)$unit"
        }

        return $available -gt 0
    } catch {
        Write-Warn "Could not query HA API: $_"
        return $false
    }
}

function Get-HAToken {
    Write-Step "Checking HA API access"

    if ($HaToken) {
        Write-Ok "HA_TOKEN provided"
        return
    }

    Write-Warn "No HA_TOKEN set"
    Write-Info "To enable API-based tests:"
    Write-Info "  1. Open $HaUrl"
    Write-Info "  2. Complete onboarding"
    Write-Info "  3. Go to Profile > Security > Long-Lived Access Tokens"
    Write-Info "  4. Create token and re-run:"
    Write-Info "     .\run_docker_test.ps1 -HaToken 'your_token_here'"
}

# ============================================================================
# Test Suites
# ============================================================================

function Invoke-SmokeTests {
    Write-Header "SMOKE TESTS (READ-ONLY)"
    $failures = 0

    if (-not (Start-HAContainer)) { return 1 }
    if (-not (Wait-HAReady)) { return 1 }

    Write-Info "Waiting 30s for custom components to load..."
    Start-Sleep -Seconds 30

    if (-not (Test-IntegrationLoaded)) { $failures++ }
    if (-not (Test-NoCriticalErrors)) { $failures++ }

    if ($failures -eq 0) {
        Write-Ok "All smoke tests passed!"
    } else {
        Write-Warn "$failures smoke test(s) failed"
    }
    return $failures
}

function Invoke-FullTests {
    Write-Header "FULL TEST SUITE (READ-ONLY)"

    $failures = 0
    $failures += Invoke-SmokeTests

    if (-not (Test-ModbusConnection)) { $failures++ }

    Get-HAToken
    if (-not (Test-EntitiesAvailable)) { $failures++ }

    Write-Header "RESULTS"
    if ($failures -eq 0) {
        Write-Ok "ALL TESTS PASSED!"
        Write-Info "HA:          $HaUrl"
        Write-Info "Integration: $HaUrl/config/integrations/integration/idm_heatpump"
        Write-Info "IDM:         ${IdmIp}:${IdmPort}"
    } else {
        Write-Warn "$failures test(s) failed"
        Write-Info "Show logs: .\run_docker_test.ps1 -Test logs"
    }
    return $failures
}

function Show-Logs {
    Write-Header "IDM-RELATED LOGS (last 100 lines)"
    docker logs --tail 500 $ContainerName 2>&1 | Where-Object { $_ -match "idm" } | Select-Object -Last 100
    Write-Host ""
    Write-Info "Full logs: docker logs $ContainerName"
}

function Show-Status {
    Write-Header "CONTAINER STATUS"
    docker ps -a --filter "name=$ContainerName" --format "table {{.Names}}`t{{.Image}}`t{{.Status}}"

    Write-Host ""
    Write-Header "HA HEALTH"
    try {
        Invoke-WebRequest -Uri "$HaUrl/api/" -TimeoutSec 5 -ErrorAction Stop | Out-Null
        Write-Ok "HA is responding"
    } catch {
        Write-Err "HA is not responding"
    }
}

# ============================================================================
# Main
# ============================================================================

switch ($Test) {
    "all"      { Invoke-FullTests }
    "smoke"    { Invoke-SmokeTests }
    "start"    { Start-HAContainer; Wait-HAReady; Write-Ok "HA ready at $HaUrl" }
    "stop"     { Stop-HAContainer }
    "restart"  { Stop-HAContainer; Start-HAContainer; Wait-HAReady }
    "logs"     { Show-Logs }
    "status"   { Show-Status }
    "clean"    { Remove-Everything }
    "test"     { Test-ModbusConnection }
    "install"  { Get-HAToken }
}
