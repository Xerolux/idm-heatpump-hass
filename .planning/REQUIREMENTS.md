# Requirements: IDM Heatpump for Home Assistant

**Defined:** 2026-07-11
**Core Value:** Users retain safe, reliable, 100% local heat-pump monitoring and control across supported IDM Navigator hardware.

## v1 Requirements

Requirements for the current verification, stability, compatibility, and Core-readiness milestone. Existing shipped capabilities are baseline context rather than rebuild requirements.

### Release Qualification

- [ ] **QUAL-01**: Maintainer can run the candidate against pytest, strict mypy, Ruff, HACS validation, Hassfest, security/package checks, and cross-repository API contracts with every required check passing against the exact published API pin.
- [ ] **REL-01**: Maintainer can verify that the release tag, manifest version, exact API dependency, checksum, built artifact contents, clean import, documentation, and release notes describe one reproducible release pair.
- [ ] **SAFE-01**: Maintainer can demonstrate on an explicitly authorized reversible register that entity writes validate, update optimistically, read back correctly, restore the original value, and retain EEPROM, cyclic-write, datatype, numeric, and raw-risk safeguards.
- [ ] **OPS-01**: Maintainer can complete the repository smoke test on a clean Home Assistant installation, covering setup, restart, reconfiguration, diagnostics, unload/reload, upgrade, first polling, optional web behavior when available, and safe writes.

### Compatibility Evidence

- [ ] **COMP-01**: Maintainer can resolve or explicitly classify Navigator 2.0/Terra SWM model detection from an exact read-only probe capture without treating address 4108 presence alone as proof.
- [ ] **COMP-02**: Maintainer has actionable Navigator 2.0 community evidence confirming or disproving the room-mode batch-mismatch recovery behavior.
- [ ] **COMP-03**: Maintainer has actionable community evidence confirming or correcting eight-room zone configuration behavior on applicable hardware.
- [ ] **COMP-04**: Maintainer has a complete redacted Navigator Pro diagnostic report sufficient to classify its model, firmware, zone/room capabilities, and support status.
- [ ] **DIAG-01**: Maintainer can classify the unresolved generic server-error report from actionable diagnostics and evidence, without guessing at a code change.

### Stable Release

- [ ] **STAB-01**: Maintainer can show a documented beta soak with no unresolved confirmed data-corruption, reconnect-loop, unsafe-write, or setup-regression report blocking stable release.
- [ ] **STAB-02**: Maintainer can execute one stable-release gate review that records pass/fail evidence for automation, artifact, smoke, hardware, diagnostics, soak, rollback, and documentation readiness.
- [ ] **STAB-03**: User can consult current release notes, README/wiki guidance, and compatibility status that agree on supported models, tested versions, limitations, and required redactions.

### Home Assistant Core Readiness

- [ ] **CORE-01**: Maintainer can audit every proposed HACS-first Core entry criterion from traceable evidence and record a go/no-go decision before opening a Core PR.
- [ ] **CORE-02**: Maintainer has a first-Core scope contract limited to config flow, model detection, coordinator polling, redacted diagnostics, and essential read-only sensors, with write paths, custom actions, broad zones, optional expansions, and quality claims explicitly deferred.
- [ ] **CORE-03**: Maintainer can verify a Core-port checklist covering dependency/test conventions, Core fixtures, documentation, brand assets, HACS-to-Core entity/device registry migration, and domain-collision behavior.

## v2 Requirements

Deferred improvements that may help later milestones but are not stable-release or initial Core-entry requirements.

### Evidence Tooling

- **EVID-01**: User can opt into a redacted selected-register protocol capture that compares batch and individual reads without custom scripts.
- **EVID-02**: Maintainer can persist anonymized compatibility reports by Navigator model and firmware, including capability sentinels.
- **EVID-03**: User can inspect poll timing and request counts in diagnostics and receive adaptive guidance when polling cannot finish reliably within the configured interval.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Cloud login or polling | Violates the 100% local product boundary. |
| Serial Modbus RTU and pre-Navigator controllers | Unsupported transport and register architecture. |
| Firmware/configuration/SD-card writes | Not required for monitoring/control and carries unacceptable device risk. |
| Guessed protocol ports, binary packets, channel meanings, units, or scaling | Evidence is incomplete; guesses would undermine safety and compatibility. |
| Climate entity | Deferred until IDM circuit/room/cooling semantics can be represented without hiding controller state. |
| Full-featured first Home Assistant Core port | Conflicts with the proposed small, read-only Core strategy. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| QUAL-01 | Phase 1 | Pending |
| REL-01 | Phase 1 | Pending |
| SAFE-01 | Phase 1 | Pending |
| OPS-01 | Phase 1 | Pending |
| COMP-01 | Phase 2 | Pending |
| COMP-02 | Phase 2 | Pending |
| COMP-03 | Phase 2 | Pending |
| COMP-04 | Phase 2 | Pending |
| DIAG-01 | Phase 2 | Pending |
| STAB-01 | Phase 3 | Pending |
| STAB-02 | Phase 3 | Pending |
| STAB-03 | Phase 3 | Pending |
| CORE-01 | Phase 4 | Pending |
| CORE-02 | Phase 4 | Pending |
| CORE-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓
- Duplicate mappings: 0 ✓

---
*Requirements defined: 2026-07-11*
*Last updated: 2026-07-11 after ingest-derived roadmap creation*
