# Lokale Navigator-Weboberfläche

## Zweck und Grenzen

Die optionale lokale Web-Verbindung liefert Navigator-Metadaten und Diagnose
ohne myIDM-Cloud. In den Verbindungseinstellungen stehen `auto`, `modbus_web`,
`modbus_only` und `web_only` zur Wahl. Bei funktionierender Web-PIN kann `auto`
auf die Web-Verbindung ausweichen, wenn Modbus nicht verfügbar ist.

| Betriebsmodus | Modbus | Lokales Web | Verfügbare Funktionen |
|---------------|--------|-------------|-----------------------|
| Nur Modbus | ja | nein | Alle unterstützten Modbus-Entitäten, Steuerelemente und Aktionen |
| Modbus + Web-Supplement | ja | ja | Modbus-Funktionen plus zusätzliche Web-Daten |
| Nur Web, Navigator 10/Pro | nein | ja | Web-Daten, Systemmodus, Warmwasser-Sollwert, Störungsquittierung, Heizkreismodus/-Sollwert und Klima-/Warmwasserkarten, soweit vom Regler bereitgestellt |
| Nur Web, Navigator 2.0 | nein | ja | Ausschließlich lesbare Werte der lokalen HTTP-Oberfläche |

Web-Steuerungen für Navigator 10/Pro prüfen Schreibwerte gegen die vom Regler
angegebenen Grenzen. Differenztemperaturgeregelte Kreise erhalten keine
Raumsteuerungen. Rohe Modbus-Registerschreibzugriffe und der einmalige
Warmwasser-Boost sind unter `web_only` nicht verfügbar. Die Weboberfläche bildet
den Boost als Wochenzeitplan ab; dessen Änderung gehört nicht zu den
unterstützten Steuerungen dieser Integration.

## Menüstruktur des Navigator 10

Dieser Menübaum wurde in der über myIDM geöffneten Navigator-10-Oberfläche
einer AERO ALM beobachtet. Die folgenden Einträge waren in der Service-Ansicht
sichtbar. Je nach Firmware, Berechtigung und Anlagenausstattung können Menüs
abweichen. Welche Daten und Bedienelemente die Integration in Home Assistant
bereitstellt, steht unter [Entitäten](Entities).

```text
Navigator
├── Home
│   ├── Wärmemenge und Leistungszahl
│   ├── Anforderungsgrund
│   └── Betriebsart System und aktueller Wärmepumpenbetrieb
├── Anlagenübersicht (zweites Symbol)
├── Statistik (Diagrammsymbol)
├── Einstellungen (Zahnrad)
│   ├── Allgemeine Einstellungen
│   ├── Informationen
│   ├── Konfiguration
│   ├── Wärmepumpe
│   ├── Heizkreis
│   ├── Speichermanagement
│   ├── Trinkwarmwasserbereitung
│   ├── Photovoltaik
│   ├── Smart Grid
│   ├── Energiemonitoring
│   ├── Gebäudeleittechnik
│   ├── Bivalenz
│   ├── Relaistest
│   ├── Fühlerabgleich
│   ├── Resetdaten
│   └── Fachmann Codeeingabe
└── Infosystem (Warndreieck)
    ├── Meldungen
    └── Meldungsverlauf
```

### Wo stehen PV-, Zähler- und GLT-Werte?

| Pfad im Navigator | Was dort zu sehen ist |
| --- | --- |
| Einstellungen → Photovoltaik → **PV Leistung** | Überschuss, PV-Erzeugung, Hausverbrauch, tatsächliche Stromaufnahme der Wärmepumpe, momentane bzw. prognostizierte Wärmeleistung nach Betriebsart, Batterieentladung und Akkustand. |
| Einstellungen → Photovoltaik oder Konfiguration → **PV Signal** | Ausgewählte PV-Quelle. **Gebäudeleittechnik / Smartfox** bezeichnet die GLT-Quelle für die Weiterleitung aus Home Assistant. |
| Einstellungen → Photovoltaik | PV-Optionen für Warmwasser und Speicherladung, Maximaltemperaturen, Hysterese, Mindest-Akkustand und Verbrauchsoffset. |
| Einstellungen → Gebäudeleittechnik → **GLT Monitor** | Registernummer, Zugriff, Reglerwert und empfangener GLT-Wert. Dazu gehören 74 (Überschuss), 78 (PV-Erzeugung), 82 (Hausverbrauch), 84 (Batterieentladung) und 86 (Akkustand). |
| Einstellungen → Gebäudeleittechnik | Modbus TCP, KNX, BACnet IP, konfigurierte GLT-Fühlereingänge und GLT-Log. |
| Einstellungen → Energiemonitoring → **S0-Zähler** | Konfiguration des S0-Impulszählers. |
| Einstellungen → Konfiguration → **Stromzähler** | Laut Hilfetext aktiviert dieser Schalter die Anzeige der elektrischen Leistungsaufnahme der Wärmepumpe in der Statistik. |
| Infosystem → Meldungen → Meldung aufklappen | Zeitpunkt und Beschreibung des Reglers. **20303** bezieht sich auf den Smart Meter der PV-Anlage. Ein sichtbarer GLT-Wert bestätigt den Empfang dieses Werts. Die Meldung nennt die genaue Auslösebedingung für 20303 nicht. |

Relaistest, Fühlerabgleich und Reset sind Servicefunktionen. Für die Anbindung
an Home Assistant und die Einordnung der GLT-Werte siehe
[Installation und Einrichtung](Installation-and-Setup) und [Fehlersuche](Troubleshooting).

## Unterstützte lokale Anmeldevarianten

Die Navigator-Generationen verwenden unterschiedliche lokale Protokolle. Die
internen Variantennamen bezeichnen den Protokoll-Client und sind keine vom
Benutzer wählbaren Einstellungen.

| Navigator-Familie | Interne Variante | Lokaler Transport | Authentifizierung |
|-------------------|------------------|-------------------|-------------------|
| Navigator 2.0 | `nav20` | HTTP, normalerweise Port 80 | Anmeldeformular mit CSRF-Token und Code für das lokale Netzwerk |
| Navigator 10 | `nav10` | WebSocket, Port 61220 | Autorisierungsframe mit dem Code für das lokale Netzwerk als `auth_code` |
| Navigator Pro | `nav10` | WebSocket-Familie des Navigator 10 | Dieselbe lokale Autorisierung wie beim Navigator 10 |

Diese Transports sind lokale Regler-Schnittstellen. Weder ein Cloud-Passwort,
ein myIDM-Kontologin noch ein Zwei-Faktor-Code wird akzeptiert.

## Code lokales Netzwerk

Der in Home Assistant eingegebene Wert ist der **Code für das lokale Netzwerk**
des Navigators. Auf einem deutschen Navigator-2.0-Display findest du ihn
normalerweise unter:

**Einstellungen → Allgemeine Einstellungen → Netzwerkeinstellungen → Code
lokales Netzwerk**

Menünamen können je nach Generation und Firmware abweichen. Führende und
abschließende Leerzeichen werden entfernt. Ein leerer Wert oder genau `0`
bedeutet, dass der lokale Web-Zugriff deaktiviert ist; die Integration bleibt
dann im Nur-Modbus-Betrieb.

Der Code wird über ein maskiertes Home-Assistant-Passwortfeld eingegeben. Er wird
niemals protokolliert und zusammen mit dem Modbus-Host, Web-Host, Port und der
Slave-ID aus der Diagnose geschwärzt. Web-Fehlerdiagnosen geben nur eine
Fehlerkategorie preis, keine URL, keinen Query-String und keinen
Autorisierungswert.

## Erkennung und Lebenszyklus zur Laufzeit

Die Integration trennt die anfängliche Protokoll-Erkennung von der normalen
Laufzeit-Wiederherstellung:

1. **Einrichtung, Neukonfiguration oder Reparatur:** Das per Modbus erkannte
   Modell dient als Hinweis, sodass das wahrscheinlichste Web-Protokoll zuerst
   versucht wird. Schlägt es fehl, wird auch das andere unterstützte Protokoll
   versucht, bevor der PIN oder die Verbindung abgelehnt wird.
2. **Erste erfolgreiche Anmeldung:** Das tatsächliche `nav20`- oder
   `nav10`-Ergebnis wird im Konfigurationseintrag gespeichert. Das Ergebnis
   stammt vom erfolgreichen Client, nicht bloß vom Modell-Hinweis.
3. **Normale Abfrage:** Der erfolgreiche Client und die authentifizierte Sitzung
   werden über die Web-Abfragezyklen hinweg wiederverwendet.
4. **Abgelaufene Sitzung oder Transportfehler:** Die fehlgeschlagene Sitzung wird
   geschlossen und dasselbe bekannte Protokoll sofort neu aufgebaut. Die normale
   Laufzeit-Wiederherstellung testet nicht die andere Navigator-Generation.
5. **Neue Erkennung:** Neukonfiguration oder Reparatur validiert die Verbindung
   erneut und kann beide Protokolle testen. Das ist angebracht, nachdem der
   Navigator ausgetauscht wurde, der Web-Host geändert wurde oder eine
   Regler-/Firmware-Änderung die lokale Schnittstelle betrifft.

Das verhindert wiederholte Zeitüberschreitungen am falschen Port und vermeidet,
dass ein vorübergehender Fehler unbemerkt eine zuvor funktionierende
Navigator-Generation wechselt.

## Modell- und Wert-Rangfolge

Modbus bleibt für registergestützte Betriebswerte maßgeblich. Web-Daten sind
additiv: Sie liefern Metadaten und zusätzliche Diagnosen, für die es keine
äquivalente Modbus-Entität gibt. Ein bereits registergestützter Wert wird kein
zweites Mal bereitgestellt.

Web-Modell- und Firmware-Metadaten können ein unbekanntes Modbus-Ergebnis
vervollständigen. Widerspricht eine vom Web gemeldete Navigator-Familie einer
eindeutigen Modbus-Erkennung, werden das widersprechende Web-Modell und die
Firmware ignoriert. Optionale Navigator-10-Infosystem-Meldungen werden separat
gelesen; schlägt diese optionale Abfrage fehl, verwirft sie den Rest eines
gültigen Web-Schnappschusses nicht.

## Abfrage- und Wiederherstellungsverhalten

- Die Web-Abfrage hat ihr eigenes Intervall, standardmäßig 30 Sekunden.
- Sie beginnt kurz nach der Modbus-Abfrage, um gleichzeitige Anfragen zu vermeiden.
- Ein Web-Authentifizierungs- oder Verbindungsproblem erzeugt ein eigenes
  Home-Assistant-Reparaturproblem und stoppt die Modbus-Updates nicht.
- Fehlende Werte aus einem erfolgreichen Web-Schnappschuss bleiben unverfügbar;
  alte Werte werden nicht erfunden.
- Der zwischengespeicherte Client wird geschlossen, wenn der
  Konfigurationseintrag entladen wird oder seine Sitzung neu aufgebaut werden muss.

## Checkliste zur Fehlerbehebung

1. Bestätige, dass der Code der Code für das lokale Netzwerk ist, keine Cloud-Zugangsdaten.
2. Bestätige, dass der Code weder leer noch `0` ist.
3. Verwende bei direktem Modbus-Zugriff die Navigator-Adresse als Web-Host. Bei einem
   Modbus-Proxy konfiguriere die ursprüngliche Navigator-Adresse separat.
4. Führe **Einstellungen → Geräte & Dienste → IDM Heatpump → Neu konfigurieren →
   Aktuelle Verbindung testen** aus.
5. Hat sich der Navigator oder sein lokales Web-Protokoll geändert, verwende
   **Verbindungseinstellungen ändern**, damit die Protokoll-Erkennung erneut läuft.
6. Lade die geschwärzte Diagnose herunter und füge beim Melden eines Problems die
   Versionen der Integration, von `modbus-connection`, `tmodbus` und der API
   sowie Navigator-Modell und Firmware bei.

Siehe [Fehlerbehebung](Troubleshooting) für kategorisierte Fehler und
[Konfiguration](Configuration) für alle Web-Optionen.

## Versionpaarung

Die dauerhaft gespeicherte Protokollauswahl wurde in der Integrationsversion
`0.8.1-beta.29` eingeführt. Der aktuelle Quellbaum verwendet die getesteten
Web-Clients `idm-heatpump-api[web]==2.17.0rc1`, die zusätzlich
Navigator-10-Heizkreisdaten für die Kreise B–G bereitstellen.

Für den unabhängigen Modbus-Pfad lautet die getestete Manifest-Reihenfolge
`modbus-connection>=4.12.7`, `tmodbus[async-serial]>=1.1.0`
und `idm-heatpump-api[web]==2.17.0rc1`. Die ersten beiden besitzen den direkten
Modbus-Socket; seit API 2.0.0 ist pymodbus gar nicht mehr installiert. Das ändert
weder das Web-Protokoll noch macht es die Version `4.12.2` zu einem
IDM-Integrations-Release.

## Capture-Updates und fehlgeschlagene Webanmeldung

Für neue Diagnosen das aktuelle [IDM-Web-Capture-Paket](https://idmtools.xerolux.de/) verwenden. Ab Tool 1.19.4 installiert und startet die App neuere signierte Programmversionen automatisch vor Aufnahme oder Upload, unter Windows und Linux/Quellcode. Linux benötigt das Paket `openssl`; System-Python wird nicht ersetzt. Quellcode-Clients bis 1.19.3 einmal manuell aktualisieren. Ein bekanntes Update oder eine ungültige Signatur sperrt die Aufnahme. Ist der Update-Dienst nicht erreichbar, bleibt lokales Auslesen möglich; `manifest.json` enthält `update_check`.

Aktuelle Aufnahmen sind bevorzugt, der Server akzeptiert aber auch ältere Tool-Versionen. Der Versionsstand allein führt nicht zur Ablehnung. Vorhandene ZIPs bleiben nach einem App-Update hochladbar; Format-, Größen-, Bereinigungs- und Prüfsummenprüfung gelten weiterhin. Die ursprüngliche Aufnahmeversion bleibt dokumentiert. Vorhandene Einsendungen und bereits ausgestellte Upload-Tickets bleiben gültig. Nach bestätigtem Neustart bleiben die aktive und eine geprüfte Rückfallversion erhalten; Diagnose-ZIPs werden nicht gelöscht.

Wenn eingegebene Webzugangsdaten weder nutzbare HTTP- noch WebSocket-Daten liefern, pausiert das Tool: Eingaben korrigieren, bewusst ohne Webdaten fortfahren oder abbrechen. Bereinigte `web_diagnostics.json` und begrenzte Login-Antwortdateien dokumentieren Fehlerkategorie, bekannte Anmeldepfade, Statuscodes und Laufzeiten ohne PIN oder Formularwerte. Unbekannte Anmeldeantworten beweisen keine falsche PIN. Beim Fortfahren ohne Web bleiben diese Belege erhalten; anschließend läuft der gewählte Modbus-Pfad. Neue Anmeldewege und NAVIGATOR-Pro-Authentifizierung bleiben bis zur Bestätigung offen; keine PIN oder rohe Anmeldeantwort öffentlich posten.
