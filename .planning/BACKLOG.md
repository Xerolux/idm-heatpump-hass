# Backlog

Erfasst beim Abschluss des v1-Milestones (0.8.6-beta.2) am 2026-07-26.
Punkte außerhalb des 0.8.7-Sentinel-Milestones, zur späteren Triage.

## Strukturell / Folge aus Sentinel-Authority (nach 0.8.7)

### BL-001: `hide_unused_registers` Vereinfachung
**Idee:** Sobald die Sentinel-Werte API-seitig deklariert sind (0.8.7), das
Filter-Feature im Integration-Code vereinfachen und die Dopplelung
Heuristik ↔ deklariert abbauen.
**Quelle:** Phase 5 LEARNINGS (Decision „hide behalten"); Nutzerfrage.
**Aufwand:** mittel (hängt an 0.8.7 SENT-02).
**Priorität:** nach 0.8.7.

### BL-002: 4108 `power_limit_hp` Standby-Dekodierung
**Idee:** 4108 liefert im Standby einen winzigen Denormal (raw `[0, 49024]` ≈
-1.75e-38), weder Wert noch bekannter Sentinel. Entweder als Sentinel
deklarieren oder dekodierungsseitig abfangen, damit
`number.idm_heatpump_leistungsbegrenzung_warmepumpe` / `…_kaskade` nicht
dauerhaft `unavailable` sind. Ggf. als zusätzlicher Nav10-Indikator nutzen.
**Quelle:** Phase 5 Live-Test (entity_export, Probe @4108).
**Aufwand:** klein-mittel (API-seitig).
**Priorität:** mittel.

## Datenqualität / berechnete Sensoren

### BL-003: Berechnete Sensoren im Standby `unavailable`
**Idee:** COP (`jahresarbeitszahl_cop_momentan`), Taktlaufzeiten,
Abtau-/Betriebsanteile, `durchschnittliche_taktlaufzeit` usw. sind im Standby
`unavailable`. Prüfen, ob das am fehlenden `thermal_power_flow_sensor`/`power_consumption_hp`
= 0.0 liegt oder an einer zu strengen 50-W-Schwelle; ggf. Zustand `unknown`
statt `unavailable` melden.
**Quelle:** Phase 5 entity_export (36 unavailable Entities).
**Aufwand:** klein.
**Priorität:** niedrig-mittel.

### BL-004: Nav10-Web-Sensoren teilweise `unavailable`
**Idee:** `momentane_leistung_*`, `laufzeit_kuhlen_web`, `diagnose_myidm_id_web`,
`diagnose_warmepumpenmodell_web` teilweise nicht verfügbar – prüfen, ob das
firmware-spezifische Datenangebot (NAV10_20.24-880) diese Settings nicht
liefert oder ob die Setting-ID-Map Lücken hat.
**Quelle:** Phase 5 entity_export + Nav10-WS-Read (60 Werte).
**Aufwand:** mittel (Feld-Diagnose nötig).
**Priorität:** niedrig.

## Geräte-Warning (cosmetisch)

### BL-005: `via_device`-Warning für Sub-Devices
**Idee:** HA loggt eine Warnung, dass Sub-Geräte (z. B. Warmwasser) ein
`via_device` referenzieren, das zum Zeitpunkt von `binary_sensor.py:45` noch
nicht existiert – Reihenfolge beim Anlegen der Geräte-Hierarchie prüfen
(future HA 2025.12 wird das strikter).
**Quelle:** Phase 5 HA-Log beim Setup.
**Aufwand:** klein.
**Priorität:** niedrig ( kosmetisch, aber timed – HA 2025.12 ).

## Open GitHub-Issues (post-milestone triage)

- **#44** (IDM Terra SWM / Navigator 2 Modellerkennung) – durch Phase-5-Test
  `test_detect_model_nav20_rejecting_power_measurement_block_stays_nav20`
  mit abgedeckt;_closed/Verifikation noch prüfen.
- **#135** (Roadmap: verbleibende Optimierungen) – Sammelissue, hierher
  zuordnen.
- **#148** (Tracking: HA modbus_connection Migration) – blockiert durch
  HA-Seite, bleibt zurückgestellt.
- **#158** (Register: Heizgrenze/Kühlgrenze) – Registerdefinitionen prüfen.
