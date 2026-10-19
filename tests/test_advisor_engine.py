"""Tests for the advisor engine: producers, forecasts, windows, plan."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.idm_heatpump import advisor_engine as advisor_engine_module
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
    RecommendationSeverity,
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
# Floored to the hour: forecast parsing folds sub-hourly samples onto
# calendar hours, so the fixtures must sit on hour boundaries.
T0 = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)


def _day(offset: float) -> datetime:
    return T0 - timedelta(days=offset)


def _hour(offset: int) -> datetime:
    return T0 + timedelta(hours=offset)


def _iso(at: datetime) -> str:
    return at.isoformat()


_TEST_ZONE = ZoneInfo("Europe/Berlin")


def _pin_local_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render window times in a fixed zone, independent of the host clock."""
    monkeypatch.setattr(advisor_engine_module.dt_util, "as_local", lambda value: value.astimezone(_TEST_ZONE))


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
    # A list whose entries all fail to parse folds an empty grid.
    assert (
        parse_pv_hourly_kwh(
            SimpleNamespace(attributes={"forecast": [{"period_start": "garbage", "pv_estimate": 1.0}]}), T0
        )
        == []
    )


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


def test_cop_domain_maps_operating_modes() -> None:
    from custom_components.idm_heatpump.advisor_engine import _cop_domain

    assert _cop_domain(1) == "heating"
    assert _cop_domain(4) == "dhw"
    assert _cop_domain(8) == "total"  # defrost
    assert _cop_domain(9) == "total"  # heating + defrost
    assert _cop_domain(5) == "total"  # mixed heating + DHW
    assert _cop_domain(2) == "total"  # cooling
    assert _cop_domain(0) == "total"
    assert _cop_domain(-1) == "total"  # not a valid flag combination
    assert _cop_domain(None) == "total"
    assert _cop_domain("garbage") == "total"


def test_quarter_hour_price_grid_folds_onto_calendar_hours() -> None:
    """15-minute day-ahead grids must not read as full hours (post-2025 EU)."""
    quarter_hours = []
    for hour in range(1, 7):
        for quarter in range(4):
            price = 0.40 if hour in (2, 3, 4) else 0.10
            quarter_hours.append({"start": _iso(_hour(hour) + timedelta(minutes=15 * quarter)), "price": price})
    state = SimpleNamespace(attributes={"today": quarter_hours})
    parsed = parse_price_hourly(state, T0)
    assert len(parsed) == 6
    # Each hour carries the mean of its quarters (here: all quarters equal).
    assert [round(value, 2) for _at, value in parsed] == [0.10, 0.40, 0.40, 0.40, 0.10, 0.10]
    # A 3-hour window over the cheap tail (hours 4-6) sums hours, not slots.
    window = best_window(parsed, hours=3, highest=False)
    assert window is not None
    assert window[0] == _hour(4)
    assert round(window[1], 2) == 0.20


def test_duplicate_price_timestamps_across_attributes_dedupe() -> None:
    """The same hour under two attribute names must not kill the window."""
    hours = [{"start": _iso(_hour(i)), "price": 0.40 - 0.05 * i} for i in range(1, 7)]
    state = SimpleNamespace(attributes={"today": hours, "raw_today": [dict(entry) for entry in hours]})
    parsed = parse_price_hourly(state, T0)
    assert len(parsed) == 6
    assert best_window(parsed, hours=3, highest=False) is not None


def test_half_hourly_pv_grid_counts_real_kwh() -> None:
    """A 30-minute Solcast-style grid contributes half of each kW value."""
    entries = []
    for hour in range(1, 7):
        for half in range(2):
            entries.append({"period_start": _iso(_hour(hour) + timedelta(minutes=30 * half)), "pv_estimate": 1.0})
    state = SimpleNamespace(attributes={"forecast": entries})
    parsed = parse_pv_hourly_kwh(state, T0)
    assert len(parsed) == 6
    # 1 kW for 30 min twice = 1 kWh per hour, not 2.
    assert all(round(kwh, 3) == 1.0 for _at, kwh in parsed)


# ----------------------------------------------------------------------
# observe(): analytics feeding and cooldown episodes
# ----------------------------------------------------------------------


def test_observe_feeds_running_metrics_and_counters() -> None:
    data = {
        "outdoor_temp": 5.0,
        "power_consumption_hp": 2.0,
        "thermal_power_flow_sensor": 4.8,
        "hp_operating_mode": 1,
        "hc_a_active_mode": 1,
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


def test_observe_falls_back_to_current_power_when_flow_sensor_is_zero() -> None:
    data = {
        "outdoor_temp": 5.0,
        "power_consumption_hp": 0.62,
        "thermal_power_flow_sensor": 0.0,
        "current_power": 3.46,
        "hp_operating_mode": 1,
        "hc_a_active_mode": 1,
        "hp_flow_temp": 30.0,
        "hp_return_temp": 26.0,
        "hc_a_room_temp": 21.0,
        "hc_a_room_setpoint_heat_normal": 21.0,
        "hc_a_flow_temp": 29.0,
    }
    engine, _advisor, analytics, _coordinator = _engine(data)
    engine.observe(now=T0)
    engine.observe(now=T0 + timedelta(minutes=1))
    assert analytics.building_model["heat_fit_samples"] == 2
    assert len(analytics._cop_map) == 1


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


async def test_dhw_window_prefers_pv_forecast(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin_local_zone(monkeypatch)
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
    # The stored timestamps are UTC; the text is the user's wall clock.
    assert (
        recs[0].recommended_value == f"{_hour(4).astimezone(_TEST_ZONE):%H:%M}-{_hour(7).astimezone(_TEST_ZONE):%H:%M}"
    )


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
        # Advancing timestamps: each sample carries the hours it represents
        # (12 min), so the weighted fit has enough effective hours.
        analytics.observe_heating(float(delta), 0.2 * delta, T0 + timedelta(minutes=12 * delta))  # 200 W/K
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


def test_producer_entity_values(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin_local_zone(monkeypatch)
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
    assert dhw.native_value == f"{_hour(4).astimezone(_TEST_ZONE):%H:%M}-{_hour(7).astimezone(_TEST_ZONE):%H:%M}"

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


# ----------------------------------------------------------------------
# Additional forecast-parsing shapes and window guards
# ----------------------------------------------------------------------


def test_parse_forecasts_accept_integer_hours_and_reject_naive_timestamps() -> None:
    # Integer keys are hour offsets from now (PVForecast detailed shape).
    detailed = SimpleNamespace(attributes={"detailed_forecast": {2: 1.25}})
    assert parse_pv_hourly_kwh(detailed, T0) == [
        (T0.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2), 1.25)
    ]

    # Naive ISO timestamps are rejected, not silently read as UTC: feeds
    # stamping naive local time would otherwise shift the whole series.
    naive_stamp = _hour(3).replace(tzinfo=None).isoformat()
    assert parse_hourly_temperatures([{"datetime": naive_stamp, "temperature": 9.0}], T0) == []
    assert parse_price_hourly(SimpleNamespace(attributes={"today": [{"start": naive_stamp, "price": 0.2}]}), T0) == []


def test_parse_forecasts_skip_non_mapping_entries() -> None:
    pv = SimpleNamespace(attributes={"forecast": ["nope", {"period_start": _iso(_hour(1)), "pv_estimate": 2.0}]})
    assert parse_pv_hourly_kwh(pv, T0) == [(_hour(1), 2.0)]

    price = SimpleNamespace(attributes={"today": ["nope", {"start": _iso(_hour(1)), "price": 0.20}]})
    assert parse_price_hourly(price, T0) == [(_hour(1), 0.2)]


def test_best_window_none_for_a_too_short_series() -> None:
    assert best_window([(_hour(1), 1.0), (_hour(2), 2.0)], highest=True) is None
    assert best_window([], highest=False) is None


# ----------------------------------------------------------------------
# observe(): clock anchor, COP intervals and cooldown guards
# ----------------------------------------------------------------------


def test_observe_without_now_anchor_uses_the_clock() -> None:
    data = {
        "power_consumption_hp": 2.0,
        "hc_a_room_temp": 21.0,
        "outdoor_temp": 5.0,
        "thermal_power_flow_sensor": 4.8,
        "hp_operating_mode": 1,
        "hc_a_active_mode": 1,
    }
    engine, _advisor, analytics, _coordinator = _engine(data)

    engine.observe()  # no anchor: the engine stamps the sample from the clock

    assert analytics.building_model["heat_fit_samples"] == 1


def test_consecutive_running_samples_integrate_a_cop_interval() -> None:
    data = {
        "outdoor_temp": 5.0,
        "power_consumption_hp": 2.0,
        "thermal_power_flow_sensor": 4.8,
        "hp_operating_mode": 1,
        "hc_a_active_mode": 1,
        "hp_flow_temp": 30.0,
        "hp_return_temp": 26.0,
    }
    engine, _advisor, analytics, _coordinator = _engine(data)

    engine.observe(now=T0)
    engine.observe(now=_hour(1))
    engine.observe(now=_hour(2))

    # Two consecutive running samples close two half-hour-capped intervals, so
    # the operating point reaches the one-hour minimum of the COP map.
    assert analytics.building_model["cop_buckets"] == 1
    expected = analytics.expected_cop(5.0, 30.0)
    assert expected is not None
    assert expected.cop == 2.4  # 4.8 kW thermal / 2.0 kW electric
    assert expected.hours == 1.0


def test_observe_idle_guards_ignore_short_and_stable_episodes() -> None:
    engine, _advisor, analytics, coordinator = _engine(
        {"power_consumption_hp": 2.0, "hc_a_room_temp": 21.0, "outdoor_temp": 0.0}
    )
    engine.observe(now=T0)
    coordinator.data = {"power_consumption_hp": 0.0, "hc_a_room_temp": 21.0, "outdoor_temp": 0.0}
    engine.observe(now=_hour(1))  # compressor stops: episode bookkeeping starts
    engine.observe(now=_hour(2))  # one hour in: below the 3 h minimum, ignored
    coordinator.data = {"power_consumption_hp": 0.0, "hc_a_room_temp": 20.95, "outdoor_temp": 0.0}
    engine.observe(now=_hour(5))  # 4 h in but only 0.05 K drop: closed without a sample
    engine.observe(now=_hour(6))  # already recorded: nothing further happens

    assert analytics.building_model["cooldown_episodes"] == 0


def test_observe_ignores_cooldown_while_indoor_matches_outdoor() -> None:
    engine, _advisor, analytics, coordinator = _engine(
        {"power_consumption_hp": 2.0, "hc_a_room_temp": 5.2, "outdoor_temp": 5.0}
    )
    engine.observe(now=T0)
    coordinator.data = {"power_consumption_hp": 0.0, "hc_a_room_temp": 5.2, "outdoor_temp": 5.0}
    engine.observe(now=_hour(1))
    coordinator.data = {"power_consumption_hp": 0.0, "hc_a_room_temp": 1.0, "outdoor_temp": 5.0}
    engine.observe(now=_hour(5))  # 4.2 K drop, but the mean room is colder than outside

    assert analytics.building_model["cooldown_episodes"] == 0


# ----------------------------------------------------------------------
# Anomaly producer: spread baseline and withdrawal
# ----------------------------------------------------------------------


def test_anomaly_producer_flags_high_spread_and_retracts_when_healed() -> None:
    data = {"power_consumption_hp": 2.0, "hp_flow_temp": 30.0, "hp_return_temp": 22.0}
    engine, advisor, analytics, coordinator = _engine(data)
    _seed_days(analytics, "hp_temperature_spread", 4.0)
    engine.observe(now=T0)
    spread_recs = [
        rec
        for rec in advisor.active_recommendations
        if rec.category is RecommendationCategory.ANOMALY and "spread_high" in rec.id
    ]
    assert len(spread_recs) == 1
    assert spread_recs[0].severity == RecommendationSeverity.WARNING  # 4 K is double the threshold

    # Seven hours later the spread normalized: the recommendation is withdrawn.
    coordinator.data = {"power_consumption_hp": 2.0, "hp_flow_temp": 30.0, "hp_return_temp": 27.0}
    engine.observe(now=_hour(7))
    assert not [rec for rec in advisor.active_recommendations if rec.category is RecommendationCategory.ANOMALY]
    assert engine.anomaly_active is False


# ----------------------------------------------------------------------
# Heating-curve producer: raise recommendation and flow excess
# ----------------------------------------------------------------------


def test_heating_curve_producer_recommends_raise_and_notes_flow_excess() -> None:
    data = {
        "power_consumption_hp": 2.0,
        "outdoor_temp": 0.0,
        "hc_a_heating_curve": 1.20,
        "hc_a_room_temp": 20.2,
        "hc_a_room_setpoint_heat_normal": 21.0,
        "hc_a_flow_temp": 45.0,
    }
    engine, advisor, analytics, _coordinator = _engine(data)
    _seed_days(analytics, "room_deviation_a", -0.9, days=8)
    # Learned flow curve: flow falls 0.5 K per K outdoor, so 40 degC at 0 degC.
    for outdoor in range(60):
        analytics.observe_flow_pair(float(outdoor), 40.0 - 0.5 * outdoor, T0 + timedelta(minutes=12 * outdoor))

    engine.observe(now=T0)

    recs = [rec for rec in advisor.active_recommendations if rec.category is RecommendationCategory.HEATING_CURVE]
    assert len(recs) == 1
    assert recs[0].current_value == 1.20
    assert recs[0].recommended_value == 1.22
    assert "room_temperature_below_target" in recs[0].reasons
    # The measured flow runs 5 K above the estimated requirement at 0 degC.
    assert "flow_temperature_above_estimated_requirement" in recs[0].reasons
    assert engine.curve_recommendations["a"]["recommended"] == 1.22


# ----------------------------------------------------------------------
# Forecast refresh without a weather entity
# ----------------------------------------------------------------------


async def test_dhw_price_window_without_weather_uses_cop_fallback() -> None:
    data = {"power_consumption_hp": 2.0}
    engine, advisor, _analytics, _coordinator = _engine(data, price_entity="sensor.price")
    price = SimpleNamespace(
        attributes={
            "unit_of_measurement": "EUR/kWh",
            "today": [{"start": _iso(_hour(i)), "price": 0.40 - 0.05 * i} for i in range(1, 7)],
        }
    )
    _configure_hass(engine, price=price)

    await engine.async_refresh_forecasts(now=T0)

    # No weather entity is configured, so the weather leg stays empty and every
    # price hour falls back to the typical COP of 3.5.
    assert engine.weather_hours == []
    assert engine.pv_hours == []
    assert len(engine.price_hours) == 6
    window = engine.dhw_window
    assert window is not None
    assert window["source"] == "electricity_price_forecast"
    assert window["heat_cost_eur_per_kwh"] < 0.1
    assert any(rec.category is RecommendationCategory.DHW for rec in advisor.active_recommendations)


async def test_dhw_price_window_prefers_the_observed_dhw_cop() -> None:
    data = {"power_consumption_hp": 2.0}
    engine, advisor, analytics, _coordinator = _engine(data, price_entity="sensor.price")
    # Observed DHW charging runs at COP 2.0 — well below the map's heating
    # expectation; the heat cost must be scored with the honest number.
    for _ in range(5):
        analytics.observe_cop_sample(5.0, 60.0, thermal_kw=2.0, electric_kw=1.0, hours=0.2, domain="dhw")
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
    assert window["assumed_cop"] == 2.0
    # Cheapest hours 4-6 at 0.20/0.15/0.10 EUR with COP 2 -> mean 0.075.
    assert window["heat_cost_eur_per_kwh"] == pytest.approx(0.075, abs=0.001)
    assert any(rec.category is RecommendationCategory.DHW for rec in advisor.active_recommendations)


async def test_dhw_window_confidence_treats_zero_quality_as_zero() -> None:
    data = {"power_consumption_hp": 2.0}
    engine, advisor, _analytics, _coordinator = _engine(data, price_entity="sensor.price")
    # Every watched sample implausible: usable_fraction is 0.0, which must
    # lower the confidence, not read as "full quality" via `or`.
    for _ in range(3):
        advisor.observe(now=T0)
    advisor._quality = {
        key: type(quality)(samples=10, usable=0, unavailable=0, implausible=10, frozen=0)
        for key, quality in advisor._quality.items()
    }
    assert advisor.usable_fraction == 0.0
    price = SimpleNamespace(
        attributes={
            "unit_of_measurement": "EUR/kWh",
            "today": [{"start": _iso(_hour(i)), "price": 0.40 - 0.05 * i} for i in range(1, 7)],
        }
    )
    _configure_hass(engine, price=price)
    await engine.async_refresh_forecasts(now=T0)

    recs = [rec for rec in advisor.active_recommendations if rec.category is RecommendationCategory.DHW]
    assert recs
    assert recs[0].confidence == 0.25  # 0.55 * 0.0 + 0.25


def test_health_penalties_match_reason_codes_not_titles() -> None:
    engine, advisor, analytics, _coordinator = _engine({"power_consumption_hp": 2.0})
    for days_ago in range(1, 4):
        at = T0 - timedelta(days=days_ago)
        analytics.observe_metric("heat_sink_flow_rate", 1.2, at)
        analytics.observe_metric("compressor_starts", 10.0, at, mode="max")
    # A warning finding whose title shares no keyword with the domain name
    # must still penalize it through its machine reason code.
    from custom_components.idm_heatpump.predictive_advisor import Recommendation as _Recommendation
    from custom_components.idm_heatpump.predictive_advisor import RecommendationCategory as _Category
    from custom_components.idm_heatpump.predictive_advisor import RecommendationSeverity as _Severity

    advisor.submit(
        _Recommendation(
            id=f"anomaly_flow_rate_low_{T0:%Y%m%d}",
            category=_Category.ANOMALY,
            severity=_Severity.WARNING,
            title="Volumenstrom weit unterBaseline",
            reasons=("heat_circle_flow_below_baseline",),
        )
    )
    health = engine.health
    assert health["components"]["hydraulics"] == 70.0
    assert health["components"]["compressor"] == 100.0


# ----------------------------------------------------------------------
# Derived scores and pass-through properties
# ----------------------------------------------------------------------


def test_engine_exposes_analytics_and_demand_reason_guard() -> None:
    engine, _advisor, analytics, coordinator = _engine({"power_consumption_hp": 2.0})
    assert engine.analytics is analytics

    coordinator.web_supplement = None
    assert engine.demand_reason_label is None


def test_health_and_efficiency_scores_compose_every_domain() -> None:
    data = {"power_consumption_hp": 2.0, "outdoor_temp": 5.0, "hp_flow_temp": 30.0}
    engine, _advisor, analytics, _coordinator = _engine(data)
    _seed_days(analytics, "heat_sink_flow_rate", 1.5)
    _seed_days(analytics, "compressor_starts", 8.0)
    _seed_days(analytics, "dhw_charge_minutes", 60.0)
    for _ in range(10):
        analytics.observe_cop_sample(5.0, 30.0, thermal_kw=4.8, electric_kw=1.2, hours=0.2)

    efficiency = engine.efficiency
    assert efficiency["expected_cop"] == 4.0
    assert efficiency["observed_cop"] == 4.0
    assert efficiency["deviation_percent"] == 0.0
    assert efficiency["score"] == 100

    health = engine.health
    assert set(health["components"]) == {"hydraulics", "compressor", "dhw", "efficiency"}
    assert health["components"]["dhw"] == 100
    assert health["score"] == 100
    assert health["write_actions"] is False


class TestImplausibleRoomTemperature:
    """A circuit without a wired room sensor reports uninitialized memory (#504).

    -327.33 is finite and slipped through ``_number()``, so the engine fed it
    to the heat-loss regression, the room-deviation metric and the heat-demand
    plan while the advisor's quality tracker correctly reported 0 % usable.
    """

    def test_implausible_room_temp_is_treated_as_missing(self) -> None:
        engine, _advisor, analytics, _coordinator = _engine(
            {
                "outdoor_temp": 5.0,
                "power_consumption_hp": 2.0,
                "thermal_power_flow_sensor": 6.0,
                "hc_a_room_temp": -327.33,
                "hc_a_room_setpoint_heat_normal": 21.0,
            }
        )

        engine.observe()

        assert analytics.metric_baseline("room_deviation_a", T0) is None
        assert analytics.heat_loss_w_per_k is None  # no observe_heating sample

    def test_implausible_room_temp_never_reaches_the_plan_indoor_temperature(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine, _advisor, analytics, _coordinator = _engine(
            {"outdoor_temp": 5.0, "power_consumption_hp": 0.0, "hc_a_room_temp": -327.33}
        )
        engine._weather_hours = [(T0, 5.0)] * 24
        monkeypatch.setattr(type(analytics), "heat_loss_w_per_k", property(lambda self: 2000.0))

        engine._compute_plan(T0)

        # indoor falls back to the 21 C default: 2 kW/K * (21-5) K * 24 h
        assert engine._plan == {"predicted_heat_demand_kwh": round(2.0 * 16.0 * 24.0, 1)}

    def test_polluted_room_deviation_storage_never_recommends(self) -> None:
        engine, advisor, _analytics, _coordinator = _engine(
            {"hc_a_heating_curve": 1.2, "hc_a_room_temp": -327.33, "hc_a_room_setpoint_heat_normal": 21.0}
        )
        # Simulate storage polluted before the plausibility filter existed.
        baseline = SimpleNamespace(days=10, median=-349.0)
        engine._analytics.metric_baseline = lambda name, now: baseline if name == "room_deviation_a" else None

        engine._produce_heating_curve(T0)

        assert not [
            recommendation
            for recommendation in advisor.active_recommendations
            if recommendation.category is RecommendationCategory.HEATING_CURVE
        ]

    def test_plausible_room_temp_still_feeds_the_models(self) -> None:
        engine, _advisor, analytics, _coordinator = _engine(
            {
                "outdoor_temp": 5.0,
                "power_consumption_hp": 2.0,
                "thermal_power_flow_sensor": 6.0,
                "hc_a_room_temp": 22.0,
                "hc_a_room_setpoint_heat_normal": 21.0,
            }
        )

        for offset in (5, 4, 3, 2, 1, 0):
            engine.observe(T0 - timedelta(days=offset))

        assert analytics.metric_baseline("room_deviation_a", T0) is not None


class TestAdvisorRoomTemperatureSources:
    """Read-only HA sensors stand in for circuits without a wired sensor (#504)."""

    def test_mapped_source_overrides_the_garbage_register(self) -> None:
        engine, _advisor, analytics, _coordinator = _engine(
            {
                "outdoor_temp": 5.0,
                "power_consumption_hp": 2.0,
                "thermal_power_flow_sensor": 6.0,
                "hc_a_room_temp": -327.33,  # uninitialized memory, no sensor wired
                "hc_a_room_setpoint_heat_normal": 21.0,
            }
        )
        engine._room_temp_entities = {"a": "sensor.room_a"}
        engine._hass.states.get = lambda entity_id: SimpleNamespace(state="22.0")

        engine.observe()

        # The deviation comes from the HA source, not the register garbage.
        for offset in (5, 4, 3, 2, 1, 0):
            engine.observe(T0 - timedelta(days=offset))
        baseline = analytics.metric_baseline("room_deviation_a", T0)
        assert baseline is not None
        assert abs(baseline.median - 1.0) < 0.2

    def test_unavailable_source_does_not_fall_back_to_the_garbage_register(self) -> None:
        engine, _advisor, analytics, _coordinator = _engine(
            {"outdoor_temp": 5.0, "power_consumption_hp": 2.0, "hc_a_room_temp": -327.33}
        )
        engine._room_temp_entities = {"a": "sensor.room_a"}
        engine._hass.states.get = lambda entity_id: None

        engine.observe()

        assert analytics.heat_loss_w_per_k is None

    def test_no_source_keeps_the_register_behaviour(self) -> None:
        engine, _advisor, analytics, _coordinator = _engine(
            {"outdoor_temp": 5.0, "power_consumption_hp": 2.0, "hc_a_room_temp": 22.0}
        )

        engine.observe()

        assert analytics.heat_loss_w_per_k is None  # needs thermal power; just no crash


@pytest.mark.parametrize("mode", [None, 0, 2, 4, 8, 5, 9, True, "1", float("nan")])
def test_building_model_rejects_nonexclusive_heating(mode: Any) -> None:
    data = {
        "hp_operating_mode": mode,
        "power_consumption_hp": 2.0,
        "thermal_power_flow_sensor": 8.0,
        "outdoor_temp": 5.0,
        "hc_a_room_temp": 21.0,
        "hc_a_room_setpoint_heat_normal": 21.0,
        "hc_a_flow_temp": 24.0,
        "hc_a_active_mode": 1,
        "hp_flow_temp": 50.0,
        "hp_return_temp": 45.0,
    }
    engine, _, analytics, _ = _engine(data)
    engine.observe(now=T0)
    engine.observe(now=T0 + timedelta(minutes=1))
    assert analytics.building_model["heat_fit_samples"] == 0
    assert analytics.building_model["flow_curve_samples"] == 0
    # The building-model gate does not disable general operating analytics.
    assert analytics._cop_map


@pytest.mark.parametrize(
    ("active", "setpoint", "expected"),
    [
        (1, 30.0, 1),
        (0, 30.0, 0),
        (2, 30.0, 0),
        (255, 30.0, 0),
        (True, 30.0, 0),
        ("1", 30.0, 0),
        (None, 30.0, 1),
        (None, 0.0, 0),
        (None, None, 0),
        (None, float("nan"), 0),
    ],
)
def test_building_model_requires_an_active_heating_circuit(active: Any, setpoint: Any, expected: int) -> None:
    data = {
        "hp_operating_mode": 1,
        "power_consumption_hp": 2.0,
        "thermal_power_flow_sensor": 4.0,
        "outdoor_temp": 5.0,
        "hc_a_room_temp": 21.0,
        "hc_a_room_setpoint_heat_normal": 21.0,
        "hc_a_flow_temp": 30.0,
        "hc_a_active_mode": active,
        "hc_a_setpoint_flow_temp": setpoint,
    }
    engine, _, analytics, _ = _engine(data)
    engine.observe(now=T0)
    assert analytics.building_model["heat_fit_samples"] == expected
    assert analytics.building_model["flow_curve_samples"] == expected


def test_building_model_uses_room_and_flow_only_from_the_heating_circuit() -> None:
    engine, _, analytics, coordinator = _engine(
        {
            "hp_operating_mode": 1,
            "power_consumption_hp": 2.0,
            "thermal_power_flow_sensor": 4.0,
            "outdoor_temp": 5.0,
            "hc_a_room_temp": 25.0,
            "hc_a_room_setpoint_heat_normal": 25.0,
            "hc_a_flow_temp": 20.0,
            "hc_a_active_mode": 0,
            "hc_b_room_temp": 21.0,
            "hc_b_room_setpoint_heat_normal": 21.0,
            "hc_b_flow_temp": 30.0,
            "hc_b_active_mode": 1,
        },
        circuits=("a", "b"),
    )
    engine.observe(now=T0)
    assert analytics._heat_fit.sx == 16.0
    assert analytics._flow_fit.sy == 30.0
    coordinator.data["hp_operating_mode"] = 4
    engine.observe(now=T0 + timedelta(minutes=1))
    assert analytics.building_model["heat_fit_samples"] == 1
    coordinator.data["hp_operating_mode"] = 1
    engine.observe(now=T0 + timedelta(minutes=2))
    assert analytics.building_model["heat_fit_samples"] == 2


# ----------------------------------------------------------------------
# Forecast.Solar core-integration source (hourly service, no attributes)
# ----------------------------------------------------------------------


class _FakeForecastSolarEntry:
    def __init__(self, config_entry_id: str) -> None:
        self.entity_id = "sensor.power_production_now"
        self.config_entry_id = config_entry_id
        self.domain = "forecast_solar"


class _FakeEntityRegistry:
    def __init__(self, entry: _FakeForecastSolarEntry | None) -> None:
        self._entry = entry

    def async_get(self, entity_id: str) -> _FakeForecastSolarEntry | None:
        return self._entry if entity_id == "sensor.power_production_now" else None


def _forecast_solar_response() -> dict[str, Any]:
    return {"service_response": {}, "wh_period": {_iso(_hour(i)): 1000.0 * i for i in range(1, 7)}}


async def test_pv_forecast_reads_the_forecast_solar_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Core Forecast.Solar sensors carry no hourly attributes; the advisor
    reads the integration's get_forecast service through the entity's
    config entry instead."""
    data = {"power_consumption_hp": 2.0}
    engine, _advisor, _analytics, _coordinator = _engine(data, pv_forecast_entity="sensor.power_production_now")

    registry = _FakeEntityRegistry(_FakeForecastSolarEntry("fs_entry"))
    # The engine resolves the registry module lazily; patch the stub module.
    import homeassistant.helpers.entity_registry as er_stub

    monkeypatch.setattr(er_stub, "async_get", lambda hass: registry)

    calls: dict[str, Any] = {}

    async def fake_call(domain, service, payload, blocking=False, return_response=False):
        calls["payload"] = payload
        return _forecast_solar_response()

    engine._hass.services.async_call = fake_call
    await engine.async_refresh_forecasts(now=T0)

    assert calls["payload"] == {"config_entry": "fs_entry", "resolution": "hourly"}
    # wh_period 1000..6000 Wh become 1..6 kWh per calendar hour.
    assert [(at - T0) // timedelta(hours=1) for at, _kwh in engine.pv_hours] == [1, 2, 3, 4, 5, 6]
    assert [round(kwh, 2) for _at, kwh in engine.pv_hours] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


async def test_pv_forecast_falls_back_when_the_entity_is_not_forecast_solar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import homeassistant.helpers.entity_registry as er_stub

    data = {"power_consumption_hp": 2.0}
    engine, _advisor, _analytics, _coordinator = _engine(data, pv_forecast_entity="sensor.pv_forecast")
    # Registry knows the entity but it belongs to another integration.
    monkeypatch.setattr(er_stub, "async_get", lambda hass: _FakeEntityRegistry(None))
    service_called = False

    async def fake_call(*args: Any, **kwargs: Any) -> None:
        nonlocal service_called
        service_called = True

    engine._hass.services.async_call = fake_call
    # The state carries a Solcast-style attribute list the fallback parses.
    engine._hass.states.get = MagicMock(
        return_value=SimpleNamespace(
            attributes={"forecast": [{"period_start": _iso(_hour(i)), "pv_estimate": 1.0} for i in range(1, 4)]}
        )
    )
    await engine.async_refresh_forecasts(now=T0)

    assert service_called is False
    assert len(engine.pv_hours) == 3


async def test_pv_forecast_service_errors_fall_back_silently(monkeypatch: pytest.MonkeyPatch) -> None:
    import homeassistant.helpers.entity_registry as er_stub

    data = {"power_consumption_hp": 2.0}
    engine, _advisor, _analytics, _coordinator = _engine(data, pv_forecast_entity="sensor.power_production_now")
    monkeypatch.setattr(er_stub, "async_get", lambda hass: _FakeEntityRegistry(_FakeForecastSolarEntry("fs_entry")))

    async def failing_call(*args: Any, **kwargs: Any) -> None:
        raise OSError("service down")

    engine._hass.services.async_call = failing_call
    engine._hass.states.get = MagicMock(return_value=None)
    await engine.async_refresh_forecasts(now=T0)

    assert engine.pv_hours == []
