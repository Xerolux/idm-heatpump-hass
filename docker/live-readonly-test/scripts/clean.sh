#!/usr/bin/env bash
# clean.sh — full teardown: stop + remove containers and the HA config volume
# contents under .storage, logs, results. DOES NOT touch .env. The proxies are
# read-only, so there is never anything to clean on the heat pump side.
# Usage: ./clean.sh [--keep-results]
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
docker compose down --remove-orphans

rm -rf homeassistant/config/.storage
find logs -mindepth 2 -type f -delete 2>/dev/null || true
if [ "${1:-}" != "--keep-results" ]; then
  find results -maxdepth 1 -type f -delete 2>/dev/null || true
fi
echo "Cleaned containers, HA .storage, logs"
