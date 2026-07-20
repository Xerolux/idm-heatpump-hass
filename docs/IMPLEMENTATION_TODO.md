# IDM Heatpump – Optimierungs- und Ausbauplan

Stand: 20.07.2026

Dieses Dokument ist die technische TODO-Liste für die nächsten Ausbaustufen von
`idm-heatpump-hass`. Änderungen werden nur übernommen, wenn Registerbedeutung,
Verfügbarkeit und Wertebereich durch die IDM-Dokumentation, die API-Metadaten
oder belastbare Gerätediagnosen abgesichert sind.

## Priorität 1 – Datenqualität und korrekte Entitäten

- [x] Binärwerte nicht mehr pauschal mit `bool(value)` auswerten.
- [x] Negative, nicht endliche und Sentinel-Werte sicher als inaktiv behandeln.
- [x] Vorbereitung auf explizite On-/Off-Werte, Bitmasken und Active-Low-Signale
      in `idm-heatpump-api`.
- [x] Aussagekräftigere `BinarySensorDeviceClass` für Fehler, Verbindung,
      Sperren, Heizen, Kühlen und laufende Aggregate.
- [x] Eigene Unit-Tests für die Binary-Semantik.
- [ ] Explizite Binary-Metadaten in `idm-heatpump-api` ergänzen und anschließend
      die heuristische Zuordnung nur noch als Fallback verwenden.
- [ ] Operative Binary-Sensoren von reinen Diagnose-Entitäten trennen.
- [ ] Alle binären IDM-Register gegen echte Diagnosedaten mindestens eines
      Navigator-10- und eines Navigator-2.0-Systems prüfen.

### Abnahme

- Kein negativer Statuswert kann als `on` erscheinen.
- Fehler-, Heiz-, Kühl-, Verbindungs- und Laufzustände haben passende
  Home-Assistant-Geräteklassen.
- Unbekannte Zustände erzeugen keinen falschen Alarm und keinen falschen
  Betriebszustand.

## Priorität 2 – Berechnete Messwerte

- [ ] Wärmepumpen-Spreizung aus `hp_flow_temp - hp_return_temp`.
- [ ] Wärmequellen-Spreizung aus Ein- und Austrittstemperatur.
- [ ] Warmwasser-Abweichung zwischen Ist- und Solltemperatur.
- [ ] Vorlauf-Abweichung zwischen Ist- und angefordertem Sollwert, sofern die
      verwendeten Register für das erkannte Modell eindeutig sind.
- [ ] Momentaner COP nur dann, wenn zeitgleich gemessene thermische und
      elektrische Leistung mit kompatiblen Einheiten verfügbar sind.
- [ ] Berechnete Sensoren ausschließlich bei vorhandenen, plausiblen
      Quelldaten registrieren.
- [ ] Für fehlende oder unplausible Quellen `unavailable` statt `0` liefern.
- [ ] Unit-Tests für Berechnung, Rundung, Division durch null, Sentinel-Werte
      und fehlende Quellen.

### Abnahme

- Alle Berechnungen stammen aus demselben Coordinator-Snapshot.
- Keine Schätzung wird als gemessener Wert ausgegeben.
- Sensoren besitzen korrekte Unit-, Device- und State-Class-Metadaten.

## Priorität 3 – Sinnvolle Standardauswahl

- [ ] Entitäten in Basis, Erweitert und Diagnose/Experte klassifizieren.
- [ ] Basiswerte standardmäßig aktivieren: Temperaturen, Betriebsmodus,
      Anforderungen, Verdichter, Leistung, Energie und Störung.
- [ ] Seltene Ventil-, Rohstatus-, Kaskaden- und Servicewerte standardmäßig
      deaktivieren, aber weiterhin über die Entity Registry verfügbar halten.
- [ ] Bestehende Benutzeraktivierungen bei Migrationen unverändert lassen.
- [ ] Dokumentation und Entity-Liste automatisch aus den API-Metadaten erzeugen.

### Abnahme

- Eine neue Installation zeigt ohne Nacharbeit eine übersichtliche,
  alltagstaugliche Geräteansicht.
- Experten verlieren keinen Zugriff auf technische Register.

## Priorität 4 – Anlagenmodule als Gerätehierarchie

- [ ] Hauptgerät für die IDM-Steuerung beibehalten.
- [ ] Heizkreise A–G als untergeordnete Geräte prüfen.
- [ ] Zonenmodule und Räume als untergeordnete Geräte prüfen.
- [ ] Solar, Kaskade, ISC und Zusatzwärmeerzeuger nur bei erkannter Hardware
      anlegen.
- [ ] Untergeräte über `via_device` mit dem Hauptgerät verbinden.
- [ ] Stabile Unique IDs und eine getestete Migration für bestehende
      Installationen sicherstellen.
- [ ] Veraltete Geräte und Entitäten nach einer geänderten Hardwareerkennung
      kontrolliert bereinigen.

### Abnahme

- Keine Entity-ID ändert sich ungewollt.
- Nicht vorhandene Module erzeugen keine leeren Geräte oder Entitäten.

## Priorität 5 – Taktung und Betriebsanalyse

- [ ] Verdichterstarts gesamt, heute sowie in rollierenden 2- und 4-Stunden-
      Fenstern.
- [ ] Laufzeit des aktuellen Takts und durchschnittliche Taktlänge.
- [ ] Abtauvorgänge heute, letzter Abtauzeitpunkt und Zeit seit letzter Abtauung.
- [ ] Kurz-Takt-Warnung mit dokumentierter, konfigurierbarer Schwelle.
- [ ] Betriebsanteile für Heizen, Warmwasser, Kühlen und Abtauen.
- [ ] Home-Assistant-Recorder und Statistiksystem bevorzugen; eigene
      Persistenzdateien nur verwenden, wenn es technisch zwingend nötig ist.

### Abnahme

- Neustarts erzeugen keine falschen Starts oder Zähler-Sprünge.
- Zähler sind monoton beziehungsweise besitzen klar definierte Reset-Zeitpunkte.

## Priorität 6 – Modbus-Last und Aktualisierung

- [ ] Abhängigkeiten jeder Entity zu ihren Quellregistern deklarieren.
- [ ] Nur aktivierte Entitäten und intern benötigte Register pollen, sofern dies
      ohne Verlust der automatischen Erkennung möglich ist.
- [ ] Registeranforderungen global deduplizieren.
- [ ] Bestehende sichere Batchplanung der API beibehalten.
- [ ] Schnelles Polling nur für wirklich zeitkritische Flankenerkennung prüfen.
- [ ] Lasttests mit vielen Heizkreisen, Zonen und Räumen durchführen.

### Abnahme

- Weniger Modbus-Requests ohne langsamere oder unvollständige Zustände.
- Schreibvorgänge und Polling bleiben über dieselbe Verbindung sauber
  serialisiert.

## Priorität 7 – Sichere Komfortfunktionen

- [ ] Warmwasser-Boost als Button mit Statussensor entwerfen.
- [ ] Vorherigen Modus und Sollwert sichern und garantiert wiederherstellen.
- [ ] Fortschritt, Zieltemperatur, Startzeit und Abbruchgrund anzeigen.
- [ ] Konflikte mit PV-, SG-Ready- und manuellen Vorgaben eindeutig priorisieren.
- [ ] Alle Schreibvorgänge durch API-Validierung und EEPROM-Drosselung führen.
- [ ] Abbruch bei Kommunikationsfehlern und Home-Assistant-Neustart testen.

### Abnahme

- Kein Boost kann einen dauerhaften, unbeabsichtigten Sollwert hinterlassen.
- Jede automatische Änderung ist im Log und in Diagnosen nachvollziehbar.

## Priorität 8 – Vorbereitung auf Home Assistants neue Modbus-Architektur

- [ ] `idm-heatpump-api` als gerätespezifische Bibliothek beibehalten.
- [ ] Transportzugriffe innerhalb der API weiter kapseln.
- [ ] Optionalen Transportadapter für `modbus-connection` erst implementieren,
      wenn Home Assistant den überarbeiteten offiziellen Ansatz veröffentlicht.
- [ ] Keine vorzeitige harte Abhängigkeit von der aktuell noch überarbeiteten
      Home-Assistant-Integration einführen.
- [ ] Direkten Pymodbus-Transport als eigenständig nutzbare API-Variante
      erhalten.

### Zielarchitektur

```text
idm-heatpump-hass
        ↓
idm-heatpump-api
        ↓
Transportadapter: direkter Pymodbus-Client oder später modbus-connection
        ↓
IDM Navigator über Modbus TCP
```

## Qualitätsanforderungen für jede Ausbaustufe

- [ ] Vollständige Tests für neue Logik und Migrationen.
- [ ] `ruff`, `mypy --strict` und `pytest` erfolgreich.
- [ ] Keine Änderungen an bestehenden Unique IDs ohne Migration.
- [ ] Deutsche und englische Übersetzungen vollständig.
- [ ] Changelog, Entity-Dokumentation und bekannte Einschränkungen aktualisiert.
- [ ] Diagnosedaten enthalten alle für Supportfälle notwendigen, aber keine
      geheimen oder personenbezogenen Werte.
