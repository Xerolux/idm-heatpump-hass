# Known Limitations

## Device Compatibility

- Navigator 10 has direct maintainer hardware confirmation. Navigator 2.0 and
  Navigator Pro are expected from the typed register model but still need
  complete diagnostics across current firmware variants.
- Older IDM controllers without Navigator firmware are **not** supported
- Modbus register mapping may vary slightly between firmware versions

## Modbus TCP

- Only **Modbus TCP** is supported (no serial Modbus RTU)
- Port and Slave ID must be configured correctly
- Some controller/firmware combinations tolerate only limited parallel Modbus clients. If timeouts correlate with another automation system, test with that client stopped or increase the polling interval

## Write Frequency

- Some Modbus registers are backed by EEPROM storage on the controller and
  tolerate only limited write cycles over the hardware lifetime.
- The integration logs a warning when the same register address is written
  more than once within 5 seconds, which helps catch runaway automation loops.
- For the raw `write_register` service, users must acknowledge the risk
  explicitly. No automatic hard-block prevents frequent EEPROM writes — treat
  unknown addresses with care.

## Single Device per Configuration Entry

- Multiple IDM heat pumps are supported. Each connection must have a unique host, port, and slave-ID combination.
- For multiple heat pumps on the same bus: use separate Slave IDs and create a separate entry for each

## Read-only Access to Certain Registers

- Some registers are **read-only** (e.g., energy meters, temperature sensors)
- Attempting to write to read-only registers may return a Modbus error
- The `write_register` service deliberately permits an explicitly acknowledged custom address, but still validates datatype and numeric encoding. It cannot infer safe ranges, EEPROM behavior or semantics for unknown addresses — **for experienced users only**

## Zone Modules

- A maximum of **10 zone modules** with up to **8 configurable rooms** each is supported. Six rooms is the current Navigator 10 default; only configure physically present rooms.

## Model and Firmware Evidence

- Navigator 10 has direct maintainer hardware coverage.
- Navigator 2.0 and Navigator Pro remain dependent on complete community diagnostics across firmware variants.
- A responding probe address alone may not prove an optional feature exists; unavailable sentinels are considered where hardware evidence exists.
- See [Stability & Release Readiness](Stability-and-Release-Readiness) for the current blockers before removing the beta label.
- Zone module configuration is adjustable via options after initial setup
- Rooms without a physical sensor may return `-1.0` as a value (marked as unavailable)

## Scheduled Updates Rather Than HA Push Updates

- Home Assistant state is updated through scheduled Modbus and optional web
  refreshes. The integration does not currently expose unsolicited controller
  events as immediate Home Assistant push updates.
- Changes made elsewhere become visible after the relevant refresh interval.

## Firmware Version

- The current firmware version is read as a diagnostic sensor (`firmware_version`)
- Firmware updates directly from Home Assistant are **not** possible
- Updates are done via the **myIDM cloud portal** or via a **USB stick using the
  controller display's service menu** (unlocked with the *Fachmann Ebene* codes
  the integration can calculate).
- The three local interfaces exposed by the controller (Modbus TCP 502,
  Navigator HTTP 80, Navigator 10 WebSocket 61220) **do not** carry any
  firmware-update endpoint. All candidate WebSocket controllers
  (`firmware`, `update`, `upgrade`, `software`, `usb`, `upload`,
  `maintenance`, `system.update`, `system.firmware`, `system.software`,
  `system.usb`) respond with `provided controller [...] is not supported!`.
  See [Navigator Protocol Analysis](Navigator-Protocol-Analysis) for the
  full verified controller catalog.

## Heat-sink Sensors Without Plate Heat Exchanger

The heat-sink block (return/flow temperature, flow rate, charging-pump signal)
only exists on plants with a plate heat exchanger (Trennwärmetauscher). Without
one, the controller reports the not-present sentinel (`-1.0`) for the whole
block and the entities correctly show *unavailable*.

The flow-rate register (`heat_sink_flow_rate`, address 1072) is listed as
UCHAR in the older revisions of the official IDM doc (Navigator 2.0 up to
rev 12, Navigator 10 rev 0); newer revisions corrected it to FLOAT, matching
the **word-swapped FLOAT32** that field readings (discussion #516) proved the
controller serves. Before
integration 0.23.0-b8 (idm-heatpump-api 2.14.4) the UCHAR decode read one byte
of the float's low word, which produced a spurious **0.0 L/min** on plants
without a plate heat exchanger and jumping, far-too-high values on plants with
a live flow signal. The register is now read as a float: real flow values
display correctly, not-present plants report *unavailable*, and when the web
supplement serves a flowmeter value it fills in for the not-present register
automatically. On plants without a plate heat exchanger and without a web
flowmeter row, simply disable the entity — nothing is wrong with the heat pump.

## Deliberately Not Implemented

- **Web connection as the core path:** Modbus operation does not depend on a web
  login. The optional read-only supplement uses the supported local Navigator
  HTTP or WebSocket session and can provide a limited web-only fallback.
- **Global `force_update`:** Not enabled by default. External time-series systems should use recorder/InfluxDB configuration or selected helper sensors to avoid unnecessary Home Assistant database load.
