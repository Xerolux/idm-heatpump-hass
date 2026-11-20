# iDM-Wärmepumpenmodelle für Home Assistant

## Kompatibilitätsstatus

Der detaillierte Modell- und Firmware-Status wird in der [Kompatibilitätsmatrix](Compatibility-Matrix) gepflegt. Die Tabelle unten ist eine kurze, installationsorientierte Zusammenfassung.

## iDM-Wärmepumpenmodelle für Home Assistantfamilien

| Gerät | Firmware | Heizkreise | Zonenmodule | Status |
|--------|----------|------------------|--------------|--------|
| IDM Navigator 10 | NAV10_20.23 auf der Testhardware beobachtet | bis zu 7 (A–G) | bis zu 10 (6 standardmäßig, 8 konfigurierbar) | Auf einem Maintainer-Testsystem bestätigt; der Firmware-Wert ist ein Nachweis, kein universelles Minimum |
| IDM Navigator 2.0 | 2.x beobachtet/erwartet | bis zu 7 (A–G) | nicht bestätigt | Erwartet; Navigator-10-exklusive Register werden gefiltert |
| IDM Navigator Pro | unbekannt | bis zu 7 (A–G) | bis zu 10 (bis zu 8 konfigurierbare Räume) | Erwartet; benötigt einen vollständigen Diagnosebericht |
| IDM Navigator 1.0 / 1.7 | n1.x-Firmware | A–G nach installiertem Umfang | eigene 1.x-Familie; nicht mit der 2.0/10-Zonenmap gleichsetzen | Offizielle 1.x-Sensor-/Coilmap und schreibbarer Holding-Block; Warmwasserkarte und Einmalaktionen nach verfügbarer Map. Breitere Firmware-/Hardwarebestätigung bleibt offen. |

## Voraussetzungen

- **Modbus TCP** muss im Navigator-Regler aktiviert sein
  - Einstellung: *Kommunikation → Modbus TCP* auf der Installateur-Ebene des
    Reglers — aktiviert durch deinen Heizungsinstallateur; die Integration
    schaltet sie nie frei
  - Standardport: **502**
  - Standard-Slave-ID: **1**

## Nicht unterstützte Geräte

| Gerät | Grund |
|--------|--------|
| IDM-Geräte ohne Netzwerkverbindung | Kein Modbus TCP |
| Andere Wärmepumpenhersteller | Anderes Modbus-Protokoll / anderes Registerlayout |

## Kompatibilität nach Wärmepumpenmodell

Lies das Wärmepumpenmodell am Typenschild ab und ermittle den Navigator-Regler
und seine Firmware separat. Für die Einrichtung per Modbus TCP bestimmt die
Navigator-Familie die Registerbelegung. Welche Werte und Bedienelemente
verfügbar sind, hängt auch von Firmware und Anlagenausstattung ab. Ein
Praxistest gilt für die jeweils genannte Kombination.

### iDM AERO ALM und AERO SLM mit Home Assistant

| Wärmepumpe | Navigator und Nachweis |
| --- | --- |
| **iDM AERO ALM 6–15** (ALM) | **Mit Navigator 10 im Betrieb beobachtet.** Die Felddiagnose dokumentiert Temperaturen, Warmwasser-Ladegrenzen und Betriebsverhalten mit Firmware `T_NAV10_20.24-1580`. Die separate Korrektur des einmaligen Warmwasser-Boosts wartet noch auf Feldbestätigung. Siehe [Erkenntnisse aus der Praxis](Findings-and-Documentation). |
| **iDM AERO SLM** (SLM) | Mit Navigator 2.0 oder 10 und aktiviertem Modbus TCP möglicherweise kompatibel. Ein vollständiger Test mit Modell, Firmware und Funktionsumfang steht aus. |

### iDM TERRA SW, SWM und HT mit Home Assistant

| Wärmepumpe | Navigator und Nachweis |
| --- | --- |
| **iDM TERRA SWM** | Mit Navigator 2.0 wird Kompatibilität erwartet. Für den Fall in der [Kompatibilitätsmatrix](Compatibility-Matrix) fehlt noch ein Rohmitschnitt der Modellerkennung. |
| **iDM TERRA SW und TERRA HT** | Mit Navigator 2.0 oder 10 möglicherweise kompatibel. In der öffentlichen Matrix fehlt ein vollständiger modellspezifischer Test. |

### iDM iPUMP mit Home Assistant

| Wärmepumpe | Navigator und Nachweis |
| --- | --- |
| **iDM iPUMP A ONE 2–8** | Ein [Anlagenbericht mit Navigator 10](https://github.com/Xerolux/idm-heatpump-hass/issues/710) nennt dieses Modell. Für den gemeldeten Vorlaufsollwert von Heizkreis A fehlt noch die Diagnose. |
| **iDM iPUMP ALM, iPUMP A, iPUMP T und iPUMP T7** | Vor der Einrichtung Navigator-Familie und Modbus-TCP-Menü prüfen. Für diese Reihen fehlt in der öffentlichen Matrix eine vollständige modellspezifische Bestätigung. |

Auch für **AERO ALM MAX, AERO AL MAX, TERRA SW MAX, TERRA TWIN und iPUMP N5
(NANO)** fehlt ein modellspezifischer Test in der öffentlichen Matrix. Prüfe
Regler und Schnittstelle, bevor du die Installation planst. [iDM-Produktübersicht](https://www.idm-energie.at/idm-produkte/)

Wenn der Regler feststeht, geht es mit der [Installationsanleitung für
Home Assistant](Installation-and-Setup) weiter.

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
