#!/usr/bin/env bash
# build.sh — build wheels, seed HA storage, build docker images.
# Linux/macOS counterpart of build.ps1. Run from anywhere; requires .env
# (copy from .env.example) in docker/live-readonly-test. Pure-local: never
# pulls a published API build into HA.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
# Default: the API repository checked out next to this integration repository.
IDM_API_REPO="${IDM_API_REPO:-$ROOT/../../../idm-heatpump-api}"

step() { printf '\n>>> %s\n' "$1"; }
ok()   { printf '[OK]   %s\n' "$1"; }
die()  { printf '[ERR]  %s\n' "$1" >&2; exit 2; }

[ -f "$ENV_FILE" ] || die ".env not found at $ENV_FILE (copy .env.example and fill in IDM_HOST / IDM_WEB_PIN)"

# Load .env (KEY=VALUE, optional surrounding quotes) so it stays shell-portable.
declare -A ENVV=()
while IFS= read -r line; do
  line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [ -z "$line" ] || [[ "$line" == \#* ]] && continue
  key="${line%%=*}"; value="${line#*=}"
  value="${value%\"}"; value="${value#\"}"
  ENVV["$key"]="$value"
done < <(grep -v '^[[:space:]]*$' "$ENV_FILE")
envor() { if [ -n "${ENVV[$1]+x}" ]; then printf '%s' "${ENVV[$1]}"; else printf '%s' "$2"; fi; }

# --- 1. Build local idm-heatpump-api wheel from source ----------------------
step "Building local idm-heatpump-api wheel from $IDM_API_REPO"
[ -f "$IDM_API_REPO/pyproject.toml" ] || die "API repo not found at $IDM_API_REPO (set IDM_API_REPO=...)"
# A python that has the 'build' package: explicit override, then the
# integration repository's venvs, then the system python.
bench_python="${BENCH_PYTHON:-}"
if [ -z "$bench_python" ]; then
  for candidate in "$ROOT/../../.venv/bin/python" "$ROOT/../../test_ha/bin/python" python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import build" >/dev/null 2>&1; then
      bench_python="$candidate"
      break
    fi
  done
fi
[ -n "$bench_python" ] || die "no python with the 'build' package found (pip install build or set BENCH_PYTHON=...)"
"$bench_python" -m build --wheel --outdir "$IDM_API_REPO/dist" "$IDM_API_REPO" >/dev/null
wheel_path="$(ls -t "$IDM_API_REPO"/dist/idm_heatpump_api-*.whl | head -1)"
wheel_name="$(basename "$wheel_path")"
ok "Built $wheel_name"
wheel_hash="$(sha256sum "$wheel_path" | cut -d' ' -f1)"
printf '    sha256: %s\n' "$wheel_hash"

# --- 2. Copy wheel into HA + api-tester build contexts ----------------------
ha_wheels="$ROOT/homeassistant/wheels"; tester_wheels="$ROOT/api-tester/wheels"
mkdir -p "$ha_wheels" "$tester_wheels"
rm -f "$ha_wheels"/idm_heatpump_api-*.whl "$tester_wheels"/idm_heatpump_api-*.whl
cp "$wheel_path" "$ha_wheels/"
cp "$wheel_path" "$tester_wheels/"
ok "Wheel staged for HA + api-tester"

# --- 3. Seed HA config_entries storage (deterministic) ----------------------
step "Seeding homeassistant/.storage/core.config_entries"
idm_host="$(envor IDM_HOST 192.0.2.10)"
web_pin="$(envor IDM_WEB_PIN "")"
entry_title="$(envor HA_ENTRY_TITLE "IDM Heatpump")"
scan_iv="$(envor HA_SCAN_INTERVAL 30)"
hide_unused="$(envor HA_HIDE_UNUSED "")"
circuits="$(envor HA_HEATING_CIRCUITS "a")"
python3 - "$ROOT/homeassistant/config/.storage" "$idm_host" "$web_pin" "$entry_title" "$scan_iv" "$hide_unused" "$circuits" <<'PY'
import json
import sys
from pathlib import Path

storage_dir, idm_host, web_pin, entry_title, scan_iv, hide_unused, circuits = sys.argv[1:]
storage_dir = Path(storage_dir)
storage_dir.mkdir(parents=True, exist_ok=True)
# Stable entry_id / unique_id so reloads keep entity registries.
entry_id = "01JULY2026-IDM-TEST-000000000001"
entry = {
    "entry_id": entry_id,
    "version": 1,
    "minor_version": 3,
    "domain": "idm_heatpump",
    "title": entry_title,
    "data": {
        "host": "modbus-proxy",
        "port": 5020,
        "slave_id": 1,
        "name": entry_title,
        "modbus_proxy": False,
        "web_host": "web-proxy",
        "web_pin": web_pin,
        "model_override": "auto",
    },
    "options": {
        "scan_interval": int(scan_iv),
        "hide_unused_registers": hide_unused.lower() == "true",
        "heating_circuits": [c.strip() for c in circuits.split(",") if c.strip()],
        "zone_count": 0,
        "device_hierarchy": True,
        "short_cycle_minutes": 15,
        "enable_cascade": False,
        "web_extra_data": web_pin != "",
        "web_scan_interval": 300,
        "room_temp_forwarding": False,
        "room_temp_forwarding_interval": 300,
        "room_temp_forwarding_tolerance": 0.2,
        "modbus_timeout": 10.0,
        "modbus_retries": 3,
    },
    "pref_disable_new_entities": False,
    "pref_disable_polling": False,
    "source": "user",
    "unique_id": f"idm-live-ro-test-{idm_host}",
    "disabled_by": None,
}
storage = {
    "version": 1,
    "minor_version": 1,
    "key": "core.config_entries",
    "data": {"entries": [entry]},
}
(storage_dir / "core.config_entries").write_text(
    json.dumps(storage, separators=(",", ":")), encoding="utf-8"
)
print(entry_id)
PY
ok "Sealed config entry (PIN only inside .storage/, which is gitignored)"

# --- 4. Write the resolved wheel name into .env (for compose build arg) -----
if grep -qE '^\s*API_WHEEL\s*=' "$ENV_FILE"; then
  sed -i.bak -E "s|^\s*API_WHEEL\s*=.*|API_WHEEL=$wheel_name|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
else
  printf '\nAPI_WHEEL=%s\n' "$wheel_name" >> "$ENV_FILE"
fi

# --- 5. Build docker images -------------------------------------------------
step "Building docker images (modbus-proxy, web-proxy, homeassistant, api-tester)"
(cd "$ROOT" && docker compose build)

# --- 6. Record build provenance ---------------------------------------------
mkdir -p "$ROOT/results"
python3 - "$ROOT/results/build_provenance.json" "$wheel_name" "$wheel_hash" "$IDM_API_REPO" "$idm_host" <<'PY'
import datetime
import json
import sys
from pathlib import Path

target, wheel_name, wheel_hash, api_repo, idm_host = sys.argv[1:]
Path(target).write_text(
    json.dumps(
        {
            "built_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "api_wheel": wheel_name,
            "api_wheel_sha256": wheel_hash,
            "api_repo": api_repo,
            "idm_host": idm_host,
            "entry_id": "01JULY2026-IDM-TEST-000000000001",
            "unique_id": f"idm-live-ro-test-{idm_host}",
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY

ok "Build complete."
echo "  Next: ./scripts/start.sh   (then ./scripts/run_probe.sh bootstrap)"
