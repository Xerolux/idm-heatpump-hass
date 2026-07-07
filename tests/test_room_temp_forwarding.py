"""Tests for external room temperature forwarding."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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
    coord.number_descriptions = [{"register": reg, "description": MagicMock(key=reg.name)}]
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
    # Let the initial forward_all and a couple of loop iterations run.
    await asyncio.sleep(0.05)
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass

    assert forwarder.async_forward_all.await_count >= 2
