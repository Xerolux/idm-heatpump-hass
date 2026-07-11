# Release Candidate Evidence: VERSION

Status: `BLOCKED`

## Candidate

| Field | Value |
|---|---|
| Version / tag | |
| Commit SHA | |
| Published at (UTC) | |
| Artifact URL | |
| SHA-256 | |
| API requirement | |

## Test Environment

| Field | Value |
|---|---|
| Tester | |
| Started / completed (UTC) | |
| Home Assistant version / installation type | |
| Heat-pump model | |
| Navigator generation / firmware | |
| Connection path | direct / proxy / other |
| Optional paths in scope | web / zones / cascade / forwarding / none |

Do not record private addresses, PINs, tokens, serial numbers, or customer data.

## Automated Preflight

| Check | Result | Evidence |
|---|---|---|
| CI with manifest-pinned API | `PENDING` | |
| CI with API main | `PENDING` | |
| HACS and Hassfest | `PENDING` | |
| CodeQL and dependency audit | `PENDING` | |
| Release workflow and ZIP inspection | `PENDING` | |
| Published checksum | `PENDING` | |

## Clean Home Assistant Smoke Test

| ID | Check | Result | Evidence / N/A reason |
|---|---|---|---|
| SMOKE-01 | Fresh artifact installation and HA restart | `PENDING` | |
| SMOKE-02 | Config flow and first poll | `PENDING` | |
| SMOKE-03 | Detected model and capabilities match hardware | `PENDING` | |
| SMOKE-04 | Reconfigure and connection test | `PENDING` | |
| SMOKE-05 | Redacted diagnostics | `PENDING` | |
| SMOKE-06 | Reversible safe entity write and read-back | `PENDING` | |
| SMOKE-07 | Original value restored | `PENDING` | |
| SMOKE-08 | Reload, unload, re-enable, and resumed polling | `PENDING` | |
| SMOKE-09 | Upgrade from immediately preceding release | `PENDING` | |
| SMOKE-10 | Optional local web path | `PENDING` | |
| SMOKE-11 | Optional room-temperature forwarding | `PENDING` | |

Allowed result values are `PASS`, `FAIL`, and `N/A`. `N/A` requires a reason.
Any required `PENDING`, `FAIL`, or unjustified `N/A` keeps the overall status
`BLOCKED` or `FAIL`.

## Soak

| Field | Value |
|---|---|
| Candidate unchanged since (UTC) | |
| Earliest eligible completion (UTC) | |
| Start observation | `PENDING` |
| Midpoint observation | `PENDING` |
| Final observation | `PENDING` |
| Confirmed blocking regressions | |

## Final Verdict

- Overall result: `BLOCKED`
- Maintainer:
- Signed at (UTC):
- Notes / linked issues:
