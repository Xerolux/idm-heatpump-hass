# IDM Heatpump - Home Assistant Integration

<p align="center">
  <img src="../images/heatpump.png" alt="IDM Heatpump" width="300"><br>
  <small><i>AI generated</i></small>
</p>

> **The complete documentation** for the IDM Heatpump integration.
> From installation to troubleshooting — with all features, entities, and services.

> **Important prerequisite:** Modbus TCP must be enabled on the IDM
> Navigator/controller under **Building management system
> (Gebäudeleittechnik) → Modbus TCP → On (Ein)**. See
> [Installation & Setup](Installation-and-Setup#enable-modbus-tcp-on-the-idm-heat-pump).

---

## What is the IDM Heatpump Integration?

The **IDM Heatpump Home Assistant Integration** connects [Home Assistant](https://www.home-assistant.io/) with the [IDM Navigator 2.0 / 10](https://www.idm-energiesysteme.de/) by IDM EnergieSysteme GmbH. It enables complete local control and monitoring of your heat pump via **Modbus TCP — no cloud, no subscription**.

| Feature | Details |
|---------|---------|
| **Protocol** | Modbus TCP (Port 502, Slave ID 1) |
| **Optional supplement** | Local Navigator web API, read-only, PIN optional |
| **Min HA Version** | 2026.5.0 |
| **Python** | 3.13+ (managed by Home Assistant) |
| **pymodbus** | pymodbus>=3.12.1,<4.0 |
| **Library** | idm-heatpump-api[web]==0.7.4 |
| **License** | MIT |
| **Languages** | DE, EN |
| **Entities** | 169+ (109 sensors, 8 binary, 44 numbers, 4 selects, 4 switches) |

---

## Core Features

- **System Monitoring**: Flow, return, hot water, outdoor temperature, pressure, flow rate
- **Heating Circuits A–G**: Up to 7 heating circuits with individual setpoint and mode control
- **Zone Modules**: Up to 10 zones with 6 rooms each (room thermostat function). Current Navigator 10 hardware uses 6 rooms per module.
- **Solar & PV**: Solar hot water heating, PV surplus utilization, battery monitoring
- **Energy Monitoring**: Heat quantity, runtimes, energy meters
- **Cascade & Bivalence**: Multi-heat pump control, heating element integration
- **BMS Remote Maintenance**: BMS temperature requests (cyclic writing)
- **Error Management**: Error detection, error acknowledgment, diagnostics export
- **Optional Web Supplement**: Navigator generation, software version, heat pump model, compact myIDM ID, web-only diagnostics, and Navigator 10 infosystem notifications without replacing Modbus values; default interval 30 seconds
- **Room Temperature Forwarding**: Optional forwarding of Home Assistant temperature sensors to IDM external room temperature registers per heating circuit
- **Readable Diagnostics**: Internal IDM messages are shown with text plus structured code/text attributes

---

## Platforms & Entities

| Platform | Entities | Description |
|----------|----------|-------------|
| **Sensor** | 110+ | Temperatures, pressures, flow rates, energy, PV, solar, cascade, booster, runtime versions |
| **Binary Sensor** | 8+ | Fault alarms, compressor status, heating/cooling/DHW demand |
| **Number** | 44+ | Writable setpoints, limits, GLT parameters, power limits |
| **Select** | 4+ | System mode, circuit modes, solar/ISC mode |
| **Switch** | 4 | External heating/cooling/DHW demand |

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
- **Library-powered**: All registers from [`idm-heatpump`](https://github.com/Xerolux/idm-heatpump-api)
- **Actionable setup diagnostics**: Separate messages for hostname/DNS errors, refused or disabled Modbus TCP, timeouts, unreachable endpoints, wrong slave IDs, invalid web PINs, and unavailable web interfaces
- **Runtime version visibility**: Integration, `idm-heatpump-api`, and `pymodbus` versions are available in a diagnostic sensor, diagnostics exports, and startup logs
- **Data types**: FLOAT, UCHAR, INT8, INT16, UINT16, BOOL, BITFLAG
- **EEPROM protection**: Sensitive registers tracked and protected
- **Auto-recovery**: Exponential backoff on connection errors
- **Navigator 10**: Heat sink sensors, flow rate (Sieb monitoring), groundwater temps, booster A/B
- **Web supplement**: Separate interval, slightly delayed from Modbus polling, and non-fatal when unavailable or disabled
- **Room forwarding**: Optional write path with state-change updates, periodic refresh, tolerance and range checks

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
