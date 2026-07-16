"""Tests for external room temperature forwarding."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump.room_temp_forwarding import (
    RoomTempForwarder,
    RoomTempForwardingConfig,
    _coerce_temperature,
)


def _make_coordinator():
    reg = RegisterDef(
        1650,
        DataType.FLOAT,
        "hc_a_ext_room_temp",
        unit="°C",
        writable=True,
        min_val=15,
        max_val=30,
    )
    coord = MagicMock()
    # Forwarder resolves the register by name via the coordinator's cached index.
    coord.get_register = MagicMock(side_effect=lambda name: reg if name == reg.name else None)
    coord.async_write_register = AsyncMock()
    return coord, reg


def _make_hass(state="21.5"):
    hass = MagicMock()
    hass.states.get = MagicMock(return_value=SimpleNamespace(state=state))
    return hass


def test_coerce_temperature():
    assert _coerce_temperature("21.5") == 21.5
    assert _coerce_temperature("unknown") is None
    assert _coerce_temperature(float("nan")) is None
    assert _coerce_temperature(float("inf")) is None


@pytest.mark.asyncio
async def test_forward_entity_writes_selected_sensor_to_matching_register():
    coord, reg = _make_coordinator()
    hass = _make_hass("22.3")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"a": "sensor.living_room_temperature"}, interval=300, tolerance=0.2),
    )

    await forwarder.async_forward_entity("sensor.living_room_temperature")

    coord.async_write_register.assert_awaited_once_with(reg, 22.3)


@pytest.mark.asyncio
async def test_forward_entity_skips_change_inside_tolerance():
    coord, reg = _make_coordinator()
    hass = _make_hass("22.0")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"a": "sensor.living_room_temperature"}, interval=300, tolerance=0.2),
    )

    await forwarder.async_forward_entity("sensor.living_room_temperature")
    hass.states.get.return_value = SimpleNamespace(state="22.1")
    await forwarder.async_forward_entity("sensor.living_room_temperature")

    coord.async_write_register.assert_awaited_once_with(reg, 22.0)


@pytest.mark.asyncio
async def test_forward_entity_ignores_invalid_sensor_state():
    coord, _reg = _make_coordinator()
    hass = _make_hass("unavailable")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"a": "sensor.living_room_temperature"}, interval=300, tolerance=0.2),
    )

    await forwarder.async_forward_entity("sensor.living_room_temperature")

    coord.async_write_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_forward_entity_ignores_out_of_range_sensor_state():
    coord, _reg = _make_coordinator()
    hass = _make_hass("35.0")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"a": "sensor.living_room_temperature"}, interval=300, tolerance=0.2),
    )

    await forwarder.async_forward_entity("sensor.living_room_temperature")

    coord.async_write_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_forward_entity_ignores_unconfigured_sensor():
    coord, _reg = _make_coordinator()
    hass = _make_hass("22.0")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"a": "sensor.living_room_temperature"}, interval=300, tolerance=0.2),
    )

    await forwarder.async_forward_entity("sensor.other_temperature")

    coord.async_write_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_loop_continues_after_forward_all_failure():
    coord, reg = _make_coordinator()
    hass = _make_hass("22.0")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"a": "sensor.living_room_temperature"}, interval=0, tolerance=0.2),
    )
    # First forward_all succeeds, subsequent ones raise but the loop must continue.
    forwarder.async_forward_all = AsyncMock(side_effect=[None, Exception("boom"), None])

    run_task = asyncio.create_task(forwarder.async_run())
    # The loop runs with interval=0, so yield repeatedly to let at least the
    # initial call and the first retry fire before cancelling. Yielding via
    # sleep(0) lets the scheduler advance the task without relying on wall-clock
    # timing, then a short sleep covers the retry.
    for _ in range(10):
        await asyncio.sleep(0)
    await asyncio.sleep(0.05)
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass

    assert forwarder.async_forward_all.await_count >= 2


def _make_event(entity_id):
    """Build a state-change event object shaped like HA's Event."""
    event = MagicMock()
    event.data = {"entity_id": entity_id}
    return event


class TestHandleStateChange:
    def test_creates_forward_task_for_string_entity_id(self):
        coord, _reg = _make_coordinator()
        hass = _make_hass("21.0")
        hass.async_create_task = MagicMock(side_effect=lambda coro: coro.close())
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": "sensor.room_temp"}, interval=300, tolerance=0.2),
        )
        forwarder._handle_state_change(_make_event("sensor.room_temp"))
        hass.async_create_task.assert_called_once()

    def test_ignores_non_string_entity_id(self):
        coord, _reg = _make_coordinator()
        hass = _make_hass("21.0")
        hass.async_create_task = MagicMock()
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": "sensor.room_temp"}, interval=300, tolerance=0.2),
        )
        # None / missing entity_id must not schedule a forward task.
        forwarder._handle_state_change(_make_event(None))
        forwarder._handle_state_change(_make_event(123))
        hass.async_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_run_unsubscribes_state_listeners_on_cancel():
    coord, _reg = _make_coordinator()
    hass = _make_hass("21.0")
    unsub = MagicMock()
    # async_track_state_change_event returns an unsubscribe callable.
    import custom_components.idm_heatpump.room_temp_forwarding as rtf_module

    async def _noop_forward_all() -> None:
        return None

    with patch.object(rtf_module, "async_track_state_change_event", return_value=unsub):
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": "sensor.room_temp"}, interval=300, tolerance=0.2),
        )
        # Use a real coroutine (not an AsyncMock) so no never-awaited coroutine
        # warnings leak when the run loop is cancelled mid-iteration.
        forwarder.async_forward_all = _noop_forward_all  # type: ignore[method-assign]
        run_task = asyncio.create_task(forwarder.async_run())
        await asyncio.sleep(0)
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass

    unsub.assert_called_once()
    assert forwarder._unsub_state == []
