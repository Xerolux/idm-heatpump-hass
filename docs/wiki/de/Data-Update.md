# Datenaktualisierung

## Wie werden die Daten abgerufen?

Die Integration nutzt Modbus TCP, um Registerdaten direkt von der IDM-Wärmepumpe zu lesen. Die gesamte Kommunikation läuft **lokal** — es gibt keine Cloud-Verbindung.

## Abfrage-Mechanismus

Die Integration verwendet den **DataUpdateCoordinator** von Home Assistant:

- Modbus-gestützte Entitäten teilen sich **eine koordinierte Aktualisierung**, die aus mehreren gruppierten Modbus-Anfragen besteht
- Modbus-Register werden nur gruppiert, wenn ihre Bereiche **exakt angrenzend und nicht überlappend** sind, mit bis zu 40 Modbus-Wörtern pro Anfrage
- Werte außerhalb der deklarierten Enum- oder numerischen Metadaten werden einzeln neu gelesen; bestätigte Problemregister bleiben für die aktuelle Client-Sitzung im Pfad der Einzelablesung
- Bekannte `sentinel_values` wie `-1`, `254` oder `255` bedeuten dort nicht verfügbar/ungenutzt, wo sie von den Register-Metadaten deklariert werden, und gelten nicht als korrupte Werte
- Der Koordinator aktualisiert nach jeder erfolgreichen Abfrage alle Entitäten gleichzeitig
- Optionale Web-Supplement-Daten nutzen einen eigenen Abfragezyklus und starten etwas nach der Modbus-Abfrage, damit beide Protokolle den Regler nicht exakt zur gleichen Zeit belasten.

## Entitätsbewusste Abfrage und Smart-Verbraucher

Der Abfrageplan behält die Register, die aktivierte Entitäten und deklarierte Hintergrund-Verbraucher benötigen. Seit 0.17.2-b6 halten die Smart-Energiestatistiken beide Leistungseingänge vor, selbst wenn ihre rohen Sensoren deaktiviert sind. Ein aktiver Komfort-Zeitplan behält ebenfalls seinen Heizkreis-Sollwert und gibt diese Anforderung beim Beenden wieder frei. Eine rohe Entität zu deaktivieren deaktiviert daher weder eine aktive Automation noch den Energiezähler; schalte stattdessen die entsprechende Funktion aus.

## Konfiguriertes Intervall

Das Abfrageintervall ist **frei konfigurierbar** (5–300 Sekunden, Standard: 10 Sekunden):

- **Einstellungen → IDM Heatpump → Konfigurieren → Abfrageintervall**
- Kürzere Intervalle liefern schnellere Updates, erzeugen aber mehr Netzwerkverkehr
- Empfehlung: 10–30 Sekunden für den normalen Betrieb

Optionale Web-Supplement-Daten haben ein eigenes Intervall (Standard: 30 Sekunden). Sie werden nur verwendet, wenn Web-Supplement-Daten aktiviert sind und eine lokale Navigator-Web-PIN konfiguriert ist.

Der erfolgreiche Web-Client für Navigator 2.0 oder Navigator 10/Pro wird zwischen den Web-Abfragen wiederverwendet. Eine fehlgeschlagene oder abgelaufene Sitzung wird verworfen und mit demselben bekannten Protokoll neu aufgebaut. Beide Protokolle werden nur getestet, solange die Variante unbekannt ist, oder wenn Einrichtung/Rekonfiguration/Reparatur eine frische Verbindungsvalidierung durchführt.

Die Raumtemperatur-Weiterleitung wird, wenn aktiviert, außerhalb der normalen Lese-Abfrage behandelt. Ausgewählte Home-Assistant-Temperatursensoren werden bei Zustandsänderungen in die passenden externen Raumtemperatur-Register geschrieben und periodisch aufgefrischt (Standard: 300 Sekunden).

## Verfügbarkeit von Entitäten

Eine Entität wird als **nicht verfügbar** markiert, wenn:
- die Verbindung zur Wärmepumpe unterbrochen ist
- das Modbus-Register einen seiner deklarierten Nicht-verfügbar-Sentinelwerte zurückgibt (zum Beispiel `-1.0`, `254` oder `255`, je nach Register)
- die Option „Unbenutzte Sensoren ausblenden“ eine bereits als ungenutzt bekannte Entität bei der Einrichtung auslässt; eine Entität, die später einen deklarierten Sentinelwert zurückgibt, wird nicht verfügbar
- ein Web-Supplement-Sensor im letzten erfolgreichen Web-Schnappschuss keinen Wert hat

## Schreiboperationen (schreibbare Entitäten)

Zahl-, Auswahl- und Schalter-Entitäten können Werte auf die Wärmepumpe schreiben:
1. Der neue Wert wird sofort **optimistisch** in der Benutzeroberfläche angezeigt
2. Danach wird eine vollständige Aktualisierung ausgelöst, um den tatsächlichen Gerätezustand zu bestätigen
3. **EEPROM-geschützte Register** dürfen nur einmal pro Minute beschrieben werden, um Hardwareverschleiß zu vermeiden

## Fehlerbehandlung

- Bei Verbindungsfehlern wird automatisch ein **Reparaturproblem** in Home Assistant erstellt
- Sobald die Verbindung wiederhergestellt ist, verschwindet das Reparaturproblem automatisch
- Der DataUpdateCoordinator protokolliert Verbindungsfehler einmalig (nicht in jedem fehlgeschlagenen Zyklus)
- Ausgeschöpfte Timeout-/Keine-Antwort-Fehlschläge brechen die Abfrage ab und lösen den normalen Reparaturablauf aus; sie zählen nie als dauerhafte Fehler einzelner Register
- Nicht unterstützte optionale Adressen werden isoliert und bei späteren Abfragen übersprungen, statt sämtliche unterstützten Daten fehlschlagen zu lassen
- Web-Supplement-Fehler werden separat protokolliert und brechen den Modbus-Aktualisierungspfad nie ab. Eine falsche PIN wird direkt während der Einrichtung/Rekonfiguration gemeldet.

## Raumtemperatur-Weiterleitung

Die optionale Raumtemperatur-Weiterleitung schreibt Home-Assistant-Sensorwerte in die externen IDM-Raumtemperatur-Register je aktivem Heizkreis. Sie nutzt eine Standardtoleranz von 0,2 °C, um unnötige wiederholte Schreibvorgänge zu vermeiden, und überspringt ungültige, nicht verfügbare, nicht-numerische oder außerhalb des Bereichs liegende Werte.

Die Weiterleitung ist standardmäßig deaktiviert und startet erst, wenn mindestens ein Heizkreis in den Integrationsoptionen eine ausgewählte Home-Assistant-Temperatur-Entität hat.

## Fachmann-Code-Sensoren

Die optionalen Fachmann-Code-Sensoren aktualisieren sich **unabhängig** alle 60 Sekunden. Sie sind lokale Hilfssensoren und keine aus Modbus-Registern gelesenen Werte. Ihre Zustände sind als sensible Zugangsinformationen zu behandeln.
