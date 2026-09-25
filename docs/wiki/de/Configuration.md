# Konfiguration

## Verbindungsparameter

| Parameter | Beschreibung | Standard |
|-----------|-------------|---------|
| **Host (IP)** | IP-Adresse des IDM Navigator | - (erforderlich) |
| **Port** | Modbus-TCP-Port | 502 |
| **Slave-ID** | Modbus-Slave-ID | 1 |
| **Name** | Name der Integration (zur Unterscheidung mehrerer Instanzen) | IDM Navigator |
| **Lokaler Web-PIN** | Optionaler PIN für lokale Daten des Navigator-Web-Supplements | leer |

Lass den Web-PIN leer, wenn du die Integration nur per Modbus betreiben
möchtest. Modbus bleibt der Basispfad und funktioniert ohne PIN. Wenn du einen
PIN angibst, kann der Einrichtungsfluss zusätzlich einen eingeschränkten
Fallback im reinen Web-Betrieb anbieten, wenn Modbus nicht verfügbar ist.

Der direkte Modbus-Socket gehört ausschließlich dieser Integration und
verwendet `modbus-connection` mit dem tmodbus-Backend. Jeder
Konfigurationseintrag besitzt eine eigene Verbindung; ein zentrales,
eintragsübergreifendes Teilen der Verbindung durch Home Assistant ist derzeit
nicht verfügbar.

## Optionen

Nach der Eingabe der Verbindungsdaten wählst du eine Tiefe der geführten
Einrichtung:

| Tiefe | Was der Assistent abfragt |
|-------|---------------------|
| Standard | Funktionsauswahl, benötigte Sensoren und sichere Standardwerte |
| Erweitert | Dieselben Funktionen plus übliche Intervalle, Schwellenwerte und Feineinstellungen |
| Experte | Dieselben Funktionen plus alle verfügbaren Transport- und Weiterleitungseinstellungen |

Jede Tiefe bietet denselben Funktionsumfang. Wähle nur die Funktionen aus, die
du ändern möchtest; jede ausgewählte Funktion öffnet eine kurze Seite für ihren
Schalter sowie die gegebenenfalls benötigten Sensor-, Heizkreis- oder
Gruppenzuordnungen. Eine abschließende Bestätigung speichert die Konfiguration
und lädt den Eintrag neu. Einstellungen aus einem tieferen Modus bleiben
gespeichert, wenn du später einen einfacheren Modus wählst. Du kannst die Tiefe
jederzeit über Neu konfigurieren > Funktionen wechseln. Neu konfigurieren >
Verbindung ändert Host, Web-Zugriff und Modbus-Proxy. Bestehende Optionen
bleiben unverändert, wenn ihre Funktion im Assistenten nicht ausgewählt war.

Wenn Beta-Funktionen neu aktiviert werden, erscheint vor dem Speichern eine
zusätzliche Bestätigungsseite. Sie ist getrennt von der Bestätigung der
alleinigen Steuerung, die der automatische Warmwasser-Manager und der
Komfortzeitplan verlangen.

### Funktionsprofil

Das **Funktionsprofil** steuert optionale IDM-spezifische Entitäten:

| Profil | Aktivierte Funktionalität |
|---------|-----------------------|
| `iDM Smart Energy & Comfort` | Berechnete COP- und Abweichungssensoren, Verdichter-Zyklusanalyse, persistente Energie-, COP- und Kostenstatistiken, Kurzzyklus-Erkennung und Warmwasser-Boost-Steuerungen; optionale Health- und Komfortfunktionen |
| `Vanilla` | Zentrale IDM-Register-Entitäten, Klima-Steuerungen, Warmwasserbereiter, Diagnose und konfigurierte Webdaten |

Das Smart-Profil ist standardmäßig aktiviert, um das vollständige bestehende
Verhalten der Integration zu erhalten. Vanilla ist nützlich, wenn nur die
ursprünglichen Reglerwerte und Steuerungen verfügbar gemacht werden sollen. Der
Wechsel des Profils lädt den Eintrag neu; optionale Entitäten können entfernt
oder neu erstellt werden, während die Kern-Entitäts-IDs unverändert bleiben.

Das Profil schreibt von sich aus keine Energiewerte und verändert die Heizkurve
nicht. Externe PV-, Batterie-, Raumtemperatur-, Feuchtigkeits- und
Speicher-Weiterleitung bleiben separate Opt-in-Funktionen und sind in ihren
eigenen Abschnitten dokumentiert.

Smart stellt außerdem persistente Energie-, COP-, Kosten-, CO₂- und optionale
PV-Eigenverbrauchs-Statistiken bereit, wenn die benötigten Leistungsregister
verfügbar sind. Strompreis und CO₂-Faktor werden lokal in den Optionen
konfiguriert; sie werden von keinem externen Dienst abgerufen.

Wenn die **Gerätehierarchie** aktiviert ist, werden optionale Entitäten in
eigenen logischen Gruppen geführt: **iDM Analytics**, **iDM Health Monitor**
und **iDM Comfort**. Bestehende Regler-, Heizkreis-, Warmwasser- und
Web-Entitäten bleiben in ihren bisherigen Gruppen und behalten ihre
Entitäts-IDs.

### Zuordnung und Weiterleitung externer Leistung

Die Kategorie **Externe Leistungsweiterleitung** ordnet bestehende
Home-Assistant-Sensoren PV-Überschuss, PV-Produktion, Hausverbrauch, Batterie
Laden/Entladen, Batterie-SOC und Heizstab-Leistung zu. Der
Weiterleitungsschalter ist standardmäßig aus. Wenn aktiviert, werden gültige
Werte bei Änderungen der Quelle und periodisch (Standard: 60 Sekunden) in die
entsprechenden IDM-GLT-Register geschrieben.

Leistungssensoren müssen W, kW oder MW liefern; die Weiterleitung rechnet in kW
um. Der Batterie-SOC muss ein ganzzahliger Prozentsatz von 0 bis 100 sein. Das
Batterievorzeichen kann beibehalten oder invertiert werden, um zur Konvention
der Quelle zu passen. Ungültige oder außerhalb des Bereichs liegende Werte
werden übersprungen; eine nicht verfügbare Quelle schreibt keinen Ersatzwert
Null. Leere Felder lassen ihre Register unangetastet. Sorge dafür, dass nicht
gleichzeitig ein anderer Energiemanager dasselbe Register beschreibt.

Die gespeicherte Zuordnung versorgt auch die optionale PV-Schätzung und den
automatischen Warmwasser-Manager. Sie können eine bestehende Zuordnung lesen,
während die Weiterleitung aus ist. Der aktuelle geführte Assistent zeigt die
Zuordnungsseite nur, wenn die Weiterleitung aktiviert ist; eine separate
Seite zur Quellenauswahl nur für den Lesezugriff gibt es noch nicht. Siehe
[Einrichtung der externen Leistungsweiterleitung](Installation-and-Setup#automatische-externe-leistungsweiterleitung-von-home-assistant)
zur Vorbereitung des Reglers und zu den Feldzuordnungen.

### Optionaler PV-Energiemanager

Die Option **Automatisches Warmwasser-Laden mit PV-Überschuss** ist
standardmäßig aus. Sie startet nur den bestehenden sicheren Warmwasser-Boost,
wenn der ausgewählte PV-Überschuss verfügbar ist. Sie setzt die Zuordnung der
externen Leistungsquellen und die ausdrückliche Bestätigung voraus, dass Home
Assistant der einzige Warmwasser-Regler ist. Das ist eine Erklärung der
alleinigen Steuerung, keine automatische Erkennung von Smartfox, openWB oder
einem anderen Regler. Deaktiviere konkurrierende Warmwasser-Steuerung, bevor
du sie bestätigst.

Fehlende, nicht verfügbare oder ungültige Quellwerte führen zum sicheren
Abschalten (fail closed). Der Manager schreibt keine GLT-Energiregister und
verändert weder das normale Heizen noch die Heizkurve oder den Heizstab.
Tarif-, Wetter- und Heiz-Vorsteuerungen werden durch diese Option nicht
aktiviert. Ein ausgewählter Tarifsensor verändert nur die Kostenrechnung; eine
automatische preisbasierte Heizsteuerung ist nicht implementiert. Siehe
[Smart Energy & Comfort](Smart-Energy-and-Comfort#optionale-pv-uberschuss-warmwasser-automation)
zu Quellenrangfolge, Standardwerten und dem Verhalten eines bereits laufenden
Boosts.

### Optionaler Komfortzeitplan und Berater

Der Komfortzeitplan ist standardmäßig deaktiviert und erfordert die
ausdrückliche Bestätigung, dass nur ein einziger Regler aktiv ist. Er schreibt
nur das Raumtemperatur-Soll des ausgewählten Heizkreises innerhalb des
konfigurierten Tagesfensters und stellt danach den vorherigen Sollwert wieder
her, wenn der aktuelle Wert noch dem geplanten Sollwert entspricht. Eine
manuelle Änderung, die während eines aktiven Zeitplans erfolgt, bleibt
unangetastet. Der erweiterte Modus bietet bis zu 16 Tagesfenster über alle
konfigurierten Heizkreise hinweg, auch über Nacht, in der in Home Assistant
konfigurierten Zeitzone. Siehe
[Zeitplan-Beispiele](Smart-Energy-and-Comfort#komfort-zeitplan-und-schreibgeschutzte-berater).

Der Heizkurven-Assistent und der Wetter-Vorheiz-Berater sind schreibgeschützt.
Sie veröffentlichen Empfehlungen, ohne ein IDM-Register zu verändern. Der
Wetterberater erfordert eine ausgewählte Home-Assistant-`weather`-Entität.
Alle Komfort-Entitäten erscheinen unter **iDM Comfort**, wenn die
Gerätehierarchie aktiviert ist.

### Optionaler iDM Health Monitor

Der **iDM Health Monitor** ist standardmäßig deaktiviert und fügt
schreibgeschützte Diagnose-Entitäten hinzu. Er prüft Kommunikationsfehler,
die Verdichter-Startfrequenz, einen aktuell niedrigen COP, die
Warmwasser-Temperaturabweichung und unplausible Temperaturwerte. Der Sensor
`iDM health report` zeigt `ok` oder `problem` und listet aktive Prüfungen in
seinen Attributen auf. Er verändert keine Wärmepumpen-Einstellung.

### Abfrageintervall

Das Abfrageintervall legt fest, wie oft Register abgefragt werden.

| Wert | Empfehlung |
|-------|---------------|
| 10 Sekunden | Für aktives Monitoring (Standard) |
| 30 Sekunden | Ausgewogen |
| 60 Sekunden | Für ruhigere Systeme |

### Web-Supplement-Daten

Die Integration kann optional zusätzliche lokale Navigator-Webdaten über
`idm-heatpump-api` lesen. Dies ist schreibgeschützt und additiv. Verwendet
wird es für Werte wie die Navigator-Generation, die Softwareversion, das
Wärmepumpenmodell, ausgewählte Web-UI-Diagnosen und Infosystem-Meldungen des
Navigator 10.

| Option | Beschreibung | Standard |
|--------|-------------|---------|
| Web-Supplement-Daten | Aktiviert die optionale lokale Web-Abfrage; sie wird nur mit einem gültigen PIN aktiv | ein |
| Web-Supplement-Intervall | Separates Abfrageintervall für Webdaten | 30 Sekunden |
| Web-Host | Optionaler separater Host für das Navigator-Webinterface, nützlich, wenn Modbus über einen Proxy läuft | Modbus-Host |

**Wichtiges Verhalten:**

- Wenn kein PIN konfiguriert ist, wird kein Web-Client erstellt und die
  Integration bleibt im reinen Modbus-Betrieb.
- Während Einrichtung, Neukonfiguration und Reparatur wird das Modbus-Modell
  nur dazu verwendet zu wählen, welches lokale Webprotokoll zuerst versucht
  wird. Schlägt dieser Versuch fehl, wird auch das andere unterstützte
  Protokoll getestet. Das tatsächlich erfolgreiche Protokoll wird mit dem
  Konfigurationseintrag gespeichert.
- Während der normalen Abfrage wird der erfolgreiche, authentifizierte Client
  wiederverwendet. Läuft seine Sitzung ab oder schlägt die Verbindung fehl,
  wird der Client geschlossen und dasselbe bekannte Protokoll sofort neu
  aufgebaut. Die andere Navigator-Generation wird bei der routinemäßigen
  Laufzeitwiederherstellung nicht geprüft.
- Nach dem Austausch des Navigators, einer Änderung des Web-Endpunkts oder
  einer Firmware-Änderung, die das lokale Interface verändert, führe
  **Neu konfigurieren → Verbindungseinstellungen ändern** aus, damit die
  Protokollerkennung erneut laufen kann.
- Ist der PIN während Einrichtung oder Neukonfiguration falsch, zeigt das
  Formular den PIN-Fehler sofort an. Nach einem Modbus-Fehler kann der PIN
  direkt im Wiederherstellungsformular korrigiert werden, ohne die Einrichtung
  neu zu starten.
- Ist das Webinterface später nicht erreichbar, läuft die Modbus-Abfrage
  weiter.
- Die Web-Abfrage läuft separat und startet kurz nach der Modbus-Abfrage, damit
  nicht beide Protokolle exakt im selben Moment den Regler belasten.
- Modbus-Registerwerte haben immer Vorrang. Web-Sensoren werden nur für
  zusätzliche Werte oder Werte ohne bestehende Modbus-Entität erstellt.
  Web-Metadaten zu Modell/Firmware können ein unbekanntes Modbus-Ergebnis
  ergänzen, ein eindeutiger Familienkonflikt wird aber ignoriert.
- Wird ein Modbus-Proxy verwendet, trage die Proxy-IP als **Host** und die
  ursprüngliche Wärmepumpen-IP als **Web-Host** ein, damit das lokale
  Navigator-Webinterface weiterhin erreichbar bleibt.

Der Navigator 2.0 verwendet einen lokalen HTTP/CSRF-Login; Navigator 10 und
Navigator Pro verwenden die WebSocket-Login-Familie des Navigator 10. Siehe
[Lokales Navigator-Webinterface](Local-Web-Interface) für die vollständige
Zustandsmaschine aus Erkennung und Wiederherstellung.

### Raumtemperatur-Weiterleitung

Die Raumtemperatur-Weiterleitung ist optional und standardmäßig deaktiviert.
Wenn aktiviert, kann die Integration ausgewählte Home-Assistant-Temperatursensoren
in die externen IDM-Raumtemperatur-Register der aktiven Heizkreise schreiben,
zum Beispiel `hc_a_ext_room_temp`.

| Option | Beschreibung | Standard |
|--------|-------------|---------|
| Raumtemperatur-Weiterleitung | Aktiviert die Weiterleitung für ausgewählte Heizkreise | aus |
| Weiterleitungsintervall | Periodisches Aktualisierungsintervall für ausgewählte Raumtemperaturen | 300 Sekunden |
| Weiterleitungstoleranz | Minimale Änderung, bevor ein wiederholter Wert erneut geschrieben wird | 0.2 °C |
| Sensor je Heizkreis | Home-Assistant-Temperatur-Entität, die weitergeleitet wird | leer |

**Wichtiges Verhalten:**

- Werte werden bei Zustandsänderungen des Sensors geschrieben und zusätzlich
  periodisch aktualisiert.
- Ungültige, nicht verfügbare, nicht numerische oder außerhalb des Bereichs
  liegende Werte werden übersprungen.
- Ein Heizkreis ohne ausgewählten Sensor bleibt unangetastet.
- Diese Funktion schreibt Modbus-Werte. Verwende Sensoren, die die
  tatsächliche Raumtemperatur abbilden, die die Wärmepumpe sehen soll.

### Externe Feuchtigkeits-Weiterleitung

Die externe Feuchtigkeits-Weiterleitung ist optional und standardmäßig
deaktiviert. Wenn aktiviert, leitet die Integration einen ausgewählten
Home-Assistant-Feuchtigkeitssensor in das globale IDM-GLT-Feuchtigkeitsregister
(`ext_humidity`) weiter. Anders als die Raumtemperatur hat die Feuchtigkeit
kein Register je Heizkreis, daher kann nur ein einziger Sensor ausgewählt
werden.

| Option | Beschreibung | Standard |
|--------|-------------|---------|
| Feuchtigkeits-Weiterleitung | Aktiviert die Weiterleitung des ausgewählten Sensors | aus |
| Weiterleitungsintervall | Periodisches Aktualisierungsintervall | 300 Sekunden |
| Weiterleitungstoleranz | Minimale Änderung, bevor ein wiederholter Wert erneut geschrieben wird | 2.0 % |
| Feuchtigkeitssensor | Home-Assistant-Feuchtigkeits-Entität, die weitergeleitet wird | leer |

Dieselben Verhaltenshinweise wie bei der Raumtemperatur-Weiterleitung gelten:
Werte werden bei Zustandsänderungen geschrieben und periodisch aktualisiert,
ungültige oder außerhalb des Bereichs liegende Werte werden übersprungen, und
ein leeres Sensorfeld deaktiviert die Weiterleitung.

### Externe Speichertemperatur-Weiterleitung

Die externe Speichertemperatur-Weiterleitung ist optional und standardmäßig
deaktiviert. Wenn aktiviert, leitet die Integration bis zu vier ausgewählte
Home-Assistant-Temperatursensoren in die festen IDM-GLT-Speicherregister
weiter: Wärmespeicher (`glt_heat_storage_temp`), Kältespeicher
(`glt_cold_storage_temp`) sowie Warmwasserspeicher unten/oben
(`glt_dhw_temp_bottom` / `glt_dhw_temp_top`).

| Option | Beschreibung | Standard |
|--------|-------------|---------|
| Speichertemperatur-Weiterleitung | Aktiviert die Weiterleitung für ausgewählte Register | aus |
| Weiterleitungsintervall | Periodisches Aktualisierungsintervall | 300 Sekunden |
| Weiterleitungstoleranz | Minimale Änderung, bevor ein wiederholter Wert erneut geschrieben wird | 0.5 °C |
| Sensor je Speicherregister | Home-Assistant-Temperatur-Entität, die weitergeleitet wird | leer |

Dieselben Verhaltenshinweise wie bei der Raumtemperatur-Weiterleitung gelten:
Werte werden bei Zustandsänderungen geschrieben und periodisch aktualisiert,
ungültige oder außerhalb des Bereichs liegende Werte werden übersprungen, und
ein leeres Feld eines Registers lässt dieses unangetastet.

### KNX-Bridge

Die KNX-Bridge ist optional und standardmäßig deaktiviert. Wenn aktiviert,
veröffentlicht die Integration die IDM-KNX-Kommunikationsobjekte auf einem
KNX-Bus und nimmt Befehle von ihm entgegen — sie ersetzt das
Weinzierl-KNX-IP-BAOS-Gateway-Modul, das IDM für den Navigator vertreibt. Sie
steuert die Home-Assistant-[KNX-Integration](https://www.home-assistant.io/integrations/knx/)
an, die eingerichtet sein muss: Gateway, Tunnelling und KNX Secure kommen von
dort.

| Option | Beschreibung | Standard |
|--------|-------------|---------|
| KNX-Bridge aktivieren | Schaltet die Bridge ein und zeigt den Schritt für die Gruppenadressen | aus |
| Werte an KNX senden | Veröffentlicht bei jeder Wertänderung ein Telegramm | ein |
| Befehle von KNX annehmen | Schreibt eingehende Werte auf beschreibbaren Objekten in die Wärmepumpe | ein |
| Leseanforderungen beantworten | Antwortet auf ein KNX-Lesetelegramm mit dem aktuellen Wert | ein |
| Vollständiges Wiederholungsintervall | Sendet jeden Wert periodisch erneut; 0 sendet nur bei Änderung | 0 Sekunden |
| Änderungstoleranz | Minimale Änderung, bevor ein numerischer Wert erneut gesendet wird | 0.1 |
| Basis-Gruppenadresse | Objektnummern werden zu dieser Adresse addiert | `8/0/0` |
| Objektgruppen | Welche Teile des Katalogs teilnehmen | alle |
| Gruppenadressen-Overrides | `register = address` pro Zeile für abweichend adressierte Objekte | leer |

Gruppenadressen werden als `Basisadresse + IDM-Objektnummer` abgeleitet; mit
der Standardbasis landet Objekt 1 (Außentemperatur) auf `8/0/1` und Objekt 222
(Modus Heizkreis A) auf `8/0/222`. Der gesamte Katalog passt in eine
Hauptgruppe. Verwende `idm_heatpump.export_knx_group_addresses`, um die
vollständige Tabelle für deinen Regler zu erhalten.

Alle Details, einschließlich der Objektgruppen und Datenpunkttypen, stehen in
[KNX-Bridge](KNX-Bridge).

### Heizkreise

Wähle die aktiven Heizkreise (A bis G). Nur aktivierte Heizkreise erzeugen Entitäten in Home Assistant.

### Zonen

Gib die Anzahl der Zonenmodule (0–10) und die aktiven Räume je Modul an. Die Integration unterstützt bis zu 8 Räume je Zone; 6 ist der API-Standard für die aktuelle Navigator-10-Hardware. Konfiguriere nur physisch vorhandene Räume, um unnötigen Validierungsverkehr für einzelne Raummodi zu vermeiden.

### Codes für die Fachmann-Ebene

Aktiviere diese optionale Funktion, um zwei Sensor-Entitäten hinzuzufügen, die
die aktuellen Zugangscodes für *Fachmann Ebene 1* und *Fachmann Ebene 2* auf
dem IDM Navigator anzeigen. Die Funktion ist standardmäßig deaktiviert.

| Sensor | Beschreibung |
|--------|-------------|
| `sensor.{name}_fachmann_ebene_1` | Aktueller Zugangscode für die Fachmann-Ebene 1 |
| `sensor.{name}_fachmann_ebene_2` | Aktueller Zugangscode für die Fachmann-Ebene 2 |

Die Sensoren aktualisieren sich jede Minute und können in einem
Home-Assistant-Dashboard oder in Benachrichtigungen verwendet werden. Es sind
von der Integration bereitgestellte Hilfssensoren statt Modbus-Registerwerte,
daher erscheinen sie nicht im Modbus-Registerkatalog.

Behandle beide Sensorzustände als sensible Zugangsinformationen. Aktiviere sie
nur bei Bedarf, beschränke die Sichtbarkeit im Dashboard, und gib die Werte
nicht in öffentlichen Screenshots, Support-Beiträgen, Benachrichtigungen an
geteilte Geräte oder Logs weiter. Die Berechnungsmethode ist bewusst nicht
Teil der öffentlichen Dokumentation.

### Raumnamen

Für jeden Raum in jeder Zone kannst du einen eigenen Namen vergeben. Diese Namen werden als Entitätsnamen in Home Assistant verwendet.

## Neukonfiguration

1. Öffne **Einstellungen → Geräte & Dienste**
2. Klicke auf **IDM Heatpump**
3. Klicke auf **Neu konfigurieren**
4. Wähle die benötigte Aktion:
   - **Funktionen** öffnet die Standard-, Erweitert- oder Experte-Einrichtung,
     um Einstellungen ausgewählter Funktionen zu ändern, ohne nicht
     ausgewählte Kategorien anzutasten.
   - **Verbindungseinstellungen ändern** aktualisiert nach Prüfung Host, Port,
     Slave-ID, lokalen Web-PIN und Proxy-Einstellungen.
   - **Aktuelle Verbindung testen** führt eine schreibgeschützte Prüfung mit
     den gespeicherten Einstellungen durch. Es wird nichts gespeichert und
     niemals in Modbus-Register geschrieben.

Der Test liest ein bekanntes IDM-Modbus-Register. Schlägt das fehl, grenzt
eine kurze DNS/TCP-Prüfung den Netzwerkfehler genauer ein. Ist ein lokaler
Web-PIN konfiguriert, prüft er zusätzlich den Navigator-Web-Endpunkt und die
Anmeldung. Das Ergebnis unterscheidet Hostname, abgelehnte Verbindung,
Timeout, nicht erreichbaren Endpunkt, fehlende Modbus-Antwort, ungültigen PIN
und Webinterface-Fehler. Sende das Ergebnisformular erneut ab, um den Test zu
wiederholen.

Ein falscher Web-PIN wird beim Ändern der Verbindung direkt abgelehnt. Bleibt
das Feld leer, bleibt der Eintrag im reinen Modbus-Betrieb.

Schlägt Modbus fehl, während ein gültiger Web-PIN vorliegt, bietet der Fluss
den reinen Web-Betrieb an und listet dessen Einschränkungen klar auf.
**Modbus-Verbindung erneut versuchen** führt zurück zum richtigen
Neukonfigurationsformular; das Zurückschalten aus dem reinen Web-Betrieb
löscht die Fallback-Kennzeichnung nach einer erfolgreichen Modbus-Prüfung.
Bestehende Heizkreis-, Zonen- und erweiterte Modbus-Optionen bleiben
erhalten, während der reine Web-Betrieb aktiv ist, und stehen nach der
Wiederherstellung von Modbus wieder zur Verfügung.

Verwende **Konfigurieren** oder **Neu konfigurieren → Funktionen
konfigurieren**, um das vollständige Optionsformular zu bearbeiten,
einschließlich Abfrageintervall, Heizkreisen, Zonen, Smart Energy & Comfort,
Gesundheitsüberwachung, Weiterleitungen und automatischen Steuerungen. Das
Speichern lädt die Integration neu, sodass optionale Entitäten den
ausgewählten Einstellungen folgen. Neu aktivierte Beta-Funktionen erfordern
vor dem Speichern eine ausdrückliche Bestätigung.

### Erweiterte Modbus-Optionen

Der eingeklappte Abschnitt **Erweiterte Modbus-Einstellungen** bietet
zusätzlich zu Timeout- und Wiederholungseinstellungen auch Steuerung für
fortgeschrittene Nutzer:

- **Pause zwischen Anforderungen (0–0.5 Sekunden)** ist der minimale
  Abstand, den die Verbindung zwischen zwei Modbus-Anforderungen einhält,
  gemessen vom Ende einer Anforderung bis zum Beginn der nächsten. `0 s`
  (Standard) sendet Anforderungen unmittelbar hintereinander, wie jede
  Version vor dieser Option. Erhöhe sie, wenn der Regler oder ein
  Modbus-Gateway mit „device busy" antwortet, Anforderungen verwirft oder
  unter einer dichten Anforderungsfolge in einen Timeout läuft. Die Pause
  gilt für jede Anforderung, sodass ein vollständiger Abfragezyklus
  entsprechend länger dauert: bei rund 40 Batches verlängert `0.1 s` einen
  Zyklus um etwa 4 Sekunden. Beginne bei `0.05 s`.
- **Pause nach dem Verbinden (0–5 Sekunden)** wird einmal nach dem Aufbau
  der Verbindung abgewartet, bevor die erste Anforderung gesendet wird — beim
  ersten Verbinden und bei jedem Wiederverbinden, nicht je Anforderung. `0 s`
  (Standard) sendet sofort. Erhöhe sie für Gateways, die eine Verbindung
  annehmen, bevor sie antworten können.
- **Abfrage-Jitter (0–20%)** fügt jeder Abfrage eine zufällige Verzögerung
  von bis zum ausgewählten Prozentsatz des Abfrageintervalls hinzu. Das
  verteilt Netzwerk- und Reglerlast, wenn mehrere Wärmepumpen gleichzeitig
  mit der Abfrage beginnen. `0%` deaktiviert den Jitter.
- **Erweiterte Kommunikationsdiagnose** erstellt Diagnose-Entitäten für die
  letzte erfolgreiche Abfrage, die Abfragedauer, aufeinanderfolgende
  Fehlschläge und die Anzahl aktiver Register. Abfragen und Fehlschläge
  insgesamt sind als Attribute und in der heruntergeladenen Diagnose
  enthalten.
- **Schreib-Cooldown (0–600 Sekunden)** gilt je Register. Eine zweite
  Schreiboperation auf dasselbe Register innerhalb des konfigurierten
  Intervalls wird abgelehnt, ohne etwas an die Wärmepumpe zu senden; Home
  Assistant meldet die verbleibende Wartezeit. `0` deaktiviert diesen Schutz
  vollständig; eine Änderung geschieht auf eigenes Risiko. Unterschiedliche
  Registeradressen blockieren einander nicht.

Der allgemeine Schreib-Cooldown ist unabhängig vom EEPROM-Schutz der API.
EEPROM-sensitive Register unterliegen daher weiterhin dem separat
konfigurierten EEPROM-Intervall und seinen Sicherheitsregeln.

## Laufzeit- und API-Versionen

IDM Heatpump ist eine benutzerdefinierte Home-Assistant-Integration und kein
Add-on. Die Integration erstellt einen Diagnosesensor mit dem Namen
**IDM-Heatpump-API-Version** (Englisch: **IDM Heatpump API version**). Sein
Zustand ist die tatsächlich installierte Version der `idm-heatpump-api`-Distribution.
Die Sensor-Attribute zeigen außerdem:

- `integration_version`: installierte Version der benutzerdefinierten Integration
- `modbus_connection_version`: installierte Version der Verbindungsbibliothek
- `tmodbus_version`: installierte Version des direkten Socket-Backends
- `home_assistant_version`: installierte Home-Assistant-Core-Version
- `python_version`: Version der Python-Laufzeit

Dieselbe Versionsmenge ist in der heruntergeladenen Diagnose enthalten. Die
Integration und die Versionen ihrer direkten Abhängigkeiten werden beim Start
des Eintrags zusätzlich protokolliert. Das ist der maßgebliche Weg, die
Laufzeit zu prüfen; die in
`custom_components/idm_heatpump/manifest.json` gepinnte Version beschreibt,
was installiert sein sollte, während der Sensor zeigt, was tatsächlich
geladen ist.

### Versionspaarung von Integration und API

Dieses Projekt hat zwei unabhängig versionierte Pakete:

| Paket | Aktuell getestete Version | Wann eine neue Version nötig wird |
|---------|------------------------|-----------------------------|
| Benutzerdefinierte Home-Assistant-Integration | `0.17.0-beta.2` (vorherige stabile Version: `0.16.2`) | Änderungen an Integrationscode, Konfigurationsfluss, Diagnose, Entitäten oder der mitgelieferten Nutzerdokumentation |
| Verbindungsbibliothek | `modbus-connection==4.12.2` | Änderungen am Transportvertrag, am Verbindungslebenszyklus oder an der Fehlersemantik |
| Direktes Socket-Backend | `tmodbus[async-serial]==0.6.2` | Änderungen an der Leitungs-/Backend-Implementierung |
| Python-Register-/Web-Bibliothek | `idm-heatpump-api[web]==2.4.3` | Änderungen an Registerschema, Kodierung/Dekodierung, Batching, Modellerkennung, Schreibsicherheit oder der wiederverwendbaren Web-Client-Implementierung |

Das Manifest listet die getestete Laufzeit in dieser Reihenfolge:
`modbus-connection==4.12.2`, `tmodbus[async-serial]==0.6.2`
und `idm-heatpump-api[web]==2.4.3`. Die ersten beiden Pakete besitzen den
direkten Socket. `idm-heatpump-api` bleibt für die IDM-spezifische
Gerätelogik verantwortlich und besitzt ihre eigene Ausnahmehierarchie; die
Integration installiert kein pymodbus mehr. `4.12.2` ist die Version von
`modbus-connection`, keine Version der IDM-Integration. Der Transport wurde
erstmals mit der IDM-Integrations-Beta `0.11.0-beta.1` ausgeliefert.

Der Adapter ist implementiert, durch automatisierte Tests abgedeckt und auf
einem Navigator 10 live verifiziert. Seine geschwärzte Diagnose meldet
`source: modbus_connection.tmodbus`, `owns_socket: true` und
`supports_shared_connection: false`. Die Abdeckung für Navigator 2.0/Pro und
ein absichtlicher Verbindungstrennungs-/Wiederverbindungstest stehen noch
aus; Schreibzugriffe auf echter Hardware bleiben außerhalb des Umfangs, sofern
nicht ausdrücklich autorisiert. IDM Heatpump ist eine benutzerdefinierte
Integration, kein Home-Assistant-Add-on.

## Debug-Protokollierung

Aktiviere erweiterte Protokollierung für die Fehlerbehebung:

```yaml
logger:
  default: info
  logs:
    custom_components.idm_heatpump: debug
```

## EEPROM-Hinweis

Bestimmte Register sind **EEPROM-sensitiv** (insgesamt 88). Diese Register werden beim Schreiben im EEPROM gespeichert und haben eine begrenzte Anzahl Schreibzyklen. Die Integration warnt vor übermäßigem Schreiben dieser Register.

## Zyklisches GLT-Schreiben

Die Register 1696 und 1698 (GLT-Temperaturanforderungen) müssen zyklisch alle 10 Minuten geschrieben werden, um aktiv zu bleiben. Die Schalter-Entitäten für GLT-Anforderungen erledigen das automatisch.

## Experimenteller KI-Anlagenberater (geplant)

Der experimentelle Berater liefert tägliche/wöchentliche Berichte und Erklärungen zu Gesundheit und Effizienz. Er ist standardmäßig aus und enthält weder Werkzeuge zur Anlagensteuerung noch eine Freigabe für Sprachassistenten. Ollama läuft lokal; v0.17.2-b10 ergänzt einzeln zu bestätigende OpenAI- und Z.ai-Berichte mit begrenzten Anfragen. Siehe [Einrichtung, Berichts-Aktionen, Datenabdeckung und Einschränkungen](Experimental-AI-Adviser).
