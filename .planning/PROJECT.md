# IDM Heatpump for Home Assistant

## What This Is

IDM Heatpump ist eine inoffizielle Home-Assistant-Custom-Integration für die
lokale Steuerung und Überwachung von IDM-Wärmepumpen mit Navigator 2.0,
Navigator 10 und Navigator Pro. Die Integration verbindet Home Assistant über
Modbus TCP und optional über die lokale Navigator-Weboberfläche mit der Anlage,
ohne Cloud-Abhängigkeit.

Das Projekt ist ein bestehendes Brownfield-System mit stabiler
Produktionsnutzung, HACS-Verteilung, umfangreicher Test-Suite und einer
library-first Architektur auf Basis von `idm-heatpump-api`.

## Core Value

Home Assistant muss eine IDM-Wärmepumpe lokal, zuverlässig und anlagensicher
überwachen und steuern können, ohne dass Reloads, Sentinel-Werte oder unsichere
Modellerkennung zentrale Automationen unbemerkt außer Betrieb setzen.

## Requirements

### Validated

- ✓ Lokale Modbus-TCP-Anbindung über `idm-heatpump-api` mit resilientem
  Batch-Polling und Isolation nicht unterstützter Register — bestehend
- ✓ Optionale lokale Navigator-Webdaten und Web-only-Fallback ohne
  Cloud-Abhängigkeit — bestehend
- ✓ Home-Assistant-Plattformen für Sensoren, Binary-Sensoren, Numbers, Selects,
  Switches, Climate, Water Heater und Buttons — bestehend
- ✓ Sichere zentrale Schreibpfade über den Coordinator mit optimistischen
  Updates und übersetzten Fehlern — bestehend
- ✓ Config Flow, Reconfigure, Options Flow, Reparaturen und redigierte
  Diagnosedaten — bestehend
- ✓ Heizkreis-, Zonen-, Kaskaden-, GLT/PV- und
  Raumtemperatur-Weiterleitungsfunktionen — bestehend
- ✓ Strikte Typprüfung, Ruff, Pytest, Hassfest, HACS-Validierung und
  Release-Vertragsprüfungen — bestehend
- ✓ Reproduzierbare Kopplung einer Integrationsversion an eine exakt gepinnte
  `idm-heatpump-api`-Version — bestehend

### Active

- [ ] Die vier Domain-Services bleiben nach Optionsänderung, Entry-Reload und
  Multi-Entry-Unload verfügbar; GitHub-Issue #171 ist durch Regressionstests
  abgedeckt.
- [ ] Schreibbare GLT-/Steuerregister bleiben bei einem temporären
  Unset-/Sentinel-Wert als Schreibziel vorhanden, während echte
  read-only/unsupported Register weiterhin ausgeblendet werden; GitHub-Issue
  #172 ist durch Setup-, Laufzeit- und Neustarttests abgedeckt.
- [ ] Der Vorgabewert-Anteil aus GitHub-Issue #170 wird gegen den Fix für #172
  verifiziert und bei bestätigter Ursache als Duplikat bzw. gemeinsamer
  Fehlerpfad dokumentiert.
- [ ] Der verbleibende Modellkonflikt aus GitHub-Issue #170 wird anhand
  redigierter Diagnose-, Firmware-, Modbus- und Web-Evidenz reproduzierbar
  eingeordnet, ohne eine Navigator-Familie zu erraten.
- [ ] Alle Fehlerbehebungen bestehen Pytest, striktes mypy, Ruff sowie die
  relevanten Cross-Repo- und Release-Vertragstests.
- [ ] Release- und Issue-Dokumentation beschreibt Ursache, Workaround,
  Verifikation und gegebenenfalls notwendige Änderungen in
  `idm-heatpump-api`.

### Out of Scope

- Cloud- oder Hersteller-APIs — die Integration bleibt vollständig lokal.
- Produktive Anbindung an Home Assistants angekündigtes
  `modbus_connection`-Modell — bis zum finalen offiziellen Vertrag blockiert.
- Unkontrollierte Schreibtests an EEPROM-sensitiven, Service- oder unbekannten
  Registern — Anlagen- und EEPROM-Schutz haben Vorrang.
- Spekulative Modellerkennungsänderungen ohne reale Diagnose- oder
  Firmware-Evidenz — ein falscher Registerplan ist riskanter als ein
  dokumentierter Diagnosebedarf.
- Änderungen stabiler Entity-Unique-IDs zur Behebung von
  Verfügbarkeitsproblemen — Registry- und Verlaufsstabilität bleiben erhalten.

## Context

- Aktuelle Integrationsversion: `0.8.5` in
  `custom_components/idm_heatpump/manifest.json`.
- Aktuell gepinnte Bibliothek: `idm-heatpump-api[web]==0.8.4`.
- Mindestumgebung: Home Assistant `2026.5.0`, Python `3.13+`.
- GitHub-Issues #170, #171 und #172 wurden am 25.07.2026 neu gemeldet.
- #171 ist im aktuellen Code nachvollziehbar: Services werden in
  `async_setup()` registriert, aber während `async_unload_entry()` entfernt und
  bei einem Entry-Reload nicht erneut registriert.
- #172 ist im aktuellen Code nachvollziehbar: Der generische
  Unused-/Sentinel-Filter unterscheidet bei Entity-Erzeugung und
  Laufzeitverfügbarkeit nicht zwischen read-only Messwerten und schreibbaren
  Eingängen.
- Die in #170 fehlenden PV-/GLT-Vorgabewerte sind schreibbare Messwertregister
  und überschneiden sich voraussichtlich mit #172. Der gleichzeitig gemeldete
  Konflikt zwischen Modbus- und Web-Modellerkennung bleibt ein eigenständiger
  Diagnosepfad.
- Die Architektur- und Qualitätsgrundlage liegt unter
  `.planning/codebase/` und wird bei wesentlichen Strukturänderungen
  aktualisiert.

## Constraints

- **Lokaler Betrieb**: Keine externen Laufzeit- oder Cloud-Abhängigkeiten — dies
  ist ein zentrales Produktversprechen.
- **Registerquelle**: Adressen, Datentypen, Schreibbarkeit und
  Modellspezifika kommen aus `idm-heatpump-api`; Plattformdateien enthalten
  keine hardcodierten Registeradressen.
- **Schreibsicherheit**: Schreibvorgänge laufen über
  `IdmCoordinator.async_write_register`; unbekannte oder
  EEPROM-empfindliche Register benötigen explizite Schutzmechanismen.
- **Kompatibilität**: Navigator 2.0, Navigator 10 und Navigator Pro sowie
  unterschiedliche Firmwarestände dürfen nicht durch eine pauschale
  Modellannahme vereinheitlicht werden.
- **Home Assistant**: Async-I/O, Config-Entry-Lifecycle, Entity Registry,
  übersetzte Fehler und Gold-Quality-Anforderungen bleiben eingehalten.
- **Typqualität**: Python-Code bleibt vollständig typisiert und besteht
  `mypy` im Strict-Modus.
- **Release-Reproduzierbarkeit**: Eine veröffentlichte Integrationsversion pinnt
  eine explizit getestete `idm-heatpump-api`-Version.
- **Git**: Entwicklung erfolgt auf `Codex/...`-Feature-Branches; kein Push auf
  `main` oder `master`.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| `idm-heatpump-api` bleibt Source of Truth für Registersemantik | Verhindert Drift zwischen Integration und Gerätebibliothek | ✓ Good |
| Der Coordinator bleibt einzige Laufzeit- und Schreibgrenze | Bewahrt Locking, Fehlerklassifikation, optimistische Updates und Poll-Reconciliation | ✓ Good |
| Domain-weite Services und Entry-spezifische Ressourcen erhalten getrennte, konsistente Lebenszyklen | Reloads dürfen keine globalen Actions entfernen | — Pending |
| Ein vorhandenes schreibbares Ziel wird nicht allein wegen eines Unset-Sentinels entfernt | Externe Eingänge müssen gerade im ungesetzten Zustand beschreibbar bleiben | — Pending |
| Read-only Sensoransicht und schreibbares Control können bei dual exponierten GLT-Registern unterschiedliche Sentinel-Sichtbarkeit haben | Schreibbarkeit bleibt erhalten, ohne ungültige Messwerte als valide Sensorwerte auszugeben | — Pending |
| Modellerkennung wird evidenz- und vertrauensbasiert korrigiert, nicht anhand einzelner UI-Texte | Falsche Modellfamilien können gefährliche oder nicht unterstützte Registerpläne erzeugen | — Pending |
| GSD-Planungsartefakte werden im Repository versioniert | Künftige Phasen, Entscheidungen und Verifikation bleiben nachvollziehbar | ✓ Good |

## Evolution

Dieses Dokument entwickelt sich an Phasen- und Meilensteinübergängen weiter.

**Nach jedem Phasenübergang:**
1. Ungültig gewordene Anforderungen mit Begründung nach Out of Scope verschieben.
2. Ausgelieferte und verifizierte Anforderungen nach Validated verschieben.
3. Neu erkannte Anforderungen unter Active ergänzen.
4. Architektur- oder Produktentscheidungen in Key Decisions festhalten.
5. Prüfen, ob What This Is und Core Value weiterhin stimmen.

**Nach jedem Meilenstein:**
1. Alle Abschnitte vollständig prüfen.
2. Core Value gegen die reale Nutzung validieren.
3. Out-of-Scope-Begründungen erneut prüfen.
4. Kontext um neue Feldberichte, Firmwarestände und Release-Erkenntnisse ergänzen.

---
*Last updated: 2026-07-25 after GSD brownfield initialization*

## Milestone 0.8.7 — Sentinel Authority in API (2026-07-26, planned)

**Status:** v1 milestone (Reliability Bugfixes, 0.8.6-beta.2) complete and
live-verified; #170/#171/#172 closed. The v1 "Active" requirements above are
therefore considered **Validated**.

**Goal (0.8.7):** Move the "unused/sentinel" classification authority from the
integration's numeric heuristic into `idm-heatpump-api` as declared
`sentinel_values` per `RegisterDef`, so the filter becomes data-driven and
device-specific instead of relying on `-1`/`255`/`65535` literals.

**Active (0.8.7):**
- [ ] **SENT-01:** `idm-heatpump-api` declares an optional `sentinel_values`
  field on `RegisterDef` and populates it across the register catalog for all
  cases currently handled by the integration's heuristic (FLOAT `-1.0`, UCHAR
  `255`, UINT16 `65535`, plus documented special sentinels); covered by tests.
- [ ] **SENT-02:** The integration resolves "register unused" from the
  API-declared `sentinel_values` (`coordinator.is_register_unused`); the numeric
  heuristic remains only as a fallback for registers without a declaration.
- [ ] **SENT-03:** Writable registers stay callable write targets under a
  declared sentinel (#172 behaviour preserved); read-only sensors of absent
  hardware keep being hidden (no `hide_unused` regression).
- [ ] **SENT-04:** Cross-repository + release-contract tests pin the
  integration to the exact API version that provides `sentinel_values`;
  pytest/mypy/ruff green; reproducible 0.8.7 release.

**Out of scope (→ backlog):** 4108 standby decode; `hide_unused_registers`
simplification; issues #44/#135/#148/#158.

---
*Last updated: 2026-07-26 — v1 milestone complete (0.8.6-beta.2); 0.8.7 milestone planned.*
