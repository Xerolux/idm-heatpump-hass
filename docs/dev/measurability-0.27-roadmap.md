# Measurability and clarity — the 0.27 roadmap

Decided: 2026-11-10. Planned minor line: `0.27.0` (betas from `v0.27.0-b1`).
Baseline: integration `0.26.13`, Home Assistant `2026.11.0` minimum,
`idm-heatpump-api[web]==2.16.2`.

Both prior roadmaps are fully worked off: the feature roadmap
(`heatpump-feature-roadmap.md`) and all nine predictive-advisor phases
(`predictive-advisor-roadmap.md`). The remaining backlog items are blocked on
field data or owner decisions (see `open-work-audit.md`). Version 0.27 therefore
takes its scope by decision, and the decision is: make the plant measurable and
make the analysis understandable — everything in this line is local,
deterministic and read-only, and each package directly serves the open
field-evidence tasks instead of waiting for them.

## Work packages

### WP1 — Request-level Modbus timing and count metrics

Today `PollStatistics` exposes whole-poll aggregates (`last_duration`,
counters, per-register outcomes via the API's `get_register_outcomes`), and the
scan-interval repair reacts to a poll that saturates its interval. What is
missing is the request level: how long each physical request (FC03/FC04/FC16,
including bisection re-reads and web fallback reads) takes, how many run per
poll cycle, and how durations distribute.

- Instrument the transport boundary (`modbus_transport.py`,
  `modbus_shared_transport.py`) with passive per-request timing: function code,
  register range size, duration, outcome (success/timeout/error class). No new
  I/O, no behavior change — measurement only, behind the existing request lock.
- Aggregate in a bounded, in-memory ring (for example the last 100 requests per
  entry): count, error counts by class, min/median/avg/max/p95 duration, split
  by transport source (shared link vs. private socket).
- Surface the aggregates in the diagnostics export and as attributes of a
  diagnostic-category sensor, so a reporter can attach evidence without a full
  diagnostics download. Privacy: keep the existing redaction rules; register
  addresses and counts are fine, host/PIN stay redacted.
- Purpose: this is the measuring stick for the open hardware validations —
  shared-link multi-entry observation, maximum-plant response times, Navigator
  2.0/Pro binary semantics — and for `#594` captures.

### WP2 — Fixable scan-interval repair with a concrete suggestion

The non-fixable warning from `#222` (`_evaluate_poll_duration`,
`_SCAN_INTERVAL_TOO_LOW_ISSUE`, 0.8 of the interval, streak-guarded) tells the
user *that* the interval is too low, but not *what to choose*.

- Extend the existing issue (do not build a second one): propose a concrete
  interval derived from the measured durations (for example p95 request-chain
  duration from WP1, rounded up to the next sensible step), named in the
  translation placeholders.
- Make the repair fixable through `repairs.py`: a repair step that shows the
  suggested value and writes it into the entry options through the existing
  options flow validation — the user confirms, nothing adapts silently.
- Keep the streak logic (no flapping), keep the warning path for users who
  cannot change the interval.

### WP3 — Localized advisor recommendation titles and descriptions

`Recommendation.summary()` already renders a localized `explanation` via
`explain_recommendation(..., language)` — but `title` and `description` are
hardcoded English strings from `advisor_engine.py` (four construction sites,
including the anomaly `title=message` path). The phase-1 decision said
producers ship translation keys (spec §13); this closes that gap.

- Replace the hardcoded strings with stable recommendation title keys plus
  placeholders (circuit, values, units), translated in `strings.json`,
  `translations/en.json`, `translations/de.json`, following the existing
  generator pipeline where applicable.
- Persist keys, not rendered strings: stored recommendations keep their ids,
  categories and reason codes unchanged, and rendering happens at display time —
  that keeps the store migration-free and language-switchable.
- Machine-readable surfaces (event payloads, `idm_advisor_recommendation`,
  Assist answers, diagnostics) keep their documented English data fields;
  localization is additive, not a breaking attribute rename.

### WP4 — Accompanying, evidence-driven items (not version blockers)

- `#493`: once IDM's written answer arrives (all five values per write?),
  carry it into the forwarding documentation and the options-flow help texts;
  clarify the "unknown vs. unavailable" presentation under HA 2026.11.
- `#577`: parser work only on attributable evidence (private capture or the
  reporter's diagnostics), per the open-work-audit decision rule.
- `#668`: close after the reporter confirms 0.26.7 on the reporting plant.

## Non-goals

- No new write paths, no automatic writes, no advisor apply-service (that
  remains the separately reviewed subject of a later line).
- No failure prediction, no tariff/PV/battery control, no occupancy schedules —
  all still blocked on data or an explicit owner decision.
- No second Modbus transport path; WP1 instruments the existing boundary.

## Definition of done (per package and for the release)

- Unit regressions per behavior; overall coverage stays at or above 95,
  `config_flow.py` at 100.
- Strict mypy against the real Home Assistant runtime; ruff clean.
- Real-HA lifecycle smoke tests green.
- Wiki: every user-visible change lands on its English page and the German
  mirror in the same pull request; `check_wiki_coverage.py` updated.
- Release notes follow the CONTRIBUTING.md style with an upgrade-notes block.
