# Changelog

## [0.1.0] - 2026-03-20

### New Features
- Initiale Implementierung der IDM Navigator 2.0 Home Assistant Integration
- Modbus TCP Client mit Batch-Lesung und Auto-Recovery
- 100+ Sensor-Entities fur Temperaturen, Drucke, Durchflusse, Energie
- 9 Binary Sensor-Entities
- ~30 Number-Entities (beschreibbare Sollwerte)
- ~15 Select-Entities (Betriebsmodi)
- 4 Switch-Entities (GLT-Anforderungen)
- 3-Schritt Konfigurations-Flow (IP/Port/Name → Optionen → Zonen)
- Options Flow zur Rekonfiguration
- 3 Services: set_system_mode, acknowledge_errors, write_register
- Diagnosedaten-Export
- Deutsche und englische Ubersetzungen
- EEPROM-Schutz fur 88 sensitive Register
- Unterstutzung fur Heizkreise A-G und Zonen 1-10
