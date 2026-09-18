# Experimental AI adviser: implementation and validation

Date: 2026-09-18. Status: v0.17.2-b7 beta, disabled by default.

## Contract

An explicit guided setup category enables local Ollama report generation.
Changing Smart/Vanilla or upgrading alone does not enable it. The feature has
no Home Assistant action tools, device I/O or write callbacks. The existing
heat-pump coordinator is observed, never controlled, and required AI source registers remain in the entity-aware polling plan.
Reports can be requested through four buttons or `generate_ai_report`; an
explicit non-zero interval enables scheduled generation.

Selected temperatures and energy counter samples are retained locally for
rolling daily/weekly summaries and comparisons. History starts at activation;
it is bounded to fourteen days and does not query Recorder. Missing, stale and
reset counters are excluded. Health flags remain deterministic local checks.
Numeric period facts accompany the model's untrusted explanation.

The transport accepts literal LAN/loopback endpoints and disables redirects
and environment proxies. Before sending facts it checks local GGUF completion
metadata and rejects cloud names and remote model metadata. Only fixed prompts
and numeric/boolean allowlisted data are sent. It has no free-text question,
document, entity-name or credentials input. Trust in the configured server is
still necessary; a deliberately forwarding proxy is outside this boundary.

One request per entry, a sixty-second cooldown and a total 180-second deadline
bound inference. Metadata has a one-MiB limit; generated responses have a
64-KiB transport limit and 6,000-character text limit. Tool-bearing, empty,
truncated and malformed responses are rejected. Disabling/unloading cancels
the current request. Failures retain the previous successful report with its
original timestamp and publish an error status. Latest results for all four report types persist in the bounded history store,
including facts and timestamps. Prose and facts remain excluded from Recorder.

## Validation

- Full suite: 1,838 passed, two skipped; integration coverage 95.43%.
- Separate config-flow run: 100% coverage.
- Strict mypy: 57 modules; Ruff lint and formatting passed.
- Documentation-language checks and generated Pages build passed.
- Local Ollama smoke test used only synthetic data, never live plant readings.
  The installed `gemma3:4b` completed the integration client's request in about
  44 seconds and disclosed the 12.5% input coverage and missing prior period.
  Its prose still contained awkward phrasing and a date placeholder. This is
  experimental output, not evidence of diagnostic or optimization accuracy.
- The real model's metadata response was about 78 KiB; this exposed and fixed
  an initially too-small metadata limit. Metadata and report bounds now have
  separate regression coverage.
- No live integration installation, configuration change, pump write, voice
  exposure or Ollama model installation was performed for this feature.

The unit suite uses the project's HA stubs. An installation test of the new
feature on actual Home Assistant and broader model-quality evaluation remain
separate rollout work; neither is implied by the local endpoint smoke test.

## Beta 7 extension validation

The additional `ai_learning.py` module uses bounded daily numeric aggregates,
not model fine-tuning. Samples are matched by operating mode and outdoor
five-degree bin, with a minimum of three earlier days and six hours of data.
Storage, scheduler, restart persistence, notifications and dashboard export
are covered by `tests/test_ai_advisor_extended.py`. The budget is configurable
from 5 to 200 MiB, default 20, with oldest-detail eviction and bounded schemas.
Scheduler due dates are saved before requests; stale deadlines do not produce
catch-up storms. Persistent notifications are the only new HA action path and
are selected by deterministic health flags, never model output.

Local gates: 1,861 passed, two skipped; total coverage 95.49%; config-flow
coverage 100%; strict mypy passed on 58 modules. Exact dependency freshness
checks passed. Live deployment evidence is recorded separately after release.
