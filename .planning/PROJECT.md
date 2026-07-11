# IDM Heatpump for Home Assistant

## What This Is

IDM Heatpump is a mature, unofficial Home Assistant custom integration for locally monitoring and controlling IDM Navigator 2.0, Navigator 10, and Navigator Pro heat pumps over Modbus TCP, with an optional read-only local web supplement. The current milestone is not a rebuild: it closes the remaining release-evidence, hardware-compatibility, stability, and Home Assistant Core-readiness gaps around the shipped integration.

## Core Value

Users retain safe, reliable, 100% local heat-pump monitoring and control across supported IDM Navigator hardware.

## Success Metric

A release is ready only when tests, strict typing, lint, API contracts, write safety, and supported real-device behavior are verified.

## Requirements

### Validated

- ✓ Local Modbus TCP polling and dynamically generated sensor, binary-sensor, number, select, and switch entities are shipped.
- ✓ Register metadata comes from `idm-heatpump-api`, with model/capability gates, contextual sentinels, bounded adjacent batches, and resilient isolation of unsupported addresses.
- ✓ Setup, reconfiguration, options, web-only fallback, diagnostics, repair issues, unload/reload, and optional local web supplementation are implemented.
- ✓ Generated writable entities, dedicated actions, raw-write risk acknowledgement, datatype validation, cyclic writes, and EEPROM protections are implemented.
- ✓ Releases use an exact `idm-heatpump-api` pin and have automated pytest, strict mypy, Ruff, HACS, Hassfest, cross-repository contract, artifact, and smoke-test infrastructure.

### Active

- [ ] Produce reproducible automated, artifact, clean-install, lifecycle, and safe-write evidence for a stable release candidate.
- [ ] Close the remaining Navigator 2.0, Terra SWM, eight-room zone, Navigator Pro, and generic-server-error evidence gaps without guessing from probe addresses.
- [ ] Complete a beta soak and make an auditable stable-release go/no-go decision with documentation, package, and compatibility data aligned.
- [ ] Audit the proposed HACS-first entry criteria and prepare a deliberately small, read-only first-Core scope only when those criteria pass.

See `.planning/REQUIREMENTS.md` for the 15 uniquely identified v1 requirements.

### Out of Scope

- Cloud login, cloud polling, subscriptions, or remote cloud control — the integration remains 100% local.
- Serial Modbus RTU, pre-Navigator controllers, and other heat-pump manufacturers — they use different transports or register models.
- Firmware, configuration, or SD-card writes and guessed binary/web protocol behavior — insufficient safety and protocol evidence.
- A climate entity — IDM circuit, room, cooling, and hot-water semantics do not yet map cleanly without hiding controller state.
- A full immediate Home Assistant Core port — Core work remains gated by HACS stability and hardware evidence.
- Write-enabled entities, custom actions, advanced services, broad zone/optional feature coverage, or Gold/Platinum claims in the first Core PR — explicitly deferred by the proposed Core strategy.

## Context

- Current integration/API pair: `0.8.1-beta.29` with exactly pinned `idm-heatpump-api[web]==0.7.6`.
- Navigator 10 has direct maintainer read-only hardware evidence; Navigator 2.0, Terra SWM, and Navigator Pro still depend on stronger community diagnostics.
- The current stability audit found no raw mismatch in 309 batch-versus-individual comparisons on one Navigator 10 system, but that result is not a universal performance or compatibility guarantee.
- Remaining stable-release gates include a clean-install smoke test, community confirmations, actionable diagnostics for the generic server error, and a regression-free beta soak.
- The source corpus and conflict analysis are summarized in `.planning/intel/SYNTHESIS.md`; no blockers or competing requirement variants remain.

## Constraints

- **Target runtime**: Home Assistant 2026.5.0 or newer, Python 3.13+, IDM Navigator 2.0/10/Pro, 100% local — compatibility and privacy boundary supplied for this milestone.
- **Protocol**: Modbus TCP is the baseline; optional Navigator web data is local, read-only, additive, and non-fatal — no cloud dependency.
- **Register authority**: `idm-heatpump-api` owns register schema, datatypes, access flags, model support, sentinels, and write classes — no ad-hoc platform addresses.
- **Release reproducibility**: Every integration release pins the exact tested API version and aligns tag, manifest, package, checksum, documentation, and release notes.
- **Write safety**: Prefer generated entities; preserve datatype/range/model metadata, EEPROM limits, cyclic-write behavior, explicit raw-write acknowledgement, and numeric validation.
- **Evidence**: Hardware investigation is read-only unless the owner explicitly authorizes a specific reversible write; diagnostics and reports must redact private device and network data.
- **Quality gate**: Tests, strict typing, lint, API contracts, write safety, and supported real-device behavior must all be verified before release.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| HACS first, Core later (proposed, non-locked) | Stabilize the hardware matrix, API contract, release process, and write safety before a small Core contribution. | — Pending |
| Keep the first Core PR central and read-only | A small config/model/coordinator/diagnostics/sensor slice is reviewable and avoids importing every HACS feature at once. | — Pending entry-criteria audit |
| Keep Modbus as the authoritative baseline and web data optional | Preserves local control and avoids duplicate or cloud-dependent values. | ✓ Good |
| Keep register definitions library-first | One typed, model-gated contract supports both API and Home Assistant behavior. | ✓ Good |
| Release integration beta.29 with API 0.7.6 | Sticky web-protocol orchestration and diagnostic redaction are integration-side changes; the pinned API already provides the required clients and register metadata. | ✓ Verified |

## Evolution

After each phase, move verified active requirements to validated, record scope changes and decisions, and re-check whether the HACS-first strategy remains appropriate. After the milestone, review the Core value, compatibility evidence, stable-release outcome, and deferred Core scope before adding new feature work.

---
*Last updated: 2026-07-11 after documentation ingest and brownfield roadmap initialization*
