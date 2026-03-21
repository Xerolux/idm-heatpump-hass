# Datenaktualisierung

## Wie werden Daten abgerufen?

Die Integration verwendet Modbus TCP, um Registerdaten direkt von der IDM Wärmepumpe zu lesen. Alle Kommunikation erfolgt **lokal** – es gibt keine Cloud-Verbindung.

## Polling-Mechanismus

Die Integration nutzt den **DataUpdateCoordinator** von Home Assistant:

- Alle Entitäten teilen sich **eine gemeinsame Abfrage** pro Polling-Zyklus
- Modbus-Register werden in **Batches von bis zu 30 aufeinanderfolgenden Adressen** gelesen, um die Anzahl der Netzwerkanfragen zu minimieren
- Der Coordinator aktualisiert alle Entitäten gleichzeitig nach jeder erfolgreichen Abfrage

## Konfiguriertes Intervall

Das Abfrageintervall ist **frei konfigurierbar** (5–300 Sekunden, Standard: 10 Sekunden):

- **Einstellungen → IDM Heatpump → Konfigurieren → Abfrageintervall**
- Kürzere Intervalle bieten schnellere Updates, erzeugen aber mehr Netzwerklast
- Empfehlung: 10–30 Sekunden für normalen Betrieb

## Entitätsverfügbarkeit

Eine Entität wird als **unavailable** markiert wenn:
- Die Verbindung zur Wärmepumpe unterbrochen ist
- Der Modbus-Register-Wert den Sentinel-Wert `-1.0` zurückgibt (unused/inaktives Register)
- Die Option "Unbenutzte Sensoren ausblenden" aktiviert ist

## Schreibvorgänge (writable entities)

Number-, Select- und Switch-Entitäten können Werte in die Wärmepumpe schreiben:
1. Der neue Wert wird **optimistisch** sofort in der UI angezeigt
2. Ein vollständiger Refresh wird danach ausgelöst, um den tatsächlichen Gerätezustand zu bestätigen
3. **EEPROM-geschützte Register** dürfen nur einmal pro Minute beschrieben werden, um Hardwareverschleiß zu vermeiden

## Fehlerbehandlung

- Bei Verbindungsfehlern wird automatisch eine **Repair Issue** in Home Assistant erstellt
- Sobald die Verbindung wiederhergestellt ist, verschwindet die Repair Issue automatisch
- Der DataUpdateCoordinator loggt Verbindungsfehler einmalig (nicht bei jedem fehlgeschlagenen Zyklus)

## Technician Code Sensoren

Die optionalen Technician-Code-Sensoren aktualisieren sich **unabhängig** alle 60 Sekunden über einen eigenen Timer, da sie keine Modbus-Registerwerte sind, sondern berechnete Codes.
