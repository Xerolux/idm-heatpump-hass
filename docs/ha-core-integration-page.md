---
title: IDM Heatpump
description: Instructions on how to integrate your IDM Navigator heat pump with Home Assistant via Modbus TCP.
ha_category:
  - Climate
  - Energy
  - Sensor
ha_release: "2026.x"
ha_iot_class: Local Polling
ha_config_flow: true
ha_codeowners:
  - "@xerolux"
ha_domain: idm_heatpump
ha_platforms:
  - binary_sensor
  - diagnostics
  - number
  - select
  - sensor
  - switch
ha_integration_type: device
ha_quality_scale: gold
ha_requirements:
  - pymodbus>=3.6.0
---

The **IDM Heatpump** integration allows you to monitor and control your [IDM Navigator 2.0](https://www.idm-energiesysteme.de/) heat pump directly from Home Assistant using the Modbus TCP protocol. All communication is local — no cloud, no account required.

## Prerequisites

- IDM Navigator 2.0 or Navigator Pro heat pump
- Modbus TCP enabled on the Navigator controller (default port: 502, Slave ID: 1)
- Network connection between Home Assistant and the heat pump

### Enable Modbus TCP on the Navigator

1. Open the Navigator web interface at `http://<ip-of-navigator>`
2. Navigate to **Settings → Communication → Modbus TCP**
3. Enable Modbus TCP
4. Note the **IP address**, **port** (default: `502`), and **Slave ID** (default: `1`)

{% include integrations/config_flow.md %}

## Configuration

The integration is set up via the UI. During setup you will configure:

| Parameter | Description | Default |
|-----------|-------------|---------|
| Host | IP address of the IDM Navigator | — (required) |
| Port | Modbus TCP port | `502` |
| Slave ID | Modbus slave ID | `1` |
| Name | Display name for the device | `IDM Navigator` |
| Scan interval | How often registers are read (5–300 s) | `10` |
| Heating circuits | Which circuits (A–G) are active | — |
| Zone modules | Number of zone modules (0–10) | `0` |
| Technician codes | Show technician-level access code sensors | `false` |

### Options

After initial setup, options can be changed via **Settings → Devices & Services → IDM Heatpump → Configure**:

- **Scan interval** – Polling frequency (5–300 seconds)
- **Active heating circuits** – Enable/disable individual heating circuits A through G
- **Zone modules** – Number of connected zone modules (each supports up to 8 rooms)
- **Room names** – Custom names for rooms in each zone module

### Reconfiguration

Host, port, and Slave ID can be updated without deleting the integration entry via **Settings → Devices & Services → IDM Heatpump → Reconfigure**.

## Platforms

### Sensor

Over 100 sensors are available, including:

| Sensor | Description |
|--------|-------------|
| System mode | Current operating mode of the heat pump |
| Outdoor temperature | Measured outside temperature |
| Flow temperature | Current supply/flow temperature |
| Return temperature | Current return temperature |
| Hot water temperature | Domestic hot water temperature |
| Hot water setpoint | Target temperature for domestic hot water |
| Heating circuit A–G flow/setpoint | Per-circuit temperatures and targets |
| Zone room temperatures | Per-room temperatures (if zone modules configured) |
| Compressor stages | Current compressor stage |
| Heat quantity | Accumulated energy output (kWh) |
| Power consumption | Current electrical consumption |
| Firmware version | Navigator firmware version (diagnostic) |
| Error code | Current error code (diagnostic) |
| Technician code level 1/2 | Time-based technician access codes (if enabled) |

Temperature sensors use `SensorDeviceClass.TEMPERATURE`, energy sensors use `ENERGY`, power sensors use `POWER`. Technical and diagnostic sensors are **disabled by default** and can be enabled individually.

### Binary sensor

| Sensor | Description |
|--------|-------------|
| Error active | `on` when a fault is present |
| Defrost active | `on` during defrost cycle |
| Heat pump running | `on` when the compressor is active |
| Hot water active | `on` during domestic hot water preparation |
| Heating active | `on` during heating operation |
| Cooling active | `on` during cooling operation |
| Solar active | `on` when solar circuit is active |
| Electric heater active | `on` when the auxiliary electric heater is active |
| GLT active | `on` when GLT remote control is active |

### Number

Write-capable register values exposed as number entities, for example:

- Hot water setpoint temperature
- Heating circuit A–G setpoint temperature
- Room setpoint temperatures (per zone/room)
- Return temperature setpoint
- Cooling setpoint temperatures

Number entities use `EntityCategory.CONFIG` and are disabled by default where applicable.

### Select

Mode selectors for:

- System operating mode (Standby / Auto / Away / Holiday / Hot water only / Heating-cooling only)
- Heating circuit A–G mode
- Room mode per zone/room (Auto / Comfort / Standard / Reduced / Off)
- Solar mode
- Smart grid mode

### Switch

| Switch | Description |
|--------|-------------|
| GLT heating request | Enable cyclic GLT heating request (writes register every 10 min) |
| GLT cooling request | Enable cyclic GLT cooling request |

### Diagnostics

The integration supports [diagnostics download](/integrations/diagnostics/) which exports the full current coordinator state including all register values, configuration, and error information. Sensitive values (IP address) are redacted automatically.

## Actions

### `idm_heatpump.set_system_mode`

Set the operating mode of the heat pump.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | string | yes | One of: `Standby`, `Automatik`, `Abwesend`, `Urlaub`, `Nur Warmwasser`, `Nur Heizung/Kuehlung` |

Example:

```yaml
action: idm_heatpump.set_system_mode
target:
  entity_id: sensor.idm_navigator_system_mode
data:
  mode: "Urlaub"
```

### `idm_heatpump.acknowledge_errors`

Acknowledge and clear active error messages on the heat pump.

```yaml
action: idm_heatpump.acknowledge_errors
target:
  device_id: <your_device_id>
```

### `idm_heatpump.write_register`

Write a value directly to a Modbus register. **For advanced users only.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `address` | integer | yes | Modbus register address (0–10000) |
| `value` | string | yes | Value to write |
| `acknowledge_risk` | boolean | yes | Must be `true` to confirm you accept the risk |

{% warning %}
Writing incorrect values to Modbus registers can damage your heat pump or invalidate your warranty. Only use this action if you know exactly what you are doing and have consulted the IDM Modbus register documentation.
{% endwarning %}

```yaml
action: idm_heatpump.write_register
target:
  device_id: <your_device_id>
data:
  address: 1005
  value: "1"
  acknowledge_risk: true
```

## Known limitations

- **Only IDM Navigator 2.0 / Navigator Pro** are officially supported. Older IDM controllers without Navigator firmware are not supported.
- **Modbus TCP only** — serial Modbus RTU is not supported.
- **EEPROM-protected registers** (88 total) can only be written once per minute. The integration enforces this limit automatically.
- **Polling only** — the heat pump does not push updates. Changes made via the Navigator web interface are visible only after the next polling cycle.
- **One device per config entry** — a single IDM heat pump per entry (uniqueness is based on IP address).
- Simultaneous Modbus TCP connections from multiple clients (e.g. Navigator web interface + Home Assistant) may cause timeout errors. Increase the scan interval or disable other Modbus clients if instability occurs.

## Troubleshooting

### Cannot connect

- Verify the **IP address** of the Navigator is correct and reachable
- Confirm **Modbus TCP** is enabled in the Navigator settings
- Check that **port 502** is not blocked by a firewall
- Ensure no other Modbus client is holding the connection open

### Entities show unavailable

- Check that the Navigator is reachable on the network
- Verify the Slave ID matches the Navigator configuration (default: `1`)
- Restart the Navigator if the issue persists

### Unexpected or extreme values (e.g. −3276.8 °C)

- This typically indicates a register address or data type mismatch for your specific firmware version
- Enable debug logging and check the raw register values
- Report the issue on [GitHub](https://github.com/Xerolux/idm-heatpump-hass/issues) with diagnostics data attached

### Enable debug logging

```yaml
logger:
  default: info
  logs:
    custom_components.idm_heatpump: debug
    pymodbus: debug
```

### Download diagnostics

1. Go to **Settings → Devices & Services**
2. Select **IDM Heatpump**
3. Click **Download diagnostics**
4. Attach the file to your bug report

## Automation examples

### Switch to holiday mode

```yaml
automation:
  - alias: "Heat pump holiday mode"
    trigger:
      - platform: state
        entity_id: input_boolean.holiday
        to: "on"
    action:
      - action: idm_heatpump.set_system_mode
        target:
          entity_id: sensor.idm_navigator_system_mode
        data:
          mode: "Urlaub"
```

### PV surplus hot water boost

```yaml
automation:
  - alias: "Hot water boost when PV surplus available"
    trigger:
      - platform: numeric_state
        entity_id: sensor.pv_surplus_power
        above: 2000
        for:
          minutes: 15
    action:
      - action: number.set_value
        target:
          entity_id: number.idm_navigator_hot_water_setpoint
        data:
          value: 60
```

### Error notification

```yaml
automation:
  - alias: "Notify on heat pump error"
    trigger:
      - platform: state
        entity_id: binary_sensor.idm_navigator_error_active
        to: "on"
    action:
      - action: notify.mobile_app
        data:
          title: "Heat pump error"
          message: "IDM Navigator reports an active error. Check the device."
```
