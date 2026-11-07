# Telemetry private test evidence — 5 November 2026

## Scope and delivery

Private integration build `0.26.0-b4` combines current upstream stable `0.25.0`,
the optional Modbus network discovery branch and the plant-only telemetry work.
Both repositories remain on local `Xe/opt-in-telemetry` branches. No public
release, tag or push was performed. Existing plant control settings were preserved.

The backend and bilingual privacy/deletion pages are deployed on the existing
IDM Tools service. The private telemetry dashboard uses the existing Authelia
owner identity and second factor. Anonymous access redirects to authentication.
No new account or password was created.

## Verification

- Integration: 3,428 unit tests passed, two skipped; total coverage 98.67% and
  configuration-flow coverage 100%. A separate configuration/discovery test run
  also met the 100% flow gate. Strict mypy and Ruff passed.
- Genuine Home Assistant lifecycle smoke tests: eleven passed, including
  consent-dependent entity registration and withdrawal cleanup.
- Backend: 64 tests and 22 subtests passed. The broader desktop-client suite
  passed 189 tests and 513 subtests; one unrelated GUI test could not initialize
  because the installed Windows Tk runtime lacks `ttk/notebook.tcl`.
- Sensitive-data and documentation-language checks passed.
- Live server: synthetic ingest, idempotent replay, numeric firmware/build
  ordering, test/stable separation, private dashboard access and verified erasure
  passed. Synthetic rows were removed and the report count restored. No real
  plant report was forced or sent by these tests.
- Live HA 2026.11.0: configuration validation and restart passed; the integration
  loaded as `0.26.0-b4`, polling succeeded with zero consecutive communication
  failures. The network-scan setup choice is present; no scan was started.
- Explicit notice-v3 consent detected myIDM automatically. Consent on/off/on
  created, removed and recreated the firmware sensor. Withdrawal removed both
  registry row and HA state. Final telemetry state is enabled for the authorized
  multi-day test. No heating setpoints, modes or actuator commands were issued.
- Unrelated IDM options and connection settings match the pre-installation
  backup. Only telemetry fields and the normal `last_run_version` marker changed.
  An integration-only rollback backup is retained on the HA host.

## Expected field behavior

The first daily report is eligible no earlier than **6 November 2026 at 20:20
Europe/Berlin**; the hourly tick may send later. Reports are at least 24 hours
apart. Aggregates and one frozen outbox are persisted; delayed saving can lose
recent unsaved changes after abrupt power loss. Clean unload flushes the store.
Disabling clears local telemetry storage and cancels upload/catalog tasks.
Already received server data is handled through verified erasure requests.

The installed firmware is in the `T_NAV10_20` test channel. The controller does
not report a heat-pump type, so only other missing-type reports in that known
controller/software series may match. Known models and stable channels remain
separate. With no matching observations, the firmware sensor is `unknown` and
explains the missing evidence in its attributes. No newer version is invented.
Catalog queries occur on startup and every six hours only with valid consent.

## Remaining observation and production limits

The actual first daily report and a multi-day stability window remain field
observations, not completed tests. Telemetry complements diagnostic captures;
it does not replace raw protocol evidence or controller service tools.

Server permissions, encrypted storage, log suppression, automatic expiry and
current backup scripts were inspected. The provider contract/processor agreement,
physical data location and provider-side snapshots cannot be established from
SSH alone. These operator obligations must be resolved before claiming complete
production privacy compliance. Technical tests are not a legal certification.

The published [HACS integration requirements](https://www.hacs.dev/docs/publish/integration/)
define repository/manifest distribution requirements; they do not certify privacy
compliance or official Home Assistant Core acceptance. The optional feature keeps
local plant operation independent of the community server.
