# Installation & Einrichtung

## Voraussetzungen

- **Home Assistant** 2026.8.1 oder neuer
- **HACS** ([Installationsanleitung](https://hacs.xyz/docs/setup/download))
- **IDM Navigator 2.0 / 10 / Pro** Wärmepumpe mit aktiviertem Modbus TCP
- Modbus TCP muss im Navigator-Controller aktiviert sein (Port 502, Slave-ID 1)

## Installation über HACS (empfohlen)

1. Öffne HACS in Home Assistant
2. Gehe zu **Integrationen**
3. Klicke auf **⋮ (drei Punkte)** → **Benutzerdefinierte Repositories**
4. Gib die URL ein: `https://github.com/Xerolux/idm-heatpump-hass`
5. Wähle **Kategorie: Integration**
6. Klicke auf **Hinzufügen**
7. Suche nach **"IDM Heatpump"**
8. Klicke auf **Herunterladen**
9. **Starte Home Assistant neu**

## Stable oder Beta wählen

Das [letzte stabile Release](https://github.com/Xerolux/idm-heatpump-hass/releases/latest)
ist der normale Installationskanal. Die in diesem Wiki beschriebene neue geführte
Einrichtung und die Smart-Energy-&-Comfort-Funktionen sind im
[0.17.2-b6 Beta](https://github.com/Xerolux/idm-heatpump-hass/releases/tag/v0.17.2-b6) verfügbar.

Um die Beta auszuprobieren, öffne das IDM-Heatpump-Repository in HACS, nutze dessen
Versionsauswahl-/Download-Aktion, aktiviere bei Bedarf Vorabversionen und wähle
`0.17.2-b6`. Sichere Home Assistant vor dem Upgrade und starte Home Assistant nach
dem Herunterladen neu. Eine neuere Dokumentationsseite aktualisiert die installierte
Integration nicht automatisch. Prüfe die installierte Version in der Diagnose der
Integration, bevor du nach den neuen Optionen suchst.

Beta-Fixes haben automatisierte Regressionsabdeckung. Sie sind keine Aussage über
eine abgeschlossene Langzeit- oder Hardware-Validierung für alle Modelle. Siehe
[Stabilität & Release-Reife](Stability-and-Release-Readiness).

## Manuelle Installation

1. Lade das neueste [Release](https://github.com/Xerolux/idm-heatpump-hass/releases) herunter (`idm_heatpump.zip`)
2. Erstelle bei Bedarf das Verzeichnis `idm_heatpump` unter `custom_components/`
3. Entpacke den Inhalt des ZIP direkt in dieses Verzeichnis; `manifest.json` muss
   unmittelbar darin liegen, ohne ein weiteres verschachteltes `idm_heatpump`-Verzeichnis:
   ```
   <ha-config>/custom_components/idm_heatpump/
   ```
4. Starte Home Assistant neu

## Modbus TCP an der IDM Wärmepumpe aktivieren

> **Erforderlich:** Der volle Betrieb der Integration ist nur möglich, wenn Modbus
> TCP am IDM Navigator/Controller aktiviert ist. Die Installation der
> Home-Assistant-Integration kann diese Controller-Einstellung nicht aus der Ferne
> aktivieren.

Die offizielle iDM-Dokumentation beschreibt die relevante Navigator-Einstellung als
**Gebäudeleittechnik / Building management system → Modbus TCP → Ein / On**.
Ein praktisches Vorgehen:

1. Öffne das lokale Display des IDM Navigators/Controllers.
2. Melde dich auf der Installateur-/Fachmann-Ebene an, falls der Controller dies verlangt.
3. Öffne **Gebäudeleittechnik** (englisch: **Building management system**).
4. Setze **Modbus TCP** auf **Ein / Aktiv** (englisch: **On / Enabled**).
5. Speichere die Einstellung. Starte den Navigator/Controller neu, wenn die
   Schnittstelle nicht sofort verfügbar wird.
6. Verbinde den Navigator mit dem lokalen Ethernet-Netzwerk und notiere seine IP-Adresse.
7. Verwende in dieser Integration **TCP-Port 502** und normalerweise **Slave-/Unit-ID 1**.

Menünamen und Berechtigungen können sich zwischen Navigator 2.0, Navigator 10,
Navigator Pro und Firmware-Versionen unterscheiden. Wenn **Gebäudeleittechnik** oder
**Modbus TCP** fehlt, nur lesbar oder gesperrt ist, bitte deinen Heizungsinstallateur
oder den iDM-Service, die Schnittstelle zu aktivieren. Ändere keine unbeteiligten
Heizungs- oder Sicherheitsparameter.

Die erforderliche Einstellung gehört zur **IDM Wärmepumpe/dem Navigator**. Eine
Modbus-TCP-Option an einem PV-Wechselrichter ist eine separate Schnittstelle und
aktiviert keinen Home-Assistant-Zugriff auf die Wärmepumpe.

Netzwerk-Checkliste:

- Home Assistant und der Navigator müssen sich lokal gegenseitig erreichen können.
- Bevorzuge kabelgebundenes Ethernet; exponiere Port 502 nicht ins Internet.
- Reserviere die Navigator-IP im Router oder konfiguriere sie konsistent, damit sie
  sich nicht unerwartet ändert.
- Teste die Adresse aus dem Netzwerk von Home Assistant, nicht nur von einem Telefon
  in einem anderen WLAN/VLAN.

Quelle: [offizielle iDM-Technikdokumentation (PDF)](https://www.idm-energie.at/wp-content/uploads/2021/04/PV_Nutzung_GLT-Smartfox.pdf),
die festlegt, dass **Modbus TCP** im Menü **Gebäudeleittechnik** des Navigators auf
**Ein** stehen muss; iDM dokumentiert TCP-Port 502 für die Modbus-Kommunikation des
Navigators zusätzlich in der [technischen PV-/GLT-Dokumentation](https://www.idm-energie.at/wp-content/uploads/2021/04/tu_de_812184_myiDMenergy_PV_Variable-Stromtarife_Navigator-2.0-1.pdf).

## Einrichtung

1. Öffne **Einstellungen → Geräte & Dienste**
2. Klicke auf **Integration hinzufügen**
3. Suche nach **"IDM Heatpump"**
4. Folge dem Konfigurationsassistenten:
   - **Im Flow angezeigte Voraussetzung**: Bestätige, dass am Navigator **Gebäudeleittechnik → Modbus TCP** aktiviert ist
   - **Verbindung**: Gib einen Namen, die IP/den Hostnamen der Wärmepumpe, Port 502 und Slave-ID 1 ein
   - **Optionaler Webzugriff**: Gib den lokalen Navigator-Web-PIN ein; bei Verwendung eines Modbus-Proxys aktiviere zusätzlich die Proxy-Option und gib die ursprüngliche Wärmepumpen-Adresse als Web-Host ein
   - **Einrichtungstiefe**: Wähle Standard, Erweitert oder Experte; diese steuern den Detailgrad, nicht welche Funktionen verfügbar sind
   - **Funktionen**: Wähle die Kategorien, die du konfigurieren möchtest, z. B. Anlage, Smart-/Vanilla-Profil, Energie, Health Monitor oder Komfort
   - **Funktionsseiten**: Gib die angeforderten Sensoren, Heizkreis-Zuordnungen und optionalen Einstellungen an; prüfe die Zuständigkeitsbestätigung, bevor du eine automatische Schreibfunktion aktivierst
   - **Zonen**: Konfiguriere die Anzahl aktiver Räume für jedes ausgewählte Zonenmodul
5. Prüfe und bestätige die Konfiguration zum Abschluss. Wie du die Einrichtungstiefe später änderst, steht in [Konfiguration](Configuration).

### Lokaler Navigator-Web-PIN (keine Cloud-2FA)

Der optionale Web-PIN ist der **lokale Netzwerk-Code, der am Navigator-Display
konfiguriert wird**. Er ist getrennt vom myIDM-App-/Cloud-Konto, dessen Passwort und
der Zwei-Faktor-Authentifizierung.

An einem Navigator 2.0 mit deutschem Display konfigurierst du ihn unter:

**Einstellungen → Allgemeine Einstellungen → Netzwerkeinstellungen → Code
lokales Netzwerk**

Die Menübezeichnungen können je nach Navigator-Generation und Firmware abweichen.
Ein leerer Wert oder `0` deaktiviert die lokale Weboberfläche. Cloud-Zugangsdaten
oder ein temporärer Zwei-Faktor-Code werden in Home Assistant daher abgelehnt.

Der Navigator 2.0 nutzt einen lokalen HTTP-Login mit CSRF-Token. Navigator 10 und
Navigator Pro nutzen die Navigator-10-WebSocket-Login-Familie. Die Einrichtung nutzt
das per Modbus erkannte Modell nur zur Wahl des ersten Versuchs, probiert bei Bedarf
das andere unterstützte Protokoll und speichert das Protokoll, das tatsächlich
funktioniert. Die normale Abfrage bleibt dann auf diesem bekannten Protokoll. Der
vollständige Lebenszyklus ist unter [Lokale Navigator-Weboberfläche](Local-Web-Interface) beschrieben.

## Einrichtungsprüfung und Fehlermeldungen

Der Einrichtungs- und der Rekonfigurations-Flow lesen ein bekanntes IDM-Register.
Schlägt das fehl, trennt eine kurze DNS-/TCP-Prüfung Netzwerkprobleme von einem
erreichbaren Endpunkt, der keine nutzbaren Modbus-Daten liefert. So kann Home
Assistant eine hilfreichere Ursache nennen, statt einen allgemeinen
Verbindungsfehler zu melden:

| Meldung | Bedeutung | Was du prüfen solltest |
|---------|---------|---------------|
| Hostname nicht gefunden | Lokales DNS/mDNS kann den eingegebenen Namen nicht auflösen | Tippfehler, lokales DNS, oder verwende die IP der Wärmepumpe |
| Verbindung abgelehnt | Ein Gerät hat geantwortet, aber TCP abgelehnt | Modbus TCP ist meist deaktiviert, oder der Port ist nicht 502 |
| Zeitüberschreitung der Verbindung | Keine TCP-Antwort innerhalb von 5 Sekunden | Falsche IP, ausgeschalteter Controller, Firewall, VLAN oder Routing |
| Ziel nicht erreichbar | Das Betriebssystem kann die Adresse nicht routen | Netzwerk-/Subnetz-/Gateway-Konfiguration |
| Keine gültige IDM-Registerantwort | TCP funktioniert, aber die Modbus-Abfrage schlug fehl | Slave-ID (üblicherweise 1), Proxy-Ziel, Modbus-Berechtigung/-Aktivierung |
| Web-PIN abgelehnt | Die Web-Authentifizierung des Navigators ist fehlgeschlagen | Korrigiere die lokale PIN direkt im Flow |
| Weboberfläche nicht verfügbar | Eine PIN wurde angegeben, aber Webdaten lassen sich nicht lesen | Ursprünglicher Web-Host, Netzwerkzugriff; PIN leeren für reinen Modbus-Betrieb |

Das Protokoll enthält Host, Port, Slave-ID, Fehlerklasse und die empfohlenen
Prüfungen. PIN-Werte werden niemals ins Protokoll geschrieben.

## Die gespeicherte Verbindung später testen

Öffne **Einstellungen → Geräte & Dienste → IDM Heatpump → Neu konfigurieren →
Aktuelle Verbindung testen**. Der Test prüft den gespeicherten Modbus-Endpunkt und,
wenn ein lokaler Web-PIN konfiguriert ist, den Web-Endpunkt des Navigators. Er ist
rein lesend: Es werden keine Einstellungen gespeichert und keine Wärmepumpen-Register
geschrieben. Nach der Korrektur einer Netzwerk- oder Controller-Einstellung kann das
Ergebnis erneut abgesendet werden, um den Test zu wiederholen.

## Deinstallation

1. Öffne **Einstellungen → Geräte & Dienste**
2. Finde die Integration **IDM Heatpump**
3. Klicke auf die drei Punkte → **Löschen**
4. (Optional) Lösche den Ordner `custom_components/idm_heatpump/`
5. Starte Home Assistant neu

## Aktualisierung

Über HACS: Öffne HACS → Integrationen → IDM Heatpump → "Update" → HA neu starten.

Manuell: Wiederhole die manuelle Installation (überschreibt die alten Dateien).


## Automatische externe Leistungsweiterleitung von Home Assistant

Öffne nach der Installation der Integration den IDM-Heatpump-Eintrag und wähle
**Neu konfigurieren → Funktionen → Externe Leistungsweiterleitung**. Beim Aktivieren
der Weiterleitung öffnet sich die Sensor-Zuordnungsseite. Jedes Feld bietet eine
durchsuchbare Liste vorhandener Home-Assistant-Sensor-Entitäten:

- PV-Überschuss → IDM `pv_surplus` (Register 74–75)
- PV-Produktion → `pv_production` (78–79)
- Hausverbrauch → `house_consumption` (82–83)
- Batterie Laden/Entladen → `battery_discharge` (84–85)
- Batterie-Ladezustand → `battery_soc` (86)
- Leistung Elektro-Heizstab → `electric_heater_power` (76–77)

Leistungssensoren müssen `W` oder `kW` liefern; die Werte werden vor dem Schreiben
nach kW umgerechnet. Der Batterie-Ladezustand ist eine ganze Prozentzahl von 0 bis
100; `-1` bedeutet, dass keine Batterie vorhanden ist. Nutzt der Energiemanager die
openWB-Vorzeichenkonvention (negativ bedeutet Entladen), wähle **Quellvorzeichen
invertieren**. Nicht verfügbare oder ungültige Sensoren werden übersprungen; die
Integration schreibt niemals null als Ersatz.

### Wichtige Zuständigkeitsregel

Nur ein System sollte ein bestimmtes IDM-GLT/PV-Register aktiv schreiben. Aktiviere
diese Weiterleitung nicht für ein Register, das auch von SMARTFOX, openWB oder einem
anderen Energiemanager geschrieben wird. Andernfalls gewinnt der letzte Schreiber,
und die Werte können pendeln.

### IDM Navigator vorbereiten

1. Öffne am Navigator/Controller die **Gebäudeleittechnik (GLT)**.
2. Aktiviere **Modbus TCP** und verwende Port **502**. Die normale Modbus-Slave-/Unit-ID ist **1**.
3. Aktiviere oder gib die vom installierten System benötigten GLT-/Energiemanagement-Eingangsregister frei. Manche Navigator-Generationen zeigen eine separate GLT/PV- oder Energiemanager-Berechtigung; die genaue Bezeichnung und Zugriffsebene hängen von Firmware und Installateur-Einstellungen ab.
4. Speichere die Einstellung und starte den Controller nur neu, wenn der Navigator es verlangt.
5. Konfiguriere die Home-Assistant-Optionen und prüfe die Werte – falls vorhanden – im GLT-/Energiemanager-Monitor des Navigators.

Wenn das Menü fehlt oder gesperrt ist, bitte den Heizungsinstallateur oder den
iDM-Service, die GLT-/Modbus-TCP-Funktion zu aktivieren. Die SMARTFOX- und
openWB-Dokumentation bestätigt, dass diese Werte für eine Energiemanager-/GLT-
Schnittstelle bestimmt sind, der genaue Aktivierungsweg hängt aber von Installation
und Firmware ab.
