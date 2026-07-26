# Plan 05-01 Summary — Navigator 10 live validation, detection fix, 0.8.6-beta.2

## What was done

- **Read-only Docker test bench** added under `docker/live-readonly-test/`:
  three proxies (Modbus FC01–04; HTTP GET/HEAD + 3 login POSTs; Nav10 WebSocket
  read-commands only), Home Assistant with the local integration mounted and the
  local `idm-heatpump-api` wheel force-installed, an api-tester container, and
  build/start/stop/clean/run_probe scripts + README + `.env.example`.
- **Live defect found and root-caused (MODEL-03 resolved):** the test device is a
  Navigator 10 (web title `NAV 10`, Nav10 WebSocket firmware
  `NAV10_20.24-880-g265e09c4a`, Nav10-only registers 4122/4126 respond), but
  `detect_model()` classified it as `Navigator 2.0` because `power_limit_hp`
  (4108) is unplausible in standby and `booster_fault` (4001) returns the
  `255` "no booster" sentinel — so after the 0.8.5 booster-sentinel tightening no
  Nav10 indicator remained for a booster-less standby Nav10.
- **Correction at the root (MODEL-04 resolved):** `idm-heatpump-api` 0.8.6 adds a
  strict tertiary indicator — the Navigator-10-only registers
  `power_consumption_hp` (4122) and `thermal_power_flow_sensor` (4126) must BOTH
  respond. Navigator 2.0 / IDM Terra SWM reject them with Modbus Exception 2, so
  the Terra-SWM safeguard (#44/#65) is preserved. 4 new regression tests added.
- **Integration bump:** manifest `0.8.6-beta.2`, pin `idm-heatpump-api[web]==0.8.6`;
  contract test + user-facing docs synced; CHANGELOG entry added.
- **Release artifacts (local only):** `release/idm_heatpump-0.8.6-beta.2.zip` +
  `.sha256`, `idm_heatpump_api-0.8.6…whl`, `release-evidence-0.8.6-beta.2.md`.

## Live verification evidence

| Check | Result |
|---|---|
| API isolated (Modbus + Nav10 WS + single/batch + sentinel + write-block) | 11/0/0 PASS |
| Modbus model detection (post-fix) | `Navigator 10` (was `Navigator 2.0`) |
| Web ↔ Modbus model consistency | agree, `conflict: false` |
| #171 service lifecycle | 6/6 services after 3 config-entry reloads |
| #172 writable sentinel targets | `hc_a_ext_room_temp`, `ext_humidity`, `ext_outdoor_temp` created + available (state `unknown`) at `-1` with `hide_unused_registers: true` |
| Stability (60 min) | 120 samples, 0 errors, entity count stable |
| Read-only proof | 5 Modbus FC06 + 3 WS `setting/save` blocks — all synthetic; 0 writes from HA |

## Automated gate

- Integration: ruff clean; mypy clean (41 files); pytest 963 passed / 2 skipped.
- API: ruff clean; mypy clean (6 files); pytest 289 passed (incl. 4 new).

## Open checkpoints closed

- MODEL-03 / MODEL-04 (Phase 3 evidence-gated) → **resolved** with field evidence
  and the exact-pinned API 0.8.6 release.
- Release action (version/tag/ZIP/SHA) → **done** as `0.8.6-beta.2` (local only,
  not pushed, no PR, no GitHub release).

## Deferred (next milestone)

- Sentinel heuristics (`-1`/`255`/`65535`) → move to API as declared
  `sentinel_values` per `RegisterDef`.
- 4108 standby decode (`leistungsbegrenzung_*` unavailable).
- `hide_unused_registers` long-term simplification.
