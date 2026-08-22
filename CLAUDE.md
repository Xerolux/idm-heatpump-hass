# CLAUDE.md — IDM Heatpump for Home Assistant

This file is a short pointer for Claude-compatible agents.

**Canonical agent guidance:** see [`AGENTS.md`](AGENTS.md).

## Snapshot (keep in sync with `manifest.json`)

- **Domain**: `idm_heatpump`
- **Version**: `0.15.0-beta.2` (previous stable: `0.14.1`)
- **Min HA**: 2026.8.1
- **Python**: 3.13+
- **Dependencies**: `modbus-connection==4.8.1`, `tmodbus[async-serial]==0.5.1`,
  `pymodbus>=3.12.1,<4.0` (API compatibility), `idm-heatpump-api[web]==1.0.2`
- **Platforms**: sensor, binary_sensor, number, select, switch, climate, water_heater, button
- **Transports**: Modbus TCP through `modbus-connection`/tmodbus (primary) + optional local Navigator web supplement / web-only mode
- **Active roadmap**: `docs/dev/heatpump-feature-roadmap.md`
- **Open work audit**: `docs/dev/open-work-audit.md`
- **Component model evaluation**: `docs/dev/component-model-evaluation.md`

**Language:** write everything in English — changelog, docs, commit messages,
pull request text, comments. German belongs only in `README_de.md` and the Home
Assistant `de` translations; `tests/test_documentation_language.py` enforces it.

Keep protocol semantics and register maps in `idm-heatpump-api`; the local
`modbus_client.py` is only the pin-specific raw-I/O bridge to tmodbus.
