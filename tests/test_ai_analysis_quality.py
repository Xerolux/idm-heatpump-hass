"""Regression scenarios for evidence-based advisor analyses and explanations."""

from __future__ import annotations

import math
import time
from datetime import timedelta
from types import SimpleNamespace

import pytest

from custom_components.idm_heatpump import ai_advisor as ai
from custom_components.idm_heatpump import health_monitor
from custom_components.idm_heatpump.advisor_engine import _bucket_hourly_kwh, _cop_domain
from custom_components.idm_heatpump.advisor_inputs import room_temperature_celsius
from custom_components.idm_heatpump.advisor_operation_reason import compose_operation_reason
from custom_components.idm_heatpump.ai_cloud import cloud_facts
from custom_components.idm_heatpump.ai_learning import LearningHistory
from tests.test_advisor_engine import T0, _engine
from tests.test_ai_advisor import manager


def _record(at: float, electric: float, thermal: float) -> dict:
    return {
        "at": at,
        "connected": True,
        "total_electrical_kwh": electric,
        "total_thermal_kwh": thermal,
        "outdoor_temp": 5.0,
    }


def test_period_sorts_and_deduplicates_without_double_counting() -> None:
    first, second, third = _record(0, 0, 0), _record(300, 1, 3), _record(600, 2, 6)
    result = ai.summarize_period([second, first, third, second], 0, 600)
    assert result["samples"] == 3
    assert result["valid_energy_intervals"] == 2
    assert result["energy_counter_coverage_percent"] == 100
    assert result["electrical_kwh_observed"] == 2
    assert result["unobserved_energy_hours"] == 0


@pytest.mark.parametrize("coverage", [0, 40, 89.9])
def test_partial_periods_do_not_produce_consumption_trends(coverage: float) -> None:
    period = ai.summarize_period([_record(0, 0, 0), _record(600, 2, 6)], 0, 600)
    previous = {**period, "energy_counter_coverage_percent": coverage}
    assert ai.compare_periods(period, previous) == {"status": "insufficient_coverage"}


def test_comparison_preserves_zero_and_refuses_zero_baselines_and_unequal_windows() -> None:
    previous = ai.summarize_period([_record(0, 0, 0), _record(600, 2, 6)], 0, 600)
    period = {**previous, "electrical_kwh_observed": 0.0, "cop_observed": None}
    result = ai.compare_periods(period, previous)
    assert result["electrical_kwh_observed_change_percent"] == -100
    assert result["cop_observed_change_percent"] is None
    assert ai.compare_periods(previous, period)["electrical_kwh_observed_change_percent"] is None
    assert ai.compare_periods(period, {**previous, "requested_hours": 24})["status"] == "different_windows"


def test_unused_temperature_never_enters_ai_report() -> None:
    obj = manager()
    obj._coordinator.data["dhw_temp_top"] = -1.0
    obj._coordinator.unused_registers = {"dhw_temp_top"}
    assert obj.build_facts("health", time.time())["current"]["dhw_temp_top"] is None


@pytest.mark.parametrize("language,needle", [("en", "Coverage is incomplete"), ("de", "Datenbasis ist lückenhaft")])
def test_report_leads_with_limits_and_explains_observation_time(language: str, needle: str) -> None:
    facts = manager().build_facts("efficiency", time.time())
    report = ai.fact_report(facts, language)
    assert needle in report[:700]
    assert ("Unobserved time" if language == "en" else "Nicht erfasste Zeit") in report
    assert len(report) < 6000


def test_report_purposes_have_distinct_focus() -> None:
    obj = manager()
    texts = [ai.fact_report(obj.build_facts(kind, time.time()), "en").split("\n\n")[1] for kind in ai.REPORT_TYPES]
    assert len(set(texts)) == 4


def test_cloud_comparison_remains_numeric_and_guard_understands_its_units() -> None:
    facts = manager().build_facts("daily", time.time())
    facts["comparison"] = {"electrical_kwh_observed_change_percent": -12.3, "private_text": "SECRET"}
    projected = cloud_facts(facts)
    assert "SECRET" not in str(projected)
    assert projected["comparison"]["electrical_kwh_observed_change_percent"] == -12.3
    assert ai.report_quality("Electrical energy changed by -12.3%.", facts)["unsupported_percentages"] == []
    assert ai.report_quality("Electrical energy changed by -12.3%.", facts)["unsupported_numbers"] == []


@pytest.mark.parametrize(
    "raw,unit,expected", [("68", "°F", 20), ("293.15", "K", 20), ("20", "°C", 20), ("20", None, 20)]
)
def test_mapped_room_temperature_is_normalized(raw: str, unit: str | None, expected: float) -> None:
    state = SimpleNamespace(state=raw, attributes={"unit_of_measurement": unit})
    assert room_temperature_celsius(state) == pytest.approx(expected)
    engine, advisor, _, _ = _engine({"hc_a_room_temp": 25})
    engine._room_temp_entities = {"a": "sensor.room"}
    advisor._room_temp_entities = {"a": "sensor.room"}
    engine._hass.states.get.return_value = state
    advisor._hass.states.get.return_value = state
    assert engine._room_temp_for("a", {}) == pytest.approx(expected)
    assert advisor._watched_value("hc_a_room_temp", {}) == pytest.approx(expected)


def test_wrong_unit_and_unavailable_sources_never_fall_back_to_register() -> None:
    engine, _, _, _ = _engine({"hc_a_room_temp": 25})
    engine._room_temp_entities = {"a": "sensor.room"}
    engine._hass.states.get.return_value = SimpleNamespace(state="22", attributes={"unit_of_measurement": "%"})
    assert engine._room_temp_for("a", {"hc_a_room_temp": 25}) is None
    assert math.isnan(room_temperature_celsius(engine._hass.states.get.return_value))


def test_failed_updates_break_learning_intervals() -> None:
    engine, _, analytics, coordinator = _engine({"power_consumption_hp": 2, "hc_a_room_temp": 21})
    coordinator.last_update_success = False
    engine._last_sample_at = T0
    engine._compressor_on = True
    engine.observe(T0)
    assert engine._last_sample_at is None and engine._compressor_on is None
    assert analytics.metric_today_samples("compressor_starts", T0) == 0


@pytest.mark.parametrize("mode", [3, 6, 17, 20, -15, -12, 1.5, True])
def test_ambiguous_modes_do_not_train_per_mode_models(mode: object) -> None:
    assert _cop_domain(mode) == "total"


def test_legacy_baselines_do_not_invent_zero_dispersion() -> None:
    history = LearningHistory()
    now = 20000 * 86400
    history.load({f"{day}:1:1": [2, 6, 21600, 72] for day in (19997, 19998, 19999)}, now)
    result = history.comparison({"at": now, "mode": 1, "outdoor_temp": 5})
    assert result["baseline_cop"] == 3
    assert "baseline_std" not in result and "deviation_z" not in result


def test_missing_cop_is_unknown_instead_of_a_passed_check() -> None:
    assert health_monitor._low_cop(SimpleNamespace(data={"outdoor_temp": 5}), None) is None


@pytest.mark.parametrize("language", ["en", "de"])
def test_operating_reason_follows_mode_and_controller_evidence(language: str) -> None:
    data = {"hp_operating_mode": 1, "power_consumption_hp": 2, "dhw_temp_top": 40, "dhw_setpoint": 50}
    result = compose_operation_reason(data, demand_reason=None, language=language)
    assert result.label == ("Heating" if language == "en" else "Heizen")
    data.update(hc_a_flow_temp=25, hc_a_setpoint_flow_temp=35)
    result = compose_operation_reason(data, demand_reason="Zeitprogramm", language=language)
    assert result.label == ("Schedule" if language == "en" else "Zeitprogramm")
    result = compose_operation_reason(
        {**data, "hp_operating_mode": 4, "dhw_temp_top": 55}, demand_reason=None, language=language
    )
    assert ("exceeded" if language == "en" else "überschritten") in result.explanation


def test_missing_flow_does_not_claim_a_measured_temperature_shortfall() -> None:
    result = compose_operation_reason({"hp_operating_mode": 1, "hc_a_setpoint_flow_temp": 35}, demand_reason=None)
    assert "unavailable" in result.explanation
    assert "below" not in result.explanation


def test_forecast_energy_is_split_at_hour_boundaries_and_duplicates_are_not_extra_energy() -> None:
    at = T0 + timedelta(minutes=45)
    result = _bucket_hourly_kwh([(at, 4), (at, 4), (at + timedelta(minutes=30), 4)])
    assert result == [(T0, 1.0), (T0 + timedelta(hours=1), 3.0)]


def test_similar_coverage_required_for_period_comparison() -> None:
    period = ai.summarize_period([_record(0, 0, 0), _record(600, 2, 6)], 0, 600)
    assert ai.compare_periods(period, {**period, "energy_counter_coverage_percent": 95}) == {
        "status": "different_coverage"
    }


@pytest.mark.parametrize("connected,outdoor,reason", [(False, 5, "stale_input"), (True, None, "missing_temperature")])
def test_learning_distinguishes_missing_evidence_from_idle(connected: bool, outdoor: float | None, reason: str) -> None:
    result = LearningHistory().comparison(
        {"at": 20000 * 86400, "connected": connected, "mode": 1, "outdoor_temp": outdoor}
    )
    assert result["status_reason"] == reason


@pytest.mark.parametrize("offsets", [[0, 1, 2], [0] * 24, list(range(12)) + list(range(13, 25))])
def test_heat_demand_never_extrapolates_a_short_or_gapped_forecast(monkeypatch, offsets: list[int]) -> None:
    engine, _, analytics, _ = _engine({"hc_a_room_temp": 21})
    monkeypatch.setattr(type(analytics), "heat_loss_w_per_k", property(lambda self: 200.0))
    engine._weather_hours = [(T0 + timedelta(hours=index), 5.0) for index in offsets]
    engine._compute_plan(T0)
    assert engine.plan is None


def test_warm_forecast_hours_cannot_cancel_cold_hour_heat_demand(monkeypatch) -> None:
    engine, _, analytics, _ = _engine({"hc_a_room_temp": 21})
    monkeypatch.setattr(type(analytics), "heat_loss_w_per_k", property(lambda self: 200.0))
    engine._weather_hours = [(T0 + timedelta(hours=index), 11.0 if index < 12 else 31.0) for index in range(24)]
    engine._compute_plan(T0)
    assert engine.plan["predicted_heat_demand_kwh"] == 24.0


def test_stale_health_data_is_unknown_but_connection_faults_remain_visible() -> None:
    from unittest.mock import MagicMock

    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test"
    coordinator.data = {"dhw_temp_top": 30, "dhw_setpoint": 50}
    coordinator.last_update_success = False
    coordinator.poll_statistics.consecutive_failures = 1
    report = health_monitor.health_report_entities(coordinator)[0]
    assert report.native_value is None
    assert "health_low_cop" in report.extra_state_attributes["unknown_checks"]
    entities = health_monitor.health_binary_entities(coordinator)
    assert all(entity.is_on is None for entity in entities[1:])
    coordinator.poll_statistics.consecutive_failures = 3
    assert report.native_value == "problem"


@pytest.mark.parametrize("language", ["de", "en"])
def test_assist_distinguishes_unknown_faults_stale_readings_and_subzero_outdoor(language: str) -> None:
    from custom_components.idm_heatpump.assist_agent import IdmHeatpumpConversationEntity
    from tests.test_assist_agent import _coordinator

    coordinator = _coordinator({"outdoor_temp": -5.5})
    agent = IdmHeatpumpConversationEntity(coordinator, None)
    assert "-5" in agent._answer("temperature", language)
    unknown = agent._answer("status", language, utterance="Fehler error")
    assert ("nicht lesbar" if language == "de" else "unavailable") in unknown
    coordinator.last_update_success = False
    answer = agent._answer("temperature", language)
    assert "-5" not in answer
    assert ("fehlgeschlagen" if language == "de" else "failed") in answer


def test_assist_energy_uses_available_thermal_register_and_labels_instantaneous_cop() -> None:
    from custom_components.idm_heatpump.assist_agent import IdmHeatpumpConversationEntity
    from tests.test_assist_agent import _coordinator

    agent = IdmHeatpumpConversationEntity(_coordinator({"power_consumption_hp": 2, "current_power": 6}), None)
    answer = agent._answer("energy", "en")
    assert "thermal power: 6 kW" in answer
    assert "Instantaneous COP: 3" in answer
