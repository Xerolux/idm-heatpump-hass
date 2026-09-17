"""Optional, conservative heating-circuit comfort scheduler."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time
from typing import Any

from .entity import async_write_translated

_LOGGER = logging.getLogger(__name__)


def _parse_time(value: str, fallback: time) -> time:
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError):
        return fallback


class ComfortScheduler:
    """Apply one daily room-temperature comfort window to one heating circuit."""

    def __init__(self, hass: Any, coordinator: Any, circuit: str, start: str, end: str, target: float) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._circuit = circuit.lower()
        self._start = _parse_time(start, time(6, 0))
        self._end = _parse_time(end, time(22, 0))
        self._target = float(target)
        self._task: asyncio.Task[None] | None = None
        self._active = False
        self._previous: float | None = None

    @property
    def register_name(self) -> str:
        return f"hc_{self._circuit}_room_setpoint_heat_normal"

    def _in_window(self, current: time) -> bool:
        if self._start == self._end:
            return False
        if self._start < self._end:
            return self._start <= current < self._end
        return current >= self._start or current < self._end

    def _current_value(self) -> float | None:
        value = (self._coordinator.data or {}).get(self.register_name)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def async_evaluate_once(self, *, now: datetime | None = None) -> None:
        register = self._coordinator.get_register(self.register_name)
        if register is None:
            return
        current = self._current_value()
        if current is None:
            return
        active = self._in_window((now or datetime.now().astimezone()).time())
        if active and not self._active:
            self._previous = current
            if abs(current - self._target) >= 0.01:
                await async_write_translated(
                    self._coordinator,
                    register,
                    self._target,
                    action_label="set scheduled comfort temperature for",
                )
            self._active = True
            return
        if not active and self._active:
            if self._previous is not None and abs(current - self._target) < 0.01:
                await async_write_translated(
                    self._coordinator,
                    register,
                    self._previous,
                    action_label="restore scheduled comfort temperature for",
                )
            self._previous = None
            self._active = False

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = self._hass.async_create_task(self._run())

    async def async_stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self.async_evaluate_once()
            except Exception:
                _LOGGER.warning("IDM comfort schedule evaluation failed", exc_info=True)
            await asyncio.sleep(60)
