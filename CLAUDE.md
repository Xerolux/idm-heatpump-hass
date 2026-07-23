# CLAUDE.md — IDM Heatpump for Home Assistant

This file is a short pointer for Claude-compatible agents.

**Canonical agent guidance:** see [`AGENTS.md`](AGENTS.md).

## Snapshot (keep in sync with `manifest.json`)

- **Domain**: `idm_heatpump`
- **Version**: `0.8.5` (stable; see `docs/release-evidence/0.8.5-beta.8.md` for the latest pre-stable candidate evidence)
- **Min HA**: 2026.5.0
- **Python**: 3.13+
- **Dependencies**: `pymodbus>=3.12.1,<4.0`, `idm-heatpump-api[web]==0.8.4`
- **Platforms**: sensor, binary_sensor, number, select, switch, climate, water_heater, button
- **Transports**: Modbus TCP (primary) + optional local Navigator web supplement / web-only mode
- **Active roadmap**: `docs/dev/heatpump-feature-roadmap.md`
- **Open work audit**: `docs/dev/open-work-audit.md`

Do not reintroduce a local `modbus_client.py`; protocol and register maps live in `idm-heatpump-api`.
