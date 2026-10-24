# iDM Smart Energy & Comfort

Die Integration kann als schlanke **Vanilla**-Integration oder mit dem
optionalen Funktionsprofil **iDM Smart Energy & Comfort** betrieben werden.

<p align="center">
  <img src="../images/smart-energy-comfort-overview.svg" alt="Smart-Energy-&-Comfort-Übersicht: Energie und Kosten, Health Monitor und Empfehlungen, Komfort-Zeitpläne und PV-Boost, externe Leistungsweiterleitung" width="860">
</p>

Dieser Leitfaden beschreibt die Version **0.18.0**.

| Funktion | Standard | Wirkung auf die Wärmepumpe |
|---------|---------|-------------------------|
| Smart-Profil | Ein | Ergänzt Analysen und Boost-Steuerung; die Analyse allein schreibt nicht |
| Health Monitor | Aus | Nur lesende Prüfungen und Bericht |
| Heizkurven-/Wetterberatung | Aus | Nur lesende Empfehlungen |
| Externe Leistungsweiterleitung | Aus | Schreibt ausgewählte HA-Werte in IDM-GLT-Eingänge |
| Automatisches PV-Überschuss-Warmwasser-Laden | Aus | Startet den Warmwasser-Boost, wenn aktiviert und zulässig |
| Komfort-Zeitplan | Aus | Schreibt Raum-Sollwerte der Heizkreise und stellt sie bedingt wieder her |

Weiterleitung, automatisches Warmwasser-Laden und Zeitplanung sind separate
Optionen. Smart zu aktivieren oder den Expertenmodus zu wählen schaltet diese
Schreibfunktionen nicht ein.

## Vanilla

Vanilla stellt die IDM-Kern-Entitäten aus Modbus und Web bereit. Es hält die
Integration schlank und legt keine zusätzlichen berechneten Analyse-Entitäten
an.

## iDM Smart Energy & Comfort

Dieses Profil ergänzt lokale berechnete Sensoren, Verdichterlaufzeit- und
Zyklusanalyse, Kurzzyklus-Diagnose, persistente elektrische und thermische
Energie-Statistiken, COP-Statistiken sowie abgesicherte Warmwasser-Boost-
Steuerungen. Die Analyse ist nur lesend. Sie stoppt den Verdichter nicht und
ändert die Heizkurve nicht.

## Aktivierung

Öffne **Einstellungen → Geräte & Dienste → IDM Heatpump → Neu konfigurieren →
Funktionen**. Wähle Standard, Erweitert oder Experte, wähle die Kategorie
**Funktionsprofil** und dann entweder:

- **iDM Smart Energy & Comfort** für die optionalen Funktionen
- **Vanilla** für nur die IDM-Kern-Entitäten

Alle Einrichtungstiefen bieten dieselben Funktionen. Erweitert und Experte
zeigen mehr Tuning-Optionen; bereits gesetzte Werte aus einem tieferen Modus
bleiben gespeichert. Wähle die zusätzlichen Kategorien, die du brauchst, folge
ihren Seiten und bestätige dann zum Speichern.

Beim Speichern wird die Integration neu geladen. Kern-Entitäts-IDs bleiben
unverändert. Wenn du Smart, Health oder einen Berater deaktivierst, werden
seine optionalen Entitätsregistrierungen entfernt; beim erneuten Aktivieren
werden seine Entitäten mit denselben IDs neu angelegt. Die Gerätshierarchie
ist optional: Analyse, Health Monitor, Komfort und Diagnose bekommen eigene
Gruppen, wenn sie aktiviert ist.

## Persistente Energie-Statistiken

Sind die erforderlichen IDM-Leistungsregister verfügbar, ergänzt Smart
Gesamt-, Tages- und Monatssensoren für elektrische und thermische Energie
sowie Gesamt-, Tages- und Monatssensoren für den COP. Werte werden nur aus
endlichen, nicht-negativen Leistungsmesswerten integriert und über
Home-Assistant-Neustarts hinweg gespeichert. Lange Abfrage-Lücken und
ungültige Messwerte werden ausgeschlossen, statt geschätzt zu werden.

Sowohl die elektrischen als auch die thermischen Leistungsregister müssen
gültige Messwerte liefern. Zähler setzen nach einer Lücke mit neuen gültigen
Intervallen fort; sie rekonstruieren keine Energie, die verbraucht wurde,
während Home Assistant offline war. Tages- und Monatszeiträume folgen der
Home-Assistant-Zeitzone und werden beim nächsten beobachteten Snapshot
zurückgesetzt. In Beta 6 wird die tägliche PV-Schätzung zusammen mit den
anderen Tageswerten zurückgesetzt, und die Leistungsregister bleiben im
Abfrageplan, auch wenn ihre rohen Entitäten deaktiviert sind. Lebenslange
Gesamtwerte bleiben über Zeitraumwechsel hinweg erhalten.

Dieselben Statistiken liefern optionale geschätzte Stromkosten, CO₂-Emissionen
und den PV-Eigenverbrauch der Wärmepumpe. Strompreis und Emissionsfaktor sind
lokale Werte des Konfigurationsflusses. Ein optionaler Home-Assistant-Sensor
mit einem Preis in EUR/kWh, €/kWh oder ct/kWh kann einen wechselnden Tarif
liefern. Jedes beobachtete Intervall wird zum aktuellen Wert bepreist;
Intervalle mit ungültigem oder nicht verfügbarem Preis bleiben unbepreist,
ihre Energie wird aber weiterhin gezählt. Die alte Schätzung mit Festpreis
bleibt erhalten, wenn eine bestehende Installation auf den Sensor umstellt.
Der PV-Eigenverbrauch wird nur berechnet, wenn in der externen
Leistungszuordnung eine PV-Produktionsquelle ausgewählt ist. Er ist eine
Schätzung, begrenzt durch die elektrische Energie der Wärmepumpe und die
ausgewählte PV-Produktion — keine gemessene Aufteilung der Solarenergie:
Haushaltslasten und Batterieflüsse werden nicht abgezogen. Der Standardwert
der Kosten liegt bei EUR 0,30/kWh, der des Emissionsfaktors bei 350 g
CO₂/kWh; konfiguriere Werte, die zu deiner Installation passen. Negative
Tarife und Preise über EUR 5/kWh behandelt die aktuelle Implementierung als
ungültig.

Analyse-Entitäten landen in einer separaten Gerätegruppe **iDM Analytics**,
wenn die Gerätshierarchie aktiviert ist. Das hält das Hauptgerät der
Wärmepumpe auf die Reglerwerte fokussiert und ändert keine Entitäts-IDs.

## Optionale PV-Überschuss-Warmwasser-Automation

Die Option **Automatisches PV-Überschuss-Warmwasser-Laden** ist
standardmäßig deaktiviert. Sie nutzt die ausgewählten externen
Leistungssensoren und startet nur den bestehenden transaktionalen
Warmwasser-Boost mit einem vorübergehend erhöhten Warmwasser-Sollwert. Der
automatische Boost lässt die Betriebsart unverändert, sodass die Raumheizung
verfügbar bleibt. Der manuelle Boost schaltet weiterhin auf nur Warmwasser.
Heizkurve und Einstellungen der Zusatzheizung werden nicht verändert.

Voraussetzungen:

- Das Smart-Profil ist aktiv.
- Die Zuordnung der externen Leistungsquellen enthält entweder einen
  PV-Überschuss-Sensor oder PV-Produktions- und Hausverbrauchssensoren.
- Ein Batterie-SOC-Sensor kann optional einen Mindest-Batteriestand erzwingen.
- Die Bestätigung, dass Home Assistant der einzige Warmwasser-Regler ist, ist
  aktiviert.

Ohne die Eigentumsbestätigung startet die Automation nie. Aktiviere sie
nicht, solange Smartfox, openWB oder ein anderes System das Warmwasser
steuert. Ungültige oder nicht verfügbare Quellwerte führen dazu, dass sicher
nichts gestartet wird (fail closed). Minimaler Überschuss, minimaler SOC,
Warmwasser-Ziel, maximale Dauer und Cooldown sind konfigurierbar.

| Einstellung | Standard | Einrichtungstiefe |
|---------|---------|-------------|
| Minimaler Überschuss | 1.0 kW | Erweitert / Experte |
| Minimaler Batterie-SOC, wenn ein Sensor ausgewählt ist | 20 % | Erweitert / Experte |
| Warmwasser-Ziel | 55 °C | Erweitert / Experte |
| Maximale Boost-Dauer | 90 Minuten | Experte |
| Sperrzeit nach Ende des automatischen Boosts | 60 Minuten | Experte |

Wähle die Sensoren in der externen Leistungszuordnung aus; die Zuordnung ist
gemeinsam, aber das Schreiben dieser Werte in GLT-Register wird separat
aktiviert. Leistungsquellen müssen W, kW oder MW angeben. Die SOC-Quelle
akzeptiert einen Prozentsatz von 0 bis 100. Ein ausdrücklich ausgewählter
Überschuss-Sensor hat Vorrang. Wird er ungültig, ersetzt der Manager ihn
nicht durch die PV-Bruttoproduktion minus Hausverbrauch. Ohne
Überschussquelle kann er diese Differenz aus zwei gültigen, nicht-negativen
Leistungsmesswerten ableiten.

Leistungsquellen lassen sich beim Rekonfigurieren wieder leeren. Vorhandene
Werte sind Vorschläge. Das Entfernen der Batterie-SOC-Auswahl entfernt nach
dem Reload diese Zuordnung und die optionale HA-Bedingung für den Boost-Start.
Andere ausgewählte Quellen bleiben erhalten. Leeren stoppt die Weiterleitung,
überschreibt aber keinen Reglerwert mit einem Ersatzwert. Der Regler kann den
letzten Wert bis zu seinem eigenen Timeout oder einer Aktualisierung durch eine
andere Quelle behalten. SOC-Quellen mit Nachkommastellen werden akzeptiert und
für das GLT-Register gerundet (97,5 % wird 98 %). Die HA-Boost-Bedingung verwendet
den ursprünglichen Wert mit Nachkommastellen.

Die Weiterleitung ist ereignisgetrieben: Eine Sensor-Aktualisierung wird
innerhalb von etwa einer Sekunde geschrieben. Weitere Aktualisierungen werden
gebündelt, ohne einen laufenden Übertragungsdurchgang abzubrechen. Änderungen
während der Übertragung lösen einen weiteren Durchgang mit den aktuellen
Quellwerten aus. Periodische und ereignisgesteuerte Durchgänge überlappen nicht.
Bei aktivierter Weiterleitung werden gültige zugeordnete GLT-Eingänge alle drei
Sekunden erneut geschrieben, auch bei unveränderten Quellen. Diese
RAM-Auffrischung hat Vorrang vor dem konfigurierten *Weiterleitungsintervall für
externe Leistungswerte* (30–3600 Sekunden). Der Schreib-Cooldown dieser Eingänge
ist auf zwei Sekunden begrenzt; schnellere Sensorereignisse können still
übersprungen werden.

Deaktivieren oder Entladen der Integration beendet diese Schreibzugriffe ohne
Nullwert, Ungültig-Markierung oder Rücksetzbefehl. Beim erneuten Aktivieren
werden die aktuellen gültigen Quellwerte verwendet, keine gespeicherten alten
Werte. Einen allgemeinen Regler-Timeout garantiert die Integration nicht:
Gespeicherte Werte und vorübergehend nicht verfügbare Regleranzeigen benötigen
jeweils einen Nachweis für die konkrete Firmware. Der am 21.10.2026 in #493
gemeldete Rückfall bleibt ungeklärt. Ein erfolgreicher Schreibzugriff oder ein
optimistischer HA-Zustand beweist keine durchgehend gültige Navigator-Anzeige.
Ein pauschales Zurücksetzen beim Beenden könnte einen anderen GLT-Schreiber
überschreiben.

Der aktuelle Assistent öffnet die Seite der Quellzuordnung über die
aktivierte externe Leistungsweiterleitung. Bestehende Zuordnungen bleiben
mit deaktivierter Weiterleitung nutzbar; ein eigenständiger, nur lesender
Quellen-Wähler wird derzeit nicht angeboten. Siehe
[Konfiguration](Configuration#zuordnung-und-weiterleitung-externer-leistung),
bevor du ein Setup änderst, das bereits einen externen Energieregler hat.

Der Manager wertet etwa alle 30 Sekunden aus. Seine Überschuss- und
SOC-Prüfungen steuern den **Start** eines Boosts. Ein späterer Abfall von
Überschuss oder SOC bricht einen bereits laufenden Boost nicht automatisch
ab; Ziel, Timeout und Wiederherstellungsregeln des Boosts gelten weiterhin.
Ein automatischer Boost startet nur im Automatik- oder Nur-Warmwasser-Modus,
nach erfolgreicher Reglerabfrage und mit gültiger Warmwassertemperatur mindestens
5 °C unter seinem Ziel. Diese feste Nachladehysterese verhindert Nachladen bei
kleinen Temperaturabfällen. Die volle Sperrzeit beginnt, wenn der Manager das
Ende, den Abbruch oder das Zeitlimit erkennt, auch ohne Sonne. Die Reservierung
wird vor dem ersten Schreibzugriff gespeichert. Reloads und Neustarts erhalten
den Schutz; nach Wiederherstellung eines unterbrochenen Boosts beginnt bei der
ersten Auswertung eine volle Sperrzeit. Auch fehlgeschlagene Starts und Starts
ohne tatsächlich aktivierten Boost behalten diesen vorsichtigen Schutz.
Benötigte Warmwasser- und Betriebsartregister bleiben auch bei deaktivierten
Rohentitäten in der Abfrage. Die
Checkbox zur exklusiven Steuerung erklärt die Eigentümerschaft; sie kann
einen anderen Regler weder finden noch stoppen. Ein vorübergehender
Auswertungsfehler wird geloggt und die nächste Auswertung erneut versucht.

### PV-Ladung des Reglers und Heizpufferzyklen

Die externe Leistungsweiterleitung ist unabhängig vom Warmwasserautomaten.
Sie übergibt ausgewählte Messwerte einschließlich des vorzeichenbehafteten
`pv_surplus` an den Navigator. Damit kann dessen **eigene PV-Ladung von
Warmwasser und Heizpuffer** entsprechend seinen PV-Schwellen, Speichergrenzen
und seiner Hysterese aktiv werden. Die Sperrzeit des Warmwasserautomaten
blockiert diese Reglerlogik nicht. Die Weiterleitung schreibt keine Betriebsart,
Heizpufferziele, Heizkurven oder SG-Ready-Werte.

Der Nettoüberschuss muss **bei Einspeisung positiv** und bei Netzbezug negativ
sein; prüfe die Vorzeichenkonvention des Wechselrichtersensors. Die Weiterleitung
erhält das Vorzeichen einer direkt gewählten Überschussquelle — ein
bidirektionaler Netzleistungszähler gehört stattdessen in das weiter unten
beschriebene eigene Feld. Wähle möglichst einen Verantwortlichen für die PV-Ladung:
den Navigator mit weitergeleiteten Messwerten oder den HA-Warmwasserautomaten
mit vorhandener Quellzuordnung und deaktivierter Weiterleitung. Beide zusammen
bilden keinen gemeinsamen Taktschutz. Lädt der Heizpuffer wiederholt nahe seiner
Obergrenze, prüfe die PV-Heizpuffereinstellungen im Navigator. Die Integration
kann keinen gemeinsamen Verdichterzyklus für Warmwasser und Puffer garantieren;
der Navigator bestimmt Reihenfolge und normalen Heizbedarf.

### Bidirektionaler Netzzähler als Überschussquelle

Statt eines dedizierten Überschusssensors kann ein einzelner bidirektionaler
Netzleistungszähler am Netzverknüpfungspunkt die Zuordnung direkt speisen,
ohne Template-Helfer (#519). Wähle ihn als **Bidirektionaler
Netzleistungssensor** und lege seine Vorzeichenkonvention fest:

- **Positiv = Netzbezug** (negativ = Einspeisung) — der übliche Standard.
- **Positiv = Einspeisung** (negativ = Netzbezug).

Die Integration normalisiert das Vorzeichen und leitet `pv_surplus` (Register
74–75) in der IDM-Konvention ab: positiv = Überschuss/Einspeisung, negativ =
Netzbezug. Ist zusätzlich ein PV-Produktionssensor gewählt, wird
`house_consumption` (Register 82–83) aus der Anlagenbilanz abgeleitet —
PV-Produktion plus Netzbezug, plus die gemappte Batterieleistung (Laden zählt
negativ). Ein explizit gewählter Überschuss- oder Verbrauchssensor hat Vorrang
vor seiner Ableitung; der Netzleistungszähler allein wird nie als
Hausverbrauch geschrieben, denn Netzbezug ist nicht der Gesamtverbrauch, solange
PV erzeugt. Ohne gültige PV-Produktionsquelle wird kein Hausverbrauch abgeleitet,
ein negativ abgeleiteter Wert wird auf null begrenzt, und W- oder kW-Quellen
werden automatisch umgerechnet. Der Konfigurationsdialog lehnt einen
Netzleistungssensor ab, für den keine Ableitung übrig bleibt (expliziter
Überschusssensor zusammen mit explizitem Verbrauchssensor oder fehlende
PV-Produktionsquelle).

Wird eine zugeordnete Batterieleistungsquelle ungültig oder nicht verfügbar,
entfällt der berechnete Hausverbrauch bis zu ihrer Rückkehr. Eine unvollständige
Leistungsbilanz wird nicht verwendet; unabhängige Überschuss- und PV-Werte
werden weitergeleitet.

Der Manager steuert weder die Heizkurve noch die elektrische Zusatzheizung.
Der optionale Tarifsensor beeinflusst nur die Kostenrechnung;
tarifgesteuerte Schreibzugriffe auf die Wärmepumpe sind nicht aktiviert.

## SolarEdge mit Batterie und mehreren Wechselrichtern über GLT

Diese Anleitung gilt, wenn HA mehrere SolarEdge-Wechselrichter und die Batterie
liest und der Navigator die Energiedaten der Anlage über GLT erhalten soll.
Die [aktuell von IDM verlinkte SolarEdge-Anleitung](https://www.idm-energie.at/wp-content/uploads/2021/04/SolarEdge-DE.pdf)
schließt Batteriespeicher und mehrere Wechselrichter bei der nativen Verbindung
aus. Die Anleitung ist älter; prüfe die Unterstützung deiner konkreten
Regler-Firmware, bevor du stattdessen die native Verbindung auswählst.

### Zuständigkeit und Quellenauswahl

1. Wähle im Navigator **Gebäudeleittechnik / Smartfox** als PV-Signal. Beende die
   native SolarEdge-Abfrage und weitere Schreiber auf dieselben GLT-Eingänge.
2. Wähle alle Wechselrichter derselben Anlage und desselben Netz-Zählers.
   Vermische keine anderen Anlagen und addiere keinen Summensensor zusätzlich
   zu seinen einzelnen Quellen.
3. Bestimme den Wechselrichter mit Batterieanschluss. Prüfe Batteriestatus und
   SOC-Verlauf, um das Leistungsvorzeichen zu bestätigen; der Sensorname reicht nicht.
4. Prüfe das Netz-Zähler-Vorzeichen bei beobachtetem Bezug oder Einspeisung.
   Der Generator verlangt für Batterie und Netz eine ausdrückliche Auswahl.
5. Verwende momentane Leistung in **W**, keine Energiezähler in kWh. Wandle
   kW-Quellen zuerst mit eigenen Helfern in W um. Der Batterie-SOC muss Prozent liefern.

### HA-Templates erzeugen

Lade [generate_solaredge_glt_templates.py](https://github.com/Xerolux/idm-heatpump-hass/blob/main/scripts/generate_solaredge_glt_templates.py)
herunter oder führe es im Repository aus. Das Skript verwendet die
Python-Standardbibliothek und erzeugt Dateien, ohne auf HA zuzugreifen oder
Hardware zu beschreiben. Ersetze die Beispiel-IDs durch deine Quellen:

```bash
python scripts/generate_solaredge_glt_templates.py --inverter sensor.pv_hybrid_power --inverter sensor.pv_second_power --inverter sensor.pv_third_power --inverter sensor.pv_fourth_power --hybrid-inverter sensor.pv_hybrid_power --battery-power sensor.battery_power --battery-soc sensor.battery_soc --grid-power sensor.grid_power --battery-positive charging --grid-positive export --output solaredge-glt.yaml --mapping-output solaredge-glt-mapping.json
```

Im Beispiel bedeutet positive Batterieleistung Laden und positive Netzleistung
Einspeisung. Passe beide Vorzeichenargumente an bestätigte Messungen an.
Die Liste kann beliebig viele Wechselrichter mit einem batteriegekoppelten
Hybrid-Wechselrichter enthalten. Doppelte oder überlappende Quell-IDs werden
abgelehnt. Mehrere Batterien oder Hybrid-Wechselrichter benötigen eine separat
geprüfte Aggregation; der Generator errät deren Aufbau nicht.

Prüfe das YAML und füge dessen Sensorblock in deine vorhandene `template:`-
Konfiguration ein; erzeuge keine doppelten Hauptschlüssel. Prüfe die HA-
Konfiguration, lade Template-Entitäten neu oder starte HA neu und kontrolliere
die erzeugten Sensoren. Bestehende Namen können andere Entitäts-IDs verursachen:
Prüfe die tatsächlichen IDs vor der Zuordnung. Das JSON ist eine Referenz für
den IDM-Optionsassistenten, **keine** Datei zum Einfügen in HA `.storage`.
Vorhandene Ausgabedateien werden nicht überschrieben. Die Dateien enthalten
deine ausgewählten Entitäts-IDs; prüfe sie vor einer Weitergabe.

### Berechnung und Verhalten bei Ausfällen

| Erzeugte Messung | Berechnung / Verhalten |
|---|---|
| Wechselrichterleistung | Summe der aktuell gültigen AC-Wechselrichterquellen in W |
| PV-Produktion | Gültige Erzeugung der übrigen Wechselrichter plus Hybrid-AC-Leistung minus normalisierte Batterieentladung; jeder Beitrag mindestens null |
| Hausverbrauch | Verfügbare AC-Wechselrichtersumme minus normalisierte Netzeinspeisung, mindestens null |
| PV-Überschuss | Netzeinspeisung minus Batterieentladung, mindestens null; fehlende Netz-/Batteriedaten oder alle Wechselrichter offline ergeben null |
| Batterieentladung | Positiv beim Entladen, negativ beim Laden |
| Verfügbare Wechselrichter | Anzahl gültiger Wechselrichterquellen in W |

Ein nicht verfügbarer Wechselrichter wird ausgelassen und bei gültigen Werten
automatisch wieder berücksichtigt. Fehlt der Hybrid-Wechselrichter oder dessen
Batterieleistung, entfällt sein PV-Beitrag; die anderen liefern weiter ihre
Beiträge. Ohne gültigen Wechselrichter sind Wechselrichter-/PV-/Hauswerte nicht
verfügbar. Ohne Netz-Zähler ist auch der Hausverbrauch nicht verfügbar.
Ungültige Batterieleistung oder eine falsche Einheit macht den Batteriewert
nicht verfügbar. Der ausdrückliche Null-Überschuss-Helfer verhindert neue PV-
Ladung, solange HA läuft. Er verändert nicht die allgemeine Integrationsregel,
ungültige Quellen zu überspringen.

Teilsummen sind unvollständige Schätzungen, keine vollständige Anlagenmessung.
Die Kombination von AC-Wechselrichter- und DC-Batterieleistung enthält zusätzlich
Umwandlungsverluste und zeitlichen Messversatz. Bevorzuge unabhängig gemessene
und geprüfte PV-/Verbrauchssummen, wenn vorhanden. Diese Anleitung stellt keinen
reglerseitigen Wächter bei einem HA- oder Netzwerkausfall bereit: Der Navigator
kann letzte Werte behalten. Sein Timeout-Verhalten muss separat geprüft werden;
allein mit diesen Templates ist keine vollständig ausfallsichere Anlage belegt.

### Weiterleitung konfigurieren und prüfen

Aktiviere in den IDM-Optionen **Externe Leistungsweiterleitung** und verwende die
erzeugte Zuordnung als Referenz. Die Weiterleitung erneuert die GLT-RAM-Werte von
sich aus in einer firmware-sicheren Kadenz: Manche Navigator-Firmwares löschen
nicht erneuerte Werte etwa zehn Sekunden nach dem letzten Schreibvorgang
(#493) — das Fallback-Intervall steuert die Anwesenheit daher nicht mehr,
lasse die Schreib-Abklingzeit auf dem Standard.
Wähle beim Batterievorzeichen **Unverändert**, weil der erzeugte Batteriehelfer
bereits normalisiert. SOC nutzt den ursprünglichen Prozentsensor und wird von
der Integration gerundet. Ordne keine E-Heizstab-Leistung zu, wenn sie nicht
unabhängig gemessen wird. Die Weiterleitung versorgt die PV-Regelung des
Navigators; lasse den separaten automatischen HA-Warmwasser-Manager für diese
Einrichtung deaktiviert. Die Zuordnungsreferenz hält diese Zuständigkeit
ausdrücklich fest.

Vergleiche alle fünf weitergeleiteten Messungen mit dem Navigator, einschließlich
Batterie-SOC und Entladung. Rücklesen vom Gerät ist aussagekräftiger als ein
optimistischer HA-Entitätswert unmittelbar nach dem Schreiben. Prüfe Laden und
Entladen, Wechselrichterausfall und Rückkehr sowie fehlende Netz-/Batteriedaten.
Die Verfügbarkeitszahl zeigt Teilsummen an. Ein kurzer erfolgreicher Test belegt
keine langfristige Zuverlässigkeit. Das Batterieanzeige-Problem #493 bei älterer
Firmware bleibt vom behobenen Abbruch laufender Übertragungen zu unterscheiden.

## Komfort-Zeitplan und schreibgeschützte Berater

Der optionale Komfort-Zeitplan kann ausgewählte Raumtemperatur-Ziele auf
konfigurierten Heizkreisen in bis zu 16 sich nicht überlappenden täglichen
Zeitfenstern schreiben. Die Mehrzeilen-Option akzeptiert
`circuit,HH:MM,HH:MM,target` pro Zeile, zum Beispiel
`a,06:00,09:00,21.0`; leer gelassen bleibt das ursprüngliche einzelne Fenster
erhalten.

Zum Beispiel mit aktivierten Heizkreisen A und D:

```text
a,06:00,09:00,21.0
a,17:00,22:00,22.0
d,22:00,05:00,20.0
```

Dies sind tägliche Fenster in der **konfigurierten Zeitzone von Home
Assistant**, nicht in der Betriebssystem-Zeitzone des Servers. Jede Endzeit
ist exklusiv; Fenster über Mitternacht werden unterstützt. Verwende schlichtes
`HH:MM` ohne Zeitzonen-Suffix und ein endliches Ziel von 15 bis 30 °C. Fenster
dürfen sich auf demselben Heizkreis nicht überlappen; verschiedene Heizkreise
dürfen parallel laufen. Wochentags- und Feiertagsregeln sind nicht Teil
dieses Zeitplaners. Das einzelne Standardfenster ist Heizkreis A,
06:00–22:00, 21 °C; es greift erst, nachdem du den Zeitplan aktivierst und
bestätigst.

Er ist standardmäßig deaktiviert und erfordert die ausdrückliche
Bestätigung, dass Home Assistant der einzige Regler für diesen Heizkreis ist.
Er stellt den vorherigen Zielwert nach dem Fenster wieder her und
überschreibt keine manuelle Änderung, die während des aktiven Zeitplans
gemacht wurde. Der vorherige Zielwert wird vor dem ersten Schreiben
gespeichert, sodass er nach einem Home-Assistant-Neustart wiederhergestellt
werden kann, wenn der geplante Wert noch vorhanden ist.

Die Auswertung läuft etwa einmal pro Minute, eine Grenze ist also kein auf
die Sekunde genauer Auslöser. In Beta 6 können ungültige aktuelle Sollwerte
keinen neuen Zeitplan scharfschalten, und ein aktiver Zeitplaner hält seinen
Sollwert im Abfrageplan, auch wenn die rohe Sollwert-Entität deaktiviert ist.
Manuelle Übersteuerungen werden respektiert, indem der beobachtete Zielwert
mit dem zuletzt geplanten Wert verglichen wird; sie sind kein
Eigentums-Schloss gegen eine andere Automation.

Der Heizkurven-Assistent und der Wetter-Vorheiz-Berater sind nur lesend. Sie
erzeugen nur Empfehlungen; sie schreiben nie einen Sollwert. Der
Heizkurven-Berater vergleicht die aktuelle Vorlauftemperatur mit dem
Heizkreis-Sollwert. Der Wetterberater fragt die Stundenvorhersage der
ausgewählten Home-Assistant-Wetter-Entität ab und meldet, wenn eine gültige
Vorhersage innerhalb von sechs Stunden unter die konfigurierte Schwelle
fällt. Ohne nutzbare Vorhersage ist er nicht verfügbar.

Diese Entitäten werden bei aktivierter Gerätshierarchie separat unter
**iDM Comfort** gruppiert.

## Optionaler iDM Health Monitor

Der **iDM Health Monitor** ist standardmäßig deaktiviert und ergänzt nur
lesende Diagnose-Entitäten. Er prüft Kommunikationsfehler, ungewöhnliche
Verdichter-Startfrequenz, ungewöhnlich niedrigen aktuellen COP, klar
verfehlte Warmwasser-Ziele, unplausible Temperaturwerte und einen
Abtauzyklus länger als 45 Minuten. Der Sensor für den Gesundheitsbericht
zeigt `ok` oder `problem` und listet aktive Prüfungen in seinen Attributen
auf. Er ändert keine Wärmepumpen-Einstellung und ersetzt keine
Techniker-Diagnose.

Die acht Prüfungen sind: Kommunikationsfehler, häufige Verdichterstarts,
niedriger momentaner COP, Warmwasser unter dem Zielwert, unplausible
Temperaturen, langer Abtauzyklus, kürzer werdende Verdichterzyklen und
wiederholte Alarmübergänge. Ein Niedrig-COP-Flag kann beim Verdichterstart
kurz erscheinen, und ein Warmwasser-unter-Ziel-Flag kann vor dem normalen
Nachheizen erscheinen. Diese Snapshot-Prüfungen belegen für sich allein noch
keinen Fehler. Der Bericht listet, welche Prüfungen aktiv sind; bei der
Interpretation des Ergebnisses müssen auch nicht verfügbare Eingangsdaten
berücksichtigt werden.

Health-Entitäten liegen bei aktivierter Gerätshierarchie in einer eigenen
Gerätegruppe **iDM Health Monitor**. Das ist nur eine diagnostische
Gruppierung und bedeutet nicht, dass die Integration die Inspektion durch
den Installateur ersetzen kann.

Die Berichtszusammenfassung kann aus den Entitäts-Attributen kopiert oder
durch Home Assistants Standard-Aktion **Diagnose herunterladen** ergänzt
werden. Dieser Export enthält ein strukturiertes `installer_report` mit
Betriebsanzahlen und -dauern, ausgewählten Temperaturen,
Fehleregister-Werten, Energie-Gesamtwerten, Health-Prüfungen und geladenen
Versionen. Er enthält bewusst keinen Host, keine PIN, keine Seriennummer und
kein anderes Verbindungsgeheimnis. Er ist ein strukturierter Schnappschuss
für den Installateur, kein Ersatz für einen Servicebericht. Er sagt
zukünftige Ausfälle nicht voraus. Eine konservative Trendprüfung vergleicht
die letzten fünf abgeschlossenen Verdichterzyklen mit fünfzehn früheren
Zyklen derselben Installation; ungewöhnlich kurze aktuelle Zyklen meldet sie
erst nach zwanzig beobachteten Zyklen. Das ist ein lokaler Anomalie-Hinweis,
keine Ausfallwahrscheinlichkeit. Die heruntergeladene Diagnose enthält die
Versionen der installierten Integration, von `idm-heatpump-api`,
`modbus-connection`, `tmodbus`, von Home Assistant und Python. Siehe
[Fehlerbehebung](Troubleshooting#smart-funktionen-und-beta-upgrades), falls
Entitäten oder Quellmesswerte fehlen.

## Experimenteller KI-Anlagenberater (geplant)

Der experimentelle Berater liefert tägliche/wöchentliche Berichte und
Erklärungen zu Gesundheit und Effizienz. Er ist standardmäßig aus und
enthält weder Werkzeuge zur Anlagensteuerung noch eine Freigabe für
Sprachassistenten. Ollama läuft lokal; v0.17.2-b10 ergänzt einzeln zu
bestätigende OpenAI- und Z.ai-Berichte mit begrenzten Anfragen. Siehe
[Einrichtung, Berichts-Aktionen, Datenabdeckung und Einschränkungen](Experimental-AI-Adviser).
