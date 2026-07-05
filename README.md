**English** | **[Deutsch](README_de.md)**

# 🔥 IDM Heatpump for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![Downloads][downloads-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hainstall][hainstallbadge]][hainstall]
[![HACS][hacs-badge]][hacs]

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

[![Release Management](https://github.com/Xerolux/idm-heatpump-hass/actions/workflows/release.yml/badge.svg)](https://github.com/Xerolux/idm-heatpump-hass/actions/workflows/release.yml)

> **Control and monitor your IDM Navigator heat pump directly in Home Assistant – 100% local via Modbus TCP.**

<p align="center">
  <img src="https://raw.githubusercontent.com/Xerolux/idm-heatpump-hass/main/docs/images/heatpump.png" alt="IDM Heatpump" width="300"><br>
  <small><i>AI generated image</i></small>
</p>

---

## 🌟 Features

| Category | What's Included |
|----------|----------------|
| **🌡️ System Monitoring** | Flow, return, hot water, outdoor temperature, pressure, flow rate |
| **🔧 Heating Circuits A–G** | Up to 7 heating circuits with individual setpoint and mode control |
| **🏠 Zone Modules** | Up to 10 zones with 6 rooms each (room thermostat function). Navigator 10 / current hardware uses 6 rooms per module. |
| **🌡️ Room Temperature Forwarding** | Optional forwarding of Home Assistant temperature sensors to IDM external room temperature registers per heating circuit |
| **💧 Hot Water** | DHW setpoint and priority control |
| **☀️ Solar & PV** | Solar hot water heating, PV surplus utilization |
| **⚡ Energy Monitoring** | Heat quantity, runtime, energy meters |
| **❄️ Cascade & Bivalence** | Multi-heat pump control, heating element integration |
| **📡 BMS Remote Maintenance** | BMS temperature requests (cyclic writing) |
| **🛡️ Error Management** | Error detection, readable internal messages, error acknowledgment, diagnostics export |
| **🔑 Technician Level** | Optional sensors for technician level 1 & 2 codes (time-based, updated every minute and pinned first) |
| **🔒 Security** | 100% local, Modbus TCP, EEPROM protection, EEPROM-sensitive registers |

---

## ⚡ Quick Start

**1. HACS – Add Integration**

<a href="https://my.home-assistant.io/redirect/hacs_repository/?repository=https%3A%2F%2Fgithub.com%2FXerolux%2Fidm-heatpump-hass&owner=Xerolux&category=Integration" target="_blank" rel="noopener noreferrer"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

```
HACS → Integrations → ⋮ → Custom Repositories
URL: https://github.com/Xerolux/idm-heatpump-hass  |  Category: Integration
→ Download "IDM Heatpump" → Restart HA
```

**2. Set Up Integration**
```
Settings → Devices & Services → Add Integration → "IDM Heatpump"
Enter IP address & port → Configure heating circuits & zones → Done!
```

**3. Done!** 🎉 Your heat pump is now smart.

> Detailed guide → **[Installation & Setup][wiki-install]**

---

## 📖 Documentation (Wiki)

The full documentation is available in the **[Wiki][wiki]**:

| Section | Pages |
|---------|-------|
| 🚀 **Getting Started** | [Installation & Setup][wiki-install] · [Configuration][wiki-config] |
| 📊 **Entities** | [All Entities][wiki-entities] · [Sensors][wiki-sensors] · [Switches][wiki-switches] · [Selects][wiki-selects] · [Numbers][wiki-numbers] |
| ⚙️ **Automation** | [Services Reference][wiki-services] |
| 🔧 **Operation** | [Troubleshooting][wiki-trouble] · [Modbus Registers][wiki-registers] |
| 👩‍💻 **Development** | [Contributing][wiki-contributing] · [Changelog][wiki-changelog] |

Maintainers should run the **[release smoke test](docs/RELEASE_SMOKE_TEST.md)**
before publishing a stable release.

---

## 🔑 Requirements

- Home Assistant **2026.5.0+**
- HACS ([Installation guide](https://hacs.xyz/docs/setup/download))
- IDM Navigator 2.0 / 10 / Pro heat pump with Modbus TCP enabled (port 502)
- Optional local Navigator web PIN for additional read-only web diagnostics
- Python 3.14.2+ (provided by Home Assistant 2026.5)
- `pymodbus>=3.12.1,<4.0` · `idm-heatpump-api[web]>=0.5,<0.6` (installed automatically)

---

## 📋 Supported Platforms

| Platform | Entities | Description |
|----------|----------|-------------|
| **Sensor** | 109+ | Temperatures, pressures, flow rates, energy, PV, solar, cascade, booster, diagnostics |
| **Binary Sensor** | 8+ | Fault alarms, compressor status, heating/cooling/DHW demand |
| **Number** | 44+ | Setpoints, temperatures, limits, GLT parameters, power limits (writable) |
| **Select** | 4+ | System mode, heating circuit modes, solar mode, ISC mode |
| **Switch** | 4 | External heating/cooling/DHW demand, one-time DHW charge |

---

## 🏗️ Architecture

```
Home Assistant
    |
    +-- IdmCoordinator (DataUpdateCoordinator, configurable polling)
    |       |
    |       +-- IdmModbusClient (pymodbus via idm-heatpump library)
    |       |       |
    |       |       +-- IDM Navigator 2.0 / 10 (Modbus TCP, Port 502)
    |       |
    |       +-- Optional local web supplement (PIN, read-only, separate interval)
    |
    |       +-- Optional RoomTempForwarder (HA sensors -> external room temp registers)
    |       |
    |       +-- Entities (sensor, binary_sensor, number, select, switch)
    |
    +-- Services (set_system_mode, acknowledge_errors, write_register)
    |
    +-- Diagnostics (JSON export via HA UI)
```

### Technical Details

- **169+ entities** generated dynamically from the `idm-heatpump` library register map
- **Batch reading**: Consecutive registers are grouped (max. 30 per batch)
- **Data types**: FLOAT (IEEE 754), UCHAR, INT8, INT16, UINT16, BOOL, BITFLAG
- **EEPROM protection**: Sensitive registers are tracked and protected from excessive writing
- **Auto-recovery**: Exponential backoff on connection errors
- **Library-powered**: All register definitions sourced from [`idm-heatpump`](https://github.com/Xerolux/idm-heatpump-api) for consistency across tools
- **Navigator 10 support**: Heat sink (Trennwärmetauscher) sensors, flow rate monitoring (Sieb detection), groundwater temperatures, booster A/B diagnostics
- **Optional web supplement**: local read-only Navigator generation, software version, model, compact myIDM ID and web-only diagnostics; default interval is 30 seconds and Modbus remains authoritative
- **Room temperature forwarding**: disabled by default; can forward selected Home Assistant temperature sensors to the IDM external room temperature registers per heating circuit with a 300 second default interval, immediate updates on state change, 0.2 °C default tolerance and range validation
- **Readable diagnostics**: the `internal_message` sensor shows clear message text and exposes `message_code` / `message_text` attributes instead of a bare numeric code
- **Entity organization**: technician code sensors are pinned at the top, followed by functional groups for configuration, switches, writable values and diagnostics

---

## 💝 Support

This integration is developed in my spare time:

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

- ⭐ Star this repository on GitHub
- 🐛 [Report bugs][issues]
- 📢 Share with other heat pump owners
- 💬 Help others in the [community][forum]

---

## 🔥 About IDM Navigator

The **IDM Navigator 2.0 / 10** by [IDM EnergieSysteme GmbH](https://www.idm-energiesysteme.de/) is a modular heat pump control system with a Modbus TCP interface for seamless Home Assistant integration.

- **Official Shop:** [idm-energiesysteme.de](https://www.idm-energiesysteme.de/)
- **Modbus Documentation:** Navigator 2.0 / 10 Modbus TCP register description

---

## ⚠️ Disclaimer

This project is an **unofficial community project** and is **not affiliated with, endorsed by, or connected to** IDM Energiesysteme GmbH.

- All trademarks, logos, and product names (e.g., "IDM", "Navigator") are property of their respective owners.
- The logos and images used are solely for identifying the compatible device and are not used commercially.
- This project is provided without any warranty. Use at your own risk — especially when writing Modbus registers.
- IDM Energiesysteme GmbH has neither authorized nor endorsed this project.

---

<div align="center">

**Made with ❤️ for the Home Assistant & Heat Pump Community**

[![GitHub][github-shield]][github]

</div>

---

<!-- Wiki Links -->
[paypal]: https://paypal.me/xerolux
[wiki]: https://github.com/Xerolux/idm-heatpump-hass/wiki
[wiki-install]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Installation-and-Setup
[wiki-config]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Configuration
[wiki-entities]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Entities
[wiki-sensors]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Entities#sensors
[wiki-switches]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Entities#switches
[wiki-selects]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Entities#selects
[wiki-numbers]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Entities#numbers
[wiki-services]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Services
[wiki-trouble]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Troubleshooting
[wiki-registers]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Modbus-Register
[wiki-contributing]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing
[wiki-changelog]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Changelog
[violet]: https://github.com/Xerolux/violet-hass

<!-- Badge Links -->
[releases-shield]: https://img.shields.io/github/release/Xerolux/idm-heatpump-hass.svg?style=for-the-badge
[releases]: https://github.com/Xerolux/idm-heatpump-hass/releases
[downloads-shield]: https://img.shields.io/github/downloads/Xerolux/idm-heatpump-hass/latest/total.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/Xerolux/idm-heatpump-hass.svg?style=for-the-badge
[commits]: https://github.com/Xerolux/idm-heatpump-hass/commits/main
[license-shield]: https://img.shields.io/github/license/Xerolux/idm-heatpump-hass.svg?style=for-the-badge
[hainstall]: https://my.home-assistant.io/redirect/config_flow_start/?domain=idm_heatpump
[hainstallbadge]: https://img.shields.io/badge/dynamic/json?style=for-the-badge&logo=home-assistant&logoColor=ccc&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.idm_heatpump.total
[hacs]: https://hacs.xyz
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[github-sponsors]: https://github.com/sponsors/xerolux
[sponsor-badge]: https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue
[kofi]: https://ko-fi.com/xerolux
[kofi-badge]: https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge
[bmac]: https://www.buymeacoffee.com/xerolux
[bmac-badge]: https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge
[forum]: https://community.home-assistant.io/
[github]: https://github.com/Xerolux/idm-heatpump-hass
[github-shield]: https://img.shields.io/badge/GitHub-Xerolux/idm--heatpump--hass-blue?style=for-the-badge&logo=github
[issues]: https://github.com/Xerolux/idm-heatpump-hass/issues
