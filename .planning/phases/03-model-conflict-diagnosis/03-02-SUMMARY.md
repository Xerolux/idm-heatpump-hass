# Plan 03-02 Summary — Evidence-Gated Model Correction (CHECKPOINT)

## Status: OPEN — evidence-gated checkpoint

No redacted field diagnostic or reproducible fixture confirming a model misclassification is available in the repository. Per the blocking checkpoint (Task 03-02-00), no category (A/B/C/D) could be confirmed, and therefore **no model-selection correction was applied**.

## Evidence required from the reporter

- Home Assistant diagnostics export (host/PIN/serial redacted — the integration now redacts myIDM/serial automatically)
- Debug log from setup up to the conflict warning
- Displayed Navigator version + firmware string
- Manual model override value
- Fresh `detect_model()` result and stored detection fields
- Web variant and firmware prefix

## What was done (non-blocking)

- The new `model_conflict` diagnostics block (from 03-01) gives the reporter a copy-pasteable, redacted evidence payload: selected/stored family, web variant, firmware evidence, manual override, and the conflict flag.
- MODEL-03/MODEL-04 remain a documented open checkpoint. The integration never switches Navigator family on a conflicting, unconfirmed display name.

## Next step

Once redacted evidence is provided, classify into A/B/C/D and execute 03-02-01 (integration reconciliation fix for B/C) or 03-02-02 (exact-pinned `idm-heatpump-api` release for D). Until then, this plan stays open and no correction is merged.

## Requirements status

MODEL-03: open (awaiting evidence). MODEL-04: open (would route through an exact-pinned upstream release if category D is confirmed).
