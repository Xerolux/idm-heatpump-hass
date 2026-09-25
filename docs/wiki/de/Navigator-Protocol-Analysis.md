# Navigator-Protokollanalyse

Diese Seite dokumentiert bestätigte Erkenntnisse aus der statischen Analyse des
Navigator-Clients und aus der rein lesenden Validierung einer Navigator-10-Installation.
Sie ist keine vollständige Protokollspezifikation.

## Bestätigte lokale Kommunikation

- Modbus TCP: Port `502`, Unit-/Slave-ID `1`.
- Lokale HTTP-Schnittstelle: Port `80`.
- Navigator-10-WebSocket: Port `61220`.
- WebSocket-Authentifizierung über die lokale PIN als `auth_code`.
- Navigator-2.0-Webzugriff: lokales HTTP auf Port `80`, Formular-Login mit
  CSRF-Token und dem lokalen Netzwerkcode.
- Für den implementierten Webzugriff nutzt der Navigator Pro die WebSocket-Variante
  des Navigator 10.
- Webdaten werden als typisierte Werte mit Einheiten oder als übersetzter Status
  geliefert.

Die Integration behält daher Modbus als Basispfad bei und nutzt die lokale
Weboberfläche nur als optionales Web-Supplement oder als Fallback. Cloud-Logins
sind nicht erforderlich.

## Erkennung und Wiederverbindung

Bei Einrichtung, Rekonfiguration und Reparatur wird zuerst die Modbus-Variante
versucht, die am wahrscheinlichsten ist, und im Fehlerfall zusätzlich die andere
lokale Variante. Gespeichert wird nur der Client, der tatsächlich erfolgreich war.
Im normalen Betrieb wird diese Sitzung wiederverwendet. Nach Sitzungs- oder
Transportfehlern wird derselbe Protokoll-Client neu aufgebaut; die andere
Navigator-Generation wird bewusst nicht probehalber aktiviert. Eine erneute
Erkennung beider Varianten erfolgt über die Rekonfiguration oder solange noch
keine zuverlässige Variante gespeichert ist.

Details: [Lokale Navigator-Weboberfläche](Local-Web-Interface).

## Validierung der Installation

Die validierte Installation wurde als **Navigator 10** erkannt. Der korrigierte
API-Detektor findet dort nur den Heizkreis **A**. Die Register der nicht
konfigurierten Heizkreise antworten zwar, liefern aber den Sentinel-Wert `-1.0`.

Auf dieser Installation antwortet die Kaskaden-Abfrage an Adresse `1147` mit dem
Rohwort `FFFF`, also UCHAR `255`. Dieser Wert bedeutet „nicht verfügbar“ und darf
die optionale Kaskaden-Registergruppe nicht aktivieren. Dadurch schrumpfte die
ermittelte Registerkarte auf dieser Installation von 170 auf 153 Definitionen.

Bei 309 rein lesenden Batch-/Einzelvergleichen über 170 Definitionen und 45 Gruppen
hinweg gab es keine Abweichung bei den Rohwerten. Die gemeldeten Werte `254`, `255`
und `-1.0` waren registerspezifische „nicht verfügbar“-Sentinels. Raum-Betriebsmodi
werden weiterhin einzeln gesichert, weil andere Navigator-2.0-Berichte plausible,
aber abweichende Batch-Werte gezeigt haben.

Der lokale Web-Client lieferte 60 normalisierte Werte zurück, darunter Temperaturen,
Drücke, Laufzeiten, Energiemengen, Statuswerte und die Softwareversion. Keine PINs,
Tokens, IP-Adressen, Seriennummern, Konto-IDs oder Rohantworten werden im Repository
gespeichert.

## Erkenntnisse aus der EXE-Analyse

Identifiziert wurden mehrere Navigator-Generationen, UDP-Discovery für ältere
Varianten, weitere TCP/TLS-Kommunikationswege, Live-Events wie `NC_CHANNELDATA`,
typisierte Kanalwerte sowie dynamische Kanäle, Parameter, Räume, Fehler,
Übersetzungen und virtuelle Kanäle.

Die konkreten Kanalnummern, Einheiten, Skalierungen, Byte-Reihenfolgen und
Spezialtypen wie `UDP_FUNCFLOAT` sind daher noch nicht zuverlässig bestimmt.

## Bewusst nicht implementiert

- myIDM-Cloud-Login, Cloud-Abfrage und Anlagenverwaltung
- Firmware-, Konfigurations- und SD-Karten-Schreibzugriffe
- feste UDP-Ports oder geratene Binärpakete
- geratene Kanalbedeutungen, Einheiten oder Skalierungsfaktoren
- undokumentierte Modbus-Schreibzugriffe

Weitere Protokollarbeit benötigt anonymisierte lokale Antworten oder Aufzeichnungen
mit Kanal-ID, Name, Einheit, Skalierung, Datentyp, Raumzuordnung und Live-Event.
Vor dem Commit müssen PINs, Tokens, Netzwerkdaten, Seriennummern und Besitzerdaten
entfernt werden.

## Hinweis zur KNX-Beispielprojektdatei (.knxproj)

Gelegentlich ist eine IDM-spezifische ETS-Projektdatei verfügbar (mit einem Namen
wie `KNX_NAVIGATOR_2_0_Beispielprojekt.knxproj`). Diese Datei beschreibt das
**KNX-Gateway** (typischerweise ein Weinzierl `KNX IP BAOS 774`) und die darauf
aktivierten Kommunikationsobjekte. Sie ist **keine** zuverlässige Quelle für die
Erkennung von IDM-Modell oder Firmware.

### Was die `.knxproj`-Datei NICHT liefert

- kein IDM-Wärmepumpenmodell
- keine IDM-Navigator-Generation (Navigator 2.0 / 10 / Pro)
- keine IDM-Firmware- oder Softwareversion
- keine IDM-Seriennummer

Die darin enthaltenen Metadaten wie `ApplicationVersion="16"`,
`VersionNumber="256"`, `MaskVersion="MV-07B0"`,
`SerialNumber="KNX IP BAOS 774"`, der Projektname (`"KNX Navigator 2.0"`) und
Gerätenamen (`"IDM NAV2.0 KNX IP Gateway"`) identifizieren ausschließlich das
KNX-Gateway und das ETS-Projekt. Sie dürfen **niemals** als IDM-Firmware oder
IDM-Modell übernommen werden. Freitext-Bezeichnungen wie „Navigator 2.0“ im
Projektnamen sind kein Ersatz für eine Modbus- oder Web-Erkennung.

### Was die `.knxproj`-Datei liefert

Die aktivierten Kommunikationsobjekte sind eine wertvolle **Vollständigkeits- und
Namensreferenz**. Eine korrigierte vollständige Auswertung dieser
Beispielprojektdatei (Stand 2026-07-27, 726 aktive Objekte) wurde am selben Tag
durch einen strikt lesenden Live-Check auf einer Navigator-10-Installation
gegeneprüft. Alle hypothetischen Zuordnungen wurden bestätigt:

| KNX-Objekt | ETS-Name (teilweise mit Tippfehlern) | API-Register | Adresse | Typ | Live-Wert |
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
`pv_target_value` (Adresse 88) sind in der API enthalten, im Beispielprojekt aber
nicht aktiv.

### Wichtige Auslegungsregeln

- **KNX-Objektnummer ≠ Modbus-Adresse** (die Nummern 992–999 sind keine Adressen).
- **KNX-DPT ≠ Modbus-Datentyp** (beispielsweise ist `battery_soc` ein einzelnes
  vorzeichenbehaftetes INT16-Register, kein Float über zwei Register).
- **KNX-Schreibflag ≠ Modbus-Schreibberechtigung.** Ein aktiviertes Schreibflag
  bedeutet nur, dass das Objekt Telegramme vom Bus annimmt; es ist kein Beleg für
  einen sicheren Modbus-Schreibzugriff.
- **`battery_soc`-Sentinel**: Der Rohwert `65535` (unsigned 16 Bit) muss als
  vorzeichenbehaftetes `−1` dekodiert werden und bedeutet „nicht verfügbar“. Eine
  UINT16-Dekodierung würde fälschlich `65535 %` anzeigen.

### Konsequenz für diese Integration

Modell- und Firmware-Erkennung bleibt ausschließlich Modbus (`detect_model()`) und
dem optionalen lokalen Web-Supplement vorbehalten. Es gibt keinen Codepfad, der
ETS- oder BAOS-Metadaten auswertet. Die zugehörigen Regressionstests liegen in
`tests/test_knx_evidence.py`. Neue Register oder Schreib-Aktionen allein aus dieser
Datei abzuleiten ist nicht gerechtfertigt; siehe den Abschnitt „Bewusst nicht
implementiert“.

## ID-Räume des IDM-Reglers

Auf einem IDM-Navigator-Regler wird eine physikalische Größe über bis zu **drei
unabhängige ID-Räume** adressiert. Diese Räume überlappen sich semantisch, sind
aber **nicht** 1:1, und die Nummern sind bewusst unterschiedlich. Sie dürfen
niemals als austauschbare Adressen verwendet werden.

| ID-Raum | Verwendet von | Beispiel Heizung | Beispiel PV-Überschuss |
|---|---|---:|---:|
| **Modbus-Register** | externes Protokoll, über `idm-heatpump-api` | 1748 | 74 |
| **Interne Stats-ID** | Statistik-Engine, SD-Karte (`stats/amount/<id>_v1.csv`, `last_values.json`) | 477 | 495 (kumulativ: 100495) |
| **KNX-Kommunikationsobjekt** | ETS-Beispielprojekt (Weinzierl BAOS 774) | 400 | 995 |

### Was das in der Praxis bedeutet

- **KNX-Objektnummer ≠ Modbus-Adresse** (bereits im KNX-Abschnitt erwähnt).
- **Interne Stats-ID ≠ Modbus-Adresse.** Beispiel: Heizenergie hat die interne
  Stats-ID `477`, aber die Modbus-Adresse `1748`. Eine Fehlermeldung der Form
  „Stat 477“ auf dem Regler-Display entspricht daher dem Modbus-Wert an Adresse
  `1748` und keiner Lücke im Modbus-Adressraum.
- **Interne Stats-ID ≠ KNX-Objektnummer.** Beispiel: PV-Überschuss hat die interne
  ID `495`, im KNX-Beispielprojekt aber die Objektnummer `995`.
- **Kumulative Stat-IDs** im Bereich 100000 (zum Beispiel `100495`) sind die
  Tagesummen der zugrunde liegenden Reihe (`495`), keine eigene physikalische
  Größe.

### Syscount-Querverweis (Energiesregister)

Die Datei `syscount.ini` auf der SD-Karte enthält die semantischen Namen der
kumulativen Zähler. Diese Integration pflegt eine gegengeprüfte Zuordnungstabelle
in [`custom_components/idm_heatpump/controller_stats_reference.py`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/custom_components/idm_heatpump/controller_stats_reference.py).
Sie ist bewusst unvollständig dokumentiert: enthalten sind nur Register, die über
mindestens zwei der drei ID-Räume gegengeprüft wurden.

| Syscount-Schlüssel | Stats-ID | Bibliotheks-Register | Modbus | KNX-Objekt | Bedeutung |
|---|---:|---|---:|---:|---|
| `ZQHPH` | 477 | `energy_heating` | 1748 | 400 | Wärmemenge Heizen (Wärmepumpe) |
| `ZQHPP` | 471 | `energy_dhw` | 1754 | 402 | Wärmemenge Warmwasser / Priorität |
| `ZQHPD` | 472 | `energy_defrost` | 1756 | 403 | Wärmemenge Abtauen |
| `ZQHPC` | — | `energy_cooling` | 1752 | 401 | Wärmemenge Kühlen |
| `ZQELH` | — | `energy_electric_heater` | 1762 | 406 | Wärmemenge elektrisches Heizelement |
| `ZQHPO` | — | `total_heat_energy` | 4128 | 999 | Wärmemenge gesamt (Nav 10) |
| — | 495 | `pv_surplus` | 74 | 995 | Photovoltaik-Überschuss |
| — | 496 | `pv_production` | 78 | 996 | Photovoltaik-Leistung |
| — | — | `house_consumption` | 82 | 992 | Hausverbrauch |
| — | — | `battery_discharge` | 84 | 993 | Batterie-Entladung |
| — | — | `battery_soc` | 86 | 994 | Batterie-Ladezustand (INT16, `-1` = n. v.) |
| — | — | `power_consumption_hp` | 4122 | 997 | Elektrische Gesamtleistung |
| — | — | `thermal_power_flow_sensor` | 4126 | 998 | Thermische Leistung |

### Verwendung im Diagnose-Export

Der Diagnose-Export der Integration (``Diagnose herunterladen`` auf der
Integrationsseite) enthält für jedes bekannte Energiesregister den gegengeprüften
`syscount`-Schlüssel. Das erlaubt einen Plausibilitätsvergleich zwischen dem
Home-Assistant-Wert und dem eigenen Zähler des Reglers, ohne die SD-Karte zu
entnehmen.

### Grenzen des Befunds

Diese Tabelle wurde auf einer bestätigten Navigator-10-Installation erhoben
(Firmware `NAV10_20.24-880-g265e09c4a`). Navigator 2.0 und Pro können andere
Stats-IDs verwenden; die Syscount-Schlüsselnamen sollten dagegen generisch sein.
Neue Einträge erfordern immer eine Gegenprüfung über mindestens zwei der drei
ID-Räume (Modbus + Syscount oder Modbus + KNX).

## SD-Karten-Struktur (Navigator 10)

Eine SD-Karte aus einem Navigator 10 enthält typischerweise die folgenden
nutzbaren Strukturen:

```
/
├── log/raw/<controller_id>/<YYMMDD>.mal   # binary daily logs, proprietary
├── recovery/
│   ├── Backup/config/<YYYY-MM-DD_HHMM>/   # daily 02:00 snapshots
│   └── autosaveconfig_<controller_id>--<id>/config/<YYYY-MM-DD_HHMM>/
└── update/backup/backup<YYYYMMDDHHMMSS>.iup   # firmware backup packages
```

Der Snapshot eines Konfigurations-Backups enthält unter anderem:

| Datei | Inhalt | Nutzbar für |
|---|---|---|
| `syscount.ini` | kumulative Zähler (`ZQHPH`, `ZQHPP` usw.) | semantischer Querverweis |
| `stats/amount/<id>_v1.csv` | tägliche Zeitreihen je Stats-ID | Plausibilitätsvergleich |
| `stats/amount/last_values.json` | letzter kumulativer Wert je Stats-ID | Plausibilitätsvergleich |
| `stats/amount/heating.csv`, `priority.csv` | benannte tägliche Zeitreihen | Plausibilitätsvergleich |
| `stats/energy/ba_energy_hp`, `ba_energy_eh` | binäre Energie- und Heizelement-Blöcke | Strukturreferenz |
| `stats/pv/ba_pv` | binäre PV-Tageszeitreihen (9 Spalten) | Strukturreferenz |
| `stats/runtimes/ba_runtimes`, `bivalence_runtimes` | binäre Laufzeitstatistiken | Strukturreferenz |
| `zone.ini` | konfigurierte Zonen (`size=0` = keine) | Erkennungskonsistenz |
| `heatpump.ini` | Fehlerpuffer-Position (keine Seriennummer!) | _geringer Wert_ |
| `frwaparam.ini` | Firmware-Parameter (FRW*/FRWA*) | geringer Wert |
| `hparam.ini`, `iparam.ini` | Heiz-/Installationsparameter | **nicht committen** (installationsspezifisch) |
| `errorLogBuffer.ini`, `paramLogBuffer.ini` | Fehler- und Parameter-Logs | **nicht committen** |

Diese Integration liest die SD-Karte nicht. Die obige Struktur ist nur zu
Support-Zwecken dokumentiert; wenn du Werte vergleichen möchtest, kannst du die
entsprechenden CSV-Dateien manuell mit deinen HA-Sensoren abgleichen.

## Navigator-10-WebSocket – Controller-Katalog

Die Weboberfläche des Navigator 10 spricht ein WebSocket-Protokoll auf Port
`61220`. Jeder Frame hat die Form `{"controller": "<name>", "command": "<verb>", "data": {...}}`.
Die Authentifizierung erfolgt beim Verbindungsaufbau über den Query-Parameter
`?auth_code=<PIN>`.

Die folgende Tabelle ist das Ergebnis einer strikt lesenden Live-Exploration
(nur `overview`/`detail`) auf einer bestätigten Navigator-10-Installation
(Firmware `NAV10_20.24-880-g265e09c4a`, Juli 2026). Sie ersetzt das frühere,
unvollständige Bild aus der statischen EXE-Analyse.

### Unterstützte Controller

| Controller | Befehle | Bedeutung |
|---|---|---|
| `status` | `overview` | Autorisierungsstatus (`{"authorized":true}`) |
| `home` | `overview`, `detail` | Status des Startbildschirms (Frostschutz-Info, Authentifizierung aktiv, Demomodus, Kopfzeile) und Detaildaten einschließlich Energiefluss (PV, Hausverbrauch, Netz) |
| `system` | `overview` | System-Detailblock (Energiemengen heute, Typenverzeichnis) |
| `system.freshwater` | `overview` | Warmwasser-Detail (Zirkulation, StatusInfo, SystemMode, temperatures) |
| `setting` | `detail`, `save`, `execute` | Einstellungen lesen (`detail`), schreiben (`save`), Aktionen auslösen (`execute`) |
| `statistic` | `overview`, `detail` | Statistikblöcke |
| `notification` | `overview`, `save` | Nachrichtenübersicht, Nachrichtenänderung |
| `authentication` | `overview` | Systeminformationen (buffer.systemMode, temperatures, energyflow) |
| `showcase` | `overview` | Demo- und Info-Sequenzen |
| `frostprotection` | `overview` | Frostschutz-Assistent (nur in einer Frostsituation aktiv) |
| `relaytest` | `overview` | Relaistest-Assistent (nur in einer Servicesituation aktiv) |

**Sub-Controller-Muster**: Die `system.*`-Sub-Controller (zum Beispiel
`system.freshwater`) verwenden im `data`-Block `parameterId` statt `settingId`.
Die Bibliothek nutzt derzeit nur `setting/detail`, `statistic/detail` und
`notification/overview`.

**Einstellungs-Aktionstypen** (über `setting/execute`): Der SPA-Code ordnet
Einstellungen anhand ihres `type`-Felds bestimmten UI-Komponenten zu. Bekannte
Aktionstypen sind `restart`, `actioncode`, `execute`, `relaytest`, `tt1`, `ttw`,
`ttboost`. `execute` ist der generische Typ „Aktion auslösen“, der serverseitig
die im Setting hinterlegte Funktion startet. Die Schaltfläche „Display neu
starten“ ist beispielsweise als Einstellung vom Typ `restart` implementiert und
wird über `setting/save` mit der entsprechenden Setting-ID ausgelöst.

### Nicht unterstützte Controller

Die folgenden Controllernamen wurden ausprobiert und vom Navigator 10
**ausdrücklich als nicht unterstützt zurückgewiesen** (`provided controller [...]
is not supported!`):

```
controller        firmware         update          upgrade
software          usb              upload          maintenance
system.update     system.firmware  system.software system.usb
does.not.exist    (negative control)
```

### Konsequenz: Firmware-Update

Die WebSocket-Schnittstelle des Navigator 10 **bietet keinen Update-Endpunkt**.
Dasselbe gilt für die HTTP-Schnittstelle (Port 80, eine reine SPA ohne
serverseitige Update-Routen) und für Modbus TCP (Port 502). Die drei lokalen
Schnittstellen des Reglers decken den normalen Lese-/Schreibbetrieb ab, aber
keine Firmware-Operationen.

Firmware-Updates auf dem Navigator 10 erfolgen dementsprechend über:

1. **das myIDM-Cloud-Portal** (`app.myidm.at`) — die kanonische Weboberfläche,
   die das Framework als „IDM-Weboberfläche“ bezeichnet. Push-Updates kommen in
   der Regel automatisch über diesen Kanal.
2. **einen USB-Stick** über das Service-Menü des Regler-Displays
   (Fachmann-Ebene). Die Integration berechnet die zeitabhängigen Codes der
   *Fachmann-Ebene* (L1/L2) und bietet sie als optionale Sensoren an. Auf dem
   Display selbst kannst du dann nach einem Menüpunkt „Update“ / „Software“ /
   „USB“ suchen.

### Explorationsnotizen für den Support

Wenn Nutzer nach Firmware-Updates fragen, ist die Antwort eindeutig:

- Lokal über die Weboberfläche oder den WebSocket: **nicht möglich**, das Gerät
  lehnt alle Update-Controller ab.
- Cloud (myIDM): der primäre Update-Kanal.
- USB plus Display: der sekundäre Service-Kanal.

Die Integration um eigene Update-Funktionen zu erweitern ist nicht geplant und
würde bedeuten, Cloud-Funktionen bewusst einzubeziehen (siehe den Abschnitt
„Bewusst nicht implementiert“).

## myIDM-Cloud-API (Referenz)

Die myIDM-Cloud (`app.myidm.at`, `www.myidm.at`, `a.myidm.at`) ist IDMs
kanonischer Telemetrie- und Steuerkanal. Die Integration nutzt sie **nicht**
(siehe „Bewusst nicht implementiert“), aber die folgenden Erkenntnisse wurden im
Juli 2026 über einen strikt lesenden Live-Login verifiziert (nur `/api/user/login`
+ `/api/installation/values`, kein `/api/installation/command`) und werden hier
als Referenz dokumentiert, um künftige Recherchen zu erleichtern.

### ⚠️ Legacy-API (verifiziert für 2022–2026)

Die hier dokumentierte API ist die **alte v0-API**, die seit mindestens 2018 in
Verwendung ist (Tom Beyer, [beyer.app](https://beyer.app/posts/2018-10-home-assistant-integration-heatpump-idm-terra-ml-complete/))
und 2022 vom ioBroker-Adapter
[`lonestar2001/ioBroker.idm`](https://github.com/lonestar2001/ioBroker.idm)
vollständig reverse-engineered wurde. Sie **funktioniert Stand Juli 2026 noch**,
aber es ist davon auszugehen, dass IDM sie mittelfristig zugunsten der neuen
OAuth2-API abschaltet (siehe unten).

### Endpunkte (alle unter `https://www.myidm.at`)

| Endpunkt | Methode | Zweck | Body (form-urlencoded) |
|---|---|---|---|
| `/api/user/login` | POST | Login, Sitzungs-Token + Anlagenliste | `username=<email>&password=<sha1(password)>` |
| `/api/installation/values` | POST | die aktuellen Werte einer Anlage lesen | `token=<token>&installation=<id>` |
| `/api/installation/command` | POST | den Modus ändern (System/Heizkreis) | `token`, `installation`, `command`, `value`, optional `circuit` |

**Wichtig**:

- `User-Agent: IDM App (iOS)` (oder `Android`) muss gesetzt sein, sonst antwortet
  der Server manchmal nicht.
- Das Passwort wird als **SHA1-Hex-Hash** gesendet (ein veraltetes Schema, kein
  Salt, kein TLS-Pinning).
- Das SSL-Zertifikat der Domain hatte historisch Kettenprobleme; manche Clients
  (zum Beispiel ioBroker) schalten die Verifikation deshalb ab.

### `/api/user/login` – Antwortstruktur

```json
{
  "token": "<64-character hex string>",
  "installations": [
    {
      "id": "64618",
      "name": "<installation name>",
      "config": { ... },
      "nav20": "<bool>",
      "nav20_online": 1,
      "navpro": "<bool>",
      "navpro_online": 0,
      "online": 0
    }
  ]
}
```

Die Felder `nav20_online` / `navpro_online` sind Konnektivitätsmarker der Cloud
und **keine** wörtliche Navigator-Generation — auf einer bestätigten
Navigator-10-Installation ist `nav20_online: 1` gesetzt, offenbar weil die
Cloud-Anbindung generisch über diesen Kanal läuft.

### `/api/installation/values` – Antwortstruktur

Top-Level-Schlüssel der JSON-Antwort:

| Schlüssel | Typ | Bedeutung |
|---|---|---|
| `mode` | string | Systemmodus (zum Beispiel `icon_12`, `icon_auto`) |
| `state` | string | Systemstatus |
| `sum_heat` | string | gesamte Wärmemenge, zum Beispiel `"31549.6 kWh"` (mit Einheit!) |
| `temp_outside` | string | Außentemperatur mit Einheit |
| `temp_heat` | string | Vor-/Rücklauf mit Einheit |
| `temp_hygienic` | string | hygienische Warmwasser-Temperatur mit Einheit |
| `temp_water` | string | Warmwasser-Temperatur mit Einheit |
| `temp_water_params` | dict | `{default, max, min, value}` für den Warmwasser-Sollwert |
| `error` | string/int | Fehleranzahl |
| `errors` | list[...] | Fehlerdetails |
| `circuits` | list[dict] | Heizkreise (siehe unten) |
| `system_mode_params` | list | verfügbare Systemmodi |
| `circuit_mode_params` | list | verfügbare Heizkreis-Modi |
| `solar_mode_params` | list | Solar-Modi (wo unterstützt) |
| `online`, `nav20_online`, `navpro_online` | int | Konnektivitätsstatus |

Je Heizkreis (`circuits[i]`):

```
info, mode, sensor_hum, state, temp_forerun, temp_forerun_actual,
temp_params_eco, temp_params_normal, temp_room, temp_room_actual,
temp_room_value
```

Werte kommen typischerweise als Strings **mit Einheiten-Suffix** an (zum
Beispiel `"52.7 °C"`), die der Client abtrennen muss.

### Icon-Zuordnungen für Modus und Status

IDM kodiert Modi und Zustände als Icon-Klassennamen (HTML/CSS-Strings), nicht
als numerische Werte. Die folgende Tabelle ist die dekodierte Zuordnung aus
ioBroker.idm und Beyer 2018:

**Systemmodus (`mode`)**

| Icon-String | Bedeutung |
|---|---|
| `icon_12` | aus |
| `icon_auto` | automatisch |
| `icon_3` | Warmwasser / einmalige Warmwasserladung |

**Systemstatus (`state`)**

| Icon-String | Bedeutung |
|---|---|
| `icon_12` | aus |
| `icon_3` | Heizen für Warmwasser |
| `icon_5` | Heizen |

**Heizkreis-Modus (`circuits[i].mode`)**

| Icon-String | Bedeutung | numerisch (für `/command`) |
|---|---|---|
| `icon_12` | aus | 0 |
| `icon_24` | Zeitprogramm | 1 |
| `icon_21` | normal | 2 |
| `icon_11` | Eco | 3 |
| `icon_10` | manuelles Heizen | 4 |
| `icon_1` | manuelles Kühlen | 5 |

**Systemmodus-Werte für `/api/installation/command` (`command=system_mode`)**

| Wert | Bedeutung |
|---|---|
| 0 | aus |
| 1 | automatisch |
| 2 | Warmwasser |
| 3 | einmaliges Warmwasser (Tasten-Charakter; springt zurück auf automatisch) |

### Datenfrische und Konsistenz

Die Cloud-Daten sind **30–60 Minuten alt**, weil die Wärmepumpe nur in diesem
Intervall in die Cloud hochlädt. Ein Plausibilitätsvergleich gegen lokale
Modbus-Lesungen (Juli 2026, Navigator-10-Installation) bestätigt die semantische
Konsistenz:

| Cloud-Wert | Modbus-Quelle | Differenz |
|---|---|---|
| `sum_heat: 31549.6 kWh` | `total_heat_energy` (Register 4128) | ~1 kWh (Cloud ist älter) |
| `temp_outside: 21.6 °C` | `outdoor_temp` (Register 1000) | typischer Tagesgang |
| `temp_hygienic: 59 °C` | `dhw_temp_top` (Register 1014) | ±1 K |

### Was die Legacy-API **nicht** bietet

- ❌ **einen Firmware-Update-Endpunkt** — weder einen Auslöser noch eine
  Statusabfrage
- ❌ das Schreiben von Temperatur-Sollwerten (nur Modus-Befehle)
- ❌ Solar-, ISC-, Booster-, Kaskaden- oder Zonendaten (nur der Basis-Heizkreis)
- ❌ Live-Daten (30–60 Minuten älter als lokal)
- ❌ Authentifizierung auf modernem Niveau (SHA1 ohne Salt, möglicherweise
  TLS-Kettenprobleme)

### Neue OAuth2-API (Stand Juli 2026: **nicht dokumentiert**)

Das aktuelle myIDM-Web-Frontend (`app.myidm.at`) verwendet eine **moderne
OAuth2+PKCE-API** unter `a.myidm.at/api/v1/`. Die alte SHA1-API und die neue
OAuth2-API existieren parallel, aber die OAuth2-API wurde **noch nicht
reverse-engineered**.

Bekannte Pfade der v1-API (nur das Verzeichnis, verifiziert durch ein lesendes
GET auf `/api/v1/` nach einem Django-Sitzungs-Login):

```
/api/v1/heatpumps/
/api/v1/heatpumps/errors-log/
/api/v1/users/
/api/v1/translations/
/api/v1/texts/
/api/v1/errors/
/api/v1/bookmarks_new/
/api/v1/bookmarks/
/api/v1/channels/
/api/v1/data-act-channels/
/api/v1/virtual-channels/
... (list incomplete)
```

Die Endpunktliste deutet auf einen größeren Funktionsumfang als die Legacy-API
hin (`virtual-channels`, `data-act-channels`), aber die API verlangt einen
OAuth2-Bearer-Token, dessen PKCE-Flow in dieser Sitzung nicht vollständig
nachvollzogen werden konnte (die Django-Sitzung wurde akzeptiert, aber der
Endpunkt `/api/v1/oauth2/authorize` verweigert die Wiederverwendung für den
SPA-Redirect).

**Offen für künftige Recherchen**:

- der vollständige PKCE-Flow mit korrekter `code_verifier`-Behandlung
- die Auflistung aller `/api/v1/...`-Endpunkte einschließlich Schreib- und
  Update-Optionen
- Reverse-Engineering der SPA `app.myidm.at` nach API-Aufrufmustern

Sollte die OAuth2-API in einer künftigen Sitzung dekodiert werden, sollte die
Dokumentation hier erweitert werden.

### Bezug zur Integration

Diese Integration ist bewusst **100 % lokal** (Modbus + Nav 10 WS) und nutzt
keine der beiden Cloud-APIs. Siehe den Abschnitt „Bewusst nicht implementiert“.
Die Cloud-API-Dokumentation hier dient nur der Vollständigkeit und dem Support
sowie möglichen künftigen Funktionen (zum Beispiel ein optionaler Cloud-Fallback,
wenn die Modbus-Erkennung fehlschlägt).
