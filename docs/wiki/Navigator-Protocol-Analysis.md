# Navigator-Protokollanalyse

Diese Seite dokumentiert bestätigte Erkenntnisse aus der statischen Analyse
des Navigator-Clients und der lesenden Validierung einer Navigator-10-Anlage.
Sie ist keine vollständige Protokollspezifikation.

## Bestätigte lokale Kommunikation

- Modbus TCP: Port `502`, Unit/Slave-ID `1`.
- Lokale HTTP-Oberfläche: Port `80`.
- Navigator-10-WebSocket: Port `61220`.
- WebSocket-Authentifizierung über den lokalen PIN als `auth_code`.
- Navigator-2.0-Webzugang: lokales HTTP auf Port `80`, Formularanmeldung mit
  CSRF-Token und lokalem Netzwerkcode.
- Navigator Pro verwendet für den implementierten Webzugang die
  Navigator-10-WebSocket-Variante.
- Webdaten werden als typisierte Werte mit Einheiten oder übersetztem Status
  geliefert.

Die Integration verwendet deshalb weiterhin Modbus als Basispfad und die
lokale Webschnittstelle nur als optionale Ergänzung beziehungsweise Fallback.
Es werden keine Cloud-Anmeldungen benötigt.

## Erkennung und Wiederverbindung

Bei Einrichtung, Neukonfiguration und Reparatur wird die durch Modbus
wahrscheinlichste Variante zuerst getestet und bei Fehlschlag auch die andere
lokale Variante geprüft. Gespeichert wird ausschließlich der tatsächlich
erfolgreiche Client. Im normalen Betrieb wird diese Sitzung wiederverwendet.
Nach Sitzungs- oder Transportfehlern wird derselbe Protokollclient neu
aufgebaut; die andere Navigator-Generation wird bewusst nicht probeweise
aktiviert. Eine erneute beidseitige Erkennung erfolgt über Neukonfiguration
beziehungsweise solange noch keine verlässliche Variante gespeichert ist.

Details: [Local Navigator Web Interface](Local-Web-Interface).

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
Varianten, weitere TCP/TLS-Kommunikationspfade, Live-Ereignisse wie `NC_CHANNELDATA`,
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

## Hinweis zur KNX-Beispielprojekt-Datei (.knxproj)

Gelegentlich liegt eine IDM-spezifische ETS-Projektdatei vor (Bezeichnung
wie `KNX_NAVIGATOR_2_0_Beispielprojekt.knxproj`). Diese Datei beschreibt
das **KNX-Gateway** (typischerweise ein Weinzierl `KNX IP BAOS 774`) und
die darauf aktivierten Kommunikationsobjekte. Sie ist **keine** verlässliche
Quelle für IDM-Modell- oder Firmwareerkennung.

### Was die `.knxproj`-Datei NICHT liefert

- kein IDM-Wärmepumpenmodell
- keine IDM-Navigator-Generation (Navigator 2.0 / 10 / Pro)
- keine IDM-Firmware- oder Softwareversion
- keine IDM-Seriennummer

Die darin enthaltenen Metadaten wie `ApplicationVersion="16"`,
`VersionNumber="256"`, `MaskVersion="MV-07B0"`, `SerialNumber="KNX IP BAOS 774"`,
Projektname (`"KNX Navigator 2.0"`) und Gerätenamen (`"IDM NAV2.0 KNX IP Gateway"`)
identifizieren ausschließlich das KNX-Gateway beziehungsweise das
ETS-Projekt. Sie dürfen **niemals** als IDM-Firmware oder IDM-Modell
übernommen werden. Free-Form-Label wie „Navigator 2.0" im Projektnamen sind
kein Ersatz für eine Modbus- oder Web-Erkennung.

### Was die `.knxproj`-Datei liefert

Die aktivierten Kommunikationsobjekte sind eine wertvolle
**Vollständigkeits- und Namensreferenz**. Eine korrigierte Vollauswertung
der genannten Beispielprojektdatei (Stand 27.07.2026, 726 aktive Objekte)
wurde am selben Tag durch eine streng lesende Live-Prüfung an einer
Navigator-10-Anlage quergeprüft. Dabei wurden alle hypothetischen Zuordnungen
bestätigt:

| KNX-Objekt | ETS-Name (z. T. mit Tippfehler) | API-Register | Adresse | Typ | Live-Wert |
|---:|---|---|---:|---|---:|
| 995 | Photovotaik Surplus | `pv_surplus` | 74 | FLOAT kW | plausibel |
| 996 | Photovotaik current | `pv_production` | 78 | FLOAT kW | plausibel |
| 992 | Home Consumption | `house_consumption` | 82 | FLOAT kW | plausibel |
| 993 | Battery Discharge | `battery_discharge` | 84 | FLOAT kW | plausibel |
| 994 | Battery state of charge | `battery_soc` | 86 | **INT16 %** | `−1` = Sentinel |
| 997 | Total electric output | `power_consumption_hp` | 4122 | FLOAT kW | plausibel |
| 998 | Current thermal output | `thermal_power_flow_sensor` | 4126 | FLOAT kW | plausibel |
| 999 | Total thermal energy | `total_heat_energy` | 4128 | FLOAT kWh | plausibel |

Zusätzlich bestätigt: `electric_heater_power` (Adresse 76) und
`pv_target_value` (Adresse 88) sind in der API enthalten, aber im
Beispiel-Projekt nicht aktiv.

### Wichtige Interpretationsregeln

- **KNX-Objektnummer ≠ Modbus-Adresse** (die Nummern 992–999 sind keine Adressen).
- **KNX-DPT ≠ Modbus-Datentyp** (z. B. ist `battery_soc` ein einzelnes
  signiertes INT16-Register, kein Zweitregister-Float).
- **KNX-WriteFlag ≠ Modbus-Schreibrecht**. Ein aktiviertes WriteFlag bedeutet
  nur, dass das Objekt Telegramme vom Bus annimmt; es ist kein Beleg für
  einen sicheren Modbus-Schreibzugriff.
- **`battery_soc` Sentinel**: Der Rohwert `65535` (unsigned 16-bit) ist
  vorzeichenbehaftet als `−1` zu dekodieren und bedeutet „nicht verfügbar".
  Eine UINT16-Dekodierung würde fälschlich `65535 %` anzeigen.

### Konsequenz für diese Integration

Die Modell- und Firmwareerkennung bleibt ausschließlich bei Modbus
(`detect_model()`) und dem optionalen lokalen Web-Supplement. Es gibt keinen
Code-Pfad, der ETS- oder BAOS-Metadaten auswertet. Die entsprechenden
Regressions-tests finden sich in `tests/test_knx_evidence.py`. Eine
Erweiterung um neue Register oder Schreibservices ist aus dieser Datei allein
nicht gerechtfertigt; siehe Abschnitt „Bewusst nicht implementiert".
