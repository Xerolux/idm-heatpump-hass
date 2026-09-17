"""Tests for the optional read-only IDM health checks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

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


def test_missing_inputs_are_conservative() -> None:
    empty = _coordinator({})
    assert module._many_starts(empty, None) is None
    assert module._low_cop(empty, None) is None
    assert module._dhw_not_reaching_target(empty, None) is None
    assert module._implausible_sensor(empty, None) is None
    assert module._long_defrost(empty, None) is None

    analysis = SimpleNamespace(supports_compressor=True, compressor_starts_last_hours=lambda _: 7)
    assert module._many_starts(empty, analysis) is True
    analysis.supports_compressor = False
    assert module._many_starts(empty, analysis) is None
    assert module._dhw_not_reaching_target(_coordinator({"dhw_temp_top": "bad", "dhw_setpoint": 50}), None) is None
    assert module._dhw_not_reaching_target(_coordinator({"dhw_temp_top": 50, "dhw_setpoint": -1}), None) is None
    assert module._implausible_sensor(_coordinator({"outdoor_temp": True, "room_temp": "bad"}), None) is False
    assert module._long_defrost(empty, SimpleNamespace(current_defrost_minutes=lambda: None)) is None


def test_health_entities_publish_problem_and_report_without_writes() -> None:
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "entry"
    coordinator.data = {"dhw_temp_top": 40, "dhw_setpoint": 50}
    coordinator.poll_statistics.consecutive_failures = 3
    coordinator.last_update_success = True
    coordinator.model_name = "Navigator 10"
    coordinator.firmware_version = "test"
    checks = module.health_binary_entities(coordinator)
    assert len(checks) == len(module.HEALTH_CHECKS)
    assert checks[0].is_on is True
    assert checks[0].available is True
    report = module.health_report_entities(coordinator)[0]
    assert report.native_value == "problem"
    attrs = report.extra_state_attributes
    assert "health_communication" in attrs["active_checks"]
    assert attrs["write_actions"] is False
    coordinator.async_write_register.assert_not_called()
