# CLAUDE.md — IDM Heatpump for Home Assistant

This file is a short pointer for Claude-compatible agents.

**Canonical agent guidance:** see [`AGENTS.md`](AGENTS.md).

## Snapshot (keep in sync with `manifest.json`)

- **Domain**: `idm_heatpump`
- **Version**: `0.12.0` (previous stable: `0.11.1`)
- **Min HA**: 2026.8.1
- **Python**: 3.13+
- **Dependencies**: `modbus-connection==4.0.0a3`, `tmodbus==0.5.0`,
  `pymodbus>=3.12.1,<4.0` (API compatibility), `idm-heatpump-api[web]==1.0.0`
- **Platforms**: sensor, binary_sensor, number, select, switch, climate, water_heater, button
- **Transports**: Modbus TCP through `modbus-connection`/tmodbus (primary) + optional local Navigator web supplement / web-only mode
- **Active roadmap**: `docs/dev/heatpump-feature-roadmap.md`
- **Open work audit**: `docs/dev/open-work-audit.md`

Keep protocol semantics and register maps in `idm-heatpump-api`; the local
`modbus_client.py` is only the pin-specific raw-I/O bridge to tmodbus.
