# Open issue review — 2026-10-18

Reviewed every open issue and its full comment history against the current
`main` checkout. There were three open issues and no open pull requests.
The feature and bug templates provide sufficient information for this review;
#546 uses free text but includes a precise reproduction, code path and setup.
No submission needs to be rejected for a missing template field.

| Issue | Finding | Resolution |
| --- | --- | --- |
| [#546](https://github.com/Xerolux/idm-heatpump-hass/issues/546) | Building regressions accept DHW and inactive-circuit samples. | Require exclusive space heating and positive circuit heating evidence; keep active-mode polling independent of enabled entities. Relearn affected legacy regressions and derived capacity once, preserving unrelated analytics. |
| [#519](https://github.com/Xerolux/idm-heatpump-hass/issues/519) | The grid-meter feature, sign normalization, precedence, rounding and documentation already exist and the reporter confirmed operation. A mapped but unavailable battery source still silently disappears from the house balance. | Skip derived household consumption until the battery source recovers; preserve independent measurements and explicit source precedence. |
| [#493](https://github.com/Xerolux/idm-heatpump-hass/issues/493) | Existing cyclic refresh, fractional SOC support, serialized batches and cooldown handling cover the known integration defects. The latest field report still observes controller register resets with forwarding unconfigured and sparse reads; the reporter is awaiting IDM feedback. | Retain cyclic RAM refresh and the existing regression tests. No additional integration fix is established by the current evidence. Controller/firmware resolution and a retest on the affected installation remain open. |

## Verification scope

Regression tests cover non-heating and mixed modes, missing/invalid mode data,
inactive circuits, circuit-flow-setpoint fallback, multiple circuits, mode
changes, persistence migration, restart preservation of newly learned models,
and invalid battery sources with recovery. Existing tests cover grid-meter
sign conventions, W/kW conversion, source precedence, quantization, fractional
SOC, refusal to write unavailable sentinels, periodic refresh and cooldowns.

Validation uses the pinned API and the minimum supported genuine Home Assistant
runtime for strict typing and lifecycle smoke tests. No live plant writes or
physical controller tests are part of this review. Issue #493 remains an
external unresolved observation; passing simulated tests cannot prove its
controller behavior is fixed. Changes are unreleased until merged and shipped.

## Local validation results

- Full unit suite: 3,049 passed, two skipped; integration coverage 99.89%
  (required minimum 95%).
- Separate config-flow coverage run: 3,049 passed, two skipped; 100% coverage.
- Real Home Assistant lifecycle suite: eight passed.
- Strict mypy: all 75 source modules passed with genuine Home Assistant 2026.8.1
  and the manifest-pinned API installed.
- Ruff lint and formatting, documentation language/version checks, the Pages
  build and the sensitive-data guard passed.

The first remote matrix run exposed an unrelated intermittent diagnostics-test
failure: unconfigured web status fields were `MagicMock` objects, and their
random memory-address representation could contain the test PIN digits. The
shared fixture now models an absent status frame as `None`, preserving the
PIN-redaction assertion and the explicit real-status tests without dependence
on memory allocation.
