# Bekannte Einschränkungen

## Gerätekompatibilität

- **Nur IDM Navigator 2.0 / Navigator Pro** werden offiziell unterstützt
- Ältere IDM-Steuerungen ohne Navigator-Firmware werden **nicht** unterstützt
- Das Modbus-Register-Mapping kann zwischen Firmware-Versionen leicht abweichen

## Modbus TCP

- Ausschließlich **Modbus TCP** wird unterstützt (kein serielles Modbus RTU)
- Port und Slave-ID müssen korrekt konfiguriert sein
- Gleichzeitige Verbindungen von mehreren Clients (z.B. IDM-Webinterface + HA) können zu Timeout-Fehlern führen
- Empfehlung: Anderen Modbus-Clients während des Betriebs deaktivieren oder das Abfrageintervall erhöhen

## EEPROM-Schutz

- **88 Register** sind EEPROM-geschützt und können nur **einmal pro Minute** beschrieben werden
- Häufigere Schreibvorgänge auf diese Register können zu Hardwareverschleiß führen
- Die Integration erzwingt dieses Limit automatisch

## Einzelgerät pro Konfigurationseintrag

- Pro Home Assistant Instanz kann **nur eine** IDM Wärmepumpe über Modbus TCP konfiguriert werden (aufgrund der IP-basierten Unique-ID)
- Für mehrere Wärmepumpen am gleichen Bus: separate Slave-IDs verwenden und für jede einen eigenen Eintrag anlegen

## Nur Lesezugriff auf bestimmte Register

- Einige Register sind **schreibgeschützt** (z.B. Energiezähler, Temperatursensoren)
- Der Schreibversuch auf read-only Register kann einen Modbus-Fehler zurückgeben
- Der `write_register`-Service umgeht diese Schutzmaßnahme – **nur für erfahrene Nutzer**

## Zonenmodule

- Maximal **10 Zonenmodule** mit je bis zu **8 Räumen** werden unterstützt
- Zonenmodul-Konfiguration ist nach der Ersteinrichtung über die Optionen anpassbar
- Räume ohne physischen Sensor liefern ggf. `-1.0` als Wert (werden als unavailable markiert)

## Keine Push-Benachrichtigungen

- Die Integration ist ein **Polling-Client** – die Wärmepumpe sendet keine Änderungsbenachrichtigungen
- Änderungen am Gerät (z.B. über das Navigator-Webinterface) sind erst nach dem nächsten Polling-Zyklus in HA sichtbar

## Firmware-Version

- Die aktuelle Firmware-Version wird als Diagnose-Sensor (`firmware_version`) ausgelesen
- Firmware-Updates direkt aus Home Assistant sind **nicht** möglich
- Updates erfolgen über das IDM-Webinterface oder per USB
