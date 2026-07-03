# Configuration

## Connection Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Host (IP)** | IP address of the IDM Navigator | - (required) |
| **Port** | Modbus TCP port | 502 |
| **Slave ID** | Modbus slave ID | 1 |
| **Name** | Integration name (to distinguish multiple instances) | IDM Navigator |
| **Local web PIN** | Optional PIN for local Navigator web supplement data | empty |

Leave the web PIN empty if you want Modbus-only operation. Modbus remains the
baseline path and works without a PIN.

## Options

### Scan Interval

The scan interval determines how often registers are polled.

| Value | Recommendation |
|-------|---------------|
| 10 seconds | For active monitoring (default) |
| 30 seconds | Balanced |
| 60 seconds | For quieter systems |

### Web Supplement Data

The integration can optionally read additional local Navigator web data through
`idm-heatpump-api`. This is read-only and additive. It is used for values such
as Navigator generation, software version, heat pump model, selected Web UI
diagnostics, and Navigator 10 infosystem notifications.

| Option | Description | Default |
|--------|-------------|---------|
| Web supplement data | Enables the optional local web poll when a PIN is configured | on when a PIN is configured |
| Web supplement interval | Separate polling interval for web data | 30 seconds |
| Web host | Optional separate host for the Navigator web interface, useful when Modbus goes through a proxy | Modbus host |

Important behavior:

- If no PIN is configured, no web client is created and the integration stays in
  Modbus-only mode.
- If the PIN is wrong during setup or reconfiguration, the form shows the PIN
  error immediately and Home Assistant logs the rejected PIN attempt.
- If the web interface is unreachable later, Modbus polling continues.
- Web polling runs separately and starts slightly after Modbus polling so both
  protocols do not hit the controller at the exact same moment.
- Modbus values always have priority. Web sensors are only created for extra
  values or for values that are not already represented by Modbus entities.
- If a Modbus proxy is used, enter the proxy IP as **Host** and the original
  heat pump IP as **Web host** so the local Navigator web interface can still
  be reached.

### Room Temperature Forwarding

Room temperature forwarding is optional and disabled by default. When enabled,
the integration can forward selected Home Assistant temperature sensors to the
IDM external room temperature registers of the active heating circuits, for
example `hc_a_ext_room_temp`.

| Option | Description | Default |
|--------|-------------|---------|
| Room temperature forwarding | Enables forwarding for selected circuits | off |
| Forwarding interval | Periodic refresh interval for selected room temperatures | 300 seconds |
| Forwarding tolerance | Minimum change before a repeated value is written again | 0.2 °C |
| Sensor per heating circuit | Home Assistant temperature entity to forward | empty |

Important behavior:

- Values are written on sensor state changes and also refreshed periodically.
- Invalid, unavailable, non-numeric or out-of-range values are skipped.
- Leaving a circuit without a selected sensor keeps that circuit untouched.
- This feature writes Modbus values. Use sensors that represent the actual room
  temperature you want the heat pump to see.

### Heating Circuits

Select the active heating circuits (A through G). Only enabled circuits create entities in Home Assistant.

### Zones

Specify the number of zone modules (0–10). Each zone module supports up to 6 rooms on current hardware (Navigator 10). Older systems may support 8 rooms.

### Technician Level Codes

Enable this option to get two additional sensor entities that display the current technician level access codes:

| Sensor | Description |
|--------|-------------|
| `sensor.{name}_fachmann_ebene_1` | 4-digit code: day + month (`DDMM`) |
| `sensor.{name}_fachmann_ebene_2` | 5-digit code derived from hour, year, month, day |

The codes are automatically updated every minute and can be displayed in a HA dashboard card or notification. They correspond to the codes that must be entered on the IDM Navigator display under *Technician Level*.

### Room Names

For each room in each zone, you can assign a custom name. These names are used as entity names in Home Assistant.

## Reconfiguration

1. Go to **Settings → Devices & Services**
2. Click **IDM Heatpump**
3. Click **Reconfigure**
4. Update host, port, slave ID, or the optional local web PIN
5. A wrong web PIN is rejected directly in the flow. Leaving it empty keeps the
   entry in Modbus-only mode.

Use **Configure** for scan interval, heating circuits, zones, technician codes,
optional web supplement settings, and optional room temperature forwarding.

## Debug Logging

Enable extended logging for troubleshooting:

```yaml
logger:
  default: info
  logs:
    custom_components.idm_heatpump: debug
```

## EEPROM Notice

Certain registers are **EEPROM-sensitive** (88 total). These registers are stored in EEPROM when written and have a limited number of write cycles. The integration warns about excessive writing of these registers.

## BMS Cyclic Writing

Registers 1696 and 1698 (BMS temperature requests) must be written cyclically every 10 minutes to remain active. The switch entities for BMS requests handle this automatically.
