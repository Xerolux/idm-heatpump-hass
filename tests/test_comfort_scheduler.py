"""Offline tests for the opt-in comfort schedule and its write safeguards."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.idm_heatpump import comfort_scheduler as module


def _scheduler(value: object = 20.0, *, start: str = "06:00", end: str = "22:00"):
    hass = MagicMock()
    hass.async_create_task.side_effect = asyncio.create_task
    coordinator = MagicMock()
    coordinator.data = {"hc_a_room_setpoint_heat_normal": value}
    coordinator.get_register.return_value = SimpleNamespace(name="hc_a_room_setpoint_heat_normal")
    return module.ComfortScheduler(hass, coordinator, "A", start, end, 22.0), coordinator


def _at(hour: int) -> datetime:
    return datetime(2026, 9, 17, hour, tzinfo=UTC)


def test_time_parsing_and_overnight_window() -> None:
    assert module._parse_time("bad", time(6)) == time(6)
    schedule, _ = _scheduler(start="22:00", end="06:00")
    assert schedule.register_name == "hc_a_room_setpoint_heat_normal"
    assert schedule._in_window(time(23))
    assert schedule._in_window(time(2))
    assert not schedule._in_window(time(12))
    equal, _ = _scheduler(start="06:00", end="06:00")
    assert not equal._in_window(time(6))


def test_multiple_windows_validate_circuits_and_overlap() -> None:
    windows = module.parse_schedule_rows("a,06:00,09:00,21\nd,22:00,05:00,20", {"a", "d"})
    assert len(windows) == 2
    assert windows[1].circuit == "d"
    for invalid in (
        "b,06:00,09:00,21",
        "a,06:00,09:00",
        "a,06:00,09:00,inf",
        "a,06:00,06:00,21",
        "a,06:00,09:00,31",
        "a,06:00,09:00,21\na,08:00,10:00,22",
        "a,22:00,05:00,20\na,04:00,06:00,21",
        "a,06:00+02:00,09:00+02:00,21",
    ):
        with pytest.raises(ValueError):
            module.parse_schedule_rows(invalid, {"a", "d"})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), -1, True])
async def test_invalid_current_temperature_never_arms_restore(monkeypatch, value) -> None:
    write = AsyncMock()
    monkeypatch.setattr(module, "async_write_translated", write)
    schedule, _ = _scheduler(value)
    await schedule.async_evaluate_once(now=_at(7))
    write.assert_not_awaited()
    assert schedule._active is False


async def test_schedule_uses_home_assistant_timezone(monkeypatch) -> None:
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 17, 21, tzinfo=UTC)

        def astimezone(self, tz=None):
            # Make the simulated host timezone independent of the test runner.
            return super().astimezone(tz or timezone(timedelta(hours=2)))

    monkeypatch.setattr(module, "datetime", FixedDatetime)
    import homeassistant.util.dt as dt_util

    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(timezone(timedelta(hours=-4))))
    write = AsyncMock()
    monkeypatch.setattr(module, "async_write_translated", write)
    schedule, _ = _scheduler()
    await schedule.async_evaluate_once()
    write.assert_awaited_once()
    assert write.await_args.args[2] == 22.0


async def test_adjacent_windows_change_target_then_restore(monkeypatch: pytest.MonkeyPatch) -> None:
    write = AsyncMock()
    monkeypatch.setattr(module, "async_write_translated", write)
    windows = module.parse_schedule_rows("a,06:00,09:00,21\na,09:00,12:00,22", {"a"})
    schedule, coordinator = _scheduler()
    schedule._windows = windows
    await schedule.async_evaluate_once(now=_at(7))
    coordinator.data[schedule.register_name] = 21.0
    await schedule.async_evaluate_once(now=_at(10))
    coordinator.data[schedule.register_name] = 22.0
    await schedule.async_evaluate_once(now=_at(13))
    assert [call.args[2] for call in write.await_args_list] == [21.0, 22.0, 20.0]


async def test_restart_recovers_pending_restore_without_overwriting_manual_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write = AsyncMock()
    monkeypatch.setattr(module, "async_write_translated", write)
    schedule, coordinator = _scheduler()
    await schedule.async_evaluate_once(now=_at(7))
    stored = schedule._store.data
    assert stored == {"active": True, "previous": 20.0, "target": 22.0}
    restarted = module.ComfortScheduler(schedule._hass, coordinator, "a", "06:00", "22:00", 22.0)
    restarted._store.data = stored
    await restarted.async_load()
    coordinator.data[restarted.register_name] = 22.0
    await restarted.async_evaluate_once(now=_at(23))
    assert write.await_args.args[2] == 20.0
    assert restarted._store.data["active"] is False

    restarted._store.data = stored
    await restarted.async_load()
    coordinator.data[restarted.register_name] = 21.0
    await restarted.async_evaluate_once(now=_at(23))
    assert write.await_count == 2


async def test_window_write_and_restore_respect_manual_change(monkeypatch: pytest.MonkeyPatch) -> None:
    write = AsyncMock()
    monkeypatch.setattr(module, "async_write_translated", write)
    schedule, coordinator = _scheduler()
    coordinator.data[schedule.register_name] = 20.0
    await schedule.async_evaluate_once(now=_at(7))
    assert write.await_count == 1
    assert write.await_args.args[2] == 22.0
    coordinator.data[schedule.register_name] = 22.0
    await schedule.async_evaluate_once(now=_at(23))
    assert write.await_count == 2
    assert write.await_args.args[2] == 20.0

    coordinator.data[schedule.register_name] = 20.0
    await schedule.async_evaluate_once(now=_at(7))
    coordinator.data[schedule.register_name] = 21.0
    await schedule.async_evaluate_once(now=_at(23))
    assert write.await_count == 3


async def test_missing_register_or_value_never_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    write = AsyncMock()
    monkeypatch.setattr(module, "async_write_translated", write)
    schedule, coordinator = _scheduler(value=None)
    await schedule.async_evaluate_once(now=_at(7))
    coordinator.data[schedule.register_name] = "bad"
    await schedule.async_evaluate_once(now=_at(7))
    coordinator.get_register.return_value = None
    await schedule.async_evaluate_once(now=_at(7))
    write.assert_not_awaited()


async def test_write_failure_clears_pending_restore(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "async_write_translated", AsyncMock(side_effect=OSError("offline")))
    schedule, _ = _scheduler()
    with pytest.raises(OSError):
        await schedule.async_evaluate_once(now=_at(7))
    assert schedule._active is False
    assert schedule._store.data["active"] is False


async def test_bad_persisted_state_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    schedule, _ = _scheduler()
    schedule._store.data = {"active": True, "previous": float("nan"), "target": 22.0}
    await schedule.async_load()
    assert schedule._active is False
    schedule._store.data = {"active": True, "previous": 20.0, "target": 22.0}
    schedule._store.async_load = AsyncMock(side_effect=OSError("store offline"))
    await schedule.async_load()
    assert schedule._active is False


async def test_start_and_stop_cancel_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    schedule, coordinator = _scheduler()
    schedule.async_evaluate_once = AsyncMock()
    schedule.start()
    await asyncio.sleep(0)
    assert schedule.async_evaluate_once.await_count == 1
    coordinator.register_required_registers.assert_called_once_with("comfort_schedule_a", {schedule.register_name})
    await schedule.async_stop()
    assert schedule._task is None
    coordinator.register_required_registers.return_value.assert_called_once_with()

    async def fail_once() -> None:
        raise RuntimeError("offline")

    monkeypatch.setattr(schedule, "async_evaluate_once", fail_once)
    schedule.start()
    await asyncio.sleep(0)
    await schedule.async_stop()
