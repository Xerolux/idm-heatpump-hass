# AI and advisor improvements - 2026-11-04

Baseline: integration `0.25.0-b6`, `origin/main` at `4215e3a`.
The existing local audit correction in energy statistics is retained.

## Review scope

Reviewed measured-data reports, optional local/cloud provider prompts and
their numerical projection/response guards, persistent local learning,
predictive advisor inputs and quality tracking, forecast aggregation, health
checks, operation explanations and the deterministic local Assist agent.
Provider consent, fixed endpoints, budgets, credential redaction and read-only
analysis boundaries remain in place. No provider request or plant write was
made during this work.

## Improvements

- Reports open with a purpose-specific daily, weekly, health or efficiency
  focus and explain incomplete evidence before presenting conclusions.
  Observed counter hours and missing time supplement coverage percentages.
- Energy intervals are sorted and deduplicated. Comparisons require equal
  requested durations, at least 90% coverage in each window and no more than
  two percentage points of coverage difference. Zero baselines never produce
  a percentage change. Neither lower consumption nor higher observed COP is
  presented as verified savings or a causal diagnosis.
- Local and cloud prompts prioritize the finding, supporting evidence and
  limitations, using calculated comparison values. Only selected numerical
  summary fields cross the existing opt-in provider boundary. The numeric
  guard handles signed changes and their percentage units consistently.
- Room inputs share Celsius conversion for Fahrenheit/Kelvin sources in
  both quality tracking and model fitting. Configured but unavailable or
  mismatched sources cannot silently switch to a register measurement.
- Failed updates break training intervals. Exact operating modes determine
  per-domain COP attribution. Old learning rows without dispersion moments
  retain their mean without claiming a zero standard deviation. Learning
  distinguishes idle, stale input and missing outdoor temperature.
- Forecast PV periods split at hour boundaries and duplicate timestamps count
  once. Forecast generation is explicitly distinguished from confirmed
  surplus. Daily heat demand requires a consecutive grid of 24 unique hours;
  warm hours do not offset cold-hour heating demand.
- Running explanations favor reported operating modes and controller demand
  over temperature guesses. Reached/exceeded DHW targets and missing circuit
  temperatures have accurate explanations.
- Missing COP is unknown rather than a passed check; stale health readings
  remain unknown while confirmed communication failures stay visible.
- Assist accepts subzero outdoor temperatures, declines to infer fault-free
  operation from absent alarm values and explains failed updates. Its energy
  answer labels instantaneous COP, supports the alternate thermal register
  and formats German decimal values with commas.

## Validation and limits

Regression scenarios cover the above evidence failures, forecast boundaries,
legacy storage and German/English explanations. Strict mypy uses the genuine
Home Assistant 2026.11.0b0 runtime with API 2.16.0b2. The real-HA lifecycle
smoke suite passes all eight tests using a fake plant transport. Config-flow
coverage remains 100% (226 tests). Ruff lint/format and documentation checks
pass. The English wiki and its German mirrors document the changed behavior.

Final full-suite result: **3312 passed, 2 skipped**, overall coverage **98.83%**
(95% required). Compared with the preceding audit, 41 additional regression
scenarios cover the AI/advisor changes. Ruff formatting covers 179 files;
strict mypy passes all 81 integration modules.

No live Ollama or cloud-model output was evaluated. Prompt improvements are
covered through request contracts and deterministic fact/guard scenarios;
free-form text remains explicitly unverified. The analysis still cannot infer
causality, reconstruct past misattributed counters or establish physical
controller behavior. Short forecast grids may now leave a daily-demand sensor
unknown instead of displaying an extrapolated figure. Changes remain local;
no deployment, release or push was performed.

## Feature follow-up: shared evidence and observed optimization review

Implemented the five requested extensions on the same local branch:

1. A shared change analysis covers energy, COP, observed compressor starts,
   DHW operating-time share, room deviation, weather context and missing data.
   Zero means no marked change; unavailable means no comparable windows.
2. Heating-curve readback changes are recorded across restarts, including a
   reversal between sampled history points. Review uses 72-hour before/after
   windows, six settling hours, 80% counter coverage, pure heating mode and
   matching two-degree outdoor bins. At least six matched heating hours and
   60% overlap are needed. Room targets, comfort, cycling and overlapping
   changes can block an otherwise attractive efficiency verdict.
3. Recommendations carry localized structured evidence: observations, reason
   explanations, current/suggested values, confidence interpretation, missing
   evidence and a first check. These are displayed in attributes and Assist.
4. Assist supports changes, higher consumption, cycling, missing evidence and
   the latest observed optimization result, using the same renderer as reports.
5. Reports, advisor entities and Assist consume one entry-owned numerical
   history and one cached analysis. The new `advisor_changes` and
   `advisor_optimization_review` sensors expose it without a model. Generated
   dashboards add a registry-aware Advisor view and explanation cards.

The shared store retains up to 28 days within a separate conservative 4 MiB
cap. Old details are pruned first. There is no Recorder backfill and no change
to the existing AI history/budget configuration. Collection only runs while
one of the two advisor features is enabled; it creates no background task.
Entity-aware polling retains its required registers even if raw sensors are
disabled. Stored analysis survives reload, and unload persists the final data.

Readback evidence does not identify who changed a curve or establish a manual
action. Descriptive review thresholds are not significance tests. Even a
positive outcome explicitly leaves causality and actual savings unverified.
Cloud input remains a numerical allowlist plus fixed status labels; circuit
keys and raw histories are excluded. No live model request, device write,
deployment or release was performed.

Feature follow-up validation:

- Full unit suite: **3343 passed, 2 skipped**, coverage **98.42%** (95% required).
- Config-flow coverage: **100%**, 226 tests passed.
- Genuine HA lifecycle smoke: **9 passed**, including real Store persistence of
  a simulated heating-curve change across reload, enum entity states and
  no remaining tasks after unload. Plant transport remains fake.
- Final targeted report/provider/Assist/evidence checks: **129 passed**.
- Strict mypy: **82 modules passed**. Ruff lint/format and documentation
  version/language/translation/changelog checks passed.
