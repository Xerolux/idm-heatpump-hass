"""Tests for the optional read-only comfort recommendations."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.idm_heatpump.comfort_advisory import (
    ComfortAdvisorySensor,
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
    sensor = heating_curve_advisory(_coordinator({"hc_a_flow_temp": 30, "hc_a_setpoint_flow_temp": 35}), "a")
    assert sensor.native_value == "increase"

    sensor = heating_curve_advisory(_coordinator({"hc_a_flow_temp": 40, "hc_a_setpoint_flow_temp": 35}), "a")
    assert sensor.native_value == "decrease"

    sensor = heating_curve_advisory(_coordinator({"hc_a_flow_temp": 36, "hc_a_setpoint_flow_temp": 35}), "a")
    assert sensor.native_value == "stable"


async def test_weather_preheat_advisory_uses_actual_hourly_forecast() -> None:
    hass = MagicMock()
    hass.services.async_call = AsyncMock(
        return_value={
            "weather.home": {
                "forecast": [
                    {"datetime": "2026-09-17T14:00:00+00:00", "temperature": 2},
                ]
            }
        }
    )
    sensor = weather_preheat_advisory(hass, _coordinator({}), "weather.home", 5)
    await sensor.async_refresh_forecast(now=datetime(2026, 9, 17, 12, tzinfo=UTC))
    assert sensor.native_value == "preheat"
    hass.services.async_call.assert_awaited_with(
        "weather", "get_forecasts", {"entity_id": "weather.home", "type": "hourly"}, blocking=True, return_response=True
    )
    hass.services.async_call.return_value["weather.home"]["forecast"][0]["temperature"] = 12
    await sensor.async_refresh_forecast(now=datetime(2026, 9, 17, 12, tzinfo=UTC))
    assert sensor.native_value == "normal"
    assert not hass.services.call.called


async def test_recommendations_are_unavailable_without_trustworthy_readings() -> None:
    curve = heating_curve_advisory(_coordinator({"hc_a_flow_temp": "bad", "hc_a_setpoint_flow_temp": 35}), "a")
    assert curve.native_value is None
    assert curve.available is False
    unset_target = heating_curve_advisory(_coordinator({"hc_a_flow_temp": 30, "hc_a_setpoint_flow_temp": 0}), "a")
    assert unset_target.native_value is None
    weather = MagicMock()
    weather.services.async_call = AsyncMock(return_value={})
    adviser = weather_preheat_advisory(weather, _coordinator({}), "weather.home", 5)
    await adviser.async_refresh_forecast()
    assert adviser.native_value is None

    weather.services.async_call.return_value = {
        "weather.home": {
            "forecast": [
                {"datetime": "invalid", "temperature": 3},
                {"datetime": "2026-09-17T14:00:00+00:00", "temperature": "bad"},
            ]
        }
    }
    await adviser.async_refresh_forecast(now=datetime(2026, 9, 17, 12, tzinfo=UTC))
    assert adviser.native_value is None
    weather.services.async_call.side_effect = OSError("weather offline")
    await adviser.async_refresh_forecast()
    assert adviser.native_value is None


async def test_forecast_task_lifecycle_and_sparse_provider_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ComfortAdvisorySensor, "async_will_remove_from_hass", AsyncMock(), raising=False)
    hass = MagicMock()
    hass.async_create_task.side_effect = asyncio.create_task
    hass.services.async_call = AsyncMock(
        return_value={
            "weather.home": {
                "forecast": [
                    None,
                    {"datetime": "2026-09-17T14:00:00", "temperature": 2},
                    {"datetime": "2026-09-17T19:00:00+00:00", "temperature": 2},
                ]
            }
        }
    )
    adviser = weather_preheat_advisory(hass, _coordinator({}), "weather.home", 5)
    await adviser.async_refresh_forecast(now=datetime(2026, 9, 17, 12, tzinfo=UTC))
    assert adviser.native_value is None
    await adviser.async_added_to_hass()
    await asyncio.sleep(0)
    assert adviser._forecast_task is not None
    await adviser.async_will_remove_from_hass()
    assert adviser._forecast_task is None


async def test_forecast_task_starts_as_a_background_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The poll loop must not hold up Home Assistant's startup wrap-up."""
    monkeypatch.setattr(ComfortAdvisorySensor, "async_will_remove_from_hass", AsyncMock(), raising=False)
    created: list = []

    class _Entry:
        entry_id = "entry"

        @staticmethod
        def async_create_background_task(entry_self, hass, coro, name):
            created.append(name)
            return asyncio.create_task(coro)

    coordinator = _coordinator({})
    coordinator.config_entry = _Entry()
    hass = MagicMock()
    hass.async_create_task = MagicMock(side_effect=asyncio.create_task)
    adviser = weather_preheat_advisory(hass, coordinator, "weather.home", 5)
    adviser.async_write_ha_state = MagicMock()
    await adviser.async_added_to_hass()
    await asyncio.sleep(0)
    assert created and "weather_advisory" in created[0]
    hass.async_create_task.assert_not_called()
    await adviser.async_will_remove_from_hass()
    assert adviser._forecast_task is None


async def test_forecast_fetch_is_bounded_against_a_hanging_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.idm_heatpump import comfort_advisory

    monkeypatch.setattr(comfort_advisory, "_FORECAST_TIMEOUT", 0.05)

    async def hang(*args, **kwargs):
        await asyncio.sleep(30)

    hass = MagicMock()
    hass.services.async_call = AsyncMock(side_effect=hang)
    adviser = weather_preheat_advisory(hass, _coordinator({}), "weather.home", 5)
    await asyncio.wait_for(adviser.async_refresh_forecast(), timeout=2)
    assert adviser.native_value is None


async def test_forecast_loop_survives_an_unexpected_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list = []

    async def refresh():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("unexpected")
        raise asyncio.CancelledError

    adviser = weather_preheat_advisory(MagicMock(), _coordinator({}), "weather.home", 5)
    adviser.async_write_ha_state = MagicMock()
    monkeypatch.setattr(adviser, "async_refresh_forecast", refresh)

    async def no_sleep(_seconds):
        pass

    monkeypatch.setattr("custom_components.idm_heatpump.comfort_advisory.asyncio.sleep", no_sleep)
    with pytest.raises(asyncio.CancelledError):
        await adviser._poll_forecast()
    assert len(calls) == 2  # the loop reached its next cycle after the crash
