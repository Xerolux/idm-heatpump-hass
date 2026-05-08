# Entities

## Sensors

The integration creates over 100 sensor entities for various measurements.

### System Sensors

| Entity | Description | Address |
|--------|-------------|---------|
| `sensor.{name}_outdoor_temp` | Outdoor temperature | 1000 |
| `sensor.{name}_flow_temp` | Flow temperature | 1001 |
| `sensor.{name}_return_temp` | Return temperature | 1002 |
| `sensor.{name}_dhw_temp` | DHW temperature | 1003 |
| `sensor.{name}_dhw_setpoint` | DHW setpoint | 1004 |
| `sensor.{name}_system_mode` | System operating mode | 1005 |
| `sensor.{name}_system_state` | System state | 1006 |
| `sensor.{name}_heat_request` | Heat request | 1008 |
| `sensor.{name}_flow_rate` | Flow rate | 1010 |
| `sensor.{name}_system_pressure` | System pressure | 1011 |
| `sensor.{name}_compressor_runtime` | Compressor runtime | 1012 |
| `sensor.{name}_heat_quantity` | Heat quantity | 1013 |

### Heating Circuit Sensors

For each enabled heating circuit (A–G):

| Entity | Description |
|--------|-------------|
| `sensor.{name}_circuit_{x}_flow_temp` | Circuit flow temperature |
| `sensor.{name}_circuit_{x}_return_temp` | Circuit return temperature |
| `sensor.{name}_circuit_{x}_setpoint` | Circuit setpoint |
| `sensor.{name}_circuit_{x}_mode` | Circuit mode |
| `sensor.{name}_circuit_{x}_state` | Circuit state |
| `sensor.{name}_circuit_{x}_curve` | Heating curve |
| `sensor.{name}_circuit_{x}_room_temp` | Room temperature |
| `sensor.{name}_circuit_{x}_mixer_pos` | Mixer position |

### Zone Sensors

For each enabled zone and room:

| Entity | Description |
|--------|-------------|
| `sensor.{name}_zone_{z}_room_{r}_temp` | Room temperature |
| `sensor.{name}_zone_{z}_room_{r}_humidity` | Room humidity |
| `sensor.{name}_zone_{z}_room_{r}_mode` | Room mode |
| `sensor.{name}_zone_{z}_mode` | Zone mode |

### Energy & Solar

| Entity | Description |
|--------|-------------|
| `sensor.{name}_energy_heating` | Energy heating |
| `sensor.{name}_energy_dhw` | Energy DHW |
| `sensor.{name}_energy_total` | Energy total |
| `sensor.{name}_solar_temp_in` | Solar temperature flow |
| `sensor.{name}_solar_temp_out` | Solar temperature return |
| `sensor.{name}_pv_power` | PV power |
| `sensor.{name}_battery_soc` | Battery state of charge |

### Technician Level Sensors

Only available when the **Show Technician Level Codes** option is enabled in the config flow:

| Entity | Description |
|--------|-------------|
| `sensor.{name}_fachmann_ebene_1` | Current technician level 1 code (`DDMM`) |
| `sensor.{name}_fachmann_ebene_2` | Current technician level 2 code (time-based) |

### Error Sensors

| Entity | Description |
|--------|-------------|
| `sensor.{name}_error_1` | Error code 1 |
| `sensor.{name}_error_2` | Error code 2 |
| `sensor.{name}_error_3` | Error code 3 |

## Numbers

Writable parameters via Number entities:

### System Numbers

| Entity | Description | Range |
|--------|-------------|-------|
| `number.{name}_dhw_setpoint` | DHW setpoint | 10-60 °C |
| `number.{name}_heating_limit` | Heating limit | -20-30 °C |

### Heating Circuit Numbers

| Entity | Description |
|--------|-------------|
| `number.{name}_circuit_{x}_setpoint` | Circuit setpoint |
| `number.{name}_circuit_{x}_room_setpoint` | Room setpoint |
| `number.{name}_circuit_{x}_curve_offset` | Heating curve offset |

## Selects

Selection fields for operating modes:

| Entity | Description | Options |
|--------|-------------|---------|
| `select.{name}_system_mode` | System operating mode | Standby, Auto, Away, Holiday, DHW Only, Heating Only |
| `select.{name}_circuit_{x}_mode` | Circuit mode | Auto, Continuous, Off, Schedule |
| `select.{name}_zone_{z}_room_{r}_mode` | Room mode | Comfort, Normal, Eco, Frost Protection |
| `select.{name}_solar_mode` | Solar mode | Auto, Continuous, Off |

## Switches

| Entity | Description |
|--------|-------------|
| `switch.{name}_glt_heat_request` | BMS heat request |
| `switch.{name}_glt_cool_request` | BMS cooling request |

## Binary Sensors

| Entity | Description |
|--------|-------------|
| `binary_sensor.{name}_error_active` | Error active |
| `binary_sensor.{name}_heating_active` | Heating active |
| `binary_sensor.{name}_dhw_active` | DHW active |
| `binary_sensor.{name}_compressor_running` | Compressor running |
