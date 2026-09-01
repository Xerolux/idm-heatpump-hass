# Services Reference

There are several ways to write values to the heat pump in this integration:
1. **Via regular entities (recommended):**
   Many values (such as temperatures, setpoints, or modes) are represented as `number`, `select`, or `switch` entities in Home Assistant. You can change them directly in dashboards or use them in automations with standard services (e.g., `number.set_value` or `select.select_option`). A list of all adjustable entities can be found at [Entities](Entities).
2. **Via specific services:**
   For special actions like acknowledging errors, setting the system mode,
   starting a DHW boost, or forwarding external climate data, there are
   dedicated services (e.g., `idm_heatpump.set_system_mode`).
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

## set_external_power

Writes external PV, consumption, battery and electric-heater measurements to
the known IDM GLT/BMS input registers. The action addresses the library
registers directly, so it does not depend on the corresponding `number`
entities being enabled or currently having a state.

**Service:** `idm_heatpump.set_external_power`

**Target:** Entity of the integration, or provide `entry_id` when multiple IDM entries are loaded

| Field | Type | Description |
|-------|------|-------------|
| `pv_surplus` | number | Optional current PV surplus in kW |
| `pv_production` | number | Optional current PV production in kW |
| `house_consumption` | number | Optional current house consumption in kW |
| `battery_discharge` | number | Optional current battery discharge power in kW |
| `battery_soc` | integer | Optional battery state of charge (`0`…`100` %) |
| `electric_heater_power` | number | Optional electric-heater power in kW |

Every measurement field is optional, but each call must contain at least one
measurement. For example, an energy manager that only knows three values can
send just those values:

```yaml
action: idm_heatpump.set_external_power
data:
  pv_surplus: 1.537
  pv_production: 1.686
  house_consumption: 0.386
```

### Validation and API range metadata

The integration's API 0.9.1 contract fixture currently records the following
range metadata:

| Register | API `min_val` | API `max_val` | Integration validation |
|----------|---------------|---------------|------------------------|
| `pv_surplus` | not set | not set | finite number |
| `pv_production` | not set | not set | finite number |
| `house_consumption` | not set | not set | finite number |
| `battery_discharge` | not set | not set | finite number |
| `battery_soc` | not set | not set | whole number `0`…`100` |
| `electric_heater_power` | not set | not set | finite number |

The valid physical range of the five power measurements can depend on the
connected energy manager and on whether the installation uses a signed value
to describe the direction of energy flow. The integration therefore does not
invent universal limits for those fields; it rejects non-numeric, NaN and
infinite values and applies library limits automatically if a future tested API
release supplies them.

The table was rechecked against the published
`idm-heatpump-api[web]==2.0.0` artifact. Those GLT power registers still do not
declare universal minimum or maximum values; the integration therefore keeps
the finite-number validation described above.

`battery_soc` is a signed INT16 register whose documented valid input is a
whole percentage from `0` to `100`; `-1` is its unavailable sentinel. The
action enforces `0`…`100` explicitly rather than accepting the sentinel as an
external input. See [Modbus Registers](Modbus-Register#pv-energy-management-datatype-reference)
for the register datatypes.

### Multiple values and partial failures

The action validates **all** supplied values and verifies that all requested
registers are available and writable before the first Modbus write. A
validation or unsupported-register error therefore writes nothing.

The subsequent device writes are separate Modbus operations and are not an
atomic transaction. If the connection fails after one or more successful
writes, earlier values may already have reached the heat pump while later
values have not. Home Assistant reports the write failure; the caller should
retry the complete current measurement set on its next update. This action is
intended for cyclic live measurements, not one-time transactional changes.

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

## start_dhw_boost

Starts a time-limited DHW quick heating cycle. The heat pump raises the DHW
target to maximum and prioritizes hot water until the boost duration expires or
is cancelled.

**Service:** `idm_heatpump.start_dhw_boost`

**Target:** Device of the integration

| Field | Type | Description |
|-------|------|-------------|
| `minutes` | number | Boost duration in minutes (1–1440). Default 60. |

**Example:**
```yaml
service: idm_heatpump.start_dhw_boost
target:
  device_id: abc123def456
data:
  minutes: 90
```

The boost is restart-safe: if Home Assistant restarts during a boost, the
remaining time is restored from the heat pump's active DHW setpoint register.

## cancel_dhw_boost

Cancels an active DHW boost and restores the previous DHW setpoint.

**Service:** `idm_heatpump.cancel_dhw_boost`

**Target:** Device of the integration

**Example:**
```yaml
service: idm_heatpump.cancel_dhw_boost
target:
  device_id: abc123def456
```

## export_knx_group_addresses

Returns the IDM KNX object table for this controller so it can be recreated
in ETS. Read-only: it calculates addresses and never sends anything on the
bus. See [KNX Bridge](KNX-Bridge) for the bridge itself.

**Service:** `idm_heatpump.export_knx_group_addresses`

**Target:** Entity or device of the integration

**Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `knx_base_address` | no | Base address the object numbers are added to. Defaults to the configured bridge address. |
| `knx_groups` | no | Limit the export to these catalogue groups. Defaults to the configured selection. |

**Example:**
```yaml
action: idm_heatpump.export_knx_group_addresses
target:
  entity_id: sensor.idm_heatpump_outdoor_temperature
data:
  knx_base_address: "8/0/0"
response_variable: knx_objects
```

**Response:**
```yaml
base_address: "8/0/0"
count: 187
objects:
  - object: 1
    group_address: "8/0/1"
    register: outdoor_temp
    dpt: "9.001"
    group: system
    writable: false
    unit: "°C"
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
