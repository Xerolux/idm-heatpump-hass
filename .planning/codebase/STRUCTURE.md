# Codebase Structure

**Analysis Date:** 2026-07-25

## Directory Layout

```text
idm-heatpump-hass/
├── custom_components/
│   └── idm_heatpump/        # Installable Home Assistant integration package
│       ├── brand/           # Integration logo and icon raster assets
│       └── translations/    # Localized config, entity, repair, and service text
├── tests/                   # Fast stub-based unit and contract tests
├── tests_real/              # Tests against real installed HA/library packages
├── docs/
│   ├── dev/                 # Maintainer architecture and migration references
│   ├── examples/            # Example Home Assistant dashboard YAML
│   ├── public/              # Static project website
│   ├── release-evidence/    # Release readiness evidence
│   └── wiki/                # User-facing GitHub Wiki source
├── scripts/                 # Metadata/reference generation and release tooling
├── docker/                  # Development/container support
├── .github/
│   ├── workflows/           # CI, quality, release, pages, and wiki automation
│   └── ISSUE_TEMPLATE/      # Structured issue intake
├── AGENTS.md                # Repository-specific implementation rules
├── manifest.json equivalent # `custom_components/idm_heatpump/manifest.json`
├── mypy.ini                 # Strict Python typing configuration
├── pytest.ini               # Test runner configuration
├── ruff.toml                # Lint/format policy
└── hacs.json                # HACS repository metadata
```

## Directory Purposes

**`custom_components/idm_heatpump/`:**
- Purpose: Contains all code and assets installed into Home Assistant.
- Contains: lifecycle, config flow, coordinator, platform modules, adapters, transports, services, diagnostics, repairs, translations, and metadata.
- Key files: `custom_components/idm_heatpump/__init__.py`, `custom_components/idm_heatpump/coordinator.py`, `custom_components/idm_heatpump/manifest.json`.

**`custom_components/idm_heatpump/translations/`:**
- Purpose: Holds supported localized UI text.
- Contains: matching English and German JSON resources.
- Key files: `custom_components/idm_heatpump/translations/en.json`, `custom_components/idm_heatpump/translations/de.json`.

**`tests/`:**
- Purpose: Runs the main fast suite without requiring a full Home Assistant installation or hardware.
- Contains: module-aligned unit tests, stubs, metadata contracts, release contracts, and cross-repository contracts.
- Key files: `tests/conftest.py`, `tests/test_init.py`, `tests/test_coordinator.py`, `tests/test_platforms.py`.

**`tests_real/`:**
- Purpose: Exercises compatibility against installed real dependencies where stubs could conceal API drift.
- Contains: real-package integration/contract tests.
- Key files: inspect `tests_real/` when changing Home Assistant or `idm-heatpump-api` boundaries.

**`docs/`:**
- Purpose: Stores user documentation, maintainer guidance, examples, static-site content, and release evidence.
- Contains: Markdown, YAML examples, and static web assets.
- Key files: `docs/CHANGELOG.md`, `docs/CONTRIBUTING.md`, `docs/wiki/Home.md`, `docs/RELEASE_PROCESS.md`.

**`scripts/`:**
- Purpose: Generates maintained artifacts and automates release communication.
- Contains: Python command-line tools.
- Key files: `scripts/generate_entity_metadata_catalog.py`, `scripts/generate_modbus_register_reference.py`, `scripts/publish_release_discussion.py`.

**`.github/`:**
- Purpose: Encodes repository automation and contributor intake.
- Contains: Actions workflows, issue/discussion templates, ownership, dependency update policy.
- Key files: `.github/workflows/ci.yml`, `.github/workflows/python-quality.yml`, `.github/workflows/release.yml`.

## Integration Module Groups

**Lifecycle and configuration:**
- `custom_components/idm_heatpump/__init__.py`: config-entry setup, migration, runtime ownership, reload, unload.
- `custom_components/idm_heatpump/config_flow.py`: user and options flows.
- `custom_components/idm_heatpump/const.py`: domain constants, defaults, option keys, enums, exceptional service register constants.
- `custom_components/idm_heatpump/manifest.json`: integration version, dependency pins, Home Assistant requirements.

**Core runtime:**
- `custom_components/idm_heatpump/coordinator.py`: polling, state publication, web merge, write facade.
- `custom_components/idm_heatpump/modbus_transport.py`: capability-based low-level transport adaptation.
- `custom_components/idm_heatpump/polling_plan.py`: polling-set planning and unsupported-register state.
- `custom_components/idm_heatpump/error_messages.py`: user-facing communication error classification.
- `custom_components/idm_heatpump/issues.py`: issue identifiers/repair coordination.

**Register and metadata adaptation:**
- `custom_components/idm_heatpump/registers.py`: platform catalogs, ordering, aliases.
- `custom_components/idm_heatpump/library_adapter.py`: library-to-Home-Assistant description conversion.
- `custom_components/idm_heatpump/adapter_registers.py`: model-specific register filtering.
- `custom_components/idm_heatpump/adapter_descriptions.py`: Home Assistant description properties.
- `custom_components/idm_heatpump/adapter_metadata.py`, `custom_components/idm_heatpump/adapter_names.py`: presentation metadata and naming.
- `custom_components/idm_heatpump/adapter_enums.py`, `custom_components/idm_heatpump/binary_semantics.py`: enum and binary-state semantics.
- `custom_components/idm_heatpump/adapter_glt.py`: GLT register classification.

**Platforms:**
- `custom_components/idm_heatpump/sensor.py`, `custom_components/idm_heatpump/binary_sensor.py`: read-oriented entity platforms.
- `custom_components/idm_heatpump/number.py`, `custom_components/idm_heatpump/select.py`, `custom_components/idm_heatpump/switch.py`: single-register writable platforms.
- `custom_components/idm_heatpump/climate.py`, `custom_components/idm_heatpump/water_heater.py`: multi-register domain entities.
- `custom_components/idm_heatpump/button.py`: one-shot action entities.
- `custom_components/idm_heatpump/entity.py`: shared register-backed entity behavior.
- `custom_components/idm_heatpump/device_hierarchy.py`: device registry parent/child placement.

**Feature modules:**
- `custom_components/idm_heatpump/web_data.py`, `custom_components/idm_heatpump/web_binary_sensors.py`: optional local web supplement.
- `custom_components/idm_heatpump/room_temp_forwarding.py`: Home Assistant sensor-to-GLT forwarding.
- `custom_components/idm_heatpump/dhw_boost.py`, `custom_components/idm_heatpump/dhw_boost_services.py`: domestic-hot-water boost workflow.
- `custom_components/idm_heatpump/operation_analysis.py`, `custom_components/idm_heatpump/operation_entities.py`: derived operational diagnostics.
- `custom_components/idm_heatpump/calculated_sensors.py`: computed sensor values.
- `custom_components/idm_heatpump/technician_codes.py`, `custom_components/idm_heatpump/internal_messages.py`: specialized local interpretations.

**Home Assistant support surfaces:**
- `custom_components/idm_heatpump/services.py`, `custom_components/idm_heatpump/services.yaml`: service implementation and schema.
- `custom_components/idm_heatpump/diagnostics.py`: redacted diagnostic export.
- `custom_components/idm_heatpump/repairs.py`: fixable issue flows.
- `custom_components/idm_heatpump/strings.json`, `custom_components/idm_heatpump/icons.json`: canonical UI strings and icons.
- `custom_components/idm_heatpump/quality_scale.yaml`: Home Assistant quality-scale evidence.

## Key File Locations

**Entry Points:**
- `custom_components/idm_heatpump/__init__.py`: integration and config-entry lifecycle.
- `custom_components/idm_heatpump/config_flow.py`: UI configuration entry point.
- `custom_components/idm_heatpump/{sensor,binary_sensor,number,select,switch,climate,water_heater,button}.py`: platform entry points.

**Configuration:**
- `custom_components/idm_heatpump/manifest.json`: runtime dependencies, version, domain metadata.
- `custom_components/idm_heatpump/const.py`: runtime option names and defaults.
- `mypy.ini`: strict typing.
- `pytest.ini`: async and plugin test settings.
- `ruff.toml`: code-quality rules.

**Core Logic:**
- `custom_components/idm_heatpump/coordinator.py`: central I/O and state.
- `custom_components/idm_heatpump/registers.py`: complete entity/register catalog.
- `custom_components/idm_heatpump/library_adapter.py`: external-library boundary.
- `custom_components/idm_heatpump/web_data.py`: optional local-web boundary.

**Testing:**
- `tests/conftest.py`: shared Home Assistant, pymodbus, and API stubs and fixtures.
- `tests/test_coordinator.py`: coordinator read/write and failure behavior.
- `tests/test_platforms.py`: common entity platform behavior.
- `tests/test_cross_repo_contract.py`: integration/API compatibility contract.
- `tests_real/`: real-dependency validation.

**Documentation:**
- `README.md`, `README_de.md`: repository landing documentation.
- `docs/wiki/`: detailed user documentation source.
- `docs/dev/`: maintainer contracts and architecture notes.
- `docs/CHANGELOG.md`: release history.

## Naming Conventions

**Files:**
- Use lowercase snake_case Python modules: `room_temp_forwarding.py`, `operation_analysis.py`.
- Name each Home Assistant platform exactly after its platform: `sensor.py`, `water_heater.py`.
- Name tests `test_<module_or_feature>.py`: `tests/test_room_temp_forwarding.py`.
- Use uppercase conventional repository documents: `README.md`, `AGENTS.md`, `CHANGELOG.md`.

**Directories:**
- Use lowercase names; use underscores for Python packages such as `custom_components/idm_heatpump/`.
- Keep user wiki pages title-cased with hyphens where appropriate, for example `docs/wiki/Installation-and-Setup.md`.

**Python symbols:**
- Use `async_<action>` for asynchronous entry points and operations.
- Use `PascalCase` for classes such as `IdmCoordinator` and `RoomTempForwarder`.
- Use `UPPER_CASE` for constants in `custom_components/idm_heatpump/const.py`.
- Prefix internal helpers with `_`, keeping the public surface deliberately small.

## Where to Add New Code

**New register-backed entity:**
- Primary code: add or expose the register through `idm-heatpump-api`, then adapt/catalog it in `custom_components/idm_heatpump/library_adapter.py` or `custom_components/idm_heatpump/registers.py`.
- Presentation metadata: use the relevant `custom_components/idm_heatpump/adapter_*.py` module.
- Platform entity: add to the corresponding `custom_components/idm_heatpump/<platform>.py`.
- Tests: `tests/test_platforms.py` or `tests/test_platforms_<domain>.py`.
- UI resources: update `custom_components/idm_heatpump/icons.json`, `custom_components/idm_heatpump/strings.json`, and both files in `custom_components/idm_heatpump/translations/`.

**New Home Assistant platform:**
- Implementation: `custom_components/idm_heatpump/<platform>.py`.
- Registration: add `Platform.<NAME>` to `PLATFORMS` in `custom_components/idm_heatpump/__init__.py`.
- Shared behavior: reuse `custom_components/idm_heatpump/entity.py`; do not duplicate device info or direct client access.
- Tests: add `tests/test_platforms_<platform>.py`.

**New coordinator/device behavior:**
- State and orchestration: `custom_components/idm_heatpump/coordinator.py`.
- Low-level transport variation: `custom_components/idm_heatpump/modbus_transport.py`.
- Poll selection/persistence logic: `custom_components/idm_heatpump/polling_plan.py`.
- Tests: mirror changes in `tests/test_coordinator.py`, `tests/test_modbus_transport.py`, or `tests/test_polling_plan.py`.

**New self-contained feature:**
- Implementation: create `custom_components/idm_heatpump/<feature>.py` and keep integration wiring in `custom_components/idm_heatpump/__init__.py` small.
- Entities: create `<feature>_entities.py` only when the entities are derived/action-oriented rather than a standard HA platform.
- Tests: create `tests/test_<feature>.py`.

**New service:**
- Schema: `custom_components/idm_heatpump/services.yaml`.
- Handler: `custom_components/idm_heatpump/services.py`, or a focused `<feature>_services.py` for a substantial workflow such as `custom_components/idm_heatpump/dhw_boost_services.py`.
- Text: `custom_components/idm_heatpump/strings.json` and both translation JSON files.
- Tests: `tests/test_services.py` or `tests/test_<feature>_services.py`.

**Utilities:**
- Shared integration helper: a focused module under `custom_components/idm_heatpump/`; avoid a generic `utils.py`.
- Development generator: `scripts/`.
- Test-only helper/fixture: `tests/conftest.py`.

**Documentation:**
- User behavior: `docs/wiki/`.
- Maintainer contracts: `docs/dev/`.
- Dashboard examples: `docs/examples/`.
- Release-visible changes: `docs/CHANGELOG.md`.

## Special Directories

**`custom_components/idm_heatpump/brand/`:**
- Purpose: Local brand assets used for integration presentation.
- Generated: No.
- Committed: Yes.

**`custom_components/idm_heatpump/translations/`:**
- Purpose: Localized UI resources that must remain structurally aligned with `custom_components/idm_heatpump/strings.json`.
- Generated: No.
- Committed: Yes.

**`docs/public/`:**
- Purpose: Static project website assets and generated/published documentation content.
- Generated: Mixed; inspect the relevant script/workflow before editing derived pages.
- Committed: Yes.

**`docs/release-evidence/`:**
- Purpose: Version-specific release verification records and template.
- Generated: No.
- Committed: Yes.

**`__pycache__/`, `.ruff_cache/`, `.pytest_cache/`, `.mypy_cache/`:**
- Purpose: Local interpreter and tool caches.
- Generated: Yes.
- Committed: No; never add new code or documentation here.

**`.planning/codebase/`:**
- Purpose: GSD-generated current-state architecture maps used by planning and execution workflows.
- Generated: Yes.
- Committed: Workflow-dependent.

---

*Structure analysis: 2026-07-25*
