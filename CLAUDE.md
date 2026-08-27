# CLAUDE.md — IDM Heatpump for Home Assistant

This file is a short pointer for Claude-compatible agents.

**Canonical agent guidance:** see [`AGENTS.md`](AGENTS.md).

## Snapshot (keep in sync with `manifest.json`)

- **Domain**: `idm_heatpump`
- **Version**: `0.16.0-rc.3` (previous stable: `0.15.1`; the `0.15.1` line was the last with pymodbus)
- **Min HA**: 2026.8.1
- **Python**: 3.14+ (Home Assistant 2026.8 requires 3.14.2)
- **Dependencies**: `modbus-connection==4.10.0`, `tmodbus[async-serial]==0.6.1`,
  `idm-heatpump-api[web]==2.0.0`
- **Platforms**: sensor, binary_sensor, number, select, switch, climate, water_heater, button
- **Transports**: Modbus TCP through `modbus-connection`/tmodbus (primary) + optional local Navigator web supplement / web-only mode
- **Optional KNX bridge**: serves the IDM KNX communication objects through the
  Home Assistant `knx` integration (`knx_bridge.py`, `knx_catalog.py`). Never add
  a KNX stack here — KNX Secure, tunnelling and routing belong to that integration.
- **Active roadmap**: `docs/dev/heatpump-feature-roadmap.md`
- **Open work audit**: `docs/dev/open-work-audit.md`
- **Component model evaluation**: `docs/dev/component-model-evaluation.md`

**Language:** write everything in English — changelog, docs, commit messages,
pull request text, comments. German belongs only in `README_de.md` and the Home
Assistant `de` translations; `tests/test_documentation_language.py` enforces it.

Keep protocol semantics and register maps in `idm-heatpump-api`; the local
`modbus_client.py` is only the pin-specific raw-I/O bridge to tmodbus.
