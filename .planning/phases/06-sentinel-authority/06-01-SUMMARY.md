# Plan 06-01 Summary — API sentinel authority (idm-heatpump-api 0.8.7)

## What was done

- Added `DATATYPE_SENTINEL_DEFAULTS` (`FLOAT` → `(-1.0,)`, `UCHAR` → `(255,)`,
  `UINT16` → `(65535,)`, `INT16` → `(-1, -32768)`) and a computed
  `RegisterDef.effective_sentinel_values` property: explicit `sentinel_values`
  are authoritative; otherwise the datatype default applies.
- Declared explicit `sentinel_values=(-32768, 65535, 255)` on the 10
  pump-status registers where `-1` is a valid "off" reading (previously handled
  by the integration's `NEGATIVE_ONE_VALID_REGISTERS` exception list).
- Regenerated the versioned register-schema fixture.
- 7 new API tests (datatype defaults, explicit override, BOOL/BITFLAG no default,
  pump-status `-1` valid, full numeric coverage).

## Verification

- API: ruff clean; mypy clean (6 files); pytest 306 passed (+17 since 0.8.6).
- Live (read-only bench, API 0.8.7): isolated API probe 11/0/0 — no behavior
  change vs 0.8.6.

## Outcome

The API is now the single source of truth for "unused / not configured"
classification. `effective_sentinel_values` resolves to a non-empty set for every
numeric register, so a consumer never needs a raw numeric heuristic.
