# Services Reference

There are several ways to write values to the heat pump in this integration:
1. **Via regular entities (recommended):**
   Many values (such as temperatures, setpoints, or modes) are represented as `number`, `select`, or `switch` entities in Home Assistant. You can change them directly in dashboards or use them in automations with standard services (e.g., `number.set_value` or `select.select_option`). A list of all adjustable entities can be found at [Entities](Entities).
2. **Via specific services:**
   For special actions like acknowledging errors or setting the system mode, there are dedicated services (e.g., `idm_heatpump.set_system_mode`).
3. **Direct Modbus access (advanced / alternative):**
   If an entity for a specific register is missing or you want to target registers directly, you can use the `idm_heatpump.write_register` service to write values directly to any Modbus register. An overview of registers can be found at [Modbus Registers](Modbus-Register). **Warning: Use at your own risk.**

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

## write_register

Writes a value directly to a Modbus register (advanced).

**Service:** `idm_heatpump.write_register`

**Target:** Device of the integration

| Field | Type | Description |
|-------|------|-------------|
| `address` | number | Modbus register address (0–10000) |
| `value` | text | Value to write |
| `acknowledge_risk` | constant | Must be set to `true` |

> **WARNING:** Direct register writing can damage your heat pump. Only use this service if you know exactly what you are doing!

**Example:**
```yaml
service: idm_heatpump.write_register
target:
  device_id: abc123def456
data:
  address: 1005
  value: "1"
  acknowledge_risk: true
```

## Automation Examples (Writing Values)

Here are some examples of how to write values via automations. For more practical examples, see the [Examples](Examples) page.

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
      acknowledge_risk: true
```
*Note: Some registers expect special formatting (Float, Int, etc.). You must ensure that the written value is valid in the Modbus context.*

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
