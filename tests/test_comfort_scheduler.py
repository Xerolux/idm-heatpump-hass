"""Offline tests for the opt-in comfort schedule and its write safeguards."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time
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


async def test_start_and_stop_cancel_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    schedule, _ = _scheduler()
    schedule.async_evaluate_once = AsyncMock()
    schedule.start()
    await asyncio.sleep(0)
    assert schedule.async_evaluate_once.await_count == 1
    await schedule.async_stop()
    assert schedule._task is None

    async def fail_once() -> None:
        raise RuntimeError("offline")

    monkeypatch.setattr(schedule, "async_evaluate_once", fail_once)
    schedule.start()
    await asyncio.sleep(0)
    await schedule.async_stop()
