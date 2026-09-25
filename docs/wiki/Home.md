# IDM Heatpump - Home Assistant Integration

<p align="center">
  <img src="../images/idm-home-assistant-hero.png" alt="IDM Heatpump integration: local Modbus TCP, local Navigator data and optional KNX" width="900"><br>
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

The **IDM Heatpump Home Assistant Integration** connects [Home Assistant](https://www.home-assistant.io/) with IDM Navigator controllers by IDM EnergieSysteme GmbH. It enables local monitoring and supported controls via **Modbus TCP — no cloud, no subscription**. Navigator 10 has direct hardware confirmation; Navigator 2.0 and Navigator Pro remain under broader compatibility validation.

| Feature | Details |
|---------|---------|
| **Protocol** | Modbus TCP (Port 502, Slave ID 1) |
| **Optional supplement** | Local Navigator web API, read-only, PIN optional |
| **Documentation version** | [0.18.0](https://github.com/Xerolux/idm-heatpump-hass/releases/tag/v0.18.0); [latest stable release](https://github.com/Xerolux/idm-heatpump-hass/releases/latest) |
| **Supported/tested HA baseline** | 2026.8.1 |
| **Python** | 3.14+ (managed by Home Assistant) |
| **Connection library** | modbus-connection==4.12.2 |
| **Socket backend** | tmodbus[async-serial]==0.6.2 |
| **Device/web library** | idm-heatpump-api[web]==2.4.3 |
| **License** | MIT |
| **Languages** | DE, EN |
| **Entities** | Model- and configuration-dependent sensors, binary sensors, numbers, selects, switches, climate, water heater, and buttons |

---

## Core Features

### New in 0.18.0

0.18.0 ships two flagship feature sets — the optional **Smart Energy & Comfort** package and the experimental **AI plant adviser** — plus a guided setup that replaces the long options form. Everything stays local by default and every automatic control remains off until explicitly enabled.

<p align="center">
  <img src="../images/smart-energy-comfort-overview.svg" alt="Smart Energy and Comfort overview: energy and costs, health monitor and advice, comfort schedules and PV boost, external power forwarding" width="860">
</p>

| Feature | What you can do | Device writes |
|---------|-----------------|---------------|
| Standard / Advanced / Expert setup | Choose the amount of configuration detail; all three modes offer the same functions | Selecting a mode does not write registers |
| Smart or Vanilla profile | Keep the core controller entities, or add energy and operating analysis with Smart | Analysis is read-only; boost controls write when used |
| Persistent energy statistics | Track electrical and thermal energy, COP, estimated costs, CO₂ and PV use | None |
| PV surplus DHW manager | Start a bounded hot-water boost using selected HA power and optional battery sensors | Optional; off by default, exclusive-control confirmation required |
| Comfort schedules | Apply daily room targets to selected circuits, with up to 16 windows and conditional restore | Optional; off by default, exclusive-control confirmation required |
| Heating and weather advice | Read flow-temperature hints and a six-hour weather recommendation | None |
| Health Monitor and installer report | Inspect eight diagnostic checks, operation history and redacted diagnostics | None |
| External power forwarding | Forward PV, household, battery and surplus sensors to the existing GLT registers | Optional; off until configured |
| Feature device groups | Find Analytics, Health Monitor, Comfort and Diagnostics separately | None; entity IDs remain unchanged |
| **AI plant adviser** *(experimental)* | Daily, weekly, health and efficiency reports from measured facts — by default without any model call; dedicated AI device, four report buttons, dashboard export, restart-safe schedule, local statistical learning with live progress | None; read-only, off by default |
| **Optional model explanations** | Free-form reports via local Ollama, an existing HA AI Task entity, or consented OpenAI/Z.ai — numeric-integrity guard, numerical fact allowlist, daily request limit | None; consent required for cloud paths |

<p align="center">
  <img src="../images/ai-adviser-overview.svg" alt="AI plant adviser overview: local history, learning, measured-data reports by default, optional model explanations behind explicit consent" width="860">
</p>

Start with [iDM Smart Energy & Comfort](Smart-Energy-and-Comfort) for activation,
examples, defaults and limitations, and with the
[Experimental AI adviser](Experimental-AI-Adviser) for setup, report modes,
privacy and the dashboard.

### Controller integration

- **System Monitoring**: Flow, return, hot water, outdoor temperature, pressure, flow rate
- **Heating Circuits A–G**: Up to 7 heating circuits with individual setpoint and mode control
- **Zone Modules**: Up to 10 zones with up to 8 configurable rooms each; current Navigator 10 hardware defaults to 6 rooms per module.
- **Solar & PV**: Solar hot water heating, PV surplus utilization, battery monitoring
- **Energy Monitoring**: Heat quantity, runtimes, energy meters
- **Cascade & Bivalence**: Multi-heat pump control, heating element integration
- **BMS Remote Maintenance**: BMS temperature requests (cyclic writing)
- **Error Management**: Error detection, error acknowledgment, diagnostics export
- **Optional Web Supplement**: Navigator generation, software version, heat pump model, compact myIDM ID, web-only diagnostics, and Navigator 10 infosystem notifications without replacing Modbus values; default interval 30 seconds
- **KNX Bridge** *(optional)*: Serves the IDM KNX communication objects — same object numbers, datapoint types and directions as IDM's ETS example project — through the Home Assistant KNX integration, so the Weinzierl KNX IP BAOS gateway module is no longer needed. See [KNX Bridge](KNX-Bridge).
- **Room Temperature Forwarding**: Optional forwarding of Home Assistant temperature sensors to IDM external room temperature registers per heating circuit
- **Readable Diagnostics**: Internal IDM messages are shown with text plus structured code/text attributes
- **Direct local Modbus runtime**: `modbus-connection` and tmodbus own the per-entry socket; `idm-heatpump-api` keeps the IDM register and safety logic

---

## Platforms & Entities

| Platform | Entities | Description |
|----------|----------|-------------|
| **Sensor** | model-dependent | Temperatures, pressures, flow rates, energy, PV, solar, cascade, booster, runtime versions |
| **Binary Sensor** | model-dependent | Fault alarms, compressor status, heating/cooling/DHW demand, web states |
| **Number** | model-dependent | Writable setpoints, limits, GLT parameters, power limits |
| **Select** | model-dependent | System mode, circuit modes, solar/ISC mode |
| **Switch** | model-dependent | External heating/cooling/DHW demand |
| **Climate** | per circuit + zone room | Heating/cooling mode + target temperature for heating circuits and zone-module rooms |
| **Water Heater** | 1 | DHW target temperature with current temperature readback |
| **Button** | 1 | Acknowledge active errors on the heat pump |

---

## Quick Navigation

### I'm new here
1. [Installation & Setup](Installation-and-Setup)
2. [Configuration](Configuration)
3. [Entities](Entities)

### I want to automate
1. [iDM Smart Energy & Comfort](Smart-Energy-and-Comfort)
2. [Configuration and source mappings](Configuration)
3. [Services Reference](Services)

### I have a problem
1. [Troubleshooting](Troubleshooting)
2. [Local Navigator Web Interface](Local-Web-Interface)
3. [Modbus Registers](Modbus-Register)
4. [Stability & Release Readiness](Stability-and-Release-Readiness)

### I want to contribute
- [Contributing Guide](Contributing)

---

## Technical Details

- **Batch reading**: Only exactly adjacent, non-overlapping ranges are grouped, up to 40 Modbus words per request
- **Value validation**: Unavailable sentinels are omitted as unused; suspicious grouped values are checked individually and quarantined for the client session
- **Library-powered**: All registers from [`idm-heatpump`](https://github.com/Xerolux/idm-heatpump-api)
- **Actionable setup diagnostics**: Separate messages for hostname/DNS errors, refused or disabled Modbus TCP, timeouts, unreachable endpoints, wrong slave IDs, invalid web PINs, and unavailable web interfaces
- **Runtime version visibility**: Integration, `idm-heatpump-api`, `modbus-connection` and `tmodbus` versions are available in a diagnostic sensor, diagnostics exports, and startup logs
- **Data types**: FLOAT, UCHAR, INT8, INT16, UINT16, BOOL, BITFLAG
- **EEPROM protection**: Sensitive registers tracked and protected
- **Transport boundary**: Raw FC03/FC04 reads and FC16 writes use the exact `modbus-connection==4.12.2` / `tmodbus[async-serial]==0.6.2` pair; `4.12.2` is the connection-library version, not the IDM integration version
- **API boundary**: `idm-heatpump-api[web]==2.4.3` provides batching, decoding and write safety. The API owns its own exception hierarchy; the integration uses the tmodbus-backed socket without a pymodbus dependency
- **Auto-recovery**: API retry/backoff plus reconnect-on-demand in the tmodbus-backed connection
- **Connection ownership**: Each config entry owns one socket and reports `supports_shared_connection: false`; Home Assistant central cross-entry sharing is not currently available
- **Validation status**: Automated checks and read-only Navigator 10 observations are available; they do not replace candidate-specific clean-install, long-duration and broader model validation. See [Stability & Release Readiness](Stability-and-Release-Readiness).
- **Navigator 10**: Heat sink sensors, flow rate (Sieb monitoring), groundwater temps, booster A/B
- **Web supplement**: Setup tests both supported local protocols when needed, stores the successful Navigator family, reuses its session and retries only that same protocol during normal runtime recovery
- **Room forwarding**: Optional write path with state-change updates, periodic refresh, tolerance and range checks

---

## Links & Resources

| Resource | Link |
|----------|------|
| GitHub Repository | https://github.com/Xerolux/idm-heatpump-hass |
| Community, Questions & Ideas | https://github.com/Xerolux/idm-heatpump-hass/discussions |
| Issues & Bugs | https://github.com/Xerolux/idm-heatpump-hass/issues |
| HACS | https://hacs.xyz/ |
| Home Assistant | https://www.home-assistant.io/ |
| IDM EnergieSysteme | https://www.idm-energiesysteme.de/ |

---

*This wiki documents the IDM Heatpump integration.*
*Developed by [Xerolux](https://github.com/Xerolux)*

## Experimental AI adviser (upcoming)

The experimental adviser provides daily/weekly reports and explanations of health and efficiency. It is off by default and has no plant control tools or voice exposure. Ollama is local; v0.17.2-b10 adds separately consented OpenAI and Z.ai reports with bounded requests. See [setup, report actions, data coverage and limitations](Experimental-AI-Adviser).
