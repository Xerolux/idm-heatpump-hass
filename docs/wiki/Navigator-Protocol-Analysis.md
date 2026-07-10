# Navigator-Protokollanalyse

Diese Seite dokumentiert bestätigte Erkenntnisse aus der statischen Analyse
des Navigator-Clients und der lesenden Validierung einer Navigator-10-Anlage.
Sie ist keine vollständige Protokollspezifikation.

## Bestätigte lokale Kommunikation

- Modbus TCP: Port `502`, Unit/Slave-ID `1`.
- Lokale HTTP-Oberfläche: Port `80`.
- Navigator-10-WebSocket: Port `61220`.
- WebSocket-Authentifizierung über den lokalen PIN als `auth_code`.
- Webdaten werden als typisierte Werte mit Einheiten oder übersetztem Status
  geliefert.

Die Integration verwendet deshalb weiterhin Modbus als Basispfad und die
lokale Webschnittstelle nur als optionale Ergänzung beziehungsweise Fallback.
Es werden keine Cloud-Anmeldungen benötigt.

## Anlagenvalidierung

Die validierte Anlage wurde als **Navigator 10** erkannt. Der korrigierte API-
Detektor erkennt dort nur Heizkreis **A**. Die Register der nicht konfigurierten
Heizkreise antworten zwar, liefern aber den Sentinelwert `-1.0`.

Der Kaskaden-Probe an Adresse `1147` antwortet auf dieser Anlage mit dem
Rohwort `FFFF` beziehungsweise UCHAR `255`. Dieser Wert ist „nicht verfügbar“
und darf die optionale Kaskaden-Registergruppe nicht aktivieren. Dadurch sank
die erkannte Karte auf dieser Anlage von 170 auf 153 Definitionen.

In 309 lesenden Batch-/Einzelvergleichen über 170 Definitionen und 45 Gruppen
gab es keine Rohwert-Abweichung. Die gemeldeten Werte `254`, `255` und `-1.0`
waren registerbezogene Nicht-verfügbar-Sentinels. Raum-Betriebsarten bleiben
trotzdem einzeln abgesichert, weil andere Navigator-2.0-Berichte plausible,
aber abweichende Batch-Werte gezeigt haben.

Der lokale Webclient lieferte 60 normalisierte Werte, darunter Temperaturen,
Drücke, Laufzeiten, Energiemengen, Statuswerte und die Softwareversion. Es
werden keine PINs, Tokens, IP-Adressen, Seriennummern, Account-IDs oder
Rohantworten im Repository gespeichert.

## Erkenntnisse aus der EXE-Analyse

Erkannt wurden mehrere Navigator-Generationen, UDP-Discovery für ältere
Varianten, TCP/TLS für Navigator 2.0, Live-Ereignisse wie `NC_CHANNELDATA`,
typisierte Kanalwerte sowie dynamische Kanäle, Parameter, Räume, Fehler,
Übersetzungen und virtuelle Kanäle.

Die konkreten Kanalnummern, Einheiten, Skalierungen, Byte-Reihenfolgen und
Sondertypen wie `UDP_FUNCFLOAT` sind damit noch nicht sicher bestimmt.

## Bewusst nicht implementiert

- myIDM-Cloud-Login, Cloud-Polling und Anlagenverwaltung
- Firmware-, Konfigurations- und SD-Karten-Schreibvorgänge
- feste UDP-Ports oder geratene Binärpakete
- geratene Kanalbedeutungen, Einheiten oder Skalierungsfaktoren
- nicht dokumentierte Modbus-Schreibzugriffe

Für weitere Protokollarbeit benötigen wir anonymisierte lokale Antworten oder
Aufzeichnungen mit Kanal-ID, Name, Einheit, Skalierung, Datentyp,
Raumzuordnung und Live-Event. Vor dem Commit müssen PINs, Tokens,
Netzwerkdaten, Seriennummern und Eigentümerdaten entfernt werden.
