#!/usr/bin/env bash
# stop.sh — stop all services (keeps volumes / .storage / logs / results).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
docker compose stop
