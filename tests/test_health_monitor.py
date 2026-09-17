"""Tests for the optional read-only IDM health checks."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.idm_heatpump import health_monitor as module


def _coordinator(data, failures=0):
    return SimpleNamespace(
        data=data,
        poll_statistics=SimpleNamespace(consecutive_failures=failures),
    )


def test_communication_issue_after_three_consecutive_failures():
    assert module._communication(_coordinator({}, failures=3), None) is True
    assert module._communication(_coordinator({}, failures=2), None) is False


def test_low_cop_and_dhw_target_checks():
    coordinator = _coordinator(
        {
            "power_consumption_hp": 2.0,
            "thermal_power_flow_sensor": 3.0,
            "dhw_temp_top": 45.0,
            "dhw_setpoint": 55.0,
        }
    )
    assert module._low_cop(coordinator, None) is True
    assert module._dhw_not_reaching_target(coordinator, None) is True


def test_implausible_sensor_check_ignores_normal_sentinels():
    assert module._implausible_sensor(_coordinator({"hp_flow_temp": -1.0}), None) is False
    assert module._implausible_sensor(_coordinator({"hp_flow_temp": 150.0}), None) is True


def test_long_defrost_check_is_conservative():
    analysis = SimpleNamespace(current_defrost_minutes=lambda: 46.0)
    assert module._long_defrost(_coordinator({}), analysis) is True
    analysis.current_defrost_minutes = lambda: 45.0
    assert module._long_defrost(_coordinator({}), analysis) is False
