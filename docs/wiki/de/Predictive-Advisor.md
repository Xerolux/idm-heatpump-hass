# Predictive Advisor

Der Predictive Advisor ist eine strikt **lesende** Analyse- und
Empfehlungsebene für Ihre Wärmepumpe. Er beobachtet die Messdaten, lernt,
wie sich Ihre Anlage verhält, und wandelt das in nachvollziehbare
Empfehlungen — er verändert niemals selbst etwas an der Wärmepumpe.

> Die NAV10-Regelung bleibt jederzeit die führende Regelung. Der Advisor
> berät; jede Änderung an der Anlage ist Ihre bewusste Aktion über die
> regulären Steuer-Entitäten.

Der Advisor ist Teil des Profils [Smart Energy and Comfort](../Smart-Energy-and-Comfort).
Er arbeitet vollständig lokal; keine Daten verlassen Ihr Home Assistant.

## Aktivieren, deaktivieren und Voraussetzungen

- **Wo**: Integration → *Konfigurieren* → *Darstellung und zusätzliche
  Funktionen* → **Predictive Advisor aktivieren** (auch im geführten Setup
  als eigene Seite). Mit dem Profil Smart Energy & Comfort standardmäßig
  aktiv.
- **Beim Deaktivieren** werden nach einem Neuladen alle `advisor_*`-Entitäten
  entfernt; die gesammelten Statistiken bleiben erhalten und kommen zurück,
  wenn du ihn wieder aktivierst.
- **Keine KI nötig.** Alles ist deterministische Statistik — Baselines,
  Regressionen und Fenstersuche — lokal auf deinem Home Assistant berechnet.
  Es wird keine Cloud und kein LLM genutzt, benötigt oder angeboten. Der
  *Experimentelle KI-Anlagenberater* ist ein völlig separates Feature; der
  Predictive Advisor funktioniert ohne ihn.
- **Optionale Eingaben**: eine Wetter-Entität (bereits für den
  Wetter-Hinweis vorhanden), ein PV-Prognose-Sensor und ein dynamischer
  Strompreis-Sensor. Alle sind optional — fehlende Eingaben deaktivieren nur
  die betroffene Empfehlung, nichts wird erfunden.

Nach dem Einspielen eines Updates findest du einen einmaligen Hinweis unter
**Einstellungen → Reparaturen** („Neu seit 0.20.1"), der zusammenfasst, was
dazugekommen ist — dort einmal wegklicken, wenn du ihn gesehen hast. Er
erscheint **genau einmal pro installiertem Update**: nie bei einer
Neuinstallation, nie erneut nach Neustarts oder Reloads — erst wieder, wenn
das nächste Update eingespielt wird.


### Raumtemperatur ohne Raumfühler

Heizkreise ohne am Navigator angeschlossenen Raumfühler melden auf dem
`hc_x_room_temp`-Register uninitialisierten Speicher (beobachtet als
-327,33 auf einem Navigator 2.0, [#504](https://github.com/Xerolux/idm-heatpump-hass/issues/504)). Der Advisor
ignoriert solche Werte. Wenn der Predictive Advisor in den Optionen
aktiviert ist, bietet der Optionsdialog pro Heizkreis einen **nur
lesenden** Home-Assistant-Temperatursensor als Raumtemperaturquelle des
Beraters an. Es wird nichts an die Wärmepumpe geschrieben; der Sensorwert
speist Modelle, Datenqualität und Fähigkeitserkennung unter demselben
Plausibilitätsbereich (0-50 °C) wie das Register. Eine konfigurierte,
nicht verfügbare Quelle zählt als nicht verfügbares Sample - ein
Zurückfallen auf den Müllwert des Registers gibt es nicht.

## Entitäten

### Gemeinsame Auswertung und Optimierungsbewertung

Predictive Advisor, Messdatenberichte und lokaler Assist nutzen dieselbe
numerische Historie und dieselben Zeitraumvergleiche. Sie sammelt Daten, solange
Predictive Advisor oder experimenteller KI-Berater aktiviert ist; ein Modell oder
Cloud-Anbieter ist nicht nötig. Sie hält bis zu 28 Tage vor, begrenzt durch einen
separaten Speicherrahmen von 4 MiB. Älteste Details werden zuerst entfernt.
Deaktivieren/Neuladen beendet die Sammlung; gespeicherte Daten bleiben erhalten.
Es gibt keinen Recorder-Nachimport; bestehende KI-Berichte bleiben separat.

- **Advisor-Veränderungen** (`advisor_changes`) zählt geänderte Vergleichswerte.
  Attribute erläutern Energie, COP, Verdichterstarts, Warmwasser-Zeitanteil,
  Raumabweichung, Wetter und fehlende Daten. Unbekannt bedeutet: kein geeigneter
  Vergleich. Null bedeutet: keine deutliche Änderung bei vergleichbaren Fenstern.
- **Advisor-Optimierungsbewertung** (`advisor_optimization_review`) protokolliert
  gelesene Heizkurvenänderungen und bewertet die letzte stabile Änderung. Wer
  die Änderung vorgenommen hat und ob sie manuell war, lässt sich daraus nicht
  feststellen. Es wird nichts geschrieben.
- Empfehlungen enthalten übersetzte Beobachtungen, Gründe, aktuelle/vorgeschlagene
  Werte, die Bedeutung der Konfidenz, fehlende Daten und eine erste Prüfung.
  Die Konfidenz ist keine Wahrscheinlichkeit für einen Defekt.
- Seit 0.27.0-b1 sind auch die **Titel der Empfehlungen übersetzt**: Sensor-Attribute
  und das lokale Assist geben sie deutsch oder englisch passend zur
  Home-Assistant-Sprache aus, mit deutschen Dezimalkommas. Das Feld `title` selbst
  bleibt der dokumentierte englische Datenbestandteil — Events, gespeicherte
  Einträge und Diagnosen bleiben sprachunabhängig; vor dem Update gespeicherte
  Empfehlungen funktionieren weiter und zeigen ihren gespeicherten Titel.
- Ein neu generiertes Anlagen-Dashboard ergänzt die vorhandenen Advisor-Entitäten
  und Erklärungskarten. Bestehende Dashboards werden nicht automatisch geändert.

Für die Bewertung sind 72 Stunden davor und 72 Stunden nach sechs Stunden
Beruhigungszeit nötig. Beide Fenster benötigen mindestens 80 % erfasste
Energie-Zählerintervalle. Verglichen werden ausschließlich Heizintervalle in
Außentemperaturbereichen von zwei Grad. Mindestens sechs gemeinsame Heizstunden
und 60 % Übereinstimmung bezogen auf die größere Heizhistorie sind nötig.
Geänderte Raumsollwerte, fehlende Komfortdaten oder überlagerte Änderungen
lassen die Wirkung offen. Ab 5 % COP-Unterschied wird eine beobachtete Änderung
ausgewiesen. Eine um mehr als 0,3 K schlechtere absolute Raumabweichung oder mehr
Starts um sowohl 0,2 pro Stunde als auch 20 % verhindern ein einfaches positives
Urteil. Das sind beschreibende Schwellen, keine statistische Signifikanz oder
Ursachenbeweise. Einflüsse wie Nutzung und Sonneneinstrahlung bleiben unbekannt.

Assist-Beispiele: **Was hat sich verändert?**, **Warum ist der Verbrauch heute
höher?**, **Wie entwickelt sich die Taktung?**, **Welche Daten fehlen noch?**,
**Hat die Änderung geholfen?**. Die letzte Frage bewertet die zuletzt erfasste
Heizkurvenänderung; sie ändert keine Einstellung und bestätigt keine Empfehlung
als umgesetzt.

Zugeordnete Raumsensoren werden vor Qualitätsprüfung und Modellberechnung von
Fahrenheit oder Kelvin in Celsius umgerechnet. Ohne Einheit bleibt die Annahme
Celsius bestehen. Nicht verfügbare oder falsch zugeordnete Quellen werden nicht
durch Registerwerte ersetzt. Fehlgeschlagene Aktualisierungen unterbrechen
Lernintervalle. Nur eindeutiger Heiz- oder Warmwasserbetrieb zählt für den
jeweiligen COP-Bereich.

Bei Laufgründen hat eine ausdrückliche Anforderung der Regelung Vorrang vor
Temperaturvermutungen. Ein kühler Warmwasserspeicher überschreibt keinen
gemeldeten Heizbetrieb; ein Speicher oberhalb des Sollwerts wird so beschrieben.

Der Wärmebedarf für 24 Stunden benötigt 24 unterschiedliche, aufeinanderfolgende
Prognosestunden. Kurze oder lückenhafte Prognosen liefern keinen Tageswert.
Warme Stunden heben den Heizbedarf kalter Stunden nicht auf. PV-Periodenenergie
wird an Stundengrenzen aufgeteilt; doppelte Zeitpunkte zählen einmal.
PV-Empfehlungen beschreiben erwartete Erzeugung, keinen bestätigten Überschuss
nach Abzug des Hausverbrauchs.

Der lokale Assist verwendet die korrigierten Laufgründe. Er berücksichtigt
negative Außentemperaturen, benennt den momentanen COP ausdrücklich und
bestätigt ohne lesbare Störungswerte keine Fehlerfreiheit. Nach fehlgeschlagenen
Aktualisierungen erklärt er die fehlende Beurteilbarkeit statt alte Werte als
aktuell auszugeben.

Alle Entitäten erscheinen mit dem Smart-Profil und werden bedeutsam, sobald
der Advisor Daten gesammelt hat. Sensoren, deren Modelle noch nicht gelernt
sind, bleiben stattdessen nicht verfügbar — sie raten nie.

| Entität | Bedeutung |
|---|---|
| `sensor.<Gerät>_advisor_status` | Beobachtungsstufe: **Sammelt Daten** (Tag 1), **Erste Hinweise** (Tag 1–7), **Empfehlungen aktiv** (ab Tag 7), **Basis etabliert** (ab Tag 30). Die Attribute zeigen erkannte Anlagenfähigkeiten, Datenqualität und die aktuelle Konfidenz |
| `sensor.<Gerät>_advisor_recommendations` | Anzahl aktiver Empfehlungen; jede wird mit vollständiger Erklärung (Gründe, Werte, Konfidenz) als Attribut veröffentlicht |
| `sensor.<Gerät>_advisor_confidence` | Konfidenz des Advisors in Prozent mit Stufe |
| `sensor.<Gerät>_advisor_operation_reason` | Warum die Wärmepumpe gerade läuft (PV-Überschuss, Warmwasser, anfordernder Heizkreis, Anforderungsgrund der Regelung) — mit den Zahlen dahinter |
| `binary_sensor.<Gerät>_advisor_anomaly_detected` | An, solange eine Anomalie-Empfehlung aktiv ist |
| `sensor.<Gerät>_advisor_health_score` | Anlagenzustand 0–100 aus dokumentierten Komponenten (Hydraulik, Verdichter, Warmwasser, Effizienz); jede Komponente existiert nur mit Baseline-Daten |
| `sensor.<Gerät>_advisor_expected_cop` / `advisor_efficiency_score` | COP, den die gelernte Außentemperatur/Vorlauf-Karte am aktuellen Betriebspunkt erwartet, und wie der beobachtete 7-Tage-**Heiz**-COP dagegensteht (der beobachtete Warmwasser-COP desselben Fensters ist als Attribut veröffentlicht; gemischte oder Abtau-Intervalle fließen in keinen der Modus-Werte) |
| `sensor.<Gerät>_advisor_building_heat_loss` | Gebäude-Wärmeverlust in W/K aus der Wärmeleistungs-Regression |
| `sensor.<Gerät>_advisor_building_thermal_inertia` | Effektive Wärmekapazität (kWh/K) aus beobachteten Abkühl-Episoden |
| `sensor.<Gerät>_advisor_optimal_flow_temp` | Vorlauftemperatur, die die gelernte Kurve bei der aktuellen Außentemperatur erzeugt hat, während die Räume im Soll lagen |
| `sensor.<Gerät>_advisor_hc_X_curve_recommendation` | Heizkurven-Empfehlung je Heizkreis — höchstens ein dokumentierter 0,02-Schritt pro Empfehlung, erst nach 7 Baseline-Tagen Raumtemperatur-Abweichung |
| `sensor.<Gerät>_advisor_dhw_recommendation` | Bestes Warmwasser-Ladefenster aus der PV-Prognose (bevorzugt) oder den günstigsten Wärmekosten (Preis ÷ erwarteter COP — den beobachteten 7-Tage-Warmwasser-COP, sobald vorhanden). Die Fensterzeiten erscheinen in deiner Home-Assistant-Zeitzone; die gespeicherten Zeitstempel bleiben UTC |
| `sensor.<Gerät>_advisor_predicted_heat_demand` | Prognostizierter Wärmebedarf der nächsten 24 Stunden (Wärmeverlust × prognostizierte Temperaturdifferenz) |
| `sensor.<Gerät>_advisor_next_24h` | Der kombinierte Plan: erwartete PV, teure Stunden und eine Konfliktwarnung, wenn das Warmwasser-Fenster darin liegt |
| `binary_sensor.<Gerät>_advisor_optimization_available` | An, solange mindestens eine unbearbeitete Empfehlung aktiv ist |

### Woher die externen Eingaben kommen

- **Wetter**: die bestehende Option *Wetter-Entität* (stündliche Prognose
  über `weather.get_forecasts`).
- **PV-Prognose**: optionaler Sensor in den Optionen
  (*PV-Prognose-Sensor für den Predictive Advisor (optional)*). Das Feld
  darf leer gelassen werden — der Advisor funktioniert auch ohne; der
  Sensor ist nur die Grundlage für die PV-basierten
  Warmwasser-Zeitfenster-Empfehlungen. PVForecast-Attribute
  (`detailed_forecast`) und Solcast-Listen (`forecast`) werden verstanden,
  und ein Sensor der Core-Integration **Forecast.Solar** wird über deren
  `get_forecast`-Service gelesen (stündliches `wh_period`) — ihre eigenen
  Sensoren tragen keine stündlichen Attribute.
- **Strompreis**: die bestehende Option *Dynamischer Strompreis-Sensor*;
  zukünftige Stundenpreise werden aus üblichen Attribut-Formen
  (`today`/`tomorrow`/`data`/`prices`-Listen) gelesen.

Fehlende oder nicht auswertbare Eingaben lassen die betroffene Empfehlung
weg — der Advisor fällt nie auf erfundene Zahlen zurück.

### Ereignisse

Jede neue, geänderte oder bestätigte Empfehlung feuert ein
`idm_advisor_recommendation`-Ereignis, das Sie in Automationen nutzen
können:

```yaml
event_type: idm_advisor_recommendation
data:
  action: new          # new | updated | status
  id: heating_curve_a_20261007
  category: heating_curve
  severity: info
  confidence: 0.91
  confidence_level: very_high
  current_value: 0.35
  recommended_value: 0.32
  reasons:
    - room_temperature_above_target
    - flow_temperature_above_estimated_requirement
```

### Wie die Konfidenz entsteht

Jede Empfehlung trägt einen Konfidenzwert mit vier Stufen — niedrig, mittel,
hoch, sehr hoch — statt pseudo-genauer Prozente. Der Wert ist eine
dokumentierte Formel: 60 % Beobachtungsabdeckung (vollständig nach 14 Tagen)
plus 40 % Anteil nutzbarer Messwerte. Schlechte Daten (nicht verfügbare,
unplausible oder eingefrorene Sensoren) senken die Konfidenz, statt
Empfehlungen zu erzeugen.

### Datenqualität

Bevor irgendetwas analysiert wird, wird jede Eingabe Probe für Probe
klassifiziert: nicht verfügbar, unplausibel (außerhalb des dokumentierten
Bereichs), eingefroren (ein von Null verschiedener Leistungs- oder
Durchflusswert, der sich drei Stunden nicht bewegt hat) oder nutzbar.
Empfehlungen werden nie aus schlechten Daten gebaut.

### Lernen des Gebäudemodells

Wärmeverlust und optimale Vorlauftemperatur lernen nur im reinen Heizbetrieb
(`hp_operating_mode == 1`) mit einem aktiv heizenden Heizkreis. Eine vorhandene
aktive Heizkreisbetriebsart muss Heizen melden; fehlt sie, ist ein positiver
Vorlaufsollwert erforderlich. Warmwasser, Kühlen, Abtauen, gemischte oder
unbekannte Betriebsarten und inaktive Heizkreise liefern keine Regressionsdaten.
Die Wärmeverlustberechnung nutzt die Raumtemperatur eines aktiven Heizkreises.
Allgemeine Betriebswerte und COP-Lernen laufen unabhängig davon weiter.

Beim Update von der bisherigen Lernlogik beginnen Wärmeverlust, Vorlaufkurve
und die daraus abgeleitete Wärmekapazität einmal neu: Alte Summendaten lassen
sich nicht nach Heizen und Warmwasser trennen. Diese Sensoren bleiben bis zu
ausreichend neuen Heizproben nicht verfügbar. Andere Analysen einschließlich
Tagesreferenzen, COP-Daten und Abkühlbeobachtungen bleiben erhalten.

## Was der Advisor niemals tun wird

- Sollwerte, Heizkurven, Betriebsarten, Zeitprogramme oder Leistungsgrenzen verändern
- PV-Boost oder Vorrangladung selbst aktivieren
- Register, Coils oder Web-Einstellungen schreiben
- Eine Empfehlung ohne Ihre explizite Bestätigung „anwenden“

Das Annehmen einer Empfehlung in einer künftigen Oberfläche hält nur fest,
dass Sie sie für sinnvoll halten. Das Anwenden eines Wertes bleibt eine
separate, bestätigte Benutzeraktion, bei der der vorherige Wert
protokolliert wird, damit er wiederhergestellt werden kann.
