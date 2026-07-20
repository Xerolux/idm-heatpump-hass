"""Restart-safe compressor, defrost and operating-mode analysis."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .binary_semantics import binary_value_is_on
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION: Final = 1
_STORAGE_SAVE_DELAY: Final = 10.0
_EVENT_RETENTION: Final = timedelta(days=8)
_MAX_COMPLETED_CYCLES: Final = 100
_COMPRESSOR_KEYS: Final = tuple(f"compressor_status_{index}" for index in range(1, 5))
_MODE_NAMES: Final = {
    1: "heating",
    2: "cooling",
    4: "dhw",
    8: "defrost",
}


def _utcnow() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(UTC)


def _parse_datetime(value: Any) -> datetime | None:
    """Parse one persisted ISO timestamp defensively."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_datetime_list(value: Any) -> list[datetime]:
    """Parse a persisted timestamp list and discard malformed values."""
    if not isinstance(value, list):
        return []
    parsed = [_parse_datetime(item) for item in value]
    return [item for item in parsed if item is not None]


def _finite_non_negative(value: Any) -> float | None:
    """Return a finite non-negative number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if numeric < 0 or numeric != numeric or numeric in (float("inf"), float("-inf")):
        return None
    return numeric


class OperationAnalysis:
    """Track observed heat-pump operating events without inventing missed edges."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        register_getter: Callable[[str], Any | None],
        *,
        short_cycle_minutes: int,
        expected_poll_interval: float,
    ) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass,
            _STORAGE_VERSION,
            f"{DOMAIN}.operation_analysis.{entry_id}",
        )
        self._register_getter = register_getter
        self.short_cycle_minutes = short_cycle_minutes
        self._max_sample_gap = max(60.0, expected_poll_interval * 3.0)

        self.total_compressor_starts = 0
        self.total_defrost_starts = 0
        self.compressor_start_events: list[datetime] = []
        self.defrost_start_events: list[datetime] = []
        self.completed_cycle_durations: list[float] = []
        self.mode_durations: dict[str, float] = {name: 0.0 for name in _MODE_NAMES.values()}

        self.last_compressor_start: datetime | None = None
        self.current_cycle_started: datetime | None = None
        self.last_cycle_duration: float | None = None
        self.last_cycle_ended: datetime | None = None
        self.last_defrost_start: datetime | None = None

        self._compressor_on: bool | None = None
        self._defrost_on: bool | None = None
        self._last_mode: int | None = None
        self._last_sample_at: datetime | None = None
        self._compressor_reconciled = False
        self._defrost_reconciled = False
        self._mode_reconciled = False

    @property
    def supports_compressor(self) -> bool:
        """Return whether at least one verified compressor status register exists."""
        return any(self._register_getter(key) is not None for key in _COMPRESSOR_KEYS)

    @property
    def supports_operating_mode(self) -> bool:
        """Return whether the verified operating-mode register exists."""
        return self._register_getter("hp_operating_mode") is not None

    async def async_load(self) -> None:
        """Load persisted observations without treating startup as a state edge."""
        try:
            stored = await self._store.async_load()
        except Exception:
            _LOGGER.warning("Could not load persisted IDM operation analysis", exc_info=True)
            return
        if not isinstance(stored, dict):
            return

        self.total_compressor_starts = max(0, int(stored.get("total_compressor_starts", 0)))
        self.total_defrost_starts = max(0, int(stored.get("total_defrost_starts", 0)))
        self.compressor_start_events = _parse_datetime_list(stored.get("compressor_start_events"))
        self.defrost_start_events = _parse_datetime_list(stored.get("defrost_start_events"))
        self.last_compressor_start = _parse_datetime(stored.get("last_compressor_start"))
        self.current_cycle_started = _parse_datetime(stored.get("current_cycle_started"))
        self.last_cycle_ended = _parse_datetime(stored.get("last_cycle_ended"))
        self.last_defrost_start = _parse_datetime(stored.get("last_defrost_start"))

        last_cycle = _finite_non_negative(stored.get("last_cycle_duration"))
        self.last_cycle_duration = last_cycle

        cycle_values = stored.get("completed_cycle_durations")
        if isinstance(cycle_values, list):
            parsed_cycles = [_finite_non_negative(item) for item in cycle_values]
            self.completed_cycle_durations = [item for item in parsed_cycles if item is not None][
                -_MAX_COMPLETED_CYCLES:
            ]

        stored_modes = stored.get("mode_durations")
        if isinstance(stored_modes, dict):
            for name in self.mode_durations:
                value = _finite_non_negative(stored_modes.get(name))
                if value is not None:
                    self.mode_durations[name] = value

        stored_compressor = stored.get("compressor_on")
        if isinstance(stored_compressor, bool):
            self._compressor_on = stored_compressor
        stored_defrost = stored.get("defrost_on")
        if isinstance(stored_defrost, bool):
            self._defrost_on = stored_defrost

        self._prune_events(_utcnow())

    async def async_save(self) -> None:
        """Persist observations immediately during config-entry unload."""
        await self._store.async_save(self._serialize())

    def _schedule_save(self) -> None:
        """Coalesce normal polling updates into a delayed storage write."""
        self._store.async_delay_save(self._serialize, _STORAGE_SAVE_DELAY)

    def _serialize(self) -> dict[str, Any]:
        """Return JSON-serializable tracker state."""
        return {
            "total_compressor_starts": self.total_compressor_starts,
            "total_defrost_starts": self.total_defrost_starts,
            "compressor_start_events": [event.isoformat() for event in self.compressor_start_events],
            "defrost_start_events": [event.isoformat() for event in self.defrost_start_events],
            "completed_cycle_durations": self.completed_cycle_durations[-_MAX_COMPLETED_CYCLES:],
            "mode_durations": dict(self.mode_durations),
            "last_compressor_start": self._iso(self.last_compressor_start),
            "current_cycle_started": self._iso(self.current_cycle_started),
            "last_cycle_duration": self.last_cycle_duration,
            "last_cycle_ended": self._iso(self.last_cycle_ended),
            "last_defrost_start": self._iso(self.last_defrost_start),
            "compressor_on": self._compressor_on,
            "defrost_on": self._defrost_on,
        }

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    def _compressor_state(
        self,
        data: Mapping[str, Any],
        unused_registers: set[str],
    ) -> bool | None:
        """Return aggregate compressor state when at least one source is valid."""
        states: list[bool] = []
        for key in _COMPRESSOR_KEYS:
            register = self._register_getter(key)
            if register is None or key not in data or key in unused_registers:
                continue
            value = data.get(key)
            if value is None:
                continue
            states.append(binary_value_is_on(register, value))
        return any(states) if states else None

    @staticmethod
    def _operating_mode(
        data: Mapping[str, Any],
        unused_registers: set[str],
    ) -> int | None:
        """Return one documented IDM operating-mode value."""
        if "hp_operating_mode" not in data or "hp_operating_mode" in unused_registers:
            return None
        value = data.get("hp_operating_mode")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        numeric = int(value)
        return numeric if numeric in {0, 1, 2, 4, 8} else None

    def process_snapshot(
        self,
        data: Mapping[str, Any],
        unused_registers: set[str],
        *,
        now: datetime | None = None,
    ) -> None:
        """Process one successful coordinator snapshot.

        The first valid observation for each source only reconciles persisted and
        live state. It never creates a start event, preventing false starts after
        Home Assistant restarts or communication gaps.
        """
        observed_at = (now or _utcnow()).astimezone(UTC)
        changed = False

        compressor_on = self._compressor_state(data, unused_registers)
        if compressor_on is not None:
            if not self._compressor_reconciled:
                if compressor_on:
                    if self._compressor_on is not True or self.current_cycle_started is None:
                        self.current_cycle_started = observed_at
                else:
                    self.current_cycle_started = None
                self._compressor_on = compressor_on
                self._compressor_reconciled = True
                changed = True
            elif compressor_on != self._compressor_on:
                if compressor_on:
                    self.total_compressor_starts += 1
                    self.compressor_start_events.append(observed_at)
                    self.last_compressor_start = observed_at
                    self.current_cycle_started = observed_at
                else:
                    if self.current_cycle_started is not None:
                        duration = (observed_at - self.current_cycle_started).total_seconds()
                        if duration >= 0:
                            self.last_cycle_duration = duration
                            self.last_cycle_ended = observed_at
                            self.completed_cycle_durations.append(duration)
                            self.completed_cycle_durations = self.completed_cycle_durations[-_MAX_COMPLETED_CYCLES:]
                    self.current_cycle_started = None
                self._compressor_on = compressor_on
                changed = True

        mode = self._operating_mode(data, unused_registers)
        if mode is not None:
            if not self._mode_reconciled:
                self._last_mode = mode
                self._last_sample_at = observed_at
                self._mode_reconciled = True
                changed = True
            else:
                changed |= self._accumulate_previous_mode(observed_at)
                self._last_mode = mode
                self._last_sample_at = observed_at

            defrost_on = mode == 8
            if not self._defrost_reconciled:
                self._defrost_on = defrost_on
                self._defrost_reconciled = True
                changed = True
            elif defrost_on != self._defrost_on:
                if defrost_on:
                    self.total_defrost_starts += 1
                    self.defrost_start_events.append(observed_at)
                    self.last_defrost_start = observed_at
                self._defrost_on = defrost_on
                changed = True
        elif self._mode_reconciled:
            # A successful snapshot with an unavailable mode pauses accounting;
            # the missing interval is never assigned to the previous mode.
            self._last_mode = None
            self._last_sample_at = observed_at

        changed |= self._prune_events(observed_at)
        if changed:
            self._schedule_save()

    def _accumulate_previous_mode(self, observed_at: datetime) -> bool:
        """Accumulate only a normal polling interval, never a communication gap."""
        if self._last_sample_at is None or self._last_mode not in _MODE_NAMES:
            return False
        elapsed = (observed_at - self._last_sample_at).total_seconds()
        if not 0 <= elapsed <= self._max_sample_gap:
            return False
        name = _MODE_NAMES[self._last_mode]
        self.mode_durations[name] += elapsed
        return elapsed > 0

    def _prune_events(self, now: datetime) -> bool:
        """Keep enough event history for day and rolling-window calculations."""
        cutoff = now - _EVENT_RETENTION
        before = (len(self.compressor_start_events), len(self.defrost_start_events))
        self.compressor_start_events = [event for event in self.compressor_start_events if event >= cutoff]
        self.defrost_start_events = [event for event in self.defrost_start_events if event >= cutoff]
        return before != (len(self.compressor_start_events), len(self.defrost_start_events))

    @staticmethod
    def _count_since(events: list[datetime], since: datetime) -> int:
        return sum(event >= since for event in events)

    @staticmethod
    def _count_today(events: list[datetime], now: datetime) -> int:
        local_date = dt_util.as_local(now).date()
        return sum(dt_util.as_local(event).date() == local_date for event in events)

    def compressor_starts_today(self, now: datetime | None = None) -> int:
        current = (now or _utcnow()).astimezone(UTC)
        return self._count_today(self.compressor_start_events, current)

    def compressor_starts_last_hours(self, hours: int, now: datetime | None = None) -> int:
        current = (now or _utcnow()).astimezone(UTC)
        return self._count_since(self.compressor_start_events, current - timedelta(hours=hours))

    def defrost_starts_today(self, now: datetime | None = None) -> int:
        current = (now or _utcnow()).astimezone(UTC)
        return self._count_today(self.defrost_start_events, current)

    def current_cycle_minutes(self, now: datetime | None = None) -> float | None:
        if self._compressor_on is not True or self.current_cycle_started is None:
            return None
        current = (now or _utcnow()).astimezone(UTC)
        elapsed = (current - self.current_cycle_started).total_seconds()
        return round(max(0.0, elapsed) / 60.0, 1)

    def average_cycle_minutes(self) -> float | None:
        if not self.completed_cycle_durations:
            return None
        return round(
            sum(self.completed_cycle_durations) / len(self.completed_cycle_durations) / 60.0,
            1,
        )

    def minutes_since_last_defrost(self, now: datetime | None = None) -> float | None:
        if self.last_defrost_start is None:
            return None
        current = (now or _utcnow()).astimezone(UTC)
        elapsed = (current - self.last_defrost_start).total_seconds()
        return round(max(0.0, elapsed) / 60.0, 1)

    def operating_share(self, mode_name: str) -> float | None:
        """Return percentage of tracked active runtime for one documented mode."""
        if mode_name not in self.mode_durations:
            return None
        total = sum(self.mode_durations.values())
        if total <= 0:
            return None
        return round(self.mode_durations[mode_name] / total * 100.0, 1)

    @property
    def last_cycle_was_short(self) -> bool | None:
        """Return whether the last fully observed cycle was below the threshold."""
        if self.last_cycle_duration is None:
            return None
        return self.last_cycle_duration < self.short_cycle_minutes * 60
