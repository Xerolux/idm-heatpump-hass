# clean.ps1 — full teardown: stop + remove containers and the HA config volume
# contents under .storage, logs, results. DOES NOT touch .env. The proxies are
# read-only, so there is never anything to clean on the heat pump side.
[CmdletBinding()]
param(
    [switch]$KeepResults
)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
docker compose down --remove-orphans
# Wipe generated HA storage + logs (keeps configuration.yaml).
$storage = Join-Path $Root "homeassistant\config\.storage"
if (Test-Path $storage) { Remove-Item -Recurse -Force $storage }
Get-ChildItem (Join-Path $Root "logs") -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    Get-ChildItem $_.FullName -File -ErrorAction SilentlyContinue | Remove-Item -Force
}
if (-not $KeepResults) {
    Get-ChildItem (Join-Path $Root "results") -File -ErrorAction SilentlyContinue | Remove-Item -Force
}
Write-Host "Cleaned containers, HA .storage, logs" -ForegroundColor Green
