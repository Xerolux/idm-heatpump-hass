# KNX-Bridge

> [!WARNING]
> **Experimentell.** Das automatisierte Verhalten ist durch Tests und statische
> Analyse abgedeckt. Einrichtung, eine sichere Nur-Empfangs-Konfiguration und
> das Neuladen der Integration wurden zusätzlich auf einer laufenden
> Home-Assistant-Installation mit aktiver KNX-Schnittstelle erprobt. Es wurden
> keine IDM-Gruppenadressen in ETS importiert, kein physisches
> Gruppenadress-Telegramm gesendet oder dekodiert, und die Buslast des ersten
> Exports ist bislang ungemessen. Behandle es als etwas zum Ausprobieren und
> Berichten, nicht als etwas, worauf du dich verlassen kannst. Siehe
> [`docs/release-evidence/0.16.0-rc.6.md`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/release-evidence/0.16.0-rc.6.md)
> für genau das, was verifiziert ist und was nicht.

Veröffentliche die Wärmepumpe auf einem KNX-Bus und nimm Befehle von dort
entgegen — über die KNX-Integration, die Home Assistant ohnehin mitbringt, und
**ohne** das IDM-KNX-Gateway-Modul.

---

## Was dies ersetzt

IDM verkauft die KNX-Anbindung des Navigators als **Weinzierl KNX IP BAOS
774**-Modul, das in ETS mit IDMs Beispielprojekt konfiguriert wird. Dieses
Projekt definiert eine feste Menge an Kommunikationsobjekten: Objekt 1 ist die
Außentemperatur, Objekt 4 der Systemmodus, Objekt 222 der Betriebsmodus des
Heizkreises A und so weiter — jedes mit Datenpunkttyp und Richtung.

Die KNX-Bridge baut diese Objektliste aus den Modbus-Werten nach, die diese
Integration ohnehin liest. Eine KNX-Installation sieht dieselben
Objektnummern, dieselben Datenpunkttypen und dieselben Lese-/Schreibrichtungen
wie mit dem Hardware-Modul. Bestehende Visualisierungen, Raumregler und
Logikbausteine funktionieren deshalb weiter — nur das Gateway ist weg.

> **Die Bridge ist kein KNX-Stack.** Sie ruft für alles auf der Busseite die
> Home-Assistant-[KNX-Integration](https://www.home-assistant.io/integrations/knx/)
> auf. IP-Tunneling, IP-Routing, die Gateway-Verbindung und **KNX Secure**
> kommen von dort und werden dort konfiguriert. Ist die KNX-Integration nicht
> eingerichtet, bleibt die Bridge inaktiv und legt ein Reparatur-Problem an.

---

## Voraussetzungen

| | |
|---|---|
| **Home-Assistant-KNX-Integration** | Eingerichtet und mit einem Gateway oder Tunnel verbunden |
| **IDM-Heatpump-Integration** | Läuft über Modbus (ein Web-only-Eintrag hat keine Registerwerte zum Veröffentlichen) |
| **Freie KNX-Hauptgruppe** | Der Katalog benötigt 1000 aufeinanderfolgende Gruppenadressen |

---

## Wo sich die Bridge in der Oberfläche findet

Die Bridge ist Teil der **Optionen** der Integration und taucht deshalb nur an
zwei Stellen und nirgendwo sonst auf:

| Ablauf | KNX-Bridge |
|---|---|
| Ersteinrichtung (Hinzufügen der Integration) | Ja — nach dem Haupt-Optionsschritt |
| **Konfigurieren** an einem bestehenden Eintrag | Ja — derselbe Schritt, vorbelegt mit den gespeicherten Werten |
| Menü **Neu konfigurieren** | Nein. Dieses Menü bearbeitet Verbindungseinstellungen (Host, Port, Slave-ID) und führt die Diagnose aus; es fasst die Optionen überhaupt nicht an — genauso wenig wie Raumtemperatur-Weiterleitung und Web-Supplement dort zu finden sind. |

Schaltest du die Bridge ab, bleiben die konfigurierte Basisadresse, die
Objektgruppen und die Überschreibungen erhalten — das erneute Einschalten
kostet dich also nicht das ETS-Mapping.

Im **Web-only-Modus** bleibt die Bridge unabhängig von der Einstellung aus:
Sie liefert Modbus-Registerwerte, die ein Web-only-Eintrag nicht liest. Das
steht beim Start im Log.

## Aktivierung

1. **Einstellungen → Geräte & Dienste → IDM Heatpump → Konfigurieren**
2. Öffne den Abschnitt **KNX-Bridge** und aktiviere **KNX-Bridge aktivieren**.
   Der Abschnitt enthält außerdem:
   - **Werte an KNX senden** — veröffentlicht ein Telegramm, wann immer sich ein Wert ändert
   - **Befehle von KNX akzeptieren** — schreibt eingehende Werte in die Wärmepumpe
   - **Leseanforderungen beantworten** — antwortet auf ein `GroupValueRead` mit dem aktuellen Wert
   - **Vollständiges Sendeintervall** — sendet jeden Wert periodisch neu (0 = nur bei Änderung)
   - **Änderungstoleranz** — wie weit sich ein Zahlenwert bewegen muss, bevor er wieder gesendet wird
3. Bestätigen. Danach folgt ein Schritt **KNX-Gruppenadressen** mit:
   - **Basis-Gruppenadresse** — siehe unten
   - **Objektgruppen** — welche Teile des Katalogs teilnehmen
   - **Gruppenadressen-Überschreibungen** — für Objekte, die dein ETS-Projekt bereits anders adressiert

---

## Wie Gruppenadressen vergeben werden

IDMs Beispielprojekt kommt mit einer **leeren** Gruppenadressentabelle: Jede
Installation vergibt ihre eigenen. Die Bridge leitet sie deshalb aus einer
Basisadresse plus der IDM-Objektnummer ab:

```
group address = base address + object number
```

Mit der Standardbasis `8/0/0`:

| IDM-Objekt | Wert | Gruppenadresse |
|---|---|---|
| 1 | Außentemperatur | `8/0/1` |
| 4 | Systemmodus | `8/0/4` |
| 21 | Warmwasser-Sollwert | `8/0/21` |
| 222 | Betriebsmodus Heizkreis A | `8/0/222` |
| 400 | Wärmemenge Heizen | `8/1/144` |
| 999 | Thermische Gesamtenergie | `8/3/231` |

Der komplette Katalog passt in eine einzige Hauptgruppe (`8/0/1` … `8/3/231`)
— eine freie Hauptgruppe ist also die ganze Planung, die nötig ist.

### Überschreibungen

Wenn dein ETS-Projekt bereits andere Adressen verwendet, liste die Ausnahmen
auf — eine pro Zeile, `register = address`:

```
outdoor_temp = 1/2/3
system_mode = 1/2/4
# lines starting with a hash are ignored
```

Ein Eintrag mit leerer Adresse nimmt dieses Objekt vollständig aus der Bridge
heraus. Alles nicht Aufgeführte behält seine abgeleitete Adresse.

---

## Objektgruppen

Jeder Katalogeintrag gehört zu einer Gruppe, und nur die ausgewählten Gruppen
werden veröffentlicht und registriert:

| Gruppe | Inhalt |
|---|---|
| `system` | Außentemperatur, Systemmodus, Fehlernummer, Puffertemperaturen, Fehlerquittierung |
| `heat_pump` | Vorlauf/Rücklauf, Wärmequelle, Verdichter, Pumpen, Bivalenzpunkte, Störungen |
| `dhw` | Warmwassertemperaturen und Sollwert |
| `heating_circuits` | Heizkreise A–G: Vorlauf, Raum, Sollwerte, Kurve, Grenzen, Modi, externe Raumtemperatur |
| `zones` | Zonenmodule 1–10 mit bis zu 8 Räumen je Modul |
| `glt` | Gebäudeleittechnik-Eingänge: externe Temperaturen, Feuchte, Anforderungen |
| `energy` | Wärmemengen und aktuelle Leistung |
| `solar` | Kollektor, Rücklauf, Ladetemperaturen und Solarmodus |
| `isc` | ISC-Kühltemperaturen und Modus |
| `cascade` | Verfügbare/laufende Stufen, angeforderte Temperaturen, Leistung und Bivalenzgrenzen |
| `booster` | Temperaturen von Booster 1 und 2, Pumpen, Verdichter |
| `pv` | PV, Batterie, Hausverbrauch, elektrische und thermische Gesamtleistung |

Objekte, deren Register der verbundene Regler nicht bereitstellt, werden
automatisch übersprungen — ein Navigator ohne Zonenmodul legt also nie
Zonenobjekte auf den Bus.

---

## Richtung

Jedes Objekt trägt die Richtung, die IDM ihm im Beispielprojekt gegeben hat:

- **Nur lesbare Objekte** (Temperaturen, Zustände, Energiezähler) werden nur
  veröffentlicht. Ein auf einer dieser Adressen eintreffendes Telegramm wird
  ignoriert.
- **Beschreibbare Objekte** (Modi, Sollwerte, externe Temperaturen,
  Anforderungen) werden veröffentlicht *und* für eingehende Telegramme
  registriert. Ein Gruppenschreibzugriff auf so eine Adresse wird über den
  normalen Schreibpfad in das zugehörige Modbus-Register geschrieben —
  inklusive der Sicherheitsprüfungen, des Schreib-Cooldowns und des
  EEPROM-Schutzes.

KNX-Bedienelemente können Zwischenwerte aussenden, während ein Drehregler
gedreht oder ein Pfeil angetippt wird. Die Bridge behält deshalb den neuesten
Wert je Register für eine eine Sekunde lange Ruhephase und schreibt nur
diesen endgültigen Wert. Ist der normale Schreib-Cooldown oder das
EEPROM-Intervall noch aktiv, bleibt der neueste Wert in der Warteschlange und
wird angewendet, sobald die Sperre abläuft; ein späteres Telegramm ersetzt
ihn. Werte, die bereits dem aktuellen Zustand des Koordinators entsprechen,
verbrauchen keinen Schreibzyklus.

Das ändert die Befehlsbehandlung, nicht die Schreibsicherheit. Die Einstufung
der EEPROM-empfindlichen Register und das standardmäßige 60-Sekunden-
EEPROM-Intervall bleiben unverändert. Das Intervall bleibt in den
Integrationseinstellungen konfigurierbar — für Besitzer, die bewusst einen
anderen Kompromiss zwischen Verschleiß und Latenz eingehen.

### Leseanforderungen

Ein KNX-Gerät, das einen Wert anfragt — ein Taster, der nach einem Neustart
seine Anzeige auffrischt, eine Visualisierung, die wieder hochkommt — sendet
ein `GroupValueRead`. Die Bridge antwortet darauf mit dem Wert, den die
Wärmepumpe gerade liefert, als `GroupValueResponse` — genau das macht der
BAOS-Gateway auch.

Die Antwort geht sofort raus und nicht über die gedrosselte
Sende-Warteschlange: Eine Leseanforderung wird jetzt beantwortet oder
überhaupt nicht sinnvoll, und ihre Anzahl ist durch die anfragenden Geräte
begrenzt. Objekte, die nur beschrieben werden können, und Werte, die der
Regler als ungenutzt meldet, werden nicht beantwortet — es gibt ja nichts,
womit man antworten könnte.

Schaltest du **Leseanforderungen beantworten** aus, bleiben diese Adressen
unregistriert und die Bridge bei Lesezugriffen stumm. Ein
`GroupValueResponse` von einem anderen Gerät wird nie in die Wärmepumpe
geschrieben: Es beantwortet die Frage eines anderen, statt uns einen Befehl
zu geben.

Die Registrierung eingehender Telegramme läuft über die Aktion
`knx.event_register` der KNX-Integration; eine Änderung am eigenen
Ereignisfilter der KNX-Integration ist daher nicht nötig.

Zwei Schutzmechanismen halten Bus und Regler davon ab, sich im Kreis zu
unterhalten: Nur Telegramme, die als *eingehend* markiert sind, werden
verarbeitet, und ein Wert, der nur das zurückmeldet, was die Bridge kurz
zuvor veröffentlicht hat, wird nicht zurückgeschrieben.

---

## Fertige ETS-Importdateien

Die Bridge sendet auf den Gruppenadressen, aber ETS braucht sie trotzdem im
Projekt, damit die echten KNX-Geräte — ein Taster, der die Vorlauftemperatur
anzeigt, eine Visualisierung, ein Logikmodul — damit verknüpft werden können.
Zwei generierte Dateien liegen im Repository, damit niemand mehrere hundert
Adressen von Hand eintippt:

| Datei | Inhalt |
|---|---|
| [`idm-waermepumpe-kompakt.xml`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/examples/knx/idm-waermepumpe-kompakt.xml) | 43 Adressen: das, was eine Anzeige oder Visualisierung realistischerweise zeigt, plus die Werte, die eine KNX-Installation an die Wärmepumpe zurückmelden kann. Heizkreise A und B. |
| [`idm-waermepumpe-komplett.xml`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/examples/knx/idm-waermepumpe-komplett.xml) | alle 654 Objekte |

Beide gehen von der Standard-Basisadresse `8/0/0` aus. Die passenden
`.csv`-Dateien sind eine lesbare Referenz — Objektnummer, Register, Richtung
—, keine Importdateien.

**Import in ETS 6** (dreistufiger Gruppenadress-Stil): Sichere das Projekt,
klicke mit der rechten Maustaste auf den obersten Eintrag unter
*Gruppenadressen*, wähle *Gruppenadressen importieren*, wähle die `.xml` aus
und gleiche den Importbericht mit bereits vorhandenen Adressen ab.

### Eigene Dateien erzeugen

Ist `8/0/0` in deinem Projekt belegt oder du möchtest eine andere Auswahl,
generiere eine Datei mit deiner eigenen Basisadresse:

```bash
# A curated subset on main group 11
python scripts/generate_knx_group_addresses.py --base 11/0/0 --profile compact --output ./out

# Only what a visualisation needs
python scripts/generate_knx_group_addresses.py --base 11/0/0 --groups system,dhw,energy --output ./out

# Named registers, whatever you like
python scripts/generate_knx_group_addresses.py --base 11/0/0 \
  --registers outdoor_temp,dhw_setpoint,hc_a_mode --output ./out
```

Die Namen stammen aus der eigenen deutschen Namenstabelle der Integration —
eine Adresse liest sich in ETS also so wie die zugehörige Entität in Home
Assistant.

## Die Objektliste für ETS exportieren

Die Aktion `idm_heatpump.export_knx_group_addresses` antwortet mit der Tabelle
für **diesen** Regler — Objektnummer, Gruppenadresse, Datenpunkttyp, Richtung
und Einheit —, sodass daraus ein frisches ETS-Projekt aufgebaut werden kann:

```yaml
action: idm_heatpump.export_knx_group_addresses
target:
  entity_id: sensor.idm_heatpump_outdoor_temperature
data:
  knx_base_address: "8/0/0"
response_variable: knx_objects
```

Die Antwort sieht so aus:

```yaml
base_address: "8/0/0"
count: 187
objects:
  - object: 1
    group_address: "8/0/1"
    register: outdoor_temp
    dpt: "9.001"
    group: system
    writable: false
    unit: "°C"
```

Beide Felder sind optional: Ohne sie verwendet die Aktion die für die Bridge
konfigurierten Adressen und Objektgruppen.

---

## Buslast

Ein erster Export sendet ein Telegramm pro Objekt; die Bridge drosselt sie
deshalb auf etwa 20 Telegramme pro Sekunde und sendet einen Wert erst wieder,
wenn er sich tatsächlich weiter als um die konfigurierte Toleranz bewegt hat.
Bei einer Anlage mit vielen Heizkreisen und Zonenmodulen beschränke die
Objektgruppen auf das, was die KNX-Seite wirklich verbraucht, statt alles zu
veröffentlichen.

---

## Datenpunkttypen

Der Katalog verwendet IDMs eigene Datenpunkttypen, wo das Beispielprojekt
einen angibt, und leitet den Rest aus dem Register ab:

| Art des Werts | DPT |
|---|---|
| Temperaturen | `9.001` |
| Feuchte | `9.007` |
| Leistung (kW) | `9.024` |
| Wärmemengen (kWh) | `14.031` |
| Prozentwerte | `5.001` |
| Modi, Zustände, Zähler | `7.001` (`5.010` für den Systemmodus) |
| Bivalenzpunkte (vorzeichenbehaftete °C) | `8.001` |
| Anforderungen | 1-Bit, gesendet als reine `0`/`1`-Nutzlast |

---

## Fehlerbehebung

**Reparatur-Problem „KNX-Bridge inaktiv“**
Die KNX-Integration ist nicht eingerichtet. Füge sie zuerst hinzu und lade
danach den IDM-Heatpump-Eintrag neu.

**Es kommt nichts am Bus an**
Prüfe, dass *Werte an KNX senden* aktiviert ist, dass die Gruppe des Objekts
ausgewählt ist und dass der Regler den Wert überhaupt meldet — Objekte, deren
Register fehlt oder als ungenutzt markiert ist, werden übersprungen.

**Ein Taster bleibt nach einem Neustart leer**
Prüfe, dass *Leseanforderungen beantworten* aktiviert ist. Sendet das Gerät
gar keine Leseanforderung, setze ein **Vollständiges Sendeintervall**, damit
jeder Wert periodisch wiederholt wird.

**Ein Befehl aus KNX bleibt ohne Wirkung**
Nur Objekte, die IDM als beschreibbar markiert, nehmen Befehle an. Prüfe,
dass *Befehle von KNX akzeptieren* aktiviert ist, und suche im Log nach
einem Schreibfehler: Der Schreibvorgang durchläuft dieselben
Sicherheitsprüfungen wie jeder andere Schreibvorgang. Ein Wert außerhalb des
Registerbereichs wird abgelehnt. Ein aktiver allgemeiner oder EEPROM-Cooldown
hält den neuesten gültigen Befehl in der Warteschlange und wendet ihn an,
sobald die Sperre abläuft.

**Zwei Objekte teilen sich eine Adresse**
Die Überschreibungsliste lehnt eine doppelte Adresse ab, und sie lehnt auch
eine Überschreibung ab, die die abgeleitete Adresse eines anderen bedienten
Objekts beansprucht — eines von beiden würde das andere lautlos verdrängen.
Kollidieren die abgeleiteten Adressen mit etwas anderem am Bus, verschiebe
die Basisadresse in eine freie Hauptgruppe.

---

## Nicht abgedeckt

Zwei Objekte des Beispielprojekts fehlen bewusst: die Objekte für die externe
Pumpenanforderung 384 (*Sole-/Zwischenpumpe*) und 385 (*Grundwasserpumpe*).
IDMs eigene Bezeichnungen lassen sich nicht eindeutig auf die beiden
zugehörigen Register abbilden, und ein falscher Rückschluss würde die falsche
Pumpe ansteuern. Verwende für diese die Aktion `write_register`, bis das
Mapping auf der Hardware bestätigt ist.

---

**Siehe auch:** [Konfiguration](Configuration) · [Aktionen](Services) · [Modbus-Register](Modbus-Register)
