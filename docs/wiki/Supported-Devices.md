# Supported Devices

## Fully Supported

| Device | Firmware | Heating Circuits | Zone Modules | Status |
|--------|----------|------------------|--------------|--------|
| IDM Navigator 2.0 | all versions | up to 7 (A–G) | no | ✅ Confirmed |
| IDM Navigator 10 | 2025+ (NAV10_20.23+) | up to 7 (A–G) | up to 10 (6 rooms each) | ✅ Confirmed |
| IDM Navigator Pro | all versions | up to 7 (A–G) | up to 10 (6 rooms each) | ✅ Confirmed |

## Requirements

- **Modbus TCP** must be enabled in the Navigator controller
  - Setting: *Technician level → Communication → Modbus TCP*
  - Default port: **502**
  - Default Slave ID: **1**

## Unsupported Devices

| Device | Reason |
|--------|--------|
| IDM older controllers (pre Navigator 2.0 / 10) | Different register mapping |
| IDM devices without network connection | No Modbus TCP |
| Other heat pump manufacturers | Different Modbus protocol / register layout |

## Untested Devices (possibly compatible)

The following devices may use the same register mapping as the Navigator 2.0 / 10, but have not been officially tested:

- IDM Terra SW (with Navigator 2.0 / 10 controller)
- IDM Terra HT (with Navigator 2.0 / 10 controller)
- IDM Aero SLM (with Navigator 2.0 / 10 controller)

> **Note:** If you successfully use an unlisted IDM device, please create a [GitHub Issue](https://github.com/Xerolux/idm-heatpump-hass/issues) so we can expand the list!

## Modbus Register Compatibility

The integration reads **168+ Modbus registers** dynamically generated from the [`idm-heatpump`](https://github.com/Xerolux/idm-heatpump-api) library:

- **Read memory** (Input Registers): Temperatures, status, energy, power
- **Read/Write memory** (Holding Registers): Operating modes, setpoints, configuration

Details on all registers: [Modbus Register Wiki](Modbus-Register)

## Known Firmware-specific Differences

- Register 1048 (`current_energy_price`) is available from Navigator 2.0 / 10 firmware 2.x
- Zone module registers (from 2000) require the IDM Navigator Pro hardware module
- PV registers (74–86) require the optional PV module
