# Entitäten

## Entitäten der Smart-Funktionen

Das optionale [Smart Energy & Comfort](Smart-Energy-and-Comfort)-Profil ergänzt elektrische und thermische Energiezähler für Gesamtlaufzeit, Tag und Monat, COP für dieselben Zeiträume, geschätzte Kosten, CO₂ und optionale PV-Nutzung sowie die Verdichterzyklus- und Betriebsanalyse. Es handelt sich um abgeleitete Werte, nicht um zusätzliche physische Zähler. Die erforderlichen Leistungsregister müssen verfügbar sein.

Der Health Monitor ergänzt acht Prüfungen auf Probleme und einen Berichtssensor. Heizkurven- und Wetterberater ergänzen schreibgeschützte Empfehlungen. Der optionale Komfort-Zeitplan verändert den bestehenden Raum-Sollwert des Heizkreises; er erzeugt keine zweite Klima-Regelentität. Das automatische Warmwasserladen nutzt die bestehenden Boost-Bedienelemente und die bestehende Zustandsmaschine.

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
| Navigator-Version (Web) | Erkannte Navigator-Generation, zum Beispiel Navigator 2.0 oder Navigator 10 |
| Software-Version (Web) | Software-Version des Reglers, gemeldet von der lokalen Weboberfläche |
| Wärmepumpen-Modell (Web) | Modell/Typ der Wärmepumpe, gemeldet von der Weboberfläche |
| myIDM-ID (Web) | Kompakte myIDM-ID, abgeleitet aus dem lokalen Web-Kontowert vor dem `@` |
| Anzahl Infosystem-Meldungen (Web) | Anzahl aktiver Navigator-10-Infosystem-Meldungen |
| Anforderungsgrund (Web) | Nur Navigator 10: der vom Regler selbst gemeldete Anforderungsgrund (Issue #353) |

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

Eine einzige Warmwasserbereiter-Entität (`water_heater.idm_heatpump`) stellt die Steuerung der Warmwasser-Zieltemperatur mit Rückmeldung der Ist-Temperatur bereit. Sie wird erzeugt, wenn beide Register `dhw_temp_top` und `dhw_setpoint` existieren.

| Eigenschaft | Register | Hinweise |
|----------|----------|-------|
| Aktuelle Temperatur | `dhw_temp_top` | Warmwassertemperatur oben im Speicher |
| Zieltemperatur | `dhw_setpoint` | Schreibbarer Sollwert (typisch 35–95 °C) |
| Betriebsmodus | k. A. | Immer „Wärmepumpe“ |

Nutzt denselben Schreibpfad des Koordinators wie die Klima-Entitäten.

---

## Button

Ein einzelner Button (`button.idm_heatpump_acknowledge_errors`) quittiert aktive Fehler an der Wärmepumpe, indem er `1` in das Nur-Schreib-Register `error_acknowledge` schreibt. Er ist immer verfügbar, damit Automationen auf Änderungen des Alarmzustands reagieren können.

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
