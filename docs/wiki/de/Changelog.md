# Changelog

Die maßgebliche, vollständige Historie wird in
[`docs/CHANGELOG.md`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CHANGELOG.md)
und in den [GitHub-Releases](https://github.com/Xerolux/idm-heatpump-hass/releases) gepflegt.
Diese Seite fasst lediglich die aktuellen Meilensteine zusammen.

## v0.23.2-b2 — 2026-10-25

Erkennt Doppelkennungen für Navigator 10-Sensoren (`B33/B113` und `B34/B114`)
auf Anlagen mit Trennwärmetauscher / frostgeschütztem Außenkreis (#598) und
bereinigt Python 3.14 Event-Loop-Warnungen sowie Quality-Scale-Pins (#599).

## v0.23.2-b1 — 2026-10-24

Der Urlaubsmodus (Wert 3) bleibt mit dem getesteten API-Prerelease auch nach
validierten Modbus-Abfragen verfügbar. EEPROM-Schutz und die Betriebsarten des
Navigator 1.7 bleiben erhalten. Tests für Stoppen und Neustarten der
Weiterleitung sowie die englische/deutsche Anleitung unterscheiden erfolgreiche
Schreibzugriffe von der Regleranzeige. Der SoC-Rückfall #493 und die verbliebenen
Web-/Statusprobleme des Navigator 1.7 in #577 bleiben offen. Das Release enthält
auch das eigenständige rein lesende Capture-Tool und einen freiwilligen Aufruf
zu privaten Diagnoseaufnahmen. Eine Konfigurationsmigration ist nicht nötig.

## v0.23.1 — 2026-10-22

Ein Fix-Release nach zwei Feldmeldungen. Hybrid-Anlagen — Navigator 1.7
mit Web-Modul der 2.0-Generation — lösen im Automatikmodus wieder korrekt
als Navigator 1.7 auf; seit 0.22.0 hatte der verbundene Web-Client die
Registerkarte auf Navigator 2.0 gekippt und rund zwanzig Modbus-Entitäten
fallen gelassen (#577). Lebenslange Wärmemengen-Zähler treten nicht mehr
um einen Cent zurück: Die eigene kWh-Integration des Controllers schwankt
in der zweiten Nachkommastelle; die neue Sicherung hält innerhalb des
Rundungsrauschens den vorherigen Wert, echte Resets kommen durch (#578).

## v0.23.0 — 2026-10-21

Der stabile Schnitt der 0.23-Linie (vierzehn Betas, 17.–20.10.2026). Der
Predictive Advisor ist im Feld gereift: Sechs neue Sensoren verfolgen den
COP von reinem Heizen und reinem Warmwasser-Laden getrennt,
Warmwasser-Fenster erscheinen in deiner Home-Assistant-Zeitzone aus
korrekt gefalteten Viertelstunden-Preis- und PV-Daten
(Forecast.Solar-Sensoren funktionieren ohne Zusatzkonfiguration),
Empfehlungen bleiben ein stabiler Eintrag pro Thema, und das Gebäudemodell
lernt nur noch aus reinem Heizbetrieb (einmaliges Neulernen beim Update).
Der Wärmetauscher-Durchfluss wird endlich korrekt gelesen: Feldbelege
bewiesen, dass Register 1072 ein wortgetauschtes FLOAT32 ist, kein UCHAR —
die Geräte-Logik zieht auf `idm-heatpump-api[web]==2.14.4` um. Nicht
konfigurierte Anlagen-Features loggen keine Validierungswarnungen mehr,
und ein Web-Platzhalter `---` bringt den Sensor-Zustand nicht mehr zum
Absturz (#532). GLT-Weitergaben öffnen keine koordinator-weiten
Nicht-verfügbar-Fenster mehr (#537), und ein neuer Sensor für die
Vorlauf-Abweichung auf Wärmepumpen-Ebene rundet die Linie ab. Mit Home
Assistant 2026.11 installiert der eingebaute Marketplace (HACS-Nachfolger,
gleicher Katalog) die Integration direkt. Rollback auf 0.22.0 bleibt
möglich.

## v0.23.0-b14 — 2026-10-20

Neuer Sensor für die Vorlauf-Abweichung auf Wärmepumpen-Ebene: der
Vorlauf der Wärmepumpe im Vergleich zum höchsten Kreis-Sollwert, der
aktuell Vorlauf anfordert — gemeldet nur im reinen Heizbetrieb, denn
während einer Warmwasser-Ladung ist der Vorlauf Ladetemperatur und
keine Versorgung. Entwurf nach einer 24-stündigen rein lesenden Sonde
auf der Referenzanlage; die Abgrenzung ist im Open-Work-Audit
dokumentiert.

## v0.23.0-b13 — 2026-10-19

Hotfix aus der PV-Inbetriebnahme auf der Referenzanlage: Die
Forecast.Solar-Quelle aus b12 griff auf echten Installationen nie
(Verwechslung von Registry-Attributen); die PV-Prognose blieb leer. Nach
dem Fix live verifiziert: Der Advisor liest die Stundendaten und
empfiehlt ein Warmwasser-Fenster.

## v0.23.0-b12 — 2026-10-19

Der Advisor kann seine PV-Prognose jetzt aus der Core-Integration
Forecast.Solar lesen (kein Account, kein API-Key): Setze die Option
*PV-Prognose-Sensor für den Predictive Advisor* auf einen ihrer Sensoren.

## v0.23.0-b11 — 2026-10-19

Hotfix, live auf der Referenzanlage während der b10-Verifikation gefunden:
Der Advisor-Effizienzwert-Sensor hat seinen Wert nie veröffentlicht (die
Engine rundete auf einen Float, der Sensor akzeptiert nur Ganzzahlen).

## v0.23.0-b10 — 2026-10-19

Advisor-Härtungs-Durchlauf plus Modus-COP: Die Warmwasser-Fensterzeiten
erscheinen jetzt in deiner Home-Assistant-Zeitzone, Viertelstunden-Preis-
und PV-Daten werden korrekt gelesen, täglich neu ausgegebene
Empfehlungen laufen nicht mehr wöchentlich ab, die Gebäudemodelle
gewichten und vergessen ihre Samples (einmaliges Neulernen), und sechs
neue Sensoren verfolgen den COP von reinem Heizen und reinem
Warmwasser-Laden getrennt (`energy_cop_heating_*`, `energy_cop_dhw_*`).
Komplette Liste im [Changelog](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CHANGELOG.md).

## v0.23.0-b9 — 2026-10-18

Nachlese zu b8, inzwischen auf zwei Anlagen live bestätigt (Diskussion #516 —
der Melder dort hat auch aufgespürt, woher das UCHAR kam: Die offizielle Doku
hat es mit den Revisionen Navigator 2.0 rev 12 → 13 und Navigator 10 rev 0 → 1
auf FLOAT korrigiert). Die Energy-Manager-Optionsfelder fehlten in beiden
Übersetzungsdateien, sodass der schlichte Options-Schritt in Deutsch und
Englisch rohe Feldnamen zeigte — jetzt übersetzt mit der Terminologie der
geführten Seiten, plus Parity-Guards, die den Build fehlschlagen lassen, wenn
`strings.json`, `en.json` und `de.json` auseinanderdriften oder die deutsche
Register-Referenz eine englische Regenerierung verpasst. Die
Fehlerbehandlungsseiten dokumentieren außerdem, dass der Navigator nur einen
Modbus-Client gleichzeitig bedient: Eine zweite Verbindung liest `-1.0`-
Sentinels auf optionalen Blöcken, während der primäre Client Live-Daten
behält — Direkttests brauchen die gestoppte Integration (live auf der
Referenzanlage bestätigt, deren Durchfluss-Entität jetzt echte L/min liest).

## v0.23.0-b8 — 2026-10-18

Der Durchfluss der Wärmesenke wird jetzt mit dem Datentyp gelesen, den der
Regler tatsächlich spricht: Feldmessungen (Diskussion #516) haben bewiesen,
dass Register 1072 ein wortgetauschtes FLOAT32 ist — nicht UCHAR, wie die
offizielle IDM-Doku angibt. Ein direkter HA-Modbus-Sensor (float32 mit
Worttausch) lieferte plausible Werte, während die UCHAR-Dekodierung der
Integration wild springende Werte zeigte: Sie las nur ein Byte des
Float-Low-Words. Pinnt `idm-heatpump-api` 2.14.4: Echte Durchflusswerte
werden korrekt angezeigt, Anlagen ohne TWT bleiben nicht verfügbar, und der
Web-Durchfluss-Fallback füllt sie weiter auf.

## v0.23.0-b7 — 2026-10-18

Das Gebäudemodell lernt nur bei reinem Heizbetrieb und aktivem Heizkreis
(#546). Alte Wärmeverlust- und Vorlaufkurvendaten sowie die abgeleitete
Wärmekapazität werden einmal neu gelernt; COP und andere Statistiken bleiben
erhalten. Der vom Netzzähler abgeleitete Hausverbrauch pausiert bei ungültiger
zugeordneter Batterieleistung, statt eine unvollständige Bilanz zu verwenden
(#519). Die Datenschutztests nutzen einen festen Webstatus-Testzustand.
Reglerseitiges Zurücksetzen des Batterie-SOC (#493) bleibt eine offene
Firmwarebeobachtung; die zyklische GLT-Auffrischung bleibt erhalten.

## v0.23.0-b6 — 2026-10-18

Audit- und Laufzeit-Härtungs-Prerelease der 0.23-Linie: hebt die
Advisor-Plausibilitätsobergrenze für `heat_sink_flow_rate` auf `250,0 L/min` an,
damit reale Durchflusswerte (wie `33,9 L/min` aus dem #516-Web-Fallback) als
nutzbare Messwerte zählen, erhält `has_flow_sensor: true` auf Anlagen ohne
Trennwärmetauscher bei `0,0 L/min` im Leerlauf, sobald das Web-Supplement einen
Flowmeter liefert, und nimmt `heat_sink_flow_temp` sowie die vom Advisor
benötigten Heizkreis-Register fest in den entitätsbewussten Polling-Plan auf.
Tägliche Empfehlungs-Neuausgaben mit unverändertem Inhalt aktualisieren ihre
Datums-ID nun direkt ohne History-Duplikate, `retract()`/`mark()` gleichen
Themen tagesübergreifend ab, `advisor_operation_reason` priorisiert `Defrosting`
und `Cooling` vor der Warmwasser-Temperaturdifferenz und vermeidet negative
Sollwert-Abstände, `advisor_forecast_task` wird beim Entladen sauber beendet,
der Web-Fallback hebt ungenutzte Sentinels sofort beim Web-Refresh auf und
meldet `status: "web_fallback"` in der Diagnose, Schreib-Bestätigungen werden
pro Task verfolgt, die Raumtemperatur-/Feuchte-Weiterleitung dedupliziert
geteilte Sensoren und protokolliert Schreib-Cooldowns auf `DEBUG`, und KNX-
sowie Watchdog-Worker starten als Hintergrund-Tasks.

## v0.23.0-b4 — 2026-10-17

Zweite Runde aus der Advisor-Feld-Validierung: Das lautlose
Verfügbarkeits-Flattern nach jedem GLT-Weitergabe-Durchlauf ist behoben
(#537) — ein abgebrochener Bestätigungs-Refresh ließ Home Assistant ein
fehlgeschlagenes Update ohne jede Log-Zeile vermerken, sodass alle
Entitäten für ~12 s *nicht verfügbar* waren, in jedem
Weitergabe-Intervall; die Bestätigung wird jetzt nur abgebrochen, solange
sie noch wartet. Der Advisor-Anforderungsgrund mischt keine englischen
und deutschen Begriffe mehr für dieselbe Ursache (#538), und die
Fake-Durchfluss-0 ohne Trennwärmetauscher zählt nicht länger als nutzbare
Advisor-Daten (#539). Keine Konfigurationsänderung nötig.

## v0.23.0-b3 — 2026-10-17

Drittes Prerelease der 0.23-Linie auf Basis einer vollständigen
End-to-End-Simulation einer produktiven Navigator-10-Anlage (`AERO ALM 6-15`,
`T_NAV10_20.24-1580-g02a20b66f`) in einer echten Home-Assistant-Instanz.
Behebt in `advisor_operation_reason` (`compose_operation_reason`), dass
Leerlauf-Meldungen der Web-Oberfläche (`Keine Anforderung`, `Aus`, `System
aus`) während des aktiven Verdichterbetriebs (z. B. durch das schnellere
10-s-Modbus-Intervall gegenüber dem 60-s-Web-Intervall oder im Nachlauf bei
erreichter Vorlauf-Solltemperatur) nicht mehr den aktiven Betriebsmodus
(`Heating`, `Cooling`) überdecken, und prüft den Abtaubetrieb
(`hp_operating_mode == 8`) vor der Heizkreis-Vorlaufprüfung, sodass Abtauen
durch Kreislaufumkehr stets als `Defrosting` statt `Heating circuit A`
gemeldet wird.

## v0.23.0-b2 — 2026-10-17

Zweites Prerelease der 0.23-Linie auf Basis eines lesenden Live-Audits an
einer Navigator-10-Anlage (`T_NAV10_20.24-1580-g02a20b66f`). Anlagen, die
ihre thermische Leistung über `current_power` (Register 1790) melden,
während `thermal_power_flow_sensor` (Register 4126) dauerhaft `0,0 kW`
liefert, berechnen nun automatisch den `calculated_cop`, die thermischen
Energiemengen (`energy_thermal_*`, `energy_cop_*`) sowie die COP- und
Gebäudemodelle des Predictive Advisors. Zudem führt das reguläre
Modbus-Setup nun `cleanup_stale_model_entities` aus (entfernt verwaiste
Register-Entitäten wie nicht konfigurierte Kaskaden-Register vor dem
Aufräumen leerer Sub-Geräte), `cleanup_stale_web_sensor_entities` bereinigt
die abgelöste Entität `web_heatpump_model` sowie auf bestätigten
Navigator-10-Reglern die 12 reinen Navigator-2.0-Statistiksensoren (`Web
2.0`), und die Energiefluss-Sensoren (`web_energyflow_grid` /
`web_energyflow_pv`) melden *nicht verfügbar* statt *unbekannt*, wenn der
Regler `grid_power` bzw. `pv_power` weglässt. Außerdem wurde die
Dokumentation der externen Leistungs-Weiterleitung zu `Hausverbrauch` vs.
`Hausverbrauch (Vorgabe)` präzisiert (#519).

## v0.23.0-b1 — 2026-10-17

Erstes Prerelease der 0.23-Linie aus den Feld-Beweisen von Issue #532.
Nicht konfigurierte Anlagen-Features (ohne Bivalenz, Solar, Kühlen oder
externe Bedarfsquelle) warnen nicht mehr bei jedem Neustart als
„ungültiger Wert" — ihre „nicht vorhanden"-Füllwerte (255 bzw. 0) sind in
der Gerätebibliothek (`idm-heatpump-api` 2.14.3) als Register-Sentinels
deklariert, die betroffenen Entitäten zeigen schlicht *nicht verfügbar*,
genau wie die Speicher-Temperaturregister schon immer. Echte
Bereichsverletzungen einer lebenden Quelle (die per KNX gelieferten
100,96 % Luftfeuchte des Reporters) bleiben abgewiesen. Und der
`---`-Platzhalter der Navigator-Webseiten für „gerade kein Wert"
(z. B. die prognostizierte Warmwasser-Leistung ohne laufenden Bedarf)
führt jetzt ebenfalls zu *nicht verfügbar*, statt bei jedem Update die
Sensor-Zustandsmaschine von Home Assistant crashen zu lassen — im Log des
Reporters zählte das 273 Listener-Fehler. Keine Konfigurationsänderung
nötig.

## v0.23.0-b5 — 2026-10-17

Dritte Runde Feld-Feedback: Register, die „nicht vorhanden" melden, zeigen
jetzt den Live-Wert des Web-Supplements (Diskussion #516) — der
Wärmesenken-Durchfluss liest ohne Trennwärmetauscher die Fake-0 aus dem
Modbus-Muster, während der Flowmeter des Controllers den echten Wert
liefert; Nicht-vorhanden-Lesungen (dokumentierte Sentinels oder die
No-TWT-Signatur) werden aus dem Web gefüllt, echte Modbus-Werte gewinnen
immer. Und tägliche Advisor-Empfehlungen lösen ihren Themen-Vorgänger ab,
statt sich als parallele „neu"-Einträge zu stapeln (ein Thema, ein
aktiver Eintrag, Konfidenz und „angesehen"-Status werden vererbt). Keine
Konfigurationsänderung nötig.

## v0.22.0 — 2026-10-15

Der stabile Schnitt der 0.22-Linie (sieben Betas, 13.–15.10.2026,
inklusive der nie veröffentlichten 0.21.3-Linie). Zwei Feldthemen
dominieren: Manche Controller löschen GLT-RAM-Inputs wenige Sekunden nach
dem letzten Write (#493) — die Weiterleitungen refreshen sie jetzt in
firmware-sicherer 3-Sekunden-Kadenz und schreiben unveränderte Werte nach
einem Controller-Neustart neu — und unplausible Raumtemperaturen fließen
nicht mehr in den Predictive Advisor (#504), der zusätzlich jetzt
Home-Assistant-Temperatursensoren als Raumquellen nehmen kann. Dazu:
Kurze Modbus-Ausfälle bleiben fünf Minuten still, statt Fehler und
Repairs zu fluten, ein bidirektionaler Netzleistungszähler wird direkt
akzeptiert (#519), weitergeleitete Werte werden quantisiert auf die
Registerauflösung geschrieben, und die geführte Options-Tour erreicht die
Advisor-Raumquellen-Stufe wieder (#527). Ein Rollback auf 0.21.2 bleibt
möglich.

## v0.22.0-b7 — 2026-10-15

Die geführte Konfiguration zeigt die *Raumtemperaturquellen des Beraters*
wieder an (#527): Wer in der geführten Options-Tour den Predictive Advisor
auswählte, sprang bisher an diesem Schritt direkt zur Übersicht — die
Raumtemperatur-Quellen des Advisors ließen sich damit nicht über die UI
auswählen, nur der klassische Optionsfluss erreichte den Schritt. Er
erscheint jetzt direkt nach der Advisor-Detailstufe und kehrt danach wie
gewohnt zur Übersicht zurück. Die Konfigurationsseite dokumentiert zudem
die Einstiegspunkte ab Home Assistant 2026.8: Die Optionen liegen hinter
dem Zahnrad-Symbol in der Eintragszeile, „Neu konfigurieren“ startet nur
das Verbindungs-Setup (#526).

## v0.22.0-b6 — 2026-10-14

Die externe Leistungsweiterleitung schreibt quantisierte Werte (#519):
Abgeleitete Summen wie der Hausverbrauch trugen bisher
Gleitkomma-Artefakte (z. B. `0,3569999999999999` statt `0,357`) in den
Entity-State, den der nächste Poll durch das gerundete Register-Readback
ersetzte — die Entity wechselte sichtbar zwischen beiden Schreibweisen.
Writes werden jetzt vor dem Schreiben auf die Registerauflösung (10 W)
gerundet, damit der State stabil bleibt und immer dem entspricht, was die
Wärmepumpe tatsächlich gespeichert hat. Der zyklische 3-Sekunden-Refresh
bleibt: GLT-Inputs liegen im Controller-RAM (nicht im EEPROM — kein
Schreibzyklen-Verschleiß), und manche Firmwares löschen sie wenige
Sekunden nach dem letzten Write.

## v0.22.0-b5 — 2026-10-14

Die externe Leistungsweiterleitung nimmt einen bidirektionalen
Netzleistungszähler direkt an (#519): Das neue Feld *Bidirektionaler
Netzleistungssensor* nimmt einen einzelnen signierten Sensor am
Netzverknüpfungspunkt mit wählbarer Vorzeichenkonvention (positiv =
Netzbezug oder positiv = Einspeisung). Die Integration normalisiert das
Vorzeichen und leitet den signierten `pv_surplus` ab; zusammen mit dem
PV-Produktionssensor wird auch der Hausverbrauch abgeleitet, einschließlich
gemappter Batterieleistung. Explizit gewählte Überschuss- und
Verbrauchssensoren behalten Vorrang, und der Netzleistungszähler allein
wird nie als Hausverbrauch geschrieben. Template-Helfer sind auf Anlagen
mit bidirektionalem Zähler damit nicht mehr nötig.

## v0.22.0-b4 — 2026-10-14

Raumtemperatur-, Speichertemperatur- und Feuchtigkeits-Weiterleitung
übersteht einen Regler-Neustart: Jeder periodische Intervall-Durchlauf
schreibt die GLT-Register jetzt neu, auch wenn sich der Quellwert nicht
bewegt hat. Zuvor unterdrückte der Toleranz-Filter jedes erneute Schreiben
unveränderter Werte, sodass ein Neustart des Reglers oder des
Modbus-Dienstes — der die flüchtigen GLT-RAM-Eingänge löscht — den
externen Raumtemperatur-Einfluss still abschaltete, bis der Quellwert
driftete (live auf einem Navigator 10 während der #493-Untersuchung
beobachtet: das Register stand eine Viertelstunde auf dem -1-Sentinel).
Ereignisgesteuerte Schreibvorgänge behalten den Toleranz-Filter, sodass
flatternde Quellen weder Schreibvorgänge spammen noch den Write-Cooldown
auslösen.

## v0.22.0-b3 — 2026-10-13

GLT-RAM-Eingänge bleiben auf Navigator 10 stabil: Die periodische
Refresh-Kadenz sinkt auf 3,0 s ($T/2$ des ca. 5,0 s Regler-Watchdogs), der
Schreib-Cooldown ist für externe Leistungsregister auf 2,0 s gedeckelt
(verhindert Ausbremsen durch allgemeine Cooldown-Einstellungen),
Bestätigungs-Vollpolls nach dem Schreiben werden unterdrückt, Batterie-SoC
wird auf ganze Zahlen (`int`) gerundet, und ein Hinweis warnt, wenn
`battery_soc` ohne `battery_discharge` konfiguriert ist.

## v0.22.0-b2 — 2026-10-13

Kurze Modbus-Aussetzer bleiben still: Ein Verbindungsfehler, der sich
innerhalb von fünf Minuten erholt, erzeugt keine Reparatur-Meldung, keine
Fehlerzeile und keine unavailable Entities mehr — der Coordinator bedient
weiterhin den letzten Datenstand, anstehende Schreibzugriffe pausieren
still, und das Log erhält eine graue Info-Zeile beim Abbrechen und eine
beim Wiederkehren der Verbindung; ein zugestellter Schreibvorgang beendet
den Ausfall vorzeitig. Nur Ausfälle länger als fünf Minuten eskalieren zur
sichtbaren Reparatur, und vom Regler beantwortete Fehler (falsche Slave-ID,
Firmware) eskalieren weiterhin sofort.

## v0.22.0-b1 — 2026-10-13

Eröffnet die 0.22-Linie und nimmt die nie stabile 0.21.3-Beta-Linie auf
(alles seit 0.21.2). GLT-RAM-Werte werden alle 5 s erneuert, da manche
Controller sie ~10 s nach dem letzten Schreibvorgang löschen (#493); der
Advisor ignoriert unplausible Raumtemperaturen und erhält nur lesende
Home-Assistant-Raumtemperaturquellen für Heizkreise ohne Raumfühler
(#504); ein verbundener nav20-Webclient korrigiert Navigator-10-
Fehldetektionen; Sensor-Bursts brechen keine laufenden Schreibvorgänge
mehr ab; Verbindungsausfälle werden einmal statt pro Durchlauf gemeldet.
Enthält die SolarEdge-GLT-Anleitung und klarere Schreibfehler-Reparaturen.

## v0.21.2 — 2026-10-12

Externe Leistungssensoren lassen sich wieder abwählen (#489), einschließlich
der Batteriequelle und ihrer optionalen HA-Boost-Bedingung. SOC mit Nachkomma-
stellen wird für den GLT-Eingang gerundet statt abgelehnt. Leeren schreibt keinen
Ersatzwert. Alle Änderungen aus 0.21.1 bleiben enthalten.

## v0.21.1 — 2026-10-12

Wartungsrelease für automatische PV-Warmwasserladung (#487) und Fachmann-Codes
auf Navigator 1.7 (#486). Automatische Boosts erhalten die Heizungsbetriebsart,
benötigen 5 °C Abstand zum Ziel und behalten eine volle Sperrzeit ab Ladeende
über Reloads und Neustarts. Navigator 1.7 erhält seinen unterstützten
Level-1-Code; die alte Level-2-Entität wird entfernt. Die PV-Pufferregelung
des Navigators bleibt unabhängig. Differenzkreis-Parameterzuordnungen sind
weiterhin unbestätigt.

## v0.21.0-b4 — 2026-10-11
## v0.21.0 — 2026-10-12

Das **Predictive-Advisor**-Release: eine strikt schreibgeschützte Analyseebene,
die die Anlage beobachtet, eigene Basenlinien lernt und beantwortet, *warum die
Wärmepumpe gerade läuft* — Anomalieerkennung gegen 30-Tage-Basenlinien, Health-
und Effizienzwerte, ein gelerntes Gebäudemodell, Heizkurven-Empfehlungen in
vorsichtigen 0,02-Schritten, Warmwasserfenster aus PV-Prognose oder dynamischen
Preisen und ein 24-Stunden-Plan. Empfehlungen feuern Ereignisse mit vollständiger
Erklärung und abgesenktem, restart-sicherem Lebenszyklus. **Kein Schreibzugriff
auf die Wärmepumpe, keine KI, keine Cloud** — mit dem Smart-Profil standardmäßig
an, mit eigenem Schalter und einmaligem Was-ist-neu-Hinweis. Das Release bringt
zusätzlich die Feldhärtung der letzten Tage: die Bereichskorrektur für
`dhw_charge_off_temp` (46–67 °C, aus den Belegen in #460), den Log-Flut-Fix für
dauerhaft ungültige Register, funktionierende geführte Konfiguration der externen
Leistung auf jedem Level (#471), Labels für alle KI-Optionsfelder und den
Transport-Floor auf dem Stand von Home Assistant 2026.10.1.

## v0.20.4 — 2026-10-11

Drittes stabiles Wartungs-Release auf der 0.20.x-Linie: **Die geführte
Konfiguration der externen Leistungsweiterleitung crasht nicht mehr auf dem
erweiterten Level** (#471) — der Assistent bot ein Weiterleitungsintervall an,
das die Optionsseite nie hatte, sodass die erweiterte Seite des Features mit
einem *Unbekannten Fehler* starb, während das Standard-Level funktionierte. Das
**Weiterleitungsintervall für externe Leistungswerte** ist jetzt eine echte
Option (30–3600 s, Standard 60 s), ein Regressionstest durchläuft jedes
geführte Feature auf jedem Level, und sensorgetriebene Weiterleitungen, die
schneller kommen als der Schreib-Cooldown, werden still übersprungen, statt in
jedem Zyklus `rejected the value` zu loggen. Der `modbus-connection`-Floor
folgt Home Assistant 2026.10.1 auf 4.12.4. Derselbe Guided-Fix liegt ab
0.21.0-b4 auch in der Beta-Linie.


Vierte Beta der `0.21.0`-Linie. **Die geführte Konfiguration der externen
Leistungsweiterleitung crasht nicht mehr auf dem erweiterten Level** (#471):
Der Assistent bot ein Weiterleitungsintervall an, das die Optionsseite nie
hatte — die erweiterte Seite des Features starb daher mit einem *Unbekannten
Fehler*, während das Standard-Level funktionierte. Das **Weiterleitungsintervall
für externe Leistungswerte** ist jetzt eine echte Option (30–3600 s, Standard
60 s), und ein Regressionstest durchläuft jedes geführte Feature auf jedem
Level, damit eine fehlende Option nie wieder ausgeliefert werden kann.
Sensorgetriebene Weiterleitungen, die schneller kommen als der
Schreib-Cooldown der Integration pro Register, werden jetzt still auf
Debug-Ebene übersprungen, statt in jedem Zyklus `rejected the value` zu
loggen — erwartete Selbstregelung, kein Reglerfehler. Ebenfalls in diesem
Schnitt: Pages-Builds gegen unsichere Ausgabeverzeichnisse gehärtet, UTF-8
im Windows-KNX-Vergleich erhalten, Web-only-Steuerungen richtig
dokumentiert, stabiles Home Assistant 2026.10.0 zusätzlich zur Mindestversion
in der CI validiert und echte HA-Lifecycle-Tests vor automatischen
Dependency-Merges verpflichtend.

## v0.21.0-b3 — 2026-10-09

Dritte Beta der `0.21.0`-Linie, eine Datenkorrektur nach den Belegen des
Reporters in #460: Der Regler speichert **63 °C** in `dhw_charge_off_temp`,
und seine eigene Weboberfläche bietet dort **50–67 °C** an — der
dokumentierte Bereich von 46–53 °C war also zu eng. Der
Validierungsbereich wächst auf **46–67 °C** (`idm-heatpump-api 2.14.2`):
Das Entity *WW Ausschalttemperatur* zeigt jetzt einen Wert, statt
unverfügbar zu bleiben, und Schreiben kann das volle Fenster nutzen, das
der Regler selbst anbietet. Die Register-Referenz ist regeneriert;
derselbe Fix liegt ab 0.20.3 auch auf der stabilen Linie.

## v0.21.0-b2 — 2026-10-09

Zweite Beta der `0.21.0`-Linie, ein Wartungsschnitt: Ein Register, das mit
einem **dauerhaft ungültigen Wert** antwortet, flutet das Home-Assistant-
Protokoll nicht mehr mit einer Warnung pro Abfrage (#460 — alle 12 s, über
6600 Einträge pro Tag bei einer AEOR ALM 4-12, deren `dhw_charge_off_temp`
außerhalb des dokumentierten Bereichs von 46–53 °C liegt). Die Warnung
feuert jetzt einmal pro Register, Wiederholungen gehen ins Debug-Protokoll,
und die Meldung nennt Wert, Ablehnungsgrund und dokumentierten Bereich.
Die Geräte-Logik zieht auf `idm-heatpump-api[web]==2.14.1`.

## v0.21.0-b1 — 2026-10-07

Erste Beta der `0.21.0`-Linie und das größte Analyse-Feature bislang: der
**Predictive Advisor** — eine strikt schreibgeschützte Empfehlungsebene, die
die Anlage beobachtet, die Datenqualität je Register verfolgt und
dokumentierte Beobachtungsstufen durchläuft (Sammeln → erste Hinweise →
Empfehlungen → etabliert). Er beantwortet, *warum die Wärmepumpe gerade
läuft*, erkennt Anomalien gegen die eigenen 30-Tage-Basenlinien, berechnet
Gesundheits- und Effizienzwerte, lernt ein Gebäudemodell (Wärmeverlust,
thermische Trägheit, optimale Vorlauftemperatur), empfiehlt Heizkurven-
Korrekturen in vorsichtigen 0,02-Schritten, findet Warmwasserfenster aus
PV-Prognose oder dynamischem Strompreis und bündelt alles in einem
24-Stunden-Plan. Empfehlungen feuern `idm_advisor_recommendation`-Ereignisse
mit vollständiger Erklärung. Vollständig lokal und deterministisch — keine
KI, keine Cloud, kein LLM — und **ohne jeden Schreibzugriff auf die
Wärmepumpe**. Mit dem Smart-Profil standardmäßig aktiv, mit eigenem
Schalter; ein einmaliger Was-ist-neu-Hinweis unter Einstellungen → Repairs
fasst die Änderungen zusammen.

## v0.20.3 — 2026-10-09

Zweites stabiles Wartungs-Release auf der 0.20.x-Linie, angestoßen durch die
Belege des Reporters in #460: Der Regler speichert **63 °C** in
`dhw_charge_off_temp`, und seine eigene Weboberfläche bietet dort **50–67
°C** an — der dokumentierte Bereich von 46–53 °C war also zu eng. Der
Validierungsbereich wächst auf **46–67 °C** (`idm-heatpump-api 2.14.2`): Das
Entity *WW Ausschalttemperatur* zeigt jetzt einen Wert, statt unverfügbar zu
bleiben, und Schreiben kann das volle Fenster nutzen. Reiner Pin- und
Dokumentations-Schnitt auf 0.20.2 (plus die cherry-gemappten
Wartungsfixes für ruff 0.17 und die Home-Assistant-Pin-Deckelung, ohne die
gegen heutige Tooling-Stände kein Release möglich wäre); derselbe
Range-Fix liegt ab 0.21.0-b3 auch in der Beta-Linie.

## v0.20.2 — 2026-10-09

Stabiles Wartungs-Release auf der 0.20.x-Linie: Ein Register, das mit einem
**dauerhaft ungültigen Wert** antwortet, flutet das Home-Assistant-Protokoll
nicht mehr mit einer Warnung pro Abfrage (#460 — alle 12 s, über 6600
Einträge pro Tag bei einer AEOR ALM 4-12, deren `dhw_charge_off_temp`
außerhalb des dokumentierten Bereichs von 46–53 °C liegt). Die Warnung
feuert jetzt einmal pro Register, Wiederholungen gehen ins Debug-Protokoll,
und die Meldung nennt Wert, Ablehnungsgrund und dokumentierten Bereich.
Reiner Pin- und Dokumentations-Schnitt auf 0.20.1 — die Geräte-Logik zieht
auf `idm-heatpump-api[web]==2.14.1`; derselbe Fix ist ab 0.21.0-b2 auch in
der 0.21.0-Beta-Linie enthalten.

## v0.20.1 — 2026-10-06

Dieses Release macht **Modbus-Unterbrechungen selbstheilend** und
vervollständigt die **Differenztemperaturkreise** aus der Beta-Linie
(#429): Liefert das lokale Webinterface weiter Daten, löst eine gescheiterte
Modbus-Abfrage keinen Dauerfehler mehr aus — ein ruhiger Repairs-Hinweis
meldet, dass die Daten weiterfließen, und ein Hintergrund-Watchdog holt
Einträge aus dem Setup-Wiederholungs-Backoff zurück, sobald der Endpunkt
wieder antwortet. Differenztemperaturkreise (zum Beispiel ein Kachelofen an
HK D) werden über das lokale Webinterface automatisch erkannt, und ihre
Geräte kehren über eine einmalige Migration zu kurzen Entitäts-IDs zurück.
Die Integration ist gegen **Home Assistant 2026.10** validiert (Minimum
bleibt 2026.8.1); die Transport-Pakete wurden Home-Assistant-eigene
Mindestversionen, die Gerätelogik zieht auf `idm-heatpump-api[web]==2.14.0`.

## v0.20.0 — 2026-09-30

Das lokale **Navigator-Webinterface wird ein vollwertiger Datenpfad**:
`web_only` wächst vom notfallmäßigen Lesezugriff zum echten Betriebsmodus —
der Navigator-10-WebSocket liefert Statistiken, Frischwasserstatus, die
Regler-Uhrzeit, Leistung, Wetter und iON-Daten und trägt capture-bestätigte
Schreibzugriffe für Betriebsart, Fehlerquittierung, Warmwasser-Sollwert und
Heizkreis-Sollwerte und -Betriebsarten, inklusive Klima- und
Warmwasser-Karten. Eine explizite Verbindungsmodus-Option, zwei
Verbindungsstatus-Entitäten und ein Reload-Button machen die Datenpfade
transparent. Die **Navigator-1.0/1.7-Integration ist komplett** (Issue
#319): der offizielle FC01/FC05-Coil-Block c3000–c3003 bringt den
Quittieren-Button und einen eigenen *Vorrangladung*-Button. Fehlercodes des
Reglers erscheinen als lesbarer deutscher Text über die mitgelieferte
Hersteller-Datenbank, und ein Sensitivdaten-Wächter ergänzt die CI.

## v0.19.0 — 2026-09-26

Der **Navigator 1.0/1.7 wird zum vollwertigen Familienmitglied**, und die
**Photovoltaik bekommt ein Gesicht** — dazu ein ehrlicher KI-Berater und
eine vollständig zweisprachige Dokumentationsseite. Die 1.x-Familie erhält
die vollständige offizielle schreibbare Haltetabelle, einen
firmware-ehrten Bereichsschutz, der Diagnosebericht je Register, einen
funktionierenden Frischwasser-Sollwert (ein capture-verifiziertes
Float-Paar, das die offizielle Tabelle falsch typisiert) und eine eigene
Warmwasser-Karte. Die PV-Sichtbarkeit (Issue #353) kommt als abgeleitete
Überschuss-Diagnose, als eigener Anforderungsgrund des Navigator 10 aus
seinem Webinterface und als eigene Gerätegruppe *Photovoltaik*. Alles
bleibt 100 % lokal; keine Entitäts-ID ändert sich. Laufzeit:
`idm-heatpump-api[web]==2.4.3`.

## v0.18.0 — 2026-09-20

Zwei Leitfeatures auf Basis von 0.17.1: das optionale Paket **Smart Energy &
Comfort** und der experimentelle **KI-Anlagenberater** — dazu eine geführte
Einrichtung, die das lange Optionsformular ersetzt. Smart Energy & Comfort
bringt persistente Energie-/COP-/CO₂-Statistiken, einen schreibgeschützten
Health Monitor, Heizkurven- und Wetter-Komfortberatung, Komfort-Zeitpläne
und einen fail-closed PV-Überschuss-Warmwasser-Boost (beide Schreib-Features
erfordern eine explizite Bestätigung des exklusiven Reglers). Der
KI-Anlagenberater ist schreibgeschützt und standardmäßig aus:
deterministische Berichte aus Messwerten, optional freie Erklärungen über
lokales Ollama, eine Home-Assistant-AI-Task-Entität oder ausdrücklich
genehmigte Cloud-Anfragen — die einzige autorisierte Cloud-Ausnahme.
Alles bleibt standardmäßig 100 % lokal. Laufzeit:
`idm-heatpump-api[web]==2.2.0`.

## v0.17.1 — 2026-09-14

Abhängigkeits- und Härtungs-Patch auf 0.17.0: Die getestete Laufzeit zieht
auf `idm-heatpump-api[web]==2.1.2`, `modbus-connection==4.12.1` und
`tmodbus[async-serial]==0.6.2`; die Release-Validierung lehnt jetzt immer
veraltete Runtime-Pins ab (der Bypass-Eingang ist entfernt), und der
Navigator-Varianten-Fallback stoppt nach erfolgreicher Navigator-10-
WebSocket-Anmeldung, statt die Protokollfamilie falsch zu melden.

## v0.17.0 — 2026-09-13

Der stabile Schnitt der 0.17.0-Linie, der ihren gesamten Beta-Zyklus zusammenfasst. Die
Schlagzeile: **Navigator-1.0/1.7-Wärmepumpen werden unterstützt** — automatisch
erkannt, mit einer eigenen, aus der offiziellen 1.x-Tabelle stammenden Registermap
bedient, samt schreibbarer PV-Supplement-Register bei aktualisierter Firmware. Der
Rest ist das September-Code-Audit: acht behobene Fehler (eine Abfrage, die ihren
Konfigurationseintrag überlebte, ein fehlgeschlagener Setup, der aktive Entitäten
zurückließ, Fahrenheit-Raumsensoren, die als Celsius geschrieben wurden,
Sentinel-Werte auf Thermostat-Karten und mehr), Härtung des Web-Supplements und des
Warmwasser-Boosts sowie die Automation, die die Abhängigkeits-Pins von selbst aktuell
hält. Laufzeit: `idm-heatpump-api` 2.1.1,
`modbus-connection` 4.11.1. Das vollständige, maßgebliche Changelog steht in
[`docs/CHANGELOG.md`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CHANGELOG.md);
ab diesem Release wird es Version zu Version geführt (Beta-Abschnitte werden beim
Schnitt in den Stable-Abschnitt eingefaltet).

## v0.17.0-beta.1 — 2026-09-09

Erster Kandidat der `0.17.0`-Linie, mit dem Ergebnis des Code-Audits aus
`docs/dev/code-audit-2026-09.md`. Acht Fehler sind behoben — darunter eine Abfrage,
die ihren Konfigurationseintrag überlebte, ein fehlgeschlagener Setup, der aktive
Entitäten zurückließ, eine zweite Wärmepumpe hinter einem Modbus-Gateway, die nicht
mehr hinzugefügt werden konnte, weitergeleitete Raumtemperaturen, die nicht nach
Grad Celsius umgerechnet wurden, und Sentinel-Werte, die einen Temperaturzustand
erreichten — zusammen mit sechs Robustheits- und drei Performance-Punkten. Beide
Laufzeit-Pins ziehen nach vorn (`modbus-connection` `4.11.1`, `idm-heatpump-api`
`2.0.1`). Keine Registermap und kein Entitäts-Bezeichner hat sich geändert.

Es ist eine **Beta**: Das Audit hat Modellerkennung, Setup und Abbau, schreibfähige
Entitäten und Aktionen berührt, und eine Änderung der Laufzeitabhängigkeit startet
die Soak-Uhr neu. Der Verifizierungsfortschritt wird in
`docs/release-evidence/0.17.0-beta.1.md` verfolgt.

## v0.16.1 — 2026-08-28

Patch auf `0.16.0`, anhand eines echten Home-Assistant-Logs. Zeigte das optionale
Web-Supplement auf eine **IP-Adresse**, schloss die Integration eine
Home-Assistant-aiohttp-Session, statt sie zu detachen — Home Assistant überschreibt
`close()` auf jeder Session, die seine Hilfsfunktionen herausgeben, weil der
darunterliegende Connector mit jeder anderen Integration geteilt wird. Die Session
wird jetzt per `detach()` freigegeben und mit `auto_cleanup=False` erzeugt, sodass
ein Web-Client, der nach einer fehlgeschlagenen Abfrage neu aufgebaut wird, die
vorherige Session nicht bis zum Home-Assistant-Stopp gepinnt lässt.

Ein Hostname war nie betroffen; er leiht sich die geteilte Session, die die
Integration nie freigab. Abfrage, Entitätszustand, Schreibvorgänge, die KNX-Bridge
und der Modbus-Pfad sind unverändert, ebenso die Laufzeit-Pins.

## v0.16.0 — 2026-08-28

Erste stabile Version der `0.16.0`-Linie. Sie schließt `0.16.0-beta.1` bis
`0.16.0-rc.6` ab, ohne Codeänderung seit RC6.

**Die Schlagzeile ist die experimentelle KNX-Bridge.** Die Integration bedient die
654 IDM-KNX-Kommunikationsobjekte selbst — mit denselben Objektnummern,
Datenpunkttypen und Lese-/Schreibrichtungen wie IDMs ETS-Beispielprojekt —, sodass
das Weinzierl-Gateway-Modul `KNX IP BAOS 774` nicht mehr benötigt wird. Sie ist
Opt-in, standardmäßig aus, und treibt die Home-Assistant-`knx`-Integration, bei der
Tunneling, Routing und KNX Secure bleiben. Eine Basis-Gruppenadresse konfiguriert
alle Objekte; `idm_heatpump.export_knx_group_addresses` und
`scripts/generate_knx_group_addresses.py` erzeugen den ETS-Import. Die
Interoperabilität mit dem physischen Bus ist noch nicht verifiziert, deshalb ist
die Funktion als experimentell markiert.

**Breaking:** pymodbus ist weg. Die Integration benötigt
`idm-heatpump-api[web]==2.0.0` und spricht Modbus TCP ausschließlich über
`modbus-connection==4.10.0` / `tmodbus[async-serial]==0.6.1`. `0.15.1` ist die
letzte Linie mit pymodbus. Auf der Leitung ändert sich nichts — Registeradressen,
Entitäts-IDs, Unique-IDs und der Schreibpfad sind identisch, sodass Entitäten,
Historie, Automationen und Dashboards das Update überstehen.

**Ebenfalls in der Linie:** jeder Entitätsname wird über einen
Home-Assistant-Übersetzungsschlüssel aufgelöst, sodass eine englische Installation
endlich englische Namen zeigt; Heizkreise, optionale Module und Räume wurden auf
Home Assistant `2026.9` zu Child-Geräten, ohne eine Geräte-ID zu verlieren; strict
mypy läuft ohne jede Deaktivierung; und die Test-Suite ist auf 95 % Abdeckung
gegated, `config_flow.py` auf 100 %.

Siehe [KNX-Bridge](KNX-Bridge).

## v0.16.0-rc.6 — 2026-08-27

Die KNX-Bridge erholt sich jetzt, wenn IDM startet, bevor Home Assistants
KNX-Runtime vollständig geladen ist. Die Registrierung der
Gruppenadressen-Ereignisse wird alle fünf Sekunden erneut versucht, und ein
Teilerfolg bleibt erhalten, sodass nur fehlende DPT-Batches erneut probiert werden.
Ein manuelles Neuladen der IDM-Integration ist nicht erforderlich.

RC5s Latest-Value-Befehlswarteschlange und alle Schreibschutze sind unverändert.
Die EEPROM-sensible Klassifizierung und der konfigurierbare 60-Sekunden-Standard
bleiben wie zuvor; die Wiederherstellung der Registrierung sendet kein Bus-Telegramm
und schreibt selbst kein Regler-Register.

## v0.16.0-rc.5 — 2026-08-27

Eingehende Befehle für die experimentelle KNX-Bridge nutzen jetzt eine
Latest-Value-Wins-Warteschlange. Schnelle Zwischen-Sollwerte werden über eine
Sekunde zusammengefasst, und ein gültiger Befehl, der auf den allgemeinen Cooldown
oder den EEPROM-Schutz trifft, bleibt so lange in der Warteschlange, bis die
Sperre abläuft, statt verloren zu gehen. Die EEPROM-sensible Registerklassifizierung
und der konfigurierbare 60-Sekunden-Standard sind unverändert.

Der Optionstext unterscheidet die Live-Evidenz jetzt präzise: Setup und Neuladen
wurden mit einer aktiven Home-Assistant-KNX-Schnittstelle im sicheren
Nur-Empfangs-Modus verifiziert, während die physische
Gruppenadressen-Telegramm-Interoperabilität und die Buslast offen bleiben, weil
keine IDM-Gruppenadressen in ETS importiert wurden.

Siehe [KNX-Bridge](KNX-Bridge).

## v0.16.0-rc.4 — 2026-08-27

**Entitätsnamen sind übersetzt.** Bislang hatten nur eine Handvoll
Steuer-Entitäten Übersetzungen; jede andere Entität — die Modbus-Register, die
berechneten Sensoren und Betriebsanalyse-Sensoren, die Fachmann-Codes und die Werte
des lokalen Web-Supplements — trug in jeder Sprache einen fest eincodierten
deutschen Namen. Alle werden jetzt über einen Home-Assistant-Übersetzungsschlüssel
aufgelöst, sodass eine englische Installation englische Namen zeigt und eine
deutsche die Namen, die sie immer hatte. Entitäts-IDs und Unique-IDs sind
unverändert.

Der Rest des Kandidaten ist Quality-Scale-Arbeit ohne sichtbare Wirkung für die
Nutzer: Der Config Flow erreichte 100 % Testabdeckung und die Suite 95 %, beides
wird in CI erzwungen; die optionalen Web-Clients nutzen Home Assistants eigene
aiohttp-Session; und das strenge Typsystem verlor seine sieben deaktivierten
Fehlercodes.

Siehe [Entitäten](Entities#entitatsnamen-und-sprachen).

## v0.16.0-rc.3 — 2026-08-27

Optionale, **experimentelle** **KNX-Bridge**: Die Integration kann die
IDM-KNX-Kommunikationsobjekte — mit denselben Objektnummern, Datenpunkttypen und
Lese-/Schreibrichtungen wie IDMs ETS-Beispielprojekt — über die
Home-Assistant-`knx`-Integration bedienen, sodass das Weinzierl-Gateway-Modul
`KNX IP BAOS 774` nicht mehr benötigt wird. KNX Secure, Tunneling und Routing
kommen aus der `knx`-Integration. Eine Basis-Gruppenadresse konfiguriert alle 654
Objekte, und `idm_heatpump.export_knx_group_addresses` liefert die Tabelle für ETS.

Experimentell: durch Unit-Tests abgedeckt, aber noch nie gegen einen realen
KNX-Bus erprobt.

Siehe [KNX-Bridge](KNX-Bridge).

## v0.15.0 — 2026-08-22

Stabiles Release, das den `0.15.0-beta.1`..`beta.3`-Zyklus abschließt. Keine
Breaking Changes: Unique-IDs, Entitäts-IDs, Registeradressen und Schreibpfade sind
unverändert, und ein bestehender Konfigurationseintrag fragt exakt wie zuvor ab.

### Geändert

- **Transport vom Alpha-Pin weg**: `modbus-connection==4.8.1` und
  `tmodbus[async-serial]==0.5.1` (zuvor `4.0.0a3` / `0.5.0`), mit einer typisierten
  Fehlerhierarchie und `ModbusDesyncError` für Gateways, die mehrere Clients
  bedienen.

### Hinzugefügt

- **Web-Raumtemperatursensoren für alle Heizkreise A–G**: `B61`–`B67`
  (`room_temperature_HK_A`..`G`), live verifiziert auf Navigator 10 ALM 6-15.
- **Verbindungs-Pacing-Optionen** unter „Erweiterte Modbus-Einstellungen“: Pause
  zwischen Anfragen (0–0,5 s) und Pause nach dem Verbinden (0–5 s), beide
  standardmäßig `0`.
- **Automatisierte Frischeprüfung der Abhängigkeits-Pins** und ein englischer
  Dokumentations-Vertrag, beides in CI erzwungen.

### Behoben

- **Invertierte NC-Digitaleingänge im Web-Supplement**:
  `ew_evu_lock_contact`, `dewpoint_humidity_alarm` und `failure_eheating` melden
  jetzt im Normalbetrieb `off` und bei Alarm, Sperrung oder Störung `on`.
- **Verwaiste veraltete Sensor-Entitäten**: übrig gebliebene `sensor.*_web`-Einträge
  aus der `binary_sensor`-Migration werden beim Start aus der Entitäts-Registry
  entfernt.

> **Hinweis zum Release-Gate**: Dieser stabile Tag wurde ohne den siebentägigen
> Soak und ohne einen signierten Stable-Kandidaten-Smoke-Test geschnitten — eine
> bewusste Maintainer-Entscheidung, festgehalten in
> `docs/release-evidence/0.15.0.md` und auf
> [Stabilität und Release-Bereitschaft](Stability-and-Release-Readiness).

## v0.15.0-beta.3 — 2026-08-22

Beta-Kandidat 3: fügt Raumtemperatursensoren für alle Heizkreise (A–G) im optionalen
Navigator-Web-Supplement hinzu und hebt `idm-heatpump-api` auf 1.0.2.

### Hinzugefügt

- **Web-Raumtemperatursensoren für alle Heizkreise A–G**: Unterstützung für
  `B61`–`B67` (`room_temperature_HK_A`..`G`), live verifiziert auf Navigator 10
  ALM 6-15 (`B64 = 21.8 °C`).
- **`idm-heatpump-api[web]`**: auf `1.0.2` angehoben.

## v0.15.0-beta.2 — 2026-08-22

Beta-Kandidat 2: behebt invertierte Zustände an normally-closed-(NC-)Digitaleingängen
im Navigator-Web-Supplement, räumt verwaiste Legacy-Sensor-Entitäten in Home
Assistants Entitäts-Registry automatisch auf und fügt eine automatisierte
Frischeprüfung der Abhängigkeits-Pins hinzu.

### Behoben

- **Invertierte NC-Digitaleingänge im Web-Supplement**: `ew_evu_lock_contact`,
  `dewpoint_humidity_alarm` und `failure_eheating` sind Normally-Closed-Kontakte und
  melden jetzt korrekt `off` im Normalbetrieb und `on` bei Alarm/Sperrung.
- **Aufräumen verwaister veralteter Sensor-Entitäten**: Alte `sensor.*_web`-Entitäten,
  die zu `binary_sensor` migriert wurden, werden beim Start automatisch aus Home
  Assistants Entitäts-Registry entfernt.
- **Plattformunterstützung des Abhängigkeits-Pin-Updaters**: Pfade zum POSIX-Format
  normalisiert.

### Hinzugefügt

- **Englischer Dokumentations-Vertrag**: durch Tests erzwungen.
- **Automatisierte Abhängigkeits-Frischeprüfung**: tägliche Pin-Verifizierung gegen
  PyPI.

## v0.15.0-beta.1 — 2026-08-19

Beta-Kandidat: Der Transport-Pin wandert vom `modbus-connection==4.0.0a3`-Alpha auf
`4.8.1`, dazu zwei neue Pacing-Optionen, die standardmäßig aus sind. Weil dies die
Laufzeitabhängigkeit des direkten Modbus-Sockets ändert, geht es über den
Pre-Release-Kanal heraus — die Soak-Uhr für einen stabilen Tag startet mit diesem
Kandidaten neu. Keine Breaking Changes; Unique-IDs, Entitäts-IDs, Registeradressen
und Schreibpfade sind unverändert, und ein bestehender Konfigurationseintrag fragt
ohne jedes Zutun exakt wie zuvor ab.

### Geändert

- **Transport gepinnt auf `modbus-connection==4.8.1` und
  `tmodbus[async-serial]==0.5.1`** (zuvor `4.0.0a3` / `0.5.0`). Die neuere
  Bibliothek ergänzt eine typisierte Fehlerhierarchie, verbindungsweites Pacing
  und — seit 4.8.0 — `ModbusDesyncError`: Antwortet ein Partner auf eine andere
  Anfrage als die gesendete (typisch für ein Gateway, das mehrere Modbus-Clients
  gleichzeitig bedient), baut das Backend die Verbindung ab, statt die fremde
  Antwort zu dekodieren. Das `async-serial`-Extra ist nicht optional, obwohl diese
  Integration nur TCP spricht: seit `modbus-connection` 4.7.0 importiert das
  Backend-Modul `serialx` auf Modulebene.
- **Die Transportfehler-Übersetzung nutzt jetzt die typisierten Exceptions**,
  statt `exception_code`-Nummern zu vergleichen. Der Vertrag ist unverändert:
  Code 2 bleibt `IllegalAddressError` (Bisektionslogik des Koordinators), die Codes
  5/6/10/11 bleiben auf dem Retry-in-Place-Pfad, und der Marker
  `exception_code=<N>`, auf den der Koordinator matcht, wird weiterhin als Zahl
  dargestellt.

### Hinzugefügt

- **Zwei Optionen unter „Erweiterte Modbus-Einstellungen“**, beide standardmäßig
  `0`: **Pause zwischen Anfragen** (0–0,5 s, minimaler Abstand vom Ende einer
  Anfrage bis zum Beginn der nächsten) und **Pause nach dem Verbinden** (0–5 s,
  einmal je Verbindung und Wiederverbindung). Erhöhe sie für Regler oder Gateways,
  die „device busy“ antworten, Anfragen verwerfen oder unter einem dichten
  Anfragestrom in Timeout laufen. Die geführten Setup-Profile setzen die
  Anfragepause gleich mit: „unzuverlässiges Netzwerk“ 0,05 s, „mehrere Clients“
  0,1 s.

## v0.14.1 — 2026-08-18

Patch-Release: drei Fehler rund um den Lebenszyklus optionaler Heizkreise. Keine
Breaking Changes; Unique-IDs, Registeradressen und Schreibpfade sind unverändert.

### Behoben

- **Sensoren eines später aktivierten Kreises erschienen nie.** Entitäten werden nur
  gebaut, während der Konfigurationseintrag lädt. Meldete der Regler in genau
  dieser einen Abfrage noch den `-1.0`-Sentinel, warf der Filter „ungenutzte
  Sensoren verbergen“ die Nur-Lese-Register des Kreises hinaus — der Kreis bekam
  also seine Steuerungen, aber weder Vorlauf-, Raum- noch Solltemperatur, bis ein
  späteres Neuladen zufällig bessere Werte erwischte. Ein konfigurierter Kreis ist
  jetzt von diesem Filter ausgenommen, genauso wie schreibbare Steuerungen bereits
  waren. Die Verfügbarkeit folgt weiterhin dem Live-Wert.
- **Die Vorlaufabweichung zeigte im Leerlauf die Vorlauftemperatur.** Ein Kreis, der
  nichts anfordert, meldet den Sollwert `0.0`. Das ist ein normaler Betriebszustand,
  kein deklarierter Sentinel, weshalb der Sensor `Vorlauf - 0` berechnete und die
  gemessene Vorlauftemperatur als 26-K-Abweichung veröffentlichte. Er ist jetzt
  unterdrückt (Zustand `unknown`), solange der Kreis nichts anfordert — wie der
  COP-Sensor im Stillstand.
- **„Unbenanntes Gerät“ in der Geräteliste.** Sub-Geräte werden vor den Plattformen
  erzeugt, damit sich `via_device`-Verweise unabhängig von der Plattformreihenfolge
  auflösen; ihr Name kommt erst mit der ersten Entität. Ein Sub-Gerät, das nie einen
  bekam, blieb als namenloser, leerer Eintrag in der Liste. Solche werden jetzt beim
  Laden des Konfigurationseintrags abgehängt. Ein Sub-Gerät, dessen Entitäten der
  Nutzer lediglich deaktiviert hat, bleibt erhalten.
- **Verwaiste Entitäten abgewählter Kreise.** Das Abwählen eines Kreises ließ seine
  Entitäten dauerhaft unverfügbar in der Registry zurück. Sie werden jetzt beim
  Laden des Konfigurationseintrags entfernt — eng begrenzt auf registergestützte
  Entitäten dieses Eintrags, deren Register auf einen unkonfigurierten Kreis zeigt.
  Erneutes Aktivieren des Kreises erstellt sie unter unveränderten Unique-IDs neu.

## v0.14.0 — 2026-08-18

Minor-Release: ein Bedienbarkeits-Fix an der Heizkurve, die Auslegungsparameter der
Kreise werden zu Experten-Entitäten, dazu ein Dashboard-Beispiel pro Kreis und ein
Vertragstest, der die Ursache des 0.13.0-Fehlers in CI erwischt.
Konfigurationseinträge, Entitäts-IDs, Unique-IDs, Registeradressen und Schreibpfade
sind unverändert, und das getestete Abhängigkeits-Paar ist identisch mit 0.13.0.

### Behoben

- **Schrittweite der Heizkurve.** `hc_{a..g}_heating_curve` ist ein FLOAT-Register
  und erbte daher die Standard-Schrittweite von 0,5, obwohl sein Wertebereich
  0,1–3,5 ist. Häufige Einstellungen wie 0,3 oder 0,4 fielen zwischen zwei Schritte
  und ließen sich nicht eingeben. Die Schrittweite ist jetzt 0,1; der Bereich kommt
  weiterhin aus `idm-heatpump-api`.

### Geändert

- **Heizkurven-Parameter sind Experten-Entitäten.** `hc_{x}_heating_curve`,
  `hc_{x}_parallel_shift`, `hc_{x}_setpoint_flow_constant` und
  `hc_{x}_setpoint_flow_cooling` werden auf **neuen** Installationen deaktiviert
  erzeugt, wie `power_limit_hp` es bereits war. Sie definieren die Auslegung des
  gesamten Heizsystems und schreiben in EEPROM-Register. Bestehende Installationen
  sind nicht betroffen — `entity_registry_enabled_default` greift nur, wenn eine
  Entität erstmals erstellt wird.

### Hinzugefügt

- **Dashboard-Beispiel pro Heizkreis**
  (`docs/examples/dashboard-idm-heating-circuit.yaml`). Home Assistant sortiert eine
  Geräteseite alphabetisch und mischt Komfort-Sollwerte mit
  Auslegungsparametern; das Beispiel hält sie in getrennten Abschnitten und ergänzt
  einen Verlaufsgraphen aus gemessenem Vorlauf, angefordertem Vorlauf, Raum- und
  Außentemperatur.
- **Vertragstest für die Web-Werteschlüssel** (`tests/test_cross_repo_contract.py`).
  Er vergleicht die Wertnamen, die `idm-heatpump-api` liefern kann, mit den
  Schlüsseln, die die Integration in Entitäten überführt, und schlägt fehl, sobald
  die API einen Wert bietet, den die Integration still verwerfen würde — die
  Ursache des Kreis-B–G-Fehlers in 0.13.0.

## v0.13.0 — 2026-08-18

Minor-Release mit einem Fix, der neue Entitäten auf Anlagen mit mehr als einem
Heizkreis erscheinen lässt, plus deutsche Namen für die optionalen Kreise. Vollständig
abwärtskompatibel: Konfigurationseinträge, Entitäts-IDs, Unique-IDs, Registeradressen
und Schreibpfade sind unverändert, und das getestete Abhängigkeits-Paar ist identisch
mit 0.12.0.

### Behoben

- **Web-Entitäten für jeden Heizkreis, nicht nur Kreis A.** Die Navigator-Webwerte
  für die Kreis-Pumpe (`M31`–`M37`), den Mischer (`M41`–`M47`) und die
  Vorlauftemperatur (`B51`–`B57`) liefert `idm-heatpump-api` für die Kreise A–G,
  aber die Integration griff nur die Kreis-A-Schlüssel aus einer statischen
  Allowlist auf. Ein später über den Options-Flow aktivierter Kreis bekam daher nie
  seine `(Web)`-Entitäten — die Werte kamen an und wurden verworfen. Web-Entitäten
  werden jetzt je konfiguriertem Heizkreis erstellt und erscheinen so beim
  Neuladen, das auf eine spätere Aktivierung folgt.
- **Deutsche Namen für die Heizkreise B–G.** Die Namenstabelle enthielt nur
  `hc_a_*`-Einträge, sodass jeder optionale Kreis auf den englischen Standard
  zurückfiel (`Hc D Cooling Limit` statt `Kühlgrenze HK D`). Die Namen für B–G
  werden jetzt aus der Kreis-A-Tabelle abgeleitet. Entitäts-IDs und Unique-IDs sind
  unverändert; nur der angezeigte Name unterscheidet sich.

## v0.12.0 — 2026-08-17

Minor-Release mit zwei neuen Funktionen und einem Abfrage-Fix. Vollständig
abwärtskompatibel: Konfigurationseinträge, Entitäts-IDs, Unique-IDs, Registeradressen
und Schreibpfade sind unverändert, und das getestete Abhängigkeits-Paar ist identisch
mit 0.11.1.

### Hinzugefügt

- **Vorlaufabweichung je Heizkreis** (`calculated_hc_{a..g}_flow_deviation`): die
  gemessene Vorlauftemperatur eines Kreises minus den Vorlauf-Sollwert, den der
  Regler für denselben Kreis anfordert. Positiv heißt Übererfüllung, negativ heißt,
  der Kreis erreicht seinen Sollwert nicht — die Kennzahl beim Tunen einer
  Heizkurve. Nichts wird geschätzt; beide Operanden sind dekodierte Register eines
  Kreises. Inaktive (`0.0`) und unkonfigurierte (`-1.0`) Kreise melden
  `unavailable` statt einer bedeutungslosen Abweichung. Mit aktivierter
  Geräte-Hierarchie sitzt der Sensor auf seinem Heizkreis-Gerät.
- **Selbstdiagnose für ein zu kurzes Abfrageintervall**: Wenn die Abfrage über
  mehrere Zyklen hintereinander mindestens 80 % ihres eigenen Intervalls beansprucht,
  erklärt ein Repair-Issue die Lage und nennt die drei wirksamen Gegenmittel. Genau
  diese Sättigung wird zu Timeouts — besonders, wenn ein zweiter Modbus-Client sich
  den Regler teilt.

### Behoben

- Berechnete Sensoren konnten unter entitätsbewusster Abfrage ihre Quellregister
  verlieren — `calculated_cop` fehlte in der handgepflegten Abhängigkeitsliste,
  sodass das Deaktivieren der beiden Leistungssensoren den COP-Sensor dauerhaft
  unverfügbar machte. Abhängigkeiten werden jetzt aus den Sensor-Definitionen
  abgeleitet.

Siehe [`docs/CHANGELOG.md`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CHANGELOG.md#0120---2026-08-17)
für den vollständigen Eintrag inklusive Test- und CI-Änderungen.

## v0.11.1 — 2026-08-15

Patch-Release, der [#192](https://github.com/Xerolux/idm-heatpump-hass/issues/192)
behebt: Eine Laufzeit-Modellkorrektur aus dem Web-Supplement (z. B. Navigator 2.0 →
Navigator 10 anhand eines NAV10-Firmware-String-Matches) aktualisierte den
Live-Zustand des Koordinators, aber Home Assistants Geräte-Registry — einmalig beim
Entitäts-Setup befüllt — erhielt die Korrektur nie, weil dieser Erkennungsschlüssel
bewusst aus dem Neulade-Fingerprint ausgeschlossen ist, um aktive Verbindungen nicht
abzureißen. Die Geräteseite zeigte weiterhin das ursprüngliche Modell, während die
Diagnose das korrigierte bereits zeigte. Der Koordinator schreibt ein geändertes
Modell, Firmware oder eine Seriennummer jetzt direkt in die Geräte-Registry, wann
immer eine Korrektur eines davon tatsächlich ändert.

## v0.11.0 — 2026-08-15

Erste stabile Version der 0.11.x-Linie, nach acht Betas
(`0.11.0-beta.1` – `0.11.0-beta.8`). Vollständig abwärtskompatibel: bestehende
Konfigurationseinträge, Entitäts-IDs, Registeradressen und Schreibpfade sind
unverändert. Siehe [`docs/CHANGELOG.md`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CHANGELOG.md#0110---2026-08-15)
für das vollständige konsolidierte Changelog.

### Hinzugefügt

- Der direkte Modbus-TCP-Socket läuft jetzt über `modbus-connection==4.0.0a3`
  mit dem `tmodbus==0.5.0`-Backend und ersetzt den bisherigen direkten
  Pymodbus-Pfad.
- Externe Feuchtigkeits-Weiterleitung und externe Speichertemperatur-Weiterleitung
  (GLT), neben der bestehenden Raumtemperatur-Weiterleitung je Heizkreis.
- Transport-Diagnose (Versionen von `modbus-connection`/`tmodbus`,
  Socket-Eigentum, Verbindungsstatus).

### Geändert

- `idm-heatpump-api[web]` gepinnt `0.9.1` → `1.0.1` (die stabile API-1.x-Linie
  führt den öffentlichen Transport-Injection-Vertrag ein, auf den sich der
  tmodbus-Pfad dieser Integration verlässt).
- Minimale Home-Assistant-Version auf `2026.8.1` angehoben;
  Geräte-Registry-Migration `via_device` → `via_device_id`.

### Behoben

- Acht bestätigte Fehler aus einem vollständigen Codebase-Audit (Preset-Modus-
  Sicherheit der Klima-Entitäten, ein `KeyError` in `write_register`, ein IP-Leck
  in der Diagnose, eine Register-Cache-Kollision, eine Lücke im Schreibfilter,
  Eingabeverlust beim Rekonfigurieren, ein veralteter Geräteinfo-Cache und ein
  Zähler-Reset bei der Zonenraum-Validierung), dazu Repair-Issue-IDs, die jetzt je
  Konfigurationseintrag gültig sind, und engere Exception-Behandlung im
  Abfrage-Koordinator.

### Bekannte Einschränkung

- Eine Nacharbeit zur Modellerkennung Navigator 2.0/Terra SWM
  ([#192](https://github.com/Xerolux/idm-heatpump-hass/issues/192)) bleibt
  offen und wird nach dem Release untersucht.

## v0.11.0-beta.3 - 2026-08-05

- Führt den direkten `modbus-connection==4.0.0a3` / `tmodbus==0.5.0`-Socket mit der
  stabilen `idm-heatpump-api[web]==1.0.0` fort.
- Flüchtige Modbus-Exception-Codes 5 (Acknowledge), 6 (Server Device Busy), 10
  (Gateway Path Unavailable) und 11 (Gateway Target Failed to Respond) werden
  jetzt in `ModbusException` übersetzt, sodass die API-Retry-Schleife sie am Ort
  auf derselben Verbindung wiederholt, statt eine harte Wiederverbindung zu
  erzwingen — passend zum API-1.0-Transportvertrag (Retry-in-Place-Pfad). Code 2
  bleibt für die Bisektionslogik des Koordinators `IllegalAddressError`.
- Die tote Menge `_NON_RETRYABLE_DEVICE_EXCEPTION_CODES` wurde entfernt und
  Kommentare korrigiert, die das API-Retry-Verhalten falsch beschrieben.

## v0.11.0-beta.1 — 2026-08-04

- Dies ist die erste IDM-Integrations-Beta, deren direkter Modbus-TCP-Socket über
  `modbus-connection==4.0.0a3` mit dem separat gepinnten
  `tmodbus==0.5.0`-Backend läuft. `4.0.0a3` ist die Version der
  Transportbibliothek; die Version der IDM-Integration ist `0.11.0-beta.1`
  (aktuell stabil: `0.10.1`).
- `idm-heatpump-api[web]==0.9.1` besitzt weiterhin das Registermodell, das
  Batching, die Enkodierung/Dekodierung, die Modellerkennung und die
  Schreibsicherheit. Seine Abhängigkeit `pymodbus>=3.12.1,<4.0` bleibt
  vorübergehend gepinnt, weil die API 0.9.1 sie noch importiert, aber pymodbus
  besitzt den direkten Socket nicht mehr.
- Diagnose und der API-Versions-Sensor führen jetzt die Versionen von
  `modbus-connection` und `tmodbus` plus geschwärzte Transport-Fähigkeiten.
- Der Adapter ist implementiert und von automatisierten Tests abgedeckt. Jeder
  Konfigurationseintrag besitzt weiterhin seinen Socket und meldet
  `supports_shared_connection: false`, weil es das zentrale Teilen über
  Konfigurationseinträge in Home Assistant nicht gibt; die Nur-Lese-Validierung
  des neuen Pfads auf echter Navigator-Hardware steht noch aus.
- Flüchtige Modbus-Antworten 5 (Acknowledge), 6 (Server Device Busy), 10
  (Gateway Path Unavailable) und 11 (Gateway Target Failed to Respond) verlassen
  die Batch-Schicht ohne Einzel-Lese-Fallback oder dauerhafte
  Register-Quarantäne. Vom Backend übernommene Busy-Retries werden vom Adapter
  nicht dupliziert.
- Diese Beta erfüllt die stabilen Hardware-Smoke- und Soak-Gates noch nicht.

## v0.8.5 — 2026-07-23

Erste stabile Version der 0.8.5-Linie. Fasst die acht Beta-Kandidaten zusammen
plus die finalen i18n- und Stabilitäts-Fixes aus dem Stable-Code-Review.

### Hinzugefügt

- **Manual Navigator model override** (Auto / Navigator 10 / Navigator 2.0 /
  Navigator Pro), wenn die automatische Erkennung mehrdeutig ist.
- **Restart-sicherer Warmwasser-Boost** mit den Services
  `idm_heatpump.start_dhw_boost` und `idm_heatpump.cancel_dhw_boost` sowie
  Start-/Cancel-Buttons. Der Boost-Zustand überlebt HA-Neustarts.
- **Optionale Gerät-Hierarchie** (Wärmepumpe, DHW-Controller, Zonenmodule als
  separate Sub-Geräte).
- **Entity-bewusstes Modbus-Polling**, **Momentan-COP-Sensor** und
  **Betriebszyklus-Analyse** (Verdichter-/Abtau-Zähler).
- **Navigator-Web-Binary-Sensoren** für Online-/Regler-Online-Status.

### Geändert

- **API-Pin aktualisiert:** `idm-heatpump-api[web]==0.8.4` (war 0.8.1).
  Bringt sentinel-aware Heizkreis-Modus-Probes, robusteren Navigator-10-vs-2.0-Differenzierer
  für Terra SWM, automatische Kaskadenerkennung und Navigator-10-Heizkreisdaten
  für die Kreise B–G.
- **Klima- und Warmwasser-Entitäten melden ihre unterstützte Schrittweite**
  (0,5 °C bzw. 1 °C für integer-backed Register).
- **Modbus-Register-Wiki** gegen API 0.8.4 regeneriert.
- **Repository aufgeräumt** (`.planning/`, alte `ROADMAP.md`, verwaiste Skripte
  und AI-Handoff-Doku entfernt).
- **README und HA-Core-Entwurf** listen jetzt alle 8 Plattformen und das
  vollständige Service-Set inkl. DHW-Boost.

### Behoben

- **Integer-Modbus-Numbers bieten keine invaliden Nachkommastellen mehr an**
  ([#158](https://github.com/Xerolux/idm-heatpump-hass/issues/158)).
- **Terra SWM / Navigator 2.0 wurde fälschlich als Navigator 10 erkannt**
  (Issue #44); die Erkennung verlangt jetzt plausible Power-Limit-Werte.
- **Water-Heater-Entität ignoriert jetzt den Unused-Sentinel** und zeigt nicht
  mehr `-1 °C` als Live-Temperatur an.
- **DHW-Boost nutzt Übersetzungsschlüssel** statt harter deutscher Strings;
  die Multi-Device-Service-ValidationError verwendet den bestehenden Schlüssel
  `multiple_entries_select_entry`.
- **DHW-Boost:`DhwBoostError` wird im Timeout-/Target-Restore-Pfad sauber
  abgefangen** statt als unhandled Task-Exception durchzuschlagen.

### Bekannte Einschränkung

- **Home Assistants experimentelle `modbus_connection` wird noch nicht
  verwendet.** Der vorbereitete Transport-Vertrag bleibt bewusst inaktiv, bis
  die offizielle HA-Schnittstelle final ist.

## v0.8.5-beta.8 — 2026-07-23

### Geändert

- **Neue Beta-Kandidatenversion `0.8.5-beta.8`:** Aktualisiert Manifest,
  Release-Evidence, Changelog und Wiki-Verweise auf den aktuellen Beta-Stand.
  Laufzeitcode, Entitäten, Register, Schreibpfade und der getestete
  `idm-heatpump-api[web]==0.8.4`-Pin bleiben unverändert.

## v0.8.5-beta.7 — 2026-07-22

### Behoben

- **Endgültiges Navigator-Modell wird mit der API synchronisiert:** Manuelle
  Modell-Overrides und eindeutige spätere Web-Korrekturen gelten nun auch für
  die modellabhängigen Register- und Schreibprüfungen der API.
- **Zukünftiger Modbus-Transportvertrag korrigiert:** Der weiterhin inaktive
  Vertrag unterscheidet FC04/Input Register und FC03/Holding Register und
  begrenzt Slave-IDs auf 1–247. Der produktive Transport bleibt unverändert.

## v0.8.5-beta.6 — 2026-07-22

### Behoben

- **Ganzzahlige Modbus-Werte verwenden jetzt Schrittweite 1:** Heiz- und
  Kühlgrenzen der Heizkreise A–G sowie alle weiteren schreibbaren Integer-
  Register bieten keine ungültigen 0,5-Schritte mehr an.
- **Climate und Warmwasser melden die unterstützte Zielwert-Schrittweite:**
  Heizkreis- und Raum-Sollwerte verwenden 0,5 °C, der ganzzahlige Warmwasser-
  Sollwert 1 °C.

## v0.8.5-beta.5 — 2026-07-22

### Geändert

- **Pin auf `idm-heatpump-api[web]==0.8.4`:** Aktualisiert die API-Bibliothek
  auf v0.8.4 für verbesserte Modbus-Modellerkennung (Erkennung aktiver Heizkreise
  über Betriebsmodus-Register, verlässliche Abfrage für Navigator 10 vs. 2.0
  bei Terra SWM Firmware und Kaskaden-Erkennung).

## v0.8.4 — 2026-07-19

### Geändert

- **Zonenmodul-Raumrelais ist jetzt ein `binary_sensor`:** Der Relaisstatus
  pro Raum (`zm{z}_room{r}_relay`) wurde bisher als numerischer Sensor mit
  `0`/`1` angezeigt. Er läuft jetzt auf der `binary_sensor`-Plattform und
  zeigt `on`/`off` (Device Class `Running`, Toggle-Icon). Erfordert das
  mitgelieferte `idm-heatpump-api[web]==0.8.1`, in dem das Relay-Register
  als `binary=True` markiert ist. Schließt #128.
- Pin auf `idm-heatpump-api[web]==0.8.1`.

## v0.8.3 — 2026-07-16

### Geändert

- **Pin auf `idm-heatpump-api[web]==0.8.0`:** Wirkt zwei Verbesserungen der
  Bibliothek automatisch aus (keine Code-Änderung an der Integration):
  - `detect_model` erkennt **nicht-kontinuierliche Heizkreise** (z. B. nur HK A
    und HK D installiert) zusätzlich über die Active-Mode-Register 1498–1504.
  - Der Navigator-10-Web-Client liefert **Vorlauf, Pumpe und Mischer der
    Heizkreise B–G** (vorher nur HK A und HK C).
  - Enthält den IPv4/IPv6-Web-Anmeldungsfix für den Navigator 2.0 aus API 0.7.7.

## v0.8.2 — 2026-07-12

### ⚠️ Wichtige Hinweise zum Update (Breaking Changes)

Das direkte Update von v0.8.1 auf v0.8.2 enthält keine zusätzlichen Breaking
Changes. Bei einem Update von v0.7.4 oder älter gelten weiterhin die
v0.8-Änderungen: lokaler Webzugriff mit PIN, die fest gepinnte API 0.7.6, neue
`climate`- und `water_heater`-Plattformen, die entfernte Entität
`ext_demand_brine_pump_m16`, fehlertolerantes Polling und IP-unabhängige Unique
IDs. Die vollständigen Hinweise stehen im [Changelog](../CHANGELOG.md).

### Korrekturen

- Benennt native Regler eindeutig als **Heizkreis A**, **Zone 1 Raum 1** und
  **Warmwasser**, statt den Gerätenamen für mehrere Entitäten anzuzeigen.
- Zeigt für Warmwasser den passenden Modus **Wärmepumpe** statt des
  irreführenden Status **Hochleistung**.
- Vervollständigt die kanonischen Entity-Texte und sichert das Naming mit Tests
  ab.

## v0.8.1-beta.29 — 2026-07-11

- Merkt sich das erfolgreiche lokale Web-Protokoll von Navigator 2.0 oder
  Navigator 10/Pro und wiederholt während der normalen Laufzeit-Wiederherstellung
  nur dieses Protokoll.
- Probiert während Setup, Rekonfiguration und Repair beide unterstützten
  Web-Protokolle und behandelt den lokalen Netzwerkcode `0` als deaktiviert.
- Schwärzt Web-Host, Web-PIN und detaillierte Web-Verbindungsstrings aus der
  heruntergeladenen Diagnose.
- Ergänzt GLT-Monitor-Diagnose, Anleitung zu schreibbaren Steuerungen, exakte
  PV-/Batterie-Datentypen und abgesicherte Beispiele für PV-Überschuss und
  externe Warmwasseranforderungen.
- Behält `idm-heatpump-api[web]==0.7.6`; dieses Release braucht eine neue
  Integrationsversion, kein neues API-Paket.
- Konsolidiert verifizierte Randbedingungen und die verbleibende
  Verifizierungsarbeit in der Projektwissensbasis und im Wiki.

## v0.8.1-beta.28 — 2026-07-11

- Pinnt das veröffentlichte `idm-heatpump-api`-Stabilitäts-Release 0.7.6.
- Leitet Transportfehler weiter, ohne gültige Register zu deaktivieren.
- Setzt bewiesene Raummodus-Batch-Abweichungen unter Quarantäne und vermeidet
  spätere Doppellesevorgänge.
- Erkennt den verifizierten Kaskade-nicht-verfügbar-Sentinel.
- Stellt explizit bestätigte Schreibvorgänge auf benutzerdefinierte Register mit
  numerischer Validierung wieder her.

## Unveröffentlichtes Stabilitäts-Audit — 2026-07-10

- Transport-/Antwortausfälle zählen nicht mehr als dauerhafte Ausfälle einzelner
  Register.
- Die Zonenraum-Modusvalidierung isoliert nicht unterstützte/ungültige Werte und
  vermeidet wiederholte Doppellesevorgänge nach der Quarantäne.
- Die Kaskadenfähigkeit des Navigator 10 erkennt den hardwareseitig bestätigten
  `255`-Nicht-verfügbar-Sentinel.
- Erweiterte Raw-Schreibvorgänge behalten numerische/Datentyp-Validierung und
  erfordern eine explizite Risiko-Bestätigung.
- Messbare [Stable-Release-Gates](Stability-and-Release-Readiness) hinzugefügt.

## v0.8.1-beta.27 — 2026-07-10

- Hat die hardwareverifizierte API 0.7.5 gepinnt.
- Register-spezifische Behandlung von Nicht-verfügbar-Sentinelwerten hinzugefügt.
- Hat 170 Definitionen über 45 Gruppen in 309 Nur-Lese-Batch-/Einzelprüfungen
  verglichen, ohne einen Rohwert-Mismatch.

---

## Historische Zusammenfassung

## v0.4.6 — 2026-05-31

- 169+ Entitäten (109 Sensoren, 8 Binärsensoren, 44 Zahl-Entitäten, 4 Auswahl-Entitäten, 4 Schalter-Entitäten)
- Vollständige Integration der `idm_heatpump`-Bibliothek (Option B abgeschlossen)
- Binärsensoren für Verdichter, Störalarme, Heiz-/Kühl-/Warmwasser-Anforderung
- Solar-, ISC-, PV- und Kaskaden-Register vollständig enthalten
- Deutsche Entitätsnamen durchgängig
- Schutz des Nur-Schreib-Registers (`error_acknowledge`)

## v0.4.4 — 2026-05-31

- Vollständige Migration auf die `idm-heatpump`-Bibliothek als Kern
- Navigator-10-Unterstützung: Wärmesenken-Sensoren, Durchfluss, Grundwassertemperaturen
- Booster-A/B-Diagnose (16 neue Sensoren)

## v0.4.0 — 2026-05-30

- Große architektonische Änderung
- Navigator-10-Unterstützung hinzugefügt
- Erste große bibliotheksgestützte dynamische Registermap

## v0.2.0 — 2026-03-22

- Erstveröffentlichung
- Grundlegende Modbus-TCP-Integration
- Systemsensoren, Heizkreise, Warmwasser-Steuerung
