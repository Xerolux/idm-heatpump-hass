"""Tests for the read-only predictive advisor framework (phase 1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.idm_heatpump import predictive_advisor as predictive_advisor_module
from custom_components.idm_heatpump import predictive_advisor_entities as predictive_advisor_entities_module
from custom_components.idm_heatpump.advisor_analytics import AdvisorAnalytics
from custom_components.idm_heatpump.advisor_engine import AdvisorEngine
from custom_components.idm_heatpump.binary_sensor import async_setup_entry as async_setup_binary_sensors
from custom_components.idm_heatpump.predictive_advisor import (
    EVENT_IDM_ADVISOR_RECOMMENDATION,
    AdvisorCapabilities,
    ConfidenceLevel,
    PredictiveAdvisor,
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
    RecommendationStatus,
    SampleQuality,
    clamp_confidence,
    classify_sample,
    confidence_level,
    detect_capabilities,
    evaluate_confidence,
    observation_stage,
    recommendation_from_dict,
)
from custom_components.idm_heatpump.predictive_advisor_entities import (
    IdmAdvisorAnomalyBinarySensor,
    IdmAdvisorBuildingHeatLossSensor,
    IdmAdvisorBuildingInertiaSensor,
    IdmAdvisorConfidenceSensor,
    IdmAdvisorCurveSensor,
    IdmAdvisorDhwWindowSensor,
    IdmAdvisorEfficiencySensor,
    IdmAdvisorExpectedCopSensor,
    IdmAdvisorHealthScoreSensor,
    IdmAdvisorHeatDemandSensor,
    IdmAdvisorOperationReasonSensor,
    IdmAdvisorOptimalFlowSensor,
    IdmAdvisorOptimizationBinarySensor,
    IdmAdvisorPlanSensor,
    IdmAdvisorRecommendationSensor,
    IdmAdvisorStatusSensor,
    _coordinator_number,
    predictive_advisor_binary_entities,
    predictive_advisor_sensor_entities,
    runtime_predictive_advisor,
)
from custom_components.idm_heatpump.sensor import async_setup_entry as async_setup_sensors

# Anchored to the real clock so the tests never decay: observation stages
# and status entities compare ``first_observed`` against ``datetime.now``,
# and a fixed past date flips those assertions one day after it is written.
T0 = datetime.now(UTC).replace(microsecond=0)


def _coordinator(
    data: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
    hass: Any = None,
) -> MagicMock:
    coordinator = MagicMock()
    coordinator.hass = hass if hass is not None else MagicMock()
    coordinator.data = data if data is not None else {}
    coordinator.config_entry = SimpleNamespace(entry_id="entry1", options=options or {})
    coordinator.web_variant = None
    coordinator.get_register = MagicMock(return_value=None)
    coordinator.last_update_success = True
    return coordinator


def _recommendation(**overrides: Any) -> Recommendation:
    values: dict[str, Any] = {
        "id": "heating_curve_a_20261007",
        "category": RecommendationCategory.HEATING_CURVE,
        "severity": RecommendationSeverity.INFO,
        "title": "Reduce heating curve HC A",
        "current_value": 0.35,
        "recommended_value": 0.32,
        "confidence": 0.91,
        "reasons": ("room_temperature_above_target", "flow_temperature_above_estimated_requirement"),
        "created_at": T0,
    }
    values.update(overrides)
    return Recommendation(**values)


# ----------------------------------------------------------------------
# Confidence and observation stage
# ----------------------------------------------------------------------


def test_clamp_confidence_bounds() -> None:
    assert clamp_confidence(-1.5) == 0.0
    assert clamp_confidence(0.914) == 0.91
    assert clamp_confidence(2.0) == 1.0
    assert clamp_confidence(float("nan")) == 0.0


def test_confidence_level_thresholds() -> None:
    assert confidence_level(0.0) is ConfidenceLevel.LOW
    assert confidence_level(0.49) is ConfidenceLevel.LOW
    assert confidence_level(0.5) is ConfidenceLevel.MEDIUM
    assert confidence_level(0.74) is ConfidenceLevel.MEDIUM
    assert confidence_level(0.75) is ConfidenceLevel.HIGH
    assert confidence_level(0.89) is ConfidenceLevel.HIGH
    assert confidence_level(0.9) is ConfidenceLevel.VERY_HIGH
    assert confidence_level(1.0) is ConfidenceLevel.VERY_HIGH


def test_evaluate_confidence_combines_coverage_and_quality() -> None:
    # Full coverage and full quality reach 1.0.
    assert evaluate_confidence(days_observed=14.0, usable_fraction=1.0) == 1.0
    # No observation at all leaves only the quality share.
    assert evaluate_confidence(days_observed=0.0, usable_fraction=1.0) == 0.4
    # No samples yet counts as zero quality.
    assert evaluate_confidence(days_observed=14.0, usable_fraction=None) == 0.6
    # Inputs are clamped: a negative past date contributes zero coverage, an
    # oversized quality share is capped at its full weight.
    assert evaluate_confidence(days_observed=-3.0, usable_fraction=5.0) == 0.4
    assert evaluate_confidence(days_observed=30.0, usable_fraction=5.0) == 1.0


def test_observation_stage_progression() -> None:
    assert observation_stage(None, T0) == "collecting"
    assert observation_stage(T0, T0 + timedelta(hours=12)) == "collecting"
    assert observation_stage(T0, T0 + timedelta(days=2)) == "early_hints"
    assert observation_stage(T0, T0 + timedelta(days=10)) == "recommending"
    assert observation_stage(T0, T0 + timedelta(days=31)) == "established"


# ----------------------------------------------------------------------
# Recommendation model
# ----------------------------------------------------------------------


def test_recommendation_round_trip() -> None:
    rec = _recommendation()
    parsed = recommendation_from_dict(rec.to_dict())
    assert parsed == rec


def test_recommendation_from_dict_rejects_malformed_entries() -> None:
    assert recommendation_from_dict(None) is None
    assert recommendation_from_dict("nope") is None
    assert recommendation_from_dict({"id": ""}) is None
    assert recommendation_from_dict({"id": "x", "category": "unknown", "severity": "info"}) is None
    # A bad status falls back to new instead of discarding the entry.
    salvaged = recommendation_from_dict(
        {"id": "x", "category": "dhw", "severity": "info", "status": "bogus", "confidence": True}
    )
    assert salvaged is not None
    assert salvaged.status is RecommendationStatus.NEW
    assert salvaged.confidence == 0.0


def test_recommendation_summary_is_machine_readable() -> None:
    summary = _recommendation().summary()
    assert summary["category"] == "heating_curve"
    assert summary["confidence_level"] == "very_high"
    assert summary["reasons"] == list(_recommendation().reasons)


# ----------------------------------------------------------------------
# Sample classification and capabilities
# ----------------------------------------------------------------------


def _classify(
    value: Any,
    *,
    previous: float | None = None,
    elapsed: timedelta = timedelta(0),
    sensitive: bool = True,
) -> SampleQuality:
    return classify_sample(
        value,
        low=-50.0,
        high=60.0,
        previous_value=previous,
        previous_changed=T0 - elapsed if previous is not None else None,
        now=T0,
        frozen_sensitive=sensitive,
    )


def test_classify_sample_categories() -> None:
    assert _classify(None) is SampleQuality.UNAVAILABLE
    assert _classify("21") is SampleQuality.IMPLAUSIBLE
    assert _classify(True) is SampleQuality.IMPLAUSIBLE
    assert _classify(999.0) is SampleQuality.IMPLAUSIBLE
    assert _classify(float("nan")) is SampleQuality.IMPLAUSIBLE
    assert _classify(21.4) is SampleQuality.USABLE


def test_classify_sample_frozen_requires_time_and_nonzero() -> None:
    # Same nonzero value after the threshold on a sensitive key is frozen.
    assert _classify(2.4, previous=2.4, elapsed=timedelta(hours=4)) is SampleQuality.FROZEN
    # Idle zeros are legitimate constants and never frozen.
    assert _classify(0.0, previous=0.0, elapsed=timedelta(hours=8)) is SampleQuality.USABLE
    # Below the threshold the same value stays usable.
    assert _classify(2.4, previous=2.4, elapsed=timedelta(hours=1)) is SampleQuality.USABLE
    # Non-sensitive keys never count as frozen.
    assert _classify(2.4, previous=2.4, elapsed=timedelta(days=2), sensitive=False) is SampleQuality.USABLE


def test_detect_capabilities_from_snapshot_and_options() -> None:
    data = {
        "outdoor_temp": 5.0,
        "power_consumption_hp": 1.2,
        "thermal_power_flow_sensor": 4.8,
        "heat_sink_flow_rate": 1.1,
        "compressor_status_1": True,
        "pv_surplus": 0.4,
        "storage_temp": 40.0,
        "hc_a_room_temp": 21.0,
    }
    capabilities = detect_capabilities(
        data,
        register_getter=lambda name: object() if name == "power_limit_hp" else None,
        web_variant="nav10",
        price_source="sensor.price",
        pv_source="sensor.pv",
    )
    assert capabilities == AdvisorCapabilities(
        has_power_meter=True,
        has_heat_meter=True,
        has_room_temperature=True,
        has_flow_sensor=True,
        has_compressor=True,
        has_pv_signal=True,
        has_power_limit=True,
        has_buffer=True,
        has_demand_reason=True,
        has_dynamic_price_source=True,
        has_pv_source=True,
    )
    empty = detect_capabilities(
        {},
        register_getter=lambda _name: None,
        web_variant=None,
        price_source=None,
        pv_source=None,
    )
    assert not any(empty.as_dict().values())


# ----------------------------------------------------------------------
# Advisor manager
# ----------------------------------------------------------------------


def test_advisor_tracks_quality_and_observation(mock_hass: Any) -> None:
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    assert advisor.first_observed is None
    assert advisor.observation_days is None
    assert advisor.stage == "collecting"
    assert advisor.usable_fraction is None

    coordinator = _coordinator(
        data={"outdoor_temp": 5.0, "hc_a_room_temp": 21.0, "power_consumption_hp": 2.4},
        hass=mock_hass,
    )
    advisor = PredictiveAdvisor(coordinator)
    advisor.observe(now=T0)
    assert advisor.first_observed == T0
    assert advisor.stage == "collecting"

    # Four hours later the stuck nonzero power reading counts as frozen.
    advisor.observe(now=T0 + timedelta(hours=4))
    summary = advisor.quality_summary()
    assert summary["power_consumption_hp"]["frozen"] == 1
    assert summary["outdoor_temp"]["unavailable"] == 0
    # The configured circuit's room temperature is watched, hc_b is not.
    assert "hc_a_room_temp" in summary
    assert "hc_b_room_temp" not in summary
    assert 0.0 <= advisor.usable_fraction <= 1.0
    assert advisor.confidence > 0.0


def test_advisor_ignores_empty_snapshots(mock_hass: Any) -> None:
    coordinator = _coordinator(data={}, hass=mock_hass)
    advisor = PredictiveAdvisor(coordinator)
    advisor.observe(now=T0)
    assert advisor.first_observed is None
    assert advisor.usable_fraction is None


def test_submit_fires_event_and_deduplicates(mock_hass: Any) -> None:
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    rec = _recommendation()

    assert advisor.submit(rec) is True
    assert advisor.recommendation_count == 1
    assert advisor.optimization_available is True

    event = mock_hass.bus.async_fire.call_args
    assert event.args[0] == EVENT_IDM_ADVISOR_RECOMMENDATION
    payload = event.args[1]
    assert payload["action"] == "new"
    assert payload["id"] == rec.id
    assert payload["category"] == "heating_curve"
    assert payload["confidence_level"] == "very_high"
    assert payload["reasons"] == list(rec.reasons)

    # Unchanged resubmission neither fires nor duplicates.
    assert advisor.submit(_recommendation()) is False
    assert mock_hass.bus.async_fire.call_count == 1

    # A changed recommendation updates in place and archives the old one.
    assert advisor.submit(_recommendation(recommended_value=0.33, confidence=0.8)) is True
    updated_event = mock_hass.bus.async_fire.call_args
    assert updated_event.args[1]["action"] == "updated"
    assert advisor.recommendation_count == 1
    assert advisor.active_recommendations[0].recommended_value == 0.33
    assert advisor.history[0].status is RecommendationStatus.OBSOLETE


def test_submit_inherits_status_of_replaced_recommendation(mock_hass: Any) -> None:
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    advisor.submit(_recommendation())
    advisor.mark(_recommendation().id, RecommendationStatus.VIEWED)
    advisor.submit(_recommendation(recommended_value=0.31))
    assert advisor.active_recommendations[0].status is RecommendationStatus.VIEWED
    assert advisor.active_recommendations[0].created_at == T0


def test_submit_supersedes_day_stamped_topic_predecessor(mock_hass: Any) -> None:
    """Daily re-issues under a new day-stamped id supersede their topic.

    Field feedback from the reference plant: four daily heating-curve
    re-issues accumulated as eight parallel "new" recommendations because
    the id changes every day. One topic must stay one active entry.
    """
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    advisor.submit(_recommendation(id="heating_curve_a_20261014"))
    advisor.submit(_recommendation(id="heating_curve_a_20261015", confidence=0.8))

    assert advisor.recommendation_count == 1
    active = advisor.active_recommendations[0]
    assert active.id == "heating_curve_a_20261015"
    assert active.confidence == 0.8
    assert active.created_at == T0
    assert advisor.history[-1].id == "heating_curve_a_20261014"
    assert advisor.history[-1].status is RecommendationStatus.OBSOLETE

    # A different topic is untouched.
    advisor.submit(_recommendation(id="heating_curve_d_20261015", title="HC D"))
    assert advisor.recommendation_count == 2


def test_submit_topic_supersede_inherits_user_status(mock_hass: Any) -> None:
    """A viewed topic keeps its user status across the daily re-issue.

    Dismissed recommendations leave the active set entirely (``mark``
    archives them), so only viewed/accepted statuses can carry over —
    the same semantics the same-id replacement path has.
    """
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    advisor.submit(_recommendation(id="heating_curve_a_20261014"))
    advisor.mark("heating_curve_a_20261014", RecommendationStatus.VIEWED)
    advisor.submit(_recommendation(id="heating_curve_a_20261015", confidence=0.7))

    active = advisor.active_recommendations[0]
    assert active.status is RecommendationStatus.VIEWED
    assert active.created_at == T0


def test_submit_clamps_confidence(mock_hass: Any) -> None:
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    advisor.submit(_recommendation(confidence=7.0))
    assert advisor.active_recommendations[0].confidence == 1.0


def test_mark_lifecycle_never_writes(mock_hass: Any) -> None:
    coordinator = _coordinator(hass=mock_hass)
    advisor = PredictiveAdvisor(coordinator)
    advisor.submit(_recommendation())

    assert advisor.mark("missing", RecommendationStatus.VIEWED) is False
    assert advisor.mark(_recommendation().id, RecommendationStatus.NEW) is False

    assert advisor.mark(_recommendation().id, RecommendationStatus.VIEWED) is True
    assert advisor.active_recommendations[0].status is RecommendationStatus.VIEWED
    assert advisor.optimization_available is True

    # Accepted is an acknowledgment only: nothing is ever written.
    assert advisor.mark(_recommendation().id, RecommendationStatus.ACCEPTED) is True
    assert advisor.active_recommendations[0].status is RecommendationStatus.ACCEPTED
    assert advisor.optimization_available is False
    coordinator.async_write_register.assert_not_called()

    assert advisor.mark(_recommendation().id, RecommendationStatus.DISMISSED) is True
    assert advisor.recommendation_count == 0
    assert advisor.history[-1].status is RecommendationStatus.DISMISSED
    assert mock_hass.bus.async_fire.call_args.args[1]["action"] == "status"


def test_retract_withdraws_resolved_recommendation(mock_hass: Any) -> None:
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    advisor.submit(_recommendation())
    assert advisor.retract("missing") is False
    assert advisor.retract(_recommendation().id) is True
    assert advisor.recommendation_count == 0
    assert advisor.history[-1].status is RecommendationStatus.OBSOLETE
    assert mock_hass.bus.async_fire.call_args.args[1]["action"] == "status"
    # Retracting twice is a no-op.
    assert advisor.retract(_recommendation().id) is False


def test_recommendations_expire_after_ttl(mock_hass: Any) -> None:
    coordinator = _coordinator(data={"outdoor_temp": 5.0}, hass=mock_hass)
    advisor = PredictiveAdvisor(coordinator)
    advisor.submit(_recommendation())
    # A snapshot eight days later retires the week-old recommendation.
    advisor.observe(now=T0 + timedelta(days=8))
    assert advisor.recommendation_count == 0
    assert advisor.history[-1].status is RecommendationStatus.EXPIRED
    # Expiry fires the same status event as mark/retract: automations
    # listening on the recommendation event hear that it ended.
    expiry_event = mock_hass.bus.async_fire.call_args
    assert expiry_event.args[0] == EVENT_IDM_ADVISOR_RECOMMENDATION
    assert expiry_event.args[1]["action"] == "status"
    assert expiry_event.args[1]["status"] == "expired"


def test_daily_re_issue_refreshes_the_ttl_anchor(monkeypatch: pytest.MonkeyPatch, mock_hass: Any) -> None:
    """A daily re-issued topic outlives its first-ever issue date.

    The TTL ran against the inherited ``created_at`` before: a topic
    re-issued daily expired seven days after its first issue and came back
    as a fresh "new" entry with a reset user status once per week.
    """
    coordinator = _coordinator(data={"outdoor_temp": 5.0}, hass=mock_hass)
    advisor = PredictiveAdvisor(coordinator)
    advisor.submit(_recommendation(id="heating_curve_a_20261012", created_at=T0))
    for day in range(1, 10):
        at = T0 + timedelta(days=day)
        monkeypatch.setattr(predictive_advisor_module, "_utcnow", lambda at=at: at)
        advisor.submit(_recommendation(id=f"heating_curve_a_{at.strftime('%Y%m%d')}"))
        monkeypatch.undo()
        advisor.observe(now=at)

    # Ten days after the first issue the topic is still one active entry
    # with no weekly expire/re-issue churn in the history.
    assert advisor.recommendation_count == 1
    assert not [rec for rec in advisor.history if rec.status is RecommendationStatus.EXPIRED]
    active = advisor.active_recommendations[0]
    assert active.created_at == T0
    assert active.effective_refreshed_at == T0 + timedelta(days=9)


def test_topic_supersede_archives_every_duplicate(mock_hass: Any) -> None:
    """Pre-dedup stores can hold several active entries of one topic."""
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    advisor._active = {
        "heating_curve_a_20261014": _recommendation(id="heating_curve_a_20261014"),
        "heating_curve_a_20261015": _recommendation(id="heating_curve_a_20261015"),
        "heating_curve_a_20261016": _recommendation(id="heating_curve_a_20261016"),
    }
    advisor.submit(_recommendation(id="heating_curve_a_20261017"))

    assert advisor.recommendation_count == 1
    assert advisor.active_recommendations[0].id == "heating_curve_a_20261017"
    # Identical content: the predecessor rolls over into the successor; the
    # two extra duplicates leave as obsolete audit-trail entries.
    archived = [rec for rec in advisor.history if rec.status is RecommendationStatus.OBSOLETE]
    assert sorted(rec.id for rec in archived) == ["heating_curve_a_20261014", "heating_curve_a_20261015"]


def test_observe_saves_counters_throttled_not_per_snapshot(mock_hass: Any) -> None:
    coordinator = _coordinator(data={"outdoor_temp": 5.0}, hass=mock_hass)
    advisor = PredictiveAdvisor(coordinator)
    advisor._store.async_delay_save = MagicMock()
    advisor.observe(now=T0)
    assert advisor._store.async_delay_save.call_count == 1

    # Snapshots inside the throttle window change only quality counters;
    # they must not schedule another store write each scan interval.
    for minutes in (1, 2, 5, 9):
        advisor.observe(now=T0 + timedelta(minutes=minutes))
    assert advisor._store.async_delay_save.call_count == 1

    # Past the window the counters are persisted again.
    advisor.observe(now=T0 + timedelta(minutes=11))
    assert advisor._store.async_delay_save.call_count == 2


async def test_persistence_round_trip(mock_hass: Any) -> None:
    coordinator = _coordinator(data={"outdoor_temp": 5.0, "hc_a_room_temp": 21.0}, hass=mock_hass)
    first = PredictiveAdvisor(coordinator)
    await first.async_load()
    first.observe(now=T0)
    first.submit(_recommendation())

    # Simulate a restart: a fresh advisor loads the stored document.
    second = PredictiveAdvisor(coordinator)
    second._store.data = first._serialize()
    await second.async_load()
    assert second.first_observed == T0
    assert second.recommendation_count == 1
    assert second.active_recommendations[0] == _recommendation()
    assert second.quality_summary()["outdoor_temp"]["samples"] == 1


async def test_async_load_survives_malformed_data(mock_hass: Any) -> None:
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    advisor._store.data = {"active": "nope", "history": [5, None], "quality": 3, "first_observed": 42}
    await advisor.async_load()
    assert advisor.recommendation_count == 0
    assert advisor.first_observed is None


async def test_async_load_survives_store_error(mock_hass: Any) -> None:
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    advisor._store.async_load = MagicMock(side_effect=OSError("disk"))
    await advisor.async_load()
    assert advisor.recommendation_count == 0


def test_required_registers_cover_watch_list() -> None:
    advisor = PredictiveAdvisor(_coordinator(options={"heating_circuits": ["a", "d"]}))
    required = advisor.required_registers
    assert "outdoor_temp" in required
    assert "hc_a_room_temp" in required
    assert "hc_d_room_temp" in required
    assert "hc_b_room_temp" not in required


def test_capabilities_read_coordinator_state() -> None:
    coordinator = _coordinator(
        data={"power_consumption_hp": 1.0, "smart_grid_status": 4},
        options={"dynamic_price_entity": "sensor.price"},
    )
    coordinator.web_variant = "nav10"
    capabilities = PredictiveAdvisor(coordinator).capabilities
    assert capabilities.has_power_meter is True
    assert capabilities.has_pv_signal is True
    assert capabilities.has_demand_reason is True
    assert capabilities.has_dynamic_price_source is True
    assert capabilities.has_heat_meter is False

    coordinator.data = {
        "power_consumption_hp": 0.62,
        "thermal_power_flow_sensor": 0.0,
        "current_power": 3.46,
    }
    advisor = PredictiveAdvisor(coordinator)
    assert advisor.capabilities.has_heat_meter is True
    assert "current_power" in advisor.required_registers
    advisor.observe(now=T0)
    assert advisor.quality_summary()["thermal_power_flow_sensor"]["usable"] == 1
    assert advisor._quality["thermal_power_flow_sensor"].last_value == pytest.approx(3.46)


# ----------------------------------------------------------------------
# Entities and platform wiring
# ----------------------------------------------------------------------


def test_runtime_guard_rejects_mocks() -> None:
    assert runtime_predictive_advisor(SimpleNamespace(predictive_advisor=None)) is None
    assert runtime_predictive_advisor(MagicMock()) is None
    advisor = PredictiveAdvisor(_coordinator())
    assert runtime_predictive_advisor(SimpleNamespace(predictive_advisor=advisor)) is advisor


def test_entity_factories_gate_on_advisor() -> None:
    coordinator = _coordinator()
    assert predictive_advisor_sensor_entities(coordinator, None) == []
    assert predictive_advisor_binary_entities(coordinator, None) == []

    advisor = PredictiveAdvisor(coordinator)
    sensors = predictive_advisor_sensor_entities(coordinator, advisor)
    binaries = predictive_advisor_binary_entities(coordinator, advisor)
    assert [type(entity) for entity in sensors] == [IdmAdvisorStatusSensor, IdmAdvisorRecommendationSensor]
    assert [type(entity) for entity in binaries] == [IdmAdvisorOptimizationBinarySensor]


def test_entity_values_before_and_after_observation() -> None:
    coordinator = _coordinator(data={"outdoor_temp": 5.0})
    advisor = PredictiveAdvisor(coordinator)
    status_sensor = IdmAdvisorStatusSensor(coordinator, advisor)
    recommendation_sensor = IdmAdvisorRecommendationSensor(coordinator, advisor)
    binary = IdmAdvisorOptimizationBinarySensor(coordinator, advisor)

    # Before the first snapshot the entities stay unavailable.
    assert status_sensor.native_value is None
    assert status_sensor.available is False
    assert recommendation_sensor.available is False
    assert binary.available is False

    advisor.observe(now=T0)
    assert status_sensor.native_value == "collecting"
    assert status_sensor.available is True
    assert status_sensor._attr_options == ["collecting", "early_hints", "recommending", "established"]
    attributes = status_sensor.extra_state_attributes
    assert attributes["write_actions"] is False
    assert attributes["capabilities"]["power_meter"] is False
    # The first observation happened at T0; depending on the wall clock at
    # test runtime that is a fraction of a day ago, never more than one day.
    assert attributes["observation_days"] == pytest.approx(0.0, abs=1.0)

    advisor.submit(_recommendation())
    assert recommendation_sensor.native_value == 1
    assert recommendation_sensor.extra_state_attributes["recommendations"][0]["id"] == _recommendation().id
    assert binary.is_on is True
    advisor.mark(_recommendation().id, RecommendationStatus.DISMISSED)
    assert binary.is_on is False
    assert binary.extra_state_attributes["write_actions"] is False


def test_entity_unique_ids_and_translation_keys() -> None:
    coordinator = _coordinator()
    advisor = PredictiveAdvisor(coordinator)
    status_sensor = IdmAdvisorStatusSensor(coordinator, advisor)
    assert status_sensor._attr_unique_id == "entry1_advisor_status"
    assert status_sensor.entity_description.translation_key == "advisor_status"
    assert IdmAdvisorRecommendationSensor(coordinator, advisor)._attr_unique_id == "entry1_advisor_recommendations"
    assert (
        IdmAdvisorOptimizationBinarySensor(coordinator, advisor)._attr_unique_id
        == "entry1_advisor_optimization_available"
    )


async def test_platforms_create_advisor_entities() -> None:
    coordinator = _coordinator(data={"outdoor_temp": 5.0})
    coordinator.sensor_descriptions = []
    advisor = PredictiveAdvisor(coordinator)
    entry = MagicMock()
    entry.options = {"feature_profile": "smart"}
    entry.runtime_data = SimpleNamespace(
        coordinator=coordinator,
        operation_analysis=None,
        predictive_advisor=advisor,
    )

    added_sensors: list[Any] = []
    await async_setup_sensors(MagicMock(), entry, MagicMock(side_effect=added_sensors.extend))
    keys = {entity.entity_description.key for entity in added_sensors}
    assert "advisor_status" in keys
    assert "advisor_recommendations" in keys

    added_binaries: list[Any] = []
    await async_setup_binary_sensors(MagicMock(), entry, MagicMock(side_effect=added_binaries.extend))
    assert any(entity.entity_description.key == "advisor_optimization_available" for entity in added_binaries)


# ----------------------------------------------------------------------
# Persistence, defensive parsing and event-bus tolerance
# ----------------------------------------------------------------------


async def test_async_load_parses_timestamps_defensively(mock_hass: Any) -> None:
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    advisor._store.data = {"first_observed": "not-a-timestamp"}
    await advisor.async_load()
    assert advisor.first_observed is None

    # A naive timestamp is interpreted as UTC instead of being discarded.
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    advisor._store.data = {"first_observed": T0.replace(tzinfo=None).isoformat()}
    await advisor.async_load()
    assert advisor.first_observed == T0


def test_observe_counts_implausible_samples(mock_hass: Any) -> None:
    coordinator = _coordinator(
        data={"outdoor_temp": 999.0, "power_consumption_hp": "many"},
        hass=mock_hass,
    )
    advisor = PredictiveAdvisor(coordinator)
    advisor.observe(now=T0)
    summary = advisor.quality_summary()
    # Out-of-range and non-numeric readings are implausible, not unavailable.
    assert summary["outdoor_temp"]["implausible"] == 1
    assert summary["power_consumption_hp"]["implausible"] == 1
    assert summary["outdoor_temp"]["samples"] == 1


async def test_async_load_restores_quality_defensively(mock_hass: Any) -> None:
    advisor = PredictiveAdvisor(_coordinator(hass=mock_hass))
    advisor._store.data = {
        "quality": {
            "outdoor_temp": "nope",
            "power_consumption_hp": {"samples": True, "usable": -1, "frozen": 2},
        }
    }
    await advisor.async_load()
    summary = advisor.quality_summary()
    # A non-mapping row restores empty statistics: no samples, no fraction.
    assert summary["outdoor_temp"]["samples"] == 0
    assert summary["outdoor_temp"]["usable_fraction"] is None
    # Bool and negative counters are discarded; the valid one survives.
    assert summary["power_consumption_hp"]["samples"] == 0
    assert summary["power_consumption_hp"]["usable_fraction"] is None
    assert summary["power_consumption_hp"]["frozen"] == 2


def test_configured_circuits_falls_back_for_malformed_option() -> None:
    # A single string instead of a list must not break circuit resolution.
    advisor = PredictiveAdvisor(_coordinator(options={"heating_circuits": "a"}))
    assert "hc_a_room_temp" in advisor.required_registers
    assert "hc_b_room_temp" not in advisor.required_registers


def test_fire_tolerates_event_bus_without_async_fire() -> None:
    coordinator = _coordinator(hass=SimpleNamespace(bus=SimpleNamespace()))
    advisor = PredictiveAdvisor(coordinator)
    assert advisor.submit(_recommendation()) is True
    assert advisor.recommendation_count == 1


async def test_async_save_persists_state_immediately(mock_hass: Any) -> None:
    coordinator = _coordinator(data={"outdoor_temp": 5.0}, hass=mock_hass)
    advisor = PredictiveAdvisor(coordinator)
    advisor.observe(now=T0)
    advisor.submit(_recommendation())
    await advisor.async_save()
    stored = advisor._store.data
    assert stored is not None
    assert stored["version"] == 1
    assert stored["first_observed"] == T0.isoformat()
    assert stored["active"][0]["id"] == _recommendation().id
    assert stored["quality"]["outdoor_temp"]["samples"] == 1


# ----------------------------------------------------------------------
# Producer entities (roadmap phases 2-9)
# ----------------------------------------------------------------------


def _producer_setup(
    data: dict[str, Any] | None = None,
) -> tuple[AdvisorEngine, PredictiveAdvisor, AdvisorAnalytics, MagicMock]:
    """Build the engine triple the producer entities read from."""
    coordinator = _coordinator(data=data)
    coordinator.web_supplement = None
    coordinator.operation_analysis = None
    hass = MagicMock()
    advisor = PredictiveAdvisor(coordinator)
    analytics = AdvisorAnalytics(hass, "entry1")
    engine = AdvisorEngine(hass, coordinator, advisor, analytics)
    return engine, advisor, analytics, coordinator


def _learn_cop_map(analytics: AdvisorAnalytics) -> None:
    """Learn one COP bin of 4.8 kW thermal / 1.2 kW electric over one hour."""
    for _ in range(2):
        analytics.observe_cop_sample(5.0, 30.0, thermal_kw=4.8, electric_kw=1.2, hours=0.5)


def test_coordinator_number_filters_unusable_values() -> None:
    assert _coordinator_number(_coordinator(data={"outdoor_temp": 3}), "outdoor_temp") == 3.0
    assert _coordinator_number(_coordinator(data={}), "outdoor_temp") is None
    assert _coordinator_number(_coordinator(data={"outdoor_temp": True}), "outdoor_temp") is None
    assert _coordinator_number(_coordinator(data={"outdoor_temp": "5.0"}), "outdoor_temp") is None
    assert _coordinator_number(_coordinator(data={"outdoor_temp": float("nan")}), "outdoor_temp") is None
    assert _coordinator_number(_coordinator(data={"outdoor_temp": float("inf")}), "outdoor_temp") is None
    coordinator = _coordinator(data={})
    coordinator.data = None
    assert _coordinator_number(coordinator, "outdoor_temp") is None


def test_confidence_sensor_before_and_after_observation() -> None:
    coordinator = _coordinator(data={"outdoor_temp": 5.0})
    advisor = PredictiveAdvisor(coordinator)
    sensor = IdmAdvisorConfidenceSensor(coordinator, advisor)

    # Before the first snapshot there is no confidence to publish.
    assert sensor.native_value is None
    attributes = sensor.extra_state_attributes
    assert attributes["level"] == "low"
    assert attributes["write_actions"] is False
    assert "formula" in attributes

    advisor.observe(now=T0)
    assert sensor.native_value == round(advisor.confidence * 100)
    assert sensor.extra_state_attributes["level"] == str(confidence_level(advisor.confidence))


def test_operation_reason_sensor_requires_mapping_snapshot() -> None:
    engine, _advisor, _analytics, coordinator = _producer_setup()
    sensor = IdmAdvisorOperationReasonSensor(coordinator, engine)

    # A non-mapping snapshot yields no reason at all.
    coordinator.data = None
    assert sensor.native_value is None
    assert sensor.available is False
    assert sensor.extra_state_attributes == {"write_actions": False}

    coordinator.data = {"hp_operating_mode": 1, "power_consumption_hp": 2.0}
    assert sensor.native_value == "Heating"
    assert sensor.available is True
    attributes = sensor.extra_state_attributes
    assert attributes["mode"] == "Heating"
    assert attributes["operating_mode"] == 1
    assert attributes["write_actions"] is False

    # The coordinator availability still gates the sensor.
    coordinator.last_update_success = False
    assert sensor.available is False


def test_anomaly_binary_sensor_tracks_anomaly_findings() -> None:
    engine, advisor, _analytics, coordinator = _producer_setup(data={"outdoor_temp": 5.0})
    sensor = IdmAdvisorAnomalyBinarySensor(coordinator, engine)
    assert sensor.is_on is False
    assert sensor.extra_state_attributes == {"findings": [], "write_actions": False}

    advisor.submit(
        _recommendation(
            id="anomaly_flow_rate_low_20261012",
            category=RecommendationCategory.ANOMALY,
            severity=RecommendationSeverity.HINT,
            title="Heat-circle flow is 20% below its 5-day baseline",
        )
    )
    assert sensor.is_on is True
    findings = sensor.extra_state_attributes["findings"]
    assert [finding["id"] for finding in findings] == ["anomaly_flow_rate_low_20261012"]
    assert findings[0]["severity"] == "hint"


def test_health_score_sensor_needs_two_domains() -> None:
    engine, _advisor, analytics, coordinator = _producer_setup(data={"outdoor_temp": 5.0})
    sensor = IdmAdvisorHealthScoreSensor(coordinator, engine)

    # With no baselined domain the score stays unpublished.
    assert sensor.native_value is None
    assert sensor.available is False
    assert sensor.extra_state_attributes["write_actions"] is False

    for days_ago in range(1, 4):
        at = T0 - timedelta(days=days_ago)
        analytics.observe_metric("heat_sink_flow_rate", 1.2, at)
        analytics.observe_metric("compressor_starts", 10.0, at, mode="max")
    assert sensor.native_value == 100
    assert sensor.available is True
    assert sensor.extra_state_attributes["components"] == {"hydraulics": 100.0, "compressor": 100.0}


def test_efficiency_sensor_exposes_learned_cop_map() -> None:
    engine, _advisor, analytics, coordinator = _producer_setup(
        data={"outdoor_temp": 5.0, "hp_flow_temp": 30.0, "power_consumption_hp": 1.2}
    )
    sensor = IdmAdvisorEfficiencySensor(coordinator, engine)
    assert sensor.native_value is None
    assert sensor.available is False
    assert sensor.extra_state_attributes == {
        "expected_cop": None,
        "observed_cop_7d": None,
        "observed_cop_heating_7d": None,
        "observed_cop_dhw_7d": None,
        "deviation_percent": None,
        "write_actions": False,
    }

    _learn_cop_map(analytics)
    # The engine publishes the score as a rounded float, so the int-typed
    # native value stays unpublished; the numbers arrive as attributes.
    assert sensor.native_value is None
    assert sensor.available is False
    attributes = sensor.extra_state_attributes
    assert attributes["expected_cop"] == 4.0
    assert attributes["observed_cop_7d"] == 4.0
    assert attributes["deviation_percent"] == 0.0


def test_expected_cop_sensor_uses_learned_map() -> None:
    engine, _advisor, analytics, coordinator = _producer_setup(data={"outdoor_temp": 5.0, "hp_flow_temp": 30.0})
    sensor = IdmAdvisorExpectedCopSensor(coordinator, engine)

    # Without learned bins there is no expected COP and no availability.
    assert sensor.native_value is None
    assert sensor.available is False
    assert sensor.extra_state_attributes == {"learned_hours": None, "deviation_percent": None, "write_actions": False}

    _learn_cop_map(analytics)
    assert sensor.native_value == 4.0
    assert sensor.available is True
    attributes = sensor.extra_state_attributes
    assert attributes["learned_hours"] == 1.0
    assert attributes["deviation_percent"] == 0.0


def test_building_model_sensors_publish_learned_model() -> None:
    engine, _advisor, analytics, coordinator = _producer_setup(data={"outdoor_temp": 5.0})
    heat_loss = IdmAdvisorBuildingHeatLossSensor(coordinator, engine)
    inertia = IdmAdvisorBuildingInertiaSensor(coordinator, engine)

    assert heat_loss.native_value is None
    assert heat_loss.available is False
    assert heat_loss.extra_state_attributes["heat_loss_w_per_k"] is None
    assert heat_loss.extra_state_attributes["write_actions"] is False
    assert inertia.native_value is None
    assert inertia.available is False
    assert inertia.extra_state_attributes["cooldown_episodes"] == 0

    # 60 regression samples with slope 0.2 kW/K learn a 200 W/K heat loss.
    # Advancing timestamps: the weighted fit needs effective observed hours.
    for index in range(60):
        delta = 15.0 + (index % 7)
        analytics.observe_heating(delta, 0.2 * delta, T0 + timedelta(minutes=12 * index))
    # Three cooldown episodes establish the inertia estimate.
    for _ in range(3):
        analytics.observe_cooldown_episode(0.1, 12.5)

    assert heat_loss.native_value == 200.0
    assert heat_loss.available is True
    assert inertia.native_value == 12.5
    assert inertia.available is True
    assert heat_loss.extra_state_attributes["heat_fit_samples"] == 60
    assert inertia.extra_state_attributes["cooldown_episodes"] == 3


def test_optimal_flow_sensor_requires_outdoor_and_learned_curve() -> None:
    engine, _advisor, analytics, coordinator = _producer_setup(data={"outdoor_temp": 5.0})
    sensor = IdmAdvisorOptimalFlowSensor(coordinator, engine)

    # Without a learned flow curve the optimal flow temperature is None.
    assert sensor.native_value is None
    assert sensor.available is False

    # 60 samples along flow = 35 - 0.5 * outdoor learn a falling curve.
    for index, outdoor in enumerate(range(-30, 30)):
        analytics.observe_flow_pair(float(outdoor), 35.0 - 0.5 * outdoor, T0 + timedelta(minutes=12 * index))
    assert sensor.native_value == 32.5
    assert sensor.available is True

    # A non-numeric outdoor temperature disables the sensor again.
    coordinator.data = {"outdoor_temp": "frozen"}
    assert sensor.native_value is None
    assert sensor.available is False


def test_curve_sensor_publishes_recommendation_details() -> None:
    engine, _advisor, _analytics, coordinator = _producer_setup(data={"outdoor_temp": 5.0})
    sensor = IdmAdvisorCurveSensor(coordinator, engine, "a")
    assert sensor.native_value is None
    assert sensor.available is False
    assert sensor.extra_state_attributes == {"write_actions": False}

    engine._curve_recommendations = {"a": {"recommended": 0.32, "current": 0.35, "baseline_days": 9}}
    assert sensor.native_value == 0.32
    assert sensor.available is True
    attributes = sensor.extra_state_attributes
    assert attributes["recommended"] == 0.32
    assert attributes["current"] == 0.35
    assert attributes["write_actions"] is False


def test_dhw_window_sensor_formats_window_and_attributes(monkeypatch: pytest.MonkeyPatch) -> None:
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("Europe/Berlin")
    monkeypatch.setattr(predictive_advisor_entities_module.dt_util, "as_local", lambda value: value.astimezone(zone))
    engine, _advisor, _analytics, coordinator = _producer_setup(data={"outdoor_temp": 5.0})
    sensor = IdmAdvisorDhwWindowSensor(coordinator, engine)
    assert sensor.native_value is None
    assert sensor.available is False
    assert sensor.extra_state_attributes == {"write_actions": False}

    start = T0 + timedelta(hours=4)
    engine._dhw_window = {
        "start": start.isoformat(),
        "hours": 3,
        "source": "pv_surplus_forecast",
        "expected_pv_kwh": 4.2,
    }
    # The stored timestamps are UTC; the sensor renders the user's wall clock.
    assert (
        sensor.native_value == f"{start.astimezone(zone):%H:%M}-{(start + timedelta(hours=3)).astimezone(zone):%H:%M}"
    )
    assert sensor.available is True
    assert sensor.extra_state_attributes["expected_pv_kwh"] == 4.2


def test_heat_demand_sensor_reads_plan_values() -> None:
    engine, _advisor, _analytics, coordinator = _producer_setup(data={"outdoor_temp": 5.0})
    sensor = IdmAdvisorHeatDemandSensor(coordinator, engine)
    assert sensor.native_value is None
    assert sensor.available is False

    engine._plan = {"expected_pv_kwh": 6.4}
    assert sensor.native_value is None  # no predicted demand in the plan yet
    attributes = sensor.extra_state_attributes
    assert attributes["expected_pv_kwh"] == 6.4
    assert attributes["indoor_reference"] == "measured room temperature, 21 C fallback"

    engine._plan = {"predicted_heat_demand_kwh": 18.2, "expected_pv_kwh": 6.4}
    assert sensor.native_value == 18.2
    assert sensor.available is True


def test_plan_sensor_gates_on_plan_presence() -> None:
    engine, _advisor, _analytics, coordinator = _producer_setup(data={"outdoor_temp": 5.0})
    sensor = IdmAdvisorPlanSensor(coordinator, engine)
    assert sensor.native_value is None
    assert sensor.available is False
    assert sensor.extra_state_attributes == {"write_actions": False}

    engine._plan = {"predicted_heat_demand_kwh": 18.2}
    assert sensor.native_value == "ok"
    assert sensor.available is True
    assert sensor.extra_state_attributes["predicted_heat_demand_kwh"] == 18.2

    engine._plan = {"dhw_window_conflicts_with_expensive_hours": True}
    assert sensor.native_value == "attention"


def test_room_temperature_capability_requires_a_plausible_reading() -> None:
    """Uninitialized memory (-327.33) is not a room sensor (#504)."""
    from custom_components.idm_heatpump.predictive_advisor import detect_capabilities

    def _capabilities(data: dict[str, Any]) -> bool:
        return detect_capabilities(
            data=data, register_getter=lambda _name: None, web_variant=None, price_source=None, pv_source=None
        ).has_room_temperature

    assert _capabilities({"hc_a_room_temp": -327.33}) is False
    assert _capabilities({"hc_a_room_temp": 22.0}) is True
    assert _capabilities({"hc_b_room_temp": 22.0}) is True
    assert _capabilities({"other": 22.0}) is False


class TestAdvisorRoomTemperatureSources:
    """Mapped read-only HA sensors stand in for missing wired sensors (#504)."""

    def _advisor(self, options: dict[str, object], states: dict[str, Any]):
        coordinator = MagicMock()
        coordinator.data = {"hc_a_room_temp": -327.33}
        coordinator.get_register = lambda name: None
        coordinator.web_variant = None
        coordinator.config_entry = SimpleNamespace(entry_id="entry1", options=options)
        coordinator.hass = MagicMock()
        coordinator.hass.states.get = states.get
        advisor = PredictiveAdvisor(coordinator)
        advisor._first_observed = datetime.now(UTC) - timedelta(days=2)
        return advisor

    def test_quality_tracks_the_mapped_source_instead_of_the_register(self):
        from custom_components.idm_heatpump.const import CONF_ADVISOR_ROOM_TEMP_ENTITIES

        advisor = self._advisor(
            {CONF_ADVISOR_ROOM_TEMP_ENTITIES: {"a": "sensor.room_a"}},
            {"sensor.room_a": SimpleNamespace(state="22.1")},
        )

        advisor.observe()
        quality = advisor.quality_summary()["hc_a_room_temp"]

        assert quality["usable"] == 1
        assert quality["implausible"] == 0  # the register garbage never counted

    def test_unavailable_source_counts_as_unavailable_not_implausible(self):
        from custom_components.idm_heatpump.const import CONF_ADVISOR_ROOM_TEMP_ENTITIES

        advisor = self._advisor({CONF_ADVISOR_ROOM_TEMP_ENTITIES: {"a": "sensor.room_a"}}, {})

        advisor.observe()
        quality = advisor.quality_summary()["hc_a_room_temp"]

        assert quality["unavailable"] == 1

    def test_capabilities_report_room_temperature_with_a_mapped_source(self):
        from custom_components.idm_heatpump.const import CONF_ADVISOR_ROOM_TEMP_ENTITIES

        advisor = self._advisor(
            {CONF_ADVISOR_ROOM_TEMP_ENTITIES: {"a": "sensor.room_a"}},
            {"sensor.room_a": SimpleNamespace(state="22.1")},
        )

        assert advisor.capabilities.has_room_temperature is True


def test_no_twt_spurious_flow_zero_is_not_a_flow_sensor(mock_hass) -> None:
    """#539: a no-TWT plant's constant 0.0 L/min is not sensor data.

    Without a plate heat exchanger the heat-sink block carries the FLOAT
    -1.0 not-present pattern and the UCHAR flow rate decodes a spurious
    0.0 — the capability must stay false and the samples must classify
    as unavailable instead of 100 % usable.
    """
    coordinator = _coordinator(
        data={
            "heat_sink_flow_rate": 0.0,
            "heat_sink_flow_temp": -1.0,
            "power_consumption_hp": 2.4,
            "outdoor_temp": 7.5,
        },
        hass=mock_hass,
    )
    advisor = PredictiveAdvisor(coordinator)
    advisor.observe(now=T0)
    quality = advisor.quality_summary()["heat_sink_flow_rate"]
    assert quality["usable"] == 0
    assert quality["unavailable"] == 1

    capabilities = detect_capabilities(
        {"heat_sink_flow_rate": 0.0, "heat_sink_flow_temp": -1.0},
        web_variant="nav10",
        register_getter=lambda _n: None,
        price_source=None,
        pv_source=None,
    )
    assert capabilities.has_flow_sensor is False


def test_twt_idle_flow_zero_stays_usable(mock_hass) -> None:
    """A real sensor's legitimate idle 0 L/min keeps counting as usable (#539)."""
    coordinator = _coordinator(
        data={
            "heat_sink_flow_rate": 0.0,
            "heat_sink_flow_temp": 22.5,
            "power_consumption_hp": 0.0,
            "outdoor_temp": 7.5,
        },
        hass=mock_hass,
    )
    advisor = PredictiveAdvisor(coordinator)
    advisor.observe(now=T0)
    quality = advisor.quality_summary()["heat_sink_flow_rate"]
    assert quality["usable"] == 1
    assert quality["unavailable"] == 0

    capabilities = detect_capabilities(
        {"heat_sink_flow_rate": 0.0, "heat_sink_flow_temp": 22.5},
        web_variant="nav10",
        register_getter=lambda _n: None,
        price_source=None,
        pv_source=None,
    )
    assert capabilities.has_flow_sensor is True


def test_flow_rate_plausibility_accepts_liter_per_minute_readings(mock_hass) -> None:
    """heat_sink_flow_rate (L/min) values like 33.9 L/min must be usable, not implausible."""
    coordinator = _coordinator(
        data={
            "heat_sink_flow_rate": 33.9,
            "heat_sink_flow_temp": 28.0,
            "power_consumption_hp": 1.8,
            "outdoor_temp": 6.0,
        },
        hass=mock_hass,
    )
    advisor = PredictiveAdvisor(coordinator)
    advisor.observe(now=T0)
    quality = advisor.quality_summary()["heat_sink_flow_rate"]
    assert quality["usable"] == 1
    assert quality["implausible"] == 0


def test_no_twt_web_flowmeter_zero_stays_usable_and_detected(mock_hass) -> None:
    """When the web supplement provides flowmeter, idle 0.0 L/min on a no-TWT plant stays usable."""
    coordinator = _coordinator(
        data={
            "heat_sink_flow_rate": 0.0,
            "heat_sink_flow_temp": -1.0,
            "power_consumption_hp": 0.0,
            "outdoor_temp": 7.5,
        },
        hass=mock_hass,
    )
    coordinator.web_supplement = SimpleNamespace(sensor_values={"flowmeter": SimpleNamespace(native_value=0.0)})
    advisor = PredictiveAdvisor(coordinator)
    advisor.observe(now=T0)
    quality = advisor.quality_summary()["heat_sink_flow_rate"]
    assert quality["usable"] == 1
    assert quality["unavailable"] == 0
    assert advisor.capabilities.has_flow_sensor is True


def test_required_registers_include_engine_and_no_twt_dependencies() -> None:
    advisor = PredictiveAdvisor(_coordinator(options={"heating_circuits": ["a"]}))
    required = set(advisor.required_registers)
    assert {
        "heat_sink_flow_temp",
        "hc_a_room_temp",
        "hc_a_active_mode",
        "hc_a_heating_curve",
        "hc_a_room_setpoint_heat_normal",
        "hc_a_flow_temp",
        "hc_a_setpoint_flow_temp",
    } <= required


def test_submit_same_topic_new_date_id_identical_content_rolls_over_in_place() -> None:
    """Daily re-issue of the same recommendation with a new date ID must not churn history or events."""
    events: list[tuple[str, dict[str, Any]]] = []
    hass = SimpleNamespace(bus=SimpleNamespace(async_fire=lambda name, payload: events.append((name, payload))))
    advisor = PredictiveAdvisor(_coordinator(hass=hass))

    day1 = _recommendation(id="curve_a_lower_20261018", created_at=T0)
    assert advisor.submit(day1) is True
    assert advisor.mark("curve_a_lower_20261018", RecommendationStatus.VIEWED) is True
    events.clear()

    day2 = _recommendation(
        id="curve_a_lower_20261019",
        created_at=T0 + timedelta(days=1),
    )
    assert advisor.submit(day2) is False
    assert advisor.history == ()
    assert events == []
    active = advisor.active_recommendations
    assert len(active) == 1
    assert active[0].id == "curve_a_lower_20261019"
    assert active[0].created_at == T0
    assert active[0].status is RecommendationStatus.VIEWED


def test_mark_and_retract_match_by_topic_across_date_stamps() -> None:
    """Retracting or marking with today's date-stamped ID finds yesterday's active entry for the same topic."""
    advisor = PredictiveAdvisor(_coordinator())
    advisor.submit(_recommendation(id="anomaly_flow_rate_low_20261018", created_at=T0))
    advisor.submit(_recommendation(id="curve_a_lower_20261018", created_at=T0))

    assert advisor.mark("curve_a_lower_20261019", RecommendationStatus.VIEWED) is True
    assert advisor.retract("anomaly_flow_rate_low_20261019") is True
    assert [r.id for r in advisor.active_recommendations] == ["curve_a_lower_20261018"]
    assert advisor.active_recommendations[0].status is RecommendationStatus.VIEWED
    assert len(advisor.history) == 1
    assert advisor.history[0].id == "anomaly_flow_rate_low_20261018"
