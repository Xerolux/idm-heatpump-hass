# Entities

## Smart feature entities

The optional [Smart Energy & Comfort](Smart-Energy-and-Comfort) profile adds
electrical and thermal energy totals for lifetime, day and month, COP for the
same periods, estimated costs, CO₂ and optional PV use, plus compressor-cycle
and operating analysis. These are derived values, not additional physical
meters. The required power registers must be available.

Health Monitor adds eight problem checks and a report sensor. Heating-curve
and weather advisers add read-only recommendations. The optional comfort
schedule changes the existing circuit room target; it does not create a
second climate controller entity. Automatic DHW charging uses the existing
boost controls and state machine.

With device hierarchy enabled, **iDM Analytics**, **iDM Health Monitor**,
**iDM Comfort** and **Diagnostics** separate these features from controller
entities. Disabling optional features removes their entity registrations;
re-enabling them restores the same IDs. Existing controller IDs are retained.

The integration dynamically generates entities based on your heat pump configuration (heating circuits, zones, optional features).

## Entity Platforms

| Platform | Count | Description |
|----------|-------|-------------|
| **Sensor** | model-dependent | Temperatures, pressures, flow rates, energy, PV, solar, cascade, booster, runtime versions, diagnostics |
| **Binary Sensor** | model-dependent | Fault alarms, compressor status, heating/cooling/DHW demand, web states |
| **Number** | model-dependent | Writable setpoints, temperature limits, GLT parameters, power limits |
| **Select** | model-dependent | System mode, heating circuit modes, solar mode, ISC mode |
| **Switch** | model-dependent | External heating/cooling/DHW demand, one-time DHW charge |
| **Climate** | per circuit + zone room | Heating/cooling mode + target temperature for heating circuits and zone-module rooms |
| **Water Heater** | 1 | DHW target temperature with current temperature readback |
| **Button** | 1 | Acknowledge active errors on the heat pump |

Exact counts depend on the detected model, active heating circuits, zones,
rooms and optional features. Adding circuits, zones, cascade, technician codes
or web supplement data can add entities.

Entities are grouped by function in Home Assistant where possible. The optional
technician code sensors are pinned at the top, followed by configuration
entities, switches, writable values, live measurements and diagnostics.

## Entity names and languages

Entity names come from the integration's translation files and follow the
language configured in Home Assistant: an English installation shows English
names, a German one shows the German names the integration has always used.
Heating circuits and zone rooms share one name per measurement and fill in their
circuit letter or zone/room number, for example *Heating circuit A flow
temperature* and *Zone 1 room 2 temperature*.

Changing the Home Assistant language changes the displayed names only. Entity
IDs and unique IDs stay exactly as they are, so dashboards, automations and
long-term statistics keep working. An entity created *after* a language change
derives its entity ID from the name in that language, as with every Home
Assistant integration.

---

## Sensors

### Runtime diagnostics

| Entity | State | Attributes | Category |
|--------|-------|------------|----------|
| IDM Heatpump API version | Installed `idm-heatpump-api` version | `integration_version`, `modbus_connection_version`, `tmodbus_version`, `home_assistant_version`, `python_version` | Diagnostic |

This sensor remains available even if heat-pump polling fails, making it useful
when collecting information for a bug report. The direct socket runtime is
identified by the `modbus_connection_version` and `tmodbus_version` attributes.

### Technician-level access codes

When enabled in the integration options, two additional sensors expose the
current access codes for *Fachmann Ebene 1* and *Fachmann Ebene 2*. They update
once per minute, are placed at the top of the IDM device entity list and are not
Modbus registers.

The option is disabled by default. Treat the values as sensitive: limit access
to their dashboard cards and never publish them in screenshots, logs or support
requests. See [Configuration](Configuration#technician-level-codes) for setup
and security guidance. The calculation method is deliberately not documented.

### System Temperatures & Pressures

| Entity | Register | Unit |
|--------|----------|------|
| Outdoor temperature | 1000 | °C |
| Average outdoor temperature | 1002 | °C |
| Storage tank temperature | 1008 | °C |
| Cold storage temperature | 1010 | °C |
| DHW temperature bottom | 1012 | °C |
| DHW temperature top | 1014 | °C |
| HP flow temperature | 1050 | °C |
| HP return temperature | 1052 | °C |
| HGL flow temperature | 1054 | °C |
| Heat source inlet/outlet | 1056/1058 | °C |
| Air intake temperatures | 1060/1064 | °C |
| Air heat exchanger temp | 1062 | °C |

### Navigator 10 — Heat Sink (Trennwärmetauscher)

| Entity | Register | Unit |
|--------|----------|------|
| Heat sink return temp (B124) | 1068 | °C |
| Heat sink flow temp (B125) | 1070 | °C |
| Heat sink flow rate (B2) | 1072 | l/min |
| Heat sink charging pump signal (M73) | 1074 | % |

### Compressors & Pumps

| Entity | Register |
|--------|----------|
| Compressor status 1–4 | 1100–1103 |
| Charging pump status (M73) | 1104 |
| Brine pump status (M16) | 1105 |
| Heat source pump status (M15) | 1106 |
| ISC cold storage pump (M84) | 1108 |
| ISC recooling pump (M17) | 1109 |
| Circulation pump (M64) | 1118 |

### Energy & Power

| Entity | Register | Unit |
|--------|----------|------|
| Energy heating | 1748 | kWh |
| Energy total | 1750 | kWh |
| Energy cooling | 1752 | kWh |
| Energy DHW | 1754 | kWh |
| Energy defrost | 1756 | kWh |
| Energy passive cooling | 1758 | kWh |
| Energy solar | 1760 | kWh |
| Energy electric heater | 1762 | kWh |
| Current power draw | 1790 | kW |
| Current power solar | 1792 | kW |
| Power consumption HP | 4122 | kW |
| Thermal power | 4126 | kW |

### PV / Energy Management

| Entity | Register | Datatype | Unit |
|--------|----------|----------|------|
| PV surplus | 74 | FLOAT, word-swapped | kW |
| Electric heater power | 76 | FLOAT, word-swapped | kW |
| PV production | 78 | FLOAT, word-swapped | kW |
| House consumption | 82 | FLOAT, word-swapped | kW |
| Battery discharge | 84 | FLOAT, word-swapped | kW |
| Battery SOC | 86 | signed INT16, one register | % |

Battery SOC accepts `0–100`; `-1` means that no battery value is available.
Treating address 86 like the surrounding two-register FLOAT values produces an
implausible result.

#### PV surplus operation (derived diagnostic)

The Navigator controllers do not expose an internal "PV surplus charging
active" state register — the whole PV block (74–88) consists of GLT
measurement inputs written by an external energy manager. The integration
therefore provides the derived diagnostic binary sensor **PV-Überschussbetrieb**
(`calculated_pv_surplus_operation`, issue #353). It is `on` when both halves of
the state are true:

1. Surplus is currently signalled to the controller: `pv_surplus` (register
   74) ≥ 0.05 kW **or** the SG-Ready signal `smart_grid_status` (register 90)
   reports *Supergreen*.
2. The heat pump is actually drawing electrical power:
   `power_consumption_hp` (register 4122) ≥ 0.05 kW, falling back to
   `hp_operating_mode` (register 1090) ≠ *Off* on installations without the
   Nav 10 power measurement.

The entity is only created when at least one source per half exists on the
detected installation; thresholds and the currently active sources are exposed
as attributes. Note for installations where the surplus is measured behind the
heat pump feeder: `pv_surplus` collapses toward zero while the heat pump absorbs
the surplus it is charged with — there the SG-Ready signal (or `pv_production`)
remains the reliable indicator, and the SG-Ready source keeps the diagnostic
meaningful.

### Solar Thermal

| Entity | Register | Unit |
|--------|----------|------|
| Solar collector temperature | 1850 | °C |
| Solar return temperature | 1852 | °C |
| Solar charging temperature | 1854 | °C |
| Solar WQ reference / pool temp | 1857 | °C |

These entities only exist while the **solar thermal system** option is enabled
(default). Plants without collectors can switch the option off in the
integration settings: the solar registers leave the poll and the empty
*Solaranlage* device group disappears after a reload. Re-enabling it restores
the entities with their previous IDs.

The integration also notices on its own: when every solar register reports
"not configured" for a full day, a repair suggestion offers to switch the
module off (or keep it, which dismisses that round of the suggestion).

### ISC (Intelligent Surface Cooling)

| Entity | Register | Unit |
|--------|----------|------|
| ISC charging temp cooling | 1870 | °C |
| ISC recooling temperature | 1872 | °C |

### Booster A/B (2nd heat generator)

| Entity | Register |
|--------|----------|
| Booster fault | 4001 |
| Booster interlock | 4002 |
| Booster A: source inlet/outlet, storage, flow, return temps | 4010–4018 |
| Booster A: source pump, charging pump, compressor | 4020–4022 |
| Booster B: equivalent registers | 4040–4052 |

### Cascade (multi-heat pump)

| Entity | Register |
|--------|----------|
| Cascade available heating/cooling/DHW | 1147–1149 |
| Cascade running heating/cooling/DHW | 1150–1152 |
| Cascade requested temps (heat/cool/DHW) | 1200–1204 |
| Cascade average flow temps | 1206–1210 |
| Cascade min/max power | 1220–1225 |
| Cascade bivalence settings | 1226–1231 |

### Heating Circuit Sensors (per circuit A–G)

| Entity | Description |
|--------|-------------|
| `hc_{x}_flow_temp` | Flow temperature |
| `hc_{x}_room_temp` | Room temperature |
| `hc_{x}_setpoint_flow_temp` | Current setpoint flow temp |
| `hc_{x}_active_mode` | Active operating mode |

### Calculated Sensors

These sensors are derived from register values of the same snapshot. Nothing is
estimated: every operand is a decoded register value, and the sensor reports no
value rather than a guess when its sources are not meaningful.

| Entity | Description |
|--------|-------------|
| `calculated_hp_temperature_delta` | Heat pump spread (flow minus return) |
| `calculated_heat_source_temperature_delta` | Heat source spread (inlet minus outlet) |
| `calculated_dhw_setpoint_deviation` | DHW actual minus setpoint |
| `calculated_cop` | Momentary COP (thermal power / electrical power) |
| `calculated_hc_{x}_flow_deviation` | Flow deviation per heating circuit |

**Flow deviation per heating circuit** compares the measured flow temperature of
a circuit (`hc_{x}_flow_temp`) with the flow setpoint the controller currently
requests for that circuit (`hc_{x}_setpoint_flow_temp`):

- **Positive** — the circuit runs above the requested setpoint (overshoot,
  typically a heating curve set too high or a mixer that opens too far).
- **Around zero** — the circuit follows its heating curve.
- **Negative** — the circuit does not reach its setpoint (undersized heat
  source, high load, defrost, or a limiting setting).

The sensor becomes **unavailable** while the circuit is idle (the controller
reports `0.0`) and on circuits that are not configured (`-1.0`). That is
intentional: a deviation calculated from a placeholder value would be
meaningless. The entity itself is created as soon as both registers exist, so a
Home Assistant restart during standby does not make it disappear.

> This deliberately compares values **within one heating circuit**. A deviation
> at heat-pump level needs an unambiguous register for the flow setpoint the
> heat pump itself requests and remains an open roadmap item.

### Optional Web Supplement Sensors

When **Web supplement data** is enabled and a local Navigator web PIN is
configured, the integration adds read-only diagnostic sensors from the local web
API. These sensors are additive; Modbus entities remain the primary data source.

Typical web-only sensors include:

| Entity | Description |
|--------|-------------|
| Navigator version (Web) | Detected Navigator generation, for example Navigator 2.0 or Navigator 10; carries the heat pump model as an attribute where the firmware reports it |
| Software version (Web) | Controller software version reported by the local web interface |
| myIDM ID (Web) | Compact myIDM ID derived from the local web account value before `@` |
| Info system notification count (Web) | Number of active Navigator 10 infosystem notifications |
| Anforderungsgrund (Web) | Navigator 10 only: the controller's own demand reason (issue #353) |

The heat pump model is deliberately no entity of its own: Navigator 10
firmware 20.24-1580 (installed from 2026-09-29) removed the model row from
the sensor page, and no other accessible web frame reports it — live-verified
against the controller, an entity would sit unavailable forever on current
firmware. Where a firmware still delivers the row (Navigator 2.0 web, older
Navigator 10 firmware) the value appears as the `heatpump_model` attribute of
the *Navigator version (Web)* sensor.

#### Demand reason from the web interface (Navigator 10 only)

The Navigator controllers expose no internal PV-mode state register over
Modbus, but the Navigator 10 web interface renders the display's
"Anforderungsgrund" — including **PV** — from a bitmask in the WebSocket
`home/detail` frame. With the web supplement active on a Navigator 10, the
integration evaluates that frame every web poll and exposes:

- **Anforderungsgrund (Web)** (`web_demand_reason`): the human-readable demand
  reason, worded like the controller's own display — for example *PV*,
  *Heizkreis A*, *Zeitprogramm*, *Mehrere Anforderungen*, *Keine Anforderung*
  or *Aus* — with the raw `operationMode`/`info` values of every contributing
  widget as attributes.
- **PV-Anforderungsgrund (Web)** (`web_demand_reason_pv`): binary sensor that
  is `on` while the controller itself reports PV as its demand reason (bit 32),
  in the heating as well as the domestic-hot-water reason table.

This is the device-reported counterpart of the derived
[`calculated_pv_surplus_operation`](#pv-surplus-operation-derived-diagnostic)
diagnostic: the web entity reflects what the controller decided, the Modbus
entity works without a web PIN. On Navigator 2.0 (different, PHP-based web
interface) only the derived Modbus entity is available.

With the **device hierarchy** enabled, all PV entities — the PV registers
(`pv_surplus`, `pv_production`, `pv_target_value`), `smart_grid_status`, the
derived diagnostic and the two web entities — share the dedicated
**Photovoltaik** subdevice instead of the main device.
| Info system notifications (Web) | Summary of active Navigator 10 infosystem notifications |
| Hot gas temperature (Web) | Web-only diagnostic temperature when available |
| Evaporator pressure (Web) | Web-only refrigerant pressure when available |
| Board temperature (Web) | Controller board temperature when available |
| Current/projected heating / cooling / hot water power (Web) | The controller's current **or projected** thermal power for that mode |

#### "Momentane/prognostizierte Leistung" is not a live measurement

The Navigator labels these three values `mom./prog. Leistung Heizen`,
`mom./prog. Leistung Kühlen` and `mom./prog. Leistung Vorrang` — *momentane bzw.
prognostizierte* power. They report what the controller currently expects to
deliver for that mode, so a non-zero value while heating or cooling is switched
off is normal and not a fault. A value that changes while the compressor is
idle is the controller re-planning, not the heat pump running.

For actual electrical draw, use **Wärmepumpe Aufnahmeleistung** /
`current_electrical_power` instead.

#### Device-side heat quantities, DHW detail and controller clock (Navigator 10 only)

Three further read-only WebSocket controllers are evaluated on every web poll
(live-verified on firmware jsonVersion 11, September 2026):

- **Heat quantity heating/hot water, total and today (Web)**
  (`web_heat_quantity_heating_total`, `web_heat_quantity_hotwater_total`,
  `web_heat_quantity_heating_today`, `web_heat_quantity_hotwater_today`): the
  controller's own `statistic/detail` heat-quantity block — the lifetime
  totals and today's values in kWh. They are an independent cross-check for
  the integration's own [energy statistics](Smart-Energy-and-Comfort) and work
  without any Modbus access.
- **Hot water circulation (Web)** (`web_dhw_circulation_active`): binary
  sensor for the domestic-hot-water circulation pump from the
  `system.freshwater/overview` frame — a state the Modbus map does not expose.
- **Hot water status info (Web)** (`web_dhw_status_info`): the numeric status
  of the freshwater block, diagnostic category.
- **Controller clock (Web)** (`web_controller_clock`): the controller's own
  clock as a timestamp sensor, with `jsonVersion`, active user level,
  language, notification count, frost-protection flag and network flag as
  attributes. The controller clock can drift, and the time-dependent
  technician codes are computed from the time shown on the display — this
  sensor makes the drift visible.

#### Connection state

Two diagnostic entities make the effective connection visible on the
dashboard — they exist in every connection mode, so a fallback is visible
at a glance:

- **Connection mode** (`connection_mode`): which transports are actually
  live right now — *Modbus + Web*, *Modbus only* or *Web only*. The web
  half reflects the last web refresh (a supplement that stopped answering
  flips the state to *Modbus only* and back on recovery). The attributes
  carry the configured mode (the `connection_mode` option from
  *Configure* → Modbus section, default *auto*) and the detected web
  variant (`nav10` or `nav20`). Every transport transition is written to
  the log at INFO level (`IDM connection state changed: …`), so support
  cases can answer "since when does the web path not answer" without
  log spam.
- **Letzte Web-Aktualisierung (Web)** (`web_last_success`): when the local
  web interface last answered successfully — the web counterpart of the
  Modbus *last success* diagnostic, always available when a web PIN is
  configured.

#### System controllers (Navigator 10)

Four read-only WebSocket controllers that the shipped frontend uses for its
performance page, weather tile, iON status and energy-flow widget are part of
the web supplement (`idm-heatpump-api` 2.12.0 or newer). They are additive —
the frames are read with the regular web poll, and every entity reports
unavailable until its frame has landed:

- **Heat pump power consumption (Web)** (`web_hp_power_consumption`): the
  live electrical consumption power in kW, with the performance mode, the
  system mode, the measurement source, the battery flag and the production
  flow temperature as attributes.
- **Heat pump environment power (Web)** (`web_hp_power_environment`): the
  source-side power in kW, with the environment source and the source inlet
  temperature as attributes.
- **Heating rod (Web)** (`web_hp_heating_rod`): binary sensor for the
  heating-rod state of the performance page.
- **Grid power (Web)** (`web_energyflow_grid`) and **PV power (Web)**
  (`web_energyflow_pv`): the energy-flow widget's grid and PV power in kW —
  placed on the PV subdevice when the device hierarchy is enabled. Firmware
  `T_NAV10_20.24-1580` removed the `house` channel from the frame; when an
  older firmware still delivers it, it is exposed as an attribute.
- **Weather forecast (Web)** (`web_weather_forecast`): the controller's own
  forecast, which it pulls through the myiDM service — today's temperature as
  the state, and today plus up to six forecast days (min/max/actual
  temperature, cloud cover, rain probability, sunshine seconds, weather
  symbol, wind speed) as attributes.
- **iON optimization active (Web)** (`web_ion_active`): diagnostic binary
  sensor for IDM's cloud energy optimization, with the enable setting and the
  subscription status as attributes.

#### Web-only controls (Navigator 10, Phase 4)

A **web-only** entry is no longer purely read-only: with the WebSocket
variant connected it gains two controls that write through the local web
interface — every other connection mode keeps writing through Modbus exactly
as before:

- **Betriebsart (Web)** (`web_system_mode`): select for the operating mode.
  It reads the current mode and the controller's own selectable values from
  the `home/overview` tile and writes through `home/save` — the same
  numbering as the Modbus `system_mode` register, validated before sending.
  A rejected write raises instead of silently failing.
- **Fehler quittieren (Web)** (`web_acknowledge_errors`): the acknowledge
  button, writing `notification/save`.
- **Warmwasser-Solltemperatur (Web)** (`web_dhw_setpoint`): the hot-water
  setpoint as a number entity. Bounds, step and the current value come from
  the device's own declared parameter definition, and every write is
  validated against that range before sending — the same write safety as the
  register path.
- **Heizkreis X (Web)** climate card per circuit (room temperature, target
  temperature, mode; `HVACAction` from the pump state) and the
  **Warmwasser (Web)** water-heater card (tank top temperature + setpoint)
  — the same validated web writes, presented as the standard Home
  Assistant cards.
- **Heizkreis X Raumsolltemperatur (Web)** / **Heizkreis X Betriebsart
  (Web)** (per configured circuit): the normal room setpoint (parameter
  `HK<x>04`) as a number and the circuit mode (parameter `HK<x>01`) as a
  select, with the device's own declared bounds/options. One
  `system.heatingcircuit/detail` frame per circuit also carries the room
  temperature and pump state. The DHW one-shot boost deliberately stays off
  the web path: this firmware exposes it only as a weekly timetable, and
  writing whole timetable strings is out of scope.

The `set_system_mode` and `acknowledge_errors` services use the same web
path automatically for web-only entries. Writes reuse the authorized web
session of the poll loop and read the state back after every write, like the
official web UI. KNX bus commands route through the same web writes for the everyday
controls (system mode, hot-water setpoint, circuit mode/setpoint,
acknowledge); other registers still require Modbus.

On Navigator 2.0, the statistics pages deliver the same shape from the older
web interface: **runtime / heat quantity / electrical energy, total per
category (Web 2.0)** sensors — hours for runtime, kWh for the energy types,
normalized with the page's own unit scale.

If a firmware does not answer one of these controllers, the affected entities
simply stay unavailable; the rest of the web snapshot is unaffected.

If a web value duplicates an existing Modbus entity, the web entity is skipped.
This prevents duplicate dashboard values and keeps Modbus as the authoritative
source for register-backed data.

Only values returned by the current local web snapshot are available. Optional
Navigator 10 infosystem notifications are read independently; if that optional
request fails, the other valid web values remain available. See [Local
Navigator Web Interface](Local-Web-Interface) for protocol and web-only-mode
details.

### Internal Message Sensor

The `internal_message` diagnostic sensor exposes the active IDM internal
message as readable text, for example a code plus message description. It also
provides the structured attributes `message_code` and `message_text` so
automations can react either to the numeric code or to the human-readable
description.

---

## Binary Sensors

| Entity | Register | Description |
|--------|----------|-------------|
| `hp_sum_alarm` | 1099 | Sum alarm (total fault) |
| `compressor_status_1` | 1100 | Compressor 1 running |
| `compressor_status_2` | 1101 | Compressor 2 running |
| `compressor_status_3` | 1102 | Compressor 3 running |
| `compressor_status_4` | 1103 | Compressor 4 running |
| `heating_demand` | 1091 | Heating demand active |
| `cooling_demand` | 1092 | Cooling demand active |
| `dhw_demand` | 1093 | DHW demand active |
| `calculated_pv_surplus_operation` | derived | Heat pump running on signalled PV surplus (see PV / Energy Management) |

### Navigator 1.0/1.7 — momentary coils (c3000/c3003)

The 1.x coil block (ma_de_812049 Rev.1) consists of momentary command bits,
not status signals: the controller executes a request the moment the bit is
set and the bit immediately falls back to 0 (verified on real 1.7 hardware,
issue #319). The coils therefore carry no state entities:

- **c3003 — Anforderung Vorrangladung** backs the **Request DHW priority
  charge** button (see [Button](#button)): a single-coil write of ON
  (function code 05), the 1.x hot-water boost. No switch exists by design —
  a switch would also write OFF, which a momentary command bit must never
  receive.
- **c3000 — Störung quittieren** backs the **Acknowledge errors** button
  (see [Services](Services.md)), single-coil write (FC05) on the 1.x family
  and holding-register write on the shared Navigator 2.0/10 family.
- **c3001/c3002 — Anforderung Heizen/Kühlen** are not exposed: requesting
  heating or cooling is what the operating-mode selects are for.

---

## Numbers (Writable)

### DHW

| Entity | Register | Range |
|--------|----------|-------|
| `dhw_setpoint` | 1032 | 35–95 °C |
| `dhw_charge_on_temp` | 1033 | 30–50 °C |
| `dhw_charge_off_temp` | 1034 | 46–53 °C |

### Heating Circuit (per circuit)

| Entity | Register | Range |
|--------|----------|-------|
| `hc_{x}_room_setpoint_heat_normal` | 1401+ | 15–30 °C |
| `hc_{x}_room_setpoint_heat_eco` | 1415+ | 10–25 °C |
| `hc_{x}_room_setpoint_cool_normal` | 1457+ | 15–30 °C |
| `hc_{x}_room_setpoint_cool_eco` | 1471+ | 15–30 °C |
| `hc_{x}_heating_curve` | 1429+ | 0.1–3.5 (step 0.1, expert) |
| `hc_{x}_heating_limit` | 1442+ | 0–50 °C |
| `hc_{x}_cooling_limit` | 1484+ | 0–36 °C |
| `hc_{x}_parallel_shift` | 1505+ | 0–30 (expert) |
| `hc_{x}_ext_room_temp` | 1650+ | 15–30 °C |

Entries marked *expert* shape the heating curve of the whole installation and
write to EEPROM registers. They are created disabled on new installations —
enable them under Settings -> Devices & Services -> IDM Heatpump -> Entities.
Existing installations keep whatever state the entity already had.
`hc_{x}_setpoint_flow_constant` and `hc_{x}_setpoint_flow_cooling` are expert
entities for the same reason.

`hc_{x}_ext_room_temp` can be controlled manually like any other number entity
or filled automatically by optional room temperature forwarding. When
forwarding is enabled, selected Home Assistant temperature sensors are written
to these external room temperature registers on state changes and periodically
with a 300 second default interval.

### GLT / External Control

| Entity | Register |
|--------|----------|
| `ext_outdoor_temp` | 1690 |
| `ext_humidity` | 1692 |
| `ext_demand_temp_heating` | 1694 |
| `ext_demand_temp_cooling` | 1695 |
| `glt_temp_demand_heating` | 1696 |
| `glt_temp_demand_cooling` | 1698 |
| `glt_heat_storage_temp` | 1716 |
| `glt_cold_storage_temp` | 1718 |
| `glt_dhw_temp_bottom` | 1720 |
| `glt_dhw_temp_top` | 1722 |

### Power Limits

These registers are model-dependent and disabled by default. Do not use them for legal or contractual load control until the behavior is verified for your exact hardware and firmware.

| Entity | Register |
|--------|----------|
| `power_limit_hp` | 4108 |
| `power_limit_cascade` | 4112 |

---

## Selects

| Entity | Register | Options |
|--------|----------|---------|
| `system_mode` | 1005 | Standby, Automatic, Absent, Hot Water Only, Heating/Cooling Only |
| `hc_{x}_mode` | 1393+ | Off, Time Program, Normal, Eco, Manual Heat, Manual Cool |
| `solar_mode` | 1856 | Off, Automatic, Manual |
| `isc_mode` | 1874 | Off, Automatic, Manual |

---

## Switches

| Entity | Register | Description |
|--------|----------|-------------|
| `demand_heating` | 1710 | External heating demand |
| `demand_cooling` | 1711 | External cooling demand |
| `demand_dhw_charging` | 1712 | External DHW charge demand |
| `demand_onetime_dhw` | 1713 | One-time DHW charge |

---

## Climate

Climate entities combine a mode selector and a temperature target into the
standard Home Assistant thermostat card. Two types are created:

### Heating Circuit Climate (`climate.hc_x`)

One per configured heating circuit (A–G). Controls the circuit operating mode
and its normal (day) room setpoint temperature.

| Control | Register | Notes |
|---------|----------|-------|
| HVAC mode | `hc_{x}_mode` | Off, Time Program, Normal, Eco, Manual Heat, Manual Cool |
| Target temperature | `hc_{x}_room_setpoint_heat_normal` | Range depends on circuit config |
| Current temperature | `hc_{x}_room_temp` | Room temperature sensor |
| HVAC action | `hp_operating_mode` | Derives HEATING/COOLING/IDLE from heat pump status |

### Zone Room Climate (`climate.zm{z}_room{r}`)

One per configured room in each zone module. Controls the room operating mode
and its temperature setpoint.

| Control | Register | Notes |
|---------|----------|-------|
| HVAC mode | `zm{z}_room{r}_mode` | Off, Time Program, Normal, Eco, Manual Heat, Manual Cool |
| Target temperature | `zm{z}_room{r}_setpoint` | Range depends on zone config |
| Current temperature | `zm{z}_room{r}_temp` | Room temperature sensor |
| HVAC action | `hp_operating_mode` | Derives HEATING/COOLING/IDLE from heat pump status |

Writes go through the coordinator's centralized write path with optimistic
updates and translated error messages.

---

## Water Heater

A single water heater entity (`water_heater.idm_heatpump`) provides DHW target
temperature control with current temperature readback. Created when the target
register (`dhw_setpoint`) and a DHW tank temperature register exist — the
shared family reports `dhw_temp_top`, the Navigator 1.0/1.7 map offers
`dhw_temp` (tank temperature, address 1012) instead.

| Property | Register | Notes |
|----------|----------|-------|
| Current temperature | `dhw_temp_top` / `dhw_temp` | Shared family: top DHW tank temperature; Navigator 1.x: `dhw_temp` tank temperature |
| Target temperature | `dhw_setpoint` | Writable setpoint (shared family 35–95 °C typical; Navigator 1.x 35–60 °C, float pair 2152–2153) |
| Operation mode | N/A | Always "Heat Pump" |

Uses the same coordinator write path as climate entities.

---

## Button

A single button (`button.idm_heatpump_acknowledge_errors`) acknowledges active
errors on the heat pump by writing `1` to the `error_acknowledge` write-only
register. Always available so automations can trigger on alarm state changes.

On a detected Navigator 1.0/1.7 a second button
(`button.idm_heatpump_request_dhw_priority_charge`, *Vorrangladung anfordern*)
requests a DHW priority charge: a single FC05 write of ON to coil c3003.
Manual use only — the official table puts the coil block under the EEPROM
note, so it must not be driven by a schedule or a timed automation.

---

## Zone Modules

For each enabled zone module (up to 10), room-level entities are created:

| Entity per room | Description |
|-----------------|-------------|
| `zm{z}_room{r}_temp` | Room temperature |
| `zm{z}_room{r}_setpoint` | Room setpoint (writable) |
| `zm{z}_room{r}_humidity` | Room humidity |
| `zm{z}_room{r}_mode` | Room operating mode |
| `zm{z}_room{r}_relay` | Relay status (binary_sensor: on/off) |

Plus per-zone: `zm{z}_mode_heat_cool`, `zm{z}_dehumidification`
