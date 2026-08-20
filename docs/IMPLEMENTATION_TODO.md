# IDM Heatpump – open TODO list

Last updated: 2026-08-18

The large strategic optimization blocks are implemented. This document only
contains items that are genuinely open, depend on real-system data, or are
blocked by an external Home Assistant decision. The local
`modbus-connection`/tmodbus adapter is implemented by now; only central entry
sharing and the read-only hardware verification of that new path are still open.


## Design document

The detailed, safety-oriented roadmap is in
[`docs/dev/heatpump-feature-roadmap.md`](dev/heatpump-feature-roadmap.md). This
TODO document stays the short operational list; the design document describes
phases, safety rules and blocked data points.

The current audit of the remaining work is in
[`docs/dev/open-work-audit.md`](dev/open-work-audit.md). It separates what is
done locally from what stays blocked for lack of real-system data or because
Home Assistant's central shared-connection contract is not available yet.

## Done

- [x] Robust binary sensor evaluation including sentinel, negative, bitmask and
      active-low support.
- [x] Explicit binary metadata in `idm-heatpump-api`.
- [x] Matching device classes for operation, heating, cooling, lockout,
      connection and fault.
- [x] Calculated heat pump and heat source spread.
- [x] Calculated domestic hot water deviation.
- [x] Navigator web states as real binary sensors.
- [x] Optional device hierarchy for heating circuits, zones, rooms, solar, ISC,
      cascade and additional heat generators.
- [x] Stable unique IDs and safe migration of existing installations.
- [x] Cycling, runtime, compressor start and defrost analysis.
- [x] Short-cycle warning and operating shares.
- [x] Restart-proof persistence of the operation analysis.
- [x] Safe domestic hot water boost with start, cancel, timeout, target
      reached, restart recovery and guaranteed restore.
- [x] Entity-based, deduplicated Modbus polling.
- [x] Protection, alarm, analysis and restore registers stay active at all
      times.
- [x] Conservative default profile added for generated technical/rare
      diagnostic entities, without changing existing unique IDs.
- [x] Validation with the pinned API level and separately against API main.
- [x] Ruff, formatter, mypy, pytest, Hassfest and security for all merged work
      packages.

## Open – needs real-system data

### COP

- [x] Unambiguous registers for simultaneous electrical and thermal power
      verified.
- [x] Behavior during heating, idle and very low power defensively secured.
- [x] Only publish the instantaneous COP sensor when both sources are reliably
      available and the system would not produce wrong figures while standing
      still.
- [/] Collect further real data sets for domestic hot water, defrost cycles and
      different Navigator firmware levels; the issue template and the field
      diagnostics guide are prepared.
      **Partly verified (2026-07-22, Nav 10):** the COP source registers
      `power_consumption_hp` (@4122) and `thermal_power_flow_sensor` (@4126)
      are confirmed live; the standby zero case is caught by the 50 W
      threshold.
      **Broad data set (2026-07-31, Nav 10):** a 15-day, 30-second recording
      from VictoriaMetrics evaluated (firmware NAV10_20.24, −7…+7 °C).
      Domestic hot water COP median 2.62 (n=1,217), heating COP median 3.00
      (n=30,551); real thermal power is within the nominal range 0–16 kW
      (electrical 0–10 kW) for 97 % of the time. A few samples during defrost
      and transition phases read outside that range (measurement artifacts of
      the flow/ΔT calculation, not real power — correctly discarded by the COP
      guard), SCOP (integral) 2.62, energy meter delta +2,548 kWh. The electric
      heating element stayed at 0.0 kW (inactive) over the whole period. Only
      firmware levels other than NAV10_20.24 remain open.

Additional user data:

- Diagnostics export from Home Assistant.
- Roughly 10–20 minutes of raw data at a 5–10 second interval.
- Screenshots from the IDM Navigator showing electrical power, thermal power,
  operating mode and compressor status.

### Flow temperature deviation

- [/] Unambiguous IDM register for the actually requested heat pump flow
      setpoint verified.
      **Partly verified (2026-07-22, Nav 10):** per heating circuit there is
      `hc_{a..g}_setpoint_flow_temp` (address 1378 ff., FLOAT, read-only) as the
      calculated flow setpoint. Sentinel `0.0` in standby, `-1.0` for heating
      circuits that are not enabled. See `docs/dev/open-work-audit.md`.
      **Field-confirmed (2026-07-31, Nav 10):** across the 15-day, 30-second
      recording, `temp_flow_target_circuit_a` behaves like the requested flow
      setpoint (heating operation ~47–48 °C, close to 0 or ~29 °C outside of a
      demand). During heating, the actual flow runs 0.2–2.9 K below the
      setpoint as expected (the largest shortfall on the coldest day).
- [ ] Document the delineation from the heating curve, mixer setpoint, maximum
      flow temperature and heating circuit setpoint.
- [ ] Check the behavior with several heating circuits and with cascades.
- [ ] Only then publish `actual flow - requested flow` as a sensor.

Required user data:

- Simultaneous values for `hp_flow_temp`, the requested flow setpoint, the
  operating mode and the active heating circuit.
- Where possible, data sets for heating, domestic hot water and idle.

### Real binary register verification

- [/] Check all binary registers against at least one Navigator 10 system.
      **Spot-verified (2026-07-22, Nav 10):** compressor, pump, valve and
      heating circuit status registers read. The three sentinel variants
      (`255` UCHAR, `-1` INT16, `65535` UINT16) were observed live and match
      the `is_register_unused` logic. See `docs/dev/open-work-audit.md`.
- [ ] Check all binary registers against at least one Navigator 2.0 system.
- [/] Document active-low, special and firmware values where they deviate from
      0/1.
      **Confirmed:** `evu_lock` uses inverse logic (`1 = Not Locked`); full
      firmware coverage stays open.

## Open – further quality improvements

- [x] Classify the entity catalog into basic, advanced and diagnostic/expert;
      the API-wide extension stays open as a separate documentation effort.
- [x] Deliberately disable rare valve, raw status, cascade and service values by
      default for new installations.
- [x] Leave existing user enablement untouched in every further migration; the
      entity registry migration contract is documented.
- [x] Generate the entity metadata catalog automatically from HA metadata.
- [x] API-wide entity documentation prepared: explicit HA overlays live in the
      entity metadata catalog, the complete register reference stays coupled to
      `idm-heatpump-api` through the existing generator; further real profile
      verification depends on data.
- [ ] Run load tests with the maximum number of heating circuits, zones and
      rooms; blocked until suitable diagnostics exports arrive through the field
      diagnostics template.
- [x] Document the diagnostics data requirements and privacy rules for field
      diagnostics.
- [x] Contract test that checks the API's web value keys against the entities
      the integration publishes (`tests/test_cross_repo_contract.py`). It
      catches the case where a new API key arrives on every poll and is
      silently discarded — the cause of the heating circuit B–G bug in
      `0.13.0`.

## Modbus transport – implemented and remaining

- [x] Implement a backend-neutral transport contract with separate FC03/FC04
      read paths, an FC16 write path, endpoint validation and redacted
      capabilities.
- [x] Wire up the production adapter `IdmModbusConnectionClient`. API 1.0.1
      keeps the register model, batch planning, encoding/decoding, model
      detection and write protection; raw I/O runs through
      `ModbusConnectionTransport`.
- [x] Pin the direct socket reproducibly to `modbus-connection==4.0.0a3` and
      `tmodbus==0.5.0`. `4.0.0a3` is the library version, not the integration
      version; the runtime path ships for the first time with `0.11.0-beta.1`.
- [x] Keep `idm-heatpump-api[web]==1.0.1` and `pymodbus>=3.12.1,<4.0`
      temporarily as a compatibility pair, because `idm_heatpump.client` still
      imports pymodbus at module level. Pymodbus does not own the direct socket.
- [x] Make the transport source, socket ownership, connection status,
      `supports_shared_connection=False` and all runtime versions diagnosable in
      redacted form.
- [ ] Validate the new tmodbus runtime path read-only on real Navigator
      hardware for setup, FC03, FC04, connection loss and reconnect. No hardware
      write tests without an explicit authorization.
- [x] Move `idm-heatpump-api` onto a public, transport-neutral I/O contract:
      since `1.0.1` the API exports `IdmModbusTransport` as a protocol,
      `IdmModbusClient` accepts the transport through `transport=`, and
      `IdmModbusConnectionClient` uses exactly that path.
- [ ] Remove the pymodbus compatibility pin as soon as the module-level import
      of `pymodbus` in `idm_heatpump.client` is optional.
- [ ] Only add a central Home Assistant shared-connection provider once it is
      stably available for custom integrations. Until then every entry owns its
      own socket and reports no sharing.

## Unchanged release rules

- The add-on version stays independent of the API version.
- The API pin is only changed in a dedicated, fully validated add-on pull
  request.
- The two transport pins are only changed as a jointly tested, exact pair.
- No estimate is published as a measured value.
- No existing unique ID is changed without a migration.
