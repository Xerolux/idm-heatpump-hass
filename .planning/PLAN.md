---
title: "GitHub-Issues #170, #171 und #172 beheben"
status: ready
created: 2026-07-25
branch: Codex/gsd-initial-planning
scope:
  - issue-170
  - issue-171
  - issue-172
requirements:
  - LIFE-01
  - LIFE-02
  - LIFE-03
  - GLT-01
  - GLT-02
  - GLT-03
  - GLT-04
  - GLT-05
  - MODEL-01
  - MODEL-02
  - MODEL-03
  - MODEL-04
  - QUAL-01
  - QUAL-02
  - REL-01
  - REL-02
---

# Umsetzungsplan: GitHub-Issues #170, #171 und #172

## Ziel

Die drei am 25.07.2026 neu gemeldeten Fehler werden mit kleinen,
rückportierbaren Änderungen behoben:

1. Die vier Domain-Services bleiben über Config-Entry-Reloads erhalten (#171).
2. Schreibbare GLT-/Steuerziele verschwinden nicht wegen eines
   Unset-Sentinels (#172 und der Vorgabewert-Anteil von #170).
3. Der verbleibende Modellkonflikt aus #170 wird anhand technischer Evidenz
   eingeordnet und nur bei reproduzierbarem Nachweis korrigiert.

Die älteren Issues #44, #135, #148 und #158 sind nicht Teil dieses Plans. Sie
werden nach Abschluss dieses Meilensteins separat triagiert.

## Bestätigte Ausgangslage

| Issue | Status der Analyse | Hauptursache |
|-------|---------------------|--------------|
| #171 | Im aktuellen Code bestätigt | Services werden in `async_setup()` registriert, aber bei `async_unload_entry()` entfernt und nach einem Reload nicht erneut registriert. |
| #172 | Im aktuellen Code bestätigt | Entity-Erzeugung und Laufzeitverfügbarkeit behandeln schreibbare Unset-Werte wie nicht vorhandene Hardware. |
| #170 | In zwei Teilprobleme getrennt | Fehlende PV-/GLT-Vorgaben überschneiden sich wahrscheinlich mit #172; die widersprüchliche Modellerkennung benötigt zusätzliche Evidenz. |

## Verbindliche Leitplanken

- Keine Modbus-Adressen in Plattformdateien hardcodieren.
- Alle Schreibvorgänge laufen weiter über
  `IdmCoordinator.async_write_register`.
- `unused_registers` bleibt für Polling und read-only Messwerte erhalten.
- Ein fehlendes oder als unsupported erkanntes Register wird nicht allein
  wegen seiner Schreibbarkeit exponiert.
- Bestehende Entity-Unique-IDs bleiben unverändert.
- Keine Schreibtests an EEPROM-sensitiven oder unbekannten Registern.
- Eine Änderung in `idm-heatpump-api` wird erst über eine exakt gepinnte,
  getestete Release-Version übernommen.

## Wave 1 – Service-Lifecycle reparieren (#171)

### Betroffene Dateien

- `custom_components/idm_heatpump/__init__.py`
- `custom_components/idm_heatpump/services.py`
- `tests/test_init.py`
- `tests/test_services.py`

### Umsetzung

1. Den Lebenszyklus der vier in `services.py` definierten Domain-Services an
   den bereits dokumentierten Domain-Lifecycle angleichen:
   - Registrierung weiterhin idempotent in `async_setup()`.
   - Kein Entfernen dieser globalen Services beim Unload eines einzelnen
     Config-Entries.
   - Service-Handler bestimmen den aktuell geladenen Entry weiterhin erst beim
     Aufruf.
2. Den Aufruf von `async_unload_services()` aus `async_unload_entry()` entfernen.
3. Die nicht mehr benötigte Unload-Funktion und ausschließlich dafür verwendete
   Konstanten entfernen. `ConfigEntryState` bleibt erhalten, soweit es für die
   Auswahl geladener Coordinators benötigt wird.
4. Das Verhalten bei keinem bzw. mehreren geladenen Entries unverändert über
   übersetzte `ServiceValidationError`-Fehler abbilden.

### Regressionstests

- Nach `async_setup()` sind alle vier Services exakt einmal registriert.
- Wiederholtes Setup registriert keine Duplikate.
- Ein erfolgreicher Entry-Unload ruft für diese vier Services kein
  `async_remove()` auf.
- Nach einem simulierten Options-Reload bleiben die Services registriert und
  aufrufbar.
- Bei zwei Entries bleibt der Servicezugriff erhalten, wenn einer entladen
  oder entfernt wird.
- Ohne geladenen Entry bleibt der Service registriert, liefert beim Aufruf aber
  `no_device_configured`.

### Abnahmekriterien

- `LIFE-01`, `LIFE-02` und `LIFE-03` sind durch automatisierte Tests belegt.
- DHW-Boost-Services behalten ihren bestehenden, separaten Entry-Lifecycle.
- Ein Home-Assistant-Core-Neustart ist nach einer Optionsänderung nicht mehr
  nötig, um die vier Services zurückzubekommen.

## Wave 2 – Schreibbare Sentinel-Ziele stabilisieren (#172, Teil von #170)

### Betroffene Dateien

- `custom_components/idm_heatpump/entity.py`
- `custom_components/idm_heatpump/number.py`
- `custom_components/idm_heatpump/select.py`
- `custom_components/idm_heatpump/switch.py`
- gegebenenfalls `custom_components/idm_heatpump/sensor.py` nur für die
  explizite Trennung dual exponierter GLT-Register
- `tests/test_entity.py`
- `tests/test_platforms.py`
- `tests/test_coordinator.py`

### Zielverhalten

Ein schreibbares Entity-Ziel darf bei einem Unset-Sentinel vorhanden und
aufrufbar bleiben, aber keinen falschen Mess- oder Schaltzustand anzeigen.

Die Gates bleiben getrennt:

1. **Register fehlt im Poll-Datensatz:** Entity nicht anlegen bzw. unavailable.
2. **Register wurde als Illegal Data Address erkannt:** Entity nicht
   exponieren.
3. **Read-only Register enthält Sentinel:** bestehende Unused-Filterung nutzen.
4. **Schreibbares Ziel enthält Sentinel:** Entity anlegen und verfügbar halten,
   Zustand als unbekannt ausgeben.

### Umsetzung

1. `should_add_entity()` um einen expliziten, keyword-only Modus für
   schreibbare Control-Entities erweitern. Dieser Modus darf den Sentinel-Check
   nur dann übersteuern, wenn:
   - das Register `writable=True` besitzt und
   - der Registername im aktuellen Coordinator-Datensatz vorhanden ist.
2. Den neuen Modus ausschließlich von `number.py`, `select.py` und `switch.py`
   verwenden. Sensoren und Binary-Sensoren behalten das bisherige
   Filterverhalten, auch wenn eine dual exponierte GLT-Definition technisch
   schreibbar ist.
3. In `IdmEntity.available` eine klar benannte Klassen- oder
   Instanzeigenschaft für schreibbare Controls berücksichtigen:
   - Coordinator erfolgreich und Register vorhanden → Sentinel darf das
     Control nicht unavailable machen.
   - Register fehlt → weiterhin unavailable.
4. Zustandsdarstellung bei Unset:
   - Number: `native_value` liefert `None`.
   - Select: `current_option` bleibt `None`.
   - Switch: `is_on` liefert `None`, statt Sentinel `255` als `True`
     darzustellen.
5. `IdmCoordinator.is_register_unused()` und die vorberechnete
   `unused_registers`-Menge nicht global abschalten. Dadurch bleiben
   Operation-Analyse und read-only Sensoren defensiv.
6. Nach einem erfolgreichen Write den bestehenden optimistischen
   Coordinator-Updatepfad nutzen; keine zweite Zustandsverwaltung einführen.

### Regressionstests

- Eine writable Number mit `-1.0` wird beim Setup erzeugt, ist verfügbar und
  hat `native_value is None`.
- Ein writable Switch mit `255` wird erzeugt, ist verfügbar und hat
  `is_on is None`.
- Ein writable Select mit einem nicht gemappten Sentinel bleibt schreibbar und
  hat `current_option is None`.
- Ein fehlendes writable Register wird nicht allein wegen `writable=True`
  erzeugt.
- Ein read-only Sensor mit `-1.0`, `255`, `65535` oder `-32768` bleibt
  ausgeblendet bzw. unavailable.
- Die Sensorseite eines dual exponierten `pv_surplus`-Registers bleibt bei
  Sentinel ausgeblendet, während die Number „Vorgabe“ vorhanden bleibt.
- Nach einem erfolgreichen Write wechselt der Control-Zustand sofort vom
  unbekannten Sentinel-Zustand auf den geschriebenen Wert.
- Entity-Unique-IDs bleiben vor und nach der Änderung identisch.

### Abnahmekriterien

- `GLT-01` bis `GLT-05` und `QUAL-01` sind durch Tests belegt.
- Die Workarounds `hide_unused_registers: false` und
  `set_external_climate` sind für diesen Fehler nicht mehr erforderlich.
- Die PV-, PV-Produktions- und Hausverbrauch-Vorgaben aus #170 werden nach
  Reload/Restart erneut geprüft.

## Wave 3 – Modellkonflikt aus #170 diagnostizieren

### Voraussetzung und Checkpoint

Vor einer Änderung der Modellerkennung werden vom Reporter redigierte Daten
benötigt:

- Home-Assistant-Diagnoseexport der Integration
- Debug-Log vom Setup bis zur Konfliktwarnung
- angezeigte Navigator-Version und Firmware
- Wert des manuellen Modell-Overrides
- Ergebnis der frischen Modbus-Erkennung
- gespeicherte Detection-Felder und verwendete Web-Variante

IP-Adressen, PIN, Seriennummer und personenbezogene Daten werden nicht in
Fixtures oder Tests übernommen.

### Betroffene Dateien je nach Befund

- `custom_components/idm_heatpump/__init__.py`
- `custom_components/idm_heatpump/coordinator.py`
- `custom_components/idm_heatpump/web_data.py`
- `custom_components/idm_heatpump/diagnostics.py`
- `custom_components/idm_heatpump/adapter_registers.py`
- `tests/test_init.py`
- `tests/test_coordinator.py`
- `tests/test_web_data.py`
- `tests/test_diagnostics.py`
- gegebenenfalls separates Repository `idm-heatpump-api`

### Diagnoseablauf

1. Nach Wave 2 feststellen, ob die drei fehlenden Vorgabewerte wieder stabil
   vorhanden sind.
2. Die Modellquellen getrennt protokollieren und vergleichen:
   - frisches `detect_model()`-Ergebnis
   - `client.model_info`
   - gespeicherte Config-Entry-Detection
   - manueller Override
   - Web-Modell, Web-Variante und Firmwarestring
3. Den Fall genau einer Kategorie zuordnen:
   - **A:** Vorgabewerte waren ausschließlich #172; Modellwarnung ist separat.
   - **B:** gespeicherte Detection-/Override-Daten sind veraltet.
   - **C:** Integrations-Reconciliation wählt trotz eindeutiger Evidenz die
     falsche Familie.
   - **D:** `idm-heatpump-api.detect_model()` klassifiziert den Controller
     falsch.
4. Nur für B bis D eine gezielte Änderung planen und mit anonymisierter Fixture
   reproduzieren.
5. Bei Kategorie D zuerst API-Test und API-Release durchführen, danach
   Integration-Pin, Cross-Repo-Test und Changelog aktualisieren.

### Abnahmekriterien

- `MODEL-01` bis `MODEL-04` sind entweder verifiziert oder als
  evidenzabhängiger, klarer Checkpoint dokumentiert.
- Navigator 2.0, Navigator 10 und Navigator Pro behalten jeweils den
  erwarteten Registerplan in den Tests.
- Es gibt keinen automatischen Modellwechsel allein aufgrund eines
  widersprüchlichen, unbestätigten Anzeigenamens.
- Diagnoseausgaben enthalten die Entscheidungsquellen, aber keine sensiblen
  Verbindungsdaten.

## Wave 4 – Gesamtprüfung und Release-Vorbereitung

### Automatisierte Prüfungen

```bash
pytest tests/
mypy custom_components/idm_heatpump/
ruff check custom_components tests
ruff format custom_components tests --check
```

Zusätzlich gezielt:

```bash
pytest tests/test_init.py tests/test_services.py
pytest tests/test_entity.py tests/test_platforms.py tests/test_coordinator.py
pytest tests/test_diagnostics.py tests/test_web_data.py
pytest tests/test_cross_repo_contract.py tests/test_release_contract.py
```

### Dokumentation und Issue-Abschluss

1. `docs/CHANGELOG.md` mit Ursache und Nutzerwirkung aktualisieren.
2. In #171 den Reload-/Service-Lifecycle-Test dokumentieren.
3. In #172 Setup-, Laufzeit-, Reload- und Restart-Verhalten dokumentieren.
4. In #170 den GLT-Anteil #172 zuordnen und den Modellteil separat
   bestätigen oder mit benötigter Evidenz offen halten.
5. Versionsänderung in `manifest.json` erst vor einem tatsächlichen Release
   durchführen.
6. Eine neue API-Version nur pinnen, wenn Wave 3 nachweislich eine
   API-Änderung erfordert.

### Release-Gate

Ein Release ist bereit, wenn:

- alle automatisierten Prüfungen grün sind,
- #171 und #172 vollständig reproduziert und behoben sind,
- der GLT-Anteil von #170 verifiziert ist,
- der Modellteil von #170 entweder feldverifiziert behoben oder ausdrücklich
  als separater offener Befund abgegrenzt ist,
- Release-ZIP und SHA-256-Prüfsumme gemäß bestehendem Release-Vertrag geprüft
  wurden.

## Risiken und Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|--------|---------------|
| Ein genereller Writable-Bypass exponiert Register nicht vorhandener Hardware | Bypass nur für im Datensatz vorhandene Register und nur auf Control-Plattformen. |
| Sentinel wird als echter Number-/Switch-Zustand dargestellt | Zustand explizit `None`, Entity bleibt nur als Schreibziel verfügbar. |
| Dual exponierte GLT-Sensoren zeigen ungültige Messwerte | Sensorplattform behält die bestehende Unused-Filterung. |
| Services werden mehrfach registriert | Bestehende `has_service()`-Idempotenz durch Tests sichern. |
| Falscher Modellfix aktiviert unzulässige Register | Keine Korrektur ohne Fixture/Feldevidenz; Registerplan pro Familie testen. |
| Upstream- und Integration-Version driften auseinander | Exakten API-Pin und Cross-Repo-Vertrag beibehalten. |

## Artefakte dieses Plans

- `.planning/PROJECT.md` – dauerhafter Projektkontext
- `.planning/REQUIREMENTS.md` – testbare Anforderungen
- `.planning/ROADMAP.md` – vier Phasen und Traceability
- `.planning/STATE.md` – aktueller GSD-Fortschritt
- `.planning/PLAN.md` – dieser zusammenhängende Umsetzungsplan
- Regressionstests für Service-Lifecycle und Writable-Sentinel-Verhalten
- optional anonymisierte Modell-Detection-Fixture
- Changelog- und GitHub-Issue-Nachweise

## Definition of Done

- #171 ist ohne Core-Neustart behoben.
- #172 ist bei Setup, Laufzeit, Reload und Restart behoben.
- Der Vorgabewert-Anteil von #170 ist nach Wave 2 eindeutig zugeordnet.
- Der Modellteil von #170 ist reproduzierbar behoben oder mit einem
  evidenzbasierten Checkpoint klar abgegrenzt.
- Alle 16 v1-Requirements sind umgesetzt oder bei MODEL-Anforderungen
  nachvollziehbar als externer Feld-Checkpoint markiert.
- Pytest, mypy, Ruff, Cross-Repo- und Release-Verträge sind grün.
- Die übrigen Issues #44, #135, #148 und #158 bleiben für die anschließende
  Triage sichtbar.
