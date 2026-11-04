# Integration audit - 2026-11-04

Baseline: `origin/main` at `4215e3a`, integration `0.25.0-b6`.
Branch: `Xe/audit-2026-11-04`.

## Scope

Fetched remote branches and tags into a clean working tree, then created an
audit branch from current main. Reviewed recent coordinator, sensor metadata
and sentinel logging changes, shared transport and recovery handling, external
measurement forwarding, entity-aware polling and energy statistics. This is a
focused source review with automated quality checks, not an exhaustive proof
that the integration is defect-free.

## Confirmed correction

Per-mode energy statistics accepted heating or hot-water bits even when a
cooling bit or unknown bits were also present. Python's IntFlag conversion
also wrapped some negative values into apparently usable modes. Two snapshots
with such a status contaminated the dedicated energy counters and COP values.

Six new parameterized regression cases reproduced the issue before the fix.
Only the exact heating and hot-water statuses now feed dedicated counters.
All-mode energy integration remains intact. This also simplifies classification
by removing unnecessary flag construction and masking. Historical counters
cannot be reconstructed from the stored aggregates and are left intact.

## Validation environment

Python 3.14.2; real Home Assistant 2026.11.0b0 and manifest-pinned API
2.16.0b2 in `test_ha`. The older `.venv` contains API 2.14.5b2 and produced
translation-contract failures; that run is not valid release evidence.
The matching runtime passes those translation tests.

## Validation

- Full unit suite: 3271 passed, 2 skipped; overall coverage 98.85%
  (required minimum 95%).
- Strict mypy: 80 source files pass against real Home Assistant.
- Ruff lint and formatting pass; Git whitespace check passes.
- Genuine Home Assistant lifecycle smoke tests: 8 passed with fake plant I/O.
- Config-flow and guided-flow tests: 226 passed; config-flow coverage 100%.
- Energy statistics and entity translations: 33 passed in the matching runtime.
- Changelog style/consolidation, wiki changelog and documentation language:
  29 passed. Documentation version claims match the manifest.

## Limits

No physical heat-pump writes, live-system deployment, release or push was
performed. Existing Home Assistant/aiohttp warnings remain visible in the
smoke output. The three-second external-power refresh is an existing mitigation
for volatile GLT inputs; changing its cadence needs controller readback evidence
and is not justified by a local code review alone.
