# Erkenntnisse und Dokumentation

Diese Seite bündelt Felderkenntnisse und die Pflege der Dokumentation. Die Wiki
folgt dem auf der [Übersicht](Home) genannten Quellstand; für ein installiertes
Release gilt dessen getaggtes Manifest. Die Versionsgeschichte steht im
[Changelog](Changelog).

## Erkenntnisregister

| Erkenntnis | Nachweis und Gültigkeitsbereich | Konsequenz und offene Fragen |
|------------|-------------------------------|------------------------------|
| PV-Meldung 20300 bei gültiger Nullproduktion | Bei einem Navigator 10 verschwand die Meldung nach Weiterleitung eines kleinen positiven Wertes ohne Quittierung. Getestete Firmware und Vorgehen stehen in der [Konfiguration](Configuration#optionaler-workaround-fur-pv-meldung-20300-bei-nullleistung). | Optionaler 10-W-Workaround mit Auswirkungen auf PV-Anzeige und Statistik des Reglers. Belegt nicht, dass jede Meldung 20300 diese Ursache hat, und behebt keine Kommunikationsausfälle. |
| Firmware-Präfixe `NAV10_` und `T_NAV10_` | Die Familienerkennung akzeptiert beide exakten Präfixe; ähnliche Angaben wie `NAV100_` werden abgelehnt. Siehe [Konfiguration](Configuration). | HTTP als Transport allein identifiziert keinen Navigator 2.0. Die explizite Modellauswahl behält Vorrang. |
| Gemeinsame Modbus-Verbindung | Die Diagnose meldet gemeinsame Nutzung, wenn die Unit-API von Home Assistant beansprucht werden kann; andernfalls greift der private Transport. Siehe [Fehlerbehebung](Troubleshooting#verbindungsabbruche). | Vor der Suche nach doppelten Clients tatsächliche Werte für `source`, `owns_socket` und `supports_shared_connection` prüfen. Ein TCP-Verbindungsaufbau belegt noch keine korrekten Registerdaten. |
| Wärmesenken-Durchfluss ist FLOAT32 | Feldmessungen zeigten die veraltete UCHAR-Deklaration älterer Registertabellen. Siehe [Bekannte Einschränkungen](Known-Limitations). | Ohne Trennwärmetauscher dürfen Werte korrekt nicht verfügbar sein. Ein Dekodierartefakt belegt keinen physischen Nulldurchfluss. |
| Differenzkreise haben andere Semantik | Die Registerwerte stehen für Speicher-/Referenztemperatur und die vorzeichenbehaftete Differenz Referenz minus Speicher. Siehe [Konfiguration](Configuration#differenztemperaturgeregelte-heizkreise) und [Entitäten](Entities#differenztemperaturgeregelte-heizkreise). | Normale Heizkreisauswahl zusätzlich zur Differenzauswahl beibehalten. Schwellen-/Hysteresezuordnung und vollständige Hardwarebestätigung bleiben offen. Gleiche Anzeigen beweisen keine Registerbedeutung. |
| Firmware-Beobachtungen sind keine Update-Angebote | Der optionale Katalog ordnet Community-Beobachtungen passenden Regler-/Modell-/Softwaredaten zu. Siehe [Telemetrie](Telemetry#firmware-orientierung). | Eigenständiges Opt-in, keine Installation und keine garantierte Verfügbarkeit für die Anlage. Nur iDM oder ein autorisierter Installateur kann ein Update beurteilen. |
| Optimierungsbeobachtung braucht vergleichbare Historie | Berichte, Predictive Advisor und Assist nutzen dieselbe begrenzte Datenbasis. Siehe [Predictive Advisor](Predictive-Advisor). | Vorher-/Nachher-Historie und geeignete Abdeckung sind erforderlich. Wetter und Nutzung können abweichen; ein Zusammenhang belegt weder Ursache noch Einsparung. |
| Web-only steuert je nach Modell unterschiedlich | Navigator 10/Pro bietet ausgewählte geprüfte Steuerungen; Navigator 2.0 HTTP ist überwiegend ein lesendes Supplement mit Uhrzeitaktion. Siehe [Protokollfähigkeiten](Protocol-Capabilities). | GLT-Weiterleitung, einmaliger Warmwasser-Boost und Leistungseingänge für berechneten COP brauchen Modbus. Ein Protokollmerkmal ist nicht automatisch als Entität umgesetzt. |
| Fachmannzugang gehört zum Installateur | Fachmanncode-Entitäten wurden entfernt; siehe [Bekannte Einschränkungen](Known-Limitations) und [Installateur-Checkliste](Installer-Checklist). | Die Integration berechnet keine Zugangscodes und installiert keine Firmware. |
| B10-Hochdruckkontakt ist im gesunden Zustand geschlossen | Die Web-Binärsensor-Definition invertiert B10 wie B5/B15; die Korrektur ist im [Changelog](Changelog) dokumentiert. | Geschlossen bedeutet kein Fehler, offen bedeutet Störung. Eine falsche Zuordnung kann einen dauerhaften Fehler vortäuschen; reale Störungen weiterhin am Regler prüfen. |
| Telemetrie-Zeitfenster müssen zu ihren Zählern passen | Unabhängige Analysespeicher können beim Reload neuer als der Telemetrie-Checkpoint sein. Siehe [Datenumfang und Übertragung](Telemetry). | Die Wiederaufnahme verwendet ein zusammengehöriges Zeit-/Zählerpaar. Bei älteren Checkpoints fehlt die Betriebsdauer einmalig im Übergangsbericht; die Betriebs- und Energiehistorie von HA bleibt erhalten. |
| Navigator 1.x kann mehr als nur lesen | Die offizielle 1.x-Map enthält den schreibbaren Holding-Block und momentane Coil-Aktionen. FHEM-Capture und API-Vertragstests sind in der [Kompatibilitätsmatrix](Compatibility-Matrix) eingeordnet. | Unterstützung ist implementiert; nicht jede Modell-/Firmware-Kombination ist vollständig physisch bestätigt. EEPROM-Grenzen beachten und die Vorrangladung nicht zyklisch automatisieren. |
| Nicht belegte Temperatur-Eingänge antworten mit Speicher-Müll | Ein Navigator-2.0-Heizkreis ohne iDM-Raumfühler meldet am Register 1364 etwa −327 °C (beobachtet −327,33 und −327,22; Issues #504, #668) statt eines deklarierten Sentinels. Der Wert ist endlich und pro Boot stabil. | Die Integration behandelt Werte ≤ −300 °C auf Temperatur-Registern als „Fühler nicht vorhanden“: die Gesundheitsprüfung ignoriert sie, die Sensor-Entität wird nicht verfügbar (außer bei Rohwerten) und Klima-/Boiler-Karten veröffentlichen keine Temperatur. Belege für Müllwerte im positiven Bereich gibt es nicht; sie bleiben markiert. |

## Die nächste Entdeckung festhalten

Reglerfamilie, relevante Firmware, Integrations-/API-Versionen, Verbindungsmodus
und die genaue Beobachtung dokumentieren. Vor Veröffentlichung Zugangsdaten,
PINs, Adressen, myIDM-IDs und andere persönliche Daten entfernen. Wenn vorhanden,
ein bereinigtes Issue, eine Capture-Beschreibung oder einen reproduzierbaren
Test verlinken.

Beobachtung, garantierte Implementierung, Vermutung und offene Bestätigung
getrennt benennen. Eine erfolgreiche Schreibantwort oder HTTP-Bestätigung
belegt weder physisches Verhalten noch langfristige Zuverlässigkeit.
Die Erklärung gehört auf die passende Funktionsseite und deren englische
Fassung, gefolgt von einem kurzen Eintrag hier. Protokolldetails stehen in der
[Navigator-Protokollanalyse](Navigator-Protocol-Analysis), Modellnachweise in
der [Kompatibilitätsmatrix](Compatibility-Matrix), offene Grenzen in
[Bekannte Einschränkungen](Known-Limitations).

## Die Wiki aktuell halten

Jedes Quellmodul der Integration ist in `docs/wiki-coverage.json` einer
Nutzerdokumentation zugeordnet. Ein Quellfingerabdruck hält je Funktionsgruppe
fest, welcher Stand geprüft wurde. Geänderte oder neue Module, fehlende
Sprachfassungen, nicht veröffentlichte Seiten und undokumentierte Aktionen
lassen die Abdeckungsprüfung fehlschlagen. Alte Release-Ankündigungen auf der
Startseite werden ebenfalls abgelehnt.

Nach dem Abgleich der englischen und deutschen Seiten mit einer Codeänderung
bestätigt `python scripts/check_wiki_coverage.py --update` die geprüften
Quellfingerabdrücke. Den Diff kontrollieren: Der Befehl aktualisiert den
Prüfvermerk, nicht den Text. Er ersetzt keine inhaltliche Prüfung. Neue
Funktionen brauchen Einrichtung, Standardwerte, Bedienung, Datenschutz,
Fehlerverhalten und Grenzen auf ihrer Funktionsseite.

CI, Abhängigkeitsprüfung, Release-Prüfung und Website-Veröffentlichung erzwingen
diese Prüfung zusätzlich zur Versionskonsistenz. Automatische Prüfungen machen
Auslassungen sichtbar, beweisen aber nicht die Richtigkeit jedes Satzes.
Felderkenntnisse bei widersprechenden Nachweisen erneut prüfen. Veröffentlichte
Versionsgeschichte wird nicht auf das heutige Verhalten umgeschrieben.
