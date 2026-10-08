"""Tests for the advisor engine: producers, forecasts, windows, plan."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.idm_heatpump.advisor_analytics import AdvisorAnalytics
from custom_components.idm_heatpump.advisor_engine import (
    AdvisorEngine,
    advisor_forecast_loop,
    best_window,
    parse_hourly_temperatures,
    parse_price_hourly,
    parse_pv_hourly_kwh,
)
from custom_components.idm_heatpump.binary_sensor import async_setup_entry as async_setup_binary_sensors
from custom_components.idm_heatpump.predictive_advisor import (
    PredictiveAdvisor,
    RecommendationCategory,
)
from custom_components.idm_heatpump.predictive_advisor_entities import (
    IdmAdvisorConfidenceSensor,
    IdmAdvisorCurveSensor,
    IdmAdvisorDhwWindowSensor,
    IdmAdvisorHeatDemandSensor,
    IdmAdvisorOperationReasonSensor,
    IdmAdvisorPlanSensor,
    predictive_advisor_anomaly_binary,
    predictive_advisor_producer_entities,
    runtime_advisor_engine,
)
from custom_components.idm_heatpump.sensor import async_setup_entry as async_setup_sensors

# Anchored to the real clock so the tests never decay: observation stages
# and status entities compare ``first_observed`` against ``datetime.now``,
# and a fixed past date flips those assertions one day after it is written.
T0 = datetime.now(UTC).replace(microsecond=0)


def _day(offset: float) -> datetime:
    return T0 - timedelta(days=offset)


def _hour(offset: int) -> datetime:
    return T0 + timedelta(hours=offset)


def _iso(at: datetime) -> str:
    return at.isoformat()


def _engine(
    data: dict[str, Any],
    *,
    circuits: tuple[str, ...] = ("a",),
    weather_entity: str | None = None,
    pv_forecast_entity: str | None = None,
    price_entity: str | None = None,
    starts_today: int = 12,
    dhw_share: float = 25.0,
) -> tuple[AdvisorEngine, PredictiveAdvisor, AdvisorAnalytics, MagicMock]:
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.config_entry = SimpleNamespace(entry_id="entry1", options={})
    coordinator.operation_analysis = SimpleNamespace(
        compressor_starts_today=lambda: starts_today,
        operating_share=lambda mode: dhw_share if mode == "dhw" else 0.0,
    )
    hass = MagicMock()
    advisor = PredictiveAdvisor(coordinator)
    advisor._first_observed = _day(8)  # stage: recommending
    analytics = AdvisorAnalytics(hass, "entry1")
    engine = AdvisorEngine(
        hass,
        coordinator,
        advisor,
        analytics,
        circuits=circuits,
        weather_entity=weather_entity,
        pv_forecast_entity=pv_forecast_entity,
        price_entity=price_entity,
    )
    return engine, advisor, analytics, coordinator


# ----------------------------------------------------------------------
# Pure forecast parsing and windows
# ----------------------------------------------------------------------


def test_parse_hourly_temperatures_filters_horizon_and_garbage() -> None:
    payload = [
        {"datetime": _iso(_hour(1)), "temperature": 5.0},
        {"datetime": _iso(_hour(2)), "temperature": 4.0},
        {"datetime": _iso(_hour(50)), "temperature": 1.0},  # beyond horizon
        {"datetime": "garbage", "temperature": 2.0},
        {"datetime": _iso(_hour(3)), "temperature": None},
        "nope",
    ]
    parsed = parse_hourly_temperatures(payload, T0)
    # Hour offsets from T0, not wall-clock hours: T0 follows the real clock.
    assert [((at - T0) // timedelta(hours=1), value) for at, value in parsed] == [(1, 5.0), (2, 4.0)]
    assert parse_hourly_temperatures("nope", T0) == []


def test_parse_pv_hourly_kwh_detailed_and_list_shapes() -> None:
    detailed = SimpleNamespace(attributes={"detailed_forecast": {_iso(_hour(1)): 1.5, _iso(_hour(2)): 2.0, "bad": 3.0}})
    parsed = parse_pv_hourly_kwh(detailed, T0)
    assert [round(value, 1) for _at, value in parsed] == [1.5, 2.0]

    solcast = SimpleNamespace(
        attributes={
            "forecast": [
                {"period_start": _iso(_hour(1)), "pv_estimate": 2.5},
                {"period_start": _iso(_hour(2)), "pv_estimate": 1.5},
            ]
        }
    )
    parsed = parse_pv_hourly_kwh(solcast, T0)
    assert [value for _at, value in parsed] == [2.5, 1.5]

    assert parse_pv_hourly_kwh(SimpleNamespace(attributes={}), T0) == []
    assert parse_pv_hourly_kwh(None, T0) == []


def test_parse_price_hourly_normalizes_cent_and_shapes() -> None:
    state = SimpleNamespace(
        attributes={
            "unit_of_measurement": "ct/kWh",
            "today": [
                {"start": _iso(_hour(1)), "price": 18.0},
                {"start": _iso(_hour(2)), "price": 24.0},
            ],
            "tomorrow": [{"start": _iso(_hour(20)), "price": 12.0}],
        }
    )
    parsed = parse_price_hourly(state, T0)
    assert [round(value, 3) for _at, value in parsed] == [0.18, 0.24, 0.12]
    assert parse_price_hourly(SimpleNamespace(attributes={"today": "nope"}), T0) == []
    assert parse_price_hourly(None, T0) == []


def test_best_window_requires_consecutive_hours() -> None:
    series = [(_hour(1), 1.0), (_hour(2), 4.0), (_hour(4), 4.0), (_hour(5), 1.0)]
    # The 2h/4h gap breaks the window in the middle; best is hours 1-2? No:
    # hours 1,2 are consecutive (sum 5), hours 4,5 consecutive (sum 5).
    window = best_window(series, hours=2, highest=True)
    assert window is not None
    assert round(window[2], 1) == 5.0
    # With a 3-hour requirement nothing consecutive exists.
    assert best_window(series, hours=3, highest=True) is None
    lowest = best_window([(_hour(1), 0.30), (_hour(2), 0.10), (_hour(3), 0.20)], hours=3, highest=False)
    assert lowest is not None
    assert round(lowest[1], 2) == 0.20


# ----------------------------------------------------------------------
# observe(): analytics feeding and cooldown episodes
# ----------------------------------------------------------------------


def test_observe_feeds_running_metrics_and_counters() -> None:
    data = {
        "outdoor_temp": 5.0,
        "power_consumption_hp": 2.0,
        "thermal_power_flow_sensor": 4.8,
        "hp_flow_temp": 30.0,
        "hp_return_temp": 26.0,
        "heat_sink_flow_rate": 1.5,
        "hc_a_room_temp": 21.0,
        "hc_a_room_setpoint_heat_normal": 21.0,
        "hc_a_flow_temp": 29.0,
    }
    engine, _advisor, analytics, _coordinator = _engine(data)
    engine.observe(now=T0)
    model = analytics.building_model
    assert model["flow_curve_samples"] == 1
    assert model["heat_fit_samples"] == 1
    today = T0.date().isoformat()
    assert analytics._daily["heat_sink_flow_rate"][today][0] == 1.5
    assert analytics._daily["hp_temperature_spread"][today][0] == 4.0
    # max-mode counters keep the running maximum, not a mean.
    assert analytics._daily["compressor_starts"][today][0] == 12
    assert analytics._daily["dhw_charge_minutes"][today][0] == 360.0


def test_observe_records_cooldown_episode() -> None:
    engine, _advisor, analytics, coordinator = _engine({"power_consumption_hp": 2.0, "hc_a_room_temp": 21.0})
    engine.observe(now=T0)
    coordinator.data = {"power_consumption_hp": 0.0, "hc_a_room_temp": 21.0, "outdoor_temp": 0.0}
    engine.observe(now=_hour(4))
    coordinator.data = {"power_consumption_hp": 0.0, "hc_a_room_temp": 19.6, "outdoor_temp": 0.0}
    engine.observe(now=_hour(8))
    assert analytics.building_model["cooldown_episodes"] == 1


def test_observe_ignores_empty_snapshots() -> None:
    engine, _advisor, analytics, _coordinator = _engine({})
    engine.observe(now=T0)
    assert analytics.building_model["heat_fit_samples"] == 0


# ----------------------------------------------------------------------
# Anomaly producer
# ----------------------------------------------------------------------


def _seed_days(analytics: AdvisorAnalytics, key: str, value: float, days: int = 4) -> None:
    for offset in range(1, days + 1):
        analytics.observe_metric(key, value, _day(offset))


def test_anomaly_producer_submits_and_retracts() -> None:
    data = {"power_consumption_hp": 2.0, "heat_sink_flow_rate": 1.0}
    engine, advisor, analytics, _coordinator = _engine(data)
    _seed_days(analytics, "heat_sink_flow_rate", 1.5)
    engine.observe(now=T0)  # first observe runs the producers
    anomaly_ids = [rec.id for rec in advisor.active_recommendations if rec.category is RecommendationCategory.ANOMALY]
    assert any("flow_rate_low" in rec_id for rec_id in anomaly_ids)
    assert engine.anomaly_active is True
    assert engine.anomaly_findings

    # A fresh engine on a healthy day withdraws the recommendation again.
    healthy_data = {"power_consumption_hp": 2.0, "heat_sink_flow_rate": 1.5}
    engine2, advisor2, analytics2, _coord2 = _engine(healthy_data)
    _seed_days(analytics2, "heat_sink_flow_rate", 1.5)
    stale = [rec for rec in advisor2.active_recommendations]
    assert stale == []
    engine2.observe(now=T0)
    assert not [rec for rec in advisor2.active_recommendations if rec.category is RecommendationCategory.ANOMALY]
    assert engine2.anomaly_active is False


def test_anomaly_producer_flags_starts_and_dhw_charge() -> None:
    data = {"power_consumption_hp": 2.0}
    engine, advisor, analytics, _coordinator = _engine(data, starts_today=19, dhw_share=62.5)
    _seed_days(analytics, "compressor_starts", 8.0)
    _seed_days(analytics, "dhw_charge_minutes", 60.0)
    engine.observe(now=T0)
    ids = [rec.id for rec in advisor.active_recommendations if rec.category is RecommendationCategory.ANOMALY]
    assert any("compressor_starts" in rec_id for rec_id in ids)
    assert any("dhw_charge_long" in rec_id for rec_id in ids)


def test_anomaly_producer_respects_observation_stage() -> None:
    data = {"power_consumption_hp": 2.0, "heat_sink_flow_rate": 1.0}
    engine, advisor, analytics, _coordinator = _engine(data)
    advisor._first_observed = T0  # collecting: no producers yet
    _seed_days(analytics, "heat_sink_flow_rate", 1.5)
    engine.observe(now=T0)
    assert advisor.recommendation_count == 0


# ----------------------------------------------------------------------
# Heating-curve producer
# ----------------------------------------------------------------------


def test_heating_curve_producer_recommends_and_retracts() -> None:
    data = {
        "power_consumption_hp": 2.0,
        "hc_a_heating_curve": 0.35,
        "hc_a_room_temp": 22.1,
        "hc_a_room_setpoint_heat_normal": 21.0,
        "hc_a_flow_temp": 32.0,
    }
    engine, advisor, analytics, _coordinator = _engine(data)
    _seed_days(analytics, "room_deviation_a", 0.9, days=8)
    engine.observe(now=T0)
    recs = [rec for rec in advisor.active_recommendations if rec.category is RecommendationCategory.HEATING_CURVE]
    assert len(recs) == 1
    assert recs[0].current_value == 0.35
    assert recs[0].recommended_value == 0.33
    assert "room_temperature_above_target" in recs[0].reasons
    assert engine.curve_recommendations["a"]["recommended"] == 0.33

    # Well-regulated rooms produce no recommendation.
    calm_data = dict(data, hc_a_room_temp=21.0)
    engine2, advisor2, analytics2, _coord2 = _engine(calm_data)
    _seed_days(analytics2, "room_deviation_a", 0.1, days=8)
    engine2.observe(now=T0)
    assert not [rec for rec in advisor2.active_recommendations if rec.category is RecommendationCategory.HEATING_CURVE]
    assert engine2.curve_recommendations == {}


# ----------------------------------------------------------------------
# Forecast refresh: DHW window and 24 h plan
# ----------------------------------------------------------------------


def _weather_payload() -> dict[str, Any]:
    forecast = [{"datetime": _iso(_hour(i)), "temperature": 1.0} for i in range(1, 25)]
    return {"weather.home": {"forecast": forecast}}


def _configure_hass(
    engine: AdvisorEngine, *, pv: Any = None, price: Any = None, weather: dict[str, Any] | None = None
) -> None:
    engine._hass.services.async_call = AsyncMock(return_value=weather if weather is not None else _weather_payload())
    states: dict[str, Any] = {}
    if pv is not None:
        states["sensor.pv_forecast"] = pv
    if price is not None:
        states["sensor.price"] = price
    engine._hass.states.get = MagicMock(side_effect=lambda entity: states.get(entity))


async def test_dhw_window_prefers_pv_forecast() -> None:
    data = {"power_consumption_hp": 2.0}
    engine, advisor, _analytics, _coordinator = _engine(
        data, weather_entity="weather.home", pv_forecast_entity="sensor.pv_forecast"
    )
    pv = SimpleNamespace(
        attributes={"forecast": [{"period_start": _iso(_hour(i)), "pv_estimate": 0.2 + 0.6 * i} for i in range(1, 7)]}
    )
    _configure_hass(engine, pv=pv)
    await engine.async_refresh_forecasts(now=T0)

    window = engine.dhw_window
    assert window is not None
    assert window["source"] == "pv_surplus_forecast"
    assert datetime.fromisoformat(window["start"]) == _hour(4)
    recs = [rec for rec in advisor.active_recommendations if rec.category is RecommendationCategory.DHW]
    assert len(recs) == 1
    assert recs[0].recommended_value == f"{_hour(4):%H:%M}-{_hour(7):%H:%M}"


async def test_dhw_window_falls_back_to_price_forecast() -> None:
    data = {"power_consumption_hp": 2.0}
    engine, advisor, _analytics, _coordinator = _engine(
        data, weather_entity="weather.home", price_entity="sensor.price"
    )
    price = SimpleNamespace(
        attributes={
            "unit_of_measurement": "EUR/kWh",
            "today": [{"start": _iso(_hour(i)), "price": 0.40 - 0.05 * i} for i in range(1, 7)],
        }
    )
    _configure_hass(engine, price=price)
    await engine.async_refresh_forecasts(now=T0)

    window = engine.dhw_window
    assert window is not None
    assert window["source"] == "electricity_price_forecast"
    assert window["heat_cost_eur_per_kwh"] < 0.1
    assert advisor.active_recommendations


async def test_dhw_window_requires_recommending_stage() -> None:
    data = {"power_consumption_hp": 2.0}
    engine, advisor, _analytics, _coordinator = _engine(
        data, weather_entity="weather.home", pv_forecast_entity="sensor.pv_forecast"
    )
    advisor._first_observed = T0  # collecting
    pv = SimpleNamespace(
        attributes={"forecast": [{"period_start": _iso(_hour(i)), "pv_estimate": 3.0} for i in range(1, 7)]}
    )
    _configure_hass(engine, pv=pv)
    await engine.async_refresh_forecasts(now=T0)
    assert engine.dhw_window is None
    assert advisor.recommendation_count == 0


async def test_plan_joins_heat_demand_pv_price_and_conflict() -> None:
    data = {"power_consumption_hp": 2.0, "hc_a_room_temp": 21.0}
    engine, advisor, analytics, _coordinator = _engine(
        data, weather_entity="weather.home", pv_forecast_entity="sensor.pv_forecast", price_entity="sensor.price"
    )
    for delta in range(1, 61):
        analytics.observe_heating(float(delta), 0.2 * delta)  # 200 W/K
    pv = SimpleNamespace(
        attributes={"forecast": [{"period_start": _iso(_hour(i)), "pv_estimate": 0.2 + 0.6 * i} for i in range(1, 7)]}
    )
    # Expensive hours exactly over the PV window (hours 4-6) force a conflict.
    price = SimpleNamespace(
        attributes={
            "today": [{"start": _iso(_hour(i)), "price": 0.90 if 4 <= i <= 6 else 0.10} for i in range(1, 7)],
        }
    )
    _configure_hass(engine, pv=pv, price=price)
    await engine.async_refresh_forecasts(now=T0)

    plan = engine.plan
    assert plan is not None
    assert plan["predicted_heat_demand_kwh"] == pytest.approx(96.0, abs=1.0)
    assert plan["expected_pv_kwh"] == pytest.approx(13.8, abs=0.1)
    assert plan["dhw_window_conflicts_with_expensive_hours"] is True
    assert any(rec.category is RecommendationCategory.ELECTRICITY_PRICE for rec in advisor.active_recommendations)


async def test_plan_without_conflict_reports_ok() -> None:
    data = {"power_consumption_hp": 2.0, "hc_a_room_temp": 21.0}
    engine, advisor, _analytics, _coordinator = _engine(
        data, weather_entity="weather.home", pv_forecast_entity="sensor.pv_forecast", price_entity="sensor.price"
    )
    pv = SimpleNamespace(
        attributes={"forecast": [{"period_start": _iso(_hour(i)), "pv_estimate": 0.2 + 0.6 * i} for i in range(1, 7)]}
    )
    price = SimpleNamespace(
        attributes={"today": [{"start": _iso(_hour(i)), "price": 0.90 if i <= 3 else 0.10} for i in range(1, 7)]}
    )
    _configure_hass(engine, pv=pv, price=price)
    await engine.async_refresh_forecasts(now=T0)
    plan = engine.plan
    assert plan is not None
    assert "dhw_window_conflicts_with_expensive_hours" not in plan
    assert not [
        rec for rec in advisor.active_recommendations if rec.category is RecommendationCategory.ELECTRICITY_PRICE
    ]


async def test_forecast_refresh_survives_service_failure() -> None:
    data = {"power_consumption_hp": 2.0}
    engine, _advisor, _analytics, _coordinator = _engine(data, weather_entity="weather.home")
    engine._hass.services.async_call = AsyncMock(side_effect=OSError("down"))
    await engine.async_refresh_forecasts(now=T0)
    assert engine.weather_hours == []
    assert engine.dhw_window is None
    assert engine.plan is None


async def test_forecast_loop_runs_until_cancelled() -> None:
    engine, _advisor, _analytics, _coordinator = _engine({})
    refresh = AsyncMock()
    with (
        patch.object(AdvisorEngine, "async_refresh_forecasts", refresh),
        patch(
            "custom_components.idm_heatpump.advisor_engine.asyncio.sleep",
            AsyncMock(side_effect=[None, asyncio.CancelledError()]),
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await advisor_forecast_loop(engine, 60)
    assert refresh.await_count == 2


async def test_forecast_loop_survives_refresh_errors() -> None:
    engine, _advisor, _analytics, _coordinator = _engine({})
    refresh = AsyncMock(side_effect=[ValueError("boom")])
    with (
        patch.object(AdvisorEngine, "async_refresh_forecasts", refresh),
        patch(
            "custom_components.idm_heatpump.advisor_engine.asyncio.sleep",
            AsyncMock(side_effect=asyncio.CancelledError()),
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await advisor_forecast_loop(engine, 60)
    assert refresh.await_count == 1


# ----------------------------------------------------------------------
# Scores and entities
# ----------------------------------------------------------------------


def test_health_and_efficiency_need_data() -> None:
    engine, _advisor, analytics, _coordinator = _engine({"power_consumption_hp": 2.0})
    assert engine.health["score"] is None
    assert engine.efficiency["score"] is None

    _seed_days(analytics, "heat_sink_flow_rate", 1.5)
    _seed_days(analytics, "compressor_starts", 8.0)
    health = engine.health
    assert health["score"] == 100
    assert set(health["components"]) == {"hydraulics", "compressor"}

    for _ in range(20):
        analytics.observe_cop_sample(5.0, 30.0, thermal_kw=4.8, electric_kw=1.2, hours=0.2)
    efficiency = engine.efficiency
    assert efficiency["observed_cop"] == 4.0


def test_runtime_guard_rejects_mocks() -> None:
    assert runtime_advisor_engine(SimpleNamespace(advisor_engine=None)) is None
    assert runtime_advisor_engine(MagicMock()) is None


def test_producer_entity_factories_gate_on_engine() -> None:
    data = {"power_consumption_hp": 2.0}
    engine, advisor, _analytics, coordinator = _engine(data)
    assert predictive_advisor_producer_entities(coordinator, None, engine) == []
    assert predictive_advisor_producer_entities(coordinator, advisor, None) == []
    assert predictive_advisor_anomaly_binary(coordinator, None, engine) == []
    entities = predictive_advisor_producer_entities(coordinator, advisor, engine)
    keys = {entity.entity_description.key for entity in entities}
    assert "advisor_confidence" in keys
    assert "advisor_operation_reason" in keys
    assert "advisor_hc_a_curve_recommendation" in keys
    binaries = predictive_advisor_anomaly_binary(coordinator, advisor, engine)
    assert len(binaries) == 1


def test_producer_entity_values() -> None:
    data = {
        "hp_operating_mode": 1,
        "power_consumption_hp": 2.0,
        "outdoor_temp": 5.0,
        "hc_a_setpoint_flow_temp": 32.0,
        "hc_a_flow_temp": 28.7,
        "hc_a_room_temp": 21.5,
        "hc_a_room_setpoint_heat_normal": 22.0,
    }
    engine, advisor, _analytics, coordinator = _engine(data)
    coordinator.last_update_success = True

    reason = IdmAdvisorOperationReasonSensor(coordinator, engine)
    assert reason.native_value == "Heating circuit A"
    assert reason.extra_state_attributes["write_actions"] is False

    confidence = IdmAdvisorConfidenceSensor(coordinator, advisor)
    assert confidence.native_value == round(advisor.confidence * 100)

    curve = IdmAdvisorCurveSensor(coordinator, engine, "a")
    assert curve._attr_unique_id == "entry1_advisor_hc_a_curve_recommendation"
    assert curve._attr_translation_placeholders == {"circuit": "A"}
    assert curve.native_value is None
    engine._curve_recommendations = {"a": {"recommended": 0.33, "current": 0.35}}
    assert curve.native_value == 0.33

    dhw = IdmAdvisorDhwWindowSensor(coordinator, engine)
    engine._dhw_window = {"start": _iso(_hour(4)), "hours": 3, "source": "pv_surplus_forecast"}
    assert dhw.native_value == f"{_hour(4):%H:%M}-{_hour(7):%H:%M}"

    demand = IdmAdvisorHeatDemandSensor(coordinator, engine)
    engine._plan = {"predicted_heat_demand_kwh": 31.4}
    assert demand.native_value == 31.4

    plan = IdmAdvisorPlanSensor(coordinator, engine)
    assert plan.native_value == "ok"
    engine._plan = {"predicted_heat_demand_kwh": 31.4, "dhw_window_conflicts_with_expensive_hours": True}
    assert plan.native_value == "attention"


async def test_platforms_create_producer_entities() -> None:
    data = {"hp_operating_mode": 1, "power_consumption_hp": 2.0}
    engine, advisor, _analytics, coordinator = _engine(data)
    coordinator.sensor_descriptions = []
    entry = MagicMock()
    entry.options = {"feature_profile": "smart"}
    entry.runtime_data = SimpleNamespace(
        coordinator=coordinator,
        operation_analysis=None,
        predictive_advisor=advisor,
        advisor_engine=engine,
    )

    added_sensors: list[Any] = []
    await async_setup_sensors(MagicMock(), entry, MagicMock(side_effect=added_sensors.extend))
    sensor_keys = {entity.entity_description.key for entity in added_sensors}
    assert "advisor_operation_reason" in sensor_keys
    assert "advisor_confidence" in sensor_keys
    assert "advisor_hc_a_curve_recommendation" in sensor_keys
    assert "advisor_next_24h" in sensor_keys

    added_binaries: list[Any] = []
    await async_setup_binary_sensors(MagicMock(), entry, MagicMock(side_effect=added_binaries.extend))
    assert "advisor_anomaly_detected" in {entity.entity_description.key for entity in added_binaries}
