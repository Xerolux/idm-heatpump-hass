# Code-Review, Fehleranalyse & Optimierungsplan

**Datum:** 2026-07-22  
**Repo:** `C:\Users\Basti\Documents\GitHub\idm-heatpump-hass`  
**Code-Stand:** `custom_components/idm_heatpump/manifest.json` → **0.8.5-beta.3**  
**Modus:** nur Planung / Review — **keine Code-Änderungen im Repo**  
**Speicherort:** `docs/dev/code-review-and-optimization-plan.md` — vollständiger Plan + Fazit aus der Code-Review-Session 2026-07-22.

---

## 1. Fazit

Die Integration ist **reif und architektonisch solide**:

- Coordinator-zentrierte I/O
- library-first Register (`idm-heatpump-api[web]==0.8.3`)
- resilientes Polling (Illegal Data Address / Exception Code 2)
- `runtime_data`, Config-/Options-/Reconfigure-Flow
- Repairs, Diagnostics, übersetzte Exceptions
- starke Stub-/Pytest-Suite und Quality-Scale-Tracking (Gold-Ziel)

Trotzdem gibt es **verifizierte Runtime-Bugs mit spürbarem Impact**:

1. Web-Detection-Persistenz kann einen **vollen Config-Entry-Reload** auslösen.
2. Web-Refresh kann einen **frischen Modbus-Snapshot überschreiben** (async Race).
3. Diagnostics **crasht im Web-only-Modus** (`update_interval is None`).
4. Web-Entities werden **unavailable**, wenn Modbus fehlschlägt — obwohl Web ok ist.

Zusätzlich: Korrektheits- und Lifecycle-Lücken bei Climate/Water-Heater-Writes, Services mit synthetischen `RegisterDef`, Background-Tasks und Room-Temp-Forwarding.

**Empfehlung:** Arbeit in **3 Implementierungs-PRs + 1 Docs-PR** nach Severity.  
Keine riskanten Register-/API-Pin-Änderungen. Keine geschätzten Messwerte. Kein Verdrahten von `modbus_transport.py`, solange der HA Shared-Connection-Vertrag fehlt.

**Nächster Schritt:** Auf deine Anweisung warten — z. B. „Phase A umsetzen“, „nur Docs speichern nach `docs/dev/…`“, oder „B1 Variante A/B“.

---

## 2. Architektur (Ist)

```
HA ConfigEntry.runtime_data → IdmHeatpumpData
  ├── IdmCoordinator (DataUpdateCoordinator)
  │     ├── IdmModbusClient (idm-heatpump-api)
  │     ├── optional IdmWebClientPool / Web-Supplement
  │     ├── unused / unsupported Register-Tracking
  │     └── optimistic Writes + delayed Refresh
  ├── optional web_task / room_temp_forwarding_task / OperationAnalysis
  └── Platforms: sensor, binary_sensor, number, select, switch,
                 climate, water_heater, button
```

### Stärken (beibehalten)

- Stabile Unique IDs `{entry_id}_{key}` + Migration
- `IdmEntity` mit Availability über precomputed `unused_registers`
- Resilientes Batch-Polling mit Bisection
- Web-PIN-/Host-Redaction in Diagnostics
- Gold/Platinum-Tracking in `quality_scale.yaml` (self-assessment)

### Dokumentations-Drift (nicht funktional, aber riskant)

- `AGENTS.md` noch ~0.8.2; Manifest 0.8.5-beta.3
- `CLAUDE.md` veraltet (~0.6.7 / lokaler `modbus_client.py`)
- Wiki/Home und Platform-Listen teilweise unvollständig
- `quality_scale.yaml`: „three services“ vs. tatsächlich mehr Services

---

## 3. Verifizierte Findings

### P0 — Critical / High (zuerst)

| ID | Severity | Thema | Ort | Wirkung | Fix-Richtung |
|----|----------|-------|-----|---------|--------------|
| **B1** | Critical | Web-Detection persistiert → **voller Reload** | `coordinator.py` `_persist_web_detection`; `__init__.py` `add_update_listener(async_reload_entry)` | `async_update_entry(data=…)` feuert den Listener → Unload/Reload. Kann Writes (DHW-Boost, Climate, Room-Temp) abbrechen. | Reload-Listener nur bei Options-/Connection-Diff; Detection darf bleiben, darf aber keinen Reload auslösen. |
| **B2** | High | Web-Refresh **überschreibt** frisches Modbus-`data` | `coordinator.py` `async_refresh_web_supplement` | Web liest `D_old`, Modbus setzt `D_new`, Web setzt `{**D_old, **web}` → Modbus-Daten verloren. | Nur Web-Keys in den **live**-Snapshot mergen; optional kurzer Snapshot-Lock mit Poll/Write. |
| **B3** | High | Diagnostics **crasht** im Web-only-Modus | `diagnostics.py`; Web-only setzt `scan_interval=None` | `update_interval.total_seconds()` → `AttributeError`. | Null-sicher: `if update_interval else None` (+ Test). |
| **B4** | High | Web-Entities hängen an Modbus-`last_update_success` | `sensor.py` `IdmWebSensor`; `web_binary_sensors.py` `IdmWebBinarySensor` | Web kann ok sein, Entities trotzdem unavailable. | Availability nur an `web_supplement` / Key-Präsenz koppeln. |

### P1 — Medium (Korrektheit / UX / Lifecycle)

| ID | Severity | Thema | Ort | Fix-Richtung |
|----|----------|-------|-----|--------------|
| **B5** | Medium | Web-Binary-Entities nur bei Key im Setup-Snapshot | `web_binary_sensors.py` `web_binary_sensor_entities` | Alle Definitionen anlegen, wenn Web enabled; Availability steuert Zustand. |
| **C1** | Medium | Climate/Water-Heater Writes ohne übersetzte Fehler | `climate.py`, `water_heater.py` | Zentrales Write-Error-Pattern wie `IdmEntity` / Services. |
| **C2** | Medium | `hvac_action` kann bei ungültigem Status werfen | `climate.py` `HeatPumpStatus(status_val)` | Defensive Coercion + try/except → IDLE/None. |
| **C3** | Medium | Services/Button: synthetische `RegisterDef` | `services.py`, `button.py` | `coordinator.get_register(...)` bevorzugen; Custom nur mit `allow_custom_register`. |
| **C4** | Medium | Climate `available` ignoriert unused/missing | `climate.py` | Keys vorhanden + nicht in `unused_registers`. |
| **C5** | Medium | Room-Temp-Forwarding: Task-Sturm | `room_temp_forwarding.py` | Debounce/Coalesce; in-flight Task ersetzen. |
| **H1** | Medium | Background-Tasks nicht entry-tracked | `__init__.py`, `coordinator.py`, `web_data.py` | `entry.async_create_background_task` für langlebige Loops. |
| **H2** | Medium | Multi-Entry Services: still erste Entry | `services.py` `_get_coordinator` | Bei mehreren Entries ohne `entry_id`/`entity_id` → `ServiceValidationError`. |
| **H3** | Low–Med | Frozen `_attr_device_info` | climate / water_heater / button | Property wie `IdmEntity` (Model/Firmware/Serial live). |
| **P1** | Medium | Zone-Room-Mode: serielle Einzelreads pro Poll | `coordinator.py` | Rate-Limit; nur konfigurierte Räume; Library-Quarantine. |
| **R1** | Medium | Optimistic Write mutiert shared `data` | `coordinator.py` `async_write_register` | Mit B2 gemeinsam: serialisierte Snapshot-Updates. |

### P2 — Low / Hygiene / Performance

| ID | Thema | Fix |
|----|-------|-----|
| **D1** | Doc/Agent-Drift | AGENTS, CLAUDE, Wiki, quality_scale Comments auf 0.8.5-beta.3 + volle Platform-/Service-Liste |
| **D2** | `register_not_supported` Issue-ID global | Pro Register oder aggregierte Liste |
| **D3** | EVU-Lock DeviceClass `LOCK` | HA-Semantik (on=unlocked) prüfen; ggf. invertieren oder SAFETY/PROBLEM |
| **D4** | Technician-Codes = Host-Lokalzeit | Dokumentieren; optional Timezone-Option |
| **D5** | Web-only unload mit vollem `PLATFORMS` | Geladene Platforms tracken |
| **D6** | `polling_plan.py` nicht Hauptpfad | Verdrahten (vorsichtig) oder dokumentieren |
| **D7** | Mutation `model_info.model_name` | rebuild/replace statt In-Place |
| **X1–X3** | Field-blocked (COP, Binary-Verify, Max-Last) | In `open-work-audit.md` belassen — **nicht** schätzen |

---

## 4. Implementierungsphasen (nach Freigabe)

### Phase A — Stabilität (P0) — 1 PR, blockiert

**Ziel:** Kein Reload durch Detection; keine verlorenen Modbus-Snapshots; Diagnostics/Web-Availability robust.

1. **B1** — Update-Listener nur bei Options-/Connection-Diff reloaden; Detection in `entry.data` darf bleiben (**Variante A**, empfohlen).
2. **B2** — Web-Metadata nur in live Snapshot mergen; optional gemeinsamer Snapshot-Lock mit Poll/Write.
3. **B3** — Diagnostics null-safe für `update_interval`.
4. **B4** — Web-Entity-Availability von Modbus entkoppeln.

**Akzeptanzkriterien**

- Bestehende Pytest-Suite grün
- Neue Tests für B1–B4
- Keine Unique-ID-/Entity-Key-Brüche
- Keine API-Pin-Änderung

**Datei-Touches Phase A**

| Datei | Änderung |
|-------|----------|
| `coordinator.py` | B1 Persistenz-Strategie; B2 Merge; optional Lock |
| `__init__.py` | Update-Listener nur bei relevanten Änderungen |
| `diagnostics.py` | Null-safe `update_interval` |
| `sensor.py` | Web-Sensor Availability |
| `web_binary_sensors.py` | Web-Binary Availability (+ optional B5) |
| `tests/test_coordinator.py` | Race + Persistenz-Reload |
| `tests/test_diagnostics.py` | Web-only |
| `tests/test_platforms.py` / `test_web_binary_sensors.py` | Availability |

### Phase B — Korrektheit Schreibpfade & Services

1. Climate/Water-Heater: zentrale Write-Error-Behandlung (C1)
2. `HeatPumpStatus` defensiv (C2)
3. Services/Button: Map-Register bevorzugen (C3)
4. Climate availability unused-aware (C4)
5. Multi-Entry ServiceValidationError (H2)

### Phase C — Lifecycle & Performance

1. Background-Tasks über `async_create_background_task` (H1)
2. Room-temp debounce (C5)
3. Room-mode validation rate-limit (P1)
4. Device-info Property (H3)
5. Optional: geladene Platforms tracken (D5)

### Phase D — Hygiene (parallel möglich)

1. Docs/Agent-Sync (D1)
2. Issue-IDs unsupported registers (D2)
3. EVU-Lock Semantics nur mit Web-Sample (D3)
4. Technician-Codes Doku (D4)

### Explizit nicht in diesem Zyklus

- Produktiv verdrahten von `modbus_transport.py`
- API-Pin ändern
- Unique-ID-Schema ohne Migrationsvertrag
- COP / Binary-Semantik / Max-Last ohne Field Diagnostics
- Broad Adapter-Refactors ohne Bug-Bezug

---

## 5. Teststrategie

- Unit/Stub-Tests erweitern (keine echte HA-Instanz nötig)
- Neue Cases:
  - Web detection persist → **kein** `async_reload`
  - Interleaved Web + Modbus behält Modbus-Keys
  - Diagnostics Web-only ohne Exception
  - Web entity available bei failed Modbus
- Nach Implementierung: `pytest`, `ruff`, `mypy` (wie CI)
- Optional manuell: Web-PIN + Modbus, Reconfigure, DHW-Boost während Web-Poll

---

## 6. Risiken & Mitigation

| Risiko | Mitigation |
|--------|------------|
| Listener-Umbau verhindert nötige Reloads nach Options | Whitelist: scan_interval, circuits, zones, hide_unused, web, hierarchy, timeouts, room forwarding, connection fields |
| Snapshot-Lock Deadlock | Kurzer dict-swap; I/O außerhalb Lock |
| Availability-Flapping | Nur Web-Entities entkoppeln; Modbus-Entities unverändert |
| Service map-register Fallback | Custom-Writes mit `allow_custom_register` behalten |

---

## 7. Designentscheidung offen: B1

- **Variante A (empfohlen):** Update-Listener reloaded nur bei Options-/Connection-Diff; Detection darf in `entry.data` bleiben.
- **Variante B:** Detection nur Runtime/Store; `entry.data` unverändert; kein Reload-Risiko, Detection eher flüchtig.

**Plan-Default:** Variante A.

---

## 8. Empfohlene Reihenfolge

1. Phase A freigeben und umsetzen (höchster Stabilitäts-Impact)
2. Phase B (Schreibpfade / Services)
3. Phase C (Lifecycle / Perf)
4. Phase D (Docs)
5. Field-blocked Themen weiter über Issue-Templates sammeln

---

## 9. Status dieser Session

- Code gelesen und Findings verifiziert (Coordinator, Init, Diagnostics, Sensor/Web-Binary, Climate, Services, Room-Temp).
- **Fazit + vollständiger Plan** sind in dieser Datei gespeichert.
- **Keine** Implementierung im Repo.
- Dokument liegt unter `docs/dev/code-review-and-optimization-plan.md`.

**Nächste Anweisung abwarten.** Mögliche nächste Befehle:

- `speichere nach docs/dev/...` — Plan ins Repo legen
- `Phase A umsetzen` — Stabilitätsfixes implementieren
- `B1 Variante A` / `B1 Variante B` — Designentscheidung festlegen
- `nur Phase D` — Docs-Hygiene

---

## 10. Umsetzungsstatus (2026-07-22)

**Status: Phase A–D implementiert und nach Git gepusht (Branch `Codex/beta-0.8.5-beta.3`).**

### Umgesetzt (Auszug)

- B1 Reload-Fingerprint (Detection-Keys lösen keinen Reload aus)
- B2 Web/Modbus Snapshot-Merge (live re-read)
- B3 Diagnostics null-safe `update_interval`
- B4/B5 Web-Entity Availability + alle Web-Binary-Defs
- C1–C4 Climate/Water-Heater/Services Write-Härtung
- H1/H2 Background-Tasks + Multi-Entry ServiceValidationError
- C5 Room-Temp Debounce, Zone-Room-Mode Rate-Limit
- D1–D5 Docs/Quality-Scale/Issue-IDs/EVU-SAFETY/Technician-Doku
- Pytest: 900 passed, 2 skipped

---

## 11. Bewusst **nicht** gemacht

Diese Punkte wurden absichtlich **nicht** implementiert oder nur dokumentiert.
Sie bleiben offen für spätere Arbeit (Field Diagnostics / HA-Core-Vertrag).

### Extern blockiert / Field-Daten nötig

| ID | Thema | Warum offen |
|----|-------|-------------|
| **X1** | Weitere COP-Verifikation (Warmwasser, Abtauen, Firmware-Varianten) | Ohne reale Anlagendaten keine sichere Kennzahl |
| **X2** | Eindeutiger WP-Vorlauf-Sollwert + Vorlauf-Abweichungssensor | Register-Semantik nicht abschließend verifiziert |
| **X3** | Binary-Register-Vollverifikation Nav 2.0 / Nav 10 | Field Diagnostics ausstehen |
| **X4** | Lasttests mit maximaler HK/Zonen/Raum-Zahl | Keine passenden Diagnoseexports |

### Home-Assistant- / API-Blocker

| Thema | Warum offen |
|-------|-------------|
| Produktiv-Verdrahtung von `modbus_transport.py` (Shared Modbus Connection) | Offizieller HA Shared-Connection-Vertrag fehlt noch |
| Weitergehende Transport-Abstraktion in `idm-heatpump-api` | API-seitig, nicht in diesem Integrations-Zyklus |
| API-Pin-Bump als eigener, isolierter „nur Pin“-PR | Pin 0.8.3 war bereits im Arbeitsstand; kein separates API-Repo-Release hier |

### Bewusst nicht angefasst (Risiko / Scope)

| Thema | Warum offen |
|-------|-------------|
| Unique-ID-Schema / Entity-Migrationen | Migrationsvertrag; kein Breaking Change ohne Bedarf |
| Broad Adapter-Refactor (`library_adapter` / `adapter_*`) | Kein Bug-Zwang; hohes Diff-Risiko |
| Entity-aware Polling als **Hauptpfad** (`polling_plan.py` voll verdrahten) | Nur vorbereitet/dokumentiert; volle Verdrahtung riskant ohne Field-Tests |
| EEPROM-Schreibschutz-Erweiterung für `write_register` | Nur dokumentiert/mitigated; kein zweiter Hard-Block ohne Produktentscheid |
| Technician-Codes: Timezone-Option in der UI | Nur dokumentiert (Host-Lokalzeit); keine neue Config-Option |
| Wiki-Vollsync aller Entity-/Platform-Seiten | Teilweise Hygiene (Home/Stability/AGENTS); kein kompletter Wiki-Rewrite |
| Offizielle HA Core Submission / Brands-Repo-Pfad | Außerhalb Custom-Integration-Scope |
| GitHub Release / HACS Stable Tag | Nicht Teil dieses Code-Fix-Zyklus |

### Nächster sinnvoller Follow-up (wenn gewünscht)

1. Field Diagnostics von echten Anlagen (X1–X4)
2. Nach HA Shared-Modbus-Vertrag: Transport-Adapter feature-gated
3. Optional: `polling_plan` schrittweise im Coordinator verdrahten
4. Optional: Wiki Entities/Services-Seiten 1:1 an 8 Platforms angleichen