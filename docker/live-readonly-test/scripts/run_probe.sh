#!/usr/bin/env bash
# run_probe.sh — run a one-shot api-tester probe by MODE (Linux counterpart of
# run_probe.ps1).
# Usage:
#   ./run_probe.sh bootstrap
#   ./run_probe.sh api-tests
#   ./run_probe.sh entities
#   ./run_probe.sh services
#   ./run_probe.sh reload          (uses RELOAD_ROUNDS, default 3)
#   ./run_probe.sh stability       (uses STABILITY_MINUTES, default 60)
#   ./run_probe.sh cmd <args...>   (free-form override)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mode="${1:-api-tests}"
if [ "$mode" = "cmd" ]; then
  shift
  docker compose run --rm --no-deps api-tester "$@"
else
  docker compose run --rm --no-deps -e "MODE=$mode" api-tester
fi
