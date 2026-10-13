"""Optional, conservative heating-circuit comfort scheduler."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Any, cast

from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import async_write_translated

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComfortWindow:
    circuit: str
    start: time
    end: time
    target: float


def parse_schedule_rows(value: str, circuits: set[str]) -> list[ComfortWindow]:
    """Parse bounded local-time windows; reject ambiguous overlap per circuit."""
    rows = [row.strip() for row in value.splitlines() if row.strip()]
    if len(rows) > 16:
        raise ValueError("at most 16 windows are supported")
    windows: list[ComfortWindow] = []
    occupied: set[tuple[str, int]] = set()
    for row in rows:
        parts = [part.strip() for part in row.split(",")]
        if len(parts) != 4 or parts[0].lower() not in circuits:
            raise ValueError("expected circuit,start,end,target")
        try:
            start = time.fromisoformat(parts[1])
            end = time.fromisoformat(parts[2])
            target = float(parts[3])
        except (TypeError, ValueError) as err:
            raise ValueError("invalid time or target") from err
        if (
            start.tzinfo is not None
            or end.tzinfo is not None
            or start.second
            or end.second
            or start.microsecond
            or end.microsecond
            or start == end
        ):
            raise ValueError("times must use HH:MM and differ")
        if not math.isfinite(target) or not 15.0 <= target <= 30.0:
            raise ValueError("target must be between 15 and 30 degrees")
        first = start.hour * 60 + start.minute
        last = end.hour * 60 + end.minute
        minutes = range(first, last) if first < last else (*range(first, 1440), *range(last))
        for minute in minutes:
            token = (parts[0].lower(), minute)
            if token in occupied:
                raise ValueError("overlapping windows on one circuit")
            occupied.add(token)
        windows.append(ComfortWindow(parts[0].lower(), start, end, target))
    return windows


def _parse_time(value: str, fallback: time) -> time:
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError):
        return fallback


class ComfortScheduler:
    """Apply one daily room-temperature comfort window to one heating circuit."""

    def __init__(
        self,
        hass: Any,
        coordinator: Any,
        circuit: str,
        start: str,
        end: str,
        target: float,
        *,
        windows: list[ComfortWindow] | None = None,
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._circuit = circuit.lower()
        self._start = _parse_time(start, time(6, 0))
        self._end = _parse_time(end, time(22, 0))
        self._target = float(target)
        self._windows = (
            windows if windows is not None else [ComfortWindow(self._circuit, self._start, self._end, self._target)]
        )
        self._task: asyncio.Task[None] | None = None
        self._release_register_demand: Callable[[], None] | None = None
        self._eval_lock = asyncio.Lock()
        self._active = False
        self._previous: float | None = None
        self._active_target: float | None = None
        entry_id = str(coordinator.config_entry.entry_id)
        self._store: Store[dict[str, float | bool | None]] = Store(
            hass, 1, f"{DOMAIN}.comfort_schedule.{entry_id}.{self._circuit}"
        )

    async def async_load(self) -> None:
        """Recover a pending restore without assuming an unobserved write."""
        try:
            saved = await self._store.async_load()
        except Exception:
            _LOGGER.warning("Could not load IDM comfort schedule restore state", exc_info=True)
            return
        if not isinstance(saved, dict) or saved.get("active") is not True:
            return
        previous = saved.get("previous")
        target = saved.get("target")
        if (
            isinstance(previous, (float, int))
            and isinstance(target, (float, int))
            and math.isfinite(previous)
            and math.isfinite(target)
        ):
            self._previous = float(previous)
            self._active_target = float(target)
            self._active = True

    async def _save_state(self) -> None:
        await self._store.async_save(
            {"active": self._active, "previous": self._previous, "target": self._active_target}
        )

    @property
    def register_name(self) -> str:
        return f"hc_{self._circuit}_room_setpoint_heat_normal"

    def _in_window(self, current: time) -> bool:
        return self._selected_target(current) is not None

    def _selected_target(self, current: time) -> float | None:
        for window in self._windows:
            if window.start == window.end:
                continue
            if (
                (window.start <= current < window.end)
                if window.start < window.end
                else (current >= window.start or current < window.end)
            ):
                return window.target
        return None

    def _current_value(self) -> float | None:
        value = (self._coordinator.data or {}).get(self.register_name)
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number != -1.0 else None

    async def async_evaluate_once(self, *, now: datetime | None = None) -> None:
        async with self._eval_lock:
            await self._async_evaluate_locked(now)

    async def _async_evaluate_locked(self, now: datetime | None) -> None:
        register = self._coordinator.get_register(self.register_name)
        if register is None:
            return
        current = self._current_value()
        if current is None:
            return
        target = self._selected_target((now or dt_util.as_local(datetime.now(UTC))).time())
        if target is not None and not self._active:
            self._previous = current
            self._active_target = target
            self._active = True
            await self._save_state()
            if abs(current - target) >= 0.01:
                try:
                    await async_write_translated(
                        self._coordinator,
                        register,
                        target,
                        action_label="set scheduled comfort temperature for",
                    )
                except Exception:
                    self._active = False
                    self._previous = None
                    self._active_target = None
                    await self._save_state()
                    raise
            return
        if target is not None and self._active and target != self._active_target:
            if self._active_target is not None and abs(current - self._active_target) < 0.01:
                await async_write_translated(
                    self._coordinator, register, target, action_label="change scheduled comfort temperature for"
                )
                self._active_target = target
                await self._save_state()
            return
        if target is None and self._active:
            if (
                self._previous is not None
                and self._active_target is not None
                and abs(current - self._active_target) < 0.01
            ):
                await async_write_translated(
                    self._coordinator,
                    register,
                    self._previous,
                    action_label="restore scheduled comfort temperature for",
                )
            self._previous = None
            self._active = False
            self._active_target = None
            await self._save_state()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._release_register_demand = self._coordinator.register_required_registers(
                f"comfort_schedule_{self._circuit}", {self.register_name}
            )
            # A foreground hass.async_create_task loop never finishes, so Home
            # Assistant's startup wrap-up waits on it and logs a bootstrap
            # timeout (#493 reporter log). The type() lookup keeps
            # MagicMock-based unit tests on the plain-task fallback.
            coro = self._run()
            background = getattr(type(self._hass), "async_create_background_task", None)
            if callable(background):
                self._task = cast(
                    "asyncio.Task[None]",
                    background(self._hass, coro, name=f"{DOMAIN}_comfort_schedule_{self._circuit}"),
                )
            else:
                create_task = getattr(self._hass, "async_create_task", None)
                self._task = cast(
                    "asyncio.Task[None]",
                    create_task(coro) if callable(create_task) else asyncio.create_task(coro),
                )

    async def async_stop(self) -> None:
        # Hold the evaluation lock while cancelling: an evaluation that is
        # already writing must finish — including its state save — before the
        # loop task goes away. Cancelling a task mid-write aborts the Modbus
        # transaction in flight (#493 race class; the same protection
        # DhwBoostManager has through its own lock).
        async with self._eval_lock:
            if self._task is not None:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None
        if self._release_register_demand is not None:
            self._release_register_demand()
            self._release_register_demand = None

    async def _run(self) -> None:
        await self.async_load()
        while True:
            try:
                await self.async_evaluate_once()
            except Exception:
                _LOGGER.warning("IDM comfort schedule evaluation failed", exc_info=True)
            await asyncio.sleep(60)
