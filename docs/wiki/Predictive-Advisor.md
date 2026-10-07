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

## What phase 1 provides

The first phase lays the foundation and starts collecting. After enabling
the Smart profile you will see:

| Entity | Meaning |
|---|---|
| `sensor.<device>_advisor_status` | Observation stage: **Collecting data** (day 1), **Early hints** (days 1–7), **Recommending** (from day 7), **Established** (from day 30). Attributes show detected plant capabilities, data quality and the current confidence |
| `sensor.<device>_advisor_recommendations` | Number of active recommendations; each one is published with its full explanation (reasons, values, confidence) as an attribute |
| `binary_sensor.<device>_advisor_optimization_available` | On while at least one unhandled recommendation is active |

Recommendations themselves arrive with the later phases (heating curve, hot
water, PV, electricity price, 24-hour plan — see the roadmap in
`docs/dev/predictive-advisor-roadmap.md`). Until then the sensors honestly
report that the advisor is still collecting.

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
