# Predictive Advisor

The Predictive Advisor is a strictly **read-only** analysis and
recommendation layer for your heat pump. It observes the measured data,
learns how your plant behaves and turns that into explainable
recommendations — it never changes anything on the heat pump by itself.

> The Navigator controller remains the leading regulator at all times. The
> advisor advises; every change to the plant is your explicit action on the
> regular control entities.

The advisor is part of the [Smart Energy and Comfort](Smart-Energy-and-Comfort)
profile. It works entirely locally; no data leaves your Home Assistant.

## Enable, disable and what it needs

- **Where**: integration → *Configure* → *Presentation and additional
  features* → **Enable predictive advisor** (also part of the guided setup as
  its own page). On by default with the Smart Energy & Comfort profile.
- **Turning it off** removes every `advisor_*` entity after a reload; the
  collected statistics are kept and return when you re-enable it.
- **No AI required.** Everything is deterministic statistics — baselines,
  regressions and window searches — computed locally on your Home
  Assistant. It does not use, need or offer any cloud or LLM. The
  *Experimental AI plant adviser* is a completely separate feature; the
  predictive advisor works without it.
- **Optional inputs**: a weather entity (already used by the weather advice),
  a PV forecast sensor and a dynamic electricity price sensor. Every one of
  them is optional — missing inputs simply disable the affected
  recommendation, nothing is invented.

After installing an update you will find a one-time notice in
**Settings → Repairs** ("What's new since 0.20.1") summarizing what was
added — dismiss it there once you have seen it. It appears **exactly once
per installed update**: never on a fresh installation, never again on
restarts or reloads, and only again when the next update is installed.

## Entities

All entities appear under the Smart profile and become meaningful as the
advisor collects data. Sensors that depend on not-yet-learned models stay
unavailable instead of guessing.

| Entity | Meaning |
|---|---|
| `sensor.<device>_advisor_status` | Observation stage: **Collecting data** (day 1), **Early hints** (days 1–7), **Recommending** (from day 7), **Established** (from day 30). Attributes show detected plant capabilities, data quality and the current confidence |
| `sensor.<device>_advisor_recommendations` | Number of active recommendations; each one is published with its full explanation (reasons, values, confidence) as an attribute |
| `sensor.<device>_advisor_confidence` | Framework confidence in percent with its level |
| `sensor.<device>_advisor_operation_reason` | Why the heat pump runs right now (PV surplus, hot water, a requesting heating circuit, controller demand reason), with the numbers behind it |
| `binary_sensor.<device>_advisor_anomaly_detected` | On while an anomaly recommendation is active |
| `sensor.<device>_advisor_health_score` | Plant health 0–100 from documented components (hydraulics, compressor, hot water, efficiency); each component exists only with baseline data |
| `sensor.<device>_advisor_expected_cop` / `advisor_efficiency_score` | COP the learned outdoor/flow map expects at the current operating point, and how the observed 7-day COP compares |
| `sensor.<device>_advisor_building_heat_loss` | Building heat loss in W/K from the thermal-power regression |
| `sensor.<device>_advisor_building_thermal_inertia` | Effective heat capacity (kWh/K) from observed cooldown episodes |
| `sensor.<device>_advisor_optimal_flow_temp` | Flow temperature the learned curve produced at the current outdoor temperature while rooms held their setpoint |
| `sensor.<device>_advisor_hc_X_curve_recommendation` | Heating-curve recommendation per circuit — at most one documented 0.02 step at a time, only after 7 baseline days of room-temperature deviation |
| `sensor.<device>_advisor_dhw_recommendation` | Best hot-water charging window from the PV forecast (preferred) or the cheapest heat cost (price ÷ expected COP) |
| `sensor.<device>_advisor_predicted_heat_demand` | Predicted thermal demand for the next 24 hours (heat loss × forecast temperature difference) |
| `sensor.<device>_advisor_next_24h` | The joined plan: expected PV, expensive hours, and a conflict warning when the hot-water window overlaps them |
| `binary_sensor.<device>_advisor_optimization_available` | On while at least one unhandled recommendation is active |

### Where the external inputs come from

- **Weather**: the existing *Weather entity* option (hourly forecast via
  `weather.get_forecasts`).
- **PV forecast**: optional sensor in the options
  (*Predictive advisor PV forecast sensor*); PVForecast-style
  `detailed_forecast` attributes and Solcast-style `forecast` lists are
  understood.
- **Electricity price**: the existing *Dynamic electricity price sensor*
  option; future hourly prices are read from common attribute shapes
  (`today`/`tomorrow`/`data`/`prices` lists).

Missing or unparsable inputs leave the affected recommendation out — the
advisor never falls back to invented numbers.

### Events

Every new, changed or acknowledged recommendation fires an
`idm_advisor_recommendation` event you can use in automations:

```yaml
event_type: idm_advisor_recommendation
data:
  action: new          # new | updated | status
  id: heating_curve_a_20261007
  category: heating_curve
  severity: info
  confidence: 0.91
  confidence_level: very_high
  current_value: 0.35
  recommended_value: 0.32
  reasons:
    - room_temperature_above_target
    - flow_temperature_above_estimated_requirement
```

### How confidence works

Each recommendation carries a confidence value with four levels — low,
medium, high, very high — instead of pseudo-exact percentages. The score is
a documented formula: 60 % observation coverage (complete after 14 days)
plus 40 % share of usable samples. Bad data (unavailable, implausible or
frozen sensors) lowers the confidence instead of producing recommendations.

### Data quality

Before anything is analyzed, every input is classified sample by sample:
unavailable, implausible (outside the documented range), frozen (a nonzero
power or flow reading that has not moved for three hours) or usable.
Recommendations are never built on bad data.

## What the advisor will never do

- Change setpoints, heating curves, modes, schedules or power limits
- Activate PV boost or priority charging on its own
- Write registers, coils or web settings
- "Apply" a recommendation without your explicit confirmation

Accepting a recommendation in a future UI records only that you consider it
sensible. Applying a value remains a separate, confirmed user action, with
the previous value journalled so it can be restored.
