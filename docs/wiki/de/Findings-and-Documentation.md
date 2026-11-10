# Erkenntnisse und Dokumentation

Diese Seite bündelt Felderkenntnisse und die Pflege der Dokumentation. Die Wiki
folgt dem auf der [Übersicht](Home) genannten Quellstand; für ein installiertes
Release gilt dessen getaggtes Manifest. Die Versionsgeschichte steht im
[Changelog](Changelog).

## Erkenntnisregister

| Erkenntnis | Nachweis und Gültigkeitsbereich | Konsequenz und offene Fragen |
|------------|-------------------------------|------------------------------|
| Capture-Wiedergabe zu #577 | Zwei privat eingereichte Captures mit Issue-Verweis bestanden die Archiv-Prüfung und wurden mit API 2.16.1 ausgewertet. HTTP-JSON lieferte drei Heizkreis-Vorlauftemperaturen; die geprüften WebSocket-Status-/Startseitenantworten waren lesbar, deren HTTP-Datenpfade lieferten 404. | Notizen beweisen weder Regleridentität noch Zuordnung zum ursprünglich gemeldeten Modul. Fehlende Größen werden nicht geschätzt. Aktuelle Melderdiagnosen, API-Version und gelesene Schlüssel mit dem genauen Modul vergleichen, bevor ein Parserfix behauptet wird. |
| GLT-Entitäten nach nicht gesetztem Startwert (#493) | Ein Regressionstest reproduziert den beim Start ausgelassenen Lesesensor. Unterstützte Eingänge behalten nun ihre Entität und erholen sich bei gültigem Rücklesewert. Siehe [Konfiguration](Configuration). | Beschreibbare Numbers behalten bereits Bedienbarkeit und Polling-Abhängigkeiten. Das Flackern der Batterieanzeige am Regler ist damit allein nicht behoben; fehlende/nicht unterstützte Register bleiben ausgefiltert. |
| Batteriebetrieb erfordert Register 84 (#493) | Der IDM-Support hat dem Melder von #493 bestätigt: Wird eine Batterie genutzt, muss Register 84 (`battery_discharge`) geschrieben werden. Nach Zuordnung von Batterie Laden/Entladen zusammen mit dem SOC trat kein Flackern mehr auf. Siehe [Einrichtung der externen Leistungsweiterleitung](Installation-and-Setup#automatische-externe-leistungsweiterleitung-von-home-assistant). | Batterie Laden/Entladen und SOC zuordnen. Bei zwei Batterien die Summe der vorzeichenbehafteten Leistung weiterleiten (positiv = Entladen). Das ist eine Eingangsanforderung des Reglers, kein Integrationsfehler. IDM hat nicht bestätigt, dass jedes andere externe Leistungsregister in jedem Zyklus geschrieben werden muss. |
| PV-Meldung 20300 bei gültiger Nullproduktion | Eine kontrollierte Versuchsreihe an einem Navigator 10 (10.11.2026) klärte den Mechanismus: Die Meldung erscheint, wenn das weitergeleitete pv_production-Register rund zehn Minuten unverändert bleibt — unabhängig vom Pegel —, und jede Wertänderung löscht sie in Sekunden. Es gibt keinen Watt-Schwellwert; der Workaround alterniert 10/20 W pro Minute. Getestete Firmware und Vorgehen in der [Konfiguration](Configuration#optionaler-workaround-fur-pv-meldung-20300-bei-nullleistung). | Alternierender 10/20-W-Herzschlag-Workaround mit Auswirkungen auf PV-Anzeige und Statistik des Reglers. Belegt nicht, dass jede Meldung 20300 diese Ursache hat, und behebt keine Kommunikationsausfälle. |
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

## Datenspende-Auswertung: 9. November 2026

Drei weitere Diagnose-ZIPs und sechs weitere Telemetrieberichte wurden geprüft.
Die beiden Navigator-10-ZIPs enthalten Web- und Statistikantworten. Numerische
Parameter werden mit dem Parameterparser verarbeitet, nicht mit dem Parser für
HTML-Abschnitte. Eine ausdrückliche Meldung über einen nicht verfügbaren Heizkreis
ist von einer fehlerhaften Antwort zu unterscheiden. API 2.16.2 und Integration
0.26.11 behalten die anderen erfolgreich gelesenen Kreise bei; die Diagnose nennt
nur die Buchstaben fehlender Kreise, keine Namen oder Antworttexte.

Offen und ausdrücklich nicht als behoben erklärt:

- Als NAVIGATOR Pro deklarierte Einsendung: 499 lesbare FC03/FC04-Wörter,
  davon 48 Funktions-/Adresspaare ohne frühere lesbare Referenz. Bedeutung,
  Skalierung und physisches Modell sind nicht bestätigt. Daraus folgen keine
  neuen Entitäten oder Änderungen offizieller Registerdefinitionen.
- Die HTTP-Anmeldung bleibt beim Loginformular. Eine falsche PIN ist nicht
  bewiesen. Frische Browseranmeldung und bereinigtes Loginprotokoll vergleichen.
- Bei allen acht Telemetrieberichten fehlt das physische Wärmepumpenmodell.
  Fähigkeitsmerkmale stammen aus API-Modellmetadaten und beweisen keine Ausstattung.
- Fünf spätere Berichte haben vollständige, zeitlich passende Laufzeitzähler;
  der Übergangsbericht lässt sie bewusst weg. Historische Abweichungen bleiben
  markiert. `NAV10_` und `T_NAV10_` werden nicht zusammengefasst.
- Bei #577 bleiben Parser und gepackte Register offen. #649 ist im gesunden
  Anlagenzustand bestätigt; ein Fehler wurde nicht ausgelöst. #493 ist
  beantwortet: Der IDM-Support verlangt bei Batterie das Schreiben von
  Register 84. #668 wartet auf Bestätigung des Melders. Frühere Antworten
  ersetzen keine bestätigte allgemeine Anforderung des Reglers, ausgenommen
  diese IDM-Bestätigung zu Register 84.

Originale bleiben unter den bisherigen Aufbewahrungsregeln erhalten. Tests
verwenden synthetische Strukturen statt gespendeter Messwerte oder Notizen.
„Bearbeitet“ bedeutet ausgewertet, nicht dass jede Hypothese bereits behoben ist.


## Datenspendenprüfung: 10. November 2026

Neue Navigator-10-Aufnahmen bestätigen beim Replay mit API 2.16.2: Ausdrücklich nicht vorhandene Heizkreise und Frischwasserkomponenten bleiben fehlend und werden nicht durch erfundene Nullwerte ersetzt. Wetterprognosen und numerische Parameter werden korrekt gelesen. Unterschiedliche Menümengen folgen der gemeldeten Verfügbarkeit; gleiche Firmware und Modbus-Adressen beweisen keine identische physische Anlage.

Die Serverauswertung zeigt jetzt betroffene Berichte und die Quellenabdeckung von Web-Abbrüchen zusätzlich zur Modbus-Fehlerquote, insgesamt und je Vergleichsgruppe. Eine kleine Gesamtquote soll einen betroffenen Bericht nicht verdecken. Das sind gemeldete Verbindungsereignisse ohne bewiesene Ursache oder Ausfalldauer; sonst stimmige Laufzeit-/Energiedaten werden nicht automatisch verworfen. Keine zusätzlichen Clientdaten, geänderten Zustimmungen oder Anlagenabfragen. Siehe [Qualität der Auswertung](Telemetry#qualitat-der-auswertung).

Eine verkleinerte Typmenge von Zahl-oder-Text zu nur Text ist im privaten Strukturvergleich sichtbar, erzeugt aber keinen neuen Typbefund für die selektive Benachrichtigung. Synthetische Tests sichern diese Unterscheidung und die Meldung eines tatsächlich neuen Typs ab. Daraus ergibt sich kein weiterer API-Parserfix. Physische Wärmepumpenmodelle, unklare Pro-Komponenten und ausdrückliche Beobachtungsgrenzen bleiben offen; Firmwarevergleiche verwenden Quelldaten statt fest codierter aktueller Versionen.
