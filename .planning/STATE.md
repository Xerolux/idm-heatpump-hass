---
gsd_state_version: '1.0'
status: complete
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 8
  completed_plans: 8
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-25)

**Core value:** Home Assistant must control and monitor the IDM heat pump locally,
reliably, and safely without reloads, sentinel values, or uncertain model
detection silently disabling central automations.
**Current focus:** Milestone complete — #171, #172 and #170 fully resolved and live-verified; `0.8.6-beta.2` release prepared locally (not pushed).

## Current Position

Phase: 5 of 5 (complete)
Plan: 8 of 8 executed (01-01, 02-01, 02-02, 03-01, 03-02, 04-01, 04-02, 05-01)
Status: Complete — automated gate green; MODEL-03/04 closed with field evidence; `0.8.6-beta.2` artifacts produced locally (not pushed, no PR, no GitHub release)
Last activity: 2026-07-26 — Phase 05: read-only live validation, Navigator 10 detection fix (API 0.8.6), 0.8.6-beta.2 release; HASS pytest 963, API pytest 289, mypy + ruff clean

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Verification: HASS pytest 963 passed / 2 skipped; mypy clean (41 files); ruff clean. API pytest 289 passed; mypy clean (6 files); ruff clean.
- Live (read-only): API 11/0/0; HA 182 entities; #171 6/6 after 3 reloads; #172 writable GLT entities available at -1; 60-min stability 0 errors; 0 writes reached the device.

**By Phase:**

| Phase | Plans | Result |
|-------|-------|--------|
| 1. Service Lifecycle | 1 | Complete |
| 2. Writable Sentinel Availability | 2 | Complete |
| 3. Model Conflict Diagnosis | 2 | Complete (MODEL-03/04 closed by Phase 5) |
| 4. Integrated Validation & Release | 2 | Complete |
| 5. Nav10 Live Validation & beta.2 | 1 | Complete (field evidence + detection fix + release) |

**Recent Trend:**
- #171 services invariant across reload/unload; #172 writable targets available-but-None under sentinel; #170 setpoints restored for supported models.

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Approved 2026-07-25; 7 plans across 4 phases (standard granularity), code-grounded.
- [Phase 1]: Domain services outlive individual config-entry reload and unload operations.
- [Phase 2]: Creation gate (`should_add_entity`) and runtime availability/state are split across 02-01 and 02-02; `unused_registers`/`is_register_unused` stay defensive for read-only.
- [Phase 2]: Writable controls report None (not sentinel) and stay available when the register is present.
- [Phase 3]: The GLT fix is verified before #170's missing setpoints are classified.
- [Phase 3]: Model correction is evidence-gated; 03-02 ran as checkpoint — no evidence → MODEL-03/04 open.
- [Phase 4]: Release ships only when the integrated gate is green and the #170 model boundary is explicit.

### Pending Todos

- (Human, when ready) Push `v0.8.6-beta.2` tag, open PR, publish GitHub/HACS release — currently intentionally local only.
- (Next milestone) Move sentinel heuristics into `idm-heatpump-api` as declared `sentinel_values`; clarify 4108 standby decode; consider `hide_unused_registers` simplification.

### Blockers/Concerns

- None for the beta. Open items are deferred to the next milestone (see below).

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| GitHub issues | #44, #135, #148, #158 | Awaiting post-milestone triage | Initial roadmap |
| #170 model part | MODEL-03 / MODEL-04 | **Resolved** (Phase 5 field evidence + API 0.8.6) | — |
| Next milestone | Sentinel → API (`sentinel_values`); 4108 decode; `hide_unused` simplification | Not started | Phase 5 close-out |

## Session Continuity

Last session: 2026-07-26
Stopped at: Milestone complete — 8/8 plans; MODEL-03/04 closed with live evidence; `0.8.6-beta.2` prepared locally; ready for next milestone planning.
Resume file: .planning/phases/05-nav10-live-validation-and-beta2/05-01-SUMMARY.md
