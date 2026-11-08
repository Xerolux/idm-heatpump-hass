"""One shared per-minute timer for the independently consented cloud observers.

Telemetry and firmware observations each used to install their own
``async_track_time_interval`` callback. With both consents active that meant
two timers waking Home Assistant every minute for what is usually a no-op
guard check. The scheduler fans one timer out to every subscriber and tears
it down when the last one unsubscribes (entry unload or withdrawal).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)
_TICK_INTERVAL = timedelta(minutes=1)


class CloudTickScheduler:
    """Deliver one timer tick to every subscribed observer, isolated."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._ticks: set[Callable[[datetime], Any]] = set()
        self._unsubscribe: Callable[[], None] | None = None

    @property
    def subscriber_count(self) -> int:
        """How many observers currently share this timer."""
        return len(self._ticks)

    def subscribe(self, tick: Callable[[datetime], Any]) -> Callable[[], None]:
        """Register an awaitable tick; the timer lives while subscribers do."""
        self._ticks.add(tick)
        if self._unsubscribe is None:
            self._unsubscribe = async_track_time_interval(self._hass, self._tick, _TICK_INTERVAL)

        def _remove() -> None:
            self._ticks.discard(tick)
            if not self._ticks and self._unsubscribe is not None:
                self._unsubscribe()
                self._unsubscribe = None

        return _remove

    async def _tick(self, now: datetime) -> None:
        for tick in tuple(self._ticks):
            try:
                await tick(now)
            except Exception:  # one observer must not stop the others
                _LOGGER.exception("Cloud observer tick failed; remaining observers still run")


def entry_cloud_scheduler(hass: HomeAssistant, entry: Any) -> CloudTickScheduler:
    """Return the per-entry shared cloud timer, creating it on first use.

    The scheduler rides on ``entry.runtime_data`` so it dies with the entry
    setup that created it; ``async_on_unload`` removers released by the
    entry cancel the underlying timer once both observers are gone.
    """
    runtime = getattr(entry, "runtime_data", None)
    existing = getattr(runtime, "cloud_scheduler", None)
    if isinstance(existing, CloudTickScheduler):
        return existing
    scheduler = CloudTickScheduler(hass)
    if runtime is not None:
        runtime.cloud_scheduler = scheduler
    return scheduler
