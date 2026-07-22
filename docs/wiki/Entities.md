# Entities

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

---

## Sensors

### Runtime diagnostics

| Entity | State | Attributes | Category |
|--------|-------|------------|----------|
| IDM Heatpump API version | Installed `idm-heatpump-api` version | `integration_version`, `pymodbus_version` | Diagnostic |

This sensor remains available even if heat-pump polling fails, making it useful
when collecting information for a bug report.

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

### Solar Thermal

| Entity | Register | Unit |
|--------|----------|------|
| Solar collector temperature | 1850 | °C |
| Solar return temperature | 1852 | °C |
| Solar charging temperature | 1854 | °C |
| Solar WQ reference / pool temp | 1857 | °C |

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

### Optional Web Supplement Sensors

When **Web supplement data** is enabled and a local Navigator web PIN is
configured, the integration adds read-only diagnostic sensors from the local web
API. These sensors are additive; Modbus entities remain the primary data source.

Typical web-only sensors include:

| Entity | Description |
|--------|-------------|
| Navigator version (Web) | Detected Navigator generation, for example Navigator 2.0 or Navigator 10 |
| Software Version (Web) | Controller software version reported by the local web interface |
| Wärmepumpenmodell (Web) | Heat pump model/type reported by the web interface |
| myIDM ID (Web) | Compact myIDM ID derived from the local web account value before `@` |
| Infosystem Meldungen Anzahl (Web) | Number of active Navigator 10 infosystem notifications |
| Infosystem Meldungen (Web) | Summary of active Navigator 10 infosystem notifications |
| Heißgastemperatur (Web) | Web-only diagnostic temperature when available |
| Verdampfer Druck (Web) | Web-only refrigerant pressure when available |
| Platinentemperatur (Web) | Controller board temperature when available |

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
| `hc_{x}_heating_curve` | 1429+ | 0.1–3.5 |
| `hc_{x}_heating_limit` | 1442+ | 0–50 °C |
| `hc_{x}_cooling_limit` | 1484+ | 0–36 °C |
| `hc_{x}_parallel_shift` | 1505+ | 0–30 |
| `hc_{x}_ext_room_temp` | 1650+ | 15–30 °C |

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
temperature control with current temperature readback. Created when both
`dhw_temp_top` and `dhw_setpoint` registers exist.

| Property | Register | Notes |
|----------|----------|-------|
| Current temperature | `dhw_temp_top` | Top DHW tank temperature |
| Target temperature | `dhw_setpoint` | Writable setpoint (35–95 °C typical) |
| Operation mode | N/A | Always "Heat Pump" |

Uses the same coordinator write path as climate entities.

---

## Button

A single button (`button.idm_heatpump_acknowledge_errors`) acknowledges active
errors on the heat pump by writing `1` to the `error_acknowledge` write-only
register. Always available so automations can trigger on alarm state changes.

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
