# Services Referenz

## set_system_mode

Setzt den Betriebsmodus der Warmepumpe.

**Service:** `idm_heatpump.set_system_mode`

**Target:** Entity der Integration

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `mode` | select | System-Betriebsmodus |

**Verfugbare Modi:**
- `Standby`
- `Automatik`
- `Abwesend`
- `Urlaub`
- `Nur Warmwasser`
- `Nur Heizung/Kuehlung`

**Beispiel:**
```yaml
service: idm_heatpump.set_system_mode
target:
  entity_id: sensor.idm_navigator_system_mode
data:
  mode: "Urlaub"
```

## acknowledge_errors

Quittiert/loscht aktive Fehlermeldungen auf der Warmepumpe.

**Service:** `idm_heatpump.acknowledge_errors`

**Target:** Gerat der Integration

**Beispiel:**
```yaml
service: idm_heatpump.acknowledge_errors
target:
  device_id: abc123def456
```

## write_register

Schreibt einen Wert direkt in ein Modbus-Register (Fortgeschritten).

**Service:** `idm_heatpump.write_register`

**Target:** Gerat der Integration

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `address` | number | Modbus-Register-Adresse (0-10000) |
| `value` | text | Zu schreibender Wert |
| `acknowledge_risk` | constant | Muss auf `true` gesetzt werden |

> **WARNUNG:** Direktes Schreiben in Register kann deine Warmepumpe beschadigen. Verwende diesen Service nur wenn du genau weisst was du tust!

**Beispiel:**
```yaml
service: idm_heatpump.write_register
target:
  device_id: abc123def456
data:
  address: 1005
  value: "1"
  acknowledge_risk: true
```

## Automatisierungs-Beispiele

### Warmepumpe bei Abwesenheit auf Standby

```yaml
automation:
  - alias: "Warmepumpe Standby bei Abwesenheit"
    trigger:
      - platform: state
        entity_id: input_boolean.zuhause
        to: "off"
    action:
      - service: idm_heatpump.set_system_mode
        target:
          entity_id: sensor.idm_navigator_system_mode
        data:
          mode: "Abwesend"
```

### Warmepumpe bei Urlaub

```yaml
automation:
  - alias: "Warmepumpe Urlaubsmodus"
    trigger:
      - platform: input_boolean
        entity_id: input_boolean.urlaub
        to: "on"
    action:
      - service: idm_heatpump.set_system_mode
        target:
          entity_id: sensor.idm_navigator_system_mode
        data:
          mode: "Urlaub"
```

### Fehler automatisch quittieren (Vorsicht!)

```yaml
automation:
  - alias: "Fehler quittieren"
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
