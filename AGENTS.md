# AGENTS.md — IDM Heatpump for Home Assistant

This file provides guidance for AI assistants working on this codebase.

## Project Overview

**IDM Heatpump** is a Home Assistant custom integration for controlling and monitoring IDM Navigator 2.0 / 10 / Pro heat pumps via Modbus TCP and an optional local web supplement. It is an unofficial community project providing 100% local control (no cloud dependency).

- **Domain**: `idm_heatpump`
- **Current Version**: `0.16.0-beta.1` (defined in `custom_components/idm_heatpump/manifest.json`; previous stable: `0.15.1`, the last line with pymodbus)
- **Quality Scale**: Gold (targets official Home Assistant Core integration standards)
- **License**: MIT
- **Min HA Version**: 2026.8.1
- **Python**: 3.13+
- **Direct Modbus Runtime**: `modbus-connection==4.10.0`, `tmodbus[async-serial]==0.6.1`
- **Device Logic**: `idm-heatpump-api[web]==2.0.0b1` (owns its own exception hierarchy; pymodbus is no longer a dependency)

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
│   ├── climate.py                    # Climate platform (heating circuits, zone-module rooms)
│   ├── water_heater.py               # Water heater platform (DHW setpoint)
│   ├── button.py                     # Button platform (acknowledge errors)
│   ├── services.py                   # Custom HA services (set_system_mode, acknowledge_errors, write_register)
│   ├── services.yaml                 # Service schema definitions
│   ├── diagnostics.py                # HA diagnostics export
│   ├── repairs.py                    # Repair flows (e.g. missing web PIN)
│   ├── registers.py                  # Collects entity descriptions from idm-heatpump-api
│   ├── library_adapter.py            # Adapter between idm-heatpump-api and HA EntityDescriptions
│   ├── modbus_client.py              # API client adapter routing raw I/O through the local transport
│   ├── modbus_transport.py           # Backend-neutral contract + modbus-connection/tmodbus implementation
│   ├── versions.py                   # Runtime dependency versions for logs, sensors, and diagnostics
│   ├── adapter_descriptions.py       # HA description helpers (icons, device classes)
│   ├── adapter_enums.py              # Enum slug maps and translation keys
│   ├── adapter_registers.py          # Register-map filtering by model
│   ├── adapter_glt.py                # GLT measurement detection helpers
│   ├── web_data.py                   # Optional local Navigator web supplement client
│   ├── room_temp_forwarding.py       # Forward HA room temperatures (per circuit) and humidity (global) to GLT registers
│   ├── technician_codes.py           # Time-based Fachmann Ebene code calculation
│   ├── internal_messages.py          # Human-readable labels for internal message codes
│   ├── log_filter.py                 # Filters repeated idm-heatpump-api register-failure warnings
│   ├── icons.json                    # Entity icon mappings
│   ├── strings.json                  # UI strings for config flow & services
│   ├── quality_scale.yaml            # Gold-scale compliance documentation
│   └── translations/
│       ├── de.json                   # German translations
│       └── en.json                   # English translations
│
├── tests/                            # Pytest test suite
│   ├── conftest.py                   # Shared fixtures and HA/API/Modbus runtime stubs
│   ├── test_init.py
│   ├── test_config_flow.py
│   ├── test_const.py
│   ├── test_coordinator.py
│   ├── test_diagnostics.py
│   ├── test_entity.py
│   ├── test_library_client.py
│   ├── test_log_filter.py
│   ├── test_platforms.py
│   ├── test_platforms_climate.py
│   ├── test_registers.py
│   ├── test_repairs.py
│   ├── test_room_temp_forwarding.py
│   ├── test_humidity_forwarding.py
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
    │       ├── IdmModbusConnectionClient (modbus_client.py)
    │       │       ├── idm-heatpump-api 0.9.1 (device logic)
    │       │       └── ModbusConnectionTransport (modbus-connection + tmodbus socket)
    │       │
    │       ├── Entity Descriptions from registers.py / library_adapter.py
    │       │
    │       └── Optional IdmWebSupplement (web_data.py)
    │
    ├── Platforms: sensor, binary_sensor, number, select, switch,
    │              climate, water_heater, button
    │       ├── sensor/binary_sensor/number/select/switch extend IdmEntity [entity.py]
    │       │   → CoordinatorEntity (register-backed, unused-register filtering)
    │       └── climate/water_heater/button extend CoordinatorEntity (+ shared device_info)
    │           (multi-register or action entities)
    │
    ├── Services [services.py]
    │       ├── set_system_mode
    │       ├── acknowledge_errors
    │       ├── write_register
    │       ├── set_external_climate
    │       └── start_dhw_boost / cancel_dhw_boost
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

5. **Transport Adapter**: `IdmModbusConnectionClient` subclasses the pinned API client and replaces its raw-I/O hooks. Register metadata, batching, decoding, model detection and write safety remain in `idm-heatpump-api`; FC03/FC04/FC16 socket I/O uses `ModbusConnectionTransport` and tmodbus.

6. **Async I/O**: All Modbus and web communication is async. The adapter keeps the API request lock, and `modbus-connection` serializes physical requests and reconnects on demand.

7. **Private Socket Ownership**: Each config entry owns one tmodbus-backed socket. Home Assistant central cross-entry sharing is not available; `supports_shared_connection` must remain `False` until a real shared provider is integrated.

8. **Optimistic Updates**: Write operations update the coordinator data immediately before the device confirms the change.

9. **Web-only Mode**: When Modbus is unavailable but a local web PIN is configured, the integration can run in a web-only fallback that exposes sensors from the Navigator's local web interface.

---

## Modbus Register System

Registers are sourced from `idm-heatpump-api` and support the data types defined there (typically `FLOAT`, `UCHAR`, `INT16`, `UINT16`, `BOOL`, `BITFLAG`).

- **Read input registers**: function code 04 (API chooses the register type; tmodbus performs raw I/O)
- **Read holding registers**: function code 03 (API chooses the register type; tmodbus performs raw I/O)
- **Write holding registers**: function code 16 (encoded and safety-checked by the API, transmitted by tmodbus)
- **Batch size**: configured by the library
- **Local filtering**: `adapter_registers.py` removes registers known to be unsupported on a specific Navigator family (e.g. Navigator 2.0).

Never hardcode Modbus register addresses in platform files. Service-specific registers that do not exist in the library map should be defined as constants in `const.py` and referenced from there.

---

## Development Commands

### Running Tests
```bash
pytest tests/
```
The `pytest.ini` disables `homeassistant` and `socket` plugins. Tests use stubs from `conftest.py` for `modbus-connection`, tmodbus and the entire Home Assistant package tree; `idm-heatpump-api` is installed for real.

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
- **ci.yml**: Runs the python-quality matrix (pytest, mypy, ruff; manifest-pinned + api-main) plus HACS validation and hassfest
- **python-quality.yml**: Reusable workflow (workflow_call) with the actual lint/type/test steps
- **api-dependency-update.yml**: Opens a PR that re-pins `idm-heatpump-api` when a new stable API release is announced
- **dependency-freshness.yml**: Checks the pinned runtime dependencies against PyPI daily and opens a PR that re-pins `modbus-connection`/`tmodbus` to the newest stable release (`scripts/check_dependency_pins.py`)
- **release.yml**: Validates tag/manifest/CHANGELOG, creates ZIP release artifacts, announces in Discussions
- **security.yml**: CodeQL (actions, python) + pip-audit
- **stale.yml**: Marks inactive issues/PRs as stale
- **pages.yml**: Deploys `docs/wiki/` + images to GitHub Pages
- **wiki-sync.yml**: Syncs `docs/wiki/` to the GitHub Wiki

---

## Code Conventions

### Language
- **Write in English.** The changelog, release notes, release evidence, the
  wiki, developer notes, issue and pull request templates, commit messages, pull
  request descriptions, code comments and docstrings are English — including
  when the conversation that produced them was in German.
- German belongs only where it is a product feature: `README_de.md`, the Home
  Assistant `de` translations, and the "Description (DE)" column of the
  generated register reference, which carries IDM's own terminology.
- Released changelog sections stay as published; they are history. The rule
  applies to the unreleased entries and to the section of the version in the
  manifest.
- `python scripts/check_documentation_language.py` reports German prose;
  `tests/test_documentation_language.py` fails the build on it. New documents
  are covered automatically — declare an exception in `EXEMPT_FILES` only for
  documentation that is German on purpose.
- **Text that tooling emits is text this rule covers.** Prose baked into a
  workflow, a script or a template — release notes, issue bodies, generated
  reports — is English too, even though the language checker only reads Markdown
  and cannot see it.

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
- Never bump a runtime pin by hand without checking PyPI first: `python scripts/check_dependency_pins.py` reports every pin that is behind, `--update` rewrites the transport pins and every document that states them. The daily `dependency-freshness.yml` workflow does exactly this and opens a PR; the release workflow refuses to publish stale pins unless `allow_stale_pins` is set. Automation never selects a pre-release for a stable pin — that is how the `4.0.0a3` alpha stayed pinned for two weeks.
- A document that states the current pins belongs in `PIN_DOCUMENTS` in `scripts/check_dependency_pins.py`; `tests/test_dependency_pins.py` fails when a new one is missing there.
- Keep `modbus-connection` and `tmodbus` exactly pinned as a tested transport pair. `4.10.0` is the `modbus-connection` library version, not the integration version. The `tmodbus[async-serial]` extra is required even though this integration is TCP-only: since `modbus-connection` 4.7.0 the `modbus_connection.tmodbus` backend module imports `serialx` at module level, so importing the backend fails without it. Do not drop the extra to save the dependency.
- pymodbus is gone as of `idm-heatpump-api` 2.0.0 / integration 0.16.0. Do not reintroduce it: the API owns `IdmModbusError` and its subclasses, and this integration's transport maps `modbus-connection` errors straight onto them.

#### Prerelease naming

- **The integration uses SemVer tags:** `v0.16.0-beta.1`, `v0.16.0-rc.1`. The
  `manifest.json` version matches the tag without the `v`. This is what HACS and
  Home Assistant read, so it does not change.
- **`idm-heatpump-api` uses PEP 440:** `2.0.0b1`, `2.0.0a1`, `2.0.0rc1` — no
  hyphen, no dot before the number. PyPI normalises `2.0.0-beta.1` to `2.0.0b1`
  anyway, so writing the normalised form is the only way the tag, the
  `pyproject.toml` version, the PyPI filename and the manifest pin all read the
  same. Tag the API repository with the PEP 440 version (`v2.0.0b1`).
- **The manifest pins the PEP 440 form**, because that is what pip resolves:
  `idm-heatpump-api[web]==2.0.0b1`, never `==2.0.0-beta.1`.

#### Release notes

- **Every release carries the support links.** The `Support` section is appended
  by `.github/workflows/release.yml` to both the generated and the curated
  release notes, so passing `release_notes` never drops it. The changelog keeps
  its own support header at the top of `docs/CHANGELOG.md`. Do not remove either
  when reworking release tooling, and keep the four links (GitHub Sponsors,
  Ko-Fi, Buy Me A Coffee, PayPal) in step with `.github/FUNDING.yml`.

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
| tmodbus transport | `modbus_client.py`, `modbus_transport.py` | Default direct socket path; per-entry ownership, no central cross-entry sharing |
| Room temp forwarding | `room_temp_forwarding.py` | Forwards HA room sensor temps (per heating circuit) to GLT registers |
| Humidity forwarding | `room_temp_forwarding.py` | Forwards one HA humidity sensor (global `ext_humidity`) to the GLT humidity register |
| Climate entities | `climate.py` | Heating-circuit + zone-module room climates; routes writes through `coordinator.async_write_register` |
| Water heater entity | `water_heater.py` | DHW target setpoint; only set up when both `dhw_temp_top` and `dhw_setpoint` exist |
| Acknowledge-errors button | `button.py` | One-shot button writing the centralized acknowledge register |
| Bitflag decoding | `adapter_enums.py`, `sensor.py` | Renders human-readable strings like "Heating\|Water\|Defrosting" |
| Diagnostics export | `diagnostics.py` | Redacts host/port/slave for privacy |
| Unused register filtering | `entity.py`, `coordinator.py` | Entities become unavailable when their register indicates "unused" |
| Repair issues | `repairs.py`, `coordinator.py` | User-fixable issues (e.g. missing web PIN) |
| API register-failure log filter | `log_filter.py` | Suppresses repeated retry-exhaustion warnings for unsupported registers |

---

## Testing Infrastructure

- **No real HA installation required**: `conftest.py` stubs the entire `homeassistant` package tree, `modbus-connection` and tmodbus.
- **Async tests**: `pytest-asyncio` with `asyncio_mode = auto`.
- **Cross-platform**: Event loop policy supports both Windows and Linux.
- Tests correspond 1:1 (or close to it) with integration modules.

---

## Important Constraints

- **Do not push to `master` or `main`** — all development should happen on feature branches (`Codex/...`).
- **Do not add cloud/external API calls** — this integration is intentionally 100% local.
- **Do not skip type hints** — mypy strict mode will fail CI.
- **Do not hardcode register addresses** in platform files — reference `const.py` or `registers.py`.
- **Do not bypass `ModbusConnectionTransport`** with a second direct socket path. The current runtime is tmodbus-backed and deliberately reports `supports_shared_connection=False`.
- **Do not write to EEPROM-sensitive registers** without proper guards.
- **Keep real-hardware transport validation read-only** unless the owner explicitly authorizes a specific write.
- **Keep entity names consistent** with `strings.json` and `translations/`.
- **Test new functionality** — untested code will not pass CI on the main branch.
- **Do not write German prose into repository documents** — English is the contract for everything except `README_de.md` and the `de` translations.

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
| Any Markdown document | Keep it English (`scripts/check_documentation_language.py`) |
