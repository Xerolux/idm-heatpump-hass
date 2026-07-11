# Example Automations

Here you'll find practical examples for using the IDM Heatpump integration, especially how to write values via automations.

---

## Writing Values via Automation (Overview)

In Home Assistant, writable values of the heat pump are represented as **entities**. To change these values in automations, you don't use `idm_heatpump.write_register`, but the standard Home Assistant services:

- For temperatures, heating curves, or setpoints (type `number`): service `number.set_value`
- For operating modes (type `select`): service `select.select_option`
- For switches (type `switch`): service `switch.turn_on` or `switch.turn_off`

**Alternative (advanced):** If a register doesn't exist as an entity, you can use the `idm_heatpump.write_register` service (see [Services Reference](Services)).

Here are some concrete use cases:

---

## Auto-activate holiday mode

Switches the heat pump to holiday mode when you leave the house:

```yaml
automation:
  - alias: "Heat pump: Holiday mode when away"
    trigger:
      - platform: state
        entity_id: person.me
        to: "not_home"
        for:
          hours: 2
    action:
      - service: idm_heatpump.set_system_mode
        data:
          mode: "holiday"
```

---

## Normal operation on return

```yaml
automation:
  - alias: "Heat pump: Auto mode on return"
    trigger:
      - platform: state
        entity_id: person.me
        to: "home"
    action:
      - service: idm_heatpump.set_system_mode
        data:
          mode: "automatic"
```

---

## Fault notification

Sends a push notification when a fault occurs:

```yaml
automation:
  - alias: "Heat pump: Fault notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.idm_heatpump_fault
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Heat Pump Fault"
          message: >
            IDM fault active. Error code: {{ states('sensor.idm_heatpump_error_code') }}
```

---

## Forward PV surplus through the supported GLT entity

Register 74 is designed to receive the current PV surplus from one energy
manager. Use the generated writable `number` entity so FLOAT word order and
validation remain inside the integration. Replace the example entity IDs with
your actual IDs. Do not run this automation if an inverter, E3DC, Smartfox or
another controller already writes the same register.

```yaml
automation:
  - alias: "Heat pump: Forward PV surplus"
    mode: restart
    trigger:
      - platform: state
        entity_id: sensor.house_pv_surplus_kw
    condition:
      - condition: template
        value_template: "{{ is_number(states('sensor.house_pv_surplus_kw')) }}"
    action:
      - service: number.set_value
        target:
          entity_id: number.idm_heatpump_pv_surplus_set
        data:
          value: "{{ [states('sensor.house_pv_surplus_kw') | float(0), 0] | max }}"
```

Thresholds at which a heat pump starts, stops or modulates depend on the exact
model, firmware, temperatures and controller configuration. A fixed 2–3 kW
threshold is therefore not a universal default.

---

## Request DHW charging with explicit safety stops

For a temporary external request, prefer the generated switch for register
1712 over repeatedly changing an EEPROM-backed DHW setpoint. The thresholds
below are examples only and must be agreed with the installer for the actual
hydraulic system.

```yaml
automation:
  - alias: "Heat pump: Start DHW request from PV"
    trigger:
      - platform: numeric_state
        entity_id: sensor.house_pv_surplus_kw
        above: 3.0
        for:
          minutes: 10
    condition:
      - condition: numeric_state
        entity_id: sensor.idm_heatpump_dhw_temp_bottom
        below: 50
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.idm_heatpump_demand_dhw_charging

  - alias: "Heat pump: Stop external DHW request"
    mode: restart
    trigger:
      - platform: numeric_state
        entity_id: sensor.idm_heatpump_dhw_temp_bottom
        above: 54
      - platform: numeric_state
        entity_id: sensor.house_pv_surplus_kw
        below: 0.5
        for:
          minutes: 10
      - platform: state
        entity_id: switch.idm_heatpump_demand_dhw_charging
        to: "on"
        for:
          minutes: 60
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.idm_heatpump_demand_dhw_charging
```

External requests should always have temperature, low-surplus and maximum-time
stop paths. Verify the behavior with the Navigator GLT Monitor before leaving
the automation unattended.

---

## EEPROM-backed DHW setpoint boost (use sparingly)

This alternative changes a persistent setpoint. It is suitable only for
occasional mode changes, not rapid tracking of fluctuating PV power:

```yaml
automation:
  - alias: "Heat pump: DHW boost on PV surplus"
    trigger:
      - platform: numeric_state
        entity_id: sensor.idm_heatpump_pv_surplus
        above: 2.0
        for:
          minutes: 15
    action:
      - service: number.set_value
        target:
          entity_id: number.idm_heatpump_dhw_setpoint
        data:
          value: 60
  - alias: "Heat pump: End DHW boost"
    trigger:
      - platform: numeric_state
        entity_id: sensor.idm_heatpump_pv_surplus
        below: 0.5
        for:
          minutes: 10
    action:
      - service: number.set_value
        target:
          entity_id: number.idm_heatpump_dhw_setpoint
        data:
          value: 48
```

---

## Heating circuit mode by schedule

Switches heating circuit A daily on a schedule:

```yaml
automation:
  - alias: "Heat pump: Circuit A – Schedule"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.idm_heatpump_circuit_a_mode
        data:
          option: "Eco"
  - alias: "Heat pump: Circuit A – Normal operation"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.idm_heatpump_circuit_a_mode
        data:
          option: "Normal"
```

---

## Energy Dashboard

Use native IDM energy sensors when your device exposes them with stable values. Where the device only exposes power, use Home Assistant helpers to integrate power over time instead of treating a power sensor as a native energy meter.

```yaml
# Daily heating energy (in configuration.yaml or helpers)
sensor:
  - platform: integration
    source: sensor.idm_heatpump_current_heating_power
    name: Daily energy heating
    unit_prefix: k
    round: 2
```

For dashboard cards, prefer sensors with `kWh` and `total_increasing` semantics. If a model does not expose a reliable total energy register, create an HA integration helper and name it clearly as a calculated value.

---

## Smart Grid Control

Reacts to the heat pump's Smart Grid status:

```yaml
automation:
  - alias: "SmartGrid: Read heat pump status"
    trigger:
      - platform: state
        entity_id: sensor.idm_heatpump_smart_grid_status
    action:
      - service: notify.persistent_notification
        data:
          title: "Smart Grid Status"
          message: "Current Smart Grid status: {{ states('sensor.idm_heatpump_smart_grid_status') }}"
```

---

## Temporary Load Limitation

Power limit registers are model-dependent and disabled by default. Only enable and automate them after confirming support for your exact model and firmware.

```yaml
automation:
  - alias: "Heat pump: temporary power limit"
    trigger:
      - platform: state
        entity_id: binary_sensor.grid_limit_active
        to: "on"
    action:
      - service: number.set_value
        target:
          entity_id: number.idm_heatpump_power_limit_hp
        data:
          value: 3.5
  - alias: "Heat pump: clear temporary power limit"
    trigger:
      - platform: state
        entity_id: binary_sensor.grid_limit_active
        to: "off"
    action:
      - service: number.set_value
        target:
          entity_id: number.idm_heatpump_power_limit_hp
        data:
          value: -1
```

---

## Acknowledge errors (manually via button helper)

```yaml
# button-helper in configuration.yaml
button:
  - platform: template
    buttons:
      idm_acknowledge_errors:
        friendly_name: "Acknowledge IDM faults"
        press:
          service: idm_heatpump.acknowledge_errors
```
