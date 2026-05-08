# IDM Heatpump - Home Assistant Integration

<p align="center">
  <img src="../images/heatpump.png" alt="IDM Heatpump" width="300"><br>
  <small><i>AI generated</i></small>
</p>

> **The complete documentation** for the IDM Heatpump integration.
> From installation to troubleshooting — with all features, entities, and services.

---

## What is the IDM Heatpump Integration?

The **IDM Heatpump Home Assistant Integration** connects [Home Assistant](https://www.home-assistant.io/) with the [IDM Navigator 2.0](https://www.idm-energiesysteme.de/) by IDM EnergieSysteme GmbH. It enables complete local control and monitoring of your heat pump via **Modbus TCP — no cloud, no subscription**.

| Feature | Details |
|---------|---------|
| **Protocol** | Modbus TCP (Port 502, Slave ID 1) |
| **Min HA Version** | 2025.12.0 |
| **Tested up to** | 2026.5 |
| **Python** | 3.13+ (HA 2026.3: 3.14.2) |
| **pymodbus** | ≥3.7.0 (HA 2026.3: 3.11.2) |
| **License** | MIT |
| **Languages** | DE, EN |
| **Registers** | 663 (215 RO, 266 RW, 16 W-only, 166 context-dependent) |

---

## Core Features

- **System Monitoring**: Flow, return, hot water, outdoor temperature, pressure, flow rate
- **Heating Circuits A–G**: Up to 7 heating circuits with individual setpoint and mode control
- **Zone Modules**: Up to 10 zones with 8 rooms each (room thermostat function)
- **Solar & PV**: Solar hot water heating, PV surplus utilization, battery monitoring
- **Energy Monitoring**: Heat quantity, runtimes, energy meters
- **Cascade & Bivalence**: Multi-heat pump control, heating element integration
- **BMS Remote Maintenance**: BMS temperature requests (cyclic writing)
- **Error Management**: Error detection, error acknowledgment, diagnostics export

---

## Platforms & Entities

| Platform | Entities | Description |
|----------|----------|-------------|
| **Sensor** | 100+ | Temperatures, pressures, flow rates, energy, runtimes |
| **Binary Sensor** | 9 | Error status, switch states |
| **Number** | ~30 | Setpoints, writable parameters |
| **Select** | ~15 | Operating modes (system, circuit, room, solar) |
| **Switch** | 4 | BMS temperature requests |

---

## Quick Navigation

### I'm new here
1. [Installation & Setup](Installation-and-Setup)
2. [Configuration](Configuration)
3. [Entities](Entities)

### I want to automate
1. [Services Reference](Services)

### I have a problem
1. [Troubleshooting](Troubleshooting)
2. [Modbus Registers](Modbus-Register)

### I want to contribute
- [Contributing Guide](Contributing)

---

## Technical Details

- **Batch reading**: Consecutive registers are grouped (max. 30 per batch)
- **Data types**: FLOAT (IEEE 754, 2 registers), UCHAR (8-bit), WORD (16-bit), BOOL
- **EEPROM protection**: 88 EEPROM-sensitive registers are protected from excessive writing
- **Auto-recovery**: Exponential backoff on connection errors
- **Address ranges**: 74-86 (PV/Battery), 1000-1199 (System), 1200-1349 (Cascade), 1350-1699 (Heating Circuits A-G), 1700-1799 (BMS/Energy), 2000-2999 (Zones)

---

## Links & Resources

| Resource | Link |
|----------|------|
| GitHub Repository | https://github.com/Xerolux/idm-heatpump-hass |
| Issues & Bugs | https://github.com/Xerolux/idm-heatpump-hass/issues |
| HACS | https://hacs.xyz/ |
| Home Assistant | https://www.home-assistant.io/ |
| IDM EnergieSysteme | https://www.idm-energiesysteme.de/ |
| Community Forum | https://community.home-assistant.io/ |

---

*This wiki documents the IDM Heatpump integration.*
*Developed by [Xerolux](https://github.com/Xerolux)*
