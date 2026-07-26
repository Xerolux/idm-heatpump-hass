# Plan 06-02 Summary — Integration consumes API sentinels (0.8.7)

## What was done

- `IdmCoordinator.is_register_unused` now treats the API's
  `RegisterDef.effective_sentinel_values` as the single authority: if a register
  resolves to a non-empty sentinel set, only those values (plus NaN/inf) count
  as unused. The previous `-1`/`255`/`65535`/`-32768` heuristic and the
  `NEGATIVE_ONE_VALID_REGISTERS` exception list are no longer evaluated.
- A documented enum state (`value in enum_options`) takes precedence over the
  sentinel default — an enum value listed in the register's `enum_options` is
  shown, not hidden.
- Removed the now-unused `UNUSED_VALUE` / `NEGATIVE_ONE_VALID_REGISTERS` imports
  from `coordinator.py` (the constants stay in `const.py` for documentation).
- Updated `tests/conftest.py` stub `RegisterDef` to mirror
  `effective_sentinel_values` + datatype defaults, aligned the stub pump-status
  and `battery_soc` registers with the real API, and reworked the
  `TestIsRegisterUnused` tests to use explicit registers per datatype.

## Verification

- Integration: ruff clean; mypy clean (41 files); pytest 963 passed / 2 skipped.
- Live (read-only bench, API 0.8.7 in HA): 182 entities; the #172 writable GLT
  targets (`hc_a_ext_room_temp`, `ext_humidity`, `ext_outdoor_temp`) stay created
  and available at `-1` with `hide_unused_registers: true`; available count
  146 → 149 (no regression, slight improvement); all 6 domain services present.
- Release contract synced to `idm-heatpump-api[web]==0.8.7`, manifest `0.8.7`,
  user-facing docs updated.

## Outcome

The unused-register filter is now data-driven and device-specific, sourced
entirely from `idm-heatpump-api`. No integration-side numeric literals remain in
the hot path. Behavior on the live Navigator 10 is preserved.
