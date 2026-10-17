"""Real-HA regression tests for the write-confirmation availability flap (#537).

Field evidence (reference plant, direct connection): after every GLT
forwarding pass — several sequential ``async_write_register`` calls, each
scheduling a 0.5 s confirmation refresh and cancelling the previous
confirmation task — every coordinator-backed entity flipped *unavailable*
for one poll cycle, silently: Home Assistant's ``DataUpdateCoordinator``
records the ``CancelledError`` that lands inside a refresh as a failed
update without logging it, and the next scheduled poll restores
availability ~12 s later.

``test_raw_cancel_inside_refresh_flips_availability`` pins that Home
Assistant behaviour. ``test_forwarder_pass_keeps_availability_up`` and
``test_guarded_cancel_keeps_availability_up`` assert the production
pattern — a forwarding pass, and the cancel-suppression guard
``IdmCoordinator`` carries since the fix — never flip availability.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

POLL_SLEEP = 0.05


class PatternCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Mimic IdmCoordinator's write/confirmation pattern in isolation.

    ``update_interval`` plays the scan interval; ``write`` replays the tail
    of ``async_write_register``: optimistic data update, listener dispatch,
    and a confirmation task that cancels its predecessor — the
    ``_delayed_refresh_task`` handling of the production coordinator.
    With ``guard_refresh=True`` the cancellation is suppressed while the
    previous task is already refreshing, exactly like the #537 fix.
    """

    def __init__(self, hass: HomeAssistant, poll_seconds: float, *, guard_refresh: bool = False) -> None:
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name="flap_repro",
            config_entry=None,
            update_interval=timedelta(seconds=poll_seconds),
            request_refresh_debouncer=Debouncer(
                hass,
                logging.getLogger(__name__),
                cooldown=3.0,
                immediate=True,
                function=self._async_refresh,
            ),
        )
        self.poll_count = 0
        self.confirmation_task: asyncio.Task[None] | None = None
        self.confirmation_refresh_running = False
        self.guard_refresh = guard_refresh

    async def _async_update_data(self) -> dict[str, Any]:
        self.poll_count += 1
        await asyncio.sleep(POLL_SLEEP)
        return {"register": self.poll_count}

    async def _delayed_refresh(self, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            self.confirmation_refresh_running = True
            try:
                await self.async_request_refresh()
            finally:
                self.confirmation_refresh_running = False
        except asyncio.CancelledError:
            pass

    def _start_confirmation(self, delay: float) -> asyncio.Task[None]:
        return asyncio.create_task(self._delayed_refresh(delay))

    async def write(self, *, delay: float = 0.5) -> None:
        updated = dict(self.data or {})
        updated["register"] = (updated.get("register") or 0) + 1000
        self.data = updated
        self.async_update_listeners()
        old_task = self.confirmation_task
        if (
            old_task is not None
            and not old_task.done()
            and not (self.guard_refresh and self.confirmation_refresh_running)
        ):
            old_task.cancel()
        self.confirmation_task = self._start_confirmation(delay)

    async def shutdown(self) -> None:
        if self.confirmation_task is not None:
            self.confirmation_task.cancel()
        await self.async_shutdown()


async def test_forwarder_pass_keeps_availability_up(smoke_hass: HomeAssistant) -> None:
    """A forwarding pass (sequential writes) must not flip last_update_success."""
    coordinator = PatternCoordinator(smoke_hass, poll_seconds=2.0)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True

    flips: list[bool] = []
    coordinator.async_add_listener(lambda: flips.append(coordinator.last_update_success))

    # The forwarding pass: several writes in quick succession, each
    # cancelling the previous confirmation task (production cadence).
    for _ in range(4):
        await coordinator.write()
        await asyncio.sleep(0.08)

    # Let the final confirmation refresh run to completion.
    await asyncio.sleep(1.0)

    assert coordinator.last_update_success is True, "confirmation flipped availability"
    assert not any(entry is False for entry in flips), f"availability flipped during pass: {flips}"
    await coordinator.shutdown()


async def test_raw_cancel_inside_refresh_flips_availability(smoke_hass: HomeAssistant) -> None:
    """Pin the Home Assistant behaviour behind #537 (documentation guard).

    Cancelling a task while it is inside ``async_request_refresh`` makes
    ``DataUpdateCoordinator`` record a silently failed update. This test
    fails if Home Assistant changes that behaviour — the #537 guard in
    ``IdmCoordinator`` would then be redundant, not wrong.
    """
    coordinator = PatternCoordinator(smoke_hass, poll_seconds=10.0)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True

    task = coordinator._start_confirmation(0.0)
    await asyncio.sleep(0.02)
    assert coordinator.confirmation_refresh_running is True
    task.cancel()
    await asyncio.sleep(0.3)

    assert coordinator.last_update_success is False, (
        "Home Assistant no longer flips last_update_success on an in-refresh cancellation"
    )
    await coordinator.shutdown()


async def test_guarded_cancel_keeps_availability_up(smoke_hass: HomeAssistant) -> None:
    """The #537 guard: an in-refresh confirmation is left alone, later ones wait."""
    coordinator = PatternCoordinator(smoke_hass, poll_seconds=10.0, guard_refresh=True)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True

    await coordinator.write(delay=0.0)
    await asyncio.sleep(0.02)
    assert coordinator.confirmation_refresh_running is True

    # The next write of the same pass must not cancel the refreshing task.
    await coordinator.write(delay=0.2)
    first_task = coordinator.confirmation_task
    await asyncio.sleep(0.5)

    assert coordinator.last_update_success is True, "guarded pass flipped availability"
    assert first_task.done() and not first_task.cancelled(), "guarded task was cancelled after all"
    await coordinator.shutdown()
