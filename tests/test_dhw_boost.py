"""Tests for the restart-safe IDM DHW boost."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump import dhw_boost as module
from custom_components.idm_heatpump.dhw_boost import DhwBoostError, DhwBoostManager


class FakeStore:
    def __init__(self, loaded=None, events=None) -> None:
        self.loaded = loaded
        self.events = events if events is not None else []
        self.saved = []

    async def async_load(self):
        return self.loaded

    async def async_save(self, data):
        snapshot = dict(data)
        self.saved.append(snapshot)
        self.events.append(("save", snapshot["active"], snapshot["status"]))


class FakeCoordinator:
    def __init__(self, events=None) -> None:
        self.events = events if events is not None else []
        self.config_entry = MagicMock()
        self.config_entry.entry_id = "entry"
        self.hass = MagicMock()
        self.hass.async_create_task.side_effect = asyncio.create_task
        self.data = {
            "system_mode": 1,
            "dhw_setpoint": 48,
            "dhw_temp_top": 45.0,
        }
        self._registers = {
            "system_mode": RegisterDef(
                address=1005,
                datatype=DataType.UCHAR,
                name="system_mode",
                writable=True,
                min_val=0,
                max_val=5,
            ),
            "dhw_setpoint": RegisterDef(
                address=1032,
                datatype=DataType.UCHAR,
                name="dhw_setpoint",
                writable=True,
                min_val=35,
                max_val=65,
            ),
            "dhw_temp_top": RegisterDef(
                address=1014,
                datatype=DataType.FLOAT,
                name="dhw_temp_top",
            ),
        }
        self.fail_write_name = None
        self.fail_write_once = False
        self._listener = None

    def get_register(self, name):
        return self._registers.get(name)

    async def async_write_register(self, register, value):
        self.events.append(("write", register.name, value))
        if self.fail_write_name == register.name:
            self.fail_write_name = None if self.fail_write_once else register.name
            raise RuntimeError("write failed")
        self.data[register.name] = value

    def async_add_listener(self, listener):
        self._listener = listener
        return lambda: setattr(self, "_listener", None)

    def async_update_listeners(self):
        return None


async def _manager(monkeypatch, *, loaded=None, events=None):
    store = FakeStore(loaded=loaded, events=events)
    monkeypatch.setattr(module, "Store", lambda *args, **kwargs: store)
    coordinator = FakeCoordinator(events=events)
    manager = DhwBoostManager(coordinator)
    await manager.async_setup()
    return manager, coordinator, store


@pytest.mark.asyncio
async def test_start_persists_snapshot_before_first_write(monkeypatch) -> None:
    events = []
    manager, coordinator, store = await _manager(monkeypatch, events=events)

    await manager.async_start(target_temperature=60, timeout_minutes=30)

    assert events[0] == ("save", True, "starting")
    assert events[1] == ("write", "dhw_setpoint", 60)
    assert events[2] == ("write", "system_mode", 4)
    assert manager.active is True
    assert coordinator.data["system_mode"] == 4
    assert coordinator.data["dhw_setpoint"] == 60
    assert store.saved[-1]["previous_mode"] == 1
    assert store.saved[-1]["previous_setpoint"] == 48
    await manager.async_shutdown()


@pytest.mark.asyncio
async def test_cancel_restores_exact_previous_values(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=59, timeout_minutes=30)

    await manager.async_cancel()

    assert manager.active is False
    assert manager.last_reason == "manual_cancel"
    assert coordinator.data["system_mode"] == 1
    assert coordinator.data["dhw_setpoint"] == 48


@pytest.mark.asyncio
async def test_target_reached_restores_automatically(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=58, timeout_minutes=30)
    coordinator.data["dhw_temp_top"] = 58.2

    await manager._async_evaluate()

    assert manager.active is False
    assert manager.last_reason == "target_reached"
    assert coordinator.data["system_mode"] == 1
    assert coordinator.data["dhw_setpoint"] == 48


@pytest.mark.asyncio
async def test_expired_deadline_restores_as_timeout(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=5)
    manager.deadline = datetime.now(UTC) - timedelta(seconds=1)

    await manager._async_evaluate()

    assert manager.active is False
    assert manager.last_reason == "timeout"
    assert coordinator.data["system_mode"] == 1


@pytest.mark.asyncio
async def test_start_failure_rolls_back_partial_write(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator.fail_write_name = "system_mode"
    coordinator.fail_write_once = True

    with pytest.raises(DhwBoostError, match="vorherige Zustand wurde wiederhergestellt"):
        await manager.async_start(target_temperature=60, timeout_minutes=30)

    assert manager.active is False
    assert coordinator.data["dhw_setpoint"] == 48
    assert coordinator.data["system_mode"] == 1


@pytest.mark.asyncio
async def test_startup_recovery_restores_persisted_snapshot(monkeypatch) -> None:
    loaded = {
        "active": True,
        "status": "active",
        "target_temperature": 60,
        "timeout_minutes": 30,
        "started_at": datetime.now(UTC).isoformat(),
        "deadline": (datetime.now(UTC) + timedelta(minutes=20)).isoformat(),
        "previous_mode": 2,
        "previous_setpoint": 47,
    }
    store = FakeStore(loaded=loaded)
    monkeypatch.setattr(module, "Store", lambda *args, **kwargs: store)
    coordinator = FakeCoordinator()
    coordinator.data["system_mode"] = 4
    coordinator.data["dhw_setpoint"] = 60
    manager = DhwBoostManager(coordinator)

    await manager.async_setup()

    assert manager.active is False
    assert manager.last_reason == "startup_recovery"
    assert coordinator.data["system_mode"] == 2
    assert coordinator.data["dhw_setpoint"] == 47


@pytest.mark.asyncio
async def test_active_boost_reasserts_owned_mode_and_setpoint(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=30)
    coordinator.data["system_mode"] = 1
    coordinator.data["dhw_setpoint"] = 50

    await manager._async_evaluate()

    assert coordinator.data["system_mode"] == 4
    assert coordinator.data["dhw_setpoint"] == 60
    await manager.async_cancel()


@pytest.mark.asyncio
async def test_target_and_timeout_are_bounded(monkeypatch) -> None:
    manager, _coordinator, _store = await _manager(monkeypatch)

    with pytest.raises(DhwBoostError, match="Zieltemperatur"):
        await manager.async_start(target_temperature=80, timeout_minutes=30)
    with pytest.raises(DhwBoostError, match="Laufzeit"):
        await manager.async_start(target_temperature=60, timeout_minutes=1)
