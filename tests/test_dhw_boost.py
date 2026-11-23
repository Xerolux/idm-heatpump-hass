"""Tests for the restart-safe IDM DHW boost."""

from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump import dhw_boost as module
from custom_components.idm_heatpump.dhw_boost import DhwBoostError, DhwBoostManager


@contextmanager
def _raises_boost_error(translation_key: str):
    """Assert a boost error carrying one translation key.

    The translation key is what Home Assistant shows the user; the message
    beside it is a developer string whose wording is free to change.
    """
    with pytest.raises(DhwBoostError) as excinfo:
        yield
    assert excinfo.value.translation_key == translation_key


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
    def __init__(self, events=None, onetime=False) -> None:
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
        if onetime:
            # Navigator 2.0/10/Pro shared map: GLT register 1713.
            self._registers["demand_onetime_dhw"] = RegisterDef(
                address=1713,
                datatype=DataType.BOOL,
                name="demand_onetime_dhw",
                writable=True,
            )
            self.data["demand_onetime_dhw"] = 0
        self.fail_write_name = None
        self.fail_write_once = False
        self._listener = None
        self.dhw_boost_manager = None

    def get_register(self, name):
        return self._registers.get(name)

    def attach_dhw_boost_manager(self, manager):
        self.dhw_boost_manager = manager

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


async def _manager(monkeypatch, *, loaded=None, events=None, onetime=False):
    store = FakeStore(loaded=loaded, events=events)
    monkeypatch.setattr(module, "Store", lambda *args, **kwargs: store)
    coordinator = FakeCoordinator(events=events, onetime=onetime)
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

    with _raises_boost_error("dhw_boost_start_failed_rolled_back"):
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

    with _raises_boost_error("dhw_boost_target_out_of_range"):
        await manager.async_start(target_temperature=80, timeout_minutes=30)
    with _raises_boost_error("dhw_boost_timeout_out_of_range"):
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

    with _raises_boost_error("dhw_boost_no_entry"):
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

    with _raises_boost_error("dhw_boost_already_active"):
        await manager.async_start(target_temperature=60, timeout_minutes=30)

    await manager.async_cancel()


@pytest.mark.asyncio
async def test_start_requires_the_control_registers(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator._registers.pop("system_mode")

    with _raises_boost_error("dhw_boost_unsupported"):
        await manager.async_start(target_temperature=60, timeout_minutes=30)


@pytest.mark.asyncio
async def test_start_requires_a_current_temperature(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator.data["dhw_temp_top"] = None

    with _raises_boost_error("dhw_boost_no_current_temp"):
        await manager.async_start(target_temperature=60, timeout_minutes=30)


@pytest.mark.asyncio
async def test_start_is_a_no_op_when_the_target_is_already_reached(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator.data["dhw_temp_top"] = 61.0

    await manager.async_start(target_temperature=60, timeout_minutes=30)

    assert manager.active is False
    assert manager.last_reason == "target_already_reached"
    assert coordinator.data["system_mode"] == 1


@pytest.mark.parametrize("temperature", [-327.33, -999.0])
@pytest.mark.asyncio
async def test_start_refuses_an_uninitialized_dhw_sensor(monkeypatch, temperature) -> None:
    """An unwired sensor answers with memory garbage (<= -300 C), not with -1 (#668).

    0.28.3 only knew the -1 sentinel, so the garbage passed as "colder than
    the target" and the energy manager could start an automatic charge on it.
    """
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator.data["dhw_temp_top"] = temperature

    with _raises_boost_error("dhw_boost_no_current_temp"):
        await manager.async_start(target_temperature=60, timeout_minutes=30)

    assert manager.active is False


@pytest.mark.asyncio
async def test_uninitialized_dhw_sensor_does_not_end_an_active_boost(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=58, timeout_minutes=30)
    coordinator.data["dhw_temp_top"] = -327.33

    await manager._async_evaluate()

    assert manager.active is True
    assert manager.status == "active"


@pytest.mark.asyncio
async def test_start_requires_a_known_previous_state(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator.data["system_mode"] = None

    with _raises_boost_error("dhw_boost_no_previous_state"):
        await manager.async_start(target_temperature=60, timeout_minutes=30)


@pytest.mark.asyncio
async def test_start_reports_an_incomplete_rollback(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator.fail_write_name = "system_mode"

    with _raises_boost_error("dhw_boost_start_failed_rollback_incomplete"):
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

    with _raises_boost_error("dhw_boost_invalid_recovery_state"):
        await manager._async_restore_locked("manual_cancel")

    assert manager.status == "recovery_invalid"
    assert manager.active is False


@pytest.mark.asyncio
async def test_writes_require_a_writable_register(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)

    with _raises_boost_error("dhw_boost_register_not_writable"):
        await manager._async_write("dhw_temp_top", 60)

    coordinator._registers.pop("dhw_setpoint")
    with _raises_boost_error("dhw_boost_register_not_writable"):
        await manager._async_write("dhw_setpoint", 60)


@pytest.mark.asyncio
async def test_target_validation_needs_the_setpoint_register(monkeypatch) -> None:
    manager, coordinator, _store = await _manager(monkeypatch)

    with _raises_boost_error("dhw_boost_invalid_target"):
        manager._validated_target("not a number")

    coordinator._registers.pop("dhw_setpoint")
    with _raises_boost_error("dhw_boost_invalid_target"):
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


def _active_manager(write_error):
    """A running boost whose next enforcement write raises ``write_error``."""
    coordinator = FakeCoordinator()

    async def _raise(register, value):
        raise write_error

    coordinator.async_write_register = _raise
    manager = DhwBoostManager(coordinator)
    manager.active = True
    manager.status = "active"
    manager.target_temperature = 60
    manager.deadline = datetime.now(UTC) + timedelta(minutes=30)
    # The controller still reports the pre-boost values, so enforcement runs.
    coordinator.data = {"dhw_temp_top": 45.0, "dhw_setpoint": 48, "system_mode": 1}
    manager._async_save = AsyncMock()
    return manager


@pytest.mark.asyncio
async def test_enforcement_treats_write_pacing_as_wait_not_failure():
    """The controller reports the old value for a poll or two after a write.

    Both the coordinator's per-register cooldown and the API's EEPROM write
    interval refuse a second write in that window. Counting those as failures
    flipped the boost status and wrote the store on every poll, with a warning
    each time.
    """
    from homeassistant.exceptions import HomeAssistantError

    cooldown = HomeAssistantError()
    cooldown.translation_key = "write_cooldown_active"
    manager = _active_manager(cooldown)

    await manager._async_evaluate()

    assert manager.status == "active", "pacing is not an enforcement failure"
    manager._async_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_enforcement_treats_the_eeprom_interval_as_wait_too():
    manager = _active_manager(RuntimeError("EEPROM register written too recently; try again in 42s"))

    await manager._async_evaluate()

    assert manager.status == "active"
    manager._async_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_enforcement_still_reports_a_real_refusal():
    manager = _active_manager(RuntimeError("controller refused"))

    await manager._async_evaluate()

    assert manager.status == "enforcement_failed"
    manager._async_save.assert_awaited()


@pytest.mark.parametrize("reason", ["target", "cancel", "timeout", "unload"])
async def test_automatic_boost_never_writes_system_mode(monkeypatch, reason):
    manager, coordinator, store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=30, preserve_system_mode=True)
    assert coordinator.data["system_mode"] == 1
    assert store.saved[-1]["preserve_system_mode"] is True
    assert manager.state_attributes["priority"] == "dhw_setpoint_only_until_end_or_cancel"
    # Even an external mode change during the boost belongs to the controller.
    coordinator.data["system_mode"] = 2
    coordinator.data["dhw_setpoint"] = 48
    await manager._async_evaluate()
    assert coordinator.data["dhw_setpoint"] == 60
    assert coordinator.data["system_mode"] == 2
    if reason == "target":
        coordinator.data["dhw_temp_top"] = 60
        await manager._async_evaluate()
    elif reason == "cancel":
        await manager.async_cancel()
    elif reason == "timeout":
        manager.deadline = datetime.now(UTC) - timedelta(seconds=1)
        await manager._async_evaluate()
    else:
        await manager.async_shutdown()
    assert not manager.active
    assert coordinator.data["dhw_setpoint"] == 48
    assert coordinator.data["system_mode"] == 2
    assert not any(event[:2] == ("write", "system_mode") for event in coordinator.events)
    await manager.async_shutdown()


async def test_automatic_boost_restart_restores_only_setpoint(monkeypatch):
    loaded = {
        "active": True,
        "preserve_system_mode": True,
        "previous_mode": 4,
        "previous_setpoint": 48,
        "target_temperature": 60,
        "timeout_minutes": 30,
    }
    manager, coordinator, _store = await _manager(monkeypatch, loaded=loaded)
    assert not manager.active
    assert coordinator.data["system_mode"] == 1
    assert not any(event[:2] == ("write", "system_mode") for event in coordinator.events)
    await manager.async_shutdown()


async def test_automatic_boost_start_failure_never_restores_system_mode(monkeypatch):
    manager, coordinator, _store = await _manager(monkeypatch)
    coordinator.fail_write_name = "dhw_setpoint"
    coordinator.fail_write_once = True
    with pytest.raises(DhwBoostError):
        await manager.async_start(target_temperature=60, timeout_minutes=30, preserve_system_mode=True)
    assert not any(event[:2] == ("write", "system_mode") for event in coordinator.events)
    await manager.async_shutdown()


@pytest.mark.parametrize("reason", ["target", "cancel", "timeout", "unload"])
async def test_onetime_demand_boost_triggers_a_charge_without_mode_switch(monkeypatch, reason):
    """With register 1713 the boost commands one charge and owns only the setpoint.

    Reported against a Navigator 10 (issue #719): switching to hot-water-only
    stopped the heating pumps without starting a DHW charge, while the native
    app triggers a one-time demand and stays in Automatic.
    """
    events = []
    manager, coordinator, store = await _manager(monkeypatch, events=events, onetime=True)
    await manager.async_start(target_temperature=60, timeout_minutes=30)

    assert ("write", "dhw_setpoint", 60) in events
    assert ("write", "demand_onetime_dhw", True) in events
    assert not any(event[:2] == ("write", "system_mode") for event in events)
    assert coordinator.data["system_mode"] == 1
    assert store.saved[-1]["uses_onetime_demand"] is True
    assert store.saved[-1]["preserve_system_mode"] is True
    assert manager.state_attributes["priority"] == "dhw_setpoint_and_onetime_demand_until_end_or_cancel"
    assert manager.state_attributes["uses_onetime_demand"] is True

    if reason == "target":
        coordinator.data["dhw_temp_top"] = 60
        await manager._async_evaluate()
    elif reason == "cancel":
        await manager.async_cancel()
    elif reason == "timeout":
        manager.deadline = datetime.now(UTC) - timedelta(seconds=1)
        await manager._async_evaluate()
    else:
        await manager.async_shutdown()
    assert not manager.active
    assert coordinator.data["dhw_setpoint"] == 48
    assert coordinator.data["system_mode"] == 1
    # The momentary command is never cleared by the integration.
    assert not any(event[:2] == ("write", "demand_onetime_dhw") and event[2] is False for event in events)
    assert not any(event[:2] == ("write", "system_mode") for event in events)
    await manager.async_shutdown()


async def test_onetime_demand_boost_enforces_only_the_setpoint(monkeypatch):
    events = []
    manager, coordinator, _store = await _manager(monkeypatch, events=events, onetime=True)
    await manager.async_start(target_temperature=60, timeout_minutes=30)
    events.clear()

    # External changes during the boost: the mode belongs to the controller,
    # the self-clearing demand bit is not re-triggered, the setpoint is owned.
    coordinator.data["system_mode"] = 2
    coordinator.data["dhw_setpoint"] = 48
    coordinator.data["demand_onetime_dhw"] = 0
    await manager._async_evaluate()

    assert coordinator.data["dhw_setpoint"] == 60
    assert coordinator.data["system_mode"] == 2
    assert ("write", "demand_onetime_dhw", True) not in events
    await manager.async_shutdown()


async def test_onetime_demand_boost_start_failure_never_switches_the_mode(monkeypatch):
    manager, coordinator, _store = await _manager(monkeypatch, onetime=True)
    coordinator.fail_write_name = "demand_onetime_dhw"
    coordinator.fail_write_once = True
    with pytest.raises(DhwBoostError):
        await manager.async_start(target_temperature=60, timeout_minutes=30)
    assert not manager.active
    assert coordinator.data["dhw_setpoint"] == 48
    assert coordinator.data["system_mode"] == 1
    assert not any(event[:2] == ("write", "system_mode") for event in coordinator.events)
    await manager.async_shutdown()


async def test_onetime_demand_boost_recovery_never_writes_mode_or_demand(monkeypatch):
    loaded = {
        "active": True,
        "preserve_system_mode": True,
        "uses_onetime_demand": True,
        "previous_mode": 1,
        "previous_setpoint": 48,
        "target_temperature": 60,
        "timeout_minutes": 30,
    }
    manager, coordinator, _store = await _manager(monkeypatch, loaded=loaded, onetime=True)
    assert not manager.active
    assert coordinator.data["dhw_setpoint"] == 48
    assert coordinator.data["system_mode"] == 1
    assert not any(event[:2] == ("write", "system_mode") for event in coordinator.events)
    assert not any(event[:2] == ("write", "demand_onetime_dhw") for event in coordinator.events)
    await manager.async_shutdown()


@pytest.mark.parametrize(
    "register_setup",
    ["not_writable", "unused"],
)
async def test_unusable_onetime_register_falls_back_to_the_mode_switch(monkeypatch, register_setup):
    events = []
    store = FakeStore(events=events)
    monkeypatch.setattr(module, "Store", lambda *args, **kwargs: store)
    coordinator = FakeCoordinator(events=events, onetime=True)
    if register_setup == "not_writable":
        register = coordinator.get_register("demand_onetime_dhw")
        coordinator._registers["demand_onetime_dhw"] = RegisterDef(
            address=register.address,
            datatype=DataType.BOOL,
            name="demand_onetime_dhw",
        )
    else:
        coordinator.unused_registers = frozenset({"demand_onetime_dhw"})
    manager = DhwBoostManager(coordinator)
    await manager.async_setup()

    await manager.async_start(target_temperature=60, timeout_minutes=30)

    assert ("write", "system_mode", 4) in events
    assert not any(event[:2] == ("write", "demand_onetime_dhw") for event in events)
    assert manager.state_attributes["priority"] == "dhw_setpoint_and_hot_water_only_until_end_or_cancel"
    await manager.async_shutdown()


@pytest.mark.asyncio
async def test_shutdown_cancels_a_pending_evaluation_task(monkeypatch) -> None:
    """A scheduled evaluation must not outlive the shutdown that restores."""
    manager, _coordinator, _store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=30)

    manager._handle_coordinator_update()
    pending = manager._evaluation_task
    assert pending is not None

    await manager.async_shutdown()

    assert manager._evaluation_task is None
    with pytest.raises(asyncio.CancelledError):
        await pending


@pytest.mark.asyncio
async def test_evaluation_returns_while_the_boost_is_not_active(monkeypatch) -> None:
    """Evaluation on an idle manager takes the lock and stops at the guard."""
    manager, coordinator, _store = await _manager(monkeypatch)

    await manager._async_evaluate()

    assert manager.active is False
    # No enforcement write may happen without an active boost.
    assert not any(event[:2] == ("write", "system_mode") for event in coordinator.events)


@pytest.mark.asyncio
async def test_enforcement_reraises_home_assistant_errors_outside_pacing():
    """A HomeAssistantError that is not write pacing is a real failure."""
    from homeassistant.exceptions import HomeAssistantError

    manager = _active_manager(HomeAssistantError(translation_key="idm_write_failed"))

    await manager._async_evaluate()

    assert manager.status == "enforcement_failed"
    manager._async_save.assert_awaited()


async def test_onetime_boost_cancel_waits_for_eeprom_then_logs_setpoint_write(monkeypatch, caplog):
    manager, coordinator, _store = await _manager(monkeypatch, onetime=True)
    coordinator.data["dhw_setpoint"] = 52
    await manager.async_start(target_temperature=60)
    coordinator.events.clear()
    write = coordinator.async_write_register
    remaining = iter([42.2, 10.4])

    async def paced(register, value):
        seconds = next(remaining, None)
        if seconds is not None:
            raise ValueError(
                f"EEPROM-sensitive register '{register.name}' was written too recently (try again in {seconds}s)"
            )
        await write(register, value)

    coordinator.async_write_register = paced
    caplog.set_level(logging.DEBUG, logger=module.__name__)
    await manager.async_cancel()
    for expected_setpoint in (60, 52):
        coordinator._listener()
        await manager._evaluation_task
        assert coordinator.data["dhw_setpoint"] == expected_setpoint

    assert not manager.active
    assert [event for event in coordinator.events if event[0] == "write"] == [("write", "dhw_setpoint", 52)]
    assert [record.getMessage() for record in caplog.records if record.name == module.__name__] == [
        "DHW boost waiting for the dhw_setpoint write interval (manual_cancel)",
        "DHW boost wrote the previous setpoint of 52 °C (manual_cancel)",
    ]
    await manager.async_shutdown()


@pytest.mark.parametrize("paced_register", ["dhw_setpoint", "system_mode"])
async def test_early_cancel_resumes_only_unfinished_writes(monkeypatch, paced_register):
    from homeassistant.exceptions import HomeAssistantError

    manager, coordinator, store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=60, timeout_minutes=30)
    write = coordinator.async_write_register
    cooldown = HomeAssistantError()
    cooldown.translation_key = "write_cooldown_active"

    async def paced(register, value):
        if register.name == paced_register:
            raise cooldown
        await write(register, value)

    coordinator.events.clear()
    coordinator.async_write_register = paced
    await manager.async_cancel()
    assert manager.active and manager.status == "recovery_required"
    saves = len(store.saved)
    await manager._async_evaluate()
    assert len(store.saved) == saves
    coordinator.async_write_register = write
    await manager._async_evaluate()
    assert not manager.active
    assert [event for event in coordinator.events if event[0] == "write"] == [
        ("write", "dhw_setpoint", 48),
        ("write", "system_mode", 1),
    ]


@pytest.mark.asyncio
async def test_restart_after_partial_restoration_preserves_new_setpoint(monkeypatch):
    loaded = {
        "active": True,
        "previous_mode": 1,
        "previous_setpoint": 48,
        "setpoint_restored": True,
    }
    events = []
    manager, _, store = await _manager(monkeypatch, loaded=loaded, events=events)
    assert [event for event in events if event[0] == "write"] == [("write", "system_mode", 1)]
    assert not manager.active
    assert store.saved[-1]["active"] is False
