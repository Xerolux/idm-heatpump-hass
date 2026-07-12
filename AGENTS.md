# AGENTS.md — IDM Heatpump for Home Assistant

This file provides guidance for AI assistants working on this codebase.

## Project Overview

**IDM Heatpump** is a Home Assistant custom integration for controlling and monitoring IDM Navigator 2.0 / 10 / Pro heat pumps via Modbus TCP and an optional local web supplement. It is an unofficial community project providing 100% local control (no cloud dependency).

- **Domain**: `idm_heatpump`
- **Current Version**: `0.8.2` (defined in `custom_components/idm_heatpump/manifest.json`)
- **Quality Scale**: Gold (targets official Home Assistant Core integration standards)
- **License**: MIT
- **Min HA Version**: 2026.5.0
- **Python**: 3.13+
- **Key Dependencies**: `pymodbus >= 3.12.1, < 4.0`, `idm-heatpump-api[web] == 0.7.6`

---

## Repository Structure

```
/
├── custom_components/idm_heatpump/   # Main integration package
│   ├── __init__.py                   # Domain setup, platform loading, entry lifecycle
│   ├── manifest.json                 # Integration metadata & HA version requirements
│   ├── const.py                      # Constants, enums, option keys, defaults
│   ├── config_flow.py                # UI config flow (user, options, zones, reconfigure, web-only fallback)
│   ├── coordinator.py                # DataUpdateCoordinator (polling, web supplement, writes)
│   ├── entity.py                     # Base entity class (IdmEntity)
│   ├── sensor.py                     # Sensor platform (Modbus + web-only sensors + technician codes)
│   ├── binary_sensor.py              # Binary sensor platform
│   ├── number.py                     # Number platform (setpoints, GLT values)
│   ├── select.py                     # Select platform (mode registers)
│   ├── switch.py                     # Switch platform (boolean writable registers)
│   ├── services.py                   # Custom HA services (set_system_mode, acknowledge_errors, write_register)
│   ├── services.yaml                 # Service schema definitions
│   ├── diagnostics.py                # HA diagnostics export
│   ├── repairs.py                    # Repair flows (e.g. missing web PIN)
│   ├── registers.py                  # Collects entity descriptions from idm-heatpump-api
│   ├── library_adapter.py            # Adapter between idm-heatpump-api and HA EntityDescriptions
│   ├── adapter_descriptions.py       # HA description helpers (icons, device classes)
│   ├── adapter_enums.py              # Enum slug maps and translation keys
│   ├── adapter_registers.py          # Register-map filtering by model
│   ├── adapter_glt.py                # GLT measurement detection helpers
│   ├── web_data.py                   # Optional local Navigator web supplement client
│   ├── room_temp_forwarding.py       # Forward HA room temperatures to GLT registers
│   ├── technician_codes.py           # Time-based Fachmann Ebene code calculation
│   ├── internal_messages.py          # Human-readable labels for internal message codes
│   ├── log_filter.py                 # Filters noisy pymodbus ERROR log records
│   ├── icons.json                    # Entity icon mappings
│   ├── strings.json                  # UI strings for config flow & services
│   ├── quality_scale.yaml            # Gold-scale compliance documentation
│   └── translations/
│       ├── de.json                   # German translations
│       └── en.json                   # English translations
│
├── tests/                            # Pytest test suite
│   ├── conftest.py                   # Shared fixtures, HA mocks, pymodbus/idm-heatpump-api stubs
│   ├── test_init.py
│   ├── test_config_flow.py
│   ├── test_const.py
│   ├── test_coordinator.py
│   ├── test_diagnostics.py
│   ├── test_entity.py
│   ├── test_library_client.py
│   ├── test_log_filter.py
│   ├── test_platforms.py
│   ├── test_registers.py
│   ├── test_repairs.py
│   ├── test_room_temp_forwarding.py
│   ├── test_services.py
│   ├── test_web_data.py
│   ├── test_adapter_helpers.py
│   ├── test_cross_repo_contract.py
│   └── test_release_contract.py
│
├── docs/                             # Documentation & wiki
│   ├── wiki/                         # Complete wiki (installation, config, entities...)
│   ├── CONTRIBUTING.md
│   ├── CHANGELOG.md
│   ├── SECURITY.md
│   └── CODE_OF_CONDUCT.md
│
├── .github/
│   ├── workflows/                    # CI/CD workflows
│   └── ISSUE_TEMPLATE/
│
├── hacs.json                         # HACS configuration
├── mypy.ini                          # Strict mypy config
├── pytest.ini                        # Pytest config
└── README.md                         # Main README (German + English)
```

---

## Architecture

```
Home Assistant
    │
    ├── IdmCoordinator (DataUpdateCoordinator) [coordinator.py]
    │       │
    │       ├── IdmModbusClient (from idm-heatpump-api, wrapped via library_adapter.py)
    │       │
    │       ├── Entity Descriptions from registers.py / library_adapter.py
    │       │
    │       └── Optional IdmWebSupplement (web_data.py)
    │
    ├── Platforms: sensor, binary_sensor, number, select, switch
    │       └── All extend IdmEntity [entity.py] → CoordinatorEntity
    │
    ├── Services [services.py]
    │       ├── set_system_mode
    │       ├── acknowledge_errors
    │       └── write_register
    │
    ├── Repairs [repairs.py]
    │       └── web_pin_missing
    │
    └── Diagnostics [diagnostics.py]
```

### Key Design Patterns

1. **Entity Inheritance**: All Modbus-backed entities extend `IdmEntity` (from `entity.py`), which extends `CoordinatorEntity`. Web-only sensors extend `CoordinatorEntity` directly.

2. **Library-first Register Definitions**: Register metadata (address, data type, read/write, etc.) is sourced from `idm-heatpump-api`. The integration enriches it with German names, icons, device classes, and translation keys via `library_adapter.py`.

3. **Batch Reading**: The library groups consecutive register addresses into batches for efficient Modbus TCP reads.

4. **Resilient Polling**: `IdmCoordinator._async_read_registers_resilient()` bisects register ranges on Modbus exception code 2 (`Illegal Data Address`) so unsupported optional registers are isolated without breaking the whole poll.

5. **Async I/O**: All Modbus and web communication is async. The library handles connection locking internally.

6. **Optimistic Updates**: Write operations update the coordinator data immediately before the device confirms the change.

7. **Web-only Mode**: When Modbus is unavailable but a local web PIN is configured, the integration can run in a web-only fallback that exposes sensors from the Navigator's local web interface.

---

## Modbus Register System

Registers are sourced from `idm-heatpump-api` and support the data types defined there (typically `FLOAT`, `UCHAR`, `INT16`, `UINT16`, `BOOL`, `BITFLAG`).

- **Read**: function code 03 (handled by the library)
- **Write**: function code 16 (handled by the library)
- **Batch size**: configured by the library
- **Local filtering**: `adapter_registers.py` removes registers known to be unsupported on a specific Navigator family (e.g. Navigator 2.0).

Never hardcode Modbus register addresses in platform files. Service-specific registers that do not exist in the library map should be defined as constants in `const.py` and referenced from there.

---

## Development Commands

### Running Tests
```bash
pytest tests/
```
The `pytest.ini` disables `homeassistant` and `socket` plugins. Tests use stubs from `conftest.py` for `pymodbus`, `idm-heatpump-api`, and the entire Home Assistant package tree.

### Type Checking
```bash
mypy custom_components/idm_heatpump/
```
The project uses **strict mypy** (`strict=true` in `mypy.ini`) with `allow_subclassing_any=true` for HA compatibility.

### Linting
```bash
ruff check custom_components tests
```

### CI/CD (GitHub Actions)
- **validate.yml**: Runs pytest and mypy
- **hacs-validation.yml**: HACS compatibility check
- **hassfest-validation.yml**: Home Assistant integration validator
- **release.yml**: Creates ZIP release artifacts
- **wiki-sync.yml**: Syncs `docs/wiki/` to GitHub Wiki

---

## Code Conventions

### Python Style
- `from __future__ import annotations` at the top of every file
- Full type annotations everywhere (strict mypy)
- Async functions named `async_<action>()` (e.g. `async_update`, `async_setup_entry`)
- Private methods/attributes prefixed with `_`
- Constants in `UPPER_CASE`
- Enums inherit from `enum.IntEnum` or `enum.IntFlag`
- Use `math.isnan(x)` instead of `x != x` for NaN checks

### Adding New Entities

1. **Ensure the register exists in `idm-heatpump-api`** or is generated by `library_adapter.py`.
2. **Add rich metadata** (German name, icon, device class) in `library_adapter.py` / `adapter_descriptions.py` if needed.
3. **Add translations** to `translations/en.json` and `translations/de.json`.
4. **Add icon** to `icons.json` if not using a default.
5. **Write tests** in `tests/test_platforms.py` or the relevant test file.

### Adding New Services

1. Define the schema in `services.yaml`.
2. Implement handler in `services.py`.
3. Add translations to `strings.json`, `translations/en.json`, `translations/de.json`.
4. Write tests in `tests/test_services.py`.

### Error Handling
- Connection failures → `ir.async_create_issue()` with `IssueSeverity.WARNING`
- Write failures → raise `HomeAssistantError` with a translation key
- Invalid parameters → raise `ServiceValidationError`
- Never swallow exceptions silently
- Catch `Exception`, not `BaseException`, unless there is a very specific reason

### Versioning
- Version is defined **only** in `custom_components/idm_heatpump/manifest.json`
- Bump version there before creating a release and update `CHANGELOG.md`
- Pin the `idm-heatpump-api` requirement for every released integration version to the exact PyPI version that is current at release time or has been explicitly tested for that release. Do not publish a release with an open-ended API lower bound such as `idm-heatpump-api>=x.y.z`; the integration release and API version must remain a reproducible pair.
- When updating to a newer `idm-heatpump-api`, verify compatibility before widening or changing the pin, then document the tested API version in the changelog/release notes.

---

## Configuration Flow

The config flow (defined in `config_flow.py`) has these steps:

1. **user**: Integration name, host, port, slave ID, optional web PIN, Modbus proxy / web host
2. **options**: Scan interval, hide unused registers, heating circuits, zone count, cascade, web settings, room temperature forwarding, Modbus timeout/retries
3. **zones**: Room count per zone (up to `MAX_ZONE_COUNT` zones × `MAX_ROOM_COUNT` rooms)
4. **modbus_failed**: Fallback step offering web-only mode when Modbus connection fails but a web PIN is configured
5. **reconfigure**: Update connection settings without removing the integration
6. **options_flow**: Re-run options after setup

---

## Special Features

| Feature | File | Notes |
|---------|------|-------|
| Technician codes | `technician_codes.py` | Time-based Fachmann Ebene L1/L2 codes, refreshed every 60s |
| Cascade support | `adapter_registers.py`, `coordinator.py` | Optional registers for multi-heatpump setups |
| Zone management | `config_flow.py`, `library_adapter.py` | Up to 10 zones × 8 rooms |
| Web supplement | `web_data.py`, `coordinator.py` | Optional local Navigator web data (Nav 2.0 / Nav 10 / Pro) |
| Web-only fallback | `__init__.py`, `config_flow.py` | Runs without Modbus when only web access is available |
| Room temp forwarding | `room_temp_forwarding.py` | Forwards HA room sensor temps to GLT registers |
| Bitflag decoding | `adapter_enums.py`, `sensor.py` | Renders human-readable strings like "Heating\|Water\|Defrosting" |
| Diagnostics export | `diagnostics.py` | Redacts host/port/slave for privacy |
| Unused register filtering | `entity.py`, `coordinator.py` | Entities become unavailable when their register indicates "unused" |
| Repair issues | `repairs.py`, `coordinator.py` | User-fixable issues (e.g. missing web PIN) |
| pymodbus log filter | `log_filter.py` | Suppresses routine connection-drop ERROR spam |

---

## Testing Infrastructure

- **No real HA installation required**: `conftest.py` stubs the entire `homeassistant` package tree, `pymodbus`, and `idm-heatpump-api`.
- **Async tests**: `pytest-asyncio` with `asyncio_mode = auto`.
- **Cross-platform**: Event loop policy supports both Windows and Linux.
- Tests correspond 1:1 (or close to it) with integration modules.

---

## Important Constraints

- **Do not push to `master` or `main`** — all development should happen on feature branches (`Codex/...`).
- **Do not add cloud/external API calls** — this integration is intentionally 100% local.
- **Do not skip type hints** — mypy strict mode will fail CI.
- **Do not hardcode register addresses** in platform files — reference `const.py` or `registers.py`.
- **Do not write to EEPROM-sensitive registers** without proper guards.
- **Keep entity names consistent** with `strings.json` and `translations/`.
- **Test new functionality** — untested code will not pass CI on the main branch.

---

## File Relationships Quick Reference

| If you change... | Also update... |
|-----------------|----------------|
| `registers.py` / `library_adapter.py` | Platform files, tests, `icons.json` |
| `config_flow.py` | `strings.json`, translations, `test_config_flow.py` |
| `services.py` | `services.yaml`, `strings.json`, translations, `test_services.py` |
| `web_data.py` | `test_web_data.py`, `repairs.py` |
| `coordinator.py` | `test_coordinator.py` |
| Any entity | `icons.json`, translations, `test_platforms.py` |
| `manifest.json` (version) | `CHANGELOG.md`, release notes |
| `AGENTS.md` (this file) | Keep it in sync with the actual codebase |
