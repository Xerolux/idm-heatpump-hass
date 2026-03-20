# Entities

## Sensoren

Die Integration erstellt uber 100 Sensor-Entities fur verschiedene Messwerte.

### System-Sensoren

| Entity | Beschreibung | Adresse |
|--------|-------------|---------|
| `sensor.{name}_outdoor_temp` | Aussentemperatur | 1000 |
| `sensor.{name}_flow_temp` | Vorlauftemperatur | 1001 |
| `sensor.{name}_return_temp` | Rucklauftemperatur | 1002 |
| `sensor.{name}_dhw_temp` | Warmwassertemperatur | 1003 |
| `sensor.{name}_dhw_setpoint` | Warmwasser-Sollwert | 1004 |
| `sensor.{name}_system_mode` | System-Betriebsmodus | 1005 |
| `sensor.{name}_system_state` | System-Zustand | 1006 |
| `sensor.{name}_heat_request` | Warmeanforderung | 1008 |
| `sensor.{name}_flow_rate` | Durchfluss | 1010 |
| `sensor.{name}_system_pressure` | Systemdruck | 1011 |
| `sensor.{name}_compressor_runtime` | Kompressor-Laufzeit | 1012 |
| `sensor.{name}_heat_quantity` | Warmemenge | 1013 |

### Heizkreis-Sensoren

Fur jeden aktivierten Heizkreis (A-G):

| Entity | Beschreibung |
|--------|-------------|
| `sensor.{name}_circuit_{x}_flow_temp` | Heizkreis-Vorlauftemperatur |
| `sensor.{name}_circuit_{x}_return_temp` | Heizkreis-Rucklauftemperatur |
| `sensor.{name}_circuit_{x}_setpoint` | Heizkreis-Sollwert |
| `sensor.{name}_circuit_{x}_mode` | Heizkreis-Modus |
| `sensor.{name}_circuit_{x}_state` | Heizkreis-Zustand |
| `sensor.{name}_circuit_{x}_curve` | Heizkurve |
| `sensor.{name}_circuit_{x}_room_temp` | Raumtemperatur |
| `sensor.{name}_circuit_{x}_mixer_pos` | Mischerstellung |

### Zonen-Sensoren

Fur jede aktivierte Zone und jeden Raum:

| Entity | Beschreibung |
|--------|-------------|
| `sensor.{name}_zone_{z}_room_{r}_temp` | Raumtemperatur |
| `sensor.{name}_zone_{z}_room_{r}_humidity` | Raumfeuchte |
| `sensor.{name}_zone_{z}_room_{r}_mode` | Raum-Modus |
| `sensor.{name}_zone_{z}_mode` | Zonen-Modus |

### Energie & Solar

| Entity | Beschreibung |
|--------|-------------|
| `sensor.{name}_energy_heating` | Energie Heizung |
| `sensor.{name}_energy_dhw` | Energie Warmwasser |
| `sensor.{name}_energy_total` | Energie gesamt |
| `sensor.{name}_solar_temp_in` | Solar-Temperatur Vorlauf |
| `sensor.{name}_solar_temp_out` | Solar-Temperatur Rucklauf |
| `sensor.{name}_pv_power` | PV-Leistung |
| `sensor.{name}_battery_soc` | Batterie-Ladezustand |

### Fehler-Sensoren

| Entity | Beschreibung |
|--------|-------------|
| `sensor.{name}_error_1` | Fehlercode 1 |
| `sensor.{name}_error_2` | Fehlercode 2 |
| `sensor.{name}_error_3` | Fehlercode 3 |

## Numbers

Beschreibbare Parameter mit Number-Entities:

### System-Numbers

| Entity | Beschreibung | Bereich |
|--------|-------------|---------|
| `number.{name}_dhw_setpoint` | Warmwasser-Sollwert | 10-60 C |
| `number.{name}_heating_limit` | Heizgrenze | -20-30 C |

### Heizkreis-Numbers

| Entity | Beschreibung |
|--------|-------------|
| `number.{name}_circuit_{x}_setpoint` | Heizkreis-Sollwert |
| `number.{name}_circuit_{x}_room_setpoint` | Raum-Sollwert |
| `number.{name}_circuit_{x}_curve_offset` | Heizkurven-Versatz |

## Selects

Auswahlfelder fur Betriebsmodi:

| Entity | Beschreibung | Optionen |
|--------|-------------|----------|
| `select.{name}_system_mode` | System-Betriebsmodus | Standby, Automatik, Abwesend, Urlaub, Nur Warmwasser, Nur Heizung |
| `select.{name}_circuit_{x}_mode` | Heizkreis-Modus | Automatik, Dauerbetrieb, Abschalt, Zeitprogramm |
| `select.{name}_zone_{z}_room_{r}_mode` | Raum-Modus | Komfort, Normal, Eco, Frostschutz |
| `select.{name}_solar_mode` | Solar-Modus | Automatik, Dauerbetrieb, Aus |

## Schalter (Switch)

| Entity | Beschreibung |
|--------|-------------|
| `switch.{name}_glt_heat_request` | GLT-Warmeanforderung |
| `switch.{name}_glt_cool_request` | GLT-Kuhlanforderung |

## Binary Sensors

| Entity | Beschreibung |
|--------|-------------|
| `binary_sensor.{name}_error_active` | Fehler aktiv |
| `binary_sensor.{name}_heating_active` | Heizung aktiv |
| `binary_sensor.{name}_dhw_active` | Warmwasser aktiv |
| `binary_sensor.{name}_compressor_running` | Kompressor lauft |
