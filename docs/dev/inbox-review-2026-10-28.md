# GitHub inbox review — 2026-10-28

## Scope

Reviewed all five open issues and their complete comment histories, checked for
open pull requests (none), and retrieved all 80 Discussions with all 39 comments
and 14 nested replies. Eight Discussions contain comments; pagination checks
showed no remaining pages. Review baseline: `801a56b`, manifest `0.24.0-b1`, API
`2.15.1`. The latest published stable release at review time is `v0.23.2`.

Issue reports were evaluated against the repository's own templates and technical
evidence. The generic GSD template checklist does not apply Node.js/runtime or
GSD-specific requirements to this Home Assistant integration. No issue is being
closed for incomplete template fields.

## Open issues

| Issue | Finding | Action / remaining evidence |
| --- | --- | --- |
| [#622](https://github.com/Xerolux/idm-heatpump-hass/issues/622) | The current baseline already uses fixed timestamps and sufficient healed observations. | Verified the existing fix and parameterized the regression for noon and 22:00 UTC, covering both same-day and next-day healing. Software-only report; ready to resolve with the test change. |
| [#596](https://github.com/Xerolux/idm-heatpump-hass/issues/596) | Holiday enum correction already shipped in stable 0.23.2. The last maintainer comment already links it and requests field confirmation. | Keep open for the reporter's natural-operation confirmation; no duplicate reminder or forced mode change. |
| [#594](https://github.com/Xerolux/idm-heatpump-hass/issues/594) | Intentional ongoing field-data collection, with current capture/privacy guidance and no unanswered comments. | Keep open. No specific new donated capture was reviewed during this audit. |
| [#577](https://github.com/Xerolux/idm-heatpump-hass/issues/577) | Reporter confirmed the automatic-model-detection correction. Empty web values and ambiguous packed status words remain separate unresolved problems. | Existing private-capture request remains appropriate. No new response payload establishes a safe parser/decoder change. Do not guess a byte mask or attribute the problem to language/firmware without evidence. |
| [#493](https://github.com/Xerolux/idm-heatpump-hass/issues/493) | Latest comment reports battery controls becoming unavailable after forwarding is disabled. Two integration defects reproduce independently of hardware. | Fix polling demand for GLT Number IDs ending in `_set`; preserve writable controls when a documented unset sentinel falls outside the normal range. The original controller/display flicker remains unresolved. |

## Confirmed #493 defects

`IdmNumber` adds `_set` to a dual-exposed GLT register's unique ID. The polling
planner previously recognized only the unsuffixed Sensor ID. When that Sensor
was disabled or had never been created under an unset initial value, an enabled
Number alone did not retain the readback register. Explicit GLT dependencies now
cover external-power inputs and zone-room temperature/humidity inputs. Disabled
Numbers and unrelated `_set` IDs do not retain registers.

The API declares battery SoC's measurement range as 0–100 and its unset sentinel
as −1. The entity range guard ran before the writable-sentinel exception, so a
present unset input became unavailable despite the existing writable-control
contract. Recognized sentinels now reach that exception; a genuine out-of-range
value (101), a missing register and a failed coordinator still cannot make a
control available. Read-only Sensors continue to report unset input unavailable.

The regression first failed on the baseline in nine cases: all eight GLT
dependency examples and the battery Number lifecycle. After the correction it
also verifies a manual write through the existing coordinator interface and
recovery when a valid snapshot returns. It does not send hardware writes.

## Discussion disposition

| Discussion | Disposition |
| --- | --- |
| [#540](https://github.com/Xerolux/idm-heatpump-hass/discussions/540) | Advisor feedback already has a stable-release follow-up; latest response is an acknowledgement. No new unresolved question. |
| [#516](https://github.com/Xerolux/idm-heatpump-hass/discussions/516) | Flow-meter datatype correction has reporter confirmation and maintainer follow-up. No additional fix established. |
| [#583](https://github.com/Xerolux/idm-heatpump-hass/discussions/583) | Latest question about requesting firmware support already answered: no verified external circulation-run command currently exists. |
| [#151](https://github.com/Xerolux/idm-heatpump-hass/discussions/151) | [Clarified](https://github.com/Xerolux/idm-heatpump-hass/discussions/151#discussioncomment-19249082) that observations of the apparent OS cannot establish storage architecture or safe write frequency; existing guards remain. |
| [#379](https://github.com/Xerolux/idm-heatpump-hass/discussions/379) | Corrected the stray leading backtick in the [published YAML example](https://github.com/Xerolux/idm-heatpump-hass/discussions/379#discussioncomment-18671656) and verified that the six-view dashboard parses. The author deferred work; the upcoming dashboard generator is not yet a published stable feature. |
| [#354](https://github.com/Xerolux/idm-heatpump-hass/discussions/354) | Supply-chain question already answered; no new user reply. |
| [#300](https://github.com/Xerolux/idm-heatpump-hass/discussions/300) | Household-consumption question already answered; no new user reply. |
| [#169](https://github.com/Xerolux/idm-heatpump-hass/discussions/169) | [Answered](https://github.com/Xerolux/idm-heatpump-hass/discussions/169#discussioncomment-19249085) the old release-thread circulation question with a link to the current explanation in #583. |

Other Discussions have no comments. The current capture request #593 remains
an ongoing collection thread, not a bug awaiting closure.

## Verification and limits

Focused entity, platform, polling and forwarding tests passed (280 tests).
Both fixed-time anomaly-retraction cases passed. Strict mypy passed against real
Home Assistant 2026.8.1 and API 2.15.1 (80 source files); real-Home-Assistant
lifecycle smoke tests passed (8 tests). The full integration coverage gate passed
with 3,237 tests and 99.64% coverage (2 skips). The independent config-flow coverage
gate and CI results are recorded on the pull request containing this review.

No controller settings, operating modes, heating/DHW cycles, external GLT inputs,
or private captures were changed or uploaded. Software tests do not establish
continuous battery-display behavior on the affected installation. This change
does not introduce a reset-to-zero or restore write on forwarding shutdown.
