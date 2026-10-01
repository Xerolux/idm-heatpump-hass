"""Self-healing reload for config entries whose Modbus endpoint recovered.

When ``async_setup_entry`` raises ``ConfigEntryNotReady`` Home Assistant
schedules a retry with exponential backoff — up to about thirty minutes. If
the outage was transient (proxy restart, controller reboot), the plant often
answers again long before the backoff expires, and a repair card lingers
although nothing is wrong any more. The *Verbindung neu laden* diagnostic
button (0.20.0-b16) skips the wait on demand; this module does the same
automatically: while entries of this integration are in setup retry, a
lightweight TCP probe checks the configured Modbus endpoint once a minute,
and after consecutive successes — with a per-entry cooldown against
hammering a genuinely broken installation — the entry is reloaded
programmatically.

The probe opens and closes a TCP connection and sends nothing; it is strictly
read-only. The watchdog only runs while at least one entry is in setup retry
(it is started on the way into the retry state and ends itself when the last
watched entry left it), so a healthy integration owns no background task.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntryState

from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

#: Seconds between probe rounds while entries are in setup retry.
PROBE_INTERVAL = 60.0
#: Seconds a single TCP probe may take.
PROBE_TIMEOUT = 3.0
#: Consecutive endpoint successes before an entry is reloaded.
REQUIRED_SUCCESSES = 2
#: Minimum seconds between automatic reloads of the same entry.
RELOAD_COOLDOWN = 600.0


@dataclass(frozen=True)
class WatchedEntry:
    """The subset of a config entry the watchdog decides on."""

    entry_id: str
    host: str
    port: int
    state: Any


async def tcp_probe(host: str, port: int) -> bool:
    """Return whether the endpoint accepts a TCP connection.

    Opens and immediately closes a connection; no byte is sent, so the
    probe cannot disturb the device or a proxy's connection accounting.
    """
    try:
        _reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=PROBE_TIMEOUT)
    except (OSError, TimeoutError, ValueError):
        return False
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    return True


class RecoveryWatchdog:
    """Decide, per probe round, whether a retrying entry should be reloaded."""

    def __init__(
        self,
        reload_entry: Callable[[str], Awaitable[None]],
        probe: Callable[[str, int], Awaitable[bool]],
        *,
        required_successes: int = REQUIRED_SUCCESSES,
        reload_cooldown: float = RELOAD_COOLDOWN,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._reload_entry = reload_entry
        self._probe = probe
        self._required_successes = required_successes
        self._reload_cooldown = reload_cooldown
        self._clock = clock
        self._consecutive: dict[str, int] = {}
        self._last_reload: dict[str, float] = {}

    async def tick(self, entries: Iterable[WatchedEntry]) -> list[str]:
        """Probe every retrying entry once; reload the recovered ones.

        Returns the entry ids that were reloaded this round.
        """
        reloaded: list[str] = []
        now = self._clock()
        for entry in entries:
            if entry.state is not ConfigEntryState.SETUP_RETRY:
                self._consecutive.pop(entry.entry_id, None)
                continue
            if not entry.host:
                continue
            if not await self._probe(entry.host, entry.port):
                self._consecutive[entry.entry_id] = 0
                continue
            successes = self._consecutive.get(entry.entry_id, 0) + 1
            self._consecutive[entry.entry_id] = successes
            if successes < self._required_successes:
                continue
            if now - self._last_reload.get(entry.entry_id, float("-inf")) < self._reload_cooldown:
                continue
            self._last_reload[entry.entry_id] = now
            self._consecutive[entry.entry_id] = 0
            _LOGGER.info(
                "IDM Modbus endpoint %s:%s answers again; reloading the config entry automatically",
                entry.host,
                entry.port,
            )
            await self._reload_entry(entry.entry_id)
            reloaded.append(entry.entry_id)
        return reloaded


def _snapshot(hass: Any) -> list[WatchedEntry]:
    """Collect this integration's entries with the fields the watchdog needs."""
    entries: list[WatchedEntry] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        host = entry.data.get(CONF_HOST)
        if not isinstance(host, str):
            continue
        port = entry.data.get(CONF_PORT, DEFAULT_PORT)
        if not isinstance(port, int):
            port = DEFAULT_PORT
        entries.append(WatchedEntry(entry_id=entry.entry_id, host=host, port=port, state=entry.state))
    return entries


def ensure_recovery_watchdog(hass: Any) -> None:
    """Start the watchdog loop unless one is already running.

    Called on the way into the setup-retry state. The loop ends itself once
    no entry of this integration is retrying any more, so nothing has to be
    stopped on unload and a healthy integration owns no task.
    """
    store = hass.data.setdefault(DOMAIN, {})
    if store.get("recovery_watchdog_task") is not None:
        return

    async def _run() -> None:
        watchdog = RecoveryWatchdog(
            reload_entry=lambda entry_id: _async_reload(hass, entry_id),
            probe=tcp_probe,
        )
        try:
            while True:
                await asyncio.sleep(PROBE_INTERVAL)
                entries = _snapshot(hass)
                if not any(entry.state is ConfigEntryState.SETUP_RETRY for entry in entries):
                    break
                await watchdog.tick(entries)
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.debug("IDM recovery watchdog stopped unexpectedly", exc_info=True)
        finally:
            store = hass.data.get(DOMAIN)
            if isinstance(store, dict):
                store.pop("recovery_watchdog_task", None)

    store["recovery_watchdog_task"] = (
        hass.async_create_task(_run()) if hasattr(hass, "async_create_task") else asyncio.create_task(_run())
    )


async def _async_reload(hass: Any, entry_id: str) -> None:
    """Reload a config entry, tolerating a shut-down Home Assistant."""
    try:
        await hass.config_entries.async_reload(entry_id)
    except Exception:
        _LOGGER.debug("Automatic reload of %s failed", entry_id, exc_info=True)
