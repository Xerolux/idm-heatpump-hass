# stop.ps1 — stop all services (keeps volumes / .storage / logs / results).
[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
docker compose stop
