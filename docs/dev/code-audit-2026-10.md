# Repository audit - October 2026

Date: 2026-10-10. Baseline: `origin/main` at `7ef353b`.
Integration: `0.21.0-b3`; device API: `2.14.2`; latest stable integration: `0.20.3`.
Branch: `Xe/full-audit-2026-10-10`.

## Scope and method

Fetched current branches and tags before review. Reviewed release and dependency
workflows, CI version enforcement, Pages generation, recovery and advisor code,
and web-control factories against their public descriptions. Ran the entire
unit suite, both coverage gates, genuine HA lifecycle smoke tests and strict
mypy against installed Home Assistant. Documentation checks cover version claims,
language, generated entity/register catalogs, translation completeness, German
page coverage and release summaries. This is an automated repository audit with
focused source review, not a claim that every possible defect has been excluded.

## Confirmed findings and fixes

| ID | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| F-01 | High | Pages output validation allowed deleting source directories such as `docs/wiki`, `scripts` or `.git`, and ancestors of the repository. | Reject output paths overlapping protected source directories before deletion; eight preservation regressions. |
| F-02 | Medium | CI verified HA before installing runtime/API dependencies, leaving subsequent resolver changes unchecked. | Move the version check after all dependency installations; assert ordering. |
| F-03 | Medium | Automatic dependency merges lacked genuine HA setup/reload/unload validation. | Run `tests_ha` before creating/merging the PR; include its sources in lint/format checks. |
| F-04 | Low | CI still used the October beta after stable 2026.10.0 was published. | Keep minimum HA 2026.8.1 and replace the second leg with stable 2026.10.0. |
| F-05 | Medium | Windows Python stdout encoding broke KNX website/CLI parity for German names. | Set UTF-8 explicitly for the Python subprocess; existing byte-for-byte parity cases pass. |
| F-06 | Medium | README, wiki home, local-web and troubleshooting pages described web-only operation as sensor-only despite implemented Navigator 10/Pro controls. | Correct EN/DE pages and prerequisites; distinguish Navigator 2.0 HTTP read-only behavior and unavailable raw-register/DHW-boost operations. |
| F-07 | Medium | Release documentation tests treated `Unreleased` as a published stable version. | Match numbered version headings; regression fixtures preserve actual prerelease/stable enforcement. |
| F-08 | Low | Integration release checklist omitted coverage failure thresholds and genuine HA smoke checks. | Document both enforced coverage gates and the smoke command. |

## Validation

- Minimum-runtime unit suite: **2426 passed, 2 skipped**; coverage **95.03%**, required 95%.
- Separate config-flow run: **2426 passed, 2 skipped**; coverage **100%**, required 100%.
- Genuine HA 2026.8.1 lifecycle smoke: **4 passed** (fake plant transport).
- Strict mypy against real HA 2026.8.1 and API 2.14.2: **75 modules passed**.
- Genuine HA 2026.10.0 lifecycle smoke: **4 passed**; strict mypy: **75 modules passed**.
  This separate environment resolved API 2.14.2, modbus-connection 4.12.4 and
  tmodbus 0.6.2 from the manifest's minimum transport requirements. Production
  backend import, client construction and disconnect also pass without device I/O.
- Ruff lint and formatting pass; documentation version/language gates pass.
- Runtime freshness: API 2.14.2 and tmodbus floor current; upstream modbus-connection
  4.12.4 correctly held below HA core's 4.12.3 pin by the existing updater.
- Clean Git-source snapshot passes the sensitive-data guard. The user's working
  directory also contains local untracked/ignored plant-test artifacts; those
  were neither committed nor used to weaken the guard.
- Complete Pages artifact builds successfully; **1897 local HTML link/asset
  references** resolve. Relative targets in **54 README/wiki Markdown files**
  resolve, including extensionless wiki links.
- All **50 live sitemap URLs** return HTTP 200; all **25 legacy GitHub wiki
  pages** contain links to the Pages site.
- Latest baseline GitHub runs: CI, security, sensitive-data guard and Pages green.
  These establish baseline health, not remote validation of this local branch.

## Initial local audit limits and remaining observations

No live Home Assistant installation, physical Modbus/KNX plant, write action,
release or deployment was part of the initial local audit. Browser interaction and visual
accessibility were not manually tested. Existing test output includes asyncio
policy deprecations and mock-related unawaited watchdog-coroutine warnings;
the real minimum-HA lifecycle tests pass without leaked-task failures. Overall
coverage is close to the 95% gate, so future code needs corresponding tests.
At the initial local checkpoint, GitHub HACS/Hassfest/CodeQL results were baseline
evidence; the branch had not yet been pushed and its remote jobs had not run.

## Publication follow-up

The owner authorized merging and publishing the audited changes on 2026-10-10.
[PR #470](https://github.com/Xerolux/idm-heatpump-hass/pull/470) carries the changes.
Remote validation records:

- [PR CI matrix and genuine HA smoke](https://github.com/Xerolux/idm-heatpump-hass/actions/runs/38045603801).
- [PR CodeQL and pip-audit](https://github.com/Xerolux/idm-heatpump-hass/actions/runs/38045603536).
- [PR sensitive-data guard](https://github.com/Xerolux/idm-heatpump-hass/actions/runs/38045603569).

The separate GitHub Advanced Security AI review failed with HTTP 402 because its
monthly quota was exhausted. This is an external service limitation, not a code
finding; the standard CodeQL and pip-audit jobs passed. Main-branch CI and Pages
deployment results remain available in the repository's Actions history after
merge. Physical-device and manual browser/accessibility validation remain outside
this publication follow-up.

