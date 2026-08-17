# Open Work Audit

Stand: 04.08.2026

Diese Prüfung trennt lokal erledigbare Arbeit von Punkten, die ohne reale
Anlagendaten oder ohne zentralen Home-Assistant-Shared-Connection-Vertrag nicht
sicher abgeschlossen werden können. Der lokale tmodbus-Adapter ist produktiv
verdrahtet; Ziel bleibt, keine Schätzung oder noch nicht hardwarevalidierte
Transporteigenschaft als abgeschlossen auszugeben.

## Lokal erledigt

- Konservatives Entity-Profil für generierte technische und seltene Register.
- Automatisch erzeugter Home-Assistant-Metadatenkatalog für explizite Overlays.
- Vollständige Modbus-Registerreferenz bleibt über
  `scripts/generate_modbus_register_reference.py` an den gepinnten
  `idm-heatpump-api`-Stand gekoppelt.
- Feld-Diagnoseleitfaden und Issue-Vorlage für reale Anlagenmessungen.
- Verdrahteter `IdmModbusConnectionClient` mit backend-neutralem
  Modbus-Transportvertrag, Endpoint-Validierung, Konfliktkennung und
  privacy-sicheren Diagnose-Helfern.
- Direkter Socket über `modbus-connection==4.0.0a3` und den separat
  gepinnten Backend-Stand `tmodbus==0.5.0`; die erste ausliefernde
  Integrationsversion ist `0.11.0-beta.1`.
- API-Gerätelogik bleibt bei `idm-heatpump-api[web]==0.9.1`. Der
  Pymodbus-Pin bleibt nur vorübergehend bestehen, weil diese API-Version ihn
  weiterhin importiert; die physische Verbindung gehört tmodbus.
- Diagnoseexport für Transportquelle, Socket-Besitz, Verbindungsstatus,
  fehlendes zentrales Sharing sowie alle Laufzeitversionen.
- Issue-Vorlage für read-only Hardware-Verifikation und eine spätere zentrale
  Home-Assistant-Modbus-Verbindung.
- Synthetischer Skalierungstest für die maximal ausgebaute Anlage
  (`tests/test_scale_load.py`): 7 Heizkreise, 10 Zonen à 8 Räume, Kaskade aktiv.
  Er sichert Registeranzahl, Eindeutigkeit von Namen und Adressen,
  Unique-ID-Kollisionen je Plattform, die Vollständigkeit der
  Coordinator-Indizes sowie Aufbau- und Auswertungslaufzeit ab. Das ist die
  lokal beweisbare Hälfte des Lasttest-Punkts; die Wirkung auf reale
  Modbus-Antwortzeiten bleibt weiterhin offen (siehe unten).
- Automatisierter Datenschutz- und Vollständigkeitstest für den Diagnose-Export
  (`tests/test_diagnostics_privacy.py`). Host, Web-Host, PIN, myIDM-ID,
  Seriennummer und Fehlertexte mit eingebetteten Verbindungsangaben dürfen im
  serialisierten Export nicht vorkommen; die für den Support nötigen Abschnitte
  müssen erhalten bleiben. Ersetzt die bisher wiederkehrende manuelle Prüfung.

## Live-verifiziert (Navigator 10, read-only Modbus FC04 + Web-Supplement)

Am 22.07.2026 wurden die nachfolgenden Punkte an einer realen Navigator-10-Anlage
(Heizkreis A, Solar/ISC/PV erkannt, Software `NAV10_20.24-880-g265e09c4a`)
verifiziert – per streng lesendem Modbus-Zugriff (Function Code 04, keine
Schreibzugriffe, keine EEPROM-Kandidaten) und zusätzlich über das lokale
Navigator-10-Web-Supplement (Port 61220, WebSocket-Authentifizierung per PIN).
Die Verifikation bestätigt die Code-Annahmen; sie ersetzt aber nicht die
breitere Feld-Diagnose für andere Navigator-Typen und Firmware-Stände.

> Diese Messung fand vor der Umstellung des direkten Sockets auf tmodbus statt.
> Sie bestätigt Registerdefinitionen und Gerätelogik, ist aber keine
> Hardware-Verifikation des neuen `modbus-connection`-/tmodbus-Pfads.

### Modellerkennung

- `IdmModbusClient.detect_model()` erkennt die Anlage korrekt als
  `Navigator 10` (Heizkreis A aktiv, Solar/ISC/PV = True, keine Kaskade).
  Die Unterscheidung läuft primär über das Navigator-10-spezifische Register
  `power_limit_hp` (Adresse 4108), das auf der Anlage antwortet.
- `client.model_info` ist eine **Property** der API (kein Callable); die
  Integration in `_detect_model_info()` greift korrekt auf die erkennten
  Attribute zu und behandelt fehlende Firmware defensiv.

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

### Web-Supplement (Navigator 10)

- Der Navigator-10-Web-Client (`IdmNavigator10WebClient`) spricht WebSocket auf
  Port 61220. Login per PIN, `connect()` und `read_data()` wurden gegen die
  reale Anlage erfolgreich durchlaufen; die `async_read_web_supplement`-Logik
  der Integration wählt für ein als Navigator 10 erkanntes Gerät diesen Client
  zuerst und fällt nur bei variantenbedingten Fehlern auf den Nav-2.0-HTTP-Client
  zurück.
- `read_data()` lieferte 60 Werte, darunter reine Web-Größen, die über Modbus
  nicht verfügbar sind: Heißgastemperatur, Kondensations-/Verdampfungsdruck,
  Verdichter-Heizung, Platinentemperatur, Laufzeiten (Heizen/Warmwasser/Abtauen/
  Stufe 1/2. Wärmeerzeuger), Schaltzyklen, myIDM-ID und die Software-Version.
- Die Software-Version (`software_version`-Feld im Web-Datenmodell) ist die
  zuverlässige Quelle für die Firmware, da das Modbus-Register 4120 auf dieser
  Firmware nicht verlässlich auslesbar ist (wird daher in
  `_detect_model_info` mit `read_firmware=False` übersprungen).

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
- Lasttests mit maximaler Zahl an Heizkreisen, Zonen und Räumen **an realer
  Hardware**. Die Skalierung der Integration selbst ist lokal abgesichert
  (`tests/test_scale_load.py`); was ein Test ohne Anlage nicht zeigen kann, ist
  das Verhalten der Regelung unter der resultierenden Anfragelast: reale
  Antwortzeiten, Batch-Verhalten und Timeout-Grenzen.
- Read-only Transporttest des neuen tmodbus-Pfads an realer Hardware: Setup,
  FC03, FC04, Verbindungsabbruch und Reconnect. Schreibtests bleiben ohne
  ausdrückliche Freigabe ausgeschlossen.

Benötigte Artefakte sind in der Field-Diagnostics-Vorlage und im
Field-Diagnostics-Guide beschrieben. Ohne diese Daten bleibt die sichere
Entscheidung: nicht veröffentlichen, nicht schätzen und keine Schreibpfade
ändern.

### Home Assistant Shared-Connection-Vertrag

Der lokale Adapter ist umgesetzt. Nur die folgenden zentralen Sharing-Punkte
bleiben blockiert, bis Home Assistant einen stabilen Vertrag für Custom
Integrations veröffentlicht:

Derzeit gibt es keinen finalen offiziellen
Shared-Connection-Vertrag, auf den dieser Provider sicher aufbauen könnte.

- Provider zwischen einem künftigen zentralen Home-Assistant-Connection-Objekt
  und `IdmModbusTransport`.
- Ownership- und Lifecycle-Regeln für mehrere Config-Entries.
- Migrationspfad ohne neue Unique IDs und ohne neuen Schreibpfad.
- Erst ein real integrierter zentraler Provider darf
  `supports_shared_connection=True` und `owns_socket=False` melden.

Bis dahin besitzt jede Config-Entry ihren direkten tmodbus-Socket und meldet
`supports_shared_connection=False`. Es gibt keine Transportoption und keinen
zweiten Pymodbus-Socketpfad.

### API-Entkopplung

`idm-heatpump-api` 0.9.1 stellt noch keinen öffentlichen transportneutralen
Client-Vertrag bereit und importiert Pymodbus. Die Integration überbrückt das
gezielt über geschützte Raw-I/O-Hooks. Ein späteres API-Release soll diesen
Adapterpunkt öffentlich machen; erst nach Kompatibilitätsprüfung darf der
temporäre Pymodbus-Pin entfallen.

## Entscheidungsregel

Ein Punkt darf nur von „blockiert“ nach „erledigt“ wechseln, wenn mindestens
eines erfüllt ist:

1. Die benötigten realen Messdaten liegen als redigierter Diagnoseexport und
   Rohdatenserie vor.
2. Die finale Home-Assistant-Dokumentation ist verlinkt und ein zentraler
   Shared-Connection-Provider ist getrennt vom bereits vorhandenen lokalen
   tmodbus-Adapter implementiert.
3. Ein Test oder Generator belegt reproduzierbar, dass die Dokumentation mit dem
   Code übereinstimmt.
