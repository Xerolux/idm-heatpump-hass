# Code Audit and Improvement Plan (September 2026)

Last updated: 2026-09-08
Audited revision: `main` at `5065bba` (integration `0.16.2`, `idm-heatpump-api[web]==2.0.0`,
`modbus-connection==4.10.0`, `tmodbus[async-serial]==0.6.2`).

This document records every defect, weakness and cleanup opportunity found in a full read of
the integration, and for each one states what to change, how, why, and how to prove it.

**Status: most of it is implemented.** Every bug (A1–A8), every robustness item (B1–B6) and
every performance item (C1–C3) has been fixed on
`claude/fehlersuche-optimierung-doku-clobcn`, together with the cleanups D1, D4, D6 and D7.
See the "Implementation status" table below for what remains and why. The per-package
descriptions are kept as written: they are the reasoning the changes rest on, and the
remaining packages are still work orders.

## Implementation status

| Package | Status | Notes |
| --- | --- | --- |
| A1–A8 | done | All eight bugs fixed, each with a test that fails without the fix. |
| B1–B6 | done | Includes the per-circuit `hvac_action`; the API does expose `hc_<x>_active_mode`, so B6's "verify first" resolved in favour of fixing it. |
| C1–C3 | done | The suite went from ~33 s to ~10 s. |
| D1 | done | Every shim for an API older than the exact pin removed. |
| D4 | done | One shared translated-write helper for all five writable platforms. |
| D6 | done | Module headers, comments and docstrings are English; the German display-name tables and the German fragments the register-name matching searches for stay. |
| D7 | done | Plus a test that fails when a module or test file is missing from `AGENTS.md`. |
| D2 | open | Encapsulating the coordinator's private attributes touches nearly every module for no user-visible gain. Worth doing, but as its own change with its own review. |
| D3 | open | Extracting model resolution is a day of work on the logic that decides which register map a controller gets. It deserves an unhurried change, not a tail-end one. |
| D5 | **attempted, reverted** | Folding `HumidityForwarder` into the keyed forwarder does not merge as cleanly as this document assumed: the humidity forwarder has its own public surface (`async_forward()`, a single entity rather than a key map) that `__init__.py` and the tests use. Wrapping it to preserve that surface restores most of the code the merge was meant to remove. Left as two classes; the docstring at the top of `room_temp_forwarding.py` already explains the split. |
| E1 | open | The one item whose absence still hides bugs. A cheaper half of it landed instead: the suite now validates against the real voluptuous when it is installed, which immediately caught three assertions written against the stub. A real-Home-Assistant smoke tree remains the right next step. |

Two findings surfaced while implementing that this audit had not recorded:

- The KNX bridge was stored on `runtime_data` only after a successful
  `async_start()`, so a bridge that failed partway through — having already
  registered demand and listeners — was unreachable for any cleanup. Fixed with B1.
- `_entry_host` in `config_flow.py` repeated the `isinstance` guard its only caller
  performs, leaving a branch no test could reach. Removed with A5.


## How to use this document

- **Work package by package.** Every package (`A1`, `B3`, …) is independent unless its
  "Depends on" line says otherwise. For the packages still open, one package = one pull
  request; do not bundle.
- **Read the "Verify first" line before coding.** Some findings rest on Home Assistant or
  API behaviour that was read from source but not executed here. The line names the exact
  thing to confirm; if it does not hold, stop and report instead of forcing the change.
- **Keep the repository contracts.** `AGENTS.md` is binding: English everywhere, strict mypy,
  ruff, the coverage gates (95 % overall, 100 % for `config_flow.py`), no register addresses
  in platform files, no second Modbus transport, no cloud calls. Device semantics belong in
  `idm-heatpump-api`; the fixes below never move register knowledge into this repository.
- **Every package ends with a test.** The suite stubs the whole `homeassistant` package
  (`tests/conftest.py`), so a change that only "looks right" is not proven. Each package lists
  the test to add. Add it in the file the package names.
- **Every package ends with a changelog line** under `## [Unreleased]` in
  `docs/CHANGELOG.md` (English; see the language rule).
- **Severity scale.** `bug` = wrong behaviour a user can hit today; `robustness` = correct in
  the happy path, fails or degrades under realistic conditions; `performance` = measurable
  waste; `cleanup` = maintainability, no behaviour change; `docs` = documentation drift.

## Baseline measured on the audited revision

Measured with Python 3.13 and the real pinned API installed, Home Assistant stubbed as in CI:

| Check | Result |
| --- | --- |
| `ruff check custom_components tests` | clean |
| `ruff format --check` | clean (97 files) |
| `pytest tests/` | 1576 passed, 34.8 s |
| Coverage (whole package) | 95 % (gate: 95 %) |
| Coverage `config_flow.py` | 100 % (gate: 100 %) |
| Lowest module coverage | `internal_messages.py` 79 %, `library_adapter.py` 89 %, `__init__.py` 90 % |
| Slowest tests | 7 × `tests/test_pages_seo.py` setups at 2–3 s each, `test_incomplete_data_skips_register` 3.0 s |

The suite is green, so nothing below is "the build is broken". The findings are about what
the suite cannot see because Home Assistant is stubbed, about cross-feature interactions,
and about code that outlived the API version it was written for.

## Priority overview

| ID | Severity | Area | One-line summary |
| --- | --- | --- | --- |
| A1 | bug | coordinator | `async_shutdown` override skips the base class, so the scheduled refresh survives unload |
| A2 | bug | polling plan / KNX | Entity-aware polling starves the KNX bridge and the KNX export of registers whose entities are disabled |
| A3 | bug | coordinator | The `register_not_supported` repair issue can never be raised with API 2.0: the bisect path is dead code |
| A4 | bug | forwarding | Room temperature forwarding ignores the source sensor's unit (°F is written as °C) |
| A5 | bug | config flow | Duplicate check keys on host only, so two units behind one Modbus proxy cannot both be added |
| A6 | bug | sensor | Unknown enum values render the German literal `Unbekannt (…)`; enum device class may reject it |
| A7 | bug | DHW boost | User-visible fallback error texts are German |
| A8 | bug | climate / water heater | `current_temperature` returns sentinel values (NaN/inf/-1) as a state |
| B1 | robustness | setup | Raising after `async_forward_entry_setups` leaves platforms loaded on a failed entry |
| B2 | robustness | coordinator / polling plan | Untracked `asyncio.create_task` background work |
| B3 | robustness | web supplement | No backoff, no timeout, rejected PIN retried every cycle |
| B4 | robustness | DHW boost | Enforcement re-writes on every poll and logs a warning each time the cooldown blocks it |
| B5 | robustness | services | Services registered without schemas; DHW boost services registered from a platform |
| B6 | robustness | climate | `hvac_action` reports the plant status for every circuit |
| C1 | performance | polling plan | Registry listener re-plans on unrelated integrations' events |
| C2 | performance | tests | `test_pages_seo.py` rebuilds the Pages artifact per test; one test sleeps 3 s |
| C3 | performance | coordinator | Polling jitter also delays write-confirmation refreshes |
| D1 | cleanup | all | Compatibility shims for API < 2.0 are dead with an exact pin |
| D2 | cleanup | all | Cross-module access to coordinator private attributes |
| D3 | cleanup | setup | `async_setup_entry` model reconciliation (≈250 lines) is untestable as a unit |
| D4 | cleanup | entities | Three copies of the translated-write-error wrapper |
| D5 | cleanup | forwarding | `RoomTempForwarder` and `HumidityForwarder` duplicate the loop, debounce and teardown |
| D6 | cleanup | all | German module headers and German literals in code |
| D7 | docs | AGENTS.md / ci.yml | Module list, test list, API version and branch convention are stale |
| E1 | robustness | tests | The coordinator stub hides lifecycle bugs; add a real-Home-Assistant smoke leg |

Recommended order: A1, A2, A3, B1 (they touch the same lifecycle code and stack cleanly),
then A4–A8, then B2–B6, then D1–D3 (which shrink the code the rest touches), then the rest.

---

## A. Bugs

### A1. Coordinator shutdown skips the base class

- **Severity:** bug
- **Files:** `custom_components/idm_heatpump/coordinator.py:1299-1313`
  (`IdmCoordinator.async_shutdown`), `custom_components/idm_heatpump/__init__.py:1109-1116`
  (`async_unload_entry` calls it), `tests/conftest.py:580-600` (`_DataUpdateCoordinator` stub).
- **Problem.** `IdmCoordinator.async_shutdown` cancels the delayed-refresh task and closes
  the web client pool, but never calls `await super().async_shutdown()`. In Home Assistant,
  `DataUpdateCoordinator.async_shutdown` is what unsubscribes the scheduled refresh timer,
  shuts down the request-refresh debouncer and sets the shutdown flag. Without it, the timer
  armed by the last poll fires after the entry is unloaded and the Modbus client is
  disconnected. The result is a poll against a closed transport, a spurious
  `cannot_connect` repair issue for an entry that no longer exists, and a reference that keeps
  the coordinator alive. Reloading the entry (any options change) creates a second, live
  coordinator next to the zombie.
- **Why the suite does not see it.** The stub `_DataUpdateCoordinator` in `conftest.py` has no
  `async_shutdown`, no timer and no `_async_unsub_refresh`, so `super()` behaviour is invisible.
- **Verify first.** Open `homeassistant/helpers/update_coordinator.py` of HA 2026.8.1 and
  confirm `async_shutdown` exists on `DataUpdateCoordinator` and what it unsubscribes. Also
  confirm whether HA already calls it on unload via `config_entry.async_on_unload`; if it does,
  the explicit call in `async_unload_entry` is fine to keep (it is idempotent) but the missing
  `super()` still matters because the override replaces the base behaviour entirely.
- **Fix.**
  1. In `async_shutdown`, call `await super().async_shutdown()` first, then the existing
     task cancellation and pool close. Keep the order: base class first so no new refresh can
     be scheduled while the pool is being closed.
  2. In `tests/conftest.py`, give the stub an `async def async_shutdown(self)` that sets
     `self.shutdown_called = True` and `self._shutdown_requested = True`, and make the stub's
     `async_request_refresh` raise if `_shutdown_requested` is set (mirrors HA's behaviour of
     ignoring refreshes after shutdown).
  3. Test in `tests/test_coordinator.py`: build a coordinator, call `async_shutdown`, assert
     `shutdown_called`, assert the web pool is closed, assert a pending delayed-refresh task
     was cancelled. Test in `tests/test_init.py`: after `async_unload_entry`, assert the
     coordinator's `shutdown_called` is `True`.
- **Effort:** small (½ h). **Depends on:** nothing. Pairs with E1.

### A2. Entity-aware polling starves the KNX bridge and the KNX export

- **Severity:** bug (silent functional loss)
- **Files:** `custom_components/idm_heatpump/polling_plan.py:20-34` (`_ALWAYS_REQUIRED`),
  `polling_plan.py:193-231` (`_async_apply_plan` replaces `coordinator._registers`),
  `custom_components/idm_heatpump/knx_bridge.py:191-199` (`_resolve`), `knx_bridge.py:356-380`
  (`_handle_coordinator_update`), `knx_bridge.py:480-492` (read-request answer),
  `custom_components/idm_heatpump/services.py:498-503` (`export_knx_group_addresses`).
- **Problem.** Entity-aware polling shrinks the polled register set to what enabled entities
  need plus a hard-coded `_ALWAYS_REQUIRED` list. The KNX bridge serves values by reading
  `coordinator.data`; after the plan is applied (one second after setup), any register whose
  Home Assistant entity the user disabled is no longer in the snapshot. `_handle_coordinator_update`
  then skips it (`value is None`), read requests on its group address go unanswered, and the
  bridge never says why. The wiki recommends disabling unused entities to relieve the
  controller, so this is the normal configuration for a KNX user, not an edge case. The same
  applies to the `export_knx_group_addresses` service: it derives "available registers" from
  `coordinator.data`, so the export shrinks with the entity selection.
  `docs/wiki/Changelog.md:338` records that calculated sensors had this exact failure mode
  before; the fix then was a per-consumer dependency table (`_CALCULATED_DEPENDENCIES`), which
  does not scale to a consumer with 654 objects.
- **Fix.** Replace the hard-coded list with a demand registry on the coordinator:
  1. In `coordinator.py`, add `register_required_registers(owner: str, names: Iterable[str]) -> Callable[[], None]`
     that stores `frozenset(names)` under `owner` in a dict and returns an unsubscribe callable,
     plus a property `externally_required_registers -> frozenset[str]` that unions them.
  2. In `polling_plan.py`, `build_required_register_names` takes the union as an extra
     parameter (keep `_ALWAYS_REQUIRED` for the coordinator's own needs; move the DHW boost
     registers there via a registration from `DhwBoostManager.__init__` instead of the literal
     names). Any change to the demand set must re-apply the plan: have the registration call
     the manager's debounced apply, the same path the registry listener uses.
  3. In `knx_bridge.py`, after `_resolve()` has produced `self._objects`, register every
     object register with the coordinator; unregister in `async_stop`. `_resolve()` must decide
     availability from the coordinator's full register set (`coordinator.get_register(name) is not None`
     and `name not in coordinator.unsupported_registers`), not from the current snapshot, so
     the plan cannot influence which objects exist.
  4. In `services.py` (`export_knx_group_addresses`), derive `available` the same way (full
     register set minus unsupported), not from `coordinator.data`.
  5. Room/humidity/storage forwarding only write, so they need no demand. Operation analysis
     already works from `_ALWAYS_REQUIRED`; leave it.
- **Tests.** `tests/test_polling_plan.py`: a registered demand keeps a register whose entity is
  disabled; unregistering drops it again; registering triggers a re-plan.
  `tests/test_knx_bridge.py`: with a plan that excludes an object's register, the bridge still
  publishes it after the next poll (the plan now includes it). `tests/test_knx_group_address_export.py`:
  the export is identical before and after the plan shrinks the snapshot.
- **Docs.** Add one sentence to `docs/wiki/KNX-Bridge.md` and `docs/wiki/Troubleshooting.md:188`:
  registers served on KNX are polled regardless of entity state.
- **Effort:** medium (3–4 h). **Depends on:** D2 is helpful (public API instead of
  `coordinator._registers`) but not required.

### A3. The `register_not_supported` repair issue is unreachable with API 2.0

- **Severity:** bug (missing user feedback) plus dead code
- **Files:** `coordinator.py:545-585` (`_async_read_registers_resilient`),
  `coordinator.py:587-616` (`_merge_unsupported_registers`), API
  `idm_heatpump/client.py:1458-1490` (`read_batch`) and its `_read_individual_fallback`.
- **Problem.** The coordinator bisects a batch on Modbus exception code 2 and raises a
  repair issue plus a warning when it isolates one register. But `read_batch` in API 2.0.0
  already catches `IdmDeviceError` per group, falls back to individual reads, and records
  the offending register in `_permanently_failed_registers` — the exception never leaves the
  library. So the bisection never runs, and the only thing that happens for an unsupported
  register is a `debug` line in `_merge_unsupported_registers`. Users never see the
  `register_not_supported` issue that `strings.json` promises, and the entity silently
  becomes unavailable. Line 590's own docstring already states that the library swallows
  the exception; the code just was not updated to match.
- **Verify first.** Read `_read_individual_fallback` in the installed API and confirm that a
  code-2 response marks the register in `_permanently_failed_registers` and does not
  re-raise. Confirm `get_unsupported_registers()` returns those names.
- **Fix.**
  1. Move the repair-issue creation and the warning from the `len(readable) == 1` branch into
     `_merge_unsupported_registers`, once per newly discovered register (it already computes
     `new_unsupported`).
  2. Reduce `_async_read_registers_resilient` to: filter the skip-list, call `read_batch`,
     re-raise. Keep the `IdmModbusError` → illegal-address check only in
     `_async_refresh_zone_room_modes`, where `read_register` really can raise it.
  3. Delete `_ILLEGAL_ADDRESS_MARKERS` string matching if `IdmModbusError.is_illegal_address`
     is always present in API 2.0 (check `idm_heatpump/exceptions.py:72-79`); otherwise keep
     the helper but drop the string fallback.
  4. Remove the `translation_placeholders` for `address` only if the register set exposes it;
     `RegisterDef.address` does, so keep the placeholder.
- **Tests.** `tests/test_coordinator.py`: a client whose `get_unsupported_registers()` returns a
  new name after a poll → exactly one `async_create_issue` call with
  `register_not_supported_<name>` and one warning; a second poll with the same name → no
  duplicate issue. Delete the tests that exercised the bisection recursion (they lock in dead
  behaviour), or keep one for the zone-room single-read path.
- **Effort:** small (1–2 h). **Depends on:** nothing.

### A4. Room temperature forwarding ignores the sensor's unit

- **Severity:** bug (wrong value written to the controller)
- **Files:** `custom_components/idm_heatpump/room_temp_forwarding.py:48-56`
  (`_coerce_temperature`), `room_temp_forwarding.py:178-187` (`async_forward_entity`),
  `room_temp_forwarding.py:189-243` (`_async_write_circuit`).
- **Problem.** The forwarder takes `state.state`, parses it as a float and writes it to the GLT
  room-temperature register, which the API defines in °C. A sensor reporting in °F (a US
  Home Assistant instance, or a device that only reports °F) forwards 68 °F as 68 °C. The
  register bounds do not catch it: 68 is inside the plausible °C range of such registers, so
  the controller receives a room temperature that is more than 40 K too high and will stop
  heating that circuit. `min_val`/`max_val` protection is not a substitute for unit handling.
- **Fix.**
  1. Read `unit = state.attributes.get("unit_of_measurement")`. When it is one of
     `UnitOfTemperature.FAHRENHEIT` / `UnitOfTemperature.KELVIN`, convert with
     `homeassistant.util.unit_conversion.TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)`.
     When it is Celsius or missing, keep the value (missing keeps today's behaviour for
     template sensors without a unit). When it is something else (`%`, `W`, …), skip with one
     warning per entity: the user picked the wrong entity.
  2. Apply the same for storage temperature forwarding (it reuses `RoomTempForwarder`); the
     humidity forwarder needs only the "unit must be `%` or missing" check.
  3. `conftest.py` may need `unit_conversion` in the stubbed `homeassistant.util` tree; add a
     minimal `TemperatureConverter` with `convert` implementing the three units.
- **Tests.** `tests/test_room_temp_forwarding.py`: a state `68` with unit `°F` writes `20.0`;
  unit `K` converts; unit `%` is skipped with a warning; no unit passes through.
- **Effort:** small (1 h). **Depends on:** nothing; D5 would let the fix land once for both
  forwarders.

### A5. Duplicate detection blocks legitimate second units behind one host

- **Severity:** bug (setup blocked)
- **Files:** `custom_components/idm_heatpump/config_flow.py:882-895` (`_has_duplicate_host`),
  `config_flow.py:1250-1262` (user step), `config_flow.py:1384` (connection/reconfigure step),
  `custom_components/idm_heatpump/modbus_transport.py` (`ModbusTcpEndpoint.connection_key`).
- **Problem.** The user step first rejects the input with `already_configured` when any entry
  has the same host, and only afterwards calls `_async_abort_entries_match` on host + port +
  slave ID. The stricter match is unreachable. Two heat pumps reached through one Modbus TCP
  proxy on different ports, or two units on one gateway with different unit IDs (a cascade
  with separate Navigator units), cannot both be configured. The transport already defines
  the right identity: `ModbusTcpEndpoint.connection_key` is `(host, port, slave_id)`.
- **Fix.**
  1. Change `_has_duplicate_host` to `_has_duplicate_endpoint(hass, host, port, slave_id, current_entry_id)`
     comparing the normalised triple. Reuse the normalisation from `ModbusTcpEndpoint`
     (`host.strip().lower()`), do not write a third one.
  2. Call it with the parsed port and slave ID in both the user step and the connection step.
     Keep `_async_abort_entries_match` (it aborts rather than errors, which is the right
     behaviour when the exact triple matches).
  3. Web-only entries: compare on the web host too (`CONF_WEB_HOST`), because two web-only
     entries for one Navigator are equally wrong.
- **Tests.** `tests/test_config_flow.py`: same host + different port succeeds; same host + same
  port + same slave ID aborts; same host + different slave ID succeeds; reconfigure of the
  current entry to its own triple is allowed. Coverage of `config_flow.py` must stay 100 %.
- **Docs.** `docs/wiki/Configuration.md`: one sentence that an endpoint is host + port + unit ID.
- **Effort:** small (1 h). **Depends on:** nothing.

### A6. Unknown enum values render a German literal and may break enum sensors

- **Severity:** bug
- **Files:** `custom_components/idm_heatpump/sensor.py:537-552` (`native_value`).
- **Problem.** When a register with `enum_options` reports a value the map does not contain,
  and no slug map exists, the sensor state becomes `Unbekannt (<value>)`. That is German in
  code (rule violation) and, for a sensor with `device_class: enum` and `options`, a value
  outside `options` makes Home Assistant raise `ValueError` on state write, which logs an
  error on every update. Where a slug map exists the code returns `None` (correct).
- **Fix.** Return `None` in the fallback branch too and emit one `debug` line per register and
  value ("unmapped enum value") using a small `set` on the entity to avoid repeats. If the
  raw value is worth exposing, put it in `extra_state_attributes["raw_value"]`.
- **Tests.** `tests/test_platforms.py`: enum register with an unmapped value → state `None`,
  attribute carries the raw value, log at debug only.
- **Effort:** small (½ h). **Depends on:** nothing.

### A7. German error texts in the DHW boost manager

- **Severity:** bug (language contract) — low user impact, because the translation key is what
  Home Assistant shows, but the literal appears in logs and in `str(err)` inside
  `dhw_boost_restore_failed` details.
- **Files:** `custom_components/idm_heatpump/dhw_boost.py:363-370`, `:377-386`, `:397-404`.
- **Fix.** Replace the three literals with English ("Stored recovery state is incomplete",
  "The previous domestic hot water state could not be fully restored yet", "Register {name}
  is not writable"). No behaviour change.
- **Tests.** Existing tests assert on translation keys; add `assert "ist" not in str(err)` is
  not meaningful — instead extend `scripts/check_documentation_language.py` per D6 so this
  cannot recur.
- **Effort:** trivial. **Depends on:** nothing.

### A8. `current_temperature` leaks sentinel values into the state

- **Severity:** bug (wrong state shown)
- **Files:** `custom_components/idm_heatpump/climate.py:121-133` (`available`),
  `climate.py:161-175` (`current_temperature`, `target_temperature`),
  `custom_components/idm_heatpump/water_heater.py:87-117`.
- **Problem.** `available` checks only the mode and target registers against
  `coordinator.unused_registers`. `current_temperature` returns `float(val)` for the current
  register without that check, so an unused room sensor (sentinel per the API, often NaN,
  inf or −1) is displayed as a temperature; NaN in particular makes the climate card show
  `nan`. The water heater has the same shape with `dhw_temp_top`.
- **Fix.** In both properties, return `None` when the register is in
  `coordinator.unused_registers` or when the float is not finite. Keep availability as is
  (a circuit without a room sensor is still a valid climate entity; the current temperature
  is simply unknown).
- **Tests.** `tests/test_platforms_climate.py` and `tests/test_platforms.py` (water heater):
  snapshot with the current-temperature register in `unused_registers` → `current_temperature is None`
  and `available` unchanged.
- **Effort:** small (½ h). **Depends on:** nothing.

---

## B. Robustness

### B1. Failure after platform forwarding leaves platforms loaded

- **Severity:** robustness (entry ends in `setup_error` with live entities)
- **Files:** `custom_components/idm_heatpump/__init__.py:952-1090` (from
  `await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)` to the end of the
  `try`), `__init__.py:1041-1080` (KNX bridge start), `__init__.py:498-518` (web-only path).
- **Problem.** After the platforms are forwarded, setup still constructs the forwarders and
  starts the KNX bridge. Only `InvalidGroupAddressError` is caught there. Any other exception
  (the `knx` integration raising from `async_start`, a `ValueError` from a malformed option
  such as a non-numeric interval) propagates to the outer `except Exception`, which
  disconnects the client and re-raises. Home Assistant then marks the entry failed, but the
  eight platforms and their entities stay registered against a coordinator whose client is
  closed. The next poll fails for every entity, the user sees a wall of unavailable entities
  plus a `cannot_connect` issue, and a retry is not scheduled because the exception was not
  `ConfigEntryNotReady`. Home Assistant's own guidance is to raise only before forwarding.
- **Fix.**
  1. Restructure `async_setup_entry` so that everything that can fail runs **before**
     `async_forward_entry_setups`: build the forwarders and the bridge config, validate the KNX
     base address (`resolve_group_addresses` is pure and can run early), and only after
     forwarding start the background tasks (which cannot raise synchronously).
  2. Wrap the post-forward section anyway: on any exception, call
     `await hass.config_entries.async_unload_platforms(entry, PLATFORMS)` and cancel the tasks
     already created before re-raising. A helper `_async_teardown_partial_setup(hass, entry)`
     that reuses the body of `async_unload_entry` avoids a second copy.
  3. Convert option parsing (`int(entry.options.get(...))` × 30) into one function
     `_entry_settings(entry) -> IdmEntrySettings` (a frozen dataclass) that raises
     `ConfigEntryError` with a translation key on malformed data. This is also the seam D3
     needs.
- **Tests.** `tests/test_init.py`: a KNX bridge whose `async_start` raises `RuntimeError` →
  `async_setup_entry` raises, `async_unload_platforms` was called, the client is disconnected,
  no background task is left running.
- **Effort:** medium (2–3 h). **Depends on:** nothing; D3 builds on the same seam.

### B2. Untracked background tasks

- **Severity:** robustness
- **Files:** `coordinator.py:1257-1264` (`asyncio.create_task(self._delayed_refresh())`),
  `polling_plan.py:147-149` (`_schedule_shutdown` fire-and-forget),
  `__init__.py:214-233` (`_create_entry_background_task` helper).
- **Problem.** Home Assistant tracks tasks created through `hass.async_create_task` or
  `entry.async_create_background_task` so it can cancel them on unload and wait for them at
  shutdown; bare `asyncio.create_task` is invisible to that machinery. The coordinator's
  confirmation refresh is bare (the comment says "so unit tests can await the real Task",
  which is a test concern leaking into production code). The polling manager's shutdown
  schedules `async_shutdown()` without awaiting it, so unload can complete while the
  registry listener is still attached and a debounced re-plan can still call
  `async_request_refresh` on a shut-down coordinator.
- **Fix.**
  1. Move `_create_entry_background_task` into a small `tasks.py` (or `helpers.py`) module and
     use it from the coordinator: `self.config_entry.async_create_background_task(self.hass, coro, name=f"{DOMAIN}_confirm_refresh_{entry_id}")`
     with the existing fallback for mocks.
  2. In `polling_plan.py`, register `async_shutdown` directly with
     `entry.async_on_unload` (it accepts coroutine functions in current Home Assistant; verify
     in `config_entries.py`); otherwise store the task and await it from
     `IdmCoordinator.async_shutdown` (A1).
  3. `_delayed_refresh` swallows `CancelledError`; let it propagate (cancellation must not be
     hidden from the task machinery).
- **Tests.** `tests/test_coordinator.py`: after `async_write_register`, the created task is the
  one returned by the entry's `async_create_background_task` stub. `tests/test_polling_manager.py`:
  after unload, the registry unsubscribe was called before the test continues (no task left).
- **Effort:** small (1–2 h). **Depends on:** A1.

### B3. Web supplement: no backoff, no timeout, PIN retried every cycle

- **Severity:** robustness
- **Files:** `__init__.py:384-393` (`_web_poll_loop`), `coordinator.py:849-910`
  (`async_refresh_web_supplement`), `custom_components/idm_heatpump/web_data.py:504-628`
  (`async_read_web_supplement`), `__init__.py:775-800` (setup-time web read).
- **Problem.** (1) The loop sleeps the configured interval whether the read succeeded or not.
  A Navigator that is off, or a wrong web host, is retried forever at full rate; each attempt
  tries the WebSocket and HTTP variants and pays their connect timeouts. (2) A rejected PIN
  is retried every cycle. Navigator firmware locks the local login after repeated failures,
  and the integration is the one producing them; the repair issue tells the user to re-enter
  the PIN, while the loop keeps burning attempts. (3) No `asyncio.timeout` bounds
  `client.read_data()` at the integration level; the setup-time read in `async_setup_entry`
  therefore blocks entry setup for as long as the API client's own timeouts allow, which
  delays every entity.
- **Fix.**
  1. In `_web_poll_loop`, track consecutive failures and sleep `min(interval * 2**failures, 10 * interval)`;
     reset on success. Expose the current backoff in diagnostics.
  2. On `IdmWebAuthenticationFailed`, stop polling until the entry is reloaded (which happens
     when the user fixes the PIN through the repair flow or reconfigure). Implement as a flag
     on the coordinator (`web_auth_blocked`) checked by the loop; log once.
  3. Wrap every `read_data()` / notifications read in `async with asyncio.timeout(WEB_READ_TIMEOUT)`
     with a constant in `const.py` (suggest 15 s, above the API's connect timeout, below the
     default web interval). Treat `TimeoutError` as a transport failure (it already maps to
     `web_timeout`).
  4. At setup, run the web read with a shorter timeout (suggest 8 s) and let the loop finish
     detection later; setup must not wait on the optional supplement.
- **Tests.** `tests/test_init.py`: loop sleeps grow after failures and reset after success;
  after an authentication failure the loop makes no further calls. `tests/test_web_data.py`:
  a `read_data` that never returns raises `TimeoutError` within the bound.
- **Effort:** medium (2 h). **Depends on:** nothing.

### B4. DHW boost enforcement fights the write cooldown and spams warnings

- **Severity:** robustness (log noise, wasted writes)
- **Files:** `custom_components/idm_heatpump/dhw_boost.py:318-337` (`_async_evaluate`
  enforcement), `coordinator.py:1097-1140` (`_record_write_error` logs at `warning`),
  `coordinator.py:1195-1210` (cooldown raises `HomeAssistantError`), API
  `client.py:1400-1410` (EEPROM write interval).
- **Problem.** While a boost is active, every coordinator update compares the snapshot with
  the target and re-writes `dhw_setpoint` / `system_mode` when they differ. The controller
  often reports the previous value for one or two polls after a write, and the API refuses a
  second write to an EEPROM register within `eeprom_write_interval` (60 s), while the
  coordinator refuses within `write_cooldown` (5 s). Each refusal is caught, flips the status
  to `enforcement_failed`, saves the store, and logs a warning — every 10 s with the default
  scan interval. The store write on every failure is also unnecessary disk I/O.
- **Fix.**
  1. Remember `last_enforced` (monotonic) per register in the manager and skip enforcement
     while `now - last_enforced < max(coordinator write cooldown, client.eeprom_write_interval)`.
  2. Treat the cooldown `HomeAssistantError` (translation key `write_cooldown_active`) and
     the API's EEPROM-interval refusal as "try again later": no status change, no store save,
     `debug` log. Keep `enforcement_failed` for real refusals.
  3. In `_record_write_error`, log EEPROM-interval and cooldown refusals at `debug`; they are
     expected pacing, not faults (check `classify_write_error` for the key it assigns).
- **Tests.** `tests/test_dhw_boost.py`: two consecutive evaluations within the interval produce
  one write; a cooldown error leaves `status == "active"` and does not call `async_save`.
- **Effort:** small (1–2 h). **Depends on:** nothing.

### B5. Service registration without schemas; DHW services registered from a platform

- **Severity:** robustness (validation), quality-scale `action-setup` consistency
- **Files:** `services.py:68-104` (`async_setup_services`), `services.py:256-300`
  (manual field checks with the comment at 269), `custom_components/idm_heatpump/dhw_boost_services.py:97-127`,
  `custom_components/idm_heatpump/button.py:59` and `:167-172` (registration from the button
  platform and unregistration on the last unload), `custom_components/idm_heatpump/services.yaml`.
- **Problem.** `hass.services.async_register` is called without `schema=`, so Home Assistant
  does not validate calls; each handler re-implements type and range checks by hand, and
  `services.yaml` promises fields that nothing enforces. The DHW boost services are registered
  when the first button platform loads and removed when the last entry unloads — the opposite
  of the `action-setup` rule that `quality_scale.yaml` reports as done for the other services.
- **Fix.**
  1. Define one `vol.Schema` per service in `services.py` (`cv.entity_ids`, `vol.Coerce(int)`
     with `vol.Range` from `const.py` limits, `cv.string` for register names) and pass it to
     `async_register`. Keep the `ServiceValidationError` paths for semantic checks the schema
     cannot express (register not writable, mode not allowed).
  2. Register `start_dhw_boost` / `cancel_dhw_boost` in `async_setup_services`; their handlers
     already resolve the coordinator per call. Delete `async_unload_dhw_boost_services` and the
     `has_service` guards.
  3. Cross-check `services.yaml` fields against the schemas in a test (parse the YAML, assert
     every field name appears in the schema and vice versa).
- **Tests.** `tests/test_services.py`: an out-of-range `timeout_minutes` is rejected by the
  schema (`vol.Invalid`), not by the handler. `tests/test_dhw_boost_services.py`: services
  exist after `async_setup` without any entry loaded.
- **Effort:** medium (2 h). **Depends on:** nothing.

### B6. `hvac_action` reports the plant status for every circuit

- **Severity:** robustness (misleading state)
- **Files:** `climate.py:268-284`, `climate.py:382-392` (zone rooms).
- **Problem.** Both climate classes derive `hvac_action` from the global `hp_operating_mode`
  bitflags. With one circuit heating and another idle, both show `heating`; during a DHW
  charge every circuit shows `heating` although no circuit water moves.
- **Verify first.** Check `idm_heatpump/registers.py` for per-circuit status registers (pump
  status, mixer position, `hc_<x>_active` or similar) and for per-room demand flags. If none
  exists, this cannot be fixed locally; document the limitation in `docs/wiki/Entities.md`
  and return `None` for `hvac_action` instead of a wrong value.
- **Fix (if a circuit register exists).** Use the circuit register for `HEATING`/`IDLE`, and
  keep the plant status only to distinguish `COOLING` when the circuit is active in cool mode.
  Add the register to `_entity_dependencies` in `polling_plan.py`.
- **Tests.** `tests/test_platforms_climate.py`: plant heating + circuit pump off → `IDLE`.
- **Effort:** small–medium. **Depends on:** the register check.

---

## C. Performance

### C1. Polling plan listens to every entity registry event

- **Severity:** performance (minor CPU), also a correctness nit
- **Files:** `polling_plan.py:172-186` (`_handle_registry_event`).
- **Problem.** The listener subscribes to `entity_registry_updated` for all integrations.
  For each event it looks the entity up and, if the entry belongs to another config entry,
  returns. A `remove` event has no registry entry any more, so it falls through the filter and
  schedules a debounced re-plan for an unrelated integration's removal. Each re-plan walks the
  whole registry for this entry.
- **Fix.** Use `event.data["action"]`: for `create`/`update` keep the lookup; for `remove`
  compare `event.data["entity_id"]` against a cached set of this entry's entity IDs built in
  `_async_apply_plan`. Alternatively use `er.async_entries_for_config_entry` once and cache the
  ID set with the plan.
- **Tests.** `tests/test_polling_manager.py`: a `remove` event for a foreign entity does not
  schedule a re-plan.
- **Effort:** small. **Depends on:** nothing.

### C2. Slow tests

- **Severity:** performance (developer time; ≈ 18 s of a 35 s suite)
- **Files:** `tests/test_pages_seo.py` (seven tests, each 2–3 s in `setup`),
  `tests/test_library_client.py::TestReadGroupFailureTracking::test_incomplete_data_skips_register` (3.0 s).
- **Fix.** Make the Pages build fixture `scope="module"` (the artifact is read-only in the
  tests). For the library-client test, patch `asyncio.sleep` in the API's retry loop (or set
  the client's retry delay to 0 through its constructor if it exposes one) so the retry
  backoff does not run in real time.
- **Tests.** The suite itself; target under 20 s.
- **Effort:** small. **Depends on:** nothing.

### C3. Polling jitter delays write-confirmation refreshes

- **Severity:** performance / UX
- **Files:** `coordinator.py:669-673` (`_async_update_data` start), `coordinator.py:1080-1085`
  (`_delayed_refresh`).
- **Problem.** The jitter sleep sits at the top of `_async_update_data`, so it also applies to
  the confirmation refresh issued 0.5 s after a write and to manual refreshes. With 20 %
  jitter on a 30 s interval a write can take up to 6.5 s to show the confirmed value.
- **Fix.** Apply jitter only to scheduled polls: set a flag in `_delayed_refresh` before
  calling `async_request_refresh`, and skip the sleep when the flag is set. Simpler
  alternative: jitter the `update_interval` itself once at setup (Home Assistant only needs
  entries to be out of phase, not each poll randomised).
- **Tests.** `tests/test_coordinator.py`: a refresh triggered by a write does not sleep.
- **Effort:** small. **Depends on:** nothing.

---

## D. Cleanup

### D1. Remove compatibility shims for API < 2.0

- **Severity:** cleanup (≈ 80 lines, clearer error paths)
- **Files:** `coordinator.py:498-506` (`effective_sentinel_values` fallback),
  `coordinator.py:587-616` (`getattr(self._client, "get_unsupported_registers")`),
  `coordinator.py:631-635` (`get_batch_unsafe_registers`), `coordinator.py:707-710`
  (`mark_batch_unsafe`), `coordinator.py:1150-1170` (`simulate_write` / `encode_value`
  fallback), `coordinator.py:1172-1190` (`client_diagnostics` duck typing),
  `__init__.py:259-266` (`detect_model(read_firmware=False)` with `TypeError` fallback),
  `__init__.py:668-673` (`eeprom_write_interval` in `try/except AttributeError`).
- **Problem.** The manifest pins `idm-heatpump-api[web]==2.0.0` exactly and `AGENTS.md`
  forbids widening the pin, so the "older API" branches can never execute. They cost
  readability and, worse, they turn a real `AttributeError` from a typo into silent
  fallback behaviour. The installed API provides every method (`client.py:543, 890, 1299,
  1319, 1709, 1724, 1733`; `eeprom_write_interval` setter at `:522`).
- **Fix.** Call the methods directly. Keep `getattr` only where the object may legitimately be
  a different type (none found). Where the coordinator's tests used a `MagicMock` client, give
  the mock the attributes explicitly (`spec=IdmModbusClient` already does).
- **Tests.** Existing suite; remove tests named `*_older_api*` / `*_without_*` that only
  exercised the fallback branches.
- **Effort:** small–medium (2 h). **Depends on:** nothing; do it before D2/D3.

### D2. Stop reaching into coordinator private attributes from other modules

- **Severity:** cleanup (encapsulation; blocks A2 done cleanly)
- **Files (writers):** `polling_plan.py:216-220` (`_registers`, `_room_mode_registers`,
  `_polling_plan_*_count`, `_entity_aware_polling_manager`), `__init__.py:498-500`
  (`_registers`, `_alias_map` in web-only setup), `custom_components/idm_heatpump/device_hierarchy.py`
  (`_hierarchy_device_ids`), `custom_components/idm_heatpump/entity.py:59`
  (`_device_info_cache`), `dhw_boost.py` (`_dhw_boost_manager`).
  **Files (readers):** `custom_components/idm_heatpump/diagnostics.py` (nine `_` fields),
  `sensor.py:474-478` (`_total_poll_count`, `_total_poll_failures`), `climate.py`,
  `device_hierarchy.py` (`_registers`).
- **Fix.** Add to `IdmCoordinator`: `active_registers -> tuple[RegisterDef, ...]`,
  `set_active_registers(registers)` (updates the room-mode subset and the plan counters
  itself), `poll_statistics -> PollStatistics` (frozen dataclass with the nine fields),
  `alias_map -> Mapping[int, Sequence[str]]`, `device_info()` (moves the cache from
  `entity.build_device_info` into the coordinator), `hierarchy_device_ids` property with a
  setter used by `device_hierarchy.py`, and `dhw_boost_manager` property. Replace the web-only
  hack (`coordinator._registers = []`) with `setup_registers(descriptions=[])`.
- **Tests.** Existing suite (behaviour unchanged) plus a small test for `poll_statistics`.
- **Effort:** medium (2–3 h). **Depends on:** D1.

### D3. Extract model reconciliation from `async_setup_entry`

- **Severity:** cleanup (testability; the 90 % coverage gap in `__init__.py` is here)
- **Files:** `__init__.py:690-880` (fresh detection × stored detection × web supplement ×
  override × stale-data cleanup), `__init__.py:255-350` (`_detect_model_info`,
  `_model_info_from_detected_name`, override helpers), `coordinator.py:918-1010`
  (`async_refresh_web_supplement` re-implements part of the same reconciliation at runtime).
- **Problem.** Roughly 250 lines of branching decide the model name, firmware string,
  `IdmModelInfo` and which `entry.data` keys to rewrite. The logic is duplicated in spirit by
  the coordinator's runtime web correction. It can only be tested through the full setup
  path with heavy mocks, which is why `__init__.py` has 44 uncovered lines.
- **Fix.**
  1. Create `model_resolution.py` with a pure function
     `resolve_model(fresh: DetectionResult, stored: StoredDetection, web: IdmWebSupplement | None, override: str | None, plant: PlantShape) -> ModelResolution`
     where `ModelResolution` carries `model_name`, `firmware_version`, `model_info`,
     `data_updates: dict[str, Any]`, `data_removals: set[str]`, `web_variant` and a
     `log_lines: list[tuple[int, str, tuple]]` for the messages `async_setup_entry` emits.
  2. `async_setup_entry` becomes: settings → connect → detect → `resolve_model` → apply
     `data_updates` → build coordinator. The coordinator's runtime correction calls the same
     function with `fresh=None`.
  3. Table-driven tests in `tests/test_model_resolution.py` over the matrix (fresh ∈ {nav20,
     nav10, unknown, failed} × stored ∈ {none, same, conflicting} × web ∈ {none, agree,
     conflict with NAV10 firmware, conflict without} × override ∈ {auto, nav10, nav20, pro}).
- **Tests.** As above; `__init__.py` coverage should rise above 95 % on its own.
- **Effort:** large (1 day). **Depends on:** B1 (settings dataclass), D1.

### D4. One translated-write-error wrapper

- **Severity:** cleanup (three identical copies)
- **Files:** `entity.py:134-166` (`IdmEntity._async_write_register`), `climate.py:135-159`
  (`IdmClimateBase._async_write_register`), `water_heater.py:129-` (`async_set_temperature`
  has the same try/except shape).
- **Fix.** Move the body into a module-level `async def async_write_translated(coordinator, reg, value, *, action_label, logger)`
  in `entity.py` and call it from the three places. Behaviour identical.
- **Tests.** Existing tests for all three platforms cover the error mapping.
- **Effort:** small. **Depends on:** nothing.

### D5. One forwarder implementation

- **Severity:** cleanup (≈ 120 duplicated lines)
- **Files:** `room_temp_forwarding.py:91-245` (`RoomTempForwarder`), `:255-374`
  (`HumidityForwarder`).
- **Problem.** Both classes implement the same run loop, state-change debounce, teardown,
  bounds check, tolerance check and error logging; they differ only in the value coercion,
  the register lookup and single-versus-many keys. `RoomTempForwarder` is already
  parameterised by `register_for_key`, `key_label` and `value_label`, so the humidity case fits
  it with one key.
- **Fix.** Add a `coerce: Callable[[Any, str | None], float | None]` parameter (value and unit,
  which A4 introduces) to `RoomTempForwarder`, rename it `ValueForwarder`, and instantiate the
  humidity forwarder as `ValueForwarder(hass, coordinator, config(entities={"ext_humidity": entity_id}), register_for_key=..., coerce=_coerce_humidity, ...)`.
  Keep `HumidityForwarder` as a thin alias for one release so `__init__.py` and tests change
  minimally.
- **Tests.** `tests/test_humidity_forwarding.py` keeps passing against the alias; add one test
  that both paths share the debounce.
- **Effort:** medium (2 h). **Depends on:** A4 preferably first.

### D6. German in code

- **Severity:** cleanup (language contract)
- **Files:** every module header (`# © 2026 Xerolux — Inoffizielle Community-Integration …`,
  `# Erstellt von …`, `# Lizenz: MIT`) in `__init__.py`, `coordinator.py`, `entity.py` and
  the other platform files; `dhw_boost.py` literals (A7); `sensor.py:551` (A6);
  `custom_components/idm_heatpump/adapter_enums.py:47` (`"Kühlbetrieb"` inside an enum label
  map — check whether that map is the German source of truth or a stray literal).
- **Note.** `adapter_metadata.py` and `adapter_names.py` carry German `name` fields on
  purpose (German source for the `de` translations); leave them.
- **Fix.** Translate the headers (or reduce them to the SPDX line `# SPDX-License-Identifier: MIT`
  plus the author line). Extend `scripts/check_documentation_language.py` with an optional
  pass over Python string literals and comments in `custom_components/` (same marker list),
  with an allow-list for `adapter_names.py`, `adapter_metadata.py`, the `translations/`
  generator and the KNX catalogue, and add the Python pass to
  `tests/test_documentation_language.py`.
- **Effort:** small (1–2 h). **Depends on:** A6, A7.

### D7. Documentation drift

- **Severity:** docs
- **Files and facts:**
  - `AGENTS.md` architecture diagram line 118 says `idm-heatpump-api 0.9.1`; the pin is
    `2.0.0`.
  - `AGENTS.md` repository tree lacks eleven modules that exist: `adapter_metadata.py`,
    `binary_semantics.py`, `calculated_sensors.py`, `controller_stats_reference.py`,
    `dhw_boost.py`, `dhw_boost_services.py`, `error_messages.py`, `operation_analysis.py`,
    `operation_entities.py`, `polling_plan.py`, `web_binary_sensors.py`.
  - `AGENTS.md` test list lacks 26 existing test files (from `test_binary_semantics.py` to
    `test_web_binary_sensors.py`; compare with `ls tests`).
  - `AGENTS.md:380` says feature branches are `Codex/...`; the repository uses `claude/...`
    and other prefixes. State the rule as "any branch except `main`".
  - `AGENTS.md` "Services" box lists `start_dhw_boost` / `cancel_dhw_boost` under
    `services.py`; they live in `dhw_boost_services.py` (until B5 moves them).
  - `.github/workflows/ci.yml:31-34` pins `2026.9.0b0` with a comment to move to `2026.9.0`
    once released; check PyPI and update.
  - `CLAUDE.md` and `AGENTS.md` should link this document next to the roadmap and the open
    work audit.
- **Fix.** Regenerate the tree from `ls`, fix the three facts, add the link. Consider a test
  in `tests/test_release_contract.py` that every `custom_components/idm_heatpump/*.py` is
  mentioned in `AGENTS.md` so the list cannot drift again.
- **Effort:** small. **Depends on:** nothing.

---

## E. Test infrastructure

### E1. Lifecycle bugs are invisible behind the Home Assistant stub

- **Severity:** robustness (of the test suite)
- **Files:** `tests/conftest.py` (`_DataUpdateCoordinator`, `_CoordinatorEntity`, the
  `ConfigEntry` stub, `issue_registry` stub), `.github/workflows/python-quality.yml` (which
  already installs the real Home Assistant for mypy).
- **Problem.** The stubs make the suite fast and hermetic, but A1, B1 and B2 are exactly the
  class of bug they cannot catch: interaction with the real coordinator timer, the real
  `ConfigEntry` task tracking, and the real unload sequence. The repository deliberately
  does not use `pytest-homeassistant-custom-component` (it pins Home Assistant and would
  defeat the version matrix) — that decision stands.
- **Fix.** Add a second, small test tree `tests_ha/` with its own `conftest.py` that does
  **not** stub Home Assistant, and run it in `python-quality.yml` after the main suite (Home
  Assistant is already installed there). Start with four tests: set up an entry against a
  fake client (`IdmModbusClient` with an in-memory transport implementing the API's
  `IdmModbusTransport` protocol), unload it and assert no timer/task remains (`hass.loop`
  has no pending tasks named with the domain), reload it, and shut Home Assistant down. Use
  `homeassistant.core.HomeAssistant` directly with a temporary config dir; no
  `pytest-homeassistant-custom-component` needed. Keep `pytest.ini` `testpaths = tests` so
  the local quick run is unchanged and add `tests_ha` explicitly in CI.
- **Effort:** medium–large (½ day for the harness, then cheap per test). **Depends on:** A1.

---

## Things checked and found sound

Recorded so the next audit does not redo them:

- `modbus_transport.py` / `modbus_client.py`: exception translation covers every
  `modbus-connection` error class, endpoint validation is complete, `close()` is idempotent,
  and the transport reports `supports_shared_connection=False` as required.
- Translations: every `translation_key` used in Python exists in `strings.json`; `en.json`
  and `de.json` have exactly the same key set as `strings.json`; every repair issue ID the
  coordinator raises has an `issues` entry.
- Calculated COP guards division by zero and idle plant (`calculated_sensors.py:135-151`).
- Room-temperature forwarding validates bounds from register metadata, debounces state
  changes and is `@callback`-safe; humidity forwarding rejects values outside 0–100.
- `operation_analysis.py` persists through `Store.async_delay_save`, not per poll.
- The write path (`async_write_register`) runs local safety validation before the network
  write, records the last error for diagnostics and raises translated errors; the cooldown
  is per register address.
- Diagnostics privacy is covered by `tests/test_diagnostics_privacy.py`.
- CI: the Home Assistant version is verified after install, the API-main leg is meaningful,
  ruff format is enforced, coverage gates are enforced, actions are pinned by SHA.

## Out of scope for this audit

- Anything that requires a register map change (belongs in `idm-heatpump-api`).
- Central Home Assistant Modbus connection sharing (tracked in
  `docs/dev/open-work-audit.md`).
- Behaviour that can only be validated on hardware; the packages above are all provable with
  the stubbed suite or the proposed `tests_ha/` harness.
