# Plan 02-01 Summary — Writable-Control Creation Gate (#172)

## What was done

Writable Number/Select/Switch entities are now created at setup even when their current value is an unset sentinel, while absent, model-excluded, and Illegal-Data-Address registers stay filtered.

## Changes

- `custom_components/idm_heatpump/entity.py`: `should_add_entity` gained a keyword-only `as_writable_control=False` mode. When True and the register is writable and present in the poll dataset (and not in `unsupported_registers`), it returns True, overriding the sentinel branch. Default behavior (sensors/binary sensors) is byte-for-byte identical.
- `number.py`, `select.py`, `switch.py`: setup calls `should_add_entity(..., as_writable_control=True)`. `sensor.py`/`binary_sensor.py` unchanged.
- `tests/test_entity.py`: `TestWritableControlAvailability` (available under sentinel; unavailable when absent; read-only entities still unavailable under sentinel).
- `tests/test_platforms.py`: `_make_coordinator` defaults `is_register_unused=False`/`unsupported_registers=set()`; repurposed number/switch skip tests to assert creation under sentinel (#172); added `test_skips_absent_register_when_hide_unused_enabled`.

## Verification

`pytest tests/test_entity.py tests/test_platforms.py -q` → green. Read-only sensor filtering unchanged; no Modbus address literals; unique IDs unchanged.

## Requirements covered

GLT-01, GLT-03.
