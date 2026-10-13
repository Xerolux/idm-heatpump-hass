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


def _coordinator():
    return SimpleNamespace(
        config_entry=SimpleNamespace(entry_id="test"),
        data={"dhw_temp_top": 45.0, "dhw_setpoint": 48, "system_mode": 1},
        last_update_success=True,
        register_required_registers=lambda *_: lambda: None,
    )


async def test_surplus_is_derived_from_production_and_consumption():
    manager = module.EnergyManager(
        _hass({"sensor.pv": _state(4), "sensor.house": _state(1)}),
        _coordinator(),
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
        _coordinator(),
        module.EnergyManagerConfig(sources={"pv_production": "sensor.pv"}),
    )

    assert manager._surplus_kw() is None
    assert manager._ready() is False


async def test_configured_surplus_failure_does_not_fall_back_to_gross_production():
    manager = module.EnergyManager(
        _hass({"sensor.net": _state("unavailable"), "sensor.pv": _state(5), "sensor.house": _state(1)}),
        _coordinator(),
        module.EnergyManagerConfig(
            sources={"pv_surplus": "sensor.net", "pv_production": "sensor.pv", "house_consumption": "sensor.house"}
        ),
    )
    assert manager._ready() is False


@pytest.mark.parametrize("pv,house", [(-1, 0), (5, -1)])
async def test_negative_production_or_consumption_cannot_trigger_boost(pv, house):
    manager = module.EnergyManager(
        _hass({"sensor.pv": _state(pv), "sensor.house": _state(house)}),
        _coordinator(),
        module.EnergyManagerConfig(sources={"pv_production": "sensor.pv", "house_consumption": "sensor.house"}),
    )
    assert manager._surplus_kw() is None
    assert manager._ready() is False


async def test_periodic_task_survives_transient_evaluation_failure(monkeypatch):
    hass = _hass({})
    hass.async_create_task = asyncio.create_task
    manager = module.EnergyManager(hass, _coordinator(), module.EnergyManagerConfig(sources={}))
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
    boost = SimpleNamespace(active=False)

    async def activate(**_kwargs):
        boost.active = True

    boost.async_start = AsyncMock(side_effect=activate)
    monkeypatch.setattr(module, "async_get_dhw_boost_manager", AsyncMock(return_value=boost))
    manager = module.EnergyManager(
        _hass({"sensor.surplus": _state(3), "sensor.soc": _state(80, "%")}),
        _coordinator(),
        module.EnergyManagerConfig(
            sources={"pv_surplus": "sensor.surplus", "battery_soc": "sensor.soc"},
            minimum_surplus_kw=2,
            minimum_battery_soc=50,
            target_temperature=57,
            timeout_minutes=45,
        ),
    )

    assert await manager.async_evaluate_once() is True
    boost.async_start.assert_awaited_once_with(target_temperature=57, timeout_minutes=45, preserve_system_mode=True)
    assert await manager.async_evaluate_once() is False
    boost.async_start.assert_awaited_once()


async def test_battery_below_threshold_does_not_write(monkeypatch):
    get_manager = AsyncMock()
    monkeypatch.setattr(module, "async_get_dhw_boost_manager", get_manager)
    manager = module.EnergyManager(
        _hass({"sensor.surplus": _state(3), "sensor.soc": _state(10, "%")}),
        _coordinator(),
        module.EnergyManagerConfig(
            sources={"pv_surplus": "sensor.surplus", "battery_soc": "sensor.soc"},
            minimum_surplus_kw=2,
            minimum_battery_soc=20,
        ),
    )

    assert await manager.async_evaluate_once() is False
    get_manager.return_value.async_start.assert_not_called()


@pytest.mark.parametrize(
    ("value", "unit"),
    [("unknown", "kW"), ("nan", "kW"), (2, None), (1, "kW")],
)
async def test_insufficient_or_invalid_surplus_never_requests_boost(monkeypatch, value, unit):
    get_manager = AsyncMock()
    monkeypatch.setattr(module, "async_get_dhw_boost_manager", get_manager)
    manager = module.EnergyManager(
        _hass({"sensor.surplus": _state(value, unit)}),
        _coordinator(),
        module.EnergyManagerConfig(sources={"pv_surplus": "sensor.surplus"}, minimum_surplus_kw=2),
    )
    assert await manager.async_evaluate_once() is False
    get_manager.return_value.async_start.assert_not_called()


async def test_existing_boost_and_boost_error_fail_closed(monkeypatch):
    boost = SimpleNamespace(active=True, async_start=AsyncMock())
    monkeypatch.setattr(module, "async_get_dhw_boost_manager", AsyncMock(return_value=boost))
    manager = module.EnergyManager(
        _hass({"sensor.surplus": _state(3)}),
        _coordinator(),
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
    manager = module.EnergyManager(hass, _coordinator(), module.EnergyManagerConfig(sources={}))
    manager.async_evaluate_once = AsyncMock(return_value=False)
    first = manager.start()
    assert manager.start() is first
    await asyncio.sleep(0)
    manager.async_evaluate_once.assert_awaited_once()
    await manager.async_stop()
    assert manager._task is None
    await manager.async_stop()


async def _automatic_manager(monkeypatch, **config):
    boost = SimpleNamespace(active=False)

    async def activate(**_kwargs):
        boost.active = True

    boost.async_start = AsyncMock(side_effect=activate)
    monkeypatch.setattr(module, "async_get_dhw_boost_manager", AsyncMock(return_value=boost))
    manager = module.EnergyManager(
        _hass({"sensor.surplus": _state(3)}),
        _coordinator(),
        module.EnergyManagerConfig(sources={"pv_surplus": "sensor.surplus"}, **config),
    )
    return manager, boost


@pytest.mark.parametrize("temperature", [50.01, 54.9, 55, None, float("nan"), float("inf"), True])
async def test_small_temperature_drops_and_invalid_samples_never_restart(monkeypatch, temperature):
    manager, boost = await _automatic_manager(monkeypatch)
    manager._coordinator.data["dhw_temp_top"] = temperature
    assert await manager.async_evaluate_once() is False
    boost.async_start.assert_not_awaited()


@pytest.mark.parametrize("mode", [0, 2, 3, 5, None])
async def test_automatic_boost_respects_modes_without_normal_dhw(monkeypatch, mode):
    manager, boost = await _automatic_manager(monkeypatch)
    manager._coordinator.data["system_mode"] = mode
    assert await manager.async_evaluate_once() is False
    boost.async_start.assert_not_awaited()


async def test_failed_poll_never_starts_from_cached_temperature(monkeypatch):
    manager, boost = await _automatic_manager(monkeypatch)
    manager._coordinator.last_update_success = False
    assert await manager.async_evaluate_once() is False
    boost.async_start.assert_not_awaited()


async def test_full_cooldown_after_long_boost_even_without_sun(monkeypatch):
    from datetime import UTC, datetime, timedelta

    now = datetime(2026, 10, 12, tzinfo=UTC)
    monkeypatch.setattr(module, "_utcnow", lambda: now)
    manager, boost = await _automatic_manager(monkeypatch)
    manager._coordinator.data["dhw_temp_top"] = 50
    assert await manager.async_evaluate_once() is True
    now += timedelta(minutes=90)
    boost.active = False
    manager._hass.states.get = lambda _: _state(0)
    assert await manager.async_evaluate_once() is False
    manager._hass.states.get = lambda _: _state(3)
    now += timedelta(minutes=59)
    assert await manager.async_evaluate_once() is False
    now += timedelta(minutes=1)
    assert await manager.async_evaluate_once() is True
    assert boost.async_start.await_count == 2


async def test_restart_retains_pending_boost_and_completed_cooldown(monkeypatch):
    from datetime import UTC, datetime, timedelta

    now = datetime(2026, 10, 12, tzinfo=UTC)
    monkeypatch.setattr(module, "_utcnow", lambda: now)
    manager, _boost = await _automatic_manager(monkeypatch)
    assert await manager.async_evaluate_once() is True
    snapshot = manager._store.data.copy()
    restarted, _boost = await _automatic_manager(monkeypatch)
    restarted._store.data = snapshot
    assert await restarted.async_evaluate_once() is False
    assert restarted._store.data["waiting_for_end"] is False
    again, _boost = await _automatic_manager(monkeypatch)
    again._store.data = restarted._store.data.copy()
    now += timedelta(minutes=59)
    assert await again.async_evaluate_once() is False
    now += timedelta(minutes=1)
    assert await again.async_evaluate_once() is True


async def test_storage_failure_prevents_device_action(monkeypatch):
    manager, boost = await _automatic_manager(monkeypatch)
    manager._store.async_save = AsyncMock(side_effect=OSError("disk full"))
    with pytest.raises(OSError):
        await manager.async_evaluate_once()
    boost.async_start.assert_not_awaited()


async def test_noop_start_is_not_reported_as_success(monkeypatch):
    manager, boost = await _automatic_manager(monkeypatch)
    boost.async_start.side_effect = None
    assert await manager.async_evaluate_once() is False


async def test_register_demand_survives_disabled_raw_entities_and_is_released():
    from unittest.mock import MagicMock

    hass = _hass({})
    hass.async_create_task = asyncio.create_task
    coordinator = _coordinator()
    release = MagicMock()
    coordinator.register_required_registers = MagicMock(return_value=release)
    manager = module.EnergyManager(hass, coordinator, module.EnergyManagerConfig(sources={}))
    manager.async_evaluate_once = AsyncMock(return_value=False)
    manager.start()
    manager.start()
    coordinator.register_required_registers.assert_called_once_with(
        "energy_manager", {"dhw_temp_top", "dhw_setpoint", "system_mode"}
    )
    await manager.async_stop()
    release.assert_called_once()


async def test_storage_load_failure_never_requests_boost(monkeypatch):
    manager, boost = await _automatic_manager(monkeypatch)
    manager._store.async_load = AsyncMock(side_effect=OSError("storage unavailable"))
    with pytest.raises(OSError):
        await manager.async_evaluate_once()
    boost.async_start.assert_not_awaited()
    assert not manager._loaded


async def test_concurrent_evaluations_start_only_one_boost(monkeypatch):
    manager, boost = await _automatic_manager(monkeypatch)
    assert await asyncio.gather(manager.async_evaluate_once(), manager.async_evaluate_once()) == [True, False]
    boost.async_start.assert_awaited_once()


async def test_pending_boost_waits_for_recovery_before_cooldown(monkeypatch):
    manager, boost = await _automatic_manager(monkeypatch)
    manager._store.data = {"waiting_for_end": True}
    boost.active = True
    assert await manager.async_evaluate_once() is False
    assert manager._blocked_until is None
    boost.async_start.assert_not_awaited()


async def test_stop_waits_for_an_in_flight_evaluation(monkeypatch):
    """Stopping must not cancel an evaluation that is already running.

    Cancelling the loop task mid-write aborts the Modbus transaction in
    flight (#493 race class). async_stop holds the evaluation lock so a
    started evaluation — including its boost start — finishes first.
    """
    from unittest.mock import MagicMock as _MagicMock

    hass = _hass({})
    hass.async_create_task = asyncio.create_task
    manager = module.EnergyManager(hass, _coordinator(), module.EnergyManagerConfig(sources={}))
    started = asyncio.Event()
    release = asyncio.Event()
    finished = asyncio.Event()
    boost = _MagicMock()
    boost.active = False

    async def slow_get_manager(_coordinator):
        started.set()
        await release.wait()
        finished.set()
        return boost

    monkeypatch.setattr(module, "async_get_dhw_boost_manager", slow_get_manager)
    task = manager.start()
    stop_task: asyncio.Task[None] | None = None
    try:
        await asyncio.wait_for(started.wait(), 2)
        stop_task = asyncio.get_running_loop().create_task(manager.async_stop())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not stop_task.done(), "async_stop returned while an evaluation was still in flight"
        release.set()
        await asyncio.wait_for(stop_task, 2)
        assert finished.is_set()
        assert manager._task is None
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        if stop_task is not None:
            await asyncio.gather(stop_task, return_exceptions=True)


def test_unit_and_number_helpers_reject_unusable_states() -> None:
    assert module._unit(SimpleNamespace(attributes=None)) is None
    assert module._unit(SimpleNamespace(attributes={"unit_of_measurement": 3.5})) is None
    assert module._number(SimpleNamespace(state="garbage", attributes={})) is None
    assert module._number(None) is None


async def test_soc_source_below_minimum_or_invalid_blocks_readiness() -> None:
    hass = _hass(
        {
            "sensor.surplus": _state(5),
            "sensor.low_soc": _state(10, "%"),
            "sensor.bad_soc": _state("unavailable", "%"),
        }
    )
    coordinator = _coordinator()
    below = module.EnergyManager(
        hass,
        coordinator,
        module.EnergyManagerConfig(sources={"pv_surplus": "sensor.surplus", "battery_soc": "sensor.low_soc"}),
    )
    invalid = module.EnergyManager(
        hass,
        coordinator,
        module.EnergyManagerConfig(sources={"pv_surplus": "sensor.surplus", "battery_soc": "sensor.bad_soc"}),
    )

    assert below._ready() is False
    assert invalid._ready() is False


async def test_start_spawns_a_background_task_bootstrap_does_not_wait_for(monkeypatch):
    """A foreground create_task loop makes HA's startup wrap-up time out (#493)."""
    from unittest.mock import MagicMock as _MagicMock

    created = []

    class _HassBackground:
        states = SimpleNamespace(get={}.get)

        @staticmethod
        def async_create_background_task(hass, coro, name=None):
            task = asyncio.ensure_future(coro)
            created.append(name)
            return task

    monkeypatch.setattr(module, "async_get_dhw_boost_manager", AsyncMock(return_value=_MagicMock(active=False)))
    manager = module.EnergyManager(_HassBackground(), _coordinator(), module.EnergyManagerConfig(sources={}))

    task = manager.start()

    assert created and created[0].startswith("idm_heatpump_energy_manager")
    assert not task.done()
    await manager.async_stop()
    assert manager._task is None
