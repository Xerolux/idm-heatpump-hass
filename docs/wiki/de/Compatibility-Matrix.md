# Kompatibilitätsmatrix

Diese Matrix dokumentiert getestete IDM-Hardware, ohne private Netzwerkdaten zu veröffentlichen. Sie trennt bestätigte Geräte von erwarteter Kompatibilität, damit du das Risiko vor der Installation einschätzen kannst.

## Statusstufen

| Status | Bedeutung |
|--------|---------|
| `confirmed` | Vom Maintainer getestet oder durch einen vollständigen Diagnosebericht mit Modell, Firmware und aktivem Funktionsumfang belegt. |
| `community-tested` | Von Benutzern mit ausreichend Details gemeldet, um das Setup nachzuvollziehen, aber keine Hardware im Besitz des Maintainers. |
| `expected` | Die Registerkarte sollte passen, aber es liegt noch kein vollständiger Diagnosebericht vor. |
| `unsupported` | Bekannt, dass das Navigator-Modbus-TCP-Registermodell, das diese Integration voraussetzt, nicht verwendet wird. |

## Gerätematrix

| Wärmepumpe / Regler | Status | Firmware | Aktive Funktionen | Verifiziert mit | Hinweise |
|------------------------|--------|----------|---------------------|---------------|-------|
| IDM 6-15 mit Navigator 10 | confirmed | von der Diagnose gemeldet | Heizkreis A, PV, Solar, ISC; Nicht-verfügbar-Sentinel der Kaskade verifiziert | HASS-Branch-Tests, API-Vertragstests, wiederholte rein lesende Modbus-Abfragen | Maintainer-Testsystem. Privater Host, Port und Netzwerkdaten werden bewusst weggelassen. |
| Navigator 10 / aktuelle Hardware | community-tested | NAV10_20.23 beobachtet; andere Versionen brauchen Belege | Bis zu 7 Heizkreise, erkannte Zonenmodule | API-Registermodell, Diagnoseberichte | Register für Wärmesenke und Booster werden nur beim Navigator 10 freigegeben; das lokale Web nutzt den Navigator-10-WebSocket-Client. |
| Navigator 2.0 | expected | 2.x beobachtet/erwartet | Heizkreise, optionales PV/Solar/ISC/Kaskade; Zonen-Unterstützung nicht bestätigt | API-Registermodell, Vertragstests | Ein aktueller Terra-SWM-Bericht braucht noch einen Rohmitschnitt der Modellerkennung; das lokale Web nutzt HTTP/CSRF. |
| Navigator 1.7 | community-tested | n1.x-Firmware | 1.x-Sensorkarte plus der offizielle RW-Holding-Block (System-/Heizkreis-Modi, Raum- und Vorlauf-Sollwerte, Heizkurven, Grenzen, Bivalenzpunkte, Solar-Modus, Warmwasser-Sollwert); PV-Supplement (Schreibzugriffe auf 74/76/78/82, Lesen von 4122), sobald Adresse 74 antwortet | API-Registermodell, Vertragstests, FHEM-Mitschnitt gegen ein echtes 1.7 (Issue #319) | Eigene Protokollfamilie; automatische Erkennung über die Illegal-Data-Address-Signatur, manueller Modell-Override verfügbar. Holding-Schreibzugriffe sind EEPROM-begrenzt (300 000 Zyklen pro Register). Deaktiviere das lokale Web-Supplement; eine 1.x-Weboberfläche ist nicht bekannt. |
| Navigator Pro / Zonenmodule | expected | unbekannt | Erkannte Zonenmodule, Raumsensoren und Raum-Modi | API-Registermodell, Vertragstests | Braucht einen vollständigen Diagnosebericht; das lokale Web folgt der Navigator-10-WebSocket-Familie. |
| Terra SWM mit Navigator-Regler | expected | unbekannt | Unbekannt | noch kein vollständiger Bericht | Bleibt auf expected, bis Modell, Firmware und Diagnose-Export vorliegen. |
| Unbekanntes künftiges Navigator-Modell | expected | unbekannt | Unbekannt | noch kein vollständiger Bericht | Muss als expected behandelt werden, bis automatische Erkennung und Diagnose die Kompatibilität belegen. |
| Regler vor dem Navigator | unsupported | beliebig | keine | Architektur-Review | Ältere Regler verwenden andere Kommunikations- und Registermodelle. |

## Anforderungen an Berichte

Bitte nenne diese Felder, wenn du Kompatibilität meldest:

- Wärmepumpenmodell und Navigator-/Regler-Modell.
- Firmware-Version aus der Diagnose.
- Version der Integration und Version von `idm-heatpump-api`.
- Aktive Heizkreise, Zonenmodule sowie PV-, Solar-, ISC- und Kaskade-Flags.
- Geschwärzter Home-Assistant-Diagnose-Export.
- Ob der Bericht rein lesend ist oder verifizierte Schreibaktionen enthält.

Veröffentliche keine privaten IP-Adressen, Hostnamen, Ports, die dein Netzwerk identifizieren, Seriennummern oder Installateur-/Kundendaten.

Regler-Generation, Wärmepumpen-Produktname und erkannte optionale Funktionen werden separat erfasst. Ein Familienname allein belegt nicht, dass PV-, Solar-, ISC-, Kaskaden- oder Zonen-Hardware installiert ist.
