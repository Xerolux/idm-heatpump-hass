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

## IDM-Controller-ID-Räume

Eine physikalische Größe wird auf einem IDM Navigator Controller von bis zu
**drei unabhängigen ID-Räumen** adressiert. Diese Räume überlappen sich
semantisch, sind aber **nicht** 1:1, und die Nummern sind bewusst
unterschiedlich. Sie dürfen niemals als austauschbare Adressen verwendet
werden.

| ID-Raum | Verwendung | Beispiel Heizen | Beispiel PV-Überschuss |
|---|---|---:|---:|
| **Modbus-Register** | externes Protokoll, via `idm-heatpump-api` | 1748 | 74 |
| **Interne Stats-ID** | Statistik-Engine, SD-Karte (`stats/amount/<id>_v1.csv`, `last_values.json`) | 477 | 495 (kumuliert: 100495) |
| **KNX-Kommunikationsobjekt** | ETS-Beispielprojekt (Weinzierl BAOS 774) | 400 | 995 |

### Was das in der Praxis bedeutet

- **KNX-Objektnummer ≠ Modbus-Adresse** (schon im KNX-Abschnitt festgehalten).
- **Interne Stats-ID ≠ Modbus-Adresse**. Beispiel: Heizenergie hat die interne
  Stats-ID `477`, aber die Modbus-Adresse `1748`. Eine Fehlermeldung der Form
  „Stat 477" auf dem Controller-Display entspricht also dem Modbus-Wert unter
  Adresse `1748` und nicht etwa einer Lücke im Modbus-Adressraum.
- **Interne Stats-ID ≠ KNX-Objektnummer**. Beispiel: PV-Überschuss hat
  intern die ID `495`, im KNX-Beispielprojekt aber die Objektnummer `995`.
- **Kumulierte Stat-IDs** im 100000er-Bereich (z. B. `100495`) sind die
  Tages-Summen der zugrundeliegenden Serie (`495`), keine eigene physikalische
  Größe.

### Syscount-Querverweis (Energieregister)

Die Datei `syscount.ini` auf der SD-Karte enthält die semantischen Bezeichnungen
der kumulierten Zähler. Diese Integration hält eine cross-geprüfte
Zuordnungstabelle in
[`custom_components/idm_heatpump/controller_stats_reference.py`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/custom_components/idm_heatpump/controller_stats_reference.py)
bereit. Sie ist unvollständig dokumentiert: nur Register, die über mindestens
zwei der drei ID-Räume quergeprüft wurden, sind enthalten.

| Syscount-Key | Stats-ID | Library-Register | Modbus | KNX-Objekt | Bedeutung |
|---|---:|---|---:|---:|---|
| `ZQHPH` | 477 | `energy_heating` | 1748 | 400 | Wärmemenge Heizen (Wärmepumpe) |
| `ZQHPP` | 471 | `energy_dhw` | 1754 | 402 | Wärmemenge Warmwasser / Priority |
| `ZQHPD` | 472 | `energy_defrost` | 1756 | 403 | Wärmemenge Abtauen |
| `ZQHPC` | — | `energy_cooling` | 1752 | 401 | Wärmemenge Kühlen |
| `ZQELH` | — | `energy_electric_heater` | 1762 | 406 | Wärmemenge Elektroheizstab |
| `ZQHPO` | — | `total_heat_energy` | 4128 | 999 | Wärmemenge gesamt (Nav10) |
| — | 495 | `pv_surplus` | 74 | 995 | Photovoltaik-Überschuss |
| — | 496 | `pv_production` | 78 | 996 | Photovoltaik-Leistung |
| — | — | `house_consumption` | 82 | 992 | Hausverbrauch |
| — | — | `battery_discharge` | 84 | 993 | Batterieentladung |
| — | — | `battery_soc` | 86 | 994 | Batterieladezustand (INT16, `-1` = n. v.) |
| — | — | `power_consumption_hp` | 4122 | 997 | Elektrische Gesamtleistung |
| — | — | `thermal_power_flow_sensor` | 4126 | 998 | Thermische Leistung |

### Verwendung im Diagnose-Export

Der Diagnose-Export der Integration (``Download diagnostics`` in der
Integration-Seite) enthält für jeden bekannten Energieregister den
zusätzlich cross-referenzierten `syscount`-Schlüssel. So lässt sich ein
Plausibilitätsvergleich zwischen Home-Assistant-Reading und
Controller-eigenem Zählerstand durchführen, ohne die SD-Karte ausbauen zu
müssen.

### Begrenzung des Befunds

Diese Tabelle wurde an einer bestätigten Navigator-10-Anlage (Firmware
`NAV10_20.24-880-g265e09c4a`) erhoben. Für Navigator 2.0 / Pro gelten
möglicherweise abweichende Stats-IDs; die Syscount-Schlüsselnamen sollten
dagegen generisch sein. Neue Einträge erfordern stets den Abgleich über
mindestens zwei der drei ID-Räume (Modbus + syscount, oder Modbus + KNX).

## SD-Karten-Struktur (Navigator 10)

Eine SD-Karte aus einem Navigator 10 enthält typischerweise folgende
verwertbare Strukturen:

```
/
├── log/raw/<controller_id>/<YYMMDD>.mal   # binäre Tageslogs, proprietär
├── recovery/
│   ├── Backup/config/<YYYY-MM-DD_HHMM>/   # tägliche 2:00-Uhr-Snapshots
│   └── autosaveconfig_<controller_id>--<id>/config/<YYYY-MM-DD_HHMM>/
└── update/backup/backup<YYYYMMDDHHMMSS>.iup   # Firmware-Backup-Pakete
```

Der Snapshot eines Konfigurations-Backups enthält unter anderem:

| Datei | Inhalt | Verwendbar für |
|---|---|---|
| `syscount.ini` | kumulierte Zähler (`ZQHPH`, `ZQHPP` etc.) | semantischer Querverweis |
| `stats/amount/<id>_v1.csv` | Tageszeitreihe pro Stats-ID | Plausibilitätsvergleich |
| `stats/amount/last_values.json` | letzter kumulierter Wert pro Stats-ID | Plausibilitätsvergleich |
| `stats/amount/heating.csv`, `priority.csv` | benannte Tageszeitreihen | Plausibilitätsvergleich |
| `stats/energy/ba_energy_hp`, `ba_energy_eh` | binäre Energie- und Stablöcher | Strukturverweis |
| `stats/pv/ba_pv` | binäre PV-Tageszeitreihe (9 Spalten) | Strukturverweis |
| `stats/runtimes/ba_runtimes`, `bivalence_runtimes` | binäre Laufzeitstatistiken | Strukturverweis |
| `zone.ini` | konfigurierte Zonen (`size=0` = keine) | Erkennungs-Konsistenz |
| `heatpump.ini` | Fehlerpuffer-Position (keine Serial!) |_low value_ |
| `frwaparam.ini` | Firmware-Parameter (FRW*/FRWA*) | low value |
| `hparam.ini`, `iparam.ini` | Heiz-/Installationsparameter | **nicht committen** (Anlagenspezifika) |
| `errorLogBuffer.ini`, `paramLogBuffer.ini` | Fehler-/Parameter-Logs | **nicht committen** |

Diese Integration liest keine SD-Karte aus. Die obige Struktur ist lediglich
für Supportzwecke dokumentiert; wenn User Werte vergleichen möchten, können
sie die entsprechenden CSV-Dateien manuell against ihre HA-Sensoren prüfen.

## Navigator 10 WebSocket – Controller-Katalog

Die Navigator-10-Weboberfläche spricht ein WebSocket-Protokoll auf Port
`61220`. Jeder Frame hat die Form `{"controller": "<name>", "command":
"<verb>", "data": {...}}`. Authentifizierung erfolgt per Query-Parameter
`?auth_code=<PIN>` beim Verbindungsaufbau.

Die folgende Tabelle ist das Ergebnis einer streng lesenden Live-Erkundung
(`overview`/`detail` nur) an einer bestätigten Navigator-10-Anlage (Firmware
`NAV10_20.24-880-g265e09c4a`, Juli 2026). Sie ersetzt das frühere, unvollständige
Bild aus der statischen EXE-Analyse.

### Unterstützte Controller

| Controller | Commands | Bedeutung |
|---|---|---|
| `status` | `overview` | Authorisierungsstatus (`{"authorized":true}`) |
| `home` | `overview`, `detail` | Startbildschirm-Status (Frostschutzinfo, Auth aktiv, Demo-Modus, Header) und Detaildaten inkl. Energy-Flow (PV, Hausverbrauch, Grid) |
| `system` | `overview` | System-Detailblock (Energiemengen heute, Typ-Wörterbuch) |
| `system.freshwater` | `overview` | DHW-Detail (Zirkulation, StatusInfo, SystemMode, Temperaturen) |
| `setting` | `detail`, `save`, `execute` | Settings lesen (`detail`), schreiben (`save`), Aktionen auslösen (`execute`) |
| `statistic` | `overview`, `detail` | Statistikblöcke |
| `notification` | `overview`, `save` | Meldungsübersicht, Meldungsänderung |
| `authentication` | `overview` | Systeminformation (buffer.systemMode, temperatures, energyflow) |
| `showcase` | `overview` | Demo-/Info-Sequenzen |
| `frostprotection` | `overview` | Frostschutz-Wizard (nur aktiv im Frostfall) |
| `relaytest` | `overview` | Relaistest-Wizard (nur im Service-Fall aktiv) |

**Subcontroller-Muster**: Die `system.*`-Subcontroller (z. B. `system.freshwater`)
nutzen im `data`-Block `parameterId` statt `settingId`. Die Bibliothek
verwendet derzeit nur `setting/detail`, `statistic/detail` und
`notification/overview`.

**Setting-Aktionstypen** (via `setting/execute`): Der SPA-Code ordnet Settings
anhand ihres `type`-Feld bestimmten UI-Komponenten zu. Bekannte Aktionstypen
sind `restart`, `actioncode`, `execute`, `relaytest`, `tt1`, `ttw`, `ttboost`.
`execute` ist dabei der generische „Aktion auslösen"-Typ, der die im Setting
hinterlegte Funktion serverseitig anstößt. Beispielsweise ist der
„Display neu starten"-Button als Setting vom Typ `restart` implementiert und
wird über `setting/save` mit dem zugehörigen Setting-ID ausgelöst.

### Nicht unterstützte Controller

Folgende Controller-Namen wurden probiert und vom Navigator 10 **ausdrücklich
als nicht unterstützt** zurückgewiesen (`provided controller [...] is not
supported!`):

```
controller        firmware         update          upgrade
software          usb              upload          maintenance
system.update     system.firmware  system.software system.usb
does.not.exist    (Negativkontrolle)
```

### Konsequenz: Firmware-Update

Die Navigator-10-WebSocket-Schnittstelle **bietet keinen Update-Endpunkt**.
Dasselbe gilt für die HTTP-Oberfläche (Port 80, reine SPA, keine serverseitigen
Update-Routen) und Modbus TCP (Port 502). Die drei lokalen Schnittstellen des
Controllers decken den normalen Lese-/Schreibbetrieb ab, aber keine
Firmware-Operationen.

Firmware-Updates beim Navigator 10 erfolgen dementsprechend über:

1. **myIDM Cloud-Portal** (`app.myidm.at`) – das kanonische Web-Interface, das
   im Framework als „IDM web interface" bezeichnet wird. Push-Aktualisierungen
   laufen in der Regel automatisch über diesen Kanal ein.
2. **USB-Stick** über den Controller-Display-Service-Menü (Fachmann-Ebene).
   Die Integration berechnet die zeitabhängigen *Fachmann Ebene* Codes
   (L1/L2) und stellt sie als optionale Sensoren zur Verfügung. Am Display
   selbst lässt sich dann nach einem „Update" / „Software" / „USB"-Menüpunkt
   suchen.

### Erkundungs-Hinweise für Support

Wenn Nutzer nach Firmware-Updates fragen, ist die Antwort klar:

- Lokal über Web oder WebSocket: **nicht möglich**, alle Update-Controller
  werden vom Gerät abgelehnt.
- Cloud (myIDM): primärer Update-Kanal.
- USB + Display: sekundärer Service-Kanal.

Eine Erweiterung der Integration um eigene Update-Funktionen ist nicht
geplant und würde den bewussten Einschluss von Cloud-Funktionen erfordern
(siehe Abschnitt „Bewusst nicht implementiert").
