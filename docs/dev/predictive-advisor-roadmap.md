# Predictive advisor roadmap

This roadmap turns the owner's predictive-advisor specification into the
integration's phased plan. The specification's single non-negotiable rule
leads everything else:

> The advisor may READ, ANALYZE and RECOMMEND. It never WRITES. No advisor
> code path may change a setpoint, heating curve, mode, schedule, coil or web
> setting on its own — not even a "sensible" one. The Navigator controller
> stays the leading regulator; every change to the plant is the user's
> explicit action on the regular control entities.

Phase 1 ships the framework below. Every later phase is a *producer* that
feeds `PredictiveAdvisor.submit()`; none of them adds a write path.

## Shipped in phase 1

| Piece | Where | Notes |
|---|---|---|
| Recommendation model | `predictive_advisor.py` `Recommendation` | id, category, severity, title, current/recommended value, unit, confidence, machine-readable reason codes, status; JSON round-trip for storage |
| Lifecycle | `PredictiveAdvisor.submit`/`mark` | `new → viewed → accepted/dismissed`, internal `expired`/`obsolete`; `accepted` is an acknowledgment only — nothing is ever written. Bounded history (50) per entry |
| Events | `idm_advisor_recommendation` | fired on `new`, `updated` and `status`; payload mirrors the spec (category, values, confidence, reasons) |
| Confidence | `evaluate_confidence`/`confidence_level` | documented formula: 60 % observation coverage (full after 14 days) + 40 % usable-sample share; four levels low/medium/high/very_high — no pseudo-precision |
| Capability detection | `AdvisorCapabilities` | power/heat meter, room temperature, flow sensor, compressor, PV signal, power limit, buffer, demand reason, dynamic price source, PV source; every later feature activates capability-based |
| Data-quality gate | `classify_sample`/`_KeyQuality` | per-key sample classification unavailable/implausible/frozen/usable with documented plausibility ranges; frozen = nonzero power/thermal/flow value unchanged ≥ 3 h (idle zeros are legitimate); gaps reset the baseline |
| Observation stages | `observation_stage` | `collecting` (< 1 d) → `early_hints` (< 7 d) → `recommending` (< 30 d) → `established` (≥ 30 d); no recommendations before day 7 |
| Persistence | HA Store `idm_heatpump.predictive_advisor.<entry_id>` | restart-safe (first-observed timestamp, active recommendations, history, quality counters); delayed save 10 s, full save on unload |
| Entities | `predictive_advisor_entities.py` | `sensor.advisor_status`, `sensor.advisor_recommendations`, `binary_sensor.advisor_optimization_available`; Smart profile only; `advisor_` prefix participates in feature cleanup |
| Polling | `coordinator.register_required_registers("predictive_advisor", …)` | the watched keys stay polled even when their entities are disabled |

## Phase plan

All nine phases are implemented. Phases 2-9 ship as producers on top of the
phase-1 framework: `advisor_analytics.py` (baselines, COP map, building
model), `advisor_operation_reason.py` (why is the heat pump running) and
`advisor_engine.py` (anomalies, health/efficiency scores, heating curve,
DHW window from PV/price forecasts, 24 h plan). The PV forecast sensor is
the `advisor_pv_forecast_entity` option; the price sensor reuses the
existing `dynamic_price_entity`.

| Phase | Content | Builds on |
|---|---|---|
| 2 — Diagnostics | Operation reason ("why is the heat pump running"), DHW status explanation, flow/spread/DHW-charge-time baselines | `web_demand_reason.py` (Nav 10 demand reason already decoded), `operation_analysis.py` (cycle baselines; needs flow-rate + spread tracking added) |
| 3 — Plant health | Anomaly detection vs. own baselines, trend detection, health components, health score with documented composition | `health_monitor.py` checks become anomaly *producers*; score only where the composition is documented |
| 4 — Efficiency | COP map (outdoor × flow × load), expected COP, efficiency score, operating-point deviation | `ai_learning.py` buckets (mode × outdoor-bin energy baselines) as the storage pattern; `calculated_sensors._cop` |
| 5 — Building model | Heat loss, thermal inertia, heat-up/cool-down rates, flow-temperature demand; passive learning only | `ai_learning.py` observation discipline (gap rejection, mode changes) |
| 6 — Heating-curve advisor | Over/under-supply detection, curve evaluation, recommendation with confidence + explanation; no automatic adoption | `comfort_advisory.heating_curve_advisory` (existing flow-deviation hint), phase 5 model |
| 7 — PV advisor | PV forecast entity (configurable), predicted surplus, DHW/heating window recommendations | `CONF_WEATHER_ENTITY`/preheat pattern for entity wiring; `evaluate_pv_surplus_state` |
| 8 — Price advisor | Price entity, future prices, heat cost per kWh (price ÷ expected COP), cheap operating windows | `CONF_DYNAMIC_PRICE_ENTITY` already feeds `energy_statistics.py`; phase 4 COP map |
| 9 — Predictive advisor | 24 h plan joining building model, weather, PV, price, COP map, DHW state | everything above |

## Deliberate phase-1 decisions

- **No own option toggle.** The framework rides the Smart feature profile,
  like energy statistics and operating analysis. A dedicated toggle and
  configurable observation windows arrive with the first producer phase that
  needs them.
- **Event names follow the specification** (`idm_advisor_recommendation`,
  later `idm_advisor_anomaly`, `idm_advisor_efficiency_warning`,
  `idm_advisor_health_warning`) rather than the `DOMAIN` prefix, per the
  owner's document.
- **Recommendation titles are English data, not translations, in phase 1.**
  With no producers there is nothing user-facing to translate; producers must
  ship translation keys for their categories (spec §13) when they arrive.
- **No accept/apply service in phase 1.** Applying a recommendation (§20)
  requires the confirmation chain plus rollback journal (§21) and is the
  explicit subject of a later, separately reviewed phase. Dismiss/view
  handling arrives with the first UI-bearing producer.
- **`mark(..., ACCEPTED)` never writes** — enforced by the class having no
  write method at all, and asserted in `tests/test_predictive_advisor.py`.

## Adaptation notes (spec ↔ codebase)

The specification names entities `sensor.idm_advisor_status`,
`sensor.idm_expected_cop` etc. This integration prefixes derived entity keys
by module (`advisor_status`, later `advisor_expected_cop`, …) and routes all
names through `entity_names.DERIVED_NAMES` + the translation generator, per
the entity-translations quality rule. The `idm_` device prefix comes from the
device name in Home Assistant, so the user-visible names still read
"iDM Heatpump Advisor status".

The spec's `smart_advisor`/`idm_advisor` module name became
`predictive_advisor` to avoid colliding with the existing experimental
`ai_advisor` (LLM-assisted reports) — the predictive advisor is deliberately
deterministic and local (spec §22–§23).
