# Changelog

Die maßgebliche, vollständige Historie wird in
[`docs/CHANGELOG.md`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CHANGELOG.md)
und in den [GitHub-Releases](https://github.com/Xerolux/idm-heatpump-hass/releases) gepflegt.
Diese Seite fasst lediglich die aktuellen Meilensteine zusammen.

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
