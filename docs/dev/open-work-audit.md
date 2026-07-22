# Open Work Audit

Stand: 21.07.2026

Diese Prüfung trennt lokal erledigbare Arbeit von Punkten, die ohne reale
Anlagendaten oder ohne finalen Home-Assistant-Vertrag nicht sicher abgeschlossen
werden können. Ziel ist, keine Schätzung als fertiges Feature auszugeben und
keine riskante Modbus-Änderung vorzeitig produktiv zu verdrahten.

## Lokal erledigt

- Konservatives Entity-Profil für generierte technische und seltene Register.
- Automatisch erzeugter Home-Assistant-Metadatenkatalog für explizite Overlays.
- Vollständige Modbus-Registerreferenz bleibt über
  `scripts/generate_modbus_register_reference.py` an den gepinnten
  `idm-heatpump-api`-Stand gekoppelt.
- Feld-Diagnoseleitfaden und Issue-Vorlage für reale Anlagenmessungen.
- Nicht verdrahteter Modbus-Transportvertrag mit Endpoint-Validierung,
  Konfliktkennung und privacy-sicheren Diagnose-Helfern.
- Issue-Vorlage für die spätere Home-Assistant-Modbus-Modernisierung.

## Live-verifiziert (Navigator 2.0, read-only Modbus FC04)

Am 22.07.2026 wurden die nachfolgenden Punkte an einer realen Navigator-2.0-Anlage
per streng lesendem Modbus-Zugriff (Function Code 04, keine Schreibzugriffe,
keine EEPROM-Kandidaten) verifiziert. Die Verifikation bestätigt die
Code-Annahmen; sie ersetzt aber nicht die breitere Feld-Diagnose für andere
Navigator-Typen und Firmware-Stände.

### COP-Quellenregister

- `power_consumption_hp` (Adresse 4122, FLOAT) und `thermal_power_flow_sensor`
  (Adresse 4126, FLOAT) sind auf der realen Anlage vorhanden und liefern im
  Heiz-/Warmwasserbetrieb plausible Leistungen; im Standby beide exakt `0.0`.
- Genau dieser `0.0`-Fall wird durch die 50-W-Schranke in `calculated_sensors.py`
  abgedeckt: der COP-Sensor geht auf `unavailable`, statt einen unplausiblen
  Wert aus Null Elektroleistung zu berechnen.
- Der frühere Stub-Schlüssel `thermal_power` ist in der echten API nicht
  definiert; der COP-Pfad verwendet korrekt `thermal_power_flow_sensor`.

### Vorlauf-Sollwert

- Es existiert eine Familie pro Heizkreis berechneter Sollwert-Register
  `hc_{a..g}_setpoint_flow_temp` (Adresse 1378 ff., FLOAT, nur lesend). Das ist
  der von der Heizkurve berechnete, angeforderte Vorlauf-Sollwert je Heizkreis.
- Im Standby liefert der aktive Heizkreis `0.0`, nicht aktivierte Heizkreise
  liefern `-1.0`. Beides sind Sentinel-Werte, die über den zentralen
  `is_register_unused`-Filter korrekt als `unavailable` dekodiert werden.
- Ergänzend gibt es konfigurierbare Sollwert-Register (`hc_*_setpoint_flow_constant`,
  `hc_*_heating_curve`, `hc_*_heating_limit`). Damit ist das Vorlauf-Abweichungs-
  Feature technisch umsetzbar; vor einer Veröffentlichung muss noch geklärt
  werden, welcher Sollwert der „angeforderte" ist und wie er pro Heizkreis
  zugeordnet wird. Die Registervariablen sind verifiziert, das Feature bleibt
  daher als „implementierbar, aber nicht freigegeben" eingestuft.

### Binary- und Status-Sentinelwerte

- Die drei Sentinel-Varianten wurden live beobachtet und passen exakt zur
  `is_register_unused`-Logik in `coordinator.py`:
  - `255` (UCHAR): nicht vorhandene Verdichter (`compressor_status_2..4`),
    nicht konfigurierte Heizkreise (`hc_b_active_mode`).
  - `-1` (INT16): nicht vorhandene Pumpen (`charging_pump_status`,
    `brine_pump_status`, `heat_source_pump_status`).
  - `65535` (UINT16): nicht vorhandene Ventile (`valve_hc_heat_cool`,
    `valve_storage_heat_cool`).
- `compressor_status_1` lieferte `0` (Verdichter aus) – plausible aktive
  Zustände sind damit unterscheidbar von „nicht vorhanden".
- `evu_lock = 1 -> Not Locked` bestätigt die inverse Active-High-Logik
  (`0 = Locked`, `1 = Not Locked`), die in den Enum-Maps korrekt hinterlegt ist.
- Die `idm-heatpump-api` definiert für diese Register aktuell keine
  `sentinel_values`; die Integration erkennt die Sentinels daher eigenständig
  über den numerischen Filter. Das ist ein bekannter Folge-Punkt für die API.

### Web-Zugriff (Navigator 2.0)

- Der Port-80-HTTP-Endpunkt antwortet. Die Login-Erkennung des
  `IdmNavigator20WebClient` schlägt jedoch mit `IdmWebAuthenticationError`
  fehl, wenn die PIN abgelehnt wird oder die Login-Form nicht die erwartete
  Struktur hat. Der Web-Only-Pfad bleibt daher von der PIN-Qualität und der
  Firmware-Oberfläche abhängig; Modbus ist der zuverlässigere Kanal.

## Extern blockiert

### Reale Anlagendaten

Diese Punkte dürfen erst als erledigt markiert werden, wenn echte Daten aus
mindestens einem passenden System vorliegen:

- COP-Verifikation für Warmwasser, Abtauen und unterschiedliche
  Navigator-Firmwares.
- Eindeutige Zuordnung des tatsächlich angeforderten
  Wärmepumpen-Vorlauf-Sollwerts.
- Binary-Register-Verifikation auf Navigator 10 und Navigator 2.0,
  einschließlich Active-Low- und Sonderwerten.
- Lasttests mit maximaler Zahl an Heizkreisen, Zonen und Räumen.

Benötigte Artefakte sind in der Field-Diagnostics-Vorlage und im
Field-Diagnostics-Guide beschrieben. Ohne diese Daten bleibt die sichere
Entscheidung: nicht veröffentlichen, nicht schätzen und keine Schreibpfade
ändern.

### Home Assistant Modbus-Vertrag

Diese Punkte bleiben blockiert, bis Home Assistant den finalen offiziellen
Shared-Connection-Vertrag veröffentlicht und Custom Integrations ihn stabil
nutzen dürfen:

- Adapter zwischen Home-Assistant-Connection-Objekt und `IdmModbusTransport`.
- Runtime-Option für einen optionalen Shared-Connection-Transport.
- Diagnoseexport der tatsächlich genutzten Transportquelle.
- Migrationspfad ohne neue Unique IDs und ohne neuen Schreibpfad.

Bis dahin bleibt die Integration beim bestehenden, getesteten
`idm-heatpump-api`-/Pymodbus-Pfad.

## Entscheidungsregel

Ein Punkt darf nur von „blockiert“ nach „erledigt“ wechseln, wenn mindestens
eines erfüllt ist:

1. Die benötigten realen Messdaten liegen als redigierter Diagnoseexport und
   Rohdatenserie vor.
2. Die finale Home-Assistant-Dokumentation ist verlinkt und der Adapter ist
   feature-gated implementiert.
3. Ein Test oder Generator belegt reproduzierbar, dass die Dokumentation mit dem
   Code übereinstimmt.
