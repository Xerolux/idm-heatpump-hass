# start.ps1 — bring up the read-only proxies + Home Assistant.
# api-tester is NOT started here; it is invoked on demand via run_probe.ps1.
[CmdletBinding()]
param(
    [switch]$NoBuild
)
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Write-Host "Missing .env. Copy .env.example to .env and fill in IDM_HOST / IDM_WEB_PIN." -ForegroundColor Red
    exit 2
}

if (-not $NoBuild) {
    if (-not (Test-Path (Join-Path $Root "homeassistant\wheels\idm_heatpump_api-0.8.5-py3-none-any.whl"))) {
        Write-Host "Wheels missing. Running build.ps1 first..." -ForegroundColor Yellow
        & (Join-Path $ScriptDir "build.ps1")
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}

Write-Host ">>> Starting modbus-proxy + web-proxy + homeassistant" -ForegroundColor Cyan
docker compose up -d modbus-proxy web-proxy homeassistant
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ">>> Waiting for proxies (healthy)..." -ForegroundColor Cyan
docker compose ps

Write-Host "`nOpen Home Assistant at: http://localhost:8123" -ForegroundColor Green
Write-Host "Run bootstrap next:      .\scripts\run_probe.ps1 bootstrap" -ForegroundColor Green
