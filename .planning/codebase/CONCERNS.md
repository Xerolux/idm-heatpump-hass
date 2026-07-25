# Codebase Concerns

**Analysis Date:** 2026-07-25

## Tech Debt

**Model detection is distributed across Modbus, persisted entry data, user override, and web detection:**
- Issue: Navigator-family selection and reconciliation span `_detect_model_info()`, setup-time persisted-data handling, web variant selection, and runtime web refresh rather than one authoritative state machine.
- Files: `custom_components/idm_heatpump/__init__.py`, `custom_components/idm_heatpump/coordinator.py`, `custom_components/idm_heatpump/web_data.py`, `custom_components/idm_heatpump/adapter_registers.py`
- Impact: A transient or ambiguous probe can select the wrong register map, and later web evidence is intentionally ignored when it conflicts with Modbus unless a narrowly recognized firmware signal proves Navigator 10. This is directly relevant to open issue #170.
- Fix approach: Introduce one typed detection result containing source, confidence, Navigator family, web protocol, and firmware evidence; derive both register filtering and web-client choice from it, and cover Navigator 2 Pro explicitly with recorded fixtures.

**Service lifecycle uses two incompatible ownership patterns:**
- Issue: Four domain services are registered once from `async_setup()` but removed from the config-entry unload path, while DHW boost services are registered during platform setup and use entry-aware unloading.
- Files: `custom_components/idm_heatpump/__init__.py`, `custom_components/idm_heatpump/services.py`, `custom_components/idm_heatpump/button.py`, `custom_components/idm_heatpump/dhw_boost_services.py`
- Impact: The lifecycle is difficult to reason about and currently produces the reload bug documented in open issue #171.
- Fix approach: Give all domain services the same idempotent setup-entry/last-entry-unload lifecycle. Pass the unloading entry ID and test single-entry reload, two-entry unload, and final-entry removal.

**Unused-value policy mixes hardware absence with temporary input state:**
- Issue: `IdmCoordinator.is_register_unused()` applies generic numeric sentinels to every register, and both entity creation and runtime availability consume the result without considering writability.
- Files: `custom_components/idm_heatpump/coordinator.py`, `custom_components/idm_heatpump/entity.py`, `custom_components/idm_heatpump/const.py`
- Impact: Writable external-input entities can hide themselves when their current value is `-1.0`; this is the self-sustaining failure in open issue #172.
- Fix approach: Model sentinel semantics in register metadata and never treat a writable input as absent solely because it has an “unset” value. Add tests for setup-time and runtime transitions with `hide_unused_registers` enabled.

**Large orchestration modules concentrate unrelated responsibilities:**
- Issue: `config_flow.py`, `__init__.py`, and `coordinator.py` combine validation, device detection, lifecycle, recovery, polling, web reconciliation, issue creation, and persistence.
- Files: `custom_components/idm_heatpump/config_flow.py`, `custom_components/idm_heatpump/__init__.py`, `custom_components/idm_heatpump/coordinator.py`
- Impact: These files are approximately 1,306, 976, and 970 lines respectively, increasing regression risk in reload, detection, and fallback paths.
- Fix approach: Extract model detection/reconciliation, entry service lifecycle, and web supplement supervision into typed modules with narrow interfaces.

## Known Bugs

**Issue #170 — conflicting model detection can remove writable PV/GLT entities:**
- Symptoms: A web/Modbus Navigator-family conflict is logged and PV surplus, household-consumption, or PV-production number entities can become unavailable.
- Files: `custom_components/idm_heatpump/__init__.py`, `custom_components/idm_heatpump/coordinator.py`, `custom_components/idm_heatpump/entity.py`, `custom_components/idm_heatpump/adapter_registers.py`
- Trigger: A controller for which Modbus and the local web supplement identify different Navigator families, combined with register-map or unused-sentinel filtering. The exact device-side reason for the reported transient values is not established by repository code.
- Workaround: Use the explicit Navigator model override only when the actual controller family is known; disabling `hide_unused_registers` may restore entities hidden by sentinel filtering but does not resolve a wrong model map.

**Issue #171 — four services disappear after config-entry reload:**
- Symptoms: `set_external_climate`, `set_system_mode`, `acknowledge_errors`, and `write_register` are absent after changing options or reloading an entry; a Core restart restores them.
- Files: `custom_components/idm_heatpump/__init__.py`, `custom_components/idm_heatpump/services.py`
- Trigger: `async_unload_entry()` calls `async_unload_services()`, which removes services when at most one entry is loaded; the subsequent `async_setup_entry()` does not call `async_setup_services()`.
- Workaround: Restart Home Assistant Core. Do not rely on a manual integration reload to restore these services.

**Issue #172 — writable GLT entities can deadlock in unavailable state:**
- Symptoms: External room-temperature and humidity number entities become unavailable after reading `-1.0`, then are omitted entirely at the next setup.
- Files: `custom_components/idm_heatpump/entity.py`, `custom_components/idm_heatpump/coordinator.py`, `custom_components/idm_heatpump/const.py`, `custom_components/idm_heatpump/services.py`
- Trigger: Enable the default `hide_unused_registers`, then allow a writable external-input register to report the generic unused sentinel.
- Workaround: Set `hide_unused_registers` to false or use `idm_heatpump.set_external_climate`, whose register lookup does not depend on entity availability. Issue #171 can independently remove that fallback service after reload.

## Security Considerations

**Raw Modbus write service:**
- Risk: `write_register` permits custom addresses and cannot infer safe ranges, semantics, or EEPROM behavior; a mistaken or malicious service call can alter controller state or accelerate EEPROM wear.
- Files: `custom_components/idm_heatpump/services.py`, `custom_components/idm_heatpump/services.yaml`, `custom_components/idm_heatpump/coordinator.py`, `docs/wiki/Known-Limitations.md`
- Current mitigation: The caller must set `acknowledge_risk`, datatypes are constrained, the API safety simulation is used when available, and rapid repeated writes emit a warning.
- Recommendations: Add an opt-in configuration gate for arbitrary addresses, enforce configurable hard rate limits, maintain a denylist for known unsafe/EEPROM-sensitive registers, and emit an audit event for every custom write.

**Local protocols carry controller credentials and control traffic:**
- Risk: Modbus TCP and the local Navigator HTTP/WebSocket interfaces are LAN-local protocols; the integration provides no transport encryption layer of its own.
- Files: `custom_components/idm_heatpump/config_flow.py`, `custom_components/idm_heatpump/web_data.py`, `custom_components/idm_heatpump/manifest.json`
- Current mitigation: The design is local-only, the PIN is stored in config entry data, and diagnostics redact host, port, slave ID, web host, and PIN in `custom_components/idm_heatpump/diagnostics.py`.
- Recommendations: State the trusted-network requirement prominently, avoid exposing controller ports across untrusted networks, and retain redaction tests whenever diagnostics fields change.

**Broad exception diagnostics can expose device-library details in debug logs:**
- Risk: Several web and transport paths log full tracebacks at debug level; dependency exception messages may include endpoints or request details.
- Files: `custom_components/idm_heatpump/web_data.py`, `custom_components/idm_heatpump/coordinator.py`, `custom_components/idm_heatpump/__init__.py`
- Current mitigation: User-facing diagnostics sanitize web errors and structured diagnostics pass through redaction.
- Recommendations: Sanitize exception strings before non-debug logging and review third-party exceptions before encouraging users to share full debug logs.

## Performance Bottlenecks

**Unsupported-register discovery can multiply startup reads:**
- Problem: On Modbus exception code 2, `_async_read_registers_resilient()` recursively bisects a failed register list until individual unsupported registers are isolated.
- Files: `custom_components/idm_heatpump/coordinator.py`
- Cause: Firmware-specific optional registers cannot always be filtered before probing.
- Improvement path: Persist unsupported-register fingerprints by model/firmware, invalidate them on version change, and retain bisection only as a discovery fallback.

**Maximum topology has no load-test evidence:**
- Problem: The integration supports up to 10 zones with 8 rooms each plus multiple heating circuits, but the repository explicitly records maximum-topology load testing as open.
- Files: `custom_components/idm_heatpump/config_flow.py`, `docs/IMPLEMENTATION_TODO.md`, `docs/dev/open-work-audit.md`
- Cause: Suitable real-device diagnostics and timing data are not yet available.
- Improvement path: Capture poll duration, batch count, register count, event-loop delay, and controller errors on a maximum configuration; set safe polling defaults from measured results.

**Wrong web variant can consume a full connection timeout:**
- Problem: Initial auto-detection may try both Navigator web protocols, and the wrong protocol can wait for the complete connect timeout.
- Files: `custom_components/idm_heatpump/web_data.py`, `custom_components/idm_heatpump/config_flow.py`
- Cause: Navigator 10 uses WebSocket while Navigator 2.0 uses HTTP/CSRF, and ambiguous model hints require probing.
- Improvement path: Persist a confidence-scored variant after success, use short protocol-probe timeouts, and expose detection timing in diagnostics.

## Fragile Areas

**Entry setup, reload, and unload sequencing:**
- Files: `custom_components/idm_heatpump/__init__.py`, `custom_components/idm_heatpump/services.py`, `custom_components/idm_heatpump/dhw_boost_services.py`
- Why fragile: Domain-global services coexist with per-entry coordinators and background tasks; HA reload state affects the loaded-entry count during cleanup.
- Safe modification: Treat reload, removal, and final-domain teardown as separate scenarios and preserve service availability while any entry remains usable.
- Test coverage: Add explicit end-to-end lifecycle tests for option update, reload failure, two entries, and removal of either entry; current open issue #171 proves a gap.

**Register availability and entity creation:**
- Files: `custom_components/idm_heatpump/entity.py`, `custom_components/idm_heatpump/coordinator.py`, `custom_components/idm_heatpump/adapter_registers.py`
- Why fragile: Model filtering, unsupported-address filtering, sentinel filtering, and missing-poll-data filtering are independent gates with different meanings.
- Safe modification: Preserve the distinction among “not part of this model,” “unsupported address,” “temporarily unread,” “unset writable input,” and “physically absent.”
- Test coverage: Add property-style cases across readable/writable registers and all sentinel values, including live transition and restart behavior from issue #172.

**DHW boost recovery performs multi-register transactional behavior without device transactions:**
- Files: `custom_components/idm_heatpump/dhw_boost.py`, `custom_components/idm_heatpump/dhw_boost_services.py`
- Why fragile: Start and restore each require multiple independent writes and persistence; network failure can occur between them.
- Safe modification: Keep persistence-before-write, locking, retry-on-update, and idempotent restore semantics intact; never simplify to untracked fire-and-forget writes.
- Test coverage: Existing focused tests in `tests/test_dhw_boost.py` and `tests/test_dhw_boost_services.py` are substantial, but hardware interruption and controller-reboot behavior remain field-dependent.

## Scaling Limits

**Zone and room topology:**
- Current capacity: Up to 10 zone modules and 8 configured rooms per zone.
- Limit: Poll size, entity count, and controller tolerance at the maximum topology have not been load-tested.
- Scaling path: Measure real maximum-topology polling before increasing limits; optimize register batches and allow profiles to disable nonessential diagnostics.

**Concurrent Modbus clients:**
- Current capacity: Multiple heat pumps use separate entries; some controllers tolerate only a limited number of parallel clients.
- Limit: Additional automation systems or proxies can cause timeouts and intermittent availability.
- Scaling path: Prefer a shared connection only after Home Assistant publishes a stable custom-integration contract; until then document client isolation and increase polling intervals where contention is observed.

## Dependencies at Risk

**`idm-heatpump-api[web]`:**
- Risk: Register definitions, model detection, optional web clients, and write-safety behavior are all supplied by one exact-pinned library version.
- Impact: Library regressions can change entity availability, model mapping, or write behavior across most of the integration.
- Migration plan: Keep the exact release pin in `custom_components/idm_heatpump/manifest.json`, run `tests/test_cross_repo_contract.py` against candidate versions, and update the integration and release evidence together.

**`pymodbus`:**
- Risk: `custom_components/idm_heatpump/manifest.json` accepts the full `>=3.12.1,<4.0` range, while transport exceptions and behavior can vary between minor versions.
- Impact: Connection classification, retry behavior, and unsupported-address detection may differ on dependency resolution without an integration release change.
- Migration plan: Test the minimum and newest supported versions in CI or narrow the range to verified minors while preserving compatibility with `idm-heatpump-api`.

## Missing Critical Features

**Complete cross-firmware hardware evidence:**
- Problem: Navigator 2.0 and Navigator Pro lack the same direct, broad firmware validation recorded for Navigator 10.
- Blocks: Confident removal of defensive filters and reliable family-specific model/register decisions.

**Final shared Home Assistant Modbus transport adapter:**
- Problem: The repository has a transport contract and validation helpers, but intentionally does not wire a shared Home Assistant connection into production.
- Blocks: Eliminating parallel-client contention through an official shared connection.

## Test Coverage Gaps

**Service lifecycle across reloads:**
- What's not tested: Preservation and re-registration of all domain services through option-triggered entry reload and multi-entry unload.
- Files: `custom_components/idm_heatpump/__init__.py`, `custom_components/idm_heatpump/services.py`, `tests/test_init.py`, `tests/test_services.py`
- Risk: Heating-control automations fail after configuration changes, as reported in issue #171.
- Priority: High

**Writable sentinel transitions:**
- What's not tested: A writable register changing to `-1.0` during runtime and remaining creatable/available after restart with unused filtering enabled.
- Files: `custom_components/idm_heatpump/entity.py`, `custom_components/idm_heatpump/coordinator.py`, `tests/test_entity.py`, `tests/test_coordinator.py`, `tests/test_platforms.py`
- Risk: External control inputs silently stop updating, as reported in issue #172.
- Priority: High

**Conflicting model evidence and Navigator 2 Pro:**
- What's not tested: Stable entity/register selection when Modbus family, stored detection, web client variant, and firmware evidence disagree for a Navigator 2 Pro-class installation.
- Files: `custom_components/idm_heatpump/__init__.py`, `custom_components/idm_heatpump/web_data.py`, `custom_components/idm_heatpump/adapter_registers.py`, `tests/test_init.py`, `tests/test_web_data.py`, `tests/test_registers.py`
- Risk: Writable PV/GLT entities can be absent or intermittent, matching issue #170.
- Priority: High

**Maximum configured topology and firmware matrix:**
- What's not tested: Real-device load at 10 zones × 8 rooms and complete binary/COP behavior across Navigator families and firmware variants.
- Files: `custom_components/idm_heatpump/config_flow.py`, `custom_components/idm_heatpump/coordinator.py`, `custom_components/idm_heatpump/calculated_sensors.py`, `docs/dev/open-work-audit.md`
- Risk: Poll latency, unsupported-register behavior, or semantic errors may only appear on large or unrepresented installations.
- Priority: Medium

---

*Concerns audit: 2026-07-25*
