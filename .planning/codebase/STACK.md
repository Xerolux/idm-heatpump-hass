# Technology Stack

**Analysis Date:** 2026-07-25

## Languages

**Primary:**
- Python 3.13+ - Home Assistant integration implementation in `custom_components/idm_heatpump/` and tests in `tests/`.

**Secondary:**
- JSON - Integration metadata, UI strings, translations, and icons in `custom_components/idm_heatpump/manifest.json`, `custom_components/idm_heatpump/strings.json`, `custom_components/idm_heatpump/translations/`, and `custom_components/idm_heatpump/icons.json`.
- YAML - Home Assistant service schemas and quality metadata in `custom_components/idm_heatpump/services.yaml` and `custom_components/idm_heatpump/quality_scale.yaml`; GitHub Actions automation in `.github/workflows/`.
- Markdown/HTML/CSS/JavaScript - User documentation and the static documentation shell in `README.md`, `docs/wiki/`, and `docs/public/`.
- Shell and inline Python - CI/release orchestration in `.github/workflows/ci.yml`, `.github/workflows/python-quality.yml`, and `.github/workflows/release.yml`.

## Runtime

**Environment:**
- Home Assistant 2026.5.0 or newer, declared by `hacs.json` and documented in `README.md`.
- Python 3.13+ is the supported runtime baseline; GitHub validation currently exercises Python 3.14 in `.github/workflows/ci.yml`.
- The integration is an async, in-process Home Assistant custom component loaded from `custom_components/idm_heatpump/__init__.py`.

**Package Manager:**
- pip, invoked by Home Assistant for manifest requirements and explicitly by `.github/workflows/python-quality.yml`.
- Lockfile: missing. Runtime reproducibility relies on the exact `idm-heatpump-api[web]==0.8.4` pin and the bounded `pymodbus>=3.12.1,<4.0` range in `custom_components/idm_heatpump/manifest.json`.

## Frameworks

**Core:**
- Home Assistant 2026.5.0+ - Config entries, entity platforms, `DataUpdateCoordinator`, repairs, diagnostics, services, device/entity registries, and managed storage throughout `custom_components/idm_heatpump/`.
- `idm-heatpump-api[web]` 0.8.4 - Library-first IDM register model, Modbus client, model detection, and optional Navigator web clients, adapted in `custom_components/idm_heatpump/library_adapter.py`, `custom_components/idm_heatpump/registers.py`, and `custom_components/idm_heatpump/web_data.py`.
- pymodbus >=3.12.1,<4.0 - Modbus TCP transport and exception model used by the API client and handled in `custom_components/idm_heatpump/coordinator.py` and `custom_components/idm_heatpump/error_messages.py`.
- Voluptuous, supplied by Home Assistant - Config and repair flow validation in `custom_components/idm_heatpump/config_flow.py` and `custom_components/idm_heatpump/repairs.py`.
- aiohttp >=3.8.0 transitively/runtime-tested - Optional local Navigator HTTP session support in `custom_components/idm_heatpump/web_data.py`; CI installs it explicitly in `.github/workflows/python-quality.yml`.

**Testing:**
- pytest - Unit and contract runner configured by `pytest.ini`; test dependencies are installed without fixed versions in `.github/workflows/python-quality.yml`.
- pytest-asyncio - Automatic async test execution via `asyncio_mode = auto` in `pytest.ini`.
- pytest-cov - Coverage collection for `custom_components/idm_heatpump` in `.github/workflows/python-quality.yml`.
- pytest-homeassistant-custom-component - CI compatibility tooling, while `tests/conftest.py` supplies extensive local Home Assistant and dependency stubs.

**Build/Dev:**
- Ruff - Linting and formatting with a 120-character line length from `ruff.toml`; commands are defined in `.github/workflows/python-quality.yml`.
- mypy - Strict static typing from `mypy.ini`.
- HACS validation and Hassfest - Repository/integration validation in `.github/workflows/ci.yml`.
- GitHub Actions - CI, dependency updates, security checks, releases, Pages deployment, stale issue handling, and wiki sync in `.github/workflows/`.

## Key Dependencies

**Critical:**
- `idm-heatpump-api[web]==0.8.4` - Keep this exact release pin when changing library contracts; update `custom_components/idm_heatpump/manifest.json` and the dependency-contract references exercised by `tests/test_cross_repo_contract.py` and `tests/test_release_contract.py`.
- `pymodbus>=3.12.1,<4.0` - Keep transport behavior within the supported major version; communication failures are classified in `custom_components/idm_heatpump/error_messages.py`.
- Home Assistant 2026.5.0+ - Use native config entries, coordinator, repair, diagnostics, entity, and storage APIs rather than adding parallel infrastructure.

**Infrastructure:**
- HACS - Primary custom-integration distribution metadata is in `hacs.json`; release archives use `idm_heatpump.zip`.
- GitHub Pages - Static documentation is assembled from `docs/wiki/`, `docs/images/`, and `docs/public/` by `.github/workflows/pages.yml`.
- Home Assistant `Store` - Local persistence for DHW boost state and operation analysis in `custom_components/idm_heatpump/dhw_boost.py` and `custom_components/idm_heatpump/operation_analysis.py`.

## Configuration

**Environment:**
- Do not add environment-variable configuration for runtime behavior. Connection details and options are collected through `custom_components/idm_heatpump/config_flow.py` and persisted by Home Assistant config entries.
- Key connection values are host, Modbus port, slave ID, optional web host, and local web PIN, with constants in `custom_components/idm_heatpump/const.py`.
- Polling intervals, model/cascade selection, zones, room-temperature forwarding, and Modbus retry/timeout settings live in config-entry options handled by `custom_components/idm_heatpump/config_flow.py`.
- Sensitive connection fields are redacted from diagnostic output by `custom_components/idm_heatpump/diagnostics.py`.

**Build:**
- `custom_components/idm_heatpump/manifest.json` is the authoritative integration version and runtime dependency manifest.
- `pytest.ini`, `mypy.ini`, and `ruff.toml` are the test, type-check, and style configurations.
- `hacs.json` defines the HACS package/archive contract.
- `.github/workflows/python-quality.yml` is the reusable quality pipeline used by CI and release validation.

## Platform Requirements

**Development:**
- Use Python 3.14 to match current CI in `.github/workflows/ci.yml`, while preserving Python 3.13+ compatibility documented in `README.md`.
- Install Home Assistant 2026.5.0, manifest requirements, Ruff, mypy, pytest, pytest-cov, pytest-asyncio, and pytest-homeassistant-custom-component as shown in `.github/workflows/python-quality.yml`.
- Run `ruff check custom_components/idm_heatpump tests --line-length=120`, `ruff format custom_components/idm_heatpump tests --check`, `mypy custom_components/idm_heatpump`, and `pytest tests/`.

**Production:**
- Deploy inside a Home Assistant 2026.5.0+ installation, normally through HACS using `hacs.json`, or manually under `custom_components/idm_heatpump/`.
- Require LAN reachability from Home Assistant to the IDM Navigator: Modbus TCP normally uses port 502; optional Navigator web access uses the device-local protocol selected by `custom_components/idm_heatpump/web_data.py`.
- No cloud runtime or separate application server is required.

---

*Stack analysis: 2026-07-25*
