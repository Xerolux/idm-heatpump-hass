"""Tests for the operation-reason composer (why is the heat pump running)."""

from __future__ import annotations

from custom_components.idm_heatpump.advisor_operation_reason import compose_operation_reason


def test_returns_none_without_mode_and_power() -> None:
    assert compose_operation_reason({}, demand_reason=None) is None
    assert compose_operation_reason({"outdoor_temp": 5.0}, demand_reason=None) is None


def test_off() -> None:
    reason = compose_operation_reason({"hp_operating_mode": 0, "power_consumption_hp": 0.0}, demand_reason=None)
    assert reason is not None
    assert reason.label == "Off"
    assert reason.explanation == "The heat pump is not running."


def test_pv_surplus_wins_over_mode() -> None:
    reason = compose_operation_reason(
        {
            "hp_operating_mode": 4,
            "power_consumption_hp": 2.0,
            "pv_surplus": 1.2,
            "smart_grid_status": 4,
        },
        demand_reason=None,
    )
    assert reason is not None
    assert reason.label == "PV surplus"
    assert reason.details["pv_surplus_kw"] == 1.2


def test_hot_water_from_mode_and_from_temperature() -> None:
    by_mode = compose_operation_reason({"hp_operating_mode": 4, "power_consumption_hp": 1.5}, demand_reason=None)
    assert by_mode is not None and by_mode.label == "Hot water"
    by_temp = compose_operation_reason(
        {"hp_operating_mode": 1, "dhw_temp_top": 41.0, "dhw_setpoint": 48.0, "power_consumption_hp": 1.5},
        demand_reason=None,
    )
    assert by_temp is not None and by_temp.label == "Hot water"
    assert "7.0 K" in by_temp.explanation


def test_requesting_heating_circuit() -> None:
    reason = compose_operation_reason(
        {
            "hp_operating_mode": 1,
            "power_consumption_hp": 2.0,
            "hc_a_setpoint_flow_temp": 32.0,
            "hc_a_flow_temp": 28.7,
            "hc_a_room_temp": 21.5,
            "hc_a_room_setpoint_heat_normal": 22.0,
        },
        demand_reason=None,
        circuits=("a",),
    )
    assert reason is not None
    assert reason.label == "Heating circuit A"
    assert reason.details["flow_setpoint"] == 32.0
    assert "under target" in reason.explanation


def test_web_demand_reason_used_as_fallback() -> None:
    reason = compose_operation_reason({"hp_operating_mode": 1, "power_consumption_hp": 1.0}, demand_reason="Warmwasser")
    assert reason is not None
    assert reason.label == "Warmwasser"
    assert "demand reason" in reason.explanation


def test_mode_label_as_last_resort() -> None:
    reason = compose_operation_reason({"hp_operating_mode": 8, "power_consumption_hp": 1.0}, demand_reason=None)
    assert reason is not None
    assert reason.label == "Defrosting"
    assert reason.mode_label == "Defrosting"


def test_garbage_values_do_not_crash() -> None:
    reason = compose_operation_reason(
        {
            "hp_operating_mode": "x",
            "power_consumption_hp": float("nan"),
            "dhw_temp_top": None,
            "hc_a_flow_temp": "warm",
        },
        demand_reason=None,
        circuits=("a",),
    )
    assert reason is None  # neither mode nor a finite power reading
