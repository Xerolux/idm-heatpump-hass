"""Exercise the optional forwarder without writing to a real controller."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.idm_heatpump import external_power_forwarding as module


def _state(value: object, unit: str | None = "kW") -> SimpleNamespace:
    return SimpleNamespace(state=value, attributes={"unit_of_measurement": unit} if unit else {})


def _forwarder(
    states: dict[str, SimpleNamespace], entities: dict[str, str], *, battery_sign: str = "as_is"
) -> tuple[module.ExternalPowerForwarder, MagicMock]:
    hass = MagicMock()
    hass.states.get.side_effect = states.get
    coordinator = MagicMock()
    coordinator.get_register.side_effect = lambda name: SimpleNamespace(
        name=name, writable=True, min_val=0 if name != "battery_discharge" else -20, max_val=100
    )
    coordinator.async_write_register = AsyncMock()
    return (
        module.ExternalPowerForwarder(
            hass,
            coordinator,
            module.ExternalPowerForwardingConfig(entities, 30, battery_sign),
        ),
        coordinator,
    )


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [(1000, "W", 1.0), (1, "kW", 1.0), (0.001, "MW", 1.0), (1, None, None), ("unknown", "W", None)],
)
def test_power_conversion(value: object, unit: str | None, expected: float | None) -> None:
    forwarder, _ = _forwarder({}, {})
    assert forwarder._value("pv_production", _state(value, unit)) == expected


def test_soc_and_battery_sign_are_validated() -> None:
    forwarder, _ = _forwarder({}, {}, battery_sign="invert")
    assert forwarder._value("battery_discharge", _state(500, "W")) == -0.5
    assert forwarder._value("battery_soc", _state(75, "%")) == 75.0
    assert forwarder._value("battery_soc", _state(-1, "%")) is None
    assert forwarder._value("battery_soc", _state(75.5, "%")) == 76.0
    assert forwarder._value("battery_soc", _state(101, "%")) is None
    assert forwarder._value("battery_soc", _state("unavailable", "%")) is None
    assert forwarder._value("pv_production", None) is None
    assert module._unit(SimpleNamespace(attributes=None)) is None
    assert module._number(object()) is None
    assert module._soc(50, "kWh") is None


async def test_valid_values_are_forwarded_and_invalid_values_skipped() -> None:
    forwarder, coordinator = _forwarder(
        {"sensor.pv": _state(1500, "W"), "sensor.bad": _state("unknown")},
        {"pv_production": "sensor.pv", "house_consumption": "sensor.bad", "bogus": "sensor.pv"},
    )
    await forwarder.async_forward()
    coordinator.async_write_register.assert_awaited_once()
    assert coordinator.async_write_register.await_args.args[1] == 1.5


async def test_battery_soc_unavailable_sentinel_is_not_written() -> None:
    forwarder, coordinator = _forwarder({"sensor.soc": _state(-1, "%")}, {"battery_soc": "sensor.soc"})
    await forwarder.async_forward()
    coordinator.async_write_register.assert_not_awaited()


async def test_successful_forward_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Successful GLT writes are visible so logs show the refresh cadence.

    When a controller clears a RAM input on its own (#493), the timestamps of
    our successful writes are the only way to tell integration-side throttling
    apart from device-side clearing.
    """
    forwarder, coordinator = _forwarder({"sensor.soc": _state(98, "%")}, {"battery_soc": "sensor.soc"})
    with caplog.at_level("DEBUG", logger="custom_components.idm_heatpump.external_power_forwarding"):
        await forwarder.async_forward()

    coordinator.async_write_register.assert_awaited_once()
    assert "Forwarded external power battery_soc = 98.0" in caplog.text


async def test_register_guards_and_transport_error(caplog: pytest.LogCaptureFixture) -> None:
    forwarder, coordinator = _forwarder({"sensor.pv": _state(2)}, {"pv_production": "sensor.pv"})
    coordinator.get_register.return_value = None
    coordinator.get_register.side_effect = None
    await forwarder.async_forward()
    coordinator.async_write_register.assert_not_awaited()

    register = SimpleNamespace(name="pv_production", writable=False, min_val=0, max_val=10)
    coordinator.get_register.return_value = register
    await forwarder.async_forward()
    coordinator.async_write_register.assert_not_awaited()

    register.writable = True
    register.max_val = 1
    await forwarder.async_forward()
    coordinator.async_write_register.assert_not_awaited()
    register.max_val = 10
    register.min_val = 3
    await forwarder.async_forward()
    coordinator.async_write_register.assert_not_awaited()

    register.min_val = 0
    coordinator.async_write_register.side_effect = RuntimeError("offline")
    await forwarder.async_forward()
    assert "Could not forward" in caplog.text


async def test_write_cooldown_is_not_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Cooldown skips are expected self-throttling, not a device problem (#471).

    Sensor-driven forwards fire on every source update; the coordinator drops
    those inside the per-register write cooldown. That used to log
    "rejected the value" on every cycle and read like a controller fault.
    """
    caplog.clear()
    forwarder, coordinator = _forwarder({"sensor.pv": _state(-3.5)}, {"pv_surplus": "sensor.pv"})
    register = SimpleNamespace(name="pv_surplus", writable=True, min_val=None, max_val=None)
    coordinator.get_register.side_effect = None
    coordinator.get_register.return_value = register

    class _CooldownError(RuntimeError):
        translation_key = "write_cooldown_active"

    coordinator.async_write_register.side_effect = _CooldownError(
        "Writing pv_surplus is still paused: 3.2 s of the 5 s write cooldown remain"
    )
    with caplog.at_level("DEBUG", logger="custom_components.idm_heatpump.external_power_forwarding"):
        await forwarder.async_forward()

    assert "Could not forward" not in caplog.text
    assert "rejected the value" not in caplog.text
    assert "write cooldown" in caplog.text


async def test_run_cleans_up_listener_on_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    forwarder, _ = _forwarder({}, {})
    unsubscribe = MagicMock()
    monkeypatch.setattr(module, "async_track_state_change_event", lambda *_: unsubscribe)
    forwarder.async_forward = AsyncMock()
    task = asyncio.create_task(forwarder.async_run())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    unsubscribe.assert_called_once()
    forwarder.async_forward.assert_awaited_once()


async def test_state_changes_debounce_to_one_forward() -> None:
    forwarder, _ = _forwarder({}, {})
    forwarder._hass.async_create_task.side_effect = asyncio.create_task
    forwarder.async_forward = AsyncMock()
    forwarder._state_changed(None)
    await asyncio.sleep(0)
    forwarder._state_changed(None)
    await asyncio.sleep(1.1)
    forwarder.async_forward.assert_awaited_once()
    assert forwarder._pending_task is None


async def test_sensor_bursts_do_not_postpone_the_pending_forward() -> None:
    forwarder, _ = _forwarder({}, {})
    forwarder._hass.async_create_task.side_effect = asyncio.create_task
    forwarder.async_forward = AsyncMock()
    forwarder._state_changed(None)
    first = forwarder._pending_task
    await asyncio.sleep(0)
    forwarder._state_changed(None)
    assert forwarder._pending_task is first
    try:
        await asyncio.sleep(1.1)
        forwarder.async_forward.assert_awaited_once()
        assert forwarder._pending_task is None
    finally:
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)


async def test_sensor_event_during_write_finishes_the_batch_and_forwards_latest_state() -> None:
    states = {"sensor.pv": _state(1), "sensor.soc": _state(80, "%")}
    forwarder, coordinator = _forwarder(states, {"pv_production": "sensor.pv", "battery_soc": "sensor.soc"})
    forwarder._hass.async_create_task.side_effect = asyncio.create_task
    started = asyncio.Event()
    release = asyncio.Event()
    writes: list[tuple[str, float]] = []

    async def write(reg: SimpleNamespace, value: float) -> None:
        writes.append((reg.name, value))
        if len(writes) == 1:
            started.set()
            await release.wait()

    coordinator.async_write_register.side_effect = write
    forwarder._state_changed(None)
    task = forwarder._pending_task
    try:
        await asyncio.wait_for(started.wait(), 2)
        states["sensor.pv"] = _state(2)
        forwarder._state_changed(None)
        assert forwarder._pending_task is task
        release.set()
        await asyncio.wait_for(task, 3)
        assert writes == [
            ("pv_production", 1.0),
            ("battery_soc", 80.0),
            ("pv_production", 2.0),
            ("battery_soc", 80.0),
        ]
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_periodic_and_event_forwards_never_interleave_batches() -> None:
    forwarder, coordinator = _forwarder(
        {"sensor.pv": _state(1), "sensor.soc": _state(80, "%")},
        {"pv_production": "sensor.pv", "battery_soc": "sensor.soc"},
    )
    started = asyncio.Event()
    release = asyncio.Event()
    writes: list[str] = []

    async def write(reg: SimpleNamespace, value: float) -> None:
        writes.append(reg.name)
        if len(writes) == 1:
            started.set()
            await release.wait()

    coordinator.async_write_register.side_effect = write
    first = asyncio.create_task(forwarder.async_forward())
    second = None
    try:
        await asyncio.wait_for(started.wait(), 1)
        second = asyncio.create_task(forwarder.async_forward())
        await asyncio.sleep(0)
        assert writes == ["pv_production"]
        release.set()
        await asyncio.wait_for(asyncio.gather(first, second), 1)
        assert writes == ["pv_production", "battery_soc", "pv_production", "battery_soc"]
    finally:
        release.set()
        for task in (first, second):
            if task is not None:
                task.cancel()
        await asyncio.gather(*(task for task in (first, second) if task is not None), return_exceptions=True)


@pytest.mark.parametrize("surplus", [-2.0, 0.0, 3.0])
async def test_forwarding_preserves_signed_measurements_without_control_writes(surplus):
    forwarder, coordinator = _forwarder(
        {"sensor.net": _state(surplus), "sensor.pv": _state(4), "sensor.soc": _state(80, "%")},
        {"pv_surplus": "sensor.net", "pv_production": "sensor.pv", "battery_soc": "sensor.soc"},
    )
    coordinator.get_register.side_effect = lambda name: SimpleNamespace(
        name=name, writable=True, min_val=None, max_val=None
    )
    await forwarder.async_forward()
    writes = [(call.args[0].name, call.args[1]) for call in coordinator.async_write_register.await_args_list]
    assert writes == [("pv_surplus", surplus), ("pv_production", 4.0), ("battery_soc", 80.0)]


@pytest.mark.parametrize("soc,expected", [(97.5, 98.0), (0.1, 0.0), (99.9, 100.0), (98.5, 98.0)])
async def test_fractional_battery_soc_is_forwarded_as_integer_percentage(soc, expected):
    forwarder, coordinator = _forwarder({"sensor.soc": _state(soc, "%")}, {"battery_soc": "sensor.soc"})
    await forwarder.async_forward()
    assert coordinator.async_write_register.await_args.args[1] == expected


async def test_run_cancels_and_awaits_a_pending_forward_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unload must cancel the owned debounce task and await it (#495 shape)."""
    forwarder, _coordinator = _forwarder({}, {"pv_production": "sensor.pv"})
    unsub = MagicMock()
    with patch(
        "custom_components.idm_heatpump.external_power_forwarding.async_track_state_change_event",
        return_value=unsub,
    ):
        loop_task = asyncio.get_running_loop().create_task(forwarder.async_run())
        try:
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            pending = asyncio.get_running_loop().create_task(asyncio.sleep(60))
            forwarder._pending_task = pending

            loop_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await loop_task

            assert pending.cancelled()
            assert forwarder._pending_task is None or forwarder._pending_task.done()
        finally:
            await asyncio.gather(loop_task, return_exceptions=True)
    unsub.assert_called_once()


async def test_periodic_pass_runs_after_the_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    forwarder, _coordinator = _forwarder({"sensor.pv": _state(1)}, {"pv_production": "sensor.pv"})
    real_sleep = asyncio.sleep

    async def short_sleep(_delay: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(module.asyncio, "sleep", short_sleep)
    unsub = MagicMock()
    with patch(
        "custom_components.idm_heatpump.external_power_forwarding.async_track_state_change_event",
        return_value=unsub,
    ):
        loop_task = asyncio.get_running_loop().create_task(forwarder.async_run())
        try:
            for _ in range(6):
                await asyncio.sleep(0)
            assert _coordinator.async_write_register.await_count >= 2
        finally:
            loop_task.cancel()
            await asyncio.gather(loop_task, return_exceptions=True)


async def test_periodic_pass_refreshes_below_the_controller_ram_hold_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Some firmwares clear GLT RAM inputs about ten seconds after the last write (#493).

    With quiet sources (no events at night) only the periodic pass refreshes
    the registers, so it must run at the firmware-safe cadence regardless of
    the configured fallback interval — a 30-60 s pass let the controller
    forget the battery between writes on the reporter's installation.
    """
    hass = MagicMock()
    hass.states.get.side_effect = {"sensor.soc": _state(90, "%")}.get
    coordinator = MagicMock()
    coordinator.get_register.side_effect = lambda name: SimpleNamespace(
        name=name, writable=True, min_val=0, max_val=100
    )
    coordinator.async_write_register = AsyncMock()
    forwarder = module.ExternalPowerForwarder(
        hass, coordinator, module.ExternalPowerForwardingConfig({"battery_soc": "sensor.soc"}, 60)
    )
    real_sleep = asyncio.sleep
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(module.asyncio, "sleep", record_sleep)
    unsub = MagicMock()
    with patch(
        "custom_components.idm_heatpump.external_power_forwarding.async_track_state_change_event",
        return_value=unsub,
    ):
        loop_task = asyncio.get_running_loop().create_task(forwarder.async_run())
        try:
            for _ in range(200):
                if len(delays) >= 4:
                    break
                await real_sleep(0)
            assert delays == [5.0, 5.0, 5.0, 5.0]
            assert coordinator.async_write_register.await_count >= 4
        finally:
            loop_task.cancel()
            await asyncio.gather(loop_task, return_exceptions=True)


async def test_connection_outage_is_reported_once_until_recovery(caplog: pytest.LogCaptureFixture) -> None:
    """The RAM refresh cadence retries every 5 s; one outage must not spam.

    A proxy outage observed in the wild (#493 maintainer log) repeated the
    per-register delivery warning on every pass for the whole outage.
    """
    forwarder, coordinator = _forwarder(
        {"sensor.pv": _state(1), "sensor.soc": _state(80, "%")},
        {"pv_production": "sensor.pv", "battery_soc": "sensor.soc"},
    )

    def _connection_lost():
        return OSError("could not connect to 192.0.2.9:5020")

    coordinator.async_write_register.side_effect = _connection_lost()
    with caplog.at_level("DEBUG", logger="custom_components.idm_heatpump.external_power_forwarding"):
        for _ in range(4):
            await forwarder.async_forward()

    warnings = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warnings) == 1  # one per outage, not per register per pass
    assert caplog.text.count("still paused") == 7  # every suppressed retry

    # Recovery clears the latch: a later outage is reported again.
    coordinator.async_write_register.side_effect = None
    with caplog.at_level("DEBUG", logger="custom_components.idm_heatpump.external_power_forwarding"):
        await forwarder.async_forward()
        coordinator.async_write_register.side_effect = _connection_lost()
        await forwarder.async_forward()

    assert len([record for record in caplog.records if record.levelname == "WARNING"]) == 2
