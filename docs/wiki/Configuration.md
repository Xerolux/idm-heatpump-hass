# Configuration

## Connection Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Host (IP)** | IP address of the IDM Navigator | - (required) |
| **Port** | Modbus TCP port | 502 |
| **Name** | Integration name (to distinguish multiple instances) | IDM Navigator |

## Options

### Scan Interval

The scan interval determines how often registers are polled.

| Value | Recommendation |
|-------|---------------|
| 10 seconds | For active monitoring (default) |
| 30 seconds | Balanced |
| 60 seconds | For quieter systems |

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
4. Changes to scan interval, heating circuits, and zones will be applied

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
