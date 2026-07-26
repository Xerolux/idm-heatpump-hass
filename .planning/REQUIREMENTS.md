# Requirements: IDM Heatpump for Home Assistant

**Defined:** 2026-07-25  
**Core Value:** Home Assistant steuert und überwacht die IDM-Wärmepumpe lokal,
zuverlässig und anlagensicher, ohne dass Reloads, Sentinel-Werte oder
Modellkonflikte zentrale Automationen unbemerkt deaktivieren.

## v1 Requirements

### Service Lifecycle

- [ ] **LIFE-01**: Nutzer können
  `idm_heatpump.set_external_climate`, `set_system_mode`,
  `acknowledge_errors` und `write_register` nach einer Optionsänderung oder
  einem Config-Entry-Reload weiterhin aufrufen.
- [ ] **LIFE-02**: Bei mehreren IDM-Config-Entries bleiben die Domain-Services
  verfügbar, wenn ein einzelner Entry entladen, neu geladen oder entfernt wird.
- [ ] **LIFE-03**: Domain-Services werden pro Home-Assistant-Start idempotent
  registriert und melden bei fehlendem geladenem Entry einen übersetzten
  Validierungsfehler, statt aus dem Service-Register zu verschwinden.

### Writable Register Availability

- [ ] **GLT-01**: Ein im Poll-Datensatz vorhandenes schreibbares
  Number-, Select- oder Switch-Ziel bleibt bei aktivem
  `hide_unused_registers` angelegt und aufrufbar, auch wenn sein aktueller Wert
  `-1.0`, `255`, `65535` oder ein anderer definierter Unset-Sentinel ist.
- [ ] **GLT-02**: Schreibbare Ziele mit einem Unset-Sentinel veröffentlichen
  keinen irreführenden Mess- oder Schaltzustand; ihr Zustand ist unbekannt, bis
  ein gültiger Wert gelesen oder erfolgreich geschrieben wurde.
- [ ] **GLT-03**: Ein schreibbares Ziel bleibt weiterhin verborgen bzw.
  unverfügbar, wenn das Register nicht zum erkannten Modell gehört, vom Gerät
  mit Illegal Data Address abgelehnt wurde oder im aktuellen Poll-Datensatz
  fehlt.
- [ ] **GLT-04**: Read-only Sensoren und die Sensorseite dual exponierter
  GLT-Messwerte behalten die bestehende Unused-Filterung, sodass Sentinel-Werte
  nicht als gültige Messdaten erscheinen.
- [ ] **GLT-05**: Nach einem erfolgreichen Schreibvorgang wird der optimistische
  Coordinator-Wert sofort als gültiger Zustand sichtbar und beim nächsten Poll
  mit dem Gerät abgeglichen.

### Model Detection and Issue #170

- [ ] **MODEL-01**: Die in Issue #170 fehlenden Vorgabe-Entitäten für
  PV-Überschuss, PV-Produktion und Hausverbrauch werden nach Umsetzung von
  GLT-01 bis GLT-05 erneut geprüft und als gemeinsamer Fehlerpfad mit #172 oder
  als eigenständiger Restfehler dokumentiert.
- [ ] **MODEL-02**: Ein Diagnosefall mit widersprüchlicher Modbus-, gespeicherter
  und Web-Modellerkennung weist nachvollziehbar Quelle, erkannte
  Navigator-Familie, Web-Variante, Firmware-Evidenz und aktiven manuellen
  Override aus.
- [ ] **MODEL-03**: Eine Modellkorrektur wird nur anhand redigierter
  Realdaten oder einer reproduzierbaren Fixture umgesetzt; sie erzeugt für
  Navigator 2.0, Navigator 10 und Navigator Pro den jeweils passenden
  Registerplan.
- [ ] **MODEL-04**: Liegt die Ursache in `idm-heatpump-api`, wird sie dort mit
  einem reproduzierbaren Detection-Test behoben und erst nach erfolgreichem
  Cross-Repo-Vertrag über eine exakt gepinnte API-Version in die Integration
  übernommen.

### Quality and Release

- [ ] **QUAL-01**: Regressionstests decken Single-Entry-Reload,
  Multi-Entry-Unload, Sentinel beim Plattform-Setup, Sentinel während des
  Betriebs, fehlende Register und dual exponierte GLT-Sensoren ab.
- [ ] **QUAL-02**: Die Änderungen bestehen `pytest tests/`,
  `mypy custom_components/idm_heatpump/` und
  `ruff check custom_components tests` sowie die Cross-Repo- und
  Release-Vertragstests.
- [ ] **REL-01**: Changelog und GitHub-Issues dokumentieren Ursache,
  Nutzerwirkung, Workaround, Testnachweis und die Zuordnung zwischen #170,
  #171 und #172.
- [ ] **REL-02**: Ein Release wird erst erstellt, nachdem mindestens die
  automatisierten Qualitätsprüfungen grün sind und der Modellteil von #170
  entweder mit Feldnachweis verifiziert oder ausdrücklich als noch offen
  abgegrenzt wurde.

## v2 Requirements

### Detection Architecture

- **DETECT-01**: Eine typisierte Detection-Entscheidung bündelt Quelle,
  Confidence, Navigator-Familie, Web-Protokoll und Firmware-Evidenz in einer
  zentralen Zustandsmaschine.
- **DETECT-02**: Redigierte Diagnoseexports enthalten eine kompakte
  Detection-Entscheidungshistorie, ohne Host, PIN, Seriennummer oder andere
  sensible Verbindungsdaten offenzulegen.

### Polling and Transport

- **POLL-01**: Nachweislich nicht unterstützte Register können
  firmwaregebunden zwischengespeichert werden, ohne die resiliente
  Bisection-Fallbacklogik zu entfernen.
- **TRANS-01**: Ein optionaler gemeinsamer Home-Assistant-Modbus-Transport wird
  erst nach Veröffentlichung eines stabilen offiziellen Vertrags evaluiert.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Cloud- oder Hersteller-API | Das Projekt garantiert vollständig lokalen Betrieb. |
| Produktive `modbus_connection`-Migration | Home Assistant überarbeitet den Vertrag noch; eine frühe Kopplung wäre instabil. |
| Direkte Testschreibvorgänge an unbekannte oder EEPROM-sensitive Register | Anlagen- und EEPROM-Schutz haben Vorrang. |
| Pauschales Vertrauen in Web- oder Modbus-Modelltexte | Modellentscheidungen benötigen reproduzierbare technische Evidenz. |
| Änderung bestehender Entity-Unique-IDs | Historie und Entity Registry müssen stabil bleiben. |
| Großflächiger Refactor von `__init__.py` oder `coordinator.py` im Bugfix | Der Fix soll klein, überprüfbar und rückportierbar bleiben. |

## Traceability

Die Roadmap ordnet jedes v1-Requirement genau einer Phase zu.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LIFE-01 | Phase 1 | Pending |
| LIFE-02 | Phase 1 | Pending |
| LIFE-03 | Phase 1 | Pending |
| GLT-01 | Phase 2 | Pending |
| GLT-02 | Phase 2 | Pending |
| GLT-03 | Phase 2 | Pending |
| GLT-04 | Phase 2 | Pending |
| GLT-05 | Phase 2 | Pending |
| MODEL-01 | Phase 3 | Pending |
| MODEL-02 | Phase 3 | Pending |
| MODEL-03 | Phase 3 | Pending |
| MODEL-04 | Phase 3 | Pending |
| QUAL-01 | Phase 2 | Pending |
| QUAL-02 | Phase 4 | Pending |
| REL-01 | Phase 4 | Pending |
| REL-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0
- Duplicate mappings: 0
- Coverage: 100%

---
*Requirements defined: 2026-07-25*
*Last updated: 2026-07-25 after roadmap creation*

## v0.8.7 Requirements — Sentinel Authority in API

**Scope:** v1 milestone (0.8.6-beta.2) is complete and live-verified. This
milestone makes the "unused/sentinel" classification data-driven and
device-specific by moving it into `idm-heatpump-api`.

### Sentinel Authority

- [ ] **SENT-01**: `idm-heatpump-api` deklariert pro `RegisterDef` ein optionales
  `sentinel_values`-Feld (typisiert) und befüllt es für alle heute per Heuristik
  behandelten Fälle (FLOAT `-1.0`, UCHAR `255`, UINT16 `65535` sowie
  dokumentierte Sonderwerte); API-Tests abgedeckt.
- [ ] **SENT-02**: Die Integration entscheidet „Register unbenutzt" über die
  API-deklarierten `sentinel_values` (`coordinator.is_register_unused`); die
  numerische Heuristik bleibt nur noch Fallback für nicht-deklarierte Register.
- [ ] **SENT-03**: Schreibbare Register bleiben auch mit deklariertem Sentinel
  Schreibziel (#172 bleibt erhalten); read-only Sensoren nicht vorhandener
  Hardware werden weiterhin ausgeblendet (keine `hide_unused`-Regression).
- [ ] **SENT-04**: Cross-Repo- und Release-Vertragstests pinnen die Integration
  auf die API-Version mit `sentinel_values`; pytest/mypy/ruff grün;
  reproduzierbares 0.8.7-Release.
