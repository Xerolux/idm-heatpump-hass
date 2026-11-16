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


def _charge_coordinator(top: float, demand: int) -> object:
    """A Navigator-10 style plant with charge hysteresis registers (#713)."""
    return _coordinator(
        {
            "dhw_temp_top": top,
            "dhw_setpoint": 55.0,
            "dhw_charge_on_temp": 46,
            "dhw_charge_off_temp": 50,
            "dhw_demand": demand,
        }
    )


def test_dhw_target_resting_tank_is_not_a_fault():
    """Normal cooling between charges must not flag (#713: setpoint 55, off 50)."""
    # The reporter's own snapshot: charge correctly completed, demand idle.
    assert module._dhw_not_reaching_target(_charge_coordinator(51.36, demand=0), None) is False
    # Cooling below the switch-off temperature on the way to the next charge.
    assert module._dhw_not_reaching_target(_charge_coordinator(48.9, demand=0), None) is False
    # Even resting inside the hysteresis band is normal between charges.
    assert module._dhw_not_reaching_target(_charge_coordinator(45.5, demand=0), None) is False


def test_dhw_target_stuck_charge_flags_only_after_grace_period():
    analysis = SimpleNamespace(dhw_charge_minutes=lambda: 95.0, dhw_consecutive_charge_failures=0)
    # A charge stuck for over 90 minutes below the switch-on temperature flags.
    assert module._dhw_not_reaching_target(_charge_coordinator(45.2, demand=1), analysis) is True
    # A freshly started charge is granted its grace period.
    fresh = SimpleNamespace(dhw_charge_minutes=lambda: 30.0, dhw_consecutive_charge_failures=0)
    assert module._dhw_not_reaching_target(_charge_coordinator(45.2, demand=1), fresh) is False
    # A long charge that lifted the tank above the switch-on temperature is healthy.
    lifted = SimpleNamespace(dhw_charge_minutes=lambda: 120.0, dhw_consecutive_charge_failures=0)
    assert module._dhw_not_reaching_target(_charge_coordinator(47.5, demand=1), lifted) is False
    # Without an analysis duration the stuck rule stays conservative.
    assert module._dhw_not_reaching_target(_charge_coordinator(45.2, demand=1), None) is False


def test_dhw_target_flags_after_repeated_failed_charges():
    failed = SimpleNamespace(dhw_charge_minutes=lambda: 0.0, dhw_consecutive_charge_failures=2)
    single = SimpleNamespace(dhw_charge_minutes=lambda: 0.0, dhw_consecutive_charge_failures=1)
    # Two consecutive charges that missed the switch-off temperature and a tank
    # still below the switch-on temperature: a real problem.
    assert module._dhw_not_reaching_target(_charge_coordinator(44.5, demand=0), failed) is True
    assert module._dhw_not_reaching_target(_charge_coordinator(44.5, demand=1), failed) is True
    # One failed charge alone is not enough evidence.
    assert module._dhw_not_reaching_target(_charge_coordinator(44.5, demand=0), single) is False
    # A tank that recovered above the switch-on temperature is fine again.
    assert module._dhw_not_reaching_target(_charge_coordinator(47.0, demand=0), failed) is False


def test_dhw_target_unknown_without_demand_signal():
    coordinator = _coordinator(
        {
            "dhw_temp_top": 45.0,
            "dhw_setpoint": 55.0,
            "dhw_charge_on_temp": 46,
            "dhw_charge_off_temp": 50,
        }
    )
    # Without the demand bit a resting tank and a failing charge are indistinguishable.
    assert module._dhw_not_reaching_target(coordinator, None) is None


def test_implausible_sensor_check_ignores_normal_sentinels():
    assert module._implausible_sensor(_coordinator({"hp_flow_temp": -1.0}), None) is False
    assert module._implausible_sensor(_coordinator({"hp_flow_temp": 150.0}), None) is True


def test_implausible_sensor_check_ignores_unwired_sensor_memory():
    """Uninitialized memory from an unwired sensor is "not present", not a fault (#668)."""
    plant = {
        "hc_a_room_temp": -327.22,
        "outdoor_temp": 4.8,
        "hp_flow_temp": 34.1,
        "dhw_temp_top": 48.0,
    }
    assert module._implausible_sensor(_coordinator(plant), None) is False
    assert module._implausible_sensor(_coordinator({"hc_a_room_temp": -327.68}), None) is False
    # A reading that is merely out of band — not uninitialized memory — still trips.
    assert module._implausible_sensor(_coordinator({"outdoor_temp": -60.0}), None) is True


def test_long_defrost_check_is_conservative():
    analysis = SimpleNamespace(current_defrost_minutes=lambda: 46.0)
    assert module._long_defrost(_coordinator({}), analysis) is True
    analysis.current_defrost_minutes = lambda: 45.0
    assert module._long_defrost(_coordinator({}), analysis) is False


def test_shortening_cycle_anomaly_requires_history_and_own_baseline() -> None:
    analysis = SimpleNamespace(supports_compressor=True, completed_cycle_durations=[1800.0] * 15 + [300.0] * 5)
    assert module._shortening_cycles(_coordinator({}), analysis) is True
    analysis.completed_cycle_durations = [1800.0] * 15 + [1200.0] * 5
    assert module._shortening_cycles(_coordinator({}), analysis) is False
    analysis.completed_cycle_durations = [300.0] * 10
    assert module._shortening_cycles(_coordinator({}), analysis) is None
    analysis.completed_cycle_durations = [0.0] * 20
    assert module._shortening_cycles(_coordinator({}), analysis) is None
    analysis.supports_compressor = False
    assert module._shortening_cycles(_coordinator({}), analysis) is None
    assert module._shortening_cycles(_coordinator({}), None) is None


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
