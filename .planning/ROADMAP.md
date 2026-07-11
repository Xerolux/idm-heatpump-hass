# Roadmap: IDM Heatpump for Home Assistant

## Overview

This roadmap advances the existing beta integration from its shipped, audited baseline to an evidence-backed stable-release decision and then to a deliberate Home Assistant Core go/no-go gate. It does not recreate existing entities, services, config flows, polling, web supplementation, diagnostics, or safety controls; phases close the remaining automated qualification, real-device compatibility, soak, release-consistency, and Core-readiness gaps.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): planned milestone work.
- Decimal phases (for example 2.1): urgent insertions created later.

- [ ] **Phase 1: Reproducible Release Qualification** - Produce passing automated, artifact, clean-install, lifecycle, and safe-write evidence for one exact release pair.
- [ ] **Phase 2: Real-Device Compatibility Evidence** - Resolve the remaining Navigator 2.0, Terra SWM, zone-room, Navigator Pro, and server-error evidence gaps.
- [ ] **Phase 3: Stable Release Decision** - Complete the beta soak and make an auditable stable-release go/no-go decision with all public release information aligned.
- [ ] **Phase 4: Home Assistant Core Readiness Gate** - Decide whether Core entry criteria are met and, if so, define the small read-only first contribution and migration checklist.

## Phase Details

### Phase 1: Reproducible Release Qualification
**Goal**: Maintainers have reproducible proof that one exact integration/API pair installs, operates, and writes safely under the supported runtime.
**Depends on**: Nothing (first phase)
**Requirements**: QUAL-01, REL-01, SAFE-01, OPS-01
**Success Criteria** (what must be TRUE):
  1. Maintainer can run every required automated quality, typing, validation, package, security, and cross-repository contract check against the exact API pin and see a passing result.
  2. Maintainer can install the checked release artifact on clean Home Assistant 2026.5.0+ and complete setup, restart, reconfiguration, diagnostics, first poll, unload/reload, and upgrade without an unexplained failure.
  3. On explicitly authorized test hardware, maintainer can perform one reversible safe write, observe optimistic update and device readback, restore the original value, and see unsafe or malformed raw writes rejected.
  4. Maintainer can compare tag, manifest, dependency pin, checksum, package contents, clean import, documentation, and release notes and find one consistent reproducible release pair.
**Plans**: TBD

### Phase 2: Real-Device Compatibility Evidence
**Goal**: Users and maintainers can distinguish confirmed, corrected, expected, and unsupported behavior from redacted real-device evidence instead of register-probe assumptions.
**Depends on**: Phase 1
**Requirements**: COMP-01, COMP-02, COMP-03, COMP-04, DIAG-01
**Success Criteria** (what must be TRUE):
  1. Navigator 2.0/Terra SWM model detection has an evidence-backed classification based on exact read-only probe data, not address 4108 presence alone.
  2. Navigator 2.0 room-mode recovery and applicable eight-room zone behavior each have actionable community confirmation or a documented correction path.
  3. Navigator Pro has a complete redacted diagnostic report that supports an honest model, firmware, zone/room, and compatibility classification.
  4. The generic server-error report has enough diagnostics to classify the failure and choose a justified fix, documentation change, or explicit no-code outcome.
**Plans**: TBD

### Phase 3: Stable Release Decision
**Goal**: Users receive a stable release only when soak evidence and every release gate support it, with limitations and compatibility stated consistently.
**Depends on**: Phase 2
**Requirements**: STAB-01, STAB-02, STAB-03
**Success Criteria** (what must be TRUE):
  1. Maintainer can review the documented beta soak and find no unresolved confirmed data-corruption, reconnect-loop, unsafe-write, or setup-regression blocker.
  2. Maintainer can inspect one gate record covering automation, artifact, smoke, real-device, diagnostics, soak, rollback, and documentation evidence and see an explicit stable-release go/no-go outcome.
  3. Users see the same tested versions, supported/expected devices, limitations, and privacy guidance in release notes, README/wiki documentation, and the compatibility matrix.
**Plans**: TBD

### Phase 4: Home Assistant Core Readiness Gate
**Goal**: Maintainers can make an evidence-backed Core go/no-go decision and, only after a pass, prepare a small reviewable read-only first contribution.
**Depends on**: Phase 3
**Requirements**: CORE-01, CORE-02, CORE-03
**Success Criteria** (what must be TRUE):
  1. Maintainer can trace every proposed Core entry criterion to current evidence and record a go/no-go decision before any Core PR opens.
  2. Reviewer can inspect a first-Core scope containing config flow, model detection, coordinator polling, redacted diagnostics, and essential read-only sensors while seeing write paths, custom actions, broad zones, optional expansions, and quality claims explicitly deferred.
  3. Maintainer can follow a Core-port checklist covering dependency and test conventions, fixtures, the `home-assistant.io` documentation page, brand assets, registry migration, and domain-collision behavior.
  4. If entry criteria remain open, the project continues as HACS without presenting the draft Core page or deferred HACS features as accepted first-Core scope.
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:** Phase 1 → Phase 2 → Phase 3 → Phase 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Reproducible Release Qualification | 0/TBD | Not started | - |
| 2. Real-Device Compatibility Evidence | 0/TBD | Not started | - |
| 3. Stable Release Decision | 0/TBD | Not started | - |
| 4. Home Assistant Core Readiness Gate | 0/TBD | Not started | - |
