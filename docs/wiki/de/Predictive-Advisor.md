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

## Was Phase 1 liefert

Die erste Phase legt das Fundament und beginnt mit der Datensammlung. Nach
dem Aktivieren des Smart-Profils sehen Sie:

| Entität | Bedeutung |
|---|---|
| `sensor.<Gerät>_advisor_status` | Beobachtungsstufe: **Sammelt Daten** (Tag 1), **Erste Hinweise** (Tag 1–7), **Empfehlungen aktiv** (ab Tag 7), **Basis etabliert** (ab Tag 30). Die Attribute zeigen erkannte Anlagenfähigkeiten, Datenqualität und die aktuelle Konfidenz |
| `sensor.<Gerät>_advisor_recommendations` | Anzahl aktiver Empfehlungen; jede wird mit vollständiger Erklärung (Gründe, Werte, Konfidenz) als Attribut veröffentlicht |
| `binary_sensor.<Gerät>_advisor_optimization_available` | An, solange mindestens eine unbearbeitete Empfehlung aktiv ist |

Die Empfehlungen selbst kommen mit den späteren Phasen (Heizkurve,
Warmwasser, PV, Strompreis, 24-Stunden-Plan — siehe Roadmap in
`docs/dev/predictive-advisor-roadmap.md`). Bis dahin melden die Sensoren
ehrlich, dass der Advisor noch sammelt.

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
