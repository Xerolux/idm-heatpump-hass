# Lokale Navigator-Weboberfläche

## Zweck und Grenzen

Die optionale Web-Verbindung ergänzt Modbus um lokale, schreibgeschützte
Navigator-Metadaten und Diagnose. Sie nutzt niemals die myIDM-Cloud und ersetzt
Modbus weder für die normale Registerüberwachung noch für die Steuerung.

| Betriebsmodus | Modbus | Lokales Web | Verfügbare Funktionen |
|---------------|--------|-------------|-----------------------|
| Nur Modbus | ja | nein | Volle Modbus-Entitäten, Steuerelemente und Aktionen |
| Modbus + Web-Supplement | ja | ja | Volle Modbus-Funktionen plus zusätzliche Web-Sensoren |
| Reiner Web-Betrieb (Fallback) | nein | ja | Nur die Web-Sensorplattform; keine Modbus-Entitäten oder Schreibvorgänge |

Im reinen Web-Betrieb gibt es keine Modbus-Registerlesezugriffe, Binärsensoren,
Number-, Select- oder Switch-Entitäten, keine rohen Register-Schreibvorgänge, keine
Systemmodus-Aktionen und keine Störungsquittierung. Verfügbar sind nur Werte, die
die lokale Weboberfläche zurückliefert.

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
`0.8.1-beta.29` eingeführt. Die aktuelle stabile Version ist `0.15.0` und liefert
die getesteten Web-Clients `idm-heatpump-api[web]==2.4.3`, die zusätzlich
Navigator-10-Heizkreisdaten für die Kreise B–G bereitstellen.

Für den unabhängigen Modbus-Pfad lautet die getestete Manifest-Reihenfolge
`modbus-connection==4.12.2`, `tmodbus[async-serial]==0.6.2`
und `idm-heatpump-api[web]==2.4.3`. Die ersten beiden besitzen den direkten
Modbus-Socket; seit API 2.0.0 ist pymodbus gar nicht mehr installiert. Das ändert
weder das Web-Protokoll noch macht es die Version `4.12.2` zu einem
IDM-Integrations-Release.
