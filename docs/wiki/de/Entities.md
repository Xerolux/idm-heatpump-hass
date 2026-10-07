# Entitäten

## Entitäten der Smart-Funktionen

Das optionale [Smart Energy & Comfort](Smart-Energy-and-Comfort)-Profil ergänzt elektrische und thermische Energiezähler für Gesamtlaufzeit, Tag und Monat, COP für dieselben Zeiträume, geschätzte Kosten, CO₂ und optionale PV-Nutzung sowie die Verdichterzyklus- und Betriebsanalyse. Es handelt sich um abgeleitete Werte, nicht um zusätzliche physische Zähler. Die erforderlichen Leistungsregister müssen verfügbar sein.

Der Health Monitor ergänzt acht Prüfungen auf Probleme und einen Berichtssensor. Heizkurven- und Wetterberater ergänzen schreibgeschützte Empfehlungen. Der [Predictive Advisor](Predictive-Advisor) ergänzt ein strikt schreibgeschütztes Empfehlungs-Framework (Status, Empfehlungen, Datenqualität). Der optionale Komfort-Zeitplan verändert den bestehenden Raum-Sollwert des Heizkreises; er erzeugt keine zweite Klima-Regelentität. Das automatische Warmwasserladen nutzt die bestehenden Boost-Bedienelemente und die bestehende Zustandsmaschine.

Mit aktivierter Gerätehierarchie separieren **iDM Analytics**, **iDM Health Monitor**, **iDM Comfort** und **Diagnose** diese Funktionen von den Regler-Entitäten. Wird eine optionale Funktion deaktiviert, werden ihre Entitätsregistrierungen entfernt; beim erneuten Aktivieren werden dieselben IDs wiederhergestellt. Bestehende Regler-IDs bleiben erhalten.

Die Integration erzeugt Entitäten dynamisch auf Grundlage deiner Wärmepumpen-Konfiguration (Heizkreise, Zonen, optionale Funktionen).

## Entitäts-Plattformen

| Plattform | Anzahl | Beschreibung |
|----------|-------|-------------|
| **Sensor** | modellabhängig | Temperaturen, Drücke, Durchflussmengen, Energie, PV, Solar, Kaskade, Booster, Laufzeitversionen, Diagnose |
| **Binärsensor** | modellabhängig | Störalarme, Verdichterstatus, Heiz-/Kühl-/Warmwasseranforderung, Web-Zustände |
| **Zahl-Entität** | modellabhängig | Schreibbare Sollwerte, Temperaturgrenzen, GLT-Parameter, Leistungsgrenzen |
| **Auswahl-Entität** | modellabhängig | Systembetriebsart, Heizkreis-Modi, Solarbetriebsart, ISC-Modus |
| **Schalter-Entität** | modellabhängig | Externe Heiz-/Kühl-/Warmwasseranforderung, einmalige Warmwasserladung |
| **Klima-Entität** | pro Heizkreis + Zonenraum | Heiz-/Kühlmodus + Zieltemperatur für Heizkreise und Zonenmodul-Räume |
| **Warmwasserbereiter** | 1 | Warmwasser-Zieltemperatur mit Ist-Temperatur-Rückmeldung |
| **Button** | 1 | Quittiert aktive Fehler an der Wärmepumpe |

Die genauen Zahlen hängen vom erkannten Modell, den aktiven Heizkreisen, Zonen, Räumen und optionalen Funktionen ab. Das Hinzufügen von Heizkreisen, Zonen, Kaskade, Fachmann-Codes oder Web-Supplement-Daten kann zusätzliche Entitäten hinzufügen.

Entitäten werden in Home Assistant, wo möglich, nach Funktion gruppiert. Die optionalen Fachmann-Code-Sensoren stehen oben angeheftet, gefolgt von Konfigurations-Entitäten, Schaltern, schreibbaren Werten, Live-Messwerten und Diagnose.

## Entitätsnamen und Sprachen

Entitätsnamen stammen aus den Übersetzungsdateien der Integration und folgen der in Home Assistant eingestellten Sprache: Eine englische Installation zeigt englische Namen, eine deutsche zeigt die deutschen Namen, die die Integration schon immer verwendet hat. Heizkreise und Zonenräume teilen sich jeweils einen Namen pro Messwert und ergänzen den Heizkreisbuchstaben oder die Zonen-/Raumnummer, zum Beispiel *Heizkreis A Vorlauftemperatur* und *Zone 1 Raum 2 Temperatur*.

Das Ändern der Home-Assistant-Sprache ändert nur die angezeigten Namen. Entitäts-IDs und Unique-IDs bleiben exakt, wie sie sind, sodass Dashboards, Automationen und Langzeitstatistiken weiter funktionieren. Eine Entität, die *nach* einem Sprachwechsel erstellt wird, leitet ihre Entitäts-ID vom Namen in dieser Sprache ab — wie bei jeder Home-Assistant-Integration.

---

## Sensoren

### Laufzeit-Diagnose

| Entität | Zustand | Attribute | Kategorie |
|--------|-------|------------|----------|
| IDM Heatpump API-Version | Installierte `idm-heatpump-api`-Version | `integration_version`, `modbus_connection_version`, `tmodbus_version`, `home_assistant_version`, `python_version` | Diagnose |

Dieser Sensor bleibt auch dann verfügbar, wenn die Abfrage der Wärmepumpe fehlschlägt, was ihn beim Zusammenstellen von Informationen für einen Fehlerbericht nützlich macht. Die direkte Socket-Laufzeit wird über die Attribute `modbus_connection_version` und `tmodbus_version` identifiziert.

### Zugangscodes der Fachmann-Ebene

Wenn die Option in den Integrationsoptionen aktiviert ist, zeigen zwei zusätzliche Sensoren die aktuellen Zugangscodes für *Fachmann Ebene 1* und *Fachmann Ebene 2*. Sie aktualisieren sich einmal pro Minute, stehen oben in der Entitätsliste des IDM-Geräts und sind keine Modbus-Register.

Die Option ist standardmäßig deaktiviert. Behandle die Werte als sensibel: beschränke den Zugriff auf ihre Dashboard-Karten und veröffentliche sie niemals in Screenshots, Logs oder Supportanfragen. Siehe [Konfiguration](Configuration#codes-fur-die-fachmann-ebene) für Einrichtung und Sicherheitshinweise. Die Berechnungsmethode ist bewusst nicht dokumentiert.

### Systemtemperaturen & Drücke

| Entität | Register | Einheit |
|--------|----------|------|
| Außentemperatur | 1000 | °C |
| Gemittelte Außentemperatur | 1002 | °C |
| Wärmespeichertemperatur | 1008 | °C |
| Kältespeichertemperatur | 1010 | °C |
| Warmwasser unten | 1012 | °C |
| Warmwasser oben | 1014 | °C |
| Wärmepumpen Vorlauftemperatur | 1050 | °C |
| Wärmepumpen Rücklauftemperatur | 1052 | °C |
| HGL Vorlauftemperatur | 1054 | °C |
| Wärmequelleneintritt/-austritt | 1056/1058 | °C |
| Luftansaugtemperaturen | 1060/1064 | °C |
| Luftwärmetauscher Temperatur | 1062 | °C |

### Navigator 10 — Wärmesenke (Trennwärmetauscher)

| Entität | Register | Einheit |
|--------|----------|------|
| Rücklauftemperatur Wärmesenke (B124) | 1068 | °C |
| Vorlauftemperatur Wärmesenke (B125) | 1070 | °C |
| Durchfluss Wärmesenke (B2) | 1072 | l/min |
| Ladepumpe Wärmesenke (M73) | 1074 | % |

### Verdichter & Pumpen

| Entität | Register |
|--------|----------|
| Verdichter 1–4 | 1100–1103 |
| Ladepumpe M73 | 1104 |
| Sole-/Zwischenkreispumpe (M16) | 1105 |
| Wärmequellenpumpe M15 | 1106 |
| ISC Kältespeicherpumpe M84 | 1108 |
| ISC Rückkühlpumpe M17 | 1109 |
| Zirkulationspumpe M64 | 1118 |

### Energie & Leistung

| Entität | Register | Einheit |
|--------|----------|------|
| Wärmemenge Heizen | 1748 | kWh |
| Wärmemenge Gesamt | 1750 | kWh |
| Wärmemenge Kühlen | 1752 | kWh |
| Wärmemenge Warmwasser | 1754 | kWh |
| Wärmemenge Abtauen | 1756 | kWh |
| Wärmemenge Passive Kühlung | 1758 | kWh |
| Wärmemenge Solar | 1760 | kWh |
| Wärmemenge E-Heizstab | 1762 | kWh |
| Momentanleistung | 1790 | kW |
| Aktuelle Solarleistung | 1792 | kW |
| Elektrische Leistungsaufnahme Wärmepumpe | 4122 | kW |
| Thermische Leistung | 4126 | kW |

### PV / Energiemanagement

| Entität | Register | Datentyp | Einheit |
|--------|----------|----------|------|
| PV Überschuss | 74 | FLOAT, wortvertauscht | kW |
| E-Heizstab Leistung | 76 | FLOAT, wortvertauscht | kW |
| PV Produktion | 78 | FLOAT, wortvertauscht | kW |
| Hausverbrauch | 82 | FLOAT, wortvertauscht | kW |
| Batterie Entladung | 84 | FLOAT, wortvertauscht | kW |
| Batterie SOC | 86 | signed INT16, ein Register | % |

Der Batterie SOC akzeptiert `0–100`; `-1` bedeutet, dass kein Batteriewert vorliegt. Wer Adresse 86 wie die umgebenden FLOAT-Werte über zwei Register behandelt, erhält ein unplausibles Ergebnis.

#### PV-Überschussbetrieb (abgeleitete Diagnose)

Die Navigator-Regler legen kein internes Statusregister „PV-Überschussladen aktiv“ offen — der gesamte PV-Block (74–88) besteht aus GLT-Messeingängen, die ein externer Energiemanager beschreibt. Die Integration stellt deshalb den abgeleiteten diagnostischen Binärsensor **PV-Überschussbetrieb** (`calculated_pv_surplus_operation`, Issue #353) bereit. Er ist `on`, wenn beide Hälften des Zustands zutreffen:

1. Dem Regler wird aktuell Überschuss signalisiert: `pv_surplus` (Register 74)
   ≥ 0,05 kW **oder** das SG-Ready-Signal `smart_grid_status` (Register 90)
   meldet *Supergreen*.
2. Die Wärmepumpe zieht tatsächlich elektrische Leistung:
   `power_consumption_hp` (Register 4122) ≥ 0,05 kW, mit Rückfall auf
   `hp_operating_mode` (Register 1090) ≠ *Aus* bei Anlagen ohne die
   Nav-10-Leistungsmessung.

Die Entität wird nur erzeugt, wenn an der erkannten Anlage mindestens eine Quelle pro Hälfte existiert; Schwellenwerte und die aktuell aktiven Quellen werden als Attribute offengelegt. Hinweis für Anlagen, bei denen der Überschuss hinter dem Abzweig der Wärmepumpe gemessen wird: `pv_surplus` fällt gegen null, solange die Wärmepumpe den Überschuss aufnimmt, mit dem sie versorgt wird — dort bleibt das SG-Ready-Signal (oder `pv_production`) der verlässliche Indikator, und die SG-Ready-Quelle hält die Diagnose aussagekräftig.

### Solarthermie

| Entität | Register | Einheit |
|--------|----------|------|
| Solar Kollektortemperatur | 1850 | °C |
| Solar Rücklauftemperatur | 1852 | °C |
| Solar Ladetemperatur | 1854 | °C |
| Solar WQ-Referenz / Pooltemperatur | 1857 | °C |

Diese Entitäten existieren nur, solange die Option **Solaranlage** aktiviert ist (Standard). Anlagen ohne Kollektoren können die Option in den Einstellungen der Integration abschalten: Die Solarregister verlassen die Abfrage, und die leere Gerätegruppe *Solaranlage* verschwindet nach einem Neuladen. Erneutes Aktivieren stellt die Entitäten mit ihren bisherigen IDs wieder her.

Die Integration bemerkt es auch von selbst: Wenn jedes Solarregister einen ganzen Tag lang „nicht konfiguriert“ meldet, bietet ein Reparaturvorschlag an, das Modul abzuschalten (oder zu behalten, was diese Runde des Vorschlags verwirft).

### ISC (Intelligent Surface Cooling)

| Entität | Register | Einheit |
|--------|----------|------|
| ISC Ladetemperatur Kühlen | 1870 | °C |
| ISC Rückkühltemperatur | 1872 | °C |

### Booster A/B (2. Wärmeerzeuger)

| Entität | Register |
|--------|----------|
| Booster Störung | 4001 |
| Booster Verriegelung | 4002 |
| Booster A: Temperaturen Wärmequellen-Ein-/Austritt, Speicher, Vorlauf, Rücklauf | 4010–4018 |
| Booster A: Wärmequellenpumpe, Ladepumpe, Verdichter | 4020–4022 |
| Booster B: entsprechende Register | 4040–4052 |

### Kaskade (mehrere Wärmepumpen)

| Entität | Register |
|--------|----------|
| Kaskade verfügbar Heizen/Kühlen/Warmwasser | 1147–1149 |
| Kaskade in Betrieb Heizen/Kühlen/Warmwasser | 1150–1152 |
| Kaskade angeforderte Temperaturen (Heizen/Kühlen/Warmwasser) | 1200–1204 |
| Kaskade gemittelte Vorlauftemperaturen | 1206–1210 |
| Kaskade Min-/Max-Leistung | 1220–1225 |
| Kaskade Bivalenz-Einstellungen | 1226–1231 |

### Heizkreis-Sensoren (pro Heizkreis A–G)

| Entität | Beschreibung |
|--------|-------------|
| `hc_{x}_flow_temp` | Vorlauftemperatur |
| `hc_{x}_room_temp` | Raumtemperatur |
| `hc_{x}_setpoint_flow_temp` | Aktueller Vorlauf-Sollwert |
| `hc_{x}_active_mode` | Aktiver Betriebsmodus |

### Berechnete Sensoren

Diese Sensoren werden aus Registerwerten desselben Schnappschusses abgeleitet. Nichts wird geschätzt: Jeder Operand ist ein dekodierter Registerwert, und der Sensor meldet lieber gar keinen Wert als eine Vermutung, wenn seine Quellen nicht aussagekräftig sind.

| Entität | Beschreibung |
|--------|-------------|
| `calculated_hp_temperature_delta` | Spreizung der Wärmepumpe (Vorlauf minus Rücklauf) |
| `calculated_heat_source_temperature_delta` | Spreizung der Wärmequelle (Eintritt minus Austritt) |
| `calculated_dhw_setpoint_deviation` | Warmwasser Ist minus Soll |
| `calculated_cop` | Momentaner COP (thermische Leistung / elektrische Leistung) |
| `calculated_hc_{x}_flow_deviation` | Vorlauf-Abweichung je Heizkreis |

Die **Vorlauf-Abweichung je Heizkreis** vergleicht die gemessene Vorlauftemperatur eines Heizkreises (`hc_{x}_flow_temp`) mit dem Vorlauf-Sollwert, den der Regler für diesen Heizkreis aktuell anfordert (`hc_{x}_setpoint_flow_temp`):

- **Positiv** — der Heizkreis läuft über dem angeforderten Sollwert (Zuvielregelung, typischerweise eine zu hoch eingestellte Heizkurve oder ein Mischer, der zu weit öffnet).
- **Um null** — der Heizkreis folgt seiner Heizkurve.
- **Negativ** — der Heizkreis erreicht seinen Sollwert nicht (unterdimensionierte Wärmequelle, hohe Last, Abtauen oder eine begrenzende Einstellung).

Der Sensor wird **nicht verfügbar**, während der Heizkreis ruht (der Regler meldet `0.0`), und bei nicht konfigurierten Heizkreisen (`-1.0`). Das ist beabsichtigt: Eine Abweichung, die aus einem Platzhalterwert berechnet würde, wäre bedeutungslos. Die Entität selbst wird erzeugt, sobald beide Register existieren, sodass ein Home-Assistant-Neustart im Standby sie nicht verschwinden lässt.

> Hier werden bewusst Werte **innerhalb eines Heizkreises** verglichen. Eine Abweichung auf Wärmepumpen-Ebene bräuchte ein eindeutiges Register für den Vorlauf-Sollwert, den die Wärmepumpe selbst anfordert, und bleibt ein offener Punkt auf der Roadmap.

### Optionale Web-Supplement-Sensoren

Wenn **Web-Supplement-Daten** aktiviert sind und eine lokale Navigator-Web-PIN konfiguriert ist, ergänzt die Integration schreibgeschützte Diagnosesensoren aus der lokalen Web-API. Diese Sensoren sind rein ergänzend; die Modbus-Entitäten bleiben die primäre Datenquelle.

Typische reine Web-Sensoren sind unter anderem:

| Entität | Beschreibung |
|--------|-------------|
| Navigator-Version (Web) | Erkannte Navigator-Generation, zum Beispiel Navigator 2.0 oder Navigator 10; trägt das Wärmepumpenmodell als Attribut, wo die Firmware es meldet |
| Software-Version (Web) | Software-Version des Reglers, gemeldet von der lokalen Weboberfläche |
| myIDM-ID (Web) | Kompakte myIDM-ID, abgeleitet aus dem lokalen Web-Kontowert vor dem `@` |
| Anzahl Infosystem-Meldungen (Web) | Anzahl aktiver Navigator-10-Infosystem-Meldungen |
| Anforderungsgrund (Web) | Nur Navigator 10: der vom Regler selbst gemeldete Anforderungsgrund (Issue #353) |

Das Wärmepumpenmodell ist bewusst keine eigene Entität: Die Navigator-10-
Firmware 20.24-1580 (ab 29.09.2026 installiert) hat die Modell-Zeile aus der
Sensor-Seite entfernt, und kein anderes zugängliches Web-Frame meldet das
Modell — live am Regler verifiziert; eine Entität würde auf aktueller
Firmware dauerhaft nicht verfügbar sein. Wo eine Firmware die Zeile noch
liefert (Navigator-2.0-Web, ältere Navigator-10-Firmware), erscheint der Wert
als `heatpump_model`-Attribut am Sensor *Navigator-Version (Web)*.

#### Anforderungsgrund aus der Weboberfläche (nur Navigator 10)

Die Navigator-Regler legen über Modbus kein internes Statusregister für den PV-Modus offen, aber die Weboberfläche des Navigator 10 rendert den „Anforderungsgrund“ der Anzeige — einschließlich **PV** — aus einer Bitmaske im WebSocket-Frame `home/detail`. Ist das Web-Supplement auf einem Navigator 10 aktiv, wertet die Integration diesen Frame bei jeder Web-Abfrage aus und stellt bereit:

- **Anforderungsgrund (Web)** (`web_demand_reason`): der lesbare Anforderungsgrund, formuliert wie die Anzeige des Reglers selbst — zum Beispiel *PV*, *Heizkreis A*, *Zeitprogramm*, *Mehrere Anforderungen*, *Keine Anforderung* oder *Aus* — mit den rohen `operationMode`/`info`-Werten aller beitragenden Widgets als Attribute.
- **PV-Anforderungsgrund (Web)** (`web_demand_reason_pv`): Binärsensor, der `on` ist, solange der Regler selbst PV als Anforderungsgrund meldet (Bit 32), sowohl in der Tabelle der Heiz- als auch der Warmwasser-Anforderungsgründe.

Dies ist das vom Gerät gemeldete Gegenstück zur abgeleiteten Diagnose [`calculated_pv_surplus_operation`](#pv-uberschussbetrieb-abgeleitete-diagnose): Die Web-Entität bildet ab, was der Regler entschieden hat, die Modbus-Entität funktioniert ohne Web-PIN. Auf dem Navigator 2.0 (andere, PHP-basierte Weboberfläche) steht nur die abgeleitete Modbus-Entität zur Verfügung.

Mit aktivierter **Gerätehierarchie** teilen sich alle PV-Entitäten — die PV-Register (`pv_surplus`, `pv_production`, `pv_target_value`), `smart_grid_status`, die abgeleitete Diagnose und die beiden Web-Entitäten — das dedizierte Untergerät **Photovoltaik** statt des Hauptgeräts.
| Infosystem-Meldungen (Web) | Zusammenfassung aktiver Navigator-10-Infosystem-Meldungen |
| Heißgastemperatur (Web) | Reine Web-Diagnosetemperatur, wenn verfügbar |
| Verdampferdruck (Web) | Reiner Web-Wert des Kältemitteldrucks, wenn verfügbar |
| Platinentemperatur (Web) | Temperatur der Reglerplatine, wenn verfügbar |
| Momentane/prognostizierte Leistung Heizen / Kühlen / Warmwasser (Web) | Die aktuelle **oder prognostizierte** thermische Leistung des Reglers für diesen Modus |

#### „Momentane/prognostizierte Leistung“ ist keine Live-Messung

Der Navigator bezeichnet diese drei Werte als `mom./prog. Leistung Heizen`, `mom./prog. Leistung Kühlen` und `mom./prog. Leistung Vorrang` — *momentane bzw. prognostizierte* Leistung. Sie melden, was der Regler für diesen Modus aktuell zu liefern erwartet; ein Wert ungleich null bei ausgeschaltetem Heizen oder Kühlen ist deshalb normal und kein Fehler. Ein Wert, der sich ändert, während der Verdichter ruht, ist eine Neuplanung des Reglers, kein laufender Betrieb der Wärmepumpe.

Für die tatsächliche elektrische Leistungsaufnahme verwende stattdessen **Elektrische Leistungsaufnahme Wärmepumpe** / `current_electrical_power`.

#### Geräteseitige Wärmemengen, Warmwasser-Detail und Regler-Uhrzeit (nur Navigator 10)

Drei weitere read-only-WebSocket-Controller werden bei jedem Web-Poll
ausgewertet (live verifiziert auf Firmware jsonVersion 11, September 2026):

- **Wärmemenge Heizen/Warmwasser gesamt und heute (Web)**
  (`web_heat_quantity_heating_total`, `web_heat_quantity_hotwater_total`,
  `web_heat_quantity_heating_today`, `web_heat_quantity_hotwater_today`): der
  `statistic/detail`-Wärmemengenblock des Reglers — die Gesamtwerte und die
  Werte des heutigen Tages in kWh. Sie sind ein unabhängiger Gegencheck für
  die [eigenen Energiestatistiken](Smart-Energy-and-Comfort) der Integration
  und funktionieren ohne jeden Modbus-Zugriff.
- **Warmwasser-Zirkulation (Web)** (`web_dhw_circulation_active`):
  Binärsensor der Warmwasser-Zirkulationspumpe aus dem Frame
  `system.freshwater/overview` — ein Zustand, den die Modbus-Map nicht
  bereitstellt.
- **Warmwasser Statusinfo (Web)** (`web_dhw_status_info`): die numerische
  Statusinformation des Freshwater-Blocks, Diagnose-Kategorie.
- **Regler-Uhrzeit (Web)** (`web_controller_clock`): die eigene Uhr des
  Reglers als Zeitstempel-Sensor, mit `jsonVersion`, aktiver Benutzerebene,
  Sprache, Meldungsanzahl, Frostschutz-Flag und Netzwerk-Flag als Attribute.
  Die Regler-Uhr kann driften, und die zeitabhängigen Fachmann-Codes werden
  nach der auf dem Display angezeigten Zeit berechnet — dieser Sensor macht
  den Drift sichtbar.

#### Verbindungsstatus

Zwei diagnostische Entitäten machen die tatsächliche Verbindung auf dem
Dashboard sichtbar — sie existieren in jedem Verbindungsmodus, ein Fallback
fällt so sofort ins Auge:

- **Verbindungsmodus** (`connection_mode`): welche Transporte gerade
  tatsächlich leben — *Modbus + Web*, *Modbus only* oder *Web only*. Die
  Web-Hälfte folgt dem letzten Web-Abruf (ein Supplement, das nicht mehr
  antwortet, kippt den Zustand auf *Modbus only* und bei Erholung
  zurück). Die Attribute führen den konfigurierten Modus (die Option
  `connection_mode` unter *Konfigurieren* → Modbus-Sektion, Standard
  *auto*) und die erkannte Web-Variante (`nav10` oder `nav20`). Jeder
  Transportwechsel wird zusätzlich als INFO-Zeile ins Log geschrieben
  (`IDM connection state changed: …`), damit Support-Fälle die Frage
  „seit wann antwortet der Web-Pfad nicht" beantworten können — ohne
  Log-Spam.
- **Verbindung neu laden** (`connection_reload`, diagnostischer Button):
  Ein Tipp lädt den Konfigurationseintrag der Integration neu. Für die
  Momente, in denen Home Assistant sonst auf seinen Setup-Wiederholungs-
  Backoff wartet — nach einem Aus der Wärmepumpe startet der Tipp
  Erkennung, Abfrage und Web-Supplement sofort neu und räumt damit auch
  die „Nicht erreichbar"-Reparaturkarte weg. Dasselbe erreicht man über
  *Reparaturen → Erneut versuchen* oder ein manuelles Neuladen; der Button
  legt es einfach aufs Dashboard.
- **Letzte Web-Aktualisierung (Web)** (`web_last_success`): wann die lokale
  Weboberfläche zuletzt erfolgreich geantwortet hat — das Web-Gegenstück
  zur Modbus-*Letzter Erfolg*-Diagnose, immer vorhanden, wenn ein Web-PIN
  konfiguriert ist.

#### System-Controller (nur Navigator 10)

Vier nur lesende WebSocket-Controller, die das mitgelieferte Frontend für
seine Leistungsseite, Wetterkachel, den iON-Status und das Energiefluss-Widget
nutzt, sind Teil des Web-Supplements (`idm-heatpump-api` 2.12.0 oder neuer).
Sie sind additiv — die Frames werden mit dem regulären Web-Poll gelesen, und
jede Entität meldet *unavailable*, bis ihr Frame angekommen ist:

- **Wärmepumpen-Verbrauchsleistung (Web)** (`web_hp_power_consumption`): die
  momentane elektrische Verbrauchsleistung in kW, mit Leistungsmodus,
  Betriebsart, Messquelle, Batterie-Flag und der Produktions-Vorlauftemperatur
  als Attribute.
- **Wärmepumpen-Umgebungsleistung (Web)** (`web_hp_power_environment`): die
  leistungsseitige Quellenleistung in kW, mit der Quellen-Messquelle und der
  Quellen-Eintrittstemperatur als Attribute.
- **Heizstab (Web)** (`web_hp_heating_rod`): Binärsensor für den Heizstab-
  Zustand der Leistungsseite.
- **Netzleistung (Web)** (`web_energyflow_grid`) und **PV-Leistung (Web)**
  (`web_energyflow_pv`): Netz- und PV-Leistung des Energiefluss-Widgets in
  kW — beim aktivierten Geräte-Hierarchie-Modus auf dem PV-Subgerät. Die
  Firmware `T_NAV10_20.24-1580` hat den `house`-Kanal aus dem Frame entfernt;
  liefern ältere Firmware-Versionen ihn noch, steht er als Attribut bereit.
- **Wettervorhersage (Web)** (`web_weather_forecast`): die eigene Vorhersage
  des Reglers, die er über den myiDM-Dienst bezieht — die heutige Temperatur
  als Zustand, heute plus bis zu sechs Prognosetage (Temperatur min/max/ist,
  Bewölkung, Regenwahrscheinlichkeit, Sonnenminuten, Wettersymbol, Wind) als
  Attribute.
- **iON-Optimierung aktiv (Web)** (`web_ion_active`): diagnostischer
  Binärsensor für IDMs Cloud-Energioptimierung, mit aktivierter Einstellung
  und Abo-Status als Attribute.

#### Web-only-Steuerung (Navigator 10, Phase 4)

Ein **Nur-Web**-Eintrag ist nicht mehr rein lesend: Mit verbundener
WebSocket-Variante erhält er zwei Steuerelemente, die über die lokale
Web-Oberfläche schreiben — jeder andere Verbindungsmodus schreibt weiterhin
genauso wie bisher über Modbus:

- **Betriebsart (Web)** (`web_system_mode`): Auswahleinheit für die
  Betriebsart. Sie liest den aktuellen Modus und die vom Regler selbst
  vorgegebenen wählbaren Werte aus der `home/overview`-Kachel und schreibt
  über `home/save` — dieselbe Numerierung wie das Modbus-Register
  `system_mode`, vor dem Senden validiert. Ein abgelehnter Schreibvorgang
  meldet einen Fehler, statt still zu scheitern.
- **Fehler quittieren (Web)** (`web_acknowledge_errors`): der
  Quittieren-Knopf, schreibt `notification/save`.
- **Warmwasser-Solltemperatur (Web)** (`web_dhw_setpoint`): die
  Warmwasser-Solltemperatur als Zahl-Entität. Grenzen, Schrittweite und der
  aktuelle Wert stammen aus der vom Gerät selbst deklarierten
  Parameterdefinition, und jeder Schreibvorgang wird vor dem Senden gegen
  genau diese Grenzen validiert — dieselbe Schreibsicherheit wie im
  Register-Pfad.
- **Heizkreis X (Web)** Climate-Karte je Heizkreis (Raumtemperatur,
  Solltemperatur, Betriebsart; `HVACAction` aus dem Pumpenstatus) und die
  **Warmwasser (Web)** Water-Heater-Karte (Speichertemperatur oben +
  Sollwert) — dieselben validierten Web-Schreibvorgänge, als Standard-
  Home-Assistant-Karten.
- **Heizkreis X Raumsolltemperatur (Web)** / **Heizkreis X Betriebsart
  (Web)** (je konfiguriertem Heizkreis): die normale Raumsolltemperatur
  (Parameter `HK<x>04`) als Zahl und die Heizkreis-Betriebsart (Parameter
  `HK<x>01`) als Auswahl, mit den vom Gerät selbst deklarierten Grenzen
  bzw. Optionen. Ein `system.heatingcircuit/detail`-Rahmen je Heizkreis
  liefert zusätzlich Raumtemperatur und Pumpenstatus. Der einmalige
  Warmwasser-Boost bleibt bewusst vom Web-Pfad fern: Diese Firmware bietet
  ihn nur als Wochen-Zeitplan an, und das Schreiben ganzer
  Zeitplan-Zeichenketten ist ausgeschlossen.

Die Dienste `set_system_mode` und `acknowledge_errors` nutzen für
Nur-Web-Einträge automatisch denselben Web-Pfad. Schreibvorgänge verwenden
die autorisierte Web-Sitzung des Abfragezyklus und lesen den Zustand nach
jedem Schreiben zurück, wie die offizielle Web-Oberfläche. Sollwerte und
weitere Steuermöglichkeiten erfordern weiterhin Modbus.

Auf dem Navigator 2.0 liefern die Statistik-Seiten dieselbe Form aus der
älteren Weboberfläche: Sensoren **Laufzeit / Wärmemenge / elektrische
Energie, gesamt je Kategorie (Web 2.0)** — Stunden für Laufzeiten, kWh für
die Energiemengen, normalisiert mit der Einheitenskala der Seite selbst.

Antwortet eine Firmware auf einen dieser Controller nicht, bleiben die
betroffenen Entitäten einfach nicht verfügbar; der Rest der Web-Snapshots ist
unbeeinflusst.

Dupliziert ein Webwert eine bestehende Modbus-Entität, wird die Web-Entität übersprungen. Das verhindert doppelte Dashboard-Werte und hält Modbus als maßgebliche Quelle für registergestützte Daten.

Verfügbar sind nur Werte, die der aktuelle lokale Web-Schnappschuss zurückliefert. Optionale Navigator-10-Infosystem-Meldungen werden unabhängig gelesen; schlägt diese optionale Anfrage fehl, bleiben die anderen gültigen Webwerte verfügbar. Siehe [Lokale Navigator-Weboberfläche](Local-Web-Interface) für Details zum Protokoll und zum reinen Web-Betrieb.

### Interner Meldungs-Sensor

Der Diagnosesensor `internal_message` gibt die aktive IDM-interne Meldung als lesbaren Text aus, zum Beispiel einen Code plus Meldungsbeschreibung. Er stellt zusätzlich die strukturierten Attribute `message_code` und `message_text` bereit, sodass Automationen sowohl auf den numerischen Code als auch auf die lesbare Beschreibung reagieren können.

---

## Binärsensoren

| Entität | Register | Beschreibung |
|--------|----------|-------------|
| `hp_sum_alarm` | 1099 | Summenstörung (Gesamtstörung) |
| `compressor_status_1` | 1100 | Verdichter 1 läuft |
| `compressor_status_2` | 1101 | Verdichter 2 läuft |
| `compressor_status_3` | 1102 | Verdichter 3 läuft |
| `compressor_status_4` | 1103 | Verdichter 4 läuft |
| `heating_demand` | 1091 | Heizanforderung aktiv |
| `cooling_demand` | 1092 | Kühlanforderung aktiv |
| `dhw_demand` | 1093 | Warmwasseranforderung aktiv |
| `calculated_pv_surplus_operation` | abgeleitet | Wärmepumpe läuft am signalisierten PV-Überschuss (siehe PV / Energiemanagement) |

### Navigator 1.0/1.7 — Momentary-Coils (c3000/c3003)

Der 1.x-Coil-Block (ma_de_812049 Rev.1) besteht aus momentanen Kommandobits,
keinen Statussignalen: Der Regler führt eine Anforderung aus, sobald das Bit
gesetzt ist, und das Bit fällt sofort auf 0 zurück (auf realer 1.7-Hardware
bestätigt, Issue #319). Die Coils tragen deshalb keine Zustands-Entitäten:

- **c3003 — Anforderung Vorrangladung** trägt den Button **Vorrangladung
  anfordern** (siehe Abschnitt *Button*): ein einzelner Single-Coil-Write von
  ON (Function Code 05), der 1.x-Warmwasser-Boost. Ein Switch wird
  bewusst nicht angeboten — ein Switch würde auch OFF schreiben, was ein
  momentanes Kommandobit niemals erhalten darf.
- **c3000 — Störung quittieren** trägt den **Störung quittieren**-Button
  (siehe [Dienste](Services)), auf der 1.x-Familie ein Single-Coil-Write
  (Function Code 05) und auf der gemeinsamen Navigator-2.0/10-Familie ein
  Holding-Register-Write.
- **c3001/c3002 — Anforderung Heizen/Kühlen** werden nicht exponiert: Heizen
  oder Kühlen anfordern ist Aufgabe der Betriebsart-Selects.

---

## Zahl-Entitäten (schreibbar)

### Warmwasser

| Entität | Register | Bereich |
|--------|----------|-------|
| `dhw_setpoint` | 1032 | 35–95 °C |
| `dhw_charge_on_temp` | 1033 | 30–50 °C |
| `dhw_charge_off_temp` | 1034 | 46–53 °C |

### Heizkreis (pro Heizkreis)

| Entität | Register | Bereich |
|--------|----------|-------|
| `hc_{x}_room_setpoint_heat_normal` | 1401+ | 15–30 °C |
| `hc_{x}_room_setpoint_heat_eco` | 1415+ | 10–25 °C |
| `hc_{x}_room_setpoint_cool_normal` | 1457+ | 15–30 °C |
| `hc_{x}_room_setpoint_cool_eco` | 1471+ | 15–30 °C |
| `hc_{x}_heating_curve` | 1429+ | 0,1–3,5 (Schritt 0,1, Experte) |
| `hc_{x}_heating_limit` | 1442+ | 0–50 °C |
| `hc_{x}_cooling_limit` | 1484+ | 0–36 °C |
| `hc_{x}_parallel_shift` | 1505+ | 0–30 (Experte) |
| `hc_{x}_ext_room_temp` | 1650+ | 15–30 °C |

Als *Experte* markierte Einträge formen die Heizkurve der gesamten Anlage und schreiben in EEPROM-Register. Sie werden bei neuen Installationen deaktiviert erzeugt — aktiviere sie unter Einstellungen -> Geräte & Dienste -> IDM Heatpump -> Entitäten. Bestehende Installationen behalten den Zustand, den die Entität bereits hatte. `hc_{x}_setpoint_flow_constant` und `hc_{x}_setpoint_flow_cooling` sind aus demselben Grund Experte-Entitäten.

`hc_{x}_ext_room_temp` lässt sich manuell wie jede andere Zahl-Entität steuern oder wird automatisch durch die optionale Raumtemperatur-Weiterleitung gefüllt. Ist die Weiterleitung aktiviert, werden ausgewählte Home-Assistant-Temperatursensoren bei Zustandsänderungen und periodisch (Standardintervall: 300 Sekunden) in diese externen Raumtemperatur-Register geschrieben.

### GLT / externe Steuerung

| Entität | Register |
|--------|----------|
| `ext_outdoor_temp` | 1690 |
| `ext_humidity` | 1692 |
| `ext_demand_temp_heating` | 1694 |
| `ext_demand_temp_cooling` | 1695 |
| `glt_temp_demand_heating` | 1696 |
| `glt_temp_demand_cooling` | 1698 |
| `glt_heat_storage_temp` | 1716 |
| `glt_cold_storage_temp` | 1718 |
| `glt_dhw_temp_bottom` | 1720 |
| `glt_dhw_temp_top` | 1722 |

### Leistungsgrenzen

Diese Register sind modellabhängig und standardmäßig deaktiviert. Verwende sie nicht für gesetzliche oder vertragliche Laststeuerung, bevor das Verhalten für deine genaue Hardware und Firmware verifiziert ist.

| Entität | Register |
|--------|----------|
| `power_limit_hp` | 4108 |
| `power_limit_cascade` | 4112 |

---

## Auswahl-Entitäten

| Entität | Register | Optionen |
|--------|----------|---------|
| `system_mode` | 1005 | Standby, Automatik, Abwesend, Nur Warmwasser, Nur Heizen/Kühlen |
| `hc_{x}_mode` | 1393+ | Aus, Zeitprogramm, Normal, Eco, Manuell Heizen, Manuell Kühlen |
| `solar_mode` | 1856 | Aus, Automatik, Manuell |
| `isc_mode` | 1874 | Aus, Automatik, Manuell |

---

## Schalter-Entitäten

| Entität | Register | Beschreibung |
|--------|----------|-------------|
| `demand_heating` | 1710 | Externe Heizanforderung |
| `demand_cooling` | 1711 | Externe Kühlanforderung |
| `demand_dhw_charging` | 1712 | Externe WW-Ladeanforderung |
| `demand_onetime_dhw` | 1713 | Einmalige WW-Anforderung |

---

## Klima-Entitäten

Klima-Entitäten kombinieren eine Modusauswahl und eine Zieltemperatur in der Standard-Thermostatkarte von Home Assistant. Zwei Typen werden erstellt:

### Heizkreis-Klima-Entität (`climate.hc_x`)

Je eine pro konfiguriertem Heizkreis (A–G). Steuert den Betriebsmodus des Heizkreises und seine normale (Tag-)Raum-Solltemperatur.

| Steuerung | Register | Hinweise |
|---------|----------|-------|
| HVAC-Modus | `hc_{x}_mode` | Aus, Zeitprogramm, Normal, Eco, Manuell Heizen, Manuell Kühlen |
| Zieltemperatur | `hc_{x}_room_setpoint_heat_normal` | Bereich hängt von der Heizkreis-Konfiguration ab |
| Aktuelle Temperatur | `hc_{x}_room_temp` | Raumtemperatursensor |
| HVAC-Aktion | `hp_operating_mode` | Leitet HEATING/COOLING/IDLE aus dem Wärmepumpenstatus ab |

### Zonenraum-Klima-Entität (`climate.zm{z}_room{r}`)

Je eine pro konfiguriertem Raum in jedem Zonenmodul. Steuert den Betriebsmodus des Raums und seinen Temperatur-Sollwert.

| Steuerung | Register | Hinweise |
|---------|----------|-------|
| HVAC-Modus | `zm{z}_room{r}_mode` | Aus, Zeitprogramm, Normal, Eco, Manuell Heizen, Manuell Kühlen |
| Zieltemperatur | `zm{z}_room{r}_setpoint` | Bereich hängt von der Zonen-Konfiguration ab |
| Aktuelle Temperatur | `zm{z}_room{r}_temp` | Raumtemperatursensor |
| HVAC-Aktion | `hp_operating_mode` | Leitet HEATING/COOLING/IDLE aus dem Wärmepumpenstatus ab |

Schreibvorgänge laufen über den zentralen Schreibpfad des Koordinators mit optimistischen Updates und übersetzten Fehlermeldungen.

---

## Warmwasserbereiter

Eine einzige Warmwasserbereiter-Entität (`water_heater.idm_heatpump`) stellt die Steuerung der Warmwasser-Zieltemperatur mit Rückmeldung der Ist-Temperatur bereit. Sie wird erzeugt, wenn das Zielregister (`dhw_setpoint`) und ein Warmwasser-Temperaturregister existieren — die gemeinsame Familie meldet `dhw_temp_top`, die Navigator-1.0/1.7-Karte bietet stattdessen `dhw_temp` (Trinkwassererwärmertemperatur, Adresse 1012).

| Eigenschaft | Register | Hinweise |
|----------|----------|-------|
| Aktuelle Temperatur | `dhw_temp_top` / `dhw_temp` | Gemeinsame Familie: Warmwassertemperatur oben im Speicher; Navigator 1.x: `dhw_temp` (Trinkwassererwärmertemperatur) |
| Zieltemperatur | `dhw_setpoint` | Schreibbarer Sollwert (gemeinsame Familie typisch 35–95 °C; Navigator 1.x 35–60 °C, Float-Paar 2152–2153) |
| Betriebsmodus | k. A. | Immer „Wärmepumpe“ |

Nutzt denselben Schreibpfad des Koordinators wie die Klima-Entitäten.

---

## Button

Ein einzelner Button (`button.idm_heatpump_acknowledge_errors`) quittiert aktive Fehler an der Wärmepumpe, indem er `1` in das Nur-Schreib-Register `error_acknowledge` schreibt. Er ist immer verfügbar, damit Automationen auf Änderungen des Alarmzustands reagieren können.

Bei erkanntem Navigator 1.0/1.7 kommt ein zweiter Button hinzu (`button.idm_heatpump_request_dhw_priority_charge`, *Vorrangladung anfordern*): Er fordert eine Warmwasser-Vorrangladung an — ein einzelner FC05-Write von ON auf Coil c3003. Nur für manuelle Nutzung — die offizielle Tabelle stellt den Coil-Block unter den EEPROM-Hinweis, also kein Zeitplan und keine getaktete Automation.

Auf mindestens einer 1.x-Firmware endet die per Coil angeforderte Vorrangladung nicht von selbst: Der Regler bleibt im Warmwassermodus, bis der Fehler 020 (*Wärmepumpenvorlauf Maximaltemperatur*) auslöst ([Issue #319](https://github.com/Xerolux/idm-heatpump-hass/issues/319)). Verhält sich deine Anlage so, nutze stattdessen die Betriebsart *Warmwasser einmalig* (der `system_mode`-Select oder der Warmwasser-Boost) — dieser Weg beendet die Ladung auf der betroffenen Hardware normal. Auf verifizierter Firmware fällt der Coil unmittelbar nach dem Schreiben auf 0 zurück, deshalb schreibt der Button niemals OFF; melde das Verhalten deiner Firmware gerne im Issue.

---

## Zonenmodule

Für jedes aktivierte Zonenmodul (bis zu 10) werden Entitäten auf Raumebene erstellt:

| Entität pro Raum | Beschreibung |
|-----------------|-------------|
| `zm{z}_room{r}_temp` | Raumtemperatur |
| `zm{z}_room{r}_setpoint` | Raum-Sollwert (schreibbar) |
| `zm{z}_room{r}_humidity` | Raumluftfeuchte |
| `zm{z}_room{r}_mode` | Raum-Betriebsmodus |
| `zm{z}_room{r}_relay` | Relaisstatus (Binärsensor: an/aus) |

Zusätzlich pro Zone: `zm{z}_mode_heat_cool`, `zm{z}_dehumidification`
## Differenztemperaturgeregelte Heizkreise

Ist ein Navigator-10-Heizkreis als **Differenztemperaturgeregelt** eingerichtet,
wähle ihn unter **Konfigurieren → Anlage → Differenztemperaturgeregelte
Heizkreise** und zusätzlich in der Liste installierter Heizkreise aus. Im
erweiterten Formular steht die Auswahl neben **Heizkreise**. Standardmäßig ist
sie leer; normale Heizkreise behalten ihr Verhalten. Die manuelle Auswahl ist
maßgeblich und unabhängig vom separaten Modul für die interne
Differenztemperaturregelung; mit konfiguriertem Web-PIN werden Kreise dieses
Typs am Navigator 10 zusätzlich automatisch über die lokale
Webschnittstelle erkannt.

Die in [Issue #429](https://github.com/Xerolux/idm-heatpump-hass/issues/429)
gemeldeten Messwerte für HK D werden folgendermaßen zugeordnet. Andere
ausgewählte Kreise verwenden die entsprechenden Register der Bibliothek:

| Entität | Quelle bei HK D | Bedeutung |
| --- | --- | --- |
| Speichertemperatur | `hc_d_flow_temp` (1356) | Gemessene Speichertemperatur |
| Referenztemperatur | `hc_d_room_temp` (1370) | Gemessene Referenztemperatur |
| Temperaturdifferenz | Referenz minus Speicher | Differenz in K; 22,63 − 41,83 = −19,20 K |
| Status Differenztemperaturregelung | `hc_d_active_mode` (1501) | 255 bedeutet in diesem Kontext Standby; 0/1/2 behalten die dokumentierte Bedeutung Aus/Heizen/Kühlen |
| Heizkreispumpe | `pump_heating_circuitD` | Tatsächlicher Pumpenzustand, sofern die lokale Web-Ergänzung ihn liefert |

Die Temperaturdifferenz steht in jedem Funktionsprofil zur Verfügung.
Fehlende, nicht unterstützte oder ungültige Messwerte ergeben keine nutzbare
Differenz. Der Status ersetzt keine Pumpenmessung; aus der Differenz wird
kein Ladezustand abgeleitet.

**Umstellung:** Speicher- und Referenzsensor behalten ihre bisherigen Unique-IDs
und Entity-IDs (`hc_d_flow_temp` / `hc_d_room_temp`). Nur ihre Standardnamen
ändern sich; selbst vergebene Namen bleiben bestehen. Automationen mit diesen
IDs funktionieren weiter. Normale Heizkreis-Sollwerte, Heizkurve,
Heiz-/Kühlgrenzen, externe Raumtemperaturvorgaben, Climate-Entitäten,
Vorlaufabweichung und Web-Mischer-/Vorlaufsensoren werden für ausgewählte
Differenzkreise aus der Registry entfernt. Passe betroffene Dashboards und
Automationen an. Beim Abwählen entstehen normale Heizkreis-Entitäten erneut;
der Differenzsensor entfällt. Anpassungen entfernter Regler bleiben nicht erhalten.

**Entity-IDs:** Das Gerät des Kreises heißt `Heizkreis D` und trägt den Typ als
Modell (*Differential temperature control*), denn Home Assistant stellt jeder
neuen Entity-ID eines Geräts den Namens-Slug voran — ein Typ-Suffix im Namen
verdoppelte die Länge aller IDs. Entity-IDs, die registriert wurden, solange der
Gerätename noch mit `(Differenztemperaturgeregelt)` endete (0.20.1-b1…b4),
werden beim nächsten Start automatisch gekürzt:
`sensor.heizkreis_d_differenztemperaturgeregelt_temperaturdifferenz_hk_d`
wird zu `sensor.heizkreis_d_temperaturdifferenz_hk_d`. Passe Dashboards an, die
mit den langen Vorab-IDs erstellt wurden; selbst umbenannte Entity-IDs und kurz
vergebene IDs, die bereits einem anderen Objekt gehören, bleiben unangetastet.

**Unbestätigte Parameter:** Die API enthält keine bestätigten Register zur
Heizkreistyp-Erkennung oder für Hysterese, Schwellwert und Maximaltemperatur
dieses Typs. Der gemeldete Wert 60 °C bei `hc_d_setpoint_flow_constant` (1452)
belegt nicht dessen Bedeutung als Schwellwert. Diese Parameter werden daher
nicht unter vermuteten Namen angezeigt. Es kommen keine neuen Schreibzugriffe
hinzu. Die Zuordnung basiert auf dem Navigator-10-Bericht in #429 und muss
noch an der Anlage des Melders bestätigt werden.
