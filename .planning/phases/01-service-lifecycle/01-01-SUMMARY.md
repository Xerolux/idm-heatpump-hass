# Plan 01-01 Summary — Service Lifecycle (#171)

## What was done

Decoupled the four domain-wide services from the per-config-entry lifecycle so they survive entry reload/unload/remove without a Home Assistant core restart.

## Changes

- `custom_components/idm_heatpump/services.py`: removed `async_unload_services` and the now-unused `_SERVICES` constant. `async_setup_services` (idempotent via `has_service`) is unchanged. `ConfigEntryState` import retained (`_get_coordinator` still uses it).
- `custom_components/idm_heatpump/__init__.py`: removed the lazy import and the `await async_unload_services(hass)` call from `async_unload_entry`. All other unload steps (platform unload, coordinator shutdown, task cancellation, client disconnect) are unchanged.
- `tests/test_services.py`: removed `TestUnloadServices`; added `TestServiceLifecycleInvariants` (exactly-once registration of all four services; idempotent re-registration when already registered).
- `tests/test_init.py`: removed the three `patch(async_unload_services)` blocks; `TestAsyncUnloadEntry` now asserts services are not removed during unload; added `test_services_survive_entry_unload` and `test_services_survive_entry_reload`.

## Verification

`pytest tests/test_init.py tests/test_services.py tests/test_dhw_boost_services.py -q` → green. DHW-Boost lifecycle (separate path via `button.py`) unchanged.

## Requirements covered

LIFE-01, LIFE-02, LIFE-03.
