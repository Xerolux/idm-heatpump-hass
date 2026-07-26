# Plan 02-02 Summary — Available + None-State + Optimistic Write (#172 runtime, #170 setpoints)

## What was done

Writable controls report unknown (None) state under a sentinel while staying available, and a successful write lifts them out of the unknown state immediately via the existing optimistic coordinator update.

## Changes

- `entity.py`: added `_writable_control` class attr, `is_writable_control()`, and `_value_is_sentinel()` (reuses `is_register_unused`, no new sentinel literals). `IdmEntity.available` keeps a present writable control available even when its name is in `unused_registers`.
- `number.py`/`select.py`/`switch.py`: None-state when `is_writable_control() and _value_is_sentinel()`; `IdmSwitch.is_on` now returns `bool | None` (255 no longer renders as `True`). `_writable_control = True` on each platform class.
- `tests/test_platforms.py`: `TestWritableControlSentinelState` (Number/Switch/Select None under sentinel + available; real value shown when not sentinel).
- `tests/test_coordinator.py`: `test_write_lifts_sentinel_state_immediately` — after `async_write_register`, `data[name]` holds the written value and `is_register_unused` no longer classifies it as sentinel, before the next poll.

## Verification

`pytest tests/test_entity.py tests/test_platforms.py tests/test_coordinator.py -q` → green. `unused_registers`/`is_register_unused` remain defensive for read-only and operation analysis.

## Requirements covered

GLT-02, GLT-04, GLT-05, QUAL-01.
