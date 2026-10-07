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

## Entitäten

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
| `sensor.<Gerät>_advisor_expected_cop` / `advisor_efficiency_score` | COP, den die gelernte Außentemperatur/Vorlauf-Karte am aktuellen Betriebspunkt erwartet, und wie der beobachtete 7-Tage-COP dagegensteht |
| `sensor.<Gerät>_advisor_building_heat_loss` | Gebäude-Wärmeverlust in W/K aus der Wärmeleistungs-Regression |
| `sensor.<Gerät>_advisor_building_thermal_inertia` | Effektive Wärmekapazität (kWh/K) aus beobachteten Abkühl-Episoden |
| `sensor.<Gerät>_advisor_optimal_flow_temp` | Vorlauftemperatur, die die gelernte Kurve bei der aktuellen Außentemperatur erzeugt hat, während die Räume im Soll lagen |
| `sensor.<Gerät>_advisor_hc_X_curve_recommendation` | Heizkurven-Empfehlung je Heizkreis — höchstens ein dokumentierter 0,02-Schritt pro Empfehlung, erst nach 7 Baseline-Tagen Raumtemperatur-Abweichung |
| `sensor.<Gerät>_advisor_dhw_recommendation` | Bestes Warmwasser-Ladefenster aus der PV-Prognose (bevorzugt) oder den günstigsten Wärmekosten (Preis ÷ erwarteter COP) |
| `sensor.<Gerät>_advisor_predicted_heat_demand` | Prognostizierter Wärmebedarf der nächsten 24 Stunden (Wärmeverlust × prognostizierte Temperaturdifferenz) |
| `sensor.<Gerät>_advisor_next_24h` | Der kombinierte Plan: erwartete PV, teure Stunden und eine Konfliktwarnung, wenn das Warmwasser-Fenster darin liegt |
| `binary_sensor.<Gerät>_advisor_optimization_available` | An, solange mindestens eine unbearbeitete Empfehlung aktiv ist |

### Woher die externen Eingaben kommen

- **Wetter**: die bestehende Option *Wetter-Entität* (stündliche Prognose
  über `weather.get_forecasts`).
- **PV-Prognose**: optionaler Sensor in den Optionen
  (*PV-Prognose-Sensor für den Predictive Advisor*); PVForecast-Attribute
  (`detailed_forecast`) und Solcast-Listen (`forecast`) werden verstanden.
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

## Was der Advisor niemals tun wird

- Sollwerte, Heizkurven, Betriebsarten, Zeitprogramme oder Leistungsgrenzen verändern
- PV-Boost oder Vorrangladung selbst aktivieren
- Register, Coils oder Web-Einstellungen schreiben
- Eine Empfehlung ohne Ihre explizite Bestätigung „anwenden“

Das Annehmen einer Empfehlung in einer künftigen Oberfläche hält nur fest,
dass Sie sie für sinnvoll halten. Das Anwenden eines Wertes bleibt eine
separate, bestätigte Benutzeraktion, bei der der vorherige Wert
protokolliert wird, damit er wiederhergestellt werden kann.
