# IDM Heatpump – offene TODO-Liste

Stand: 20.07.2026

Die großen Optimierungsblöcke aus dem Repository-Vergleich sind umgesetzt. Dieses
Dokument enthält nur noch Punkte, die tatsächlich offen, datenabhängig oder durch
einen externen Home-Assistant-Entscheid blockiert sind.

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
- [x] Prüfung mit API-Pin `0.8.1` und separat gegen API-Main.
- [x] Ruff, Formatter, Mypy, Pytest, Hassfest und Security für alle gemergten
      Arbeitspakete.

## Offen – benötigt reale Anlagendaten

### COP

- [ ] Eindeutiges Register für die zeitgleiche elektrische Gesamtleistung
      verifizieren.
- [ ] Eindeutiges Register für die thermische Leistung verifizieren.
- [ ] Alternativ Durchfluss, Vorlauf, Rücklauf und Wärmeträgermedium für eine
      thermische Leistungsberechnung verifizieren.
- [ ] Werte für Heizen, Warmwasser, Leerlauf und möglichst Abtauen über mehrere
      Minuten mit identischem Zeitstempel erfassen.
- [ ] Skalierung, Einheit und Verhalten bei Verdichterstillstand prüfen.
- [ ] Erst danach einen momentanen COP-Sensor implementieren.

Benötigte Nutzerdaten:

- Diagnoseexport aus Home Assistant.
- Etwa 10–20 Minuten Rohdaten im Intervall von 5–10 Sekunden.
- Screenshots aus dem IDM-Navigator mit elektrischer Leistung, thermischer
  Leistung beziehungsweise Durchfluss, Vorlauf, Rücklauf, Betriebsart und
  Verdichterstatus.

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

- [ ] Entity-Katalog vollständig in Basis, Erweitert und Diagnose/Experte
      klassifizieren.
- [ ] Seltene Ventil-, Rohstatus-, Kaskaden- und Servicewerte für neue
      Installationen gezielt standardmäßig deaktivieren.
- [ ] Bestehende Benutzeraktivierungen bei jeder weiteren Migration unverändert
      lassen.
- [ ] Entity-Dokumentation automatisiert aus API- und HA-Metadaten erzeugen.
- [ ] Lasttests mit maximaler Zahl an Heizkreisen, Zonen und Räumen durchführen.
- [ ] Diagnosedaten regelmäßig auf Vollständigkeit und Datenschutz prüfen.

## Blockiert – Home Assistant

- [ ] Transportzugriffe in `idm-heatpump-api` weiter abstrahieren, ohne die
      direkte Pymodbus-Nutzung zu verlieren.
- [ ] Optionalen `modbus-connection`-Transportadapter erst implementieren, wenn
      Home Assistant den überarbeiteten offiziellen Integrationsvertrag
      veröffentlicht hat.
- [x] Bis dahin keine harte oder vorzeitige Abhängigkeit einführen.

## Unveränderte Release-Regeln

- Add-on-Version bleibt unabhängig von der API-Version.
- Der API-Pin wird nur in einem eigenen, vollständig geprüften Add-on-PR
  geändert.
- Keine Schätzung wird als Messwert veröffentlicht.
- Keine bestehende Unique ID wird ohne Migration geändert.
