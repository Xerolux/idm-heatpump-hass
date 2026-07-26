# =============================================================================
# build.ps1 — build wheels, seed HA storage, build docker images.
# Run from docker/live-readonly-test (or pass -Root). Requires .env (copy from
# .env.example). Pure-local: never pulls a published API build into HA.
# =============================================================================
[CmdletBinding()]
param(
    [string]$ApiRepo = "C:\Users\basti\Documents\GitHub\idm-heatpump-api",
    [string]$EnvFile  = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
if (-not $EnvFile) { $EnvFile = Join-Path $Root ".env" }

function Write-Step($m){ Write-Host "`n>>> $m" -ForegroundColor Cyan }
function Write-Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Write-Err($m){ Write-Host "[ERR]  $m" -ForegroundColor Red }

if (-not (Test-Path $EnvFile)) {
    Write-Err ".env not found at $EnvFile"
    Write-Host "  Copy .env.example to .env and fill in IDM_HOST / IDM_WEB_PIN."
    exit 2
}

# --- Load .env manually (Get-Content) so it stays cross-shell portable ----
$envVars = @{}
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $idx = $line.IndexOf("=")
    if ($idx -le 0) { return }
    $k = $line.Substring(0,$idx).Trim()
    $v = $line.Substring($idx+1).Trim()
    if ($v.StartsWith('"') -and $v.EndsWith('"')) { $v = $v.Substring(1,$v.Length-2) }
    $envVars[$k] = $v
}
function EnvOr($k,$d){ if ($envVars.ContainsKey($k)) { return $envVars[$k] } else { return $d } }

# --- 1. Build local idm-heatpump-api wheel from source --------------------
Write-Step "Building local idm-heatpump-api wheel from $ApiRepo"
if (-not (Test-Path (Join-Path $ApiRepo "pyproject.toml"))) {
    Write-Err "API repo not found at $ApiRepo"
    exit 3
}
$distDir = Join-Path $ApiRepo "dist"
python -m build --wheel --outdir $distDir $ApiRepo
if ($LASTEXITCODE -ne 0) { Write-Err "Wheel build failed"; exit 4 }
$wheel = Get-ChildItem $distDir -Filter "idm_heatpump_api-*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Ok "Built $($wheel.Name)"
$wheelHash = (Get-FileHash $wheel.FullName -Algorithm SHA256).Hash.ToLower()
Write-Host "    sha256: $wheelHash"

# --- 2. Copy wheel into HA + api-tester build contexts --------------------
$haWheels = Join-Path $Root "homeassistant\wheels"
$testerWheels = Join-Path $Root "api-tester\wheels"
New-Item -ItemType Directory -Path $haWheels -Force | Out-Null
New-Item -ItemType Directory -Path $testerWheels -Force | Out-Null
Get-ChildItem $haWheels -Filter "*.whl" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $testerWheels -Filter "*.whl" -ErrorAction SilentlyContinue | Remove-Item -Force
Copy-Item $wheel.FullName (Join-Path $haWheels $wheel.Name) -Force
Copy-Item $wheel.FullName (Join-Path $testerWheels $wheel.Name) -Force
Write-Ok "Wheel staged for HA + api-tester"

# --- 3. Seed HA config_entries storage (deterministic) --------------------
Write-Step "Seeding homeassistant/.storage/core.config_entries"
$storageDir = Join-Path $Root "homeassistant\config\.storage"
New-Item -ItemType Directory -Path $storageDir -Force | Out-Null

$idmHost    = EnvOr "IDM_HOST" "192.168.178.103"
$webHost    = "web-proxy"   # service name; web-proxy listens on port 80 internally
$modbusHost = "modbus-proxy"
$webPin     = EnvOr "IDM_WEB_PIN" ""
$entryTitle = EnvOr "HA_ENTRY_TITLE" "IDM Heatpump"
$scanIv     = [int](EnvOr "HA_SCAN_INTERVAL" "30")
$hideUnused = ($envVars.ContainsKey("HA_HIDE_UNUSED") -and $envVars["HA_HIDE_UNUSED"] -eq "true")
$circuits   = @((EnvOr "HA_HEATING_CIRCUITS" "a") -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })

# Stable entry_id / unique_id so reloads keep entity registries.
$entryId  = "01JULY2026-IDM-TEST-000000000001"
$uniqueId = "idm-live-ro-test-$idmHost"

$data = [ordered]@{
    host = $modbusHost
    port = 5020
    slave_id = 1
    name = $entryTitle
    modbus_proxy = $false
    web_host = $webHost
    web_pin = $webPin
    model_override = "auto"
}
$options = [ordered]@{
    scan_interval = $scanIv
    hide_unused_registers = $hideUnused
    heating_circuits = $circuits
    zone_count = 0
    device_hierarchy = $true
    short_cycle_minutes = 15
    technician_codes = $false
    enable_cascade = $false
    web_extra_data = ($webPin -ne "")
    web_scan_interval = 300
    room_temp_forwarding = $false
    room_temp_forwarding_interval = 300
    room_temp_forwarding_tolerance = 0.2
    modbus_timeout = 10.0
    modbus_retries = 3
}

$entry = [ordered]@{
    entry_id = $entryId
    version = 1
    minor_version = 3
    domain = "idm_heatpump"
    title = $entryTitle
    data = $data
    options = $options
    pref_disable_new_entities = $false
    pref_disable_polling = $false
    source = "user"
    unique_id = $uniqueId
    disabled_by = $null
}
$storage = [ordered]@{
    version = 1
    minor_version = 1
    key = "core.config_entries"
    data = [ordered]@{ entries = @($entry) }
}
$storageJson = $storage | ConvertTo-Json -Depth 12 -Compress
$storagePath = Join-Path $storageDir "core.config_entries"
[System.IO.File]::WriteAllText($storagePath, $storageJson, [System.Text.UTF8Encoding]::new($false))

# Pin scrub check: the only file under config/ that may contain the PIN.
$pinFiles = Get-ChildItem (Join-Path $Root "homeassistant\config") -Recurse -File | Where-Object {
    $_.Name -notlike "*.yaml" } | ForEach-Object { $_.FullName }
Write-Ok "Sealed config entry to $storagePath"
Write-Host "    (PIN present only inside .storage/, which is gitignored)"

# --- 4. Write the resolved wheel name into .env (for compose build arg) ---
# Already same name; ensure .env has API_WHEEL matching the built wheel.
($envVars["API_WHEEL"] = $wheel.Name) | Out-Null
$lines = Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*API_WHEEL\s*=') { "API_WHEEL=$($wheel.Name)" } else { $_ }
}
# Only rewrite if changed
if (-not ($lines -contains "API_WHEEL=$($wheel.Name)")) { $lines += "API_WHEEL=$($wheel.Name)" }
Set-Content -Path $EnvFile -Value $lines -Encoding utf8

# --- 5. Build docker images ------------------------------------------------
Write-Step "Building docker images (modbus-proxy, web-proxy, homeassistant, api-tester)"
Push-Location $Root
try {
    docker compose build
    if ($LASTEXITCODE -ne 0) { Write-Err "docker compose build failed"; exit 5 }
} finally { Pop-Location }

# --- 6. Record build provenance -------------------------------------------
$provenance = [ordered]@{
    built_at = (Get-Date).ToString("o")
    api_wheel = $wheel.Name
    api_wheel_sha256 = $wheelHash
    api_repo = $ApiRepo
    idm_host = $idmHost
    entry_id = $entryId
    unique_id = $uniqueId
}
$resultsDir = Join-Path $Root "results"
New-Item -ItemType Directory -Path $resultsDir -Force | Out-Null
$provenance | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $resultsDir "build_provenance.json") -Encoding utf8

Write-Ok "Build complete."
Write-Host "  Next: .\scripts\start.ps1   (then .\scripts\bootstrap_ha.ps1 to onboard + export entities)"
