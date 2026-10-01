"""Self-healing reload for config entries in setup retry (anti-panic package)."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any

from homeassistant.config_entries import ConfigEntryState

from custom_components.idm_heatpump.const import CONF_HOST, CONF_PORT, DOMAIN
from custom_components.idm_heatpump.recovery_watchdog import (
    RecoveryWatchdog,
    WatchedEntry,
    ensure_recovery_watchdog,
    tcp_probe,
)


def _entry(entry_id: str, *, state: Any, host: str = "192.0.2.10", port: int = 502) -> WatchedEntry:
    return WatchedEntry(entry_id=entry_id, host=host, port=port, state=state)


class _ProbeScript:
    """Probe stub that answers a scripted sequence, then always False."""

    def __init__(self, answers: list[bool]) -> None:
        self._answers = list(answers)
        self.calls: list[tuple[str, int]] = []

    async def __call__(self, host: str, port: int) -> bool:
        self.calls.append((host, port))
        return self._answers.pop(0) if self._answers else False


class _ReloadRecorder:
    def __init__(self) -> None:
        self.entry_ids: list[str] = []

    async def __call__(self, entry_id: str) -> None:
        self.entry_ids.append(entry_id)


class TestRecoveryWatchdog:
    async def test_reloads_after_consecutive_successes(self) -> None:
        reloads = _ReloadRecorder()
        clock = time.monotonic
        watchdog = RecoveryWatchdog(reloads, _ProbeScript([True, True]), clock=clock)
        retrying = _entry("e1", state=ConfigEntryState.SETUP_RETRY)

        first = await watchdog.tick([retrying])
        second = await watchdog.tick([retrying])

        assert first == []
        assert second == ["e1"]
        assert reloads.entry_ids == ["e1"]

    async def test_single_success_does_not_reload(self) -> None:
        reloads = _ReloadRecorder()
        watchdog = RecoveryWatchdog(reloads, _ProbeScript([True, False]), required_successes=2, clock=time.monotonic)
        retrying = _entry("e1", state=ConfigEntryState.SETUP_RETRY)

        assert await watchdog.tick([retrying]) == []
        # The failed probe resets the streak: two more rounds are needed.
        assert await watchdog.tick([retrying]) == []
        assert reloads.entry_ids == []

    async def test_healthy_entries_are_ignored(self) -> None:
        reloads = _ReloadRecorder()
        probe = _ProbeScript([True, True, True, True])
        watchdog = RecoveryWatchdog(reloads, probe, clock=time.monotonic)
        loaded = _entry("e1", state=ConfigEntryState.LOADED)

        assert await watchdog.tick([loaded]) == []
        assert await watchdog.tick([loaded]) == []
        assert probe.calls == []
        assert reloads.entry_ids == []

    async def test_reload_respects_the_cooldown(self) -> None:
        reloads = _ReloadRecorder()
        now = {"t": 1000.0}
        watchdog = RecoveryWatchdog(
            reloads,
            _ProbeScript([True] * 10),
            required_successes=2,
            reload_cooldown=600.0,
            clock=lambda: now["t"],
        )
        retrying = _entry("e1", state=ConfigEntryState.SETUP_RETRY)

        await watchdog.tick([retrying])
        assert await watchdog.tick([retrying]) == ["e1"]

        # Endpoint keeps answering, but the cooldown holds the reload back.
        now["t"] = 1300.0
        await watchdog.tick([retrying])
        assert await watchdog.tick([retrying]) == []

        # The streak kept growing while the cooldown blocked, so the first
        # round after it expires reloads immediately.
        now["t"] = 1700.0
        assert await watchdog.tick([retrying]) == ["e1"]
        assert reloads.entry_ids == ["e1", "e1"]

    async def test_recovery_clears_the_streak_for_the_next_outage(self) -> None:
        reloads = _ReloadRecorder()
        now = {"t": 0.0}
        watchdog = RecoveryWatchdog(
            reloads,
            _ProbeScript([True] * 10),
            required_successes=2,
            reload_cooldown=0.0,
            clock=lambda: now["t"],
        )
        entry = _entry("e1", state=ConfigEntryState.SETUP_RETRY)

        await watchdog.tick([entry])
        await watchdog.tick([entry])
        # The entry recovered and is loaded again.
        await watchdog.tick([_entry("e1", state=ConfigEntryState.LOADED)])
        # A later outage starts from zero successes.
        await watchdog.tick([entry])
        assert await watchdog.tick([entry]) == ["e1"]
        assert reloads.entry_ids == ["e1", "e1"]


class TestTcpProbe:
    async def test_open_port_answers_true(self) -> None:
        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            assert await tcp_probe("127.0.0.1", port) is True
        finally:
            server.close()
            await server.wait_closed()

    async def test_closed_port_answers_false(self) -> None:
        # Bind and close to find a port nothing listens on.
        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        server.close()
        await server.wait_closed()

        assert await tcp_probe("127.0.0.1", port) is False


class TestWatchdogLifecycle:
    async def test_ensure_starts_one_task_and_the_loop_ends_without_retrying_entries(
        self, mock_hass, monkeypatch
    ) -> None:
        import custom_components.idm_heatpump.recovery_watchdog as rw

        monkeypatch.setattr(rw, "PROBE_INTERVAL", 0.05)
        reloaded = {"entries": []}

        async def _fake_reload(entry_id: str) -> None:
            reloaded["entries"].append(entry_id)

        created: list[asyncio.Task] = []

        def _create(coro):  # the stub hass may not implement async_create_task
            task = asyncio.get_running_loop().create_task(coro)
            created.append(task)
            return task

        # hass.async_create_task missing on the stub -> exercise the fallback
        if hasattr(mock_hass, "async_create_task"):
            monkeypatch.delattr(mock_hass, "async_create_task")

        loaded_entry = SimpleNamespace(
            entry_id="e1",
            data={CONF_HOST: "127.0.0.1", CONF_PORT: 502},
            state=ConfigEntryState.LOADED,
        )
        mock_hass.config_entries.async_entries = lambda domain: [loaded_entry]

        ensure_recovery_watchdog(mock_hass)
        first_task = mock_hass.data[DOMAIN]["recovery_watchdog_task"]
        # A second call while running must not stack another loop.
        ensure_recovery_watchdog(mock_hass)
        assert mock_hass.data[DOMAIN]["recovery_watchdog_task"] is first_task

        # The loop saw no retrying entry and ended itself, cleaning the slot.
        await asyncio.wait_for(first_task, timeout=2.0)
        assert "recovery_watchdog_task" not in mock_hass.data[DOMAIN]

    async def test_snapshot_maps_entries_and_defaults(self, mock_hass) -> None:
        from custom_components.idm_heatpump.recovery_watchdog import _snapshot

        entry = SimpleNamespace(
            entry_id="e1",
            data={CONF_HOST: "192.0.2.5"},
            state=None,
        )
        mock_hass.config_entries.async_entries = lambda domain: [entry]

        result = _snapshot(mock_hass)

        assert [(e.entry_id, e.host, e.port) for e in result] == [("e1", "192.0.2.5", 502)]
