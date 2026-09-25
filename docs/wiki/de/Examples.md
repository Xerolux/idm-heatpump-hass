# Beispiel-Automationen

Hier findest du praktische Beispiele für den Einsatz der IDM-Wärmepumpen-Integration, insbesondere wie du Werte über Automationen schreibst.

---

## Werte über Automationen schreiben (Überblick)

In Home Assistant werden schreibbare Werte der Wärmepumpe als **Entitäten** dargestellt. Um diese Werte in Automationen zu ändern, verwendest du nicht `idm_heatpump.write_register`, sondern die Standard-Aktionen (Services) von Home Assistant:

- Für Temperaturen, Heizkurven oder Sollwerte (Typ `number`): Aktion `number.set_value`
- Für Betriebsmodi (Typ `select`): Aktion `select.select_option`
- Für Schalter (Typ `switch`): Aktion `switch.turn_on` oder `switch.turn_off`

**Alternative (fortgeschritten):** Existiert für ein Register keine Entität, kannst du die Aktion `idm_heatpump.write_register` verwenden (siehe [Aktionen (Services) – Referenz](Services)).

Hier sind einige konkrete Anwendungsfälle:

---

## Urlaubsmodus automatisch aktivieren

Schaltet die Wärmepumpe in den Urlaubsmodus, sobald du das Haus verlässt:

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

## Normalbetrieb bei Rückkehr

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

## Störungsmeldung

Sendet eine Push-Benachrichtigung, wenn eine Störung auftritt:

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

## Energiemanagement-Messwerte über die GLT-Aktion weiterleiten

Die Aktion `set_external_power` leitet jede verfügbare Teilmenge der PV-, Haus- und
Batteriemesswerte weiter, ohne von generierten `number`-Entitäten abzuhängen. Die
Integration behält Datentyp-, Registerverfügbarkeits- und Schreibsicherheitsprüfungen
im Schreibpfad bei. Ersetze die Beispiel-Sensor-IDs durch deine tatsächlichen IDs. Lasse
diese Automation nicht laufen, wenn ein Wechselrichter, ein E3DC, ein Smartfox oder ein
anderer Regler bereits dieselben Register schreibt.

```yaml
automation:
  - alias: "Heat pump: Forward external power measurements"
    mode: restart
    trigger:
      - platform: state
        entity_id: sensor.house_pv_surplus_kw
    action:
      - action: idm_heatpump.set_external_power
        data:
          pv_surplus: "{{ states('sensor.house_pv_surplus_kw') }}"
          pv_production: "{{ states('sensor.house_pv_production_kw') }}"
          house_consumption: "{{ states('sensor.house_consumption_kw') }}"
```

Ungültige, nicht verfügbare, NaN- oder unendliche Eingaben lehnt die Aktion ab. Kann ein
Quell-Sensor unabhängig davon nicht verfügbar sein, lasse das Feld in einem separaten
Aufruf weg oder baue die Aktionsdaten dynamisch auf, statt es durch null zu ersetzen.
Mehrere Felder werden vor dem Schreiben validiert, aber die einzelnen
Modbus-Schreibvorgänge sind nicht atomar; nach einem Verbindungsfehler sollte das nächste
zyklische Update das vollständige aktuelle Set erneut senden. Siehe
[Aktionen (Services) – Referenz](Services#set-external-power).

Bei welchen Schwellenwerten eine Wärmepumpe startet, stoppt oder moduliert, hängt vom
genauen Modell, der Firmware, den Temperaturen und der Reglerkonfiguration ab. Ein fester
Schwellenwert von 2–3 kW ist daher kein universeller Standard.

---

## Warmwasser-Ladung mit expliziten Sicherheitsstopps anfordern

Für eine temporäre externe Anforderung verwende bevorzugt den generierten Schalter für
Register 1712, statt wiederholt einen EEPROM-gestützten Warmwasser-Sollwert zu ändern.
Die unten stehenden Schwellenwerte sind nur Beispiele und müssen für die tatsächliche
hydraulische Anlage mit dem Installateur abgestimmt werden.

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

Externe Anforderungen sollten immer Stopp-Pfade für Temperatur, nachlassenden Überschuss
und maximale Laufzeit haben. Prüfe das Verhalten mit dem Navigator-GLT-Monitor, bevor du
die Automation unbeaufsichtigt laufen lässt.

---

## PV-Überschussbetrieb als Zustand (Prognose-Helfer)

Der abgeleitete diagnostische **PV-Überschussbetrieb**
(`binary_sensor.<device>_pv_uberschussbetrieb`; siehe *Entitäten → PV /
Energiemanagement → PV-Überschussbetrieb*) ist `on`, solange dem Regler ein Überschuss
signalisiert wird *und* die Wärmepumpe elektrische Leistung aufnimmt. Er ersetzt
handgeschriebene Template-Logik, die PV- und Netz-Sensoren kombiniert, z. B. für
Energie-Prognose-Helfer:

```yaml
template:
  - sensor:
      - name: "Heat pump PV surplus consumption"
        unit_of_measurement: "kW"
        state: >-
          {% if is_state('binary_sensor.idm_heatpump_pv_uberschussbetrieb', 'on') %}
            {{ states('sensor.idm_heatpump_power_consumption_hp') | float(0) }}
          {% else %}
            0
          {% endif %}
```

Bei Anlagen, bei denen `pv_surplus` hinter dem Abzweig der Wärmepumpe gemessen wird und
während des Ladens gegen null fällt, speise stattdessen das SG-Ready-Signal *Supergreen*
in die Wärmepumpe ein (oder verlasse dich auf die Quelle `smart_grid_status`, die der
diagnostische Sensor bereits auswertet), anstatt auf den schrumpfenden Überschusswert zu
setzen.

---

## EEPROM-gestützter Warmwasser-Sollwert-Boost (sparsam einsetzen)

Diese Alternative ändert einen persistenten Sollwert. Sie eignet sich nur für gelegentliche
Moduswechsel, nicht zum schnellen Nachführen schwankender PV-Leistung:

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

## Heizkreis-Modus nach Zeitplan

Schaltet Heizkreis A täglich nach Zeitplan um:

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

## Energie-Dashboard

Verwende native IDM-Energiesensoren, wenn dein Gerät sie mit stabilen Werten liefert. Stellt
das Gerät nur Leistungen bereit, verwende Home-Assistant-Helfer, um Leistung über die Zeit
zu integrieren, statt einen Leistungssensor wie einen nativen Energiezähler zu behandeln.

```yaml
# Daily heating energy (in configuration.yaml or helpers)
sensor:
  - platform: integration
    source: sensor.idm_heatpump_current_heating_power
    name: Daily energy heating
    unit_prefix: k
    round: 2
```

Bevorzuge für Dashboard-Karten Sensoren mit `kWh`- und `total_increasing`-Semantik. Liefert
ein Modell kein verlässliches Gesamtenergie-Register, lege einen HA-Integrations-Helfer an
und benenne ihn deutlich als berechneten Wert.

---

## Smart-Grid-Steuerung

Reagiert auf den Smart-Grid-Status der Wärmepumpe:

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

## Temporäre Leistungsbegrenzung

Die Register der Leistungsbegrenzung sind modellabhängig und standardmäßig deaktiviert.
Aktiviere und automatisiere sie erst, nachdem du die Unterstützung für dein genaues Modell
und deine Firmware bestätigt hast.

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

## Fehler quittieren (manuell per Button-Helfer)

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
