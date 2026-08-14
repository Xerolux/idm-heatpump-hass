"""Tests for external humidity forwarding."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump.room_temp_forwarding import (
    HumidityForwarder,
    HumidityForwardingConfig,
    _coerce_humidity,
)


def _make_coordinator():
    reg = RegisterDef(
        1692,
        DataType.FLOAT,
        "ext_humidity",
        unit="%",
        writable=True,
        min_val=0,
        max_val=100,
    )
    coord = MagicMock()
    coord.get_register = MagicMock(side_effect=lambda name: reg if name == reg.name else None)
    coord.async_write_register = AsyncMock()
    return coord, reg


def _make_hass(state="45.0"):
    hass = MagicMock()
    hass.states.get = MagicMock(return_value=SimpleNamespace(state=state))
    return hass


def test_coerce_humidity():
    assert _coerce_humidity("45.0") == 45.0
    assert _coerce_humidity("unknown") is None
    assert _coerce_humidity(float("nan")) is None
    assert _coerce_humidity(float("inf")) is None
    assert _coerce_humidity(-1.0) is None
    assert _coerce_humidity(100.1) is None
    assert _coerce_humidity(0.0) == 0.0
    assert _coerce_humidity(100.0) == 100.0


@pytest.mark.asyncio
async def test_forward_writes_selected_sensor_to_humidity_register():
    coord, reg = _make_coordinator()
    hass = _make_hass("52.3")
    forwarder = HumidityForwarder(
        hass,
        coord,
        HumidityForwardingConfig(entity_id="sensor.living_room_humidity", interval=300, tolerance=2.0),
    )

    await forwarder.async_forward()

    coord.async_write_register.assert_awaited_once_with(reg, 52.3)


@pytest.mark.asyncio
async def test_forward_skips_change_inside_tolerance():
    coord, reg = _make_coordinator()
    hass = _make_hass("50.0")
    forwarder = HumidityForwarder(
        hass,
        coord,
        HumidityForwardingConfig(entity_id="sensor.living_room_humidity", interval=300, tolerance=2.0),
    )

    await forwarder.async_forward()
    hass.states.get.return_value = SimpleNamespace(state="51.0")
    await forwarder.async_forward()

    coord.async_write_register.assert_awaited_once_with(reg, 50.0)


@pytest.mark.asyncio
async def test_forward_ignores_invalid_sensor_state():
    coord, _reg = _make_coordinator()
    hass = _make_hass("unavailable")
    forwarder = HumidityForwarder(
        hass,
        coord,
        HumidityForwardingConfig(entity_id="sensor.living_room_humidity", interval=300, tolerance=2.0),
    )

    await forwarder.async_forward()

    coord.async_write_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_forward_ignores_out_of_range_sensor_state():
    coord, _reg = _make_coordinator()
    hass = _make_hass("150.0")
    forwarder = HumidityForwarder(
        hass,
        coord,
        HumidityForwardingConfig(entity_id="sensor.living_room_humidity", interval=300, tolerance=2.0),
    )

    await forwarder.async_forward()

    coord.async_write_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_forward_noop_when_no_entity_configured():
    coord, _reg = _make_coordinator()
    hass = _make_hass("50.0")
    forwarder = HumidityForwarder(
        hass,
        coord,
        HumidityForwardingConfig(entity_id="", interval=300, tolerance=2.0),
    )

    await forwarder.async_forward()

    coord.async_write_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_loop_continues_after_forward_failure():
    coord, _reg = _make_coordinator()
    hass = _make_hass("50.0")
    forwarder = HumidityForwarder(
        hass,
        coord,
        HumidityForwardingConfig(entity_id="sensor.living_room_humidity", interval=0, tolerance=2.0),
    )
    forwarder.async_forward = AsyncMock(side_effect=[None, Exception("boom"), None])

    run_task = asyncio.create_task(forwarder.async_run())
    for _ in range(10):
        await asyncio.sleep(0)
    await asyncio.sleep(0.05)
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass

    assert forwarder.async_forward.await_count >= 2


def _make_event(entity_id):
    event = MagicMock()
    event.data = {"entity_id": entity_id}
    return event


class TestHandleStateChange:
    def test_creates_forward_task_for_string_entity_id(self):
        coord, _reg = _make_coordinator()
        hass = _make_hass("45.0")
        hass.async_create_task = MagicMock(side_effect=lambda coro: coro.close())
        forwarder = HumidityForwarder(
            hass,
            coord,
            HumidityForwardingConfig(entity_id="sensor.humidity", interval=300, tolerance=2.0),
        )
        forwarder._handle_state_change(_make_event("sensor.humidity"))
        hass.async_create_task.assert_called_once()

    def test_ignores_non_string_entity_id(self):
        coord, _reg = _make_coordinator()
        hass = _make_hass("45.0")
        hass.async_create_task = MagicMock()
        forwarder = HumidityForwarder(
            hass,
            coord,
            HumidityForwardingConfig(entity_id="sensor.humidity", interval=300, tolerance=2.0),
        )
        forwarder._handle_state_change(_make_event(None))
        forwarder._handle_state_change(_make_event(123))
        hass.async_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_run_unsubscribes_state_listener_on_cancel():
    coord, _reg = _make_coordinator()
    hass = _make_hass("45.0")
    unsub = MagicMock()
    import custom_components.idm_heatpump.room_temp_forwarding as rtf_module

    async def _noop_forward() -> None:
        return None

    with patch.object(rtf_module, "async_track_state_change_event", return_value=unsub):
        forwarder = HumidityForwarder(
            hass,
            coord,
            HumidityForwardingConfig(entity_id="sensor.humidity", interval=300, tolerance=2.0),
        )
        forwarder.async_forward = _noop_forward  # type: ignore[method-assign]
        run_task = asyncio.create_task(forwarder.async_run())
        await asyncio.sleep(0)
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass

    unsub.assert_called_once()
    assert forwarder._unsub_state is None
