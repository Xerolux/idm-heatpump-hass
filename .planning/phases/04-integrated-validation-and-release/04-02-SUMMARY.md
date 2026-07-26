# Plan 04-02 Summary — Changelog + Release-Gate Decision

## What was done

- `docs/CHANGELOG.md`: added a `### Fixed` block under `## [Unreleased]` documenting cause, user impact, workaround, and verification for #171, #172 (and the setpoint part of #170), and the #170 model diagnostic/redaction. The #170 model part is explicitly recorded as an evidence-gated checkpoint.
- No `### Changed` entry was added: no `idm-heatpump-api` pin bump occurred.
- `manifest.json` version left at `0.8.5` — a version bump + `## [X.Y.Z]` heading is applied only at the actual release action.

## Release-gate assessment (REL-02)

| Criterion | Status |
|-----------|--------|
| Automated gate green (pytest/mypy/ruff/contracts) | ✅ (see 04-01) |
| #171 reproduced and fixed | ✅ |
| #172 reproduced and fixed (setup/runtime/reload) | ✅ |
| GLT/setpoint part of #170 verified | ✅ (resolved via #172 for model-supported registers) |
| Model part of #170 field-verified **or** explicitly bounded open | ✅ explicitly bounded open (03-02) |

A bounded, reproducible release is therefore permitted with the #170 model part explicitly documented as an open, evidence-gated checkpoint.

## Remaining human action (not performed)

Creating the actual release is a publish action and was **not** executed: `manifest.json` version bump (e.g. 0.8.6), converting `## [Unreleased]` into a dated `## [0.8.6]` heading, tagging `v0.8.6`, and producing/verifying the release ZIP + SHA-256 per the existing release contract. These await an explicit release instruction.

## Requirements covered

REL-01 (changelog + issue documentation). REL-02 (release gate satisfied for a bounded release; actual publish pending explicit instruction).
