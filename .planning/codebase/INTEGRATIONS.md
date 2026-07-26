# External Integrations

**Analysis Date:** 2026-07-25

## APIs & External Services

**Local Heat-Pump Control:**
- IDM Navigator Modbus TCP - Polls telemetry and writes supported heat-pump registers entirely over the local network.
  - SDK/Client: `idm-heatpump-api[web]==0.8.4`, backed by `pymodbus>=3.12.1,<4.0`, instantiated from `custom_components/idm_heatpump/__init__.py` through adapters in `custom_components/idm_heatpump/library_adapter.py`.
  - Protocol: Modbus TCP, default port 502, function code handling delegated to the library.
  - Auth: No account or token; connection uses config-entry host, port, and slave ID constants from `custom_components/idm_heatpump/const.py`.
  - Resilience: `custom_components/idm_heatpump/coordinator.py` performs async polling and isolates illegal-address failures so unsupported optional registers do not fail the entire update.

**Local Web Supplement:**
- IDM Navigator local web interface - Supplements Modbus data and provides a web-only fallback for Navigator 2.0, Navigator 10, and Navigator Pro.
  - SDK/Client: Optional web clients exported by `idm-heatpump-api[web]`, created and normalized in `custom_components/idm_heatpump/web_data.py`.
  - Protocol: Navigator 10/Pro uses a device-local WebSocket (documented in `custom_components/idm_heatpump/web_data.py` as port 61220); Navigator 2.0 uses local HTTP with CSRF handling delegated to the API package.
  - Auth: Local Navigator web PIN stored in the Home Assistant config entry under `CONF_WEB_PIN`; `custom_components/idm_heatpump/config_flow.py` validates it and `custom_components/idm_heatpump/repairs.py` provides correction flows.
  - HTTP client: aiohttp sessions are created only when needed for IP-host cookie compatibility in `custom_components/idm_heatpump/web_data.py`.
  - Data: Local controller metadata, sensor values, and optional Navigator 10 infosystem notifications are normalized into `IdmWebSupplement` in `custom_components/idm_heatpump/web_data.py`.

**Home Assistant Runtime:**
- Home Assistant - Hosts config entries, platform entities, service registration, repairs, diagnostics, registries, event tracking, and scheduling.
  - SDK/Client: Native `homeassistant.*` APIs imported throughout `custom_components/idm_heatpump/`.
  - Auth: Managed by the containing Home Assistant instance; this integration defines no independent user identity or authorization provider.
  - Internal callbacks: Room-temperature source state changes are observed through Home Assistant events in `custom_components/idm_heatpump/room_temp_forwarding.py`.

**Documentation and Distribution:**
- HACS - Installs the custom integration using metadata in `hacs.json` and validates releases through `.github/workflows/ci.yml`.
- GitHub Releases - Publishes versioned ZIP artifacts through `.github/workflows/release.yml`.
- GitHub Pages - Hosts static documentation built from `docs/public/`, `docs/wiki/`, and `docs/images/` through `.github/workflows/pages.yml`.
- GitHub repository dispatch - Companion API releases can trigger `.github/workflows/api-dependency-update.yml` to create an exact dependency-pin update pull request; this is development automation, not runtime communication.

## Data Storage

**Databases:**
- Not detected. The integration does not connect directly to SQL, NoSQL, or time-series databases.
- Home Assistant owns entity state/history outside this repository; integration code interacts through Home Assistant APIs rather than a database client.

**File Storage:**
- Home Assistant managed `Store` only.
  - DHW boost state is persisted by `custom_components/idm_heatpump/dhw_boost.py`.
  - Operational analysis snapshots are persisted by `custom_components/idm_heatpump/operation_analysis.py`.
  - Do not introduce direct arbitrary filesystem persistence when Home Assistant `Store` satisfies the use case.

**Caching:**
- No external cache service.
- In-memory coordinator data and persistent web-client pooling live in `custom_components/idm_heatpump/coordinator.py` and `custom_components/idm_heatpump/web_data.py`.

## Authentication & Identity

**Auth Provider:**
- Custom device-local PIN for the optional Navigator web interface.
  - Implementation: `custom_components/idm_heatpump/web_data.py` delegates authentication to `idm-heatpump-api[web]`, converts API authentication failures into `IdmWebAuthenticationFailed`, and supports both Navigator protocol variants.
  - Configuration: `custom_components/idm_heatpump/config_flow.py` stores the PIN in the Home Assistant config entry; `custom_components/idm_heatpump/repairs.py` updates invalid or missing PINs.
  - Privacy: `custom_components/idm_heatpump/diagnostics.py` redacts the web PIN, hosts, port, and slave ID.
- Modbus TCP has no application-level authentication in this integration; network isolation is the practical access boundary.
- OAuth, API-key, cloud-account, and SSO providers: Not detected.

## Monitoring & Observability

**Error Tracking:**
- No external error-tracking service.
- Home Assistant repair issues surface missing/invalid web PINs and communication problems from `custom_components/idm_heatpump/coordinator.py`, `custom_components/idm_heatpump/__init__.py`, and `custom_components/idm_heatpump/repairs.py`.

**Logs:**
- Standard Python logging feeds Home Assistant logs from modules under `custom_components/idm_heatpump/`.
- `custom_components/idm_heatpump/log_filter.py` suppresses narrowly matched routine pymodbus and API transport noise while coordinator-level failures remain actionable.
- `custom_components/idm_heatpump/diagnostics.py` exports redacted runtime/configuration diagnostics and dependency versions.

## CI/CD & Deployment

**Hosting:**
- Runtime hosting is the user's Home Assistant instance; the integration has no standalone hosted backend.
- HACS/GitHub Releases distribute `idm_heatpump.zip` according to `hacs.json` and `.github/workflows/release.yml`.
- GitHub Pages hosts documentation via `.github/workflows/pages.yml`.

**CI Pipeline:**
- GitHub Actions in `.github/workflows/ci.yml` validates Python 3.14, Home Assistant 2026.5.0, the manifest-pinned API, and the API main branch.
- `.github/workflows/python-quality.yml` runs Ruff, strict mypy, pytest coverage, HACS validation, and Hassfest through the calling workflows.
- `.github/workflows/security.yml` runs CodeQL and `pip-audit`.
- `.github/workflows/api-dependency-update.yml` consumes a validated companion-library version and opens a dependency update PR.
- `.github/workflows/wiki-sync.yml` synchronizes `docs/wiki/` to the GitHub Wiki.

## Environment Configuration

**Required env vars:**
- Runtime: None. Home Assistant config entries contain all device connection settings.
- CI: Workflow-scoped variables such as `API_DEPENDENCY_MODE`, `RELEASE_TAG`, and `API_VERSION` are declared within `.github/workflows/`; they are not integration runtime configuration.

**Secrets location:**
- The optional local web PIN is held by Home Assistant in config-entry data; its key is defined as `CONF_WEB_PIN` in `custom_components/idm_heatpump/const.py`.
- GitHub credentials/tokens are managed by GitHub Actions permissions and repository configuration; no credential files are part of the runtime integration.
- Diagnostic redaction is enforced in `custom_components/idm_heatpump/diagnostics.py`.

## Webhooks & Callbacks

**Incoming:**
- Runtime webhooks: None.
- Development automation: `.github/workflows/api-dependency-update.yml` accepts the GitHub `repository_dispatch` event type `idm_heatpump_api_release`.
- Home Assistant service calls are internal runtime entry points defined in `custom_components/idm_heatpump/services.py`, `custom_components/idm_heatpump/dhw_boost_services.py`, and `custom_components/idm_heatpump/services.yaml`; they are not public HTTP webhooks.

**Outgoing:**
- Runtime webhooks: None.
- Device writes go directly to local Modbus TCP through `custom_components/idm_heatpump/coordinator.py`.
- Optional web reads go directly to the configured local Navigator host through `custom_components/idm_heatpump/web_data.py`.
- No telemetry, cloud analytics, or external account API calls are present in runtime code.

---

*Integration audit: 2026-07-25*
