<p align="center"><strong>English</strong> · <a href="README_de.md">Deutsch</a></p>

<div align="center">
  <a href="https://xerolux.github.io/idm-heatpump-hass/">
    <img src="https://raw.githubusercontent.com/Xerolux/idm-heatpump-hass/main/docs/images/heatpump.png" alt="IDM Heatpump" width="240">
  </a>
  <h1>IDM Heatpump for Home Assistant</h1>
  <p><strong>Monitor and control your IDM Navigator heat pump locally through Modbus TCP — without a cloud dependency.</strong></p>
  <p>
    <a href="https://xerolux.github.io/idm-heatpump-hass/"><strong>Website</strong></a> ·
    <a href="https://xerolux.github.io/idm-heatpump-hass/docs/#/home"><strong>Documentation</strong></a> ·
    <a href="https://github.com/Xerolux/idm-heatpump-hass/releases/latest"><strong>Download</strong></a> ·
    <a href="https://github.com/Xerolux/idm-heatpump-hass/discussions"><strong>Community</strong></a>
  </p>
</div>

<p align="center">
  <a href="https://github.com/Xerolux/idm-heatpump-hass/releases"><img src="https://img.shields.io/github/release/Xerolux/idm-heatpump-hass.svg?style=for-the-badge" alt="Latest release"></a>
  <a href="https://github.com/Xerolux/idm-heatpump-hass/releases"><img src="https://img.shields.io/github/downloads/Xerolux/idm-heatpump-hass/latest/total.svg?style=for-the-badge" alt="Downloads"></a>
  <a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=idm_heatpump"><img src="https://img.shields.io/badge/Home%20Assistant-Install-41BDF5.svg?style=for-the-badge&logo=home-assistant&logoColor=white" alt="Add to Home Assistant"></a>
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge" alt="HACS custom integration"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Xerolux/idm-heatpump-hass.svg?style=for-the-badge" alt="MIT License"></a>
</p>

> [!TIP]
> New here? Start with the **[Installation & Setup guide][wiki-install]** or explore the **[searchable documentation][wiki]**.

---

## 🌟 Features

| Category | What's Included |
|----------|----------------|
| **🌡️ System Monitoring** | Flow, return, hot water, outdoor temperature, pressure, flow rate |
| **🔧 Heating Circuits A–G** | Up to 7 heating circuits with individual setpoint and mode control |
| **🏠 Zone Modules** | Up to 10 zones with up to 8 configurable rooms each (room thermostat function); 6 rooms is the current Navigator 10 default. |
| **🌡️ Room Temperature Forwarding** | Optional forwarding of Home Assistant temperature sensors to IDM external room temperature registers per heating circuit |
| **💧 Hot Water** | DHW setpoint and priority control |
| **☀️ Solar & PV** | Solar hot water heating, PV surplus utilization |
| **⚡ Energy Monitoring** | Heat quantity, runtime, energy meters |
| **❄️ Cascade & Bivalence** | Multi-heat pump control, heating element integration |
| **📡 BMS Remote Maintenance** | BMS temperature requests (cyclic writing) |
| **🛡️ Error Management** | Error detection, readable internal messages, error acknowledgment, diagnostics export |
| **🧭 Guided Setup Diagnostics** | Distinguishes unknown hosts, refused/disabled Modbus TCP, timeouts, unreachable networks, wrong slave IDs, invalid web PINs and unavailable web interfaces |
| **🧪 Read-only Connection Test** | Reconfigure menu can test the saved Modbus and optional local web connection without changing settings or writing registers |
| **📦 Runtime Versions** | Diagnostic sensor and export show the installed integration, `idm-heatpump-api` and `pymodbus` versions |
| **🔑 Technician Level** | Optional sensors for the current level 1 & 2 access codes (disabled by default, updated every minute and pinned first) |
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

**2. Enable Modbus TCP on the IDM heat pump — required for full operation**

On the IDM Navigator/controller open:

```text
Building management system (BMS / Gebäudeleittechnik)
→ Modbus TCP
→ On / Enabled
```

Then connect the Navigator to the local network, note its IP address and keep
the usual values **port 502** and **slave/unit ID 1**. Depending on the
Navigator generation, software version and access level, the menu name can
differ or be available only at installer/technician level. If the option is
missing or locked, ask your heating installer or iDM service to enable it.

This is the Modbus TCP setting of the **heat pump/Navigator**, not a similarly
named setting on a PV inverter. See the
[detailed activation guide][wiki-install-modbus] and the
[official iDM technical document][idm-modbus-source].

**3. Set Up Integration**
```
Settings → Devices & Services → Add Integration → "IDM Heatpump"
Enter heat pump IP, port 502 and slave ID 1 → Configure heating circuits & zones → Done!
```

If setup fails, the flow explains whether the hostname is invalid, the TCP
connection was refused (often Modbus TCP is disabled), the request timed out,
or the controller did not answer for the selected slave ID. An optional local
web PIN enables a validated, read-only web-only fallback.

Later, use **Settings → Devices & Services → IDM Heatpump → Reconfigure →
Test current connection** for a safe repeatable Modbus and optional web test.

Writable controls are exposed as `number`, `select` and `switch` entities and
can also be selected under **Automations → Add action**. For register-level
diagnosis, the Navigator's **GLT Monitor** can be compared with the integration
diagnostics without writing test values.

**4. Done!** 🎉 Your heat pump is now smart.

> Detailed guide → **[Installation & Setup][wiki-install]**

---

## 📖 Documentation

The complete, searchable documentation is available on the **[project website][wiki]**:

| Section | Pages |
|---------|-------|
| 🚀 **Getting Started** | [Installation & Setup][wiki-install] · [Configuration][wiki-config] |
| 📊 **Entities** | [All Entities][wiki-entities] · [Sensors][wiki-sensors] · [Switches][wiki-switches] · [Selects][wiki-selects] · [Numbers][wiki-numbers] |
| ⚙️ **Automation** | [Services Reference][wiki-services] |
| 🔧 **Operation** | [Troubleshooting][wiki-trouble] · [Modbus Registers][wiki-registers] · [Stability & Release Readiness][wiki-stability] |
| 👩‍💻 **Development** | [Contributing][wiki-contributing] · [Changelog][wiki-changelog] |

Maintainers should run the **[release smoke test](docs/RELEASE_SMOKE_TEST.md)**
before publishing a stable release.

---

## 🔑 Requirements

- Home Assistant **2026.5.0+**
- HACS ([Installation guide](https://hacs.xyz/docs/setup/download))
- IDM Navigator 2.0 / 10 / Pro heat pump with Modbus TCP enabled (port 502)
- Optional local Navigator web PIN for additional read-only web diagnostics
- Python 3.13+ (provided by Home Assistant)
- `pymodbus>=3.12.1,<4.0` · `idm-heatpump-api[web]==0.8.3` (installed automatically)

---

## 📋 Supported Platforms

| Platform | Entities | Description |
|----------|----------|-------------|
| **Sensor** | model-dependent | Temperatures, pressures, flow rates, energy, PV, solar, cascade, booster, runtime versions and diagnostics |
| **Binary Sensor** | model-dependent | Fault alarms, compressor status, heating/cooling/DHW demand |
| **Number** | model-dependent | Setpoints, temperatures, limits, GLT parameters, power limits (writable) |
| **Select** | model-dependent | System mode, heating circuit modes, solar mode, ISC mode |
| **Switch** | model-dependent | External heating/cooling/DHW demand, one-time DHW charge |

<details>
<summary><strong>🏗️ Architecture & technical details</strong></summary>

### Architecture

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

- **Dynamic entities** generated from the detected model, enabled circuits, zones and optional capabilities
- **Batch reading**: only exactly adjacent, non-overlapping register ranges are grouped, up to 40 Modbus words per request
- **Value safety**: declared unavailable sentinels are treated as unused; implausible batch values are verified individually and quarantined for the client session
- **Data types**: FLOAT (IEEE 754), UCHAR, INT8, INT16, UINT16, BOOL, BITFLAG
- **EEPROM protection**: Sensitive registers are tracked and protected from excessive writing
- **Auto-recovery**: Exponential backoff on connection errors
- **Library-powered**: All register definitions sourced from [`idm-heatpump`](https://github.com/Xerolux/idm-heatpump-api) for consistency across tools
- **Navigator 10 support**: Heat sink (Trennwärmetauscher) sensors, flow rate monitoring (Sieb detection), groundwater temperatures, booster A/B diagnostics
- **Optional web supplement**: setup detects Navigator 2.0 HTTP or Navigator 10/Pro WebSocket locally, remembers the successful protocol, reuses that session and keeps routine reconnects on the known variant; Modbus remains authoritative
- **Room temperature forwarding**: disabled by default; can forward selected Home Assistant temperature sensors to the IDM external room temperature registers per heating circuit with a 300 second default interval, immediate updates on state change, 0.2 °C default tolerance and range validation
- **Readable diagnostics**: the `internal_message` sensor shows clear message text and exposes `message_code` / `message_text` attributes instead of a bare numeric code
- **Actionable connection diagnostics**: setup, reconfigure, logs and repairs distinguish DNS/hostname errors, refused TCP connections, timeouts, unreachable endpoints, missing Modbus replies, wrong web PINs and web-interface failures
- **Built-in test menu**: Reconfigure offers a non-destructive connection test for a known IDM Modbus register, targeted DNS/TCP failure classification and, when configured, local Navigator web authentication
- **Visible runtime stack**: the diagnostic `IDM Heatpump API version` sensor exposes the installed API version and includes the integration and `pymodbus` versions as attributes; the same versions are included in diagnostics exports and startup logs
- **Entity organization**: technician code sensors are pinned at the top, followed by functional groups for configuration, switches, writable values and diagnostics
- **PV/GLT correctness**: float inputs use IDM word order, battery SOC is a single signed 16-bit percentage value, and documentation warns against multiple energy managers writing the same register
- **Hardware-assisted diagnosis**: troubleshooting explains how to compare Home Assistant values and timestamps with the Navigator GLT Monitor
- **Private diagnostics**: Modbus/web hosts, port, slave ID and local web PIN are redacted; detailed web connection strings are reduced to a safe error category

</details>

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
- 💬 Ask questions and help others in [GitHub Discussions][discussions]

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

<!-- Documentation Links -->
[paypal]: https://paypal.me/xerolux
[wiki]: https://xerolux.github.io/idm-heatpump-hass/docs/#/home
[wiki-install]: https://xerolux.github.io/idm-heatpump-hass/docs/#/installation-and-setup
[wiki-install-modbus]: https://xerolux.github.io/idm-heatpump-hass/docs/#/installation-and-setup/enable-modbus-tcp-on-the-idm-heat-pump
[wiki-config]: https://xerolux.github.io/idm-heatpump-hass/docs/#/configuration
[wiki-entities]: https://xerolux.github.io/idm-heatpump-hass/docs/#/entities
[wiki-sensors]: https://xerolux.github.io/idm-heatpump-hass/docs/#/entities/sensors
[wiki-switches]: https://xerolux.github.io/idm-heatpump-hass/docs/#/entities/switches
[wiki-selects]: https://xerolux.github.io/idm-heatpump-hass/docs/#/entities/selects
[wiki-numbers]: https://xerolux.github.io/idm-heatpump-hass/docs/#/entities/numbers
[wiki-services]: https://xerolux.github.io/idm-heatpump-hass/docs/#/services
[wiki-trouble]: https://xerolux.github.io/idm-heatpump-hass/docs/#/troubleshooting
[wiki-stability]: https://xerolux.github.io/idm-heatpump-hass/docs/#/stability-and-release-readiness
[idm-modbus-source]: https://www.idm-energie.at/wp-content/uploads/2021/04/PV_Nutzung_GLT-Smartfox.pdf
[wiki-registers]: https://xerolux.github.io/idm-heatpump-hass/docs/#/modbus-register
[wiki-contributing]: https://xerolux.github.io/idm-heatpump-hass/docs/#/contributing
[wiki-changelog]: https://xerolux.github.io/idm-heatpump-hass/docs/#/changelog
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
[discussions]: https://github.com/Xerolux/idm-heatpump-hass/discussions
[github]: https://github.com/Xerolux/idm-heatpump-hass
[github-shield]: https://img.shields.io/badge/GitHub-Xerolux/idm--heatpump--hass-blue?style=for-the-badge&logo=github
[issues]: https://github.com/Xerolux/idm-heatpump-hass/issues
