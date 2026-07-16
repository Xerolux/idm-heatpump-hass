# Services Reference

There are several ways to write values to the heat pump in this integration:
1. **Via regular entities (recommended):**
   Many values (such as temperatures, setpoints, or modes) are represented as `number`, `select`, or `switch` entities in Home Assistant. You can change them directly in dashboards or use them in automations with standard services (e.g., `number.set_value` or `select.select_option`). A list of all adjustable entities can be found at [Entities](Entities).
2. **Via specific services:**
   For special actions like acknowledging errors or setting the system mode, there are dedicated services (e.g., `idm_heatpump.set_system_mode`).
3. **Direct Modbus access (advanced / alternative):**
   If an entity for a specific register is missing or you want to target registers directly, you can use the `idm_heatpump.write_register` service to write values directly to any Modbus register. An overview of registers can be found at [Modbus Registers](Modbus-Register). **Warning: Use at your own risk.**

### Where to find writable controls in Home Assistant

On the IDM device page, writable values appear as `number`, `select` and
`switch` entities rather than a separate actuator list. In an automation open
**Add action**, search for the entity or IDM, and choose the corresponding
entity action. IDM-specific actions such as error acknowledgement are listed in
the same action picker. Prefer these generated entities because they retain the
library datatype, value range, model availability and EEPROM/cyclic-write
metadata.

### Which values can be written?
With this integration you can essentially change the following values (see [Entities](Entities)):
- **Temperatures & setpoints** via `number` entities (e.g., DHW setpoint, circuit setpoint, heating limit).
- **Operating modes** via `select` entities (e.g., system operating mode, circuit mode, room mode).
- **BMS temperature requests** via `switch` entities (cyclic writing of BMS registers is handled automatically by the integration).

---

## set_system_mode

Sets the operating mode of the heat pump.

**Service:** `idm_heatpump.set_system_mode`

**Target:** Entity of the integration

| Field | Type | Description |
|-------|------|-------------|
| `mode` | select | System operating mode |

**Available modes:**
- `Standby`
- `Auto`
- `Away`
- `Holiday`
- `DHW Only`
- `Heating/Cooling Only`

**Example:**
```yaml
service: idm_heatpump.set_system_mode
target:
  entity_id: sensor.idm_navigator_system_mode
data:
  mode: "Holiday"
```

## acknowledge_errors

Acknowledges/clears active error messages on the heat pump.

**Service:** `idm_heatpump.acknowledge_errors`

**Target:** Device of the integration

**Example:**
```yaml
service: idm_heatpump.acknowledge_errors
target:
  device_id: abc123def456
```

## set_external_climate

Writes an external room temperature and optionally relative humidity to the IDM GLT/BMS registers without requiring raw Modbus addresses. The service uses the known register definitions from `idm-heatpump-api`, so model availability, datatype and write-safety checks stay active.

**Service:** `idm_heatpump.set_external_climate`

**Target:** Entity of the integration, or provide `entry_id` when multiple IDM entries are loaded

| Field | Type | Description |
|-------|------|-------------|
| `heating_circuit` | select | Heating circuit `A`–`G` for the external room temperature |
| `room_temperature` | number | External room temperature in °C (`-20`…`60`) |
| `humidity` | number | Optional external relative humidity in % (`0`…`100`) |

**Example:**
```yaml
action: idm_heatpump.set_external_climate
data:
  heating_circuit: A
  room_temperature: 23.1
  humidity: 58.4
```

**Cyclic automation example:**
```yaml
alias: Forward living room climate to IDM
trigger:
  - platform: time_pattern
    minutes: "/5"
  - platform: state
    entity_id:
      - sensor.living_room_temperature
      - sensor.living_room_humidity
action:
  - action: idm_heatpump.set_external_climate
    target:
      entity_id: sensor.idm_navigator_system_mode
    data:
      heating_circuit: A
      room_temperature: "{{ states('sensor.living_room_temperature') | float }}"
      humidity: "{{ states('sensor.living_room_humidity') | float }}"
```

## write_register

Writes a value directly to a Modbus register (advanced).

**Service:** `idm_heatpump.write_register`

**Target:** Device of the integration

| Field | Type | Description |
|-------|------|-------------|
| `address` | number | Modbus register address (0–10000) |
| `value` | text | Value to write |
| `datatype` | select | `uint16` (default), `int16`, `float`, `uchar` or `bool` |
| `acknowledge_risk` | constant | Must be set to `true` |

> **WARNING:** Direct register writing can damage your heat pump. Only use this service if you know exactly what you are doing. The integration validates numeric conversion and encoding, but a custom address has no known range, enum, EEPROM or semantic metadata.

**Example:**
```yaml
service: idm_heatpump.write_register
target:
  device_id: abc123def456
data:
  address: 1005
  value: "1"
  datatype: uchar
  acknowledge_risk: true
```

## Automation Examples (Writing Values)

The following examples show how to write values through automations.

### Change a regular entity (recommended method)
If you want to adjust a target temperature, for example, use the standard service `number.set_value`:
```yaml
action:
  - service: number.set_value
    target:
      entity_id: number.idm_navigator_dhw_setpoint
    data:
      value: "50"
```

Or to adjust a mode (`select.select_option`):
```yaml
action:
  - service: select.select_option
    target:
      entity_id: select.idm_navigator_circuit_a_mode
    data:
      option: "Eco"
```

### Direct Modbus write access (write_register)
To write to any register (here register 1005 for the operating mode) via an automation, use the `idm_heatpump.write_register` service:
```yaml
action:
  - service: idm_heatpump.write_register
    target:
      device_id: abc123def456
    data:
      address: 1005
      value: "1"
      datatype: uchar
      acknowledge_risk: true
```
*The datatype is mandatory whenever the register is not an unsigned 16-bit integer. Non-numeric values and values that cannot be represented by the selected datatype are rejected before network I/O.*

### Heat pump standby when away

```yaml
automation:
  - alias: "Heat pump standby when away"
    trigger:
      - platform: state
        entity_id: input_boolean.home
        to: "off"
    action:
      - service: idm_heatpump.set_system_mode
        target:
          entity_id: sensor.idm_navigator_system_mode
        data:
          mode: "Away"
```

### Heat pump holiday mode

```yaml
automation:
  - alias: "Heat pump holiday mode"
    trigger:
      - platform: input_boolean
        entity_id: input_boolean.holiday
        to: "on"
    action:
      - service: idm_heatpump.set_system_mode
        target:
          entity_id: sensor.idm_navigator_system_mode
        data:
          mode: "Holiday"
```

### Auto-acknowledge errors (use with caution!)

```yaml
automation:
  - alias: "Acknowledge errors"
    trigger:
      - platform: state
        entity_id: binary_sensor.idm_navigator_error_active
        to: "on"
        for:
          minutes: 5
    action:
      - service: idm_heatpump.acknowledge_errors
        target:
          device_id: abc123def456
```
