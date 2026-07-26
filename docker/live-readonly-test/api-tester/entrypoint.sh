#!/bin/sh
# Dispatch api-tester container work by MODE.
set -e
MODE="${MODE:-api-tests}"
case "$MODE" in
  api-tests)  exec python -u /app/run_api_tests.py ;;
  bootstrap)  exec python -u /app/ha_probe.py bootstrap ;;
  setup)      exec python -u /app/ha_probe.py setup ;;
  entities)   exec python -u /app/ha_probe.py entities ;;
  services)   exec python -u /app/ha_probe.py services ;;
  reload)     exec python -u /app/ha_probe.py reload --rounds "${RELOAD_ROUNDS:-3}" ;;
  stability)  exec python -u /app/ha_probe.py stability --minutes "${STABILITY_MINUTES:-60}" ;;
  idle)       echo "[api-tester] idle; keeping container alive"; exec sleep infinity ;;
  *)          echo "unknown MODE=$MODE"; exit 2 ;;
esac
