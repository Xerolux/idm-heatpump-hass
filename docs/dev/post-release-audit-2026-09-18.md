# Post-release audit: 2026-09-18

## Scope

Reviewed the changes from stable `v0.17.1` to `9f00fe0` (`v0.17.2-b5`),
with emphasis on energy statistics, automatic energy management, comfort
scheduling, external power forwarding and their polling dependencies.
The starting checkout was clean and identical to `origin/main` after fetching.
Corrections are isolated on `Xe/audit-post-release`.

## Confirmed defects and corrections

| Area | Reproduction and impact | Correction |
| --- | --- | --- |
| Energy polling | Disable raw power entities while keeping energy statistics. Their source registers can disappear from the polling plan and stop accumulation. | The attached accumulator declares its two required registers for the coordinator lifetime. |
| Comfort polling | Disable the raw setpoint and climate entities while a schedule is enabled. The schedule loses its observed setpoint. | Each running scheduler declares its setpoint dependency and releases it when stopped. |
| Schedule timezone | Configure a Home Assistant timezone different from the host timezone. Daily windows run at host-local times. | Use Home Assistant's local-time conversion. |
| Schedule inputs | An offset-bearing window parses successfully but fails when compared with local naive times. NaN, infinity, booleans and the unused setpoint sentinel can arm a restore or trigger a write. | Reject offset-bearing windows and invalid current setpoints before taking ownership. |
| Surplus selection | Make the selected net-surplus sensor unavailable while gross production and consumption remain available. The manager silently substitutes their difference and can request a boost. | An explicitly configured surplus source is authoritative; its failure blocks the action. Negative production/consumption inputs are also rejected. |
| Energy-manager lifecycle | Raise an unexpected transient exception during evaluation. The periodic task terminates permanently. | Log the failure and retry on the normal interval; task cancellation still propagates. |
| Daily PV statistics | Advance the local day, including a month boundary or an invalid power sample. Today's PV total retains yesterday's value. | Reset the daily PV estimate with the other daily totals. |
| Forwarding debounce | Replace an already-running debounce task. The cancelled task's cleanup clears the replacement's reference. | Clear the reference only when the finishing task still owns it. |

The regressions were exercised against the original implementations before
the fixes. The timezone test simulates a host timezone independently of the
machine executing the test. All device writes in these tests use mocks.

## Local validation

An isolated temporary virtual environment uses Python 3.14.2, installed Home
Assistant 2026.8.1 and the exact manifest runtime dependencies. The global
Python environment was not upgraded.

- Baseline: 1767 passed, 2 skipped; 95.15% integration coverage.
- Fixed tree: 1781 passed, 2 skipped; 95.27% integration coverage.
- Separate full-suite config-flow gate: 1781 passed, 2 skipped; 100% coverage.
- Strict mypy passes for 55 source modules against installed Home Assistant.
- Ruff lint and formatting pass.
- Dependency freshness check reports all three runtime pins current.
- Production transport import, construction and disconnect smoke test passes
  against real libraries without opening a network connection.

The suite still uses Home Assistant stubs. This work does not close E1, the
real-Home-Assistant lifecycle smoke-test package in the September audit plan.
The newly added behavior has not been installed on the live controller.

## Live observation

Read-only Home Assistant REST and WebSocket requests confirmed:

- Home Assistant 2026.9.2 / Python 3.14.6, integration 0.17.2-b5, API 2.1.2,
  modbus-connection 4.12.1 and tmodbus 0.6.2.
- One loaded Navigator 10 entry, no model conflict, web supplement available.
- 245 registered entities, 12 disabled, and 233 states. There were 23
  unavailable states, including optional web values, cascade values despite
  cascade being disabled, unused humidity, no recorded defrost and the inactive
  boost-cancel action. This is not evidence that all 23 are defects; each
  category needs its own availability or registry-cleanup assessment.
- Initial diagnostics: 687 polls, zero failures, 113 active registers out of
  168 known registers; about 12 ms for the last poll.
- After the owner reported startup, the compressor was on in DHW mode. Between
  polls 709 and 713, electrical power rose from 1.24 to 1.65 kW, thermal power
  from 1.93 to 7.50 kW, and instantaneous COP from 1.56 to 4.55.
- Electrical and thermal lifetime counters advanced from 0.48130 / 1.72462 kWh
  to 0.49901 / 1.79425 kWh. No communication failures or plant sum alarm were
  observed. A transient low-COP health flag cleared on the next sampled state;
  the present health check has no startup grace period, so it must be read as
  an instantaneous observation rather than an equipment fault diagnosis.
- Final running sample: 716 polls, zero failures; 1.68 kW electrical, 6.94 kW
  thermal, COP 4.13. Totals reached 0.51286 / 1.85475 kWh and no health checks
  were active.

The legacy `/api/error_log` endpoint returned HTTP 404, so its response was
not used as log evidence. The supported read-only `system_log/list` WebSocket
command returned seven log entries. One matched the shared Modbus dependency:
SolarEdge Modbus Multi failed setup at 05:58:14 UTC with
`ImportError: cannot import name 'Placement' from 'modbus_connection.model.component'`.
Its config entry remains in `setup_error`. A fresh local install of the
manifest-pinned dependency successfully imports the same SunSpec module, so
the live cause remains unresolved; it cannot be attributed to a missing symbol
in the published package from this evidence alone. There were no entries
identifying an IDM integration error. No SolarEdge repair or HA restart was
attempted as part of this read-only test.

No integration reload, restart, deployment, service action, Modbus write or
KNX write was performed. This short observation verifies data acquisition and
counter progression during one DHW startup; it is not a long-duration test or
evidence for other operating modes.

## GitHub checks

The existing main CI, Security and release runs for `v0.17.2-b5` succeeded.
The separate GitHub Advanced Security AI review for PR #335 failed before
producing a review: its log reports `400 The requested model is not supported`.
This is an external review-service failure, not a finding in the integration.
No remote CI run has validated this local audit branch yet.
