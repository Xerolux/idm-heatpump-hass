# Fehlerbehebung

## Smart-Funktionen und Beta-Upgrades

| Symptom | Was du prüfen solltest |
|---------|------------------------|
| Die neuen Funktionsseiten fehlen | Prüfe die installierte Version in der Diagnose. Diese Anleitung beschreibt die Beta 0.17.2-b6. Der Download der Dokumentation oder eines ZIP aktualisiert HA nicht, solange die Integrationsdateien nicht installiert und HA nicht neu gestartet wurde. |
| Analytics-, Health- oder Comfort-Entitäten fehlen | Prüfe das Smart-/Vanilla-Profil und jeden optionalen Schalter. Mit aktivierter Gerätehierarchie findest du sie in der entsprechenden Funktionsgruppe. Deaktivierte optionale Funktionen entfernen ihre Registrierungen. |
| Energie- oder COP-Statistiken stoppen | Sowohl die elektrische als auch die thermische Leistungsmessung muss gültig sein. Lange Lücken werden ausgeschlossen; Zähler schätzen fehlenden Verbrauch nicht. Beta 6 hält benötigte Leistungsregister in der Abfrage, auch wenn die rohen Entitäten deaktiviert sind. |
| PV-Laden startet nicht | Prüfe das Smart-Profil, den Energy-Manager-Schalter, die Bestätigung der alleinigen Steuerung, die Leistungseinheiten, die Überschuss-/SOC-Schwellen, einen bestehenden Boost und die Sperrzeit der Automatik. Ein ausgewählter, aber nicht verfügbarer Überschuss-Sensor verhindert den Start. |
| PV-Laden läuft weiter, obwohl der Überschuss sinkt | Der Überschuss steuert nur den Start, nicht den weiteren Betrieb. Ein aktiver Boost folgt seiner Zieltemperatur, seinem Timeout und seinen Wiederherstellungsregeln. |
| Comfort läuft zu einem unerwarteten Zeitpunkt | Prüfe die Zeitzone von HA, die konfigurierten Heizkreise und sich nicht überschneidende tägliche Zeitfenster. Beta 6 verwendet die Zeitzone von HA; die Auswertung erfolgt ungefähr einmal pro Minute. |
| Der vorherige Raum-Sollwert wurde nicht wiederhergestellt | Eine manuelle Änderung verhindert die Wiederherstellung, wenn der aktuelle Sollwert vom zuletzt geplanten Wert abweicht. Prüfe den aktuellen Wert und konkurrierende Automations. |
| Health meldet beim Start kurzzeitig einen niedrigen COP | Sieh dir Leistung, Betriebsart und die nachfolgenden Messwerte an. Die aktuelle Prüfung ist eine Momentaufnahme und kann die Anlaufphase anzeigen. Ein kurzzeitiger Hinweis allein ist noch keine Fehlerdiagnose. |
| Wetterempfehlungen sind nicht verfügbar | Die ausgewählte Wetter-Entität muss brauchbare stündliche Vorhersagen für die nächsten sechs Stunden liefern. Der Berater kann fehlende Vorhersagedaten nicht ableiten. |

Verwende für eine Supportanfrage **Diagnose herunterladen** auf der IDM-Integration.
Sie enthält einen Installateurbericht, Laufzeitversionen, Abfragefehler und aktive
Health-Prüfungen mit geschwärzten Verbindungsgeheimnissen. Siehe
[Smart Energy & Comfort](Smart-Energy-and-Comfort) für Konfigurationsbeispiele.

## Verbindungsprobleme

### Den integrierten Verbindungstest ausführen

Öffne **Einstellungen → Geräte & Dienste → IDM Heatpump → Neu konfigurieren → Aktuelle
Verbindung testen**. Dies führt einen schreibgeschützten Test mit den gespeicherten
Einstellungen durch:

1. Ein bekanntes IDM-Modbus-Register wird mit der konfigurierten Slave-ID gelesen.
2. Schlägt das fehl, wird eine kurze DNS-/TCP-Prüfung durchgeführt, um die Netzwerkursache zu bestimmen.
3. Ist ein lokaler Web-PIN vorhanden, werden der Web-Endpunkt des Navigators und der PIN überprüft.

Der Test verändert weder den Konfigurationseintrag noch schreibt er auf die Wärmepumpe. Das
übersetzte Ergebnis benennt die fehlschlagende Stufe, und das Absenden des Ergebnisformulars
führt den Test erneut aus. Derselbe kategorisierte Grund wird ins Protokoll geschrieben, ohne
den PIN preiszugeben.

### „Hostname konnte nicht aufgelöst werden“

- Prüfe die Schreibweise des konfigurierten Hostnamens
- Stelle sicher, dass Home Assistant denselben lokalen DNS-/mDNS-Server wie dein Browser verwenden kann
- Konfiguriere die Integration mit der festen IP-Adresse der Wärmepumpe neu, um DNS-Probleme auszuschließen

### „Modbus-TCP-Verbindung abgelehnt“

Das Zielgerät hat TCP aktiv abgelehnt. Das ist das stärkste verfügbare Anzeichen dafür, dass
**Modbus TCP nicht aktiviert** ist oder der falsche Port verwendet wurde.

- Öffne auf dem Navigator/Regler **Gebäudeleittechnik
  (GLT) → Modbus TCP** und stelle es auf **Ein**
- Fehlt dieses Menü oder ist es gesperrt, melde dich auf der Installateur-/Fachmann-Ebene an oder
  bitte deinen Heizungsinstallateur bzw. den iDM-Service, es zu aktivieren
- Verwende den TCP-Port **502**, sofern der Regler oder ein Proxy nicht anders konfiguriert wurde
- Starte den Navigator/Regler nach dem Aktivieren von Modbus neu, falls die Einstellung nicht sofort wirksam wird
- Wird ein Proxy verwendet, vergewissere dich, dass er auf dem eingegebenen Host und Port lauscht

Diese Einstellung muss an der **Wärmepumpe/dem Navigator** aktiviert werden, nicht an einem
PV-Wechselrichter. Siehe [Modbus TCP an der IDM-Wärmepumpe aktivieren](Installation-and-Setup#modbus-tcp-an-der-idm-warmepumpe-aktivieren)
für die vollständige Checkliste und offizielle iDM-Referenzen.

### „Zeitüberschreitung der Modbus-TCP-Verbindung“ oder „Endpunkt ist nicht erreichbar“

- Prüfe die **IP-Adresse** des IDM Navigators
- Stelle sicher, dass der Regler eingeschaltet ist
- Prüfe, ob eine Firewall, ein VLAN, ein Subnetz oder eine Routing-Regel Port 502 blockiert
- Pinge die IP-Adresse an: `ping <ip-of-navigator>`

Eine Zeitüberschreitung bedeutet, dass innerhalb von fünf Sekunden keine Antwort eingegangen
ist. „Nicht erreichbar“ bedeutet, dass das Betriebssystem einen Netzwerk-/Routing-Fehler
gemeldet hat.

### Verbindungsabbrüche

- Prüfe die Netzwerkverbindung (LAN-Kabel empfohlen)
- Erhöhe das Abfrageintervall (z. B. auf 30 Sekunden)
- Aktiviere die Debug-Protokollierung (siehe [Konfiguration](Configuration))
- Die auf tmodbus basierende Verbindung markiert eine abgebrochene Verbindung als getrennt und
  baut sie beim nächsten Vorgang wieder auf; die Wiederholungs-/Backoff-Strategie der API bleibt
  dabei wirksam. Treten weiterhin Abbrüche auf, prüfe die Stabilität des lokalen Netzwerks oder des WLAN.

Jeder IDM-Konfigurationseintrag besitzt derzeit seinen eigenen direkten tmodbus-Socket. Das
zentrale, eintragsübergreifende Verbindungs-Sharing von Home Assistant ist nicht verfügbar,
weshalb die Diagnose `supports_shared_connection: false` meldet. Vermeide es, während der
Fehlersuche bei Verbindungsabbrüchen einen weiteren Modbus-Client gegen denselben Endpunkt
laufen zu lassen.

### „Keine gültige IDM-Registerantwort“

- Prüfe die **Slave-ID** (Standard: 1)
- Bestätige, dass Modbus-Zugriff aktiviert bzw. für externe Clients freigegeben ist
- Prüfe, ob andere Modbus-Clients gleichzeitig auf denselben Port zugreifen
- Starte den IDM Navigator nach dem Aktivieren von Modbus neu

Diese Meldung bedeutet, dass der TCP-Endpunkt erreicht wurde, die Einrichtungs-Abfrage aber
keine verwertbaren IDM-Registerdaten erhalten hat. Sie unterscheidet sich daher von einem
Netzwerk- oder Firewall-Fehler.

### Modbus ist an der Wärmepumpe nicht verfügbar

Gib während der Einrichtung den lokalen Web-PIN des Navigators ein. Kann die Webschnittstelle
authentifiziert werden, bietet der Wiederherstellungsschritt **nur Web-Daten** an. Dieser Modus
stellt schreibgeschützte Web-Sensoren bereit, aber keine Modbus-Heizkreis-/Zonenregister,
keine schreibbaren Entitäten, keine Betriebsartensteuerung und keine Störungsquittierung. Die
volle Funktionalität erfordert weiterhin, dass Modbus TCP vom Installateur oder iDM-Service
aktiviert wird, falls der lokale Regler die Einstellung nicht anbietet.

### „Navigator-Web-PIN abgelehnt“

- Öffne **Einstellungen → Geräte & Dienste → IDM Heatpump → Neu konfigurieren → Verbindungseinstellungen ändern**
- Prüfe am Navigator-Display **Einstellungen → Allgemeine
  Einstellungen → Netzwerkeinstellungen → Code lokales Netzwerk**
  (englisch: **Settings → General settings → Network settings → Local network code**)
- Gib diesen Code für das lokale Netzwerk in Home Assistant ein
- Verwende kein Cloud-/App-Passwort und keinen Zwei-Faktor-Authentifizierungscode
- Ein leerer Code für das lokale Netzwerk oder `0` deaktiviert den lokalen Web-Zugriff des Navigators
- Leere den PIN, wenn du bewusst nur mit Modbus betreiben willst

Die Reparaturbenachrichtigung und das Protokoll zur Laufzeit unterscheiden
Authentifizierungsfehler von Netzwerkfehlern. Die Reparaturaktion kann einen neuen PIN
überprüfen oder die optionalen Web-Daten deaktivieren. Der PIN selbst wird niemals protokolliert.

Nachdem ein Protokoll einmal funktioniert hat, wiederholt die normale Laufzeit-Wiederherstellung
bewusst nur genau dieses Navigator-2.0- bzw. Navigator-10/Pro-Protokoll. Sie schließt eine
fehlgeschlagene Sitzung und baut denselben Client neu auf, statt unbemerkt auf eine andere
Reglergeneration umzuschalten. Haben sich der Regler, das Firmware-Verhalten oder der
Web-Endpunkt geändert, führe **Neu konfigurieren → Verbindungseinstellungen ändern** aus, um
eine neue Erkennung durchzuführen.

### „Navigator-Weboberfläche konnte nicht gelesen werden“

- Bei direktem Modbus-Zugriff ist der Web-Host normalerweise dieselbe Wärmepumpen-IP
- Bei einem Modbus-Proxy aktiviere die Proxy-Option und gib die **ursprüngliche Wärmepumpenadresse** als Web-Host ein
- Stelle sicher, dass Home Assistant die lokale Weboberfläche des Navigators erreichen kann
- Leere den Web-PIN, um nur mit Modbus fortzufahren

Web-Authentifizierungsfehler und allgemeine Web-Verbindungsfehler erzeugen getrennte
Reparaturprobleme. Keiner von beiden stoppt eine funktionierende Modbus-Abfrage.

### Der reine Web-Betrieb stellt weniger Entitäten bereit als erwartet

Das ist beabsichtigt. Der reine Web-Betrieb lädt nur schreibgeschützte Sensoren, die die lokale
Weboberfläche zurückliefert. Es gibt keine Modbus-Abfrage, keine Binärsensoren, Number-,
Select- und Switch-Entitäten, keine Register-Schreibvorgänge, keine Systemmodus-Aktion und
keine Störungsquittierung. Werte, die im letzten erfolgreichen Web-Schnappschuss fehlen,
bleiben unverfügbar.

## Probleme mit Entitäten

### Fehlende Entitäten

- Stelle sicher, dass die entsprechenden **Heizkreise** und **Zonen** in der Konfiguration aktiviert sind
- Konfiguriere die Integration neu
- Starte Home Assistant neu

### Falsche oder absurde Werte (z. B. -3276.8°C)

- Notiere den Entitäts-/Registernamen, den angezeigten Wert, das Navigator-Modell und den Zeitpunkt der Beobachtung.
- Lade die Diagnose herunter und gib die installierten Integrations-/API-Versionen und erkannten Funktionen an.
- Gib nach Möglichkeit den Wert an, den der Navigator gleichzeitig angezeigt hat. Ein plausibler, aber abweichender Wert ist genauso wichtig wie eine offensichtlich absurde Zahl.
- Geh nicht davon aus, dass jeder Wert `254`, `255` oder `-1` fehlerhaft ist: Es sind nur dort gültige „nicht verfügbar“-Sentinels, wo die Register-Metadaten sie als solche ausweisen.
- Melde den Fall als [Bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md). Maintainer sollten die exakte FC03/FC04-Adresse/-Anzahl und die Rohwörter in Stapel- und Einzellesevorgängen vergleichen, bevor sie Datentyp- oder Adress-Metadaten ändern.

### Werte mit dem GLT-Monitor des Navigators vergleichen

Öffne bei schwierigen Register- oder Schreibproblemen den **GLT-Monitor** am Navigator im
Bereich Gebäudeleittechnik/GLT. Menübezeichnungen und Zugriffsebene unterscheiden sich je
nach Regler und Firmware; möglicherweise ist der Fachmann-Zugriff erforderlich. Der Monitor
zeigt die Werte und die Kommunikation, die der Regler selbst sieht, und ist daher der beste
Vergleichspunkt auf dem Gerät für Home-Assistant-Diagnosen.

Erfasse beim Melden einer Abweichung gleichzeitig:

- Navigator-Generation, Firmware und Wärmepumpen-Modell
- Entitätsname und Bibliotheks-Registername, Adresse und Datentyp
- Home-Assistant-Wert und Zeitstempel
- Anzeigewert des Navigators und GLT-Monitor-Wert
- Ob der Wert in einem Stapel oder einzeln gelesen wurde
- Jedes System, das das Register schreiben kann, etwa Home Assistant, ein Wechselrichter,
  E3DC, Smartfox oder ein anderer GLT-Regler

Wechselt ein schreibbarer Wert zwischen zwei Werten hin und her, deaktiviere zuerst alle
anderen Schreiber. Eine sich wiederholende Änderung bedeutet oft, dass zwei Automations oder
Energy-Manager dasselbe GLT-Register beanspruchen; sie ist kein Beweis für einen falschen
Datentyp.

### Bedienelemente oder Aktoren scheinen zu fehlen

Schreibbare Funktionen erscheinen nicht alle als klassische „Aktoren“. Öffne das IDM-Gerät
und suche nach `number`-, `select`- und `switch`-Entitäten. Wähle in einer Automation
**Aktion hinzufügen** und wähle die Entitäts-Aktion (`number.set_value`,
`select.select_option`, `switch.turn_on`/`switch.turn_off`) oder eine IDM-spezifische Aktion.
Das erweiterte Schreiben roher Register ist bewusst nur über die risikobestätigte IDM-Aktion
verfügbar, die unter [Aktionen](Services) dokumentiert ist.

### Werte aktualisieren sich nicht

- Prüfe das **Abfrageintervall** in den Optionen
- Durchsuche die Home-Assistant-Protokolle nach Fehlermeldungen
- Konfiguriere die Integration neu

### „IDM-Abfrage passt kaum in das Abfrageintervall“

Dieses Reparaturproblem erscheint, wenn das Lesen aller Register über mehrere Abfragen hinweg
mindestens 80 % des konfigurierten Abfrageintervalls beansprucht hat. Der Regler bekommt dann
zwischen den Anfragen fast keine Ruhezeit, was sich meist als Zeitüberschreitungen zeigt —
besonders wenn ein zweiter Modbus-Client die Wärmepumpe mitbenutzt.

Was hilft, nach Wirkung geordnet:

1. **Erhöhe das Abfrageintervall** in den Integrationsoptionen. Die meisten Werte ändern
   sich weit langsamer, als eine 10-Sekunden-Abfrage vermuten lässt.
2. **Deaktiviere Entitäten, die du nicht verwendest.** Die Abfrage ist entitätsbezogen: Das
   Register einer deaktivierten Entität wird aus dem Abfrageplan entfernt, was den Zyklus
   direkt verkürzt.
3. **Prüfe auf einen zweiten Modbus-Client** (Energy Manager, eine weitere
   Home-Assistant-Instanz, ein KNX-Gateway), der gleichzeitig die Wärmepumpe abfragt.

Das Problem verschwindet von selbst, sobald die Abfragen wieder komfortabel im Intervall
bleiben. Um die zugrunde liegenden Zahlen zu sehen, aktiviere die **Kommunikationsdiagnose**
in den Optionen — sie legt die Abfragedauer und die Anzahl aktiv abgefragter Register als
Sensoren offen.

## Ein Registerschreibvorgang wird abgelehnt

Symptom: Das Ändern eines Werts (zum Beispiel der Zieltemperatur eines Heizkreises in der
Klima-Karte) schlägt sofort fehl, Home Assistant zeigt einen Schreibfehler, und der Navigator
ändert sich nicht. Das Lesen desselben Registers funktioniert weiterhin.

Die Integration unterscheidet zwei sehr unterschiedliche Ursachen, und die Meldung sagt,
welche davon zutrifft:

**1. Der Schreibvorgang wurde vor dem Senden blockiert.** Es hat keine Modbus-Anfrage Home
Assistant verlassen. Typische Ursachen und ihre Meldungen:

| Meldung | Ursache | Was du tun solltest |
| --- | --- | --- |
| „wurde zu kurz zuvor geschrieben“ | EEPROM-Schreibschutz | Warte das EEPROM-Schreibintervall ab (standardmäßig 60 s) |
| „kann noch nicht geschrieben werden“ | Die Option **Schreib-Cooldown** | Warte die angegebene Zeit ab oder verringere den Cooldown |
| „außerhalb des zulässigen Bereichs“ | Der Wert liegt außerhalb des dokumentierten Registerbereichs | Wähle einen Wert innerhalb der Entitätsgrenzen |
| „von diesem Wärmepumpenmodell nicht unterstützt“ | Das Register ist nicht in der Registerliste des erkannten Modells enthalten | Prüfe das erkannte Navigator-Modell in der Diagnose |

**2. Die Wärmepumpe antwortete mit einem Fehler.** Die Anfrage erreichte den Regler und wurde
von ihm abgelehnt. Die Meldung nennt den Modbus-Exception-Code, und dieselbe Information wird
als `last_write_error` ins Protokoll und in den Diagnose-Download geschrieben.

Ein nur lesbarer Wert, der dennoch als schreibbar dokumentiert ist, geht fast immer auf die
eigenen Zugriffsregeln des Reglers zurück, nicht auf die Integration:

- **Prüfe die GLT-Zugriffseinstellung am Navigator.** Im Bereich Gebäudeleittechnik (GLT)
  pflegt der Regler eine Registerliste mit einer Zugriffsspalte pro Register. Ein dort nicht
  zum Schreiben freigegebenes Register wird abgelehnt, selbst wenn Adresse, Datentyp und Wert
  korrekt sind. Das ist die häufigste Ursache, wenn einige Schreibvorgänge funktionieren
  (Betriebsart, externe Raumtemperatur), andere am selben Gerät aber nicht.
- **Prüfe, ob die Funktion für diesen Heizkreis oder dieses Bauteil aktiviert ist.** Ein
  nicht konfigurierter Heizkreis oder eine vom Installateur nicht freigeschaltete Funktion
  lehnt Schreibvorgänge auf ihre Register ab.
- **Prüfe auf einen zweiten Schreiber.** Eine andere Gebäudeleittechnik, ein Energy Manager
  oder ein Wechselrichter, der dasselbe Register schreibt, kann einen Schreibvorgang wie
  abgelehnt oder sofort zurückgesetzt aussehen lassen.
- **Vergleiche mit dem GLT-Monitor**, wie oben beschrieben. Er zeigt den Wert und die
  Zugriffsrechte, die der Regler selbst sieht.

Füge beim Melden die exakte Protokollzeile bei — sie enthält jetzt den Registernamen, die
Adresse, den Wert und den technischen Grund, zum Beispiel:

```text
The IDM controller refused the write of 24.0 to hc_c_room_setpoint_heat_normal
(address 1405): IdmDeviceError: ... [Modbus exception code 4 (Server Device Failure)]
```

## EEPROM-Warnungen

Wenn du beim Schreiben von Werten eine EEPROM-Warnung erhältst:

- Diese Register haben eine begrenzte Anzahl von Schreibzyklen
- Änderungen an diesen Werten sollten **sparsam** erfolgen
- Die Integration warnt automatisch vor der EEPROM-Empfindlichkeit

## Debug-Protokollierung

Aktiviere die erweiterte Protokollierung:

```yaml
logger:
  default: info
  logs:
    custom_components.idm_heatpump: debug
```

Suche im Protokoll nach:
- `idm_heatpump` - integrationsspezifische Meldungen
- `Modbus read error` - Modbus-Lesefehler
- `Modbus write error` - Modbus-Schreibfehler
- `Decode failed` - Register-Dekodierungsfehler

## Diagnosedaten exportieren

1. Öffne **Einstellungen → Geräte & Dienste**
2. Klicke auf **IDM Heatpump**
3. Klicke auf **Diagnose herunterladen**
4. Hänge die Datei an deinen [Bug-Report](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md) an

Der Export enthält die installierten Versionen der Integration, von Home Assistant Core, Python,
`idm-heatpump-api`, `modbus-connection` und `tmodbus`. Sie sind auch am Diagnose-Sensor
**IDM Heatpump API version** sichtbar. Der Client-Diagnoseblock meldet zusätzlich einen
geschwärzten Endpunkt, die Transport-Quelle, den Socket-Besitz, den aktuellen
Verbindungszustand und ob zentrales Sharing unterstützt wird.

## Bug-Report-Checkliste

Bitte füge bei:

- Wärmepumpen-Modell und Navigator-/Regler-Modell.
- Firmware-Version aus dem Diagnose-Export.
- Home-Assistant-Version plus die Versionen der Integration, von `idm-heatpump-api`,
  `modbus-connection` und `tmodbus`.
- Aktive Heizkreise, Zonenmodule sowie PV-, Solar-, ISC- und Kaskade-Flags.
- Den geschwärzten Diagnose-Export.
- Relevante Protokollzeilen rund um den ersten Fehler.
- Ob das Problem nur das Lesen betrifft, ein fehlgeschlagener Schreibvorgang, ein unverfügbares Register oder ein unerwarteter Wert ist.

Gib keine privaten IP-Adressen, Hostnamen, Seriennummern, Installateur-/Kundendaten oder
ungeschwärzte Netzwerkdetails an.

## 👩‍💻 Für Entwickler (Mock-Tests)

Führe beim Testen von Codeänderungen an der Basislogik **niemals** Schreiboperationen über
Modbus (`write_register`) live gegen eine echte Wärmepumpe aus. Nutze die Test-Suite des
Repository und Fake-Transports für Dekodier-, Enkodier-, Wiederholungs-, Wiederverbindungs-
und Schreibsicherheitstests. Der tmodbus-Adapter ist implementiert und wird automatisch
getestet, aber die schreibgeschützte Validierung an echter Hardware für Setup, FC03, FC04 und
die Wiederverbindungspfade steht noch aus. Hardware-Validierung muss schreibgeschützt bleiben,
sofern der Besitzer nicht ausdrücklich einen bestimmten Schreibvorgang autorisiert.

## Häufige Fehler und Lösungen

| Problem | Lösung |
|---------|--------|
| Hostname nicht gefunden | DNS/Namen korrigieren oder die Wärmepumpen-IP verwenden |
| Verbindung abgelehnt | Modbus TCP aktivieren und Port 502 prüfen |
| Verbindungs-Timeout | IP, Stromversorgung, Firewall, VLAN und Routing prüfen |
| Keine gültige Registerantwort | Slave-ID, Proxy-Ziel und Modbus-Berechtigung prüfen |
| Web-PIN abgelehnt | Lokalen PIN unter „Neu konfigurieren“ neu eingeben oder leeren |
| Integration startet nicht | Die kategorisierte Protokollmeldung lesen und Diagnose herunterladen |
| Falsche Temperaturen | Register-Zuordnung prüfen, Bug melden |
| Schreibvorgang fehlgeschlagen | Register schreibbar? EEPROM-Warnung beachten |
| Alle Entitäten „nicht verfügbar“ | Navigator erreichbar? Modbus TCP aktiviert? |
