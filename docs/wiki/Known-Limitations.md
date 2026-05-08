# Known Limitations

## Device Compatibility

- **Only IDM Navigator 2.0 / Navigator Pro** are officially supported
- Older IDM controllers without Navigator firmware are **not** supported
- Modbus register mapping may vary slightly between firmware versions

## Modbus TCP

- Only **Modbus TCP** is supported (no serial Modbus RTU)
- Port and Slave ID must be configured correctly
- Simultaneous connections from multiple clients (e.g., IDM web interface + HA) can cause timeout errors
- Recommendation: Disable other Modbus clients during operation or increase the polling interval

## EEPROM Protection

- **88 registers** are EEPROM-protected and can only be written **once per minute**
- More frequent write operations to these registers can cause hardware wear
- The integration enforces this limit automatically

## Single Device per Configuration Entry

- Only **one** IDM heat pump can be configured per Home Assistant instance via Modbus TCP (due to IP-based unique ID)
- For multiple heat pumps on the same bus: use separate Slave IDs and create a separate entry for each

## Read-only Access to Certain Registers

- Some registers are **read-only** (e.g., energy meters, temperature sensors)
- Attempting to write to read-only registers may return a Modbus error
- The `write_register` service bypasses this protection — **for experienced users only**

## Zone Modules

- A maximum of **10 zone modules** with up to **8 rooms** each are supported
- Zone module configuration is adjustable via options after initial setup
- Rooms without a physical sensor may return `-1.0` as a value (marked as unavailable)

## No Push Notifications

- The integration is a **polling client** — the heat pump does not send change notifications
- Changes made on the device (e.g., via the Navigator web interface) are only visible in HA after the next polling cycle

## Firmware Version

- The current firmware version is read as a diagnostic sensor (`firmware_version`)
- Firmware updates directly from Home Assistant are **not** possible
- Updates are done via the IDM web interface or USB
