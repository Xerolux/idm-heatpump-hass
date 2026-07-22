# Plan: Issue #128 — Relay-Status als Binary-Sensor (API + Integration)

## Problem
Relais-Status pro Raum (`zm{z}_room{r}_relay`) wird als Sensor mit 0/1 angezeigt. Soll ein `binary_sensor` sein, der `on`/`off` zeigt. Heutige Ursache: das Register kommt als `UCHAR` mit `binary=False` aus der `idm-heatpump-api` und wird deshalb in der Integration auf den Sensor-Pfad geschickt.

## Strategie: Option C (API + Integration)
- **API**: Relay semantisch als binär markieren (`binary=True` auf dem UCHAR-Register — entspricht der Library-Konvention, siehe `heating_demand`, `cooling_demand`, `compressor_status_1..4`).
- **Integration**: Zone-Sensor-Generator um den Binary-Filter ergänzen + Zone-Binary-Sensor-Generator um den per-Zone Loop erweitern (analog zu `get_all_sensor_descriptions`).
- **Kompatibilität**: Integration muss auch mit alter API (binary=False) funktionieren → Integration filtert zusätzlich nach Namens-Endung `_relay` als Fallback. So läuft die Integration auch dann korrekt, wenn Nutzer noch nicht die neue API installiert haben.

---

## Phase 1 — API-Repo (`C:\Users\basti\Documents\GitHub\idm-heatpump-api`)

### Branch
`Codex/issue-128-relay-binary` (per AGENTS.md: keine Commits auf main)

### 1.1 Relay als binär markieren
**Datei:** `idm_heatpump/registers.py` (Zeile 1529-1533)
- `RegisterDef(...)` um `binary=True` ergänzen. Einzeiler, wirkt auf alle 80 Relay-Register via Generator.

### 1.2 Schema-Fixture neu generieren
**Datei:** `tests/fixtures/register_schema_v1.json`
- Wird von `test_register_schema.py:test_register_maps_match_versioned_reference_schema` strict-gegengetestet. Nach 1.1 schlägt der fehl, weil 80 Einträge `binary: true` bekommen.
- Lösung: Fixture mit dem neuen Soll-Stand regenerieren (Skript via `_current_schema()` oder manuell mit dem Test-Helper serialisieren). Keine `schema_version`-Erhöhung nötig — nur Datenänderung.

### 1.3 Neuer Test
**Datei:** `tests/test_registers.py` (in `class TestZoneModules`)
- `test_zone_module_relay_is_binary`: assert `zm1_room1_relay.binary is True` und `writable is False` (read-only binary entspricht der Binary-Sensor-Konfiguration in der Integration).

### 1.4 Changelog
**Datei:** `CHANGELOG.md`
- Eintrag unter neue Version 0.8.1: `fix: mark zone module room relay registers as binary (UCHAR + binary=True)` + Referenz auf Issue #128.

### 1.5 Version bump
**Datei:** `pyproject.toml` (Zeile 15)
- `0.8.0` → `0.8.1`

### 1.6 PR + Merge + Release (API)
- Commit + Push auf Feature-Branch.
- PR-Titel: `fix: mark zone relay registers as binary (closes Xerolux/idm-heatpump-hass#128)`
- Merge nach `main` (Squash, wie bei recent PRs #49/#50).
- Release via `gh release create v0.8.1` ODER Triggern des `release.yml`-Workflows mit `version_mode=custom` + `custom_version=0.8.1`. **Wichtig:** danach `publish.yml` abwarten (PyPI Trusted Publishing auf Tag `v*`).
- Verifikation: `pip show idm-heatpump-api` bzw. `https://pypi.org/pypi/idm-heatpump-api/json` liefert 0.8.1.

---

## Phase 2 — Integration (`C:\Users\basti\Documents\GitHub\idm-heatpump-hass`)

### Branch
`Codex/issue-128-relay-binary-sensor` (neuer Branch vom aktuellen main)

### 2.1 Zone-Sensor-Generator: Binary-Filter + Relay-Fallback
**Datei:** `custom_components/idm_heatpump/library_adapter.py` (Funktion `get_library_zone_sensors`, Zeile 274-295)
- In der Schleife ergänzen: `if reg.binary or name.endswith("_relay"): continue`. Das schließt Relay-Register (egal ob API `binary=True` liefert oder noch die alte `binary=False`) aus der Sensor-Liste aus.

### 2.2 Zone-Binary-Sensor-Generator: pro Zone
**Datei:** `custom_components/idm_heatpump/library_adapter.py` (neue Funktion `get_library_zone_binary_sensors(zone_idx, room_count)`)
- Spiegelbild zu `get_library_zone_sensors`: ruft `_get_zone_module_registers_compat(zone_idx, room_count)` auf und erzeugt für jedes Register, das `binary=True` ODER `name.endswith("_relay")` ist und `writable=False`, ein `BinarySensorEntityDescription`.
- Device-Class via `infer_binary_device_class(name)` (liefert für `relay` aktuell `None` → okay, HA zeigt dann generischen Binary an). Optional: in `adapter_descriptions._BINARY_DC_KEYWORDS` um `("relay", BinarySensorDeviceClass.RUNNING)` ergänzen, damit Relais als "Running" getagged werden. Empfehlung: ja ergänzen, macht UI konsistenter.
- Icon: `get_icon_for_register` hat keinen Relay-Branch → bekommt default `mdi:information-outline`. Optional: Relay-Branch mit `mdi:toggle-switch` ergänzen. Empfehlung: ja.

### 2.3 Binary-Sensor-Dispatcher: Zone-Loop
**Datei:** `custom_components/idm_heatpump/registers.py` (Funktion `get_all_binary_sensor_descriptions`, Zeile 240-260)
- Aktuell ruft diese nur `get_library_binary_sensors(zone_modules=zone_count)` auf. Die Zone-Register kommen dort nicht an, weil die Library `get_zone_module_registers` nur für Sensoren pro Zone gezogen wird (siehe Kommentar registers.py:201-205). Deshalb die neue `get_library_zone_binary_sensors` in einem Loop analog zu Zeile 221-223 einbinden:
  ```
  for z in range(zone_count):
      rooms = zone_rooms.get(z, 6)
      descriptions.extend(get_library_zone_binary_sensors(z + 1, rooms))
  ```

### 2.4 Test-Stub: Relay-Register hinzufügen
**Datei:** `tests/conftest.py` (`_zone_regs`, Zeile 975-988)
- In der Per-Room-Liste ergänzen: `RegisterDef(off + 6, DataType.UCHAR, f"zm{zone_idx}_room{r}_relay", binary=True)`. Damit spiegelt der Stub die neue API und die Relay-Tests haben Daten zum Arbeiten.

### 2.5 Neue Tests
**Datei:** `tests/test_registers.py` (oder `tests/test_platforms.py`)
- `test_zone_relay_not_in_sensor_descriptions`: baue `get_all_sensor_descriptions` mit zone_count=1, zone_rooms={0:2}, assert kein `*_relay`-Key auftaucht.
- `test_zone_relay_in_binary_sensor_descriptions`: baue `get_all_binary_sensor_descriptions` mit gleicher Konfig, assert `zm1_room1_relay` und `zm1_room2_relay` in den Binary-Beschreibungen sind und `writable=False`.
- `test_zone_relay_binary_with_legacy_api` (Kompatibilität): Stub mit `binary=False`, aber Name endet auf `_relay` → muss trotzdem in binary_sensor landen (Fallback-Logik).

### 2.6 Manifest: API-Pin anheben
**Datei:** `custom_components/idm_heatpump/manifest.json` (Zeile 11)
- `idm-heatpump-api[web]==0.8.0` → `==0.8.1`. Per AGENTS.md Versioning-Regel: exakter Pin, getestete Version dokumentieren.

### 2.7 Übersetzungen / Icons (optional je nach 2.2)
**Dateien:** `custom_components/idm_heatpump/icons.json` (nur falls Icon-Branch ergänzt), `strings.json`/`translations/*.json` (nur falls translation_key gesetzt — aktuell synthetisiert der Adapter den Namen "Zone X Raum Y Relais", kein translation_key nötig).

### 2.8 Wiki aktualisieren
**Dateien:** `docs/wiki/Entities.md` (Zeile 307), `docs/wiki/Modbus-Register.md` (Relay-Zeilen Typ-Spalte `UCHAR` → `UCHAR (binary)`)
- Hinweis: Relay-Status jetzt als Binary-Sensor. (wiki-sync.yml pusht das dann ins GitHub Wiki.)

### 2.9 Changelog + Integration-Version
**Datei:** `docs/CHANGELOG.md` + `custom_components/idm_heatpump/manifest.json` (Version-Feld oben)
- Neue Version: `0.8.3` → `0.8.4` (oder `0.9.0` falls du minor bumped — Empfehlung `0.8.4`, da Bugfix).
- Changelog-Eintrag: "fix: expose zone module room relay as binary_sensor (on/off) instead of numeric sensor (0/1). Requires idm-heatpump-api >=0.8.1. Closes #128."

### 2.10 PR + Merge + Release (Integration)
- PR-Titel: `fix: expose zone relay as binary_sensor (closes #128)`
- Nach CI-Grün: Merge nach main (Squash).
- Release: ZIP-Artifact via `release.yml` triggern oder Tag `v0.8.4` + GitHub Release mit HACS-kompatiblen Assets.

---

## Phase 3 — Issue-Antwort

### 3.1 Auf Issue #128 antworten ( Englisch, freundlich, persönlich)
- Inhalt: Dank für den Hinweis, Erklärung dass es root-cause in der Library war (Relay war als UCHAR ohne Binary-Flag definiert), Beschreibung der Änderung (API 0.8.1 + Integration 0.8.4 setzen Relay als binary_sensor mit on/off um), Hinweis dass die Versionen in Kürze über HACS/PyPI verfügbar sind, Bitte um Feedback nach Update.
- **Issue offen lassen** (ausdrückliche Anweisung).

---

## Build Sequence (topologisch)
1. **API-Branch** → API-Code-Änderungen → Fixture neu generieren → Tests lokal grün → API-PR → Merge → API-Release 0.8.1 → PyPI verifizieren.
2. **Integration-Branch** (nach PyPI-Verfügbarkeit von 0.8.1) → Code-Änderungen → Tests → Integration-PR → Merge → Release 0.8.4.
3. **Issue-Antwort** nach erfolgreichem Release.

## Verifikation am Ende
- API: `pytest` im API-Repo grün, `gh release view v0.8.1` existiert, PyPI zeigt 0.8.1.
- Integration: `pytest tests/` grün, `mypy custom_components/idm_heatpump/` grün, `ruff check` grün, `gh release view v0.8.4` existiert.
- Issue #128 hat einen Kommentar von dir, Status bleibt "open".

## Wichtige Sicherheits-Checks
- Keine EEPROM-sensiblen Register berührt.
- Keine Cloud-externen Calls (100% lokal bleibt erhalten).
- Keine hardcoded Modbus-Adressen in Platform-Files (nur Library + const.py).
- Kompatibilitäts-Fallback stellt sicher, dass Integration nicht bricht, falls API 0.8.1 noch nicht installiert ist (ältere HA-Setups, die manuell pinnen).
- Feature-Branches nur, kein direkter Push auf main (per AGENTS.md).

## Offene Punkte, die ich selbst entscheiden werde (mit default)
- Device-Class `RUNNING` für Relay: **ja** (UI-Konsistenz).
- Icon `mdi:toggle-switch` für Relay: **ja**.
- Versionsbump Integration: **0.8.4** (Bugfix-Pfad, konsistent mit 0.8.3).
- Falls du hierran etwas anders sehen willst, korrigiere mich vor Start.