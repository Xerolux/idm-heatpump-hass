# Plan 03-01 Summary — Model-Conflict Diagnostic + #170 Re-verification

## What was done

Added a structured, fully redacted model-conflict diagnostic and re-verified the #170 setpoint symptom against the #172 fix — no model-selection change.

## Changes

- `coordinator.py`: new read-only `model_conflict_summary` property deriving selected/stored Navigator family, web variant, firmware evidence, manual override, and a `conflict` flag from existing detection fields only (no I/O, no selection, no persistence).
- `diagnostics.py`: `_model_conflict_diagnostics` helper emits the structured block; `TO_REDACT` extended to redact `myidm_id`, `serial_number`, `serial`; `model_conflict` added to the diagnostics `data` output.
- `tests/test_diagnostics.py`: `model_conflict` block structure, conflict+override reflection, and private-data redaction (incl. myIDM/serial).
- `tests/test_coordinator.py`: `TestModelConflictSummary` (match/conflict/override/missing-stored cases).
- `tests/test_platforms.py`: `TestClassifySetpoints170` — model-supported PV-surplus writable target is created under sentinel (#172 path resolves #170 for supported models); when the register is absent from the dataset it is not created (a detection defect stays observable and separable).

## Verification

`pytest tests/test_diagnostics.py tests/test_web_data.py tests/test_coordinator.py tests/test_platforms.py tests/test_entity.py -q` → green.

## Requirements covered

MODEL-01 (setpoints classified as resolved-by-#172 for supported models vs. a distinct remaining defect when excluded), MODEL-02 (structured redacted diagnostic).

## Classification outcome

MODEL-01: the missing #170 setpoints are the #172 writable-sentinel path for model-supported registers. MODEL-02 diagnostic is available. MODEL-03/MODEL-04 require redacted field evidence (plan 03-02).
