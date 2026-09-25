# Unterstützte Geräte

## Kompatibilitätsstatus

Der detaillierte Modell- und Firmware-Status wird in der [Kompatibilitätsmatrix](Compatibility-Matrix) gepflegt. Die Tabelle unten ist eine kurze, installationsorientierte Zusammenfassung.

## Unterstützte Gerätefamilien

| Gerät | Firmware | Heizkreise | Zonenmodule | Status |
|--------|----------|------------------|--------------|--------|
| IDM Navigator 10 | NAV10_20.23 auf der Testhardware beobachtet | bis zu 7 (A–G) | bis zu 10 (6 standardmäßig, 8 konfigurierbar) | Auf einem Maintainer-Testsystem bestätigt; der Firmware-Wert ist ein Nachweis, kein universelles Minimum |
| IDM Navigator 2.0 | 2.x beobachtet/erwartet | bis zu 7 (A–G) | nicht bestätigt | Erwartet; Navigator-10-exklusive Register werden gefiltert |
| IDM Navigator Pro | unbekannt | bis zu 7 (A–G) | bis zu 10 (bis zu 8 konfigurierbare Räume) | Erwartet; benötigt einen vollständigen Diagnosebericht |
| IDM Navigator 1.7 | n1.x-Firmware | statische Sensor-Slots A–G | keine | Nur-Lese-Sensormap aus der offiziellen 1.x-Tabelle; PV-Supplement-Schreibvorgänge, wenn die Firmware sie bereitstellt; benötigt Community-Tests |

## Voraussetzungen

- **Modbus TCP** muss im Navigator-Regler aktiviert sein
  - Einstellung: *Fachmann-Ebene → Kommunikation → Modbus TCP*
  - Standardport: **502**
  - Standard-Slave-ID: **1**

## Nicht unterstützte Geräte

| Gerät | Grund |
|--------|--------|
| IDM Navigator 1.0 | Eigene 1.x-Protokollfamilie; nur die 1.7-Map ist implementiert |
| IDM-Geräte ohne Netzwerkverbindung | Kein Modbus TCP |
| Andere Wärmepumpenhersteller | Anderes Modbus-Protokoll / anderes Registerlayout |

## Ungetestete Geräte (möglicherweise kompatibel)

Die folgenden Geräte könnten dieselbe Registerbelegung wie der Navigator 2.0 / 10 verwenden, sind aber in der öffentlichen Community-Testmatrix noch nicht bestätigt:

- IDM Terra SW (mit Navigator-2.0-/10-Regler)
- IDM Terra HT (mit Navigator-2.0-/10-Regler)
- IDM Aero SLM (mit Navigator-2.0-/10-Regler)

> **Hinweis:** Wenn du ein nicht gelistetes IDM-Gerät erfolgreich verwendest, teile bitte einen detaillierten [Kompatibilitätsbericht in Q&A](https://github.com/Xerolux/idm-heatpump-hass/discussions/categories/q-a), damit wir die Liste erweitern können. Wähle im Formular **Devices or firmware compatibility**.

## Modbus-Register-Kompatibilität

Die Integration baut aus der Bibliothek
[`idm-heatpump`](https://github.com/Xerolux/idm-heatpump-api) eine modell- und
konfigurationsabhängige Modbus-Registermap:

- **Lesespeicher** (Input Registers): Temperaturen, Status, Energie, Leistung
- **Lese-/Schreibspeicher** (Holding Registers): Betriebsmodi, Sollwerte, Konfiguration

Details zu allen Registern: [Modbus-Register-Wiki](Modbus-Register)

Kompatibilitätsnachweise und Berichtsfelder: [Kompatibilitätsmatrix](Compatibility-Matrix)

## Bekannte firmwarespezifische Unterschiede

- Register 1048 (`current_energy_price`) ist optional und firmwareabhängig;
  die Integration isoliert es, wenn der aktive Regler es nicht unterstützt.
- Zonen-Register (ab 2000) erfordern installierte und erkannte/konfigurierte
  Zonenmodule. Sie werden nicht allein über den Namen der Navigator-Familie
  aktiviert.
- PV-Register (74–86) erfordern das optionale PV-Modul

## Lokale Web-Kompatibilität

- Navigator 2.0 nutzt den lokalen HTTP/CSRF-Client (intern `nav20`).
- Navigator 10 und Navigator Pro nutzen den Navigator-10-WebSocket-Client
  (intern `nav10`).
- Setup/Rekonfiguration können beide Varianten testen; die normale Abfrage bleibt
  auf der Variante, die tatsächlich erfolgreich war. Siehe
  [Lokale Navigator-Weboberfläche](Local-Web-Interface).
