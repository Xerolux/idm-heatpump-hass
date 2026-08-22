# Open Work Audit

Last updated: 2026-08-18

This audit separates work that can be finished locally from items that cannot be
completed safely without real-system data or without a central Home Assistant
shared-connection contract. The local tmodbus adapter is wired up in production;
the goal remains to never declare an estimate, or a transport property that has
not been validated on hardware, as finished.

## Done locally

- Conservative entity profile for generated technical and rare registers.
- Automatically generated Home Assistant metadata catalog for explicit overlays.
- The complete Modbus register reference stays coupled to the pinned
  `idm-heatpump-api` level through
  `scripts/generate_modbus_register_reference.py`.
- Field diagnostics guide and issue template for real-system measurements.
- Wired-up `IdmModbusConnectionClient` with a backend-neutral Modbus transport
  contract, endpoint validation, conflict detection and privacy-safe diagnostics
  helpers.
- Direct socket through `modbus-connection==4.8.1` and the separately pinned
  backend level `tmodbus[async-serial]==0.5.1`; the first integration version to
  ship it is `0.11.0-beta.1`.
- API device logic stays with `idm-heatpump-api[web]==1.0.3`. The pymodbus pin
  only remains temporarily because `idm_heatpump.client` still imports it at
  module level; the physical connection belongs to tmodbus.
- Diagnostics export for the transport source, socket ownership, connection
  status, the missing central sharing and all runtime versions.
- Issue template for the read-only hardware verification and for a later central
  Home Assistant Modbus connection.
- Synthetic scaling test for the maximally equipped installation
  (`tests/test_scale_load.py`): 7 heating circuits, 10 zones with 8 rooms each,
  cascade active. It covers the register count, uniqueness of names and
  addresses, unique ID collisions per platform, the completeness of the
  coordinator indexes, and build and evaluation runtime. That is the locally
  provable half of the load test item; the effect on real Modbus response times
  stays open (see below).
- Web entities per configured heating circuit instead of fixed to heating
  circuit A (`0.13.0`). The pump, mixer and flow temperature of heating circuits
  B–G arrived through the web supplement and were discarded by the fixed
  allowlists.
- Contract test for the web value keys (`tests/test_cross_repo_contract.py`). It
  compares the value names `idm-heatpump-api` can produce with the set the
  integration publishes as entities, and fails as soon as the API delivers a key
  the integration silently throws away. It is skipped against the stubbed API;
  in CI it runs against the real library.
- Automated privacy and completeness test for the diagnostics export
  (`tests/test_diagnostics_privacy.py`). The host, web host, PIN, myIDM ID,
  serial number and error texts with embedded connection details must not appear
  in the serialized export, while the sections support needs must be preserved.
  It replaces the recurring manual check.

## Live-verified (Navigator 10, read-only Modbus FC04 + web supplement)

On 2026-07-22 the following points were verified on a real Navigator 10 system
(heating circuit A, solar/ISC/PV detected, software `NAV10_20.24-880-g265e09c4a`)
— through strictly read-only Modbus access (function code 04, no writes, no
EEPROM candidates) and additionally through the local Navigator 10 web
supplement (port 61220, WebSocket authentication by PIN). The verification
confirms the code's assumptions; it does not replace the broader field
diagnostics for other Navigator types and firmware levels.

> This measurement was taken before the direct socket moved to tmodbus. It
> confirms register definitions and device logic, but it is not a hardware
> verification of the new `modbus-connection`/tmodbus path.

### Model detection

- `IdmModbusClient.detect_model()` correctly detects the installation as
  `Navigator 10` (heating circuit A active, solar/ISC/PV = True, no cascade).
  The distinction is made primarily through the Navigator 10 specific register
  `power_limit_hp` (address 4108), which answers on this installation.
- `client.model_info` is a **property** of the API (not a callable); the
  integration accesses the detected attributes correctly in
  `_detect_model_info()` and handles missing firmware defensively.

### COP source registers

- `power_consumption_hp` (address 4122, FLOAT) and `thermal_power_flow_sensor`
  (address 4126, FLOAT) exist on the real installation and deliver plausible
  power values during heating and domestic hot water operation; in standby both
  read exactly `0.0`.
- Exactly that `0.0` case is covered by the 50 W threshold in
  `calculated_sensors.py`: the COP sensor goes `unavailable` instead of
  computing an implausible value from zero electrical power.
- The former stub key `thermal_power` is not defined in the real API; the COP
  path correctly uses `thermal_power_flow_sensor`.

### Flow setpoint

- There is a family of calculated setpoint registers per heating circuit,
  `hc_{a..g}_setpoint_flow_temp` (address 1378 ff., FLOAT, read-only). That is
  the requested flow setpoint calculated by the heating curve, per heating
  circuit.
- In standby the active heating circuit returns `0.0`, heating circuits that are
  not enabled return `-1.0`. Both are sentinel values that the central
  `is_register_unused` filter correctly decodes as `unavailable`.
- In addition there are configurable setpoint registers
  (`hc_*_setpoint_flow_constant`, `hc_*_heating_curve`, `hc_*_heating_limit`).
  The flow deviation feature is therefore technically feasible; before it can be
  published it still has to be clarified which setpoint is the "requested" one
  and how it is assigned per heating circuit. The register variables are
  verified, so the feature stays classified as "implementable, but not
  released".

### Binary and status sentinel values

- The three sentinel variants were observed live and match the
  `is_register_unused` logic in `coordinator.py` exactly:
  - `255` (UCHAR): compressors that are not present (`compressor_status_2..4`),
    heating circuits that are not configured (`hc_b_active_mode`).
  - `-1` (INT16): pumps that are not present (`charging_pump_status`,
    `brine_pump_status`, `heat_source_pump_status`).
  - `65535` (UINT16): valves that are not present (`valve_hc_heat_cool`,
    `valve_storage_heat_cool`).
- `compressor_status_1` returned `0` (compressor off) — plausible active states
  are therefore distinguishable from "not present".
- `evu_lock = 1 -> Not Locked` confirms the inverse active-high logic
  (`0 = Locked`, `1 = Not Locked`) that the enum maps carry correctly.
- These sentinels now live in the API and are no longer open:
  `RegisterDef.effective_sentinel_values` returns the documented default per
  data type (`FLOAT` → `-1.0`, `UCHAR` → `255`, `UINT16` → `65535`, `INT16` →
  `-1`/`-32768`), in addition to the values individual registers declare
  explicitly. Since 0.8.7 `is_register_unused` in `coordinator.py` uses that
  information exclusively; the former hand-written numeric filter is no longer
  evaluated.

### Web supplement (Navigator 10)

- The Navigator 10 web client (`IdmNavigator10WebClient`) speaks WebSocket on
  port 61220. Login by PIN, `connect()` and `read_data()` were run successfully
  against the real installation; for a device detected as Navigator 10 the
  integration's `async_read_web_supplement` logic picks this client first and
  only falls back to the Nav 2.0 HTTP client on variant-specific errors.
- `read_data()` returned 60 values, among them pure web quantities that are not
  available over Modbus: hot gas temperature, condensation and evaporation
  pressure, compressor heating, board temperature, runtimes (heating, domestic
  hot water, defrost, stage 1 and second heat generator), switching cycles, the
  myIDM ID and the software version.
- The software version (the `software_version` field of the web data model) is
  the reliable source for the firmware, because Modbus register 4120 cannot be
  read reliably on this firmware (it is therefore skipped in
  `_detect_model_info` with `read_firmware=False`).

## Externally blocked

### Real-system data

These points may only be marked done once real data from at least one suitable
system is available:

- COP verification for domestic hot water, defrost cycles and different
  Navigator firmware levels.
- Unambiguous identification of the flow setpoint the heat pump actually
  requests.
- Binary register verification on Navigator 10 and Navigator 2.0, including
  active-low and special values.
- Load tests with the maximum number of heating circuits, zones and rooms **on
  real hardware**. The scaling of the integration itself is covered locally
  (`tests/test_scale_load.py`); what a test without an installation cannot show
  is how the controller behaves under the resulting request load: real response
  times, batch behavior and timeout limits.
- Read-only transport test of the new tmodbus path on real hardware: setup,
  FC03, FC04, connection loss and reconnect. Write tests remain excluded without
  an explicit authorization.

The required artifacts are described in the field diagnostics template and in
the field diagnostics guide. Without that data the safe decision stands: do not
publish, do not estimate, and do not change write paths.

### Home Assistant shared-connection contract

The local adapter is implemented. Only the following central sharing points stay
blocked until Home Assistant publishes a stable contract for custom
integrations:

There is currently no final official shared-connection contract such a provider
could safely build on.

- Provider between a future central Home Assistant connection object and
  `IdmModbusTransport`.
- Ownership and lifecycle rules for several config entries.
- Migration path without new unique IDs and without a new write path.
- Only a central provider that is really integrated may report
  `supports_shared_connection=True` and `owns_socket=False`.

Until then every config entry owns its direct tmodbus socket and reports
`supports_shared_connection=False`. There is no transport option and no second
pymodbus socket path.

### API decoupling

`idm-heatpump-api` 1.0.1 now provides the transport-neutral contract publicly:
`IdmModbusTransport` is an exported, runtime-checkable protocol, and
`IdmModbusClient` accepts a transport instance through the public parameter
`transport=`. The integration uses exactly that path; protected raw I/O hooks
are no longer needed for it.

The only thing left open is the pymodbus pin: `idm_heatpump.client` still
imports `pymodbus` at module level, regardless of which transport is injected.
The pin may only be dropped once that import is optional.

## Decision rule

An item may only move from "blocked" to "done" when at least one of these holds:

1. The required real measurements are available as a redacted diagnostics export
   and a raw data series.
2. The final Home Assistant documentation is linked and a central
   shared-connection provider is implemented separately from the local tmodbus
   adapter that already exists.
3. A test or generator proves reproducibly that the documentation matches the
   code.
