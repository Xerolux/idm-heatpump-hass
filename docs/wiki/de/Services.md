# Aktionen (Services) – Referenz

In dieser Integration gibt es mehrere Möglichkeiten, Werte in die Wärmepumpe zu schreiben:
1. **Über reguläre Entitäten (empfohlen):**
   Viele Werte (etwa Temperaturen, Sollwerte oder Modi) werden in Home Assistant als `number`-, `select`- oder `switch`-Entitäten dargestellt. Du kannst sie direkt in Dashboards ändern oder in Automationen mit Standard-Aktionen verwenden (z. B. `number.set_value` oder `select.select_option`). Eine Liste aller einstellbaren Entitäten findest du unter [Entitäten](Entities).
2. **Über spezifische Aktionen:**
   Für besondere Aktionen wie das Quittieren von Fehlern, das Setzen des Systemmodus, das Starten eines Warmwasser-Boosts oder das Weiterleiten externer Klimadaten gibt es dedizierte Aktionen (z. B. `idm_heatpump.set_system_mode`).
3. **Direkter Modbus-Zugriff (fortgeschritten / Alternative):**
   Wenn für ein bestimmtes Register keine Entität existiert oder du Register direkt ansprechen willst, kannst du mit der Aktion `idm_heatpump.write_register` Werte direkt in beliebige Modbus-Register schreiben. Eine Registerübersicht findest du unter [Modbus-Register](Modbus-Register). **Warnung:** Verwendung auf eigene Gefahr.

### Wo du schreibbare Steuerelemente in Home Assistant findest

Auf der IDM-Geräteseite erscheinen schreibbare Werte als `number`-, `select`- und
`switch`-Entitäten statt in einer separaten Aktorliste. Öffne in einer
Automation **Aktion hinzufügen**, suche nach der Entität oder nach IDM und
wähle die entsprechende Entitäts-Aktion. IDM-spezifische Aktionen wie die
Fehlerquittierung erscheinen im selben Aktions-Auswahldialog. Bevorzuge diese
generierten Entitäten, denn sie bewahren den Datentyp der Bibliothek, den
Wertebereich, die Modellverfügbarkeit sowie die Metadaten zu EEPROM und
zyklischem Schreiben.

### Welche Werte können geschrieben werden?
Mit dieser Integration kannst du im Wesentlichen die folgenden Werte ändern (siehe [Entitäten](Entities)):
- **Temperaturen & Sollwerte** über `number`-Entitäten (z. B. Warmwasser-Sollwert, Kreis-Sollwert, Heizgrenze).
- **Betriebsmodi** über `select`-Entitäten (z. B. System-Betriebsmodus, Kreis-Modus, Raum-Modus).
- **GLT-Temperaturanforderungen** über `switch`-Entitäten (das zyklische Schreiben der GLT-Register übernimmt die Integration automatisch).

---

## set_system_mode

Setzt den Betriebsmodus der Wärmepumpe.

**Aktion:** `idm_heatpump.set_system_mode`

**Ziel:** Entität der Integration

| Feld | Typ | Beschreibung |
|-------|------|-------------|
| `mode` | select | System-Betriebsmodus |

**Verfügbare Modi:**
- `Standby`
- `Auto`
- `Away`
- `Holiday`
- `DHW Only`
- `Heating/Cooling Only`

**Beispiel:**
```yaml
service: idm_heatpump.set_system_mode
target:
  entity_id: sensor.idm_navigator_system_mode
data:
  mode: "Holiday"
```

## acknowledge_errors

Quittiert/löscht aktive Fehlermeldungen der Wärmepumpe.

**Aktion:** `idm_heatpump.acknowledge_errors`

**Ziel:** Gerät der Integration

**Beispiel:**
```yaml
service: idm_heatpump.acknowledge_errors
target:
  device_id: abc123def456
```

## set_external_climate

Schreibt eine externe Raumtemperatur und optional eine relative Luftfeuchtigkeit in die IDM-GLT-Register, ohne dass rohe Modbus-Adressen nötig sind. Die Aktion verwendet die bekannten Registerdefinitionen aus `idm-heatpump-api`, sodass Modellverfügbarkeit, Datentyp und Schreibsicherheitsprüfungen aktiv bleiben.

**Aktion:** `idm_heatpump.set_external_climate`

**Ziel:** Entität der Integration, oder gib `entry_id` an, wenn mehrere IDM-Einträge geladen sind

| Feld | Typ | Beschreibung |
|-------|------|-------------|
| `heating_circuit` | select | Heizkreis `A`–`G` für die externe Raumtemperatur |
| `room_temperature` | number | Externe Raumtemperatur in °C (`-20`…`60`) |
| `humidity` | number | Optionale externe relative Luftfeuchtigkeit in % (`0`…`100`) |

**Beispiel:**
```yaml
action: idm_heatpump.set_external_climate
data:
  heating_circuit: A
  room_temperature: 23.1
  humidity: 58.4
```

**Beispiel für eine zyklische Automation:**
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

Schreibt externe PV-, Verbrauchs-, Batterie- und Elektroheizstab-Messwerte in
die bekannten IDM-GLT-Eingangsregister. Die Aktion adressiert die
Bibliotheks-Register direkt und hängt daher nicht davon ab, ob die
entsprechenden `number`-Entitäten aktiviert sind oder gerade einen Zustand
haben.

**Aktion:** `idm_heatpump.set_external_power`

**Ziel:** Entität der Integration, oder gib `entry_id` an, wenn mehrere IDM-Einträge geladen sind

| Feld | Typ | Beschreibung |
|-------|------|-------------|
| `pv_surplus` | number | Optionaler aktueller PV-Überschuss in kW |
| `pv_production` | number | Optionale aktuelle PV-Produktion in kW |
| `house_consumption` | number | Optionaler aktueller Hausverbrauch in kW |
| `battery_discharge` | number | Optionale aktuelle Entladeleistung der Batterie in kW |
| `battery_soc` | integer | Optionaler Ladezustand der Batterie (`0`…`100` %) |
| `electric_heater_power` | number | Optionale Leistung des Elektroheizstabs in kW |

Jedes Messwertfeld ist optional, aber jeder Aufruf muss mindestens einen
Messwert enthalten. Ein Energiemanager, der nur drei Werte kennt, kann
beispielsweise genau diese Werte senden:

```yaml
action: idm_heatpump.set_external_power
data:
  pv_surplus: 1.537
  pv_production: 1.686
  house_consumption: 0.386
```

### Validierung und API-Bereichsmetadaten

Der Kontrakt-Fixture der API 0.9.1 dieser Integration erfasst derzeit die
folgenden Bereichsmetadaten:

| Register | API `min_val` | API `max_val` | Validierung der Integration |
|----------|---------------|---------------|------------------------------|
| `pv_surplus` | nicht gesetzt | nicht gesetzt | endliche Zahl |
| `pv_production` | nicht gesetzt | nicht gesetzt | endliche Zahl |
| `house_consumption` | nicht gesetzt | nicht gesetzt | endliche Zahl |
| `battery_discharge` | nicht gesetzt | nicht gesetzt | endliche Zahl |
| `battery_soc` | nicht gesetzt | nicht gesetzt | ganze Zahl `0`…`100` |
| `electric_heater_power` | nicht gesetzt | nicht gesetzt | endliche Zahl |

Der gültige physikalische Bereich der fünf Leistungsmesswerte kann vom
angeschlossenen Energiemanager abhängen und davon, ob die Anlage einen
vorzeichenbehafteten Wert zur Beschreibung der Energieflussrichtung verwendet.
Die Integration erfindet daher keine universellen Grenzen für diese Felder;
sie lehnt nicht-numerische, NaN- und unendliche Werte ab und wendet
Bibliotheksgrenzen automatisch an, falls eine künftige getestete API-Version
sie liefert.

Die Tabelle wurde erneut mit dem veröffentlichten Artefakt
`idm-heatpump-api[web]==2.4.3` abgeglichen. Diese GLT-Leistungsregister
deklarieren weiterhin keine universellen Mindest- oder Höchstwerte; die
Integration behält daher die oben beschriebene Validierung auf endliche
Zahlen bei.

`battery_soc` ist ein vorzeichenbehaftetes INT16-Register, dessen dokumentierte
gültige Eingabe eine ganze Prozentzahl von `0` bis `100` ist; `-1` ist sein
Sentinel-Wert für „nicht verfügbar“. Die Aktion erzwingt `0`…`100` explizit,
statt den Sentinel-Wert als externe Eingabe zu akzeptieren. Siehe
[Modbus-Register](Modbus-Register#datentyp-referenz-fur-pv-energiemanagement)
für die Register-Datentypen.

### Mehrere Werte und Teilfehler

Die Aktion validiert **alle** angegebenen Werte und stellt sicher, dass alle
angeforderten Register verfügbar und beschreibbar sind, bevor der erste
Modbus-Schreibvorgang erfolgt. Tritt ein Validierungsfehler auf oder wird ein
Register nicht unterstützt, wird daher gar nichts geschrieben.

Die anschließenden Schreibvorgänge auf das Gerät sind einzelne
Modbus-Operationen und keine atomare Transaktion. Bricht die Verbindung nach
einem oder mehreren erfolgreichen Schreibvorgängen ab, können frühere Werte
die Wärmepumpe bereits erreicht haben, während spätere Werte nicht angekommen
sind. Home Assistant meldet den Schreibfehler; der Aufrufer sollte das
vollständige aktuelle Messwertset beim nächsten Update erneut senden. Diese
Aktion ist für zyklische Live-Messwerte gedacht, nicht für einmalige
transaktionale Änderungen.

## write_register

Schreibt einen Wert direkt in ein Modbus-Register (fortgeschritten).

**Aktion:** `idm_heatpump.write_register`

**Ziel:** Gerät der Integration

| Feld | Typ | Beschreibung |
|-------|------|-------------|
| `address` | number | Modbus-Registeradresse (0–10000) |
| `value` | text | Zu schreibender Wert |
| `datatype` | select | `uint16` (Standard), `int16`, `float`, `uchar` oder `bool` |
| `acknowledge_risk` | constant | Muss auf `true` gesetzt werden |

> **Warnung:** Direktes Schreiben von Registern kann deine Wärmepumpe
beschädigen. Verwende diese Aktion nur, wenn du genau weißt, was du tust. Die
Integration prüft die numerische Umwandlung und die Kodierung, aber eine frei
gewählte Adresse hat keine bekannten Bereichs-, Enum-, EEPROM- oder
semantischen Metadaten.

**Beispiel:**
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

Startet eine zeitlich begrenzte Warmwasser-Schnellladung. Die Wärmepumpe hebt
das Warmwasser-Ziel auf das Maximum und priorisiert Warmwasser, bis die
Boost-Dauer abläuft oder abgebrochen wird.

**Aktion:** `idm_heatpump.start_dhw_boost`

**Ziel:** Gerät der Integration

| Feld | Typ | Beschreibung |
|-------|------|-------------|
| `minutes` | number | Boost-Dauer in Minuten (1–1440). Standard 60. |

**Beispiel:**
```yaml
service: idm_heatpump.start_dhw_boost
target:
  device_id: abc123def456
data:
  minutes: 90
```

Der Boost ist neustartsicher: Startet Home Assistant während eines Boosts neu,
wird die verbleibende Zeit aus dem aktiven Warmwasser-Sollwertregister der
Wärmepumpe wiederhergestellt.

## cancel_dhw_boost

Bricht einen aktiven Warmwasser-Boost ab und stellt den vorherigen Warmwasser-Sollwert wieder her.

**Aktion:** `idm_heatpump.cancel_dhw_boost`

**Ziel:** Gerät der Integration

**Beispiel:**
```yaml
service: idm_heatpump.cancel_dhw_boost
target:
  device_id: abc123def456
```

## export_knx_group_addresses

Gibt die IDM-KNX-Objekttabelle dieses Reglers zurück, damit sie in ETS
nachgebaut werden kann. Schreibgeschützt: Die Aktion berechnet Adressen und
sendet niemals etwas auf den Bus. Siehe [KNX-Bridge](KNX-Bridge) für die
Bridge selbst.

**Aktion:** `idm_heatpump.export_knx_group_addresses`

**Ziel:** Entität oder Gerät der Integration

**Felder:**

| Feld | Erforderlich | Beschreibung |
|-------|----------|-------------|
| `knx_base_address` | nein | Basisadresse, zu der die Objektnummern addiert werden. Standard ist die konfigurierte Bridge-Adresse. |
| `knx_groups` | nein | Beschränkt den Export auf diese Kataloggruppen. Standard ist die konfigurierte Auswahl. |

**Beispiel:**
```yaml
action: idm_heatpump.export_knx_group_addresses
target:
  entity_id: sensor.idm_heatpump_outdoor_temperature
data:
  knx_base_address: "8/0/0"
response_variable: knx_objects
```

**Antwort:**
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

## Automation-Beispiele (Werte schreiben)

Die folgenden Beispiele zeigen, wie du Werte über Automationen schreibst.

### Eine reguläre Entität ändern (empfohlene Methode)
Wenn du beispielsweise eine Zieltemperatur anpassen möchtest, verwende die Standard-Aktion `number.set_value`:
```yaml
action:
  - service: number.set_value
    target:
      entity_id: number.idm_navigator_dhw_setpoint
    data:
      value: "50"
```

Oder um einen Modus anzupassen (`select.select_option`):
```yaml
action:
  - service: select.select_option
    target:
      entity_id: select.idm_navigator_circuit_a_mode
    data:
      option: "Eco"
```

### Direkter Modbus-Schreibzugriff (write_register)
Um über eine Automation ein beliebiges Register zu beschreiben (hier Register 1005 für den Betriebsmodus), verwende die Aktion `idm_heatpump.write_register`:
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
*Der Datentyp ist immer anzugeben, wenn das Register keine vorzeichenlose 16-Bit-Ganzzahl ist. Nicht-numerische Werte und Werte, die sich mit dem gewählten Datentyp nicht darstellen lassen, werden vor dem Netzwerk-I/O abgelehnt.*

### Wärmepumpe auf Standby bei Abwesenheit

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

### Urlaubsmodus der Wärmepumpe

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

### Fehler automatisch quittieren (mit Vorsicht verwenden!)

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

## Experimenteller KI-Anlagenberater (geplant)

Der experimentelle Berater liefert tägliche und wöchentliche Berichte sowie Erklärungen zur Anlagengesundheit und Effizienz. Er ist standardmäßig deaktiviert und bringt weder Werkzeuge zur Anlagensteuerung noch eine Sprachassistent-Anbindung mit. Ollama läuft lokal; v0.17.2-b10 ergänzt OpenAI- und Z.ai-Berichte mit separater Zustimmung und begrenzten Anfragekontingenten. Siehe [Einrichtung, Berichts-Aktionen, Datenabdeckung und Einschränkungen](Experimental-AI-Adviser).
