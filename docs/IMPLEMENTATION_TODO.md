# IDM Heatpump – offene TODO-Liste

Stand: 21.07.2026

Die großen strategischen Optimierungsblöcke sind umgesetzt. Dieses
Dokument enthält nur noch Punkte, die tatsächlich offen, datenabhängig oder durch
einen externen Home-Assistant-Entscheid blockiert sind.


## Design-Dokument

Die detaillierte, sicherheitsorientierte Roadmap steht in
[`docs/dev/heatpump-feature-roadmap.md`](dev/heatpump-feature-roadmap.md). Dieses
TODO-Dokument bleibt die kurze operative Liste; das Design-Dokument beschreibt
Phasen, Sicherheitsregeln und blockierte Datenpunkte.

Die aktuelle Prüfung der noch offenen Arbeit steht in
[`docs/dev/open-work-audit.md`](dev/open-work-audit.md). Dort ist getrennt, was
lokal erledigt ist und was wegen fehlender realer Anlagendaten oder eines noch
nicht finalen Home-Assistant-Modbus-Vertrags blockiert bleibt.

## Erledigt

- [x] Robuste Binary-Sensor-Auswertung einschließlich Sentinel-, Negativ-,
      Bitmasken- und Active-Low-Unterstützung.
- [x] Explizite Binary-Metadaten in `idm-heatpump-api`.
- [x] Passende Geräteklassen für Betrieb, Heizen, Kühlen, Sperre, Verbindung und
      Störung.
- [x] Berechnete Wärmepumpen- und Wärmequellen-Spreizung.
- [x] Berechnete Warmwasser-Abweichung.
- [x] Navigator-Webzustände als echte Binary-Sensoren.
- [x] Optionale Gerätehierarchie für Heizkreise, Zonen, Räume, Solar, ISC,
      Kaskade und Zusatzwärmeerzeuger.
- [x] Stabile Unique IDs und sichere Migration bestehender Installationen.
- [x] Taktungs-, Laufzeit-, Verdichterstart- und Abtauanalyse.
- [x] Kurz-Takt-Warnung und Betriebsanteile.
- [x] Neustartfeste Persistenz der Betriebsanalyse.
- [x] Sicherer Warmwasser-Boost mit Start, Abbruch, Timeout, Zielerreichung,
      Neustart-Recovery und garantierter Wiederherstellung.
- [x] Entity-basiertes, dedupliziertes Modbus-Polling.
- [x] Schutz-, Alarm-, Analyse- und Restore-Register bleiben immer aktiv.
- [x] Konservatives Default-Profil für generierte technische/seltene
      Diagnose-Entities ergänzt, ohne bestehende Unique IDs zu ändern.
- [x] Prüfung mit API-Pin `0.8.1` und separat gegen API-Main.
- [x] Ruff, Formatter, Mypy, Pytest, Hassfest und Security für alle gemergten
      Arbeitspakete.

## Offen – benötigt reale Anlagendaten

### COP

- [x] Eindeutige Register für zeitgleiche elektrische und thermische Leistung
      verifiziert.
- [x] Verhalten bei Heizen, Leerlauf und Kleinstleistung defensiv abgesichert.
- [x] Momentanen COP-Sensor nur veröffentlichen, wenn beide Quellen belastbar
      verfügbar sind und die Anlage nicht im Stillstand falsche Kennzahlen
      erzeugen würde.
- [ ] Weitere reale Datensätze für Warmwasser, Abtauen und unterschiedliche
      Navigator-Firmwares sammeln; Issue-Vorlage und Field-Diagnostics-Guide
      sind vorbereitet.

Zusätzliche Nutzerdaten:

- Diagnoseexport aus Home Assistant.
- Etwa 10–20 Minuten Rohdaten im Intervall von 5–10 Sekunden.
- Screenshots aus dem IDM-Navigator mit elektrischer Leistung, thermischer
  Leistung, Betriebsart und Verdichterstatus.

### Vorlauf-Abweichung

- [ ] Eindeutiges IDM-Register für den tatsächlich angeforderten
      Wärmepumpen-Vorlauf-Sollwert verifizieren.
- [ ] Abgrenzung zu Heizkurve, Mischer-Sollwert, maximalem Vorlauf und
      Heizkreis-Sollwert dokumentieren.
- [ ] Verhalten bei mehreren Heizkreisen und Kaskaden prüfen.
- [ ] Erst danach `Ist-Vorlauf - angeforderter Vorlauf` als Sensor ausgeben.

Benötigte Nutzerdaten:

- Zeitgleiche Werte für `hp_flow_temp`, angeforderten Vorlauf-Sollwert,
  Betriebsart und aktiven Heizkreis.
- Nach Möglichkeit Datensätze für Heizen, Warmwasser und Leerlauf.

### Reale Binary-Register-Verifikation

- [ ] Alle binären Register mindestens gegen ein Navigator-10-System prüfen.
- [ ] Alle binären Register mindestens gegen ein Navigator-2.0-System prüfen.
- [ ] Active-Low-, Sonder- und Firmwarewerte dokumentieren, falls sie von 0/1
      abweichen.

## Offen – weitere Qualitätsverbesserungen

- [x] Entity-Katalog in Basis, Erweitert und Diagnose/Experte klassifizieren;
      API-weite Erweiterung bleibt als separater Dokumentationsausbau offen.
- [x] Seltene Ventil-, Rohstatus-, Kaskaden- und Servicewerte für neue
      Installationen gezielt standardmäßig deaktivieren.
- [x] Bestehende Benutzeraktivierungen bei jeder weiteren Migration unverändert
      lassen; der Entity-Registry-Migrationsvertrag ist dokumentiert.
- [x] Entity-Metadatenkatalog automatisiert aus HA-Metadaten erzeugen.
- [x] API-weite Entity-Dokumentation vorbereitet: explizite HA-Overlays stehen
      im Entity-Metadatenkatalog, die vollständige Registerreferenz bleibt über
      den bestehenden Generator an `idm-heatpump-api` gekoppelt; weitere reale
      Profilverifikation ist datenabhängig.
- [ ] Lasttests mit maximaler Zahl an Heizkreisen, Zonen und Räumen durchführen;
      blockiert bis passende Diagnoseexports über die Field-Diagnostics-Vorlage
      vorliegen.
- [x] Diagnosedaten-Anforderungen und Datenschutzregeln für Felddiagnosen
      dokumentieren.

## Blockiert – Home Assistant

- [x] Minimalen Transportvertrag für spätere Adapter im HASS-Repository
      dokumentieren, ohne ihn produktiv einzubinden.
- [ ] Transportzugriffe in `idm-heatpump-api` weiter abstrahieren, ohne die
      direkte Pymodbus-Nutzung zu verlieren; integrationsseitig sind Vertrag,
      Endpoint-Validierung und redigierte Diagnose-Helfer vorbereitet.
- [ ] Optionalen `modbus-connection`-Transportadapter erst implementieren, wenn
      Home Assistant den überarbeiteten offiziellen Integrationsvertrag
      veröffentlicht hat; bis dahin den Issue mit der vorbereiteten Vorlage,
      Vertrag, Akzeptanzkriterien und Migrationsfragen pflegen.
- [x] Bis dahin keine harte oder vorzeitige Abhängigkeit einführen.

## Unveränderte Release-Regeln

- Add-on-Version bleibt unabhängig von der API-Version.
- Der API-Pin wird nur in einem eigenen, vollständig geprüften Add-on-PR
  geändert.
- Keine Schätzung wird als Messwert veröffentlicht.
- Keine bestehende Unique ID wird ohne Migration geändert.
