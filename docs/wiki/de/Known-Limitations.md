# Bekannte Einschränkungen

## Gerätekompatibilität

- Für den Navigator 10 liegt eine direkte Hardware-Bestätigung der Maintainer vor.
  Navigator 2.0 und Navigator Pro werden aufgrund des typisierten Registermodells
  erwartet, benötigen aber noch vollständige Diagnosen über aktuelle
  Firmware-Varianten hinweg.
- Ältere IDM-Regler ohne Navigator-Firmware werden **nicht** unterstützt
- Die Modbus-Registerzuordnung kann sich zwischen Firmware-Versionen leicht
  unterscheiden

## Modbus TCP

- Es wird nur **Modbus TCP** unterstützt (kein serielles Modbus RTU)
- Port und Slave-ID müssen korrekt konfiguriert sein
- Manche Regler-/Firmware-Kombinationen erlauben nur begrenzt parallele Modbus-Clients. Wenn Timeouts mit einem anderen Automationssystem zusammenhängen, teste mit gestopptem Client oder erhöhe das Abfrageintervall

## Schreibfrequenz

- Einige Modbus-Register liegen im EEPROM-Speicher des Reglers und erlauben über
  die Hardware-Lebensdauer nur begrenzte Schreibzyklen.
- Die Integration protokolliert eine Warnung, wenn dieselbe Registeradresse
  innerhalb von 5 Sekunden mehrfach beschrieben wird; das hilft, durchlaufende
  Automationsschleifen zu erkennen.
- Bei der rohen `write_register`-Aktion müssen Nutzer das Risiko ausdrücklich
  bestätigen. Kein automatischer Hard-Block verhindert häufige
  EEPROM-Schreibvorgänge — gehe mit unbekannten Adressen sorgfältig um.

## Ein Gerät pro Konfigurationseintrag

- Mehrere IDM-Wärmepumpen werden unterstützt. Jede Verbindung muss eine eindeutige Kombination aus Host, Port und Slave-ID haben.
- Bei mehreren Wärmepumpen am selben Bus: verwende separate Slave-IDs und lege für jede einen eigenen Eintrag an

## Schreibgeschützter Zugriff auf bestimmte Register

- Einige Register sind **schreibgeschützt** (z. B. Energiezähler, Temperaturfühler)
- Schreibversuche auf schreibgeschützte Register können einen Modbus-Fehler zurückgeben
- Die `write_register`-Aktion erlaubt absichtlich eine ausdrücklich bestätigte benutzerdefinierte Adresse, prüft aber weiterhin Datentyp und numerische Kodierung. Sichere Bereiche, EEPROM-Verhalten oder die Semantik unbekannter Adressen kann sie nicht ableiten — **nur für erfahrene Nutzer**

## Zonenmodule

- Unterstützt werden maximal **10 Zonenmodule** mit jeweils bis zu **8 konfigurierbaren Räumen**. Sechs Räume sind die aktuelle Navigator-10-Standardeinstellung; konfiguriere nur physisch vorhandene Räume.

## Modell- und Firmware-Nachweise

- Für den Navigator 10 liegt direkte Hardware-Abdeckung durch die Maintainer vor.
- Navigator 2.0 und Navigator Pro bleiben abhängig von vollständigen Community-Diagnosen über Firmware-Varianten hinweg.
- Eine antwortende Probe-Adresse allein beweist nicht zwingend, dass ein optionales Feature existiert; Sentinelwerte für Nicht-Verfügbarkeit werden berücksichtigt, wo Hardware-Nachweise existieren.
- Siehe [Stabilität & Release-Reife](Stability-and-Release-Readiness) für die aktuellen Blocker, bevor das Beta-Label entfernt wird.
- Die Zonenmodul-Konfiguration ist nach der Ersteinrichtung über die Optionen anpassbar
- Räume ohne physischen Sensor können `-1.0` als Wert liefern (als nicht verfügbar markiert)

## Geplante Updates statt HA-Push-Updates

- Der Home-Assistant-Zustand wird über geplante Modbus- und optionale
  Web-Aktualisierungen aktualisiert. Die Integration stellt unangeforderte
  Regler-Ereignisse derzeit nicht als unmittelbare Home-Assistant-Push-Updates
  bereit.
- Änderungen, die anderswo vorgenommen werden, werden nach dem jeweiligen
  Aktualisierungsintervall sichtbar.

## Firmware-Version

- Die aktuelle Firmware-Version wird als Diagnose-Sensor (`firmware_version`) gelesen
- Firmware-Updates direkt aus Home Assistant sind **nicht** möglich
- Updates erfolgen über das **myIDM-Cloud-Portal** oder über einen **USB-Stick
  über das Service-Menü des Regler-Displays** (freigeschaltet mit den
  *Fachmann-Ebene*-Codes, die die Integration berechnen kann).
- Die drei vom Regler bereitgestellten lokalen Schnittstellen (Modbus TCP 502,
  Navigator HTTP 80, Navigator 10 WebSocket 61220) tragen **keinen**
  Firmware-Update-Endpunkt. Alle in Betracht kommenden WebSocket-Controller
  (`firmware`, `update`, `upgrade`, `software`, `usb`, `upload`,
  `maintenance`, `system.update`, `system.firmware`, `system.software`,
  `system.usb`) antworten mit `provided controller [...] is not supported!`.
  Siehe die [Navigator-Protokollanalyse](Navigator-Protocol-Analysis) für den
  vollständigen verifizierten Controller-Katalog.

## Bewusst nicht implementiert

- **Web-Verbindung als Kernpfad:** Der Modbus-Betrieb hängt nicht von einem
  Web-Login ab. Das optionale schreibgeschützte Web-Supplement nutzt die
  unterstützte lokale Navigator-HTTP- oder WebSocket-Sitzung und kann einen
  begrenzten Fallback im reinen Web-Betrieb bieten.
- **Globales `force_update`:** Standardmäßig nicht aktiviert. Externe
  Zeitreihensysteme sollten Recorder-/InfluxDB-Konfiguration oder ausgewählte
  Hilfs-Sensoren verwenden, um unnötige Home-Assistant-Datenbanklast zu
  vermeiden.
