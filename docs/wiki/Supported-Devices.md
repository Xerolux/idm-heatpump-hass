# Unterstützte Geräte

## Vollständig unterstützt

| Gerät | Firmware | Heizkreise | Zonenmodule | Status |
|-------|----------|------------|-------------|--------|
| IDM Navigator 2.0 | alle Versionen | bis zu 7 (A–G) | nein | ✅ Bestätigt |
| IDM Navigator Pro | alle Versionen | bis zu 7 (A–G) | bis zu 10 (je 8 Räume) | ✅ Bestätigt |

## Voraussetzungen

- **Modbus TCP** muss in der Navigator-Steuerung aktiviert sein
  - Einstellung: *Fachmannebene → Kommunikation → Modbus TCP*
  - Standard-Port: **502**
  - Standard Slave-ID: **1**

## Nicht unterstützte Geräte

| Gerät | Grund |
|-------|-------|
| IDM ältere Steuerungen (vor Navigator 2.0) | Anderes Register-Mapping |
| IDM Geräte ohne Netzwerkanschluss | Kein Modbus TCP |
| Andere Wärmepumpen-Hersteller | Anderes Modbus-Protokoll / Register-Layout |

## Nicht getestete Geräte (möglicherweise kompatibel)

Folgende Geräte nutzen möglicherweise das gleiche Register-Mapping wie der Navigator 2.0, wurden aber nicht offiziell getestet:

- IDM Terra SW (mit Navigator 2.0 Steuerung)
- IDM Terra HT (mit Navigator 2.0 Steuerung)
- IDM Aero SLM (mit Navigator 2.0 Steuerung)

> **Hinweis:** Wenn du ein nicht aufgeführtes IDM-Gerät erfolgreich verwendest, erstelle bitte ein [GitHub Issue](https://github.com/Xerolux/idm-heatpump-hass/issues) damit wir die Liste erweitern können!

## Modbus Register-Kompatibilität

Die Integration liest **663 Modbus-Register** basierend auf der IDM Navigator 2.0 Dokumentation:

- **Lesespeicher** (Input Registers): Temperaturen, Status, Energie, Leistung
- **Schreib-/Lesespeicher** (Holding Registers): Betriebsmodi, Sollwerte, Konfiguration

Details zu allen Registern: [Modbus-Register Wiki](Modbus-Register)

## Bekannte Firmware-spezifische Unterschiede

- Register 1048 (`current_energy_price`) ist ab Navigator 2.0 Firmware 2.x verfügbar
- Zonenmodul-Register (ab 2000) erfordern das IDM Navigator Pro Hardware-Modul
- PV-Register (74–86) erfordern das optionale PV-Modul
