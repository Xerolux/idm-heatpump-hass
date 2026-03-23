# CLAUDE.md — IDM Heatpump for Home Assistant

This file provides guidance for AI assistants working on this codebase.

## Project Overview

**IDM Heatpump** is a Home Assistant custom integration for controlling and monitoring IDM Navigator 2.0 heat pumps via Modbus TCP. It is an unofficial community project providing 100% local control (no cloud dependency).

- **Domain**: `idm_heatpump`
- **Current Version**: `0.2.9` (defined in `custom_components/idm_heatpump/manifest.json`)
- **Quality Scale**: Gold (targets official Home Assistant Core integration standards)
- **License**: MIT
- **Min HA Version**: 2025.12.0
- **Python**: 3.13+
- **Key Dependency**: `pymodbus >= 3.12.1`

---

## Repository Structure

```
/
├── custom_components/idm_heatpump/   # Main integration package
│   ├── __init__.py                   # Setup, platform loading, entry lifecycle
│   ├── manifest.json                 # Integration metadata & HA version requirements
│   ├── const.py                      # Constants & enums (SystemMode, CircuitMode, etc.)
│   ├── coordinator.py                # DataUpdateCoordinator (polling logic)
│   ├── modbus_client.py              # Async Modbus TCP client (pymodbus wrapper)
│   ├── registers.py                  # 663 Modbus register definitions (959 lines)
│   ├── config_flow.py                # UI config flow (5 steps)
│   ├── entity.py                     # Base entity class (IdmEntity)
│   ├── sensor.py                     # Sensor platform (100+ entities)
│   ├── binary_sensor.py              # Binary sensor platform (9 entities)
│   ├── number.py                     # Number platform (~30 entities)
│   ├── select.py                     # Select platform (~15 entities)
│   ├── switch.py                     # Switch platform (4 entities)
│   ├── services.py                   # Custom HA services (3 services)
│   ├── diagnostics.py                # HA diagnostics export
│   ├── technician_codes.py           # Time-based Fachmann Ebene code calculation
│   ├── icons.json                    # Entity icon mappings
│   ├── strings.json                  # UI strings for config flow & services
│   ├── services.yaml                 # Service schema definitions
│   ├── quality_scale.yaml            # Gold-scale compliance documentation
│   └── translations/
│       ├── de.json                   # German translations
│       └── en.json                   # English translations
│
├── tests/                            # Pytest test suite
│   ├── conftest.py                   # Shared fixtures, HA mocks, pymodbus stubs
│   ├── test_init.py
│   ├── test_config_flow.py
│   ├── test_const.py
│   ├── test_coordinator.py
│   ├── test_diagnostics.py
│   ├── test_entity.py
│   ├── test_modbus_client.py
│   ├── test_platforms.py
│   ├── test_registers.py
│   └── test_services.py
│
├── docs/                             # Documentation & wiki
│   ├── wiki/                         # Complete wiki (installation, config, entities...)
│   ├── CONTRIBUTING.md
│   ├── CHANGELOG.md
│   ├── SECURITY.md
│   └── CODE_OF_CONDUCT.md
│
├── .github/
│   ├── workflows/                    # 13 CI/CD workflows
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
    │       ├── IdmModbusClient [modbus_client.py]
    │       │       └── AsyncModbusTcpClient (pymodbus)
    │       │
    │       └── Entity Descriptions from registers.py
    │
    ├── Platforms: sensor, binary_sensor, number, select, switch
    │       └── All extend IdmEntity [entity.py] → CoordinatorEntity
    │
    ├── Services [services.py]
    │       ├── set_system_mode
    │       ├── acknowledge_errors
    │       └── write_register
    │
    └── Diagnostics [diagnostics.py]
```

### Key Design Patterns

1. **Entity Inheritance**: All entities extend `IdmEntity` (from `entity.py`), which extends `CoordinatorEntity`. This centralizes device info, availability logic, and unused-register filtering.

2. **Declarative Register Definitions** (`registers.py`): Each register is defined with address, data type, read/write access, and metadata. Never hardcode register addresses in platform files.

3. **Batch Reading**: Consecutive register addresses are grouped into batches (max 30 registers) for efficient Modbus TCP reads.

4. **Async I/O**: All Modbus communication is async. A lock in `modbus_client.py` prevents concurrent access.

5. **Optimistic Updates**: Write operations update the UI immediately before confirming the device acknowledged the change.

---

## Modbus Register System

Registers are defined in `registers.py` and support 7 data types:

| Type | Description | Size |
|------|-------------|------|
| `FLOAT` | IEEE 754 float | 2 registers |
| `UCHAR` | 8-bit unsigned int | 1 register |
| `INT8` | 8-bit signed int | 1 register |
| `INT16` | 16-bit signed int | 1 register |
| `UINT16` | 16-bit unsigned int | 1 register |
| `BOOL` | Boolean flag | 1 register |
| `BITFLAG` | Bitfield with human-readable decoding | 1+ registers |

- **Read-only registers**: function code 03
- **Write**: function code 16 (write multiple registers)
- **EEPROM-sensitive registers** are tracked separately to prevent wear
- Batch size: max 30 registers per Modbus request

---

## Development Commands

### Running Tests
```bash
pytest tests/
```
The `pytest.ini` disables `homeassistant` and `socket` plugins. Tests use stubs from `conftest.py` for pymodbus and the entire Home Assistant package tree.

### Type Checking
```bash
mypy custom_components/idm_heatpump/
```
The project uses **strict mypy** (`strict=true` in `mypy.ini`) with `allow_subclassing_any=true` for HA compatibility.

### CI/CD (GitHub Actions)
- **validate.yml**: Runs pytest on Python 3.14 + HA 2026.3.1
- **hacs-validation.yml**: HACS compatibility check
- **hassfest-validation.yml**: Home Assistant integration validator
- **release.yml**: Creates ZIP release artifacts
- **wiki-sync.yml**: Syncs `docs/wiki/` to GitHub Wiki

---

## Code Conventions

### Python Style
- `from __future__ import annotations` at the top of every file
- Full type annotations everywhere (strict mypy)
- Async functions named `async_<action>()` (e.g., `async_update`, `async_setup_entry`)
- Private methods/attributes prefixed with `_`
- Constants in `UPPER_CASE`
- Enums inherit from `enum.IntEnum` or `enum.IntFlag`

### Adding New Entities

1. **Define the register** in `registers.py` — add address, data type, access flags, name, and unit.
2. **Add to the appropriate platform** (`sensor.py`, `number.py`, etc.) using the standard entity description dataclass pattern.
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

### Versioning
- Version is defined **only** in `custom_components/idm_heatpump/manifest.json`
- Bump version there before creating a release

---

## Configuration Flow

The config flow has 5 steps (defined in `config_flow.py`):

1. **user**: Host, port, slave ID, integration name
2. **options**: Scan interval, number of circuits/zones, cascade support, technician codes
3. **zones**: Room count per zone (up to 10 zones × 8 rooms)
4. **reconfigure**: Update connection settings without removing integration
5. **options_flow**: Re-run options after setup

---

## Special Features

| Feature | File | Notes |
|---------|------|-------|
| Technician codes | `technician_codes.py` | Time-based Fachmann Ebene L1/L2 codes, updated every 60s |
| Cascade support | `registers.py`, `coordinator.py` | Optional registers for multi-heatpump setups |
| Zone management | `config_flow.py`, `registers.py` | Up to 10 zones × 8 rooms |
| EEPROM protection | `registers.py`, `modbus_client.py` | Tracks write-sensitive registers |
| Bitflag decoding | `modbus_client.py` | Renders human-readable strings like "Heating\|Water\|Defrosting" |
| Diagnostics export | `diagnostics.py` | Redacts host/port for privacy |
| Unused register filtering | `entity.py` | Entities become unavailable when their register isn't in the polled data |

---

## Testing Infrastructure

- **No real HA installation required**: `conftest.py` stubs the entire `homeassistant` package tree and `pymodbus`.
- **Async tests**: `pytest-asyncio` with `asyncio_mode = auto`.
- **Cross-platform**: Event loop policy supports both Windows and Linux.
- All 11 test files correspond 1:1 to integration modules.

---

## Important Constraints

- **Do not push to `master` or `main`** — all development should happen on feature branches (`claude/...`).
- **Do not add cloud/external API calls** — this integration is intentionally 100% local.
- **Do not skip type hints** — mypy strict mode will fail CI.
- **Do not hardcode register addresses** in platform files — always reference `registers.py`.
- **Do not write to EEPROM-sensitive registers** without proper guards.
- **Keep entity names consistent** with `strings.json` and `translations/`.
- **Test new functionality** — untested code will not pass CI on the main branch.

---

## File Relationships Quick Reference

| If you change... | Also update... |
|-----------------|----------------|
| `registers.py` | Platform files that reference new registers, tests |
| `config_flow.py` | `strings.json`, translations, `test_config_flow.py` |
| `services.py` | `services.yaml`, `strings.json`, translations, `test_services.py` |
| Any entity | `icons.json`, translations, `test_platforms.py` |
| `manifest.json` (version) | `CHANGELOG.md`, release notes |
| `modbus_client.py` | `test_modbus_client.py` |
| `coordinator.py` | `test_coordinator.py` |
