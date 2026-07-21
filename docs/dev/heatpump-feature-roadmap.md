# IDM Heatpump Feature Roadmap

Stand: 21.07.2026

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
- **Modbus-Zukunft offenhalten:** Die aktuelle Pymodbus-basierte Verbindung
  bleibt stabil; ein späterer `modbus-connection`-Adapter wird erst nach einem
  finalen Home-Assistant-Vertrag umgesetzt.

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
- [ ] Heizkurven-UX erst nach Registerverifikation:
  - pro Heizkreis sauber gruppiert,
  - klare Min/Max/Step-Werte,
  - als Expertenwerte deaktiviert, wenn das Risiko für Fehlbedienung zu hoch ist.

### Phase 3 – Architektur und Home-Assistant-Modbus-Zukunft

Home Assistant hat im Juli 2026 eine Modernisierung der Modbus-Anbindung
angekündigt und kurz danach darauf hingewiesen, dass der Integrationsvertrag
noch überarbeitet wird. Deshalb wird aktuell keine harte Abhängigkeit auf eine
neue HA-seitige Modbus-Verbindungsintegration eingeführt.

- [x] Aktuelle Integration bleibt über `idm-heatpump-api` und den zentralen
  Coordinator gekapselt.
- [x] Plattformdateien führen keine direkten Modbus-Transporte ein.
- [x] Manifest pinnt die getestete API-Version reproduzierbar.
- [x] Minimalen, noch nicht eingebundenen Transportvertrag für spätere Adapter
  dokumentieren und im Integrationscode ablegen.
- [ ] `idm-heatpump-api` weiter transportneutral strukturieren:
  - Registermodell,
  - Encoding/Decoding,
  - Batchplanung,
  - Fehlerklassifikation,
  - Transportadapter.
- [ ] Optionalen `modbus-connection`-Transportadapter erst implementieren, wenn die
  Home-Assistant-Schnittstelle final dokumentiert ist.
- [ ] Migration bestehender Nutzer separat planen, falls ein Shared-Connection-
  Modell später stabil empfohlen wird.

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

Ein Sensor für `Ist-Vorlauf minus angeforderter Vorlauf` benötigt zuerst ein
eindeutiges Register für den tatsächlich von der Wärmepumpe angeforderten
Vorlauf-Sollwert. Heizkurven-, Mischer- und Maximalwerte dürfen nicht vermischt
werden.

### Binärregister-Semantik

Binärregister müssen weiter gegen reale Navigator-2.0-, Navigator-10- und
Navigator-Pro-Anlagen geprüft werden, insbesondere bei Active-Low-, Sentinel-
oder firmwareabhängigen Sonderwerten.

## Nächste konkrete TODOs

1. API-weite Entity-Dokumentation auf Basis des neuen Metadatenkatalogs ausbauen.
2. Reale Diagnoseexports für Vorlauf-Abweichung und Binärregister über die
   Field-Diagnostics-Vorlage sammeln.
3. Den bestehenden Modbus-Issue mit der vorbereiteten Issue-Vorlage pflegen,
   bis die offenen HA-Entscheidungen final sind.
4. `idm-heatpump-api` auf Transportgrenzen auditieren und einen späteren
   Adapterpunkt dokumentieren.
