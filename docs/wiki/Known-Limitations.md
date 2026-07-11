# Known Limitations

## Device Compatibility

- **Only IDM Navigator 2.0 / 10 / Navigator Pro** are confirmed in the current community test matrix
- Older IDM controllers without Navigator firmware are **not** supported
- Modbus register mapping may vary slightly between firmware versions

## Modbus TCP

- Only **Modbus TCP** is supported (no serial Modbus RTU)
- Port and Slave ID must be configured correctly
- Some controller/firmware combinations tolerate only limited parallel Modbus clients. If timeouts correlate with another automation system, test with that client stopped or increase the polling interval

## EEPROM Protection

- **88 registers** are EEPROM-protected and can only be written **once per minute**
- More frequent write operations to these registers can cause hardware wear
- The integration enforces this limit automatically

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

## No Push Notifications

- The integration is a **polling client** — the heat pump does not send change notifications
- Changes made on the device (e.g., via the Navigator web interface) are only visible in HA after the next polling cycle

## Firmware Version

- The current firmware version is read as a diagnostic sensor (`firmware_version`)
- Firmware updates directly from Home Assistant are **not** possible
- Updates are done via the IDM web interface or USB

## Deliberately Not Implemented

- **Climate entity:** Not exposed yet because IDM modes combine heating circuits, rooms, cooling and hot water in ways that do not map cleanly to one Home Assistant climate entity.
- **Web UI scraping:** Not used as a core path. The integration stays on the documented local Modbus/API contract and does not depend on Navigator web-login cookies.
- **Global `force_update`:** Not enabled by default. External time-series systems should use recorder/InfluxDB configuration or selected helper sensors to avoid unnecessary Home Assistant database load.
