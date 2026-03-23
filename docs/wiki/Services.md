# Services Referenz

In dieser Integration gibt es mehrere Möglichkeiten, Werte auf die Wärmepumpe zu schreiben:
1. **Über die regulären Entitäten (Empfohlen):**
   Viele Werte (wie Temperaturen, Sollwerte oder Modi) werden als `number`, `select` oder `switch` Entitäten in Home Assistant abgebildet. Diese kannst du direkt in Dashboards verändern oder in Automatisierungen mit den Standard-Diensten (z.B. `number.set_value` oder `select.select_option`) nutzen.
2. **Über spezifische Dienste:**
   Für spezielle Aktionen wie das Quittieren von Fehlern oder das Setzen des Systemmodus gibt es dedizierte Dienste (z.B. `idm_heatpump.set_system_mode`).
3. **Direkter Modbus-Zugriff (Fortgeschritten):**
   Fehlt eine Entität für ein bestimmtes Register, kannst du mit dem Dienst `idm_heatpump.write_register` direkt Werte in beliebige Modbus-Register schreiben. **Achtung: Dies geschieht auf eigene Gefahr.**

---

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

## Automatisierungs-Beispiele (Werte schreiben)

Hier sind einige Beispiele, wie du Werte über Automatisierungen schreiben kannst. Weitere praxisnahe Beispiele findest du auf der Seite [Examples](Examples.md).

### Reguläre Entität ändern (Empfohlene Methode)
Möchtest du z.B. eine Solltemperatur anpassen, nutze den Standard-Dienst `number.set_value`:
```yaml
action:
  - service: number.set_value
    target:
      entity_id: number.idm_navigator_warmwasser_solltemperatur
    data:
      value: "50"
```

Oder um einen Modus anzupassen (`select.select_option`):
```yaml
action:
  - service: select.select_option
    target:
      entity_id: select.idm_navigator_betriebsart_hk_a
    data:
      option: "Eco"
```

### Direkter Modbus-Schreibzugriff (write_register)
Um ein beliebiges Register (hier Register 1005 für die Betriebsart) über eine Automatisierung zu beschreiben, nutzt du den Dienst `idm_heatpump.write_register`:
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
*Hinweis: Beachte, dass manche Register spezielle Formatierungen (Float, Int etc.) erwarten. Du musst sicherstellen, dass der geschriebene Wert im Modbus-Kontext gültig ist.*

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
