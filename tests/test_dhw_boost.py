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


@pytest.mark.asyncio
async def test_helpers_reject_unusable_values() -> None:
    """Persisted state and coordinator values arrive untrusted."""
    assert module._parse_datetime(None) is None
    assert module._parse_datetime("not-a-timestamp") is None
    naive = module._parse_datetime("2026-01-01T10:00:00")
    assert naive is not None and naive.tzinfo is UTC
    assert module._finite_number(True) is None
    assert module._finite_number("45") is None
    assert module._finite_number(float("inf")) is None
    assert DhwBoostManager._safe_int(True) is None
    assert DhwBoostManager._safe_int("nope") is None
    assert DhwBoostManager._safe_int("7") == 7


def test_manager_requires_a_config_entry() -> None:
    coordinator = FakeCoordinator()
    coordinator.config_entry = None

    with pytest.raises(DhwBoostError, match="Konfigurationseintrag"):
        DhwBoostManager(coordinator)


@pytest.mark.asyncio
async def test_defaults_are_exposed_for_the_service_schema(monkeypatch) -> None:
    manager, _coordinator, _store = await _manager(monkeypatch)

    assert manager.default_target_temperature == module._DEFAULT_TARGET
    assert manager.default_timeout_minutes == module._DEFAULT_TIMEOUT_MINUTES


@pytest.mark.asyncio
async def test_setup_runs_once_and_survives_an_unreadable_store(monkeypatch) -> None:
    class _BrokenStore(FakeStore):
        async def async_load(self):
            raise RuntimeError("store is corrupt")

    store = _BrokenStore()
    monkeypatch.setattr(module, "Store", lambda *args, **kwargs: store)
    manager = DhwBoostManager(FakeCoordinator())

    await manager.async_setup()
    await manager.async_setup()  # second call must not re-read the store

    assert manager.active is False


@pytest.mark.asyncio
async def test_startup_recovery_keeps_the_entry_loading_when_restore_fails(monkeypatch) -> None:
    loaded = {
        "active": True,
        "status": "active",
        "target_temperature": 60,
        "timeout_minutes": 30,
        "previous_mode": 2,
        "previous_setpoint": 47,
    }
    store = FakeStore(loaded=loaded)
    monkeypatch.setattr(module, "Store", lambda *args, **kwargs: store)
    coordinator = FakeCoordinator()
    coordinator.fail_write_name = "dhw_setpoint"
    manager = DhwBoostManager(coordinator)

    await manager.async_setup()

    assert manager.status == "recovery_required"


@pytest.mark.asyncio
async def test_start_rejects_a_second_boost(monkeypatch) -> None:
    manager, _coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=30)

    with pytest.raises(DhwBoostError, match="bereits aktiv"):
        await manager.async_start(target_temperature=60, timeout_minutes=30)

    await manager.async_cancel()


@pytest.mark.asyncio
async def test_start_requires_the_control_registers(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator._registers.pop("system_mode")

    with pytest.raises(DhwBoostError, match="Systemmodusregister"):
        await manager.async_start(target_temperature=60, timeout_minutes=30)


@pytest.mark.asyncio
async def test_start_requires_a_current_temperature(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator.data["dhw_temp_top"] = None

    with pytest.raises(DhwBoostError, match="Warmwassertemperatur"):
        await manager.async_start(target_temperature=60, timeout_minutes=30)


@pytest.mark.asyncio
async def test_start_is_a_no_op_when_the_target_is_already_reached(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator.data["dhw_temp_top"] = 61.0

    await manager.async_start(target_temperature=60, timeout_minutes=30)

    assert manager.active is False
    assert manager.last_reason == "target_already_reached"
    assert coordinator.data["system_mode"] == 1


@pytest.mark.asyncio
async def test_start_requires_a_known_previous_state(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator.data["system_mode"] = None

    with pytest.raises(DhwBoostError, match="Systemmodus"):
        await manager.async_start(target_temperature=60, timeout_minutes=30)


@pytest.mark.asyncio
async def test_start_reports_an_incomplete_rollback(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator.fail_write_name = "system_mode"

    with pytest.raises(DhwBoostError, match="nicht vollständig"):
        await manager.async_start(target_temperature=60, timeout_minutes=30)

    assert manager.status == "recovery_required"


@pytest.mark.asyncio
async def test_cancel_without_an_active_boost_is_a_no_op(monkeypatch) -> None:
    manager, _coordinator, _store = await _manager(monkeypatch)

    await manager.async_cancel()

    assert manager.last_reason == "not_active"
    assert manager.status == "idle"


@pytest.mark.asyncio
async def test_shutdown_restores_an_active_boost(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=30)

    await manager.async_shutdown()

    assert coordinator.data["system_mode"] == 1
    assert coordinator.data["dhw_setpoint"] == 48


@pytest.mark.asyncio
async def test_shutdown_keeps_persisted_recovery_when_restore_fails(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=30)
    coordinator.fail_write_name = "dhw_setpoint"

    await manager.async_shutdown()

    assert manager.status == "recovery_required"


@pytest.mark.asyncio
async def test_coordinator_updates_schedule_one_evaluation(monkeypatch) -> None:
    manager, _coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=30)

    manager._handle_coordinator_update()
    task = manager._evaluation_task
    assert task is not None
    manager._handle_coordinator_update()  # a second update must not queue a task
    assert manager._evaluation_task is task
    await task

    await manager.async_cancel()


@pytest.mark.asyncio
async def test_evaluation_is_reentrancy_safe(monkeypatch) -> None:
    manager, _coordinator, _store = await _manager(monkeypatch)
    manager._evaluation_in_progress = True

    await manager._async_evaluate()

    assert manager._evaluation_in_progress is True
    manager._evaluation_in_progress = False


@pytest.mark.asyncio
async def test_evaluation_retries_a_pending_recovery(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=30)
    coordinator.fail_write_name = "dhw_setpoint"
    coordinator.fail_write_once = True
    manager.status = "recovery_required"

    await manager._async_evaluate()  # first retry fails and stays pending
    assert manager.status == "recovery_required"

    await manager._async_evaluate()  # the next update restores the state
    assert manager.active is False
    assert coordinator.data["system_mode"] == 1


@pytest.mark.asyncio
async def test_timeout_keeps_recovery_pending_when_the_write_fails(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=5)
    manager.deadline = datetime.now(UTC) - timedelta(seconds=1)
    coordinator.fail_write_name = "dhw_setpoint"

    await manager._async_evaluate()

    assert manager.status == "recovery_required"


@pytest.mark.asyncio
async def test_target_reached_keeps_recovery_pending_when_the_write_fails(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=58, timeout_minutes=30)
    coordinator.data["dhw_temp_top"] = 59.0
    coordinator.fail_write_name = "dhw_setpoint"

    await manager._async_evaluate()

    assert manager.status == "recovery_required"


@pytest.mark.asyncio
async def test_failed_reassertion_is_retried_on_the_next_update(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=30)
    coordinator.data["dhw_setpoint"] = 50
    coordinator.fail_write_name = "dhw_setpoint"
    coordinator.fail_write_once = True

    await manager._async_evaluate()

    assert manager.status == "enforcement_failed"
    coordinator.fail_write_name = None
    await manager._async_evaluate()
    assert coordinator.data["dhw_setpoint"] == 60
    await manager.async_cancel()


@pytest.mark.asyncio
async def test_deadline_watchdog_evaluates_when_it_expires(monkeypatch) -> None:
    manager, _coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=30)
    manager.deadline = datetime.now(UTC) - timedelta(seconds=1)

    await manager._async_timeout()

    assert manager.active is False
    assert manager.last_reason == "timeout"


@pytest.mark.asyncio
async def test_deadline_watchdog_without_a_deadline_returns(monkeypatch) -> None:
    manager, _coordinator, _store = await _manager(monkeypatch)
    manager.deadline = None

    await manager._async_timeout()

    assert manager.active is False


@pytest.mark.asyncio
async def test_restore_rejects_an_incomplete_snapshot(monkeypatch) -> None:
    manager, _coordinator, _store = await _manager(monkeypatch)
    manager.active = True
    manager.previous_mode = None
    manager.previous_setpoint = None

    with pytest.raises(DhwBoostError, match="unvollständig"):
        await manager._async_restore_locked("manual_cancel")

    assert manager.status == "recovery_invalid"
    assert manager.active is False


@pytest.mark.asyncio
async def test_writes_require_a_writable_register(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)

    with pytest.raises(DhwBoostError, match="nicht schreibbar"):
        await manager._async_write("dhw_temp_top", 60)

    coordinator._registers.pop("dhw_setpoint")
    with pytest.raises(DhwBoostError, match="nicht schreibbar"):
        await manager._async_write("dhw_setpoint", 60)


@pytest.mark.asyncio
async def test_target_validation_needs_the_setpoint_register(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)

    with pytest.raises(DhwBoostError, match="Zieltemperatur"):
        manager._validated_target("not a number")

    coordinator._registers.pop("dhw_setpoint")
    with pytest.raises(DhwBoostError, match="Zieltemperatur"):
        manager._validated_target(60)


@pytest.mark.asyncio
async def test_state_attributes_describe_the_current_boost(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=30)

    attributes = manager.state_attributes

    assert attributes["active"] is True
    assert attributes["target_temperature"] == 60
    assert attributes["current_temperature"] == coordinator.data["dhw_temp_top"]
    await manager.async_cancel()


@pytest.mark.asyncio
async def test_one_manager_is_reused_per_coordinator(monkeypatch) -> None:
    store = FakeStore()
    monkeypatch.setattr(module, "Store", lambda *args, **kwargs: store)
    coordinator = FakeCoordinator()

    first = await module.async_get_dhw_boost_manager(coordinator)
    second = await module.async_get_dhw_boost_manager(coordinator)

    assert first is second
