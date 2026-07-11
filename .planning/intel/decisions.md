# Synthesized Decisions

## HACS first, Core later

source: docs/CORE_STRATEGY.md

- Status: proposed
- Locked: false
- Decision: Continue as a HACS custom integration until the hardware matrix, API contract, release process, and write-safety behavior have had a stable maintenance period. When a Home Assistant Core contribution is attempted, keep the first PR small and limited to a central platform with essential read-only monitoring.
- Deferred from the first Core PR: write-enabled entities, custom actions and advanced services, broad zone-module coverage, optional cascade/PV/solar/ISC expansions, and Gold or Platinum quality claims.
- Entry criteria: current Navigator 2.0 and Navigator 10 confirmations; a stable, exactly pinned API contract; model-gated registers; lifecycle, diagnostics, and repair tests; documented release and rollback; and repository protections and security automation.
- Scope: HACS custom integration; Home Assistant Core contribution; entry criteria; initial Core scope; Core port adjustments; HACS-to-Core migration.
