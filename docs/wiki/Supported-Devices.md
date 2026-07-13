# Supported Devices

## Compatibility Status

The detailed model and firmware status is maintained in the [Compatibility Matrix](Compatibility-Matrix). The table below is a short installation-oriented summary.

## Supported Device Families

| Device | Firmware | Heating Circuits | Zone Modules | Status |
|--------|----------|------------------|--------------|--------|
| IDM Navigator 10 | NAV10_20.23 observed on tested hardware | up to 7 (A–G) | up to 10 (6 default, 8 configurable) | Confirmed on one maintainer test system; firmware value is evidence, not a universal minimum |
| IDM Navigator 2.0 | 2.x observed/expected | up to 7 (A–G) | not confirmed | Expected; Navigator-10-only registers are filtered |
| IDM Navigator Pro | unknown | up to 7 (A–G) | up to 10 (up to 8 configurable rooms) | Expected; needs complete diagnostics report |

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

The following devices may use the same register mapping as the Navigator 2.0 / 10, but are not yet confirmed in the public community test matrix:

- IDM Terra SW (with Navigator 2.0 / 10 controller)
- IDM Terra HT (with Navigator 2.0 / 10 controller)
- IDM Aero SLM (with Navigator 2.0 / 10 controller)

> **Note:** If you successfully use an unlisted IDM device, please share a detailed [compatibility report in Q&A](https://github.com/Xerolux/idm-heatpump-hass/discussions/categories/q-a) so we can expand the list. Select **Devices or firmware compatibility** in the form.

## Modbus Register Compatibility

The integration builds a model- and configuration-dependent Modbus register map
from the [`idm-heatpump`](https://github.com/Xerolux/idm-heatpump-api) library:

- **Read memory** (Input Registers): Temperatures, status, energy, power
- **Read/Write memory** (Holding Registers): Operating modes, setpoints, configuration

Details on all registers: [Modbus Register Wiki](Modbus-Register)

Compatibility evidence and report fields: [Compatibility Matrix](Compatibility-Matrix)

## Known Firmware-specific Differences

- Register 1048 (`current_energy_price`) is optional and firmware-dependent;
  the integration isolates it when the active controller does not support it.
- Zone registers (from 2000) require installed and detected/configured zone
  modules. They are not enabled solely from the Navigator family name.
- PV registers (74–86) require the optional PV module

## Local Web Compatibility

- Navigator 2.0 uses the local HTTP/CSRF client (`nav20` internally).
- Navigator 10 and Navigator Pro use the Navigator-10 WebSocket client
  (`nav10` internally).
- Setup/reconfiguration can test both variants; normal polling remains on the
  one that actually succeeded. See [Local Navigator Web
  Interface](Local-Web-Interface).
