# Hardware Proof — idm_heatpump on a live IDM heat pump

**Date:** 2026-09-09, 18:34 CEST
**Method:** Read-only inspection of the live Home Assistant instance over its
REST API (`/api/`, `/api/config`, `/api/states`, `/api/template`). No service
calls were made, no entity was written, no heat-pump register was written. The
validation complies with the repository rule that real-hardware validation
stays read-only.

## 1. Environment

| Item | Value |
|---|---|
| Home Assistant | 2026.9.1 |
| Instance | Local LAN address (redacted; owner-provided for the session) |
| Auth | Long-lived access token (valid until 2036), owner-provided for this test |
| Total states in HA | 2,586 |
| Repo commit under test | `1493fc621ec9e50c45715cb90f242731f3895366` (main, `v0.17.0-beta.2-1-g1493fc6`, pulled before the probe) |

## 2. Version match: repository vs. installed integration

The integration exposes its runtime identity on
`sensor.alm6_15_idm_heatpump_api_version` (state = `idm-heatpump-api` version,
attributes carry the other versions). Every pin matches the repository
`manifest.json` at the commit above — the running installation **is** the
current `main` build:

| Component | Repo `manifest.json` | Live device | Match |
|---|---|---|---|
| Integration version | `0.17.0-beta.2` | `0.17.0-beta.2` (attribute `integration_version`) | ✅ |
| `idm-heatpump-api[web]` | `==2.0.1` | `2.0.1` (sensor state) | ✅ |
| `modbus-connection` | `==4.11.1` | `4.11.1` (attribute `modbus_connection_version`) | ✅ |
| `tmodbus[async-serial]` | `==0.6.2` | `0.6.2` (attribute `tmodbus_version`) | ✅ |

## 3. Live device identity

| Item | Value |
|---|---|
| Controller | Navigator 10 (`sensor.alm6_15_navigator_version_web`) |
| Firmware | `NAV10_20.24-880-g265e09c4a` (`sensor.alm6_15_software_version_web`) |
| Config-entry device prefix | `alm6_15` (device name configured by the owner) |
| Web supplement | Active — the `*_web` entities report fresh controller data |

## 4. Entity census (proof the integration is fully set up)

`integration_entities('idm_heatpump')` returned **193 entities**, all present in
the live state machine:

| Platform | Count |
|---|---|
| sensor | 109 |
| number | 48 |
| binary_sensor | 22 |
| switch | 4 |
| select | 4 |
| climate | 2 |
| button | 3 |
| water_heater | 1 |
| **Total** | **193** |

Availability: **183/193 available**. The 10 unavailable entities are optional
values the plant does not currently provide — web-diagnostic values the
Navigator 10 does not publish (`Wärmepumpenmodell (Web)`, `Hochdruckstörung
(Web)`, `Laufzeit Kühlen (Web)`, the three `Momentane/prognostizierte Leistung
… (Web)` values), inputs for hardware that is not installed (`Batterie SOC
(Vorgabe)`), defrost-history values with no recorded defrost event since the
last restart (`Letzter Abtaustart`, `Zeit seit letztem Abtaustart`), and the
DHW-boost cancel button with no boost running. None of these indicates a fault;
all Modbus-backed core entities are available.

## 5. Live readings (read at 18:34 CEST)

The `age` column is the time since the value last changed at the moment of the
probe. Analog values re-changing every few seconds is direct evidence of an
active polling cycle (all ages line up on a 10-second raster: 7.7 s, 27.7 s,
77.7 s, 137.7 s — the configured scan interval with per-batch refresh):

| Entity | Value | Age |
|---|---|---|
| `sensor.alm6_15_aussentemperatur` (outdoor temp) | 15.07 °C | 7.7 s |
| `sensor.alm6_15_gemittelte_aussentemperatur` (averaged outdoor) | 19.08 °C | 77.7 s |
| `sensor.alm6_15_luftansaugtemperatur` (air intake) | 12.97 °C | 7.7 s |
| `sensor.alm6_15_heissgastemperatur_web` (hot gas) | 22.9 °C | 854 s |
| `sensor.alm6_15_vorlauftemperatur_hk_a` (flow temp HK A) | 24.12 °C | 7.7 s |
| `sensor.alm6_15_sollvorlauftemperatur_hk_a` (flow setpoint HK A) | 0.0 °C (heating off) | — |
| `sensor.alm6_15_warmepumpen_vorlauftemperatur` (HP flow) | 24.9 °C | 7.7 s |
| `sensor.alm6_15_warmepumpen_rucklauftemperatur` (HP return) | 22.75 °C | 137.7 s |
| `sensor.alm6_15_warmepumpen_spreizung` (HP spread) | 2.15 K | 7.7 s |
| `sensor.alm6_15_trinkwassererwarmer_oben` (DHW top) | 54.92 °C | 27.7 s |
| `sensor.alm6_15_trinkwassererwarmer_unten` (DHW bottom) | 52.69 °C | 7.7 s |
| `sensor.alm6_15_warmespeichertemperatur` (buffer) | 37.76 °C | 7.7 s |
| `sensor.alm6_15_raumtemperatur_hk_a` (room temp, forwarded) | 22.88 °C | 7.7 s |
| `binary_sensor.alm6_15_verdichter_1` (compressor 1) | off | — |
| `select.alm6_15_systembetriebsart` (system mode) | `hot_water_only` | — |
| `sensor.alm6_15_warmepumpen_betriebsart` (HP operating mode) | `Standby` | — |
| `sensor.alm6_15_interne_meldung` (internal message) | `000 - Keine Meldung` (no message) | — |
| `sensor.alm6_15_smart_grid_status` | `Yellow` | — |
| `sensor.alm6_15_warmemenge_gesamt` (total heat energy) | 31,708.66 kWh | — |
| `sensor.alm6_15_warmemenge_heizen` (heating energy) | 27,230.17 kWh | — |
| `sensor.alm6_15_warmemenge_warmwasser` (DHW energy) | 3,474.47 kWh | — |
| `climate.alm6_15` | HVAC `heat` | 418 s |
| `climate.heizkreis_d_heizkreis_d` (HC D) | HVAC `heat` | 3,568 s |
| `water_heater.alm6_15` | `heat_pump` | 288 s |

Operating state is plausible for a mild September day (15 °C outdoor, heating
demand zero, system in `hot_water_only` with a charged 54.9 °C DHW tank and the
compressor idle): the integration correctly mirrors the real plant state.

## 6. Health

- The Modbus polling loop demonstrably refreshes analog values on the ~10 s
  scan raster (section 5); no register-failure warnings were observable from
  the outside.
- `/api/error_log` answers `404 Not Found` on this HA version, so the log file
  could not be exported over REST; health is evidenced instead by the fresh
  polling data and the fully available core entity set.
- The KNX bridge, room-temperature forwarding (`raumtemperatur_hk_a` tracks a
  forwarded room sensor) and the GLT number inputs are part of the entity set.

## 7. Visual evidence

The owner's Lovelace dashboard (`/lovelace/home`) was captured through a real
Chrome render using the same long-lived token for the session (injected as the
frontend's own `hassTokens` storage; the WebSocket session authenticated with
`auth_ok` on HA 2026.9.1):

- `screenshots/dashboard_home_top.png` — the live "Übersicht" dashboard. Shows
  the owner's heat-pump cards for the **Wärmepumpe ALM6-15**: outdoor
  temperature 15.1 °C, DHW 54.9 °C, flow temperature 24.1 °C and further live
  values matching the API readings in section 5, rendered by the installed
  custom cards (mini-graph-card, multiple-entity-row, custom-sidebar).
- Browser console during capture confirms the dashboard stack initialized
  (`MINI-GRAPH-CARD`, `MULTIPLE-ENTITY-ROW`, `BROWSER_MOD`, `CUSTOM-SIDEBAR`,
  `STATE-SWITCH`).

The dashboard render is additional evidence that the 193 entities are not just
present in the state machine but actively drive the owner's UI.

## 8. Evidence files

| File | Content |
|---|---|
| `evidence/probe_summary.json` | API/config responses, entity census, platform counts |
| `evidence/idm_states_full.json` | Full raw state objects of all 193 entities (incl. version attributes) |
| `evidence/idm_states_compact.json` | entity_id / state / unit / friendly_name / age / availability |
| `screenshots/dashboard_home_top.png` | Live dashboard render (see section 7) |

## 9. Verdict

The `idm_heatpump` integration **version 0.17.0-beta.2 (repo main
`1493fc6`)** is running against a real IDM heat pump controlled by a
Navigator 10, exposes 193 entities of which all core entities are available,
polls the device live on a ~10 s cycle, and reports physically plausible
readings for the current weather and season. Repository pins and the installed
runtime match exactly. The whole validation was read-only.

*Credentials note: the access token used for this probe was provided by the
owner, is stored only in a local temp file, and is not included in any evidence
file.*
