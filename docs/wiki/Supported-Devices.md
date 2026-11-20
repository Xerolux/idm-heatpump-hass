# iDM heat pump models for Home Assistant

## Compatibility Status

The detailed model and firmware status is maintained in the [Compatibility Matrix](Compatibility-Matrix). The table below is a short installation-oriented summary.

## Supported Device Families

| Device | Firmware | Heating Circuits | Zone Modules | Status |
|--------|----------|------------------|--------------|--------|
| IDM Navigator 10 | NAV10_20.23 observed on tested hardware | up to 7 (A–G) | up to 10 (6 default, 8 configurable) | Confirmed on one maintainer test system; firmware value is evidence, not a universal minimum |
| IDM Navigator 2.0 | 2.x observed/expected | up to 7 (A–G) | not confirmed | Expected; Navigator-10-only registers are filtered |
| IDM Navigator Pro | unknown | up to 7 (A–G) | up to 10 (up to 8 configurable rooms) | Expected; needs complete diagnostics report |
| IDM Navigator 1.0 / 1.7 | n1.x firmware | A–G as installed | Separate 1.x family; do not assume the 2.0/10 zone map | Official 1.x sensor/coil map and writable holding block; water-heater card and one-shot actions where mapped. Broader firmware/hardware confirmation remains open. |

## Requirements

- **Modbus TCP** must be enabled in the Navigator controller
  - Setting: *Communication → Modbus TCP* at the controller's installer
    level — enabled by your heating installer; the integration never
    unlocks it
  - Default port: **502**
  - Default Slave ID: **1**

## Unsupported Devices

| Device | Reason |
|--------|--------|
| IDM devices without network connection | No Modbus TCP |
| Other heat pump manufacturers | Different Modbus protocol / register layout |

## Compatibility by heat pump model

Use the model name on the heat pump and identify its Navigator controller and
firmware separately. For Modbus TCP setup, the Navigator family determines
the register map. The amount of data and the controls exposed also depend on
firmware and installed equipment. A field test applies to the combination
listed in the table.

### iDM AERO ALM and AERO SLM with Home Assistant

| Heat pump | Navigator and evidence |
| --- | --- |
| **iDM AERO ALM 6–15** (ALM) | **Navigator 10 observed in use.** Field diagnostics record temperatures, hot-water thresholds and operating behavior on firmware `T_NAV10_20.24-1580`. The separate one-time hot-water boost fix still awaits field confirmation. See [field findings](Findings-and-Documentation). |
| **iDM AERO SLM** (SLM) | Potentially compatible with Navigator 2.0 or 10 and Modbus TCP enabled. A complete model, firmware and feature test is still outstanding. |

### iDM TERRA SW, SWM and HT with Home Assistant

| Heat pump | Navigator and evidence |
| --- | --- |
| **iDM TERRA SWM** | Navigator 2.0 compatibility is expected. A raw model-detection capture is still needed for the case in the [compatibility matrix](Compatibility-Matrix). |
| **iDM TERRA SW and TERRA HT** | Potentially compatible with Navigator 2.0 or 10. The public matrix has no complete model-specific test. |

### iDM iPUMP with Home Assistant

| Heat pump | Navigator and evidence |
| --- | --- |
| **iDM iPUMP A ONE 2–8** | A [Navigator 10 installation report](https://github.com/Xerolux/idm-heatpump-hass/issues/710) identifies this model. The reported heating-circuit flow setpoint issue still needs diagnostics. |
| **iDM iPUMP ALM, iPUMP A, iPUMP T and iPUMP T7** | Check the Navigator family and its Modbus TCP menu before setup. The public matrix lacks complete model-specific verification for these series. |

For **AERO ALM MAX, AERO AL MAX, TERRA SW MAX, TERRA TWIN and iPUMP N5
(NANO)**, the public matrix also lacks a model-specific test. Check the
controller and its interface before planning an installation. [iDM product
overview](https://www.idm-energie.at/idm-produkte/)

Once you identify the controller, follow the [Home Assistant installation
guide](Installation-and-Setup).

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
