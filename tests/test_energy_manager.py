"""Tests for the optional, fail-closed energy manager."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

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


async def test_configured_surplus_failure_does_not_fall_back_to_gross_production():
    manager = module.EnergyManager(
        _hass({"sensor.net": _state("unavailable"), "sensor.pv": _state(5), "sensor.house": _state(1)}),
        object(),
        module.EnergyManagerConfig(
            sources={"pv_surplus": "sensor.net", "pv_production": "sensor.pv", "house_consumption": "sensor.house"}
        ),
    )
    assert manager._ready() is False


@pytest.mark.parametrize("pv,house", [(-1, 0), (5, -1)])
async def test_negative_production_or_consumption_cannot_trigger_boost(pv, house):
    manager = module.EnergyManager(
        _hass({"sensor.pv": _state(pv), "sensor.house": _state(house)}),
        object(),
        module.EnergyManagerConfig(sources={"pv_production": "sensor.pv", "house_consumption": "sensor.house"}),
    )
    assert manager._surplus_kw() is None
    assert manager._ready() is False


async def test_periodic_task_survives_transient_evaluation_failure(monkeypatch):
    hass = _hass({})
    hass.async_create_task = asyncio.create_task
    manager = module.EnergyManager(hass, object(), module.EnergyManagerConfig(sources={}))
    recovered = asyncio.Event()

    async def evaluate():
        if manager.async_evaluate_once.await_count == 1:
            raise OSError("temporary storage failure")
        recovered.set()
        return False

    original_sleep = asyncio.sleep

    async def short_sleep(_delay):
        await original_sleep(0)

    monkeypatch.setattr(module.asyncio, "sleep", short_sleep)
    manager.async_evaluate_once = AsyncMock(side_effect=evaluate)
    task = manager.start()
    try:
        await asyncio.wait_for(recovered.wait(), timeout=0.5)
        assert not task.done()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


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
    assert await manager.async_evaluate_once() is False
    boost.async_start.assert_awaited_once()


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


@pytest.mark.parametrize(
    ("value", "unit"),
    [("unknown", "kW"), ("nan", "kW"), (2, None), (1, "kW")],
)
async def test_insufficient_or_invalid_surplus_never_requests_boost(monkeypatch, value, unit):
    get_manager = AsyncMock()
    monkeypatch.setattr(module, "async_get_dhw_boost_manager", get_manager)
    manager = module.EnergyManager(
        _hass({"sensor.surplus": _state(value, unit)}),
        object(),
        module.EnergyManagerConfig(sources={"pv_surplus": "sensor.surplus"}, minimum_surplus_kw=2),
    )
    assert await manager.async_evaluate_once() is False
    get_manager.assert_not_awaited()


async def test_existing_boost_and_boost_error_fail_closed(monkeypatch):
    boost = SimpleNamespace(active=True, async_start=AsyncMock())
    monkeypatch.setattr(module, "async_get_dhw_boost_manager", AsyncMock(return_value=boost))
    manager = module.EnergyManager(
        _hass({"sensor.surplus": _state(3)}),
        object(),
        module.EnergyManagerConfig(sources={"pv_surplus": "sensor.surplus"}),
    )
    assert await manager.async_evaluate_once() is False
    boost.async_start.assert_not_awaited()
    boost.active = False
    boost.async_start.side_effect = module.DhwBoostError("refused")
    assert await manager.async_evaluate_once() is False


async def test_power_and_soc_units_fail_closed() -> None:
    assert module._power_kw(_state(1000, "W")) == 1
    assert module._power_kw(_state(0.001, "MW")) == 1
    assert module._power_kw(_state(1, "bad")) is None
    assert module._soc(_state(-1, "%")) is None
    assert module._soc(_state(101, "%")) is None
    assert module._soc(_state(80, None)) == 80
    assert module._number(None) is None


async def test_periodic_task_starts_once_and_stops() -> None:
    hass = _hass({})
    hass.async_create_task = asyncio.create_task
    manager = module.EnergyManager(hass, object(), module.EnergyManagerConfig(sources={}))
    manager.async_evaluate_once = AsyncMock(return_value=False)
    first = manager.start()
    assert manager.start() is first
    await asyncio.sleep(0)
    manager.async_evaluate_once.assert_awaited_once()
    await manager.async_stop()
    assert manager._task is None
    await manager.async_stop()
