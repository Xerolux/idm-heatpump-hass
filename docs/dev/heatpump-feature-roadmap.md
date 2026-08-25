# IDM Heatpump Feature Roadmap

Last updated: 2026-08-18

This document collects the next safe and worthwhile work packages for
`idm-heatpump-hass`. The focus is local functionality, comprehensible behavior,
protection of the installation, and an architecture that can absorb later Home
Assistant changes to the Modbus transport.

## Guiding principles

- **Local first:** no cloud dependencies and no external runtime APIs.
- **Safe before convenient:** every writing feature needs clear registers,
  limits, restoration and tests.
- **No estimated readings as facts:** derived values are clearly marked as
  analysis or calculated sensors.
- **Registers belong in the API:** device knowledge, data types and addresses
  stay in `idm-heatpump-api` or in central adapter/constant modules, not in
  platform files.
- **Protect existing installations:** unique IDs, entity registry decisions and
  user options stay migration-safe; the details are in the entity registry
  migration contract.
- **Keep the transport boundaries:** the direct socket runs through the
  implemented `modbus-connection`/tmodbus adapter. Device logic stays in
  `idm-heatpump-api`; central cross-entry sharing is only added once Home
  Assistant offers a stable contract.

## Phase plan

### Phase 1 – value without risk to the installation

These work packages come first because they mostly document, visualize or
surface analysis values that already exist.

- [x] Publish the operation analysis as sensors:
  - recorded heat pump cycles,
  - today's and short-term cycles,
  - current, last and average cycle runtime,
  - defrost counter,
  - operating shares.
- [x] Publish the short-cycle warning as a problem sensor.
- [x] Publish the Navigator web states as real binary sensors.
- [x] Offer the device hierarchy for large installations as an option.
- [x] Use entity-aware polling so that expert values which are not enabled are
  not read unnecessarily.
- [x] Add dashboard examples for overview, domestic hot water, energy and
  diagnostics as separate, conservative starting points.
- [x] Classify the entity catalog consistently into basic, advanced and
  diagnostic/expert; the API-wide extension stays documented as open.
- [x] Generate the entity metadata catalog automatically from HA metadata; the
  API-wide entity documentation stays open as the next step.

### Phase 2 – convenience features with protection mechanisms

Writing convenience features are only permitted when they are deterministic,
bounded and recoverable.

- [x] Safe domestic hot water boost:
  - start only when the registers exist and are writable,
  - target temperature and runtime limits,
  - persistence before the first write,
  - rollback on start failures,
  - restoration on cancel, timeout, target reached and restart.
- [x] Room temperature forwarding to building-management registers:
  - configured HA sensors only,
  - limit checks from register metadata,
  - tolerance against write noise,
  - cyclic and event-based updates.
- [x] Documented PV/building-management examples with an ownership note and
  write protection recommendations.
- [ ] PV/smart grid assistant only after an additional safety review:
  - unambiguous register ownership,
  - minimum runtimes,
  - hysteresis,
  - write interval limiting,
  - no competition with existing energy managers.
- [x] Heating curve UX:
  - `idm-heatpump-api` supplies min/max per register (`min_val`/`max_val`) and
    it is adopted unchanged; the integration does not duplicate device limits.
  - The heating curve step was corrected to 0.1. As a FLOAT register it got the
    default step of 0.5, even though its range is 0.1–3.5 — common values such
    as 0.3 fell between two steps.
  - `heating_curve`, `parallel_shift`, `setpoint_flow_constant` and
    `setpoint_flow_cooling` are created disabled for new installations. Existing
    entities stay unchanged.
  - Grouping through a dashboard example per heating circuit
    (`docs/examples/dashboard-idm-heating-circuit.yaml`); the device page in
    Home Assistant sorts alphabetically and has no sub-groups.

### Phase 3 – architecture and the future of Modbus in Home Assistant

The local adapter is implemented and the direct socket uses tmodbus. Home
Assistant's central contract for cross-entry sharing, by contrast, is still not
stably available to custom integrations. These two levels must not be confused
in planning or in diagnostics.

- [x] The current integration stays encapsulated behind `idm-heatpump-api` and
  the central coordinator.
- [x] Platform files do not introduce direct Modbus transports.
- [x] The manifest pins the tested API version reproducibly.
- [x] Implement a backend-neutral transport contract with FC03, FC04, FC16,
  endpoint validation and redacted capabilities.
- [x] Wire up `IdmModbusConnectionClient` as the production adapter and run raw
  I/O through `modbus-connection==4.10.0` and `tmodbus[async-serial]==0.6.1`. The
  path ships for the first time with `0.11.0-beta.1`.
- [x] Keep `idm-heatpump-api[web]==2.0.0b1` for device logic and
  `pymodbus>=3.12.1,<4.0` temporarily for its imports and error contract;
  pymodbus does not own the direct socket.
- [x] Diagnose the private per-entry socket ownership and the missing central
  sharing as `owns_socket=True` / `supports_shared_connection=False`.
- [ ] Validate the new tmodbus path read-only on real Navigator hardware; no
  write tests without an explicit authorization.
- [x] Structure `idm-heatpump-api` transport-neutrally and provide a public I/O
  contract: since `1.0.1` the API exports the runtime-checkable protocol
  `IdmModbusTransport`, and `IdmModbusClient` accepts the transport through the
  public parameter `transport=`. The register model, encoding/decoding, batch
  planning and error classification stay in the API.
- [ ] Remove the pymodbus compatibility pin. It no longer depends on the
  transport contract, only on `idm_heatpump.client` importing `pymodbus` at
  module level — independently of the injected transport.
- [x] Evaluate the component/planning module of `modbus-connection`
  (`modbus_connection.model`) as a replacement for batching and decoding in
  `idm-heatpump-api`. Result: do not implement — the register map fits
  completely (586/586 data points, 0 decoding deviations), but the read planning
  merges the three documented logical overlaps into one request, while the
  register invariants require them to be requested individually. Measurement and
  re-evaluation criterion: `docs/dev/component-model-evaluation.md`.
- [ ] Only implement an additional central Home Assistant connection provider
  once the interface is stably documented for custom integrations.
- [ ] Plan the migration of existing users separately, should a central
  shared-connection model later be stably recommended.

## Safety rules for all new write features

Every new write feature must meet these criteria:

1. The register is known, writable and centrally defined.
2. Values are validated against register metadata or conservative integration
   limits.
3. Rapidly changing input values are throttled or hysteresis-controlled.
4. For temporary operating changes, the previous state is persisted beforehand.
5. Errors lead to clear Home Assistant errors, not to silent aborts.
6. Tests cover success, invalid values, communication errors, restoration and
   restart recovery.
7. The documentation explains the benefit, the limits and the possible effects
   on the installation.

## Open data points before further readings

### Instantaneous COP

The instantaneous COP is implemented as soon as simultaneous electrical and
thermal power registers are available and not marked unused. The sensor stays
deliberately defensive: while the system is idle, when sources are missing, or
when the power is too low to be reliable, no value is published.

### Flow temperature deviation

At **heating circuit level** the deviation is implemented: `hc_{x}_flow_temp`
minus `hc_{x}_setpoint_flow_temp` compares two registers of the same heating
circuit, and the setpoint calculated by the heating curve is unambiguous for
that circuit. Sentinel values (`0.0` while idle, `-1.0` for a heating circuit
that is not configured) run through the central `is_register_unused` filter, and
the sensor then reports `unavailable`.

At **heat pump level** the point stays open: a sensor for
`actual flow minus requested flow` first needs an unambiguous register for the
flow setpoint the heat pump actually requests. Heating curve, mixer and maximum
values must not be mixed up.

### Binary register semantics

Binary registers still have to be verified against real Navigator 2.0,
Navigator 10 and Navigator Pro installations, in particular for active-low,
sentinel or firmware-dependent special values.

## Next concrete TODOs

1. Clarify the room temperature per heating circuit in the web supplement:
   `idm-heatpump-api` only maps `B61` onto `room_temperature_HK_A`. Over Modbus
   there is `hc_{a..g}_room_temp` for every heating circuit, so the point
   concerns web-only mode alone. Whether `B62`–`B67` exist for the remaining
   heating circuits is unconfirmed and measurable on an installation with
   several heating circuits.
2. Collect real diagnostics exports for the flow deviation and the binary
   registers through the field diagnostics template.
3. Validate the new tmodbus path read-only on real hardware for setup, FC03,
   FC04, connection loss and reconnect.
4. Make the module-level import of `pymodbus` in `idm_heatpump.client` optional
   and only then remove the compatibility pin. The public transport contract has
   been in place since API `1.0.1` and is already in use.
5. Maintain the existing Modbus issue for the open central Home Assistant shared
   connection and for a migration-safe provider implementation.
