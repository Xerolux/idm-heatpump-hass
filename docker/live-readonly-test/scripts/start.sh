#!/usr/bin/env bash
# start.sh — start the proxies + Home Assistant (Linux counterpart of start.ps1).
# Usage: ./start.sh [--no-build]   (skips the automatic build.ps1 fallback)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

[ -f .env ] || { echo "Missing .env. Copy .env.example to .env and fill in IDM_HOST / IDM_WEB_PIN." >&2; exit 2; }

if [ "${1:-}" != "--no-build" ]; then
  if ! ls homeassistant/wheels/idm_heatpump_api-*.whl >/dev/null 2>&1; then
    echo "Wheels missing. Running build.sh first..."
    "$SCRIPT_DIR/build.sh"
  fi
fi

# Linux bind-mount permissions: the proxies and the api-tester run as uid 1000
# inside the containers, while the mounted directories may belong to the
# invoking user. Make them group/world writable so the probes can write their
# reports without weakening anything else.
mkdir -p results logs/modbus-proxy logs/web-proxy logs/homeassistant
chmod -R a+rwX results logs 2>/dev/null || true

echo ">>> Starting modbus-proxy + web-proxy + homeassistant"
docker compose up -d modbus-proxy web-proxy homeassistant
