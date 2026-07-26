# Backlog

Erfasst beim Abschluss des v1-Milestones (0.8.6-beta.2) am 2026-07-26,
aktualisiert nach Abschluss 0.8.7 / Backlog-Triage am 2026-07-26.

Status-Legende: ✅ erledigt · ⏸ bewusst zurückgestellt · 🔍 Feld-Diagnose nötig

## Strukturell / Folge aus Sentinel-Authority (nach 0.8.7)

### BL-001: `hide_unused_registers` Vereinfachung — ⏸ bewusst behalten
**Entscheidung:** Option bleibt erhalten. Die Sentinel-Autorität liegt nun in
der API (0.8.7); das Filter-Feature selbst ist für die UI-Hygiene weiterhin
nützlich (ohne sie würde die Entity-Liste mit `unavailable`/`unknown`-Sensoren
nicht vorhandener Hardware volllaufen, da die Verfügbarkeit sentinel-basiert ist).
Die konkrete #172-Lücke (schreibbare Ziele) ist bereits geschlossen.
**Quelle:** Phase 5 LEARNINGS; Nutzergespräch 2026-07-26.

### BL-002: 4108 `power_limit_hp` Standby — ✅ Non-issue (geschlossen)
**Befund:** 4108/4112 dekodieren korrekt zu `-1.0` (FLOAT-Sentinel „keine
Leistungsbegrenzung konfiguriert"); die früher beobachtete „tiny denormal"-Lesung
war ein Sondenfehler (falsche Wortreihenfolge). Die Entities
`leistungsbegrenzung_warmepumpe`/`…_kaskade` sind `disabled_by="integration"`
(erweiterte EEPROM-Register, bewusst standardmäßig deaktiviert). Mit #172 +
API 0.8.7 wären sie bei Aktivierung verfügbar (Zustand `unknown`).
**Quelle:** Phase 5/6 Live-Sonden.

## Datenqualität / berechnete Sensoren

### BL-003: Berechnete Sensoren im Standby — ✅ erledigt (0.8.7)
**Fix:** `IdmCalculatedSensor.available` hängt nur noch an „Quellen vorhanden +
endlich + nicht unused"; der berechnete Wert darf `None` sein (Zustand `unknown`)
ohne die Entity `unavailable` zu machen. COP im Standby (P_el = 0) zeigt nun
`unknown` statt `unavailable`. Die COP-Unterdrückung selbst bleibt (#135).
**Quelle:** `calculated_sensors.py`; `tests/test_calculated_sensors.py`.

### BL-004: Nav10-Web-Sensoren teilweise `unavailable` — 🔍 Feld-Diagnose offen
**Befund:** `momentane_leistung_*`, `laufzeit_kuhlen_web`, `diagnose_myidm_id_web`,
`diagnose_warmepumpenmodell_web` teilweise nicht verfügbar. Der Nav10-WS-Read
liefert 60 Werte; vermutlich liefert die Firmware `NAV10_20.24-880` einzelne
Setting-IDs nicht oder die Map hat Lücken.
**Nächster Schritt:** Setting-ID-Rohtable der Anlage mit dem Web-Client mitschneiden
und gegen `DEFAULT_NAVIGATOR10_SETTING_IDS` abgleichen.
**Quelle:** Phase 5 entity_export + Nav10-WS-Read.

## Geräte-Warning (future-compat)

### BL-005: `via_device`-Warning — ✅ erledigt (0.8.7)
**Fix:** `precreate_main_device()` legt das Hauptgerät über die stabile
Kennung an, bevor Plattformen weitergeleitet werden → `via_device` der
Sub-Geräte (Heizkreise, Warmwasser, Module) löst immer auf. Vermeidet die
HA-2025.12-Strictness-Warnung.
**Quelle:** `device_hierarchy.py`; `__init__.py`.

## Open GitHub-Issues (post-milestone triage)

- **#44** (IDM Terra SWM / Navigator 2 Modellerkennung) — ✅ durch Phase-5-Test
  `test_detect_model_nav20_rejecting_power_measurement_block_stays_nav20`
  abgedeckt; Terra-SWM bleibt Navigator 2.0 (4122/4126 werden abgelehnt).
- **#135** (Roadmap: Optimierungen) — ✅ adressiert: entitätsbasiertes Polling
  („81/152"), COP-Quellenregister verifiziert, berechnete Sensoren melden `unknown`.
- **#148** (HA `modbus_connection` Migration) — ⏸ blockiert durch HA-Seite
  (finaler offizieller Vertrag ausstehend); Tracking-Issue bleibt offen.
- **#158** (Heizgrenze/Kühlgrenze-Register) — ✅ verifiziert: Register
  `hc_{a..g}_heating_limit`/`hc_{a..g}_cooling_limit` sind in der API definiert;
  live liest HK A `heating_limit=15`, `cooling_limit=25` (korrekt, kein #109-200).

