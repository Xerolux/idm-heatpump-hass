# Roadmap: IDM Heatpump Reliability Bugfixes

## Overview

This milestone resolves GitHub issues #170, #171, and #172 through four focused
brownfield phases. It first stabilizes Home Assistant service ownership, then
separates writable unset values from genuinely unsupported registers, uses that
result to diagnose the remaining model conflict without guessing a Navigator
family, and closes with integrated verification and release evidence. The 16 v1
requirements are each assigned to exactly one phase; issues #44, #135, #148,
and #158 remain outside this milestone.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Service Lifecycle** - Keep domain services callable across reloads and multi-entry teardown.
- [ ] **Phase 2: Writable Sentinel Availability** - Preserve safe writable targets without exposing sentinel values as valid state.
- [ ] **Phase 3: Model Conflict Diagnosis and Correction** - Classify #170 after the GLT fix and correct model selection only from reproducible evidence.
- [ ] **Phase 4: Integrated Validation and Release** - Prove the fixes together and publish bounded, reproducible release evidence.

## Phase Details

### Phase 1: Service Lifecycle
**Goal**: Users can rely on the four core IDM domain services throughout Home Assistant entry reload and unload lifecycles.
**Depends on**: Nothing (first phase)
**Requirements**: LIFE-01, LIFE-02, LIFE-03
**Success Criteria** (what must be TRUE):
  1. Users can call `set_external_climate`, `set_system_mode`, `acknowledge_errors`, and `write_register` after an options change or config-entry reload.
  2. Unloading, reloading, or removing one IDM entry does not remove the services needed by another loaded IDM entry.
  3. Each service is registered once per Home Assistant start and returns a translated validation error when no usable entry is loaded.
**Plans**: TBD

### Phase 2: Writable Sentinel Availability
**Goal**: Users retain safe control of writable inputs when a device reports an unset sentinel, while unsupported and read-only data remain correctly filtered.
**Depends on**: Phase 1
**Requirements**: GLT-01, GLT-02, GLT-03, GLT-04, GLT-05, QUAL-01
**Success Criteria** (what must be TRUE):
  1. With `hide_unused_registers` enabled, a model-supported writable Number, Select, or Switch survives setup, runtime sentinel transitions, reload, and restart and remains a callable write target.
  2. A writable target showing an unset sentinel reports unknown state until a valid read or successful write; a successful write becomes visible immediately and is reconciled by the next poll.
  3. Model-excluded, Illegal-Data-Address, and absent registers remain hidden or unavailable, while read-only and dual-exposed sensor views never present sentinel values as valid measurements.
**Plans**: TBD

### Phase 3: Model Conflict Diagnosis and Correction
**Goal**: Users receive an evidence-based resolution of issue #170 without an unsafe guess about their Navigator family.
**Depends on**: Phase 2
**Requirements**: MODEL-01, MODEL-02, MODEL-03, MODEL-04
**Success Criteria** (what must be TRUE):
  1. The missing PV-surplus, PV-production, and household-consumption setpoints from #170 are retested after Phase 2 and documented as either the #172 path or a distinct remaining defect.
  2. A conflicting-model diagnostic identifies the Modbus and stored sources, selected Navigator family, web variant, firmware evidence, and any active manual override without exposing private connection data.
  3. Any model-selection correction is backed by redacted field evidence or a reproducible fixture and selects the appropriate register plan for Navigator 2.0, Navigator 10, and Navigator Pro cases.
  4. If the defect belongs to `idm-heatpump-api`, users receive it only through an exact-pinned API release whose detection and cross-repository contract tests pass.
**Plans**: TBD

### Phase 4: Integrated Validation and Release
**Goal**: Users can install a reproducible bugfix release whose scope, evidence, and remaining #170 boundary are explicit.
**Depends on**: Phase 3
**Requirements**: QUAL-02, REL-01, REL-02
**Success Criteria** (what must be TRUE):
  1. The complete milestone passes Pytest, strict mypy, Ruff, cross-repository contracts, and release-contract checks.
  2. The changelog and issue records explain cause, user impact, workaround, verification evidence, and the relationship among #170, #171, and #172.
  3. A release is created only after automated checks pass and the model portion of #170 is either field-verified or explicitly bounded as still open.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Service Lifecycle | 0/TBD | Not started | - |
| 2. Writable Sentinel Availability | 0/TBD | Not started | - |
| 3. Model Conflict Diagnosis and Correction | 0/TBD | Not started | - |
| 4. Integrated Validation and Release | 0/TBD | Not started | - |

---
*Roadmap created: 2026-07-25*
*Coverage: 16/16 v1 requirements mapped exactly once*
