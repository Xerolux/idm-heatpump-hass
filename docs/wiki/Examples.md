# Beispiel-Automatisierungen

Hier findest du praktische Beispiele für den Einsatz der IDM Heatpump Integration.

---

## Urlaubsmodus automatisch aktivieren

Schaltet die Wärmepumpe in den Urlaubsmodus wenn du das Haus verlässt:

```yaml
automation:
  - alias: "Wärmepumpe: Urlaubsmodus bei Abwesenheit"
    trigger:
      - platform: state
        entity_id: person.ich
        to: "not_home"
        for:
          hours: 2
    action:
      - service: idm_heatpump_v2.set_system_mode
        data:
          mode: "urlaub"
```

---

## Normalbetrieb bei Heimkehr

```yaml
automation:
  - alias: "Wärmepumpe: Automatik bei Heimkehr"
    trigger:
      - platform: state
        entity_id: person.ich
        to: "home"
    action:
      - service: idm_heatpump_v2.set_system_mode
        data:
          mode: "automatik"
```

---

## Benachrichtigung bei Störung

Sendet eine Push-Benachrichtigung wenn eine Störung auftritt:

```yaml
automation:
  - alias: "Wärmepumpe: Störungsbenachrichtigung"
    trigger:
      - platform: state
        entity_id: binary_sensor.idm_heatpump_stoerung
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Wärmepumpe Störung"
          message: >
            IDM Störung aktiv. Fehlercode: {{ states('sensor.idm_heatpump_fehlercode') }}
```

---

## Warmwasser-Boost bei PV-Überschuss

Erhöht die Warmwasser-Solltemperatur wenn PV-Überschuss vorhanden ist:

```yaml
automation:
  - alias: "Wärmepumpe: WW-Boost bei PV-Überschuss"
    trigger:
      - platform: numeric_state
        entity_id: sensor.idm_heatpump_pv_surplus
        above: 2.0
        for:
          minutes: 15
    action:
      - service: number.set_value
        target:
          entity_id: number.idm_heatpump_warmwasser_solltemperatur
        data:
          value: 60
  - alias: "Wärmepumpe: WW-Boost beenden"
    trigger:
      - platform: numeric_state
        entity_id: sensor.idm_heatpump_pv_surplus
        below: 0.5
        for:
          minutes: 10
    action:
      - service: number.set_value
        target:
          entity_id: number.idm_heatpump_warmwasser_solltemperatur
        data:
          value: 48
```

---

## Heizkreis-Modus per Zeitplan

Wechselt den Heizkreis A täglich nach Zeitplan:

```yaml
automation:
  - alias: "Wärmepumpe: Heizkreis A – Zeitprogramm"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.idm_heatpump_betriebsart_hk_a
        data:
          option: "Eco"
  - alias: "Wärmepumpe: Heizkreis A – Normalbetrieb"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.idm_heatpump_betriebsart_hk_a
        data:
          option: "Normal"
```

---

## Energie-Dashboard

Für ein Energie-Dashboard in Home Assistant:

```yaml
# Tägliche Heizenergie (in configuration.yaml oder helpers)
sensor:
  - platform: integration
    source: sensor.idm_heatpump_aktuelle_leistung_heizen
    name: Tagesenergie Heizen
    unit_prefix: k
    round: 2
```

---

## Smart-Grid-Steuerung

Reagiert auf Smart-Grid-Status der Wärmepumpe:

```yaml
automation:
  - alias: "SmartGrid: Wärmepumpe Status auslesen"
    trigger:
      - platform: state
        entity_id: sensor.idm_heatpump_smart_grid_status
    action:
      - service: notify.persistent_notification
        data:
          title: "Smart Grid Status"
          message: "Aktueller Smart-Grid-Status: {{ states('sensor.idm_heatpump_smart_grid_status') }}"
```

---

## Fehler quittieren (manuell via Button-Helper)

```yaml
# button-helper in configuration.yaml
button:
  - platform: template
    buttons:
      idm_acknowledge_errors:
        friendly_name: "IDM Störungen quittieren"
        press:
          service: idm_heatpump_v2.acknowledge_errors
```
