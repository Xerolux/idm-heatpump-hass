# IDM Heatpump Feature Roadmap

Stand: 18.08.2026

Dieses Dokument bündelt die nächsten sicheren und sinnvollen Arbeitspakete für
`idm-heatpump-hass`. Der Fokus liegt auf lokaler Funktion, nachvollziehbarem
Verhalten, Schutz der Anlage und einer Architektur, die spätere Home-Assistant-
Änderungen beim Modbus-Transport aufnehmen kann.

## Leitprinzipien

- **Lokal zuerst:** Keine Cloud-Abhängigkeiten und keine externen Laufzeit-APIs.
- **Sicher vor komfortabel:** Jede schreibende Funktion braucht klare Register,
  Grenzwerte, Wiederherstellung und Tests.
- **Keine geschätzten Messwerte als Fakten:** Abgeleitete Werte werden klar als
  Analyse- oder berechnete Sensoren gekennzeichnet.
- **Register gehören in die API:** Gerätewissen, Datentypen und Adressen bleiben
  in `idm-heatpump-api` oder in zentralen Adapter-/Konstantenmodulen, nicht in
  Plattformdateien.
- **Bestehende Installationen schützen:** Unique IDs, Entity-Registry-Entscheide
  und Nutzeroptionen bleiben migrationssicher; Details stehen im
  Entity-Registry-Migrationsvertrag.
- **Transportgrenzen beibehalten:** Der direkte Socket läuft über den
  implementierten `modbus-connection`-/tmodbus-Adapter. Gerätelogik bleibt in
  `idm-heatpump-api`; zentrales Entry-übergreifendes Sharing wird erst mit
  einem stabilen Home-Assistant-Vertrag ergänzt.

## Phasenplan

### Phase 1 – Nutzwert ohne Anlagenrisiko

Diese Arbeitspakete sind bevorzugt, weil sie hauptsächlich dokumentieren,
visualisieren oder vorhandene Analysewerte sichtbar machen.

- [x] Betriebsanalyse als Sensoren bereitstellen:
  - erfasste Wärmepumpentakte,
  - heutige und kurzzeitige Takte,
  - aktuelle, letzte und durchschnittliche Taktlaufzeit,
  - Abtauzähler,
  - Betriebsanteile.
- [x] Kurz-Takt-Warnung als Problemsensor bereitstellen.
- [x] Navigator-Webzustände als echte Binary-Sensoren bereitstellen.
- [x] Device-Hierarchy für große Anlagen optional bereitstellen.
- [x] Entity-bewusstes Polling verwenden, damit nicht aktivierte Expertenwerte
  nicht unnötig gelesen werden.
- [x] Dashboard-Beispiele für Übersicht, Warmwasser, Energie und Diagnose
  als getrennte, konservative Startpunkte ergänzen.
- [x] Entity-Katalog konsequent in Basis, Erweitert und Diagnose/Experte
  klassifizieren; API-weite Erweiterung bleibt dokumentiert offen.
- [x] Entity-Metadatenkatalog automatisiert aus HA-Metadaten erzeugen;
  API-weite Entity-Dokumentation bleibt als nächster Ausbau offen.

### Phase 2 – Komfortfunktionen mit Schutzmechanismen

Schreibende Komfortfunktionen sind nur zulässig, wenn sie deterministisch,
begrenzt und wiederherstellbar sind.

- [x] Sicherer Warmwasser-Boost:
  - Start nur bei vorhandenen und schreibbaren Registern,
  - Zieltemperatur- und Laufzeitgrenzen,
  - Persistenz vor dem ersten Schreibvorgang,
  - Rollback bei Startfehlern,
  - Wiederherstellung bei Abbruch, Timeout, Zielerreichung und Neustart.
- [x] Raumtemperatur-Weiterleitung an GLT-Register:
  - nur konfigurierte HA-Sensoren,
  - Grenzwertprüfung aus Registermetadaten,
  - Toleranz gegen Schreibrauschen,
  - zyklische und ereignisbasierte Aktualisierung.
- [x] Dokumentierte PV-/GLT-Beispiele mit Ownership-Hinweis und
  Schreibschutzempfehlungen.
- [ ] PV-/Smart-Grid-Assistent erst nach zusätzlicher Sicherheitsprüfung:
  - eindeutiger Registerbesitz,
  - Mindestlaufzeiten,
  - Hysterese,
  - Schreibintervallbegrenzung,
  - keine Konkurrenz zu vorhandenen Energie-Managern.
- [x] Heizkurven-UX:
  - Min/Max liefert `idm-heatpump-api` je Register (`min_val`/`max_val`) und
    wird unverändert übernommen; die Integration dupliziert keine Gerätegrenzen.
  - Schrittweite der Heizkurve auf 0,1 korrigiert. Als FLOAT-Register bekam sie
    die Standardschrittweite 0,5, obwohl ihr Bereich 0,1–3,5 beträgt — übliche
    Werte wie 0,3 lagen zwischen zwei Schritten.
  - `heating_curve`, `parallel_shift`, `setpoint_flow_constant` und
    `setpoint_flow_cooling` entstehen für neue Installationen deaktiviert.
    Bestehende Entitäten bleiben unverändert.
  - Gruppierung über ein Dashboard-Beispiel je Heizkreis
    (`docs/examples/dashboard-idm-heating-circuit.yaml`); die Geräteseite in
    Home Assistant sortiert alphabetisch und kennt keine Untergruppen.

### Phase 3 – Architektur und Home-Assistant-Modbus-Zukunft

Der lokale Adapter ist umgesetzt und der direkte Socket verwendet tmodbus.
Home Assistants zentraler Vertrag für Entry-übergreifendes Sharing steht Custom
Integrations dagegen weiterhin nicht stabil zur Verfügung. Diese beiden Ebenen
dürfen in Planung und Diagnose nicht miteinander verwechselt werden.

- [x] Aktuelle Integration bleibt über `idm-heatpump-api` und den zentralen
  Coordinator gekapselt.
- [x] Plattformdateien führen keine direkten Modbus-Transporte ein.
- [x] Manifest pinnt die getestete API-Version reproduzierbar.
- [x] Backend-neutralen Transportvertrag mit FC03, FC04, FC16,
  Endpoint-Validierung und redigierten Capabilities implementieren.
- [x] `IdmModbusConnectionClient` als produktiven Adapter verdrahten und rohe
  I/O über `modbus-connection==4.8.1` sowie `tmodbus[async-serial]==0.5.1`
  ausführen. Der Pfad wird erstmals mit `0.11.0-beta.1` ausgeliefert.
- [x] `idm-heatpump-api[web]==1.0.1` für Gerätelogik und
  `pymodbus>=3.12.1,<4.0` vorübergehend für dessen Imports/Fehlervertrag
  beibehalten; Pymodbus besitzt nicht den direkten Socket.
- [x] Pro Entry privaten Socket-Besitz und fehlendes zentrales Sharing als
  `owns_socket=True` / `supports_shared_connection=False` diagnostizieren.
- [ ] Den neuen tmodbus-Pfad read-only an realer Navigator-Hardware validieren;
  keine Schreibtests ohne ausdrückliche Freigabe.
- [x] `idm-heatpump-api` transportneutral strukturieren und einen
  öffentlichen I/O-Vertrag bereitstellen: seit `1.0.1` exportiert die API das
  zur Laufzeit prüfbare Protocol `IdmModbusTransport`, und `IdmModbusClient`
  nimmt den Transport über den öffentlichen Parameter `transport=` entgegen.
  Registermodell, Encoding/Decoding, Batchplanung und Fehlerklassifikation
  bleiben in der API.
- [ ] Den Pymodbus-Kompatibilitätspin entfernen. Er hängt nicht mehr am
  Transportvertrag, sondern allein daran, dass `idm_heatpump.client` `pymodbus`
  auf Modulebene importiert — unabhängig vom injizierten Transport.
- [ ] Einen zusätzlichen zentralen Home-Assistant-Connection-Provider erst
  implementieren, wenn die Schnittstelle für Custom Integrations stabil
  dokumentiert ist.
- [ ] Migration bestehender Nutzer separat planen, falls ein zentrales
  Shared-Connection-Modell später stabil empfohlen wird.

## Sicherheitsregeln für alle neuen Schreibfunktionen

Jede neue Schreibfunktion muss folgende Kriterien erfüllen:

1. Das Register ist bekannt, schreibbar und zentral definiert.
2. Werte werden gegen Register-Metadaten oder konservative Integrationsgrenzen
   validiert.
3. Schnell schwankende Eingangswerte werden gedrosselt oder hysteresegeführt.
4. Bei temporären Betriebsänderungen wird der vorherige Zustand vorab
   persistent gespeichert.
5. Fehler führen zu klaren Home-Assistant-Fehlern, nicht zu stillen Abbrüchen.
6. Tests decken Erfolg, ungültige Werte, Kommunikationsfehler, Wiederherstellung
   und Neustart-Recovery ab.
7. Die Dokumentation erklärt Nutzen, Grenzen und mögliche Anlagenwirkungen.

## Offene Datenpunkte vor weiteren Messwerten

### Momentaner COP

Der momentane COP ist umgesetzt, sobald zeitgleiche elektrische und thermische
Leistungsregister verfügbar und nicht als unbenutzt markiert sind. Der Sensor
bleibt bewusst defensiv: Bei Stillstand, fehlenden Quellen oder nicht
belastbarer Kleinstleistung wird kein Wert veröffentlicht.

### Vorlauf-Abweichung

Auf **Heizkreisebene** ist die Abweichung umgesetzt: `hc_{x}_flow_temp` minus
`hc_{x}_setpoint_flow_temp` vergleicht zwei Register desselben Heizkreises, und
der von der Heizkurve berechnete Sollwert ist für diesen Heizkreis eindeutig.
Sentinelwerte (`0.0` im Stillstand, `-1.0` bei nicht konfiguriertem Heizkreis)
laufen über den zentralen `is_register_unused`-Filter, der Sensor meldet dann
`unavailable`.

Auf **Wärmepumpenebene** bleibt der Punkt offen: Ein Sensor für
`Ist-Vorlauf minus angeforderter Vorlauf` benötigt zuerst ein eindeutiges
Register für den tatsächlich von der Wärmepumpe angeforderten Vorlauf-Sollwert.
Heizkurven-, Mischer- und Maximalwerte dürfen nicht vermischt werden.

### Binärregister-Semantik

Binärregister müssen weiter gegen reale Navigator-2.0-, Navigator-10- und
Navigator-Pro-Anlagen geprüft werden, insbesondere bei Active-Low-, Sentinel-
oder firmwareabhängigen Sonderwerten.

## Nächste konkrete TODOs

1. Raumtemperatur je Heizkreis im Web-Supplement klären: `idm-heatpump-api`
   mappt nur `B61` auf `room_temperature_HK_A`. Über Modbus existiert
   `hc_{a..g}_room_temp` für alle Heizkreise, der Punkt betrifft daher allein
   den Web-only-Modus. Ob `B62`–`B67` für die übrigen Heizkreise existieren,
   ist unbestätigt und auf einer Anlage mit mehreren Heizkreisen messbar.
2. Reale Diagnoseexports für Vorlauf-Abweichung und Binärregister über die
   Field-Diagnostics-Vorlage sammeln.
3. Den neuen tmodbus-Pfad für Setup, FC03, FC04, Verbindungsabbruch und
   Reconnect read-only an realer Hardware validieren.
4. Den Modulimport von `pymodbus` in `idm_heatpump.client` optional machen
   und erst danach den Kompatibilitätspin entfernen. Der öffentliche
   Transportvertrag steht seit API `1.0.1` und wird bereits genutzt.
5. Den bestehenden Modbus-Issue für die offene zentrale Home-Assistant-
   Shared-Connection sowie eine migrationssichere Provider-Implementierung
   pflegen.
