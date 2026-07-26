# run_probe.ps1 — run a one-shot api-tester probe by MODE.
# Usage:
#   .\run_probe.ps1 bootstrap
#   .\run_probe.ps1 api-tests
#   .\run_probe.ps1 entities
#   .\run_probe.ps1 services
#   .\run_probe.ps1 reload          (uses RELOAD_ROUNDS, default 3)
#   .\run_probe.ps1 stability       (uses STABILITY_MINUTES, default 60)
#   .\run_probe.ps1 cmd <args...>   (free-form override)
[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Mode = "api-tests",
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

switch ($Mode) {
    "cmd" {
        # Free-form: pass remaining args directly to the container.
        docker compose run --rm --no-deps api-tester @Rest
    }
    default {
        docker compose run --rm --no-deps -e MODE=$Mode api-tester
    }
}
exit $LASTEXITCODE
