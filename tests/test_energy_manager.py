"""Tests for the optional, fail-closed energy manager."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.idm_heatpump import energy_manager as module


def _state(value: object, unit: str | None = "kW") -> SimpleNamespace:
    attributes = {} if unit is None else {"unit_of_measurement": unit}
    return SimpleNamespace(state=value, attributes=attributes)


def _hass(states: dict[str, SimpleNamespace]):
    return SimpleNamespace(states=SimpleNamespace(get=states.get))


async def test_surplus_is_derived_from_production_and_consumption():
    manager = module.EnergyManager(
        _hass({"sensor.pv": _state(4), "sensor.house": _state(1)}),
        object(),
        module.EnergyManagerConfig(
            sources={"pv_production": "sensor.pv", "house_consumption": "sensor.house"},
            minimum_surplus_kw=2,
        ),
    )

    assert manager._surplus_kw() == 3
    assert manager._ready() is True


async def test_invalid_or_missing_power_source_fails_closed():
    manager = module.EnergyManager(
        _hass({"sensor.pv": _state("unknown")}),
        object(),
        module.EnergyManagerConfig(sources={"pv_production": "sensor.pv"}),
    )

    assert manager._surplus_kw() is None
    assert manager._ready() is False


async def test_ready_starts_existing_transactional_boost(monkeypatch):
    boost = SimpleNamespace(active=False, async_start=AsyncMock())
    monkeypatch.setattr(module, "async_get_dhw_boost_manager", AsyncMock(return_value=boost))
    manager = module.EnergyManager(
        _hass({"sensor.surplus": _state(3), "sensor.soc": _state(80, "%")}),
        object(),
        module.EnergyManagerConfig(
            sources={"pv_surplus": "sensor.surplus", "battery_soc": "sensor.soc"},
            minimum_surplus_kw=2,
            minimum_battery_soc=50,
            target_temperature=57,
            timeout_minutes=45,
        ),
    )

    assert await manager.async_evaluate_once() is True
    boost.async_start.assert_awaited_once_with(target_temperature=57, timeout_minutes=45)


async def test_battery_below_threshold_does_not_write(monkeypatch):
    get_manager = AsyncMock()
    monkeypatch.setattr(module, "async_get_dhw_boost_manager", get_manager)
    manager = module.EnergyManager(
        _hass({"sensor.surplus": _state(3), "sensor.soc": _state(10, "%")}),
        object(),
        module.EnergyManagerConfig(
            sources={"pv_surplus": "sensor.surplus", "battery_soc": "sensor.soc"},
            minimum_surplus_kw=2,
            minimum_battery_soc=20,
        ),
    )

    assert await manager.async_evaluate_once() is False
    get_manager.assert_not_awaited()
