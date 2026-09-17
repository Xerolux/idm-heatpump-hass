"""Tests for the optional read-only comfort recommendations."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.idm_heatpump.comfort_advisory import (
    heating_curve_advisory,
    weather_preheat_advisory,
)


def _coordinator(data: dict[str, float]) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.config_entry.entry_id = "entry"
    coordinator.last_update_success = True
    coordinator.energy_statistics = None
    return coordinator


def test_heating_curve_advisory_reports_direction() -> None:
    sensor = heating_curve_advisory(
        _coordinator({"hc_a_flow_temp": 30, "hc_a_setpoint_flow_temp": 35}), "a"
    )
    assert sensor.native_value == "increase"

    sensor = heating_curve_advisory(
        _coordinator({"hc_a_flow_temp": 40, "hc_a_setpoint_flow_temp": 35}), "a"
    )
    assert sensor.native_value == "decrease"

    sensor = heating_curve_advisory(
        _coordinator({"hc_a_flow_temp": 36, "hc_a_setpoint_flow_temp": 35}), "a"
    )
    assert sensor.native_value == "stable"


def test_weather_preheat_advisory_is_read_only() -> None:
    hass = MagicMock()
    hass.states.get.return_value = SimpleNamespace(state="sunny", attributes={"temperature": 2})
    sensor = weather_preheat_advisory(hass, _coordinator({}), "weather.home", 5)
    assert sensor.native_value == "preheat"
    hass.states.get.return_value = SimpleNamespace(state="sunny", attributes={"temperature": 12})
    assert sensor.native_value == "normal"
    assert not hass.services.call.called
