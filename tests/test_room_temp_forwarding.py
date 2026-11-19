"""Tests for external room temperature forwarding."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump.room_temp_forwarding import (
    STORAGE_TEMP_REGISTER_NAMES,
    RoomTempForwarder,
    RoomTempForwardingConfig,
    _coerce_temperature,
    register_for_storage_temp_key,
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


def _make_hass(state="21.5", unit=None):
    hass = MagicMock()
    attributes = {} if unit is None else {"unit_of_measurement": unit}
    hass.states.get = MagicMock(return_value=SimpleNamespace(state=state, attributes=attributes))
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
async def test_forward_entity_converts_fahrenheit_to_celsius():
    """A °F source sensor must not have its bare number written to a °C register.

    68 °F is 20 °C. Writing 68 straight through passes the register bounds
    (68 is a plausible Celsius value there), so the controller silently saw a
    room more than 40 K too warm and stopped heating the circuit.
    """
    coord, reg = _make_coordinator()
    hass = _make_hass("68", unit="°F")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"a": "sensor.living_room_temperature"}, interval=300, tolerance=0.2),
    )

    await forwarder.async_forward_entity("sensor.living_room_temperature")

    coord.async_write_register.assert_awaited_once_with(reg, 20.0)


@pytest.mark.asyncio
async def test_forward_entity_converts_kelvin_to_celsius():
    coord, _reg = _make_coordinator()
    hass = _make_hass("293.15", unit="K")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"a": "sensor.living_room_temperature"}, interval=300, tolerance=0.2),
    )

    await forwarder.async_forward_entity("sensor.living_room_temperature")

    written = coord.async_write_register.await_args.args[1]
    assert written == pytest.approx(20.0)


@pytest.mark.asyncio
async def test_forward_entity_passes_celsius_and_a_missing_unit_through():
    """A template sensor without a unit keeps the behaviour it always had."""
    for unit in ("°C", None):
        coord, reg = _make_coordinator()
        hass = _make_hass("21.5", unit=unit)
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": "sensor.living_room_temperature"}, interval=300, tolerance=0.2),
        )

        await forwarder.async_forward_entity("sensor.living_room_temperature")

        coord.async_write_register.assert_awaited_once_with(reg, 21.5)


@pytest.mark.asyncio
async def test_forward_entity_refuses_a_source_that_is_not_a_temperature(caplog):
    """Picking a humidity or power entity is a configuration mistake, reported once."""
    coord, _reg = _make_coordinator()
    hass = _make_hass("55", unit="%")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"a": "sensor.living_room_humidity"}, interval=300, tolerance=0.2),
    )

    await forwarder.async_forward_entity("sensor.living_room_humidity")
    await forwarder.async_forward_entity("sensor.living_room_humidity")

    coord.async_write_register.assert_not_awaited()
    warnings = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warnings) == 1, "a permanent misconfiguration must not be repeated every cycle"


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
async def test_interval_pass_rewrites_unchanged_value():
    coord, reg = _make_coordinator()
    hass = _make_hass("21.5")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"a": "sensor.living_room_temperature"}, interval=300, tolerance=0.2),
    )

    await forwarder.async_forward_entity("sensor.living_room_temperature")
    assert coord.async_write_register.await_count == 1

    # One interval later the register is rewritten although the source value
    # has not moved: a controller restart wipes the GLT RAM register and an
    # unchanged value would otherwise never be restored.
    forwarder._last_write_monotonic["a"] -= 300.5
    await forwarder.async_forward_entity("sensor.living_room_temperature")

    assert coord.async_write_register.await_count == 2
    coord.async_write_register.assert_any_await(reg, 21.5)


@pytest.mark.asyncio
async def test_recent_refresh_keeps_tolerating_unchanged_value():
    coord, reg = _make_coordinator()
    hass = _make_hass("21.5")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"a": "sensor.living_room_temperature"}, interval=300, tolerance=0.2),
    )

    await forwarder.async_forward_entity("sensor.living_room_temperature")
    # Immediately afterwards the periodic pass must not pile up writes (and
    # must not trip the coordinator write cooldown) for an unchanged value.
    await forwarder.async_forward_all()

    coord.async_write_register.assert_awaited_once_with(reg, 21.5)


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
    coord, _reg = _make_coordinator()
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


def _make_storage_coordinator():
    reg = RegisterDef(
        1716,
        DataType.FLOAT,
        "glt_heat_storage_temp",
        unit="°C",
        writable=True,
    )
    coord = MagicMock()
    coord.get_register = MagicMock(side_effect=lambda name: reg if name == reg.name else None)
    coord.async_write_register = AsyncMock()
    return coord, reg


class TestStorageTempKeyResolution:
    def test_register_for_storage_key_resolves_all_fixed_keys(self):
        coord = MagicMock()
        coord.get_register = MagicMock(side_effect=lambda name: name)

        for key, register_name in STORAGE_TEMP_REGISTER_NAMES.items():
            assert register_for_storage_temp_key(coord, key) == register_name

    def test_register_for_storage_key_returns_none_for_unknown_key(self):
        coord = MagicMock()
        assert register_for_storage_temp_key(coord, "unknown_key") is None
        coord.get_register.assert_not_called()


@pytest.mark.asyncio
async def test_forward_entity_writes_to_storage_register_via_injected_resolver():
    """RoomTempForwarder reused for storage temps via register_for_key/key_label/value_label."""
    coord, reg = _make_storage_coordinator()
    hass = _make_hass("48.5")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"heat_storage": "sensor.heat_storage"}, interval=300, tolerance=0.2),
        register_for_key=register_for_storage_temp_key,
        key_label="storage key",
        value_label="storage temperature",
    )

    await forwarder.async_forward_entity("sensor.heat_storage")

    coord.async_write_register.assert_awaited_once_with(reg, 48.5)


@pytest.mark.asyncio
async def test_forward_entity_skips_unresolvable_storage_key():
    coord, _reg = _make_storage_coordinator()
    hass = _make_hass("48.5")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(entities={"unknown_key": "sensor.mystery"}, interval=300, tolerance=0.2),
        register_for_key=register_for_storage_temp_key,
    )

    await forwarder.async_forward_entity("sensor.mystery")

    coord.async_write_register.assert_not_awaited()


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


class TestStateListenerRunsOnEventLoop:
    """The state listener must be a Home Assistant callback, not an executor job.

    Without ``@callback`` Home Assistant classifies the listener as an executor
    job and runs it in a worker thread, where its ``hass.async_create_task``
    call is a thread-safety violation (#237).
    """

    def test_room_temp_listener_is_marked_as_callback(self):
        coord, _ = _make_coordinator()
        forwarder = RoomTempForwarder(
            _make_hass(),
            coord,
            RoomTempForwardingConfig(entities={"a": "sensor.room_temp"}, interval=300, tolerance=0.2),
        )
        assert getattr(forwarder._handle_state_change, "_hass_callback", False) is True

    def test_humidity_listener_is_marked_as_callback(self):
        from custom_components.idm_heatpump.room_temp_forwarding import (
            HumidityForwarder,
            HumidityForwardingConfig,
        )

        coord, _ = _make_coordinator()
        forwarder = HumidityForwarder(
            _make_hass(),
            coord,
            HumidityForwardingConfig(entity_id="sensor.humidity", interval=300, tolerance=2.0),
        )
        assert getattr(forwarder._handle_state_change, "_hass_callback", False) is True


class TestForwardingLifecycle:
    """Debounce, range checks and write failures of both forwarders.

    Forwarding writes to the heat pump, so a value outside the register range
    or a failed write must never be silently retried in a loop.
    """

    def _forwarder(self, hass, coordinator, entities=None):
        return RoomTempForwarder(
            hass,
            coordinator,
            RoomTempForwardingConfig(
                entities=entities or {"a": "sensor.living_room_temperature"},
                interval=300,
                tolerance=0.2,
            ),
        )

    @pytest.mark.asyncio
    async def test_state_changes_are_debounced_into_one_write(self):
        coord, reg = _make_coordinator()
        hass = _make_hass("22.3")
        hass.async_create_task.side_effect = asyncio.ensure_future
        forwarder = self._forwarder(hass, coord)
        forwarder._debounce_seconds = 0

        event = SimpleNamespace(data={"entity_id": "sensor.living_room_temperature"})
        forwarder._handle_state_change(event)
        first = forwarder._pending_forward_tasks["sensor.living_room_temperature"]
        forwarder._handle_state_change(event)

        assert forwarder._pending_forward_tasks["sensor.living_room_temperature"] is first
        await asyncio.wait_for(first, 2)

        assert not first.cancelled()
        coord.async_write_register.assert_awaited_once_with(reg, 22.3)

    @pytest.mark.asyncio
    async def test_sensor_event_during_write_is_not_cancelled_and_forwards_latest_state(self):
        """A burst while the Modbus write is in flight must not cancel it.

        Cancelling a task that is already writing aborts the FC16 transaction
        mid-flight and starves the write (#493 — the same race #495 fixed for
        external power). Events received during a write schedule a follow-up
        pass that reads the latest state.
        """
        coord, _reg = _make_coordinator()
        hass = _make_hass("22.3")
        hass.async_create_task.side_effect = asyncio.ensure_future
        forwarder = self._forwarder(hass, coord)
        forwarder._debounce_seconds = 0
        started = asyncio.Event()
        release = asyncio.Event()
        writes: list[float] = []

        async def write(_reg, value):
            writes.append(value)
            if len(writes) == 1:
                started.set()
                await release.wait()

        coord.async_write_register = AsyncMock(side_effect=write)

        event = SimpleNamespace(data={"entity_id": "sensor.living_room_temperature"})
        forwarder._handle_state_change(event)
        task = forwarder._pending_forward_tasks["sensor.living_room_temperature"]
        try:
            await asyncio.wait_for(started.wait(), 2)
            hass.states.get = MagicMock(
                return_value=SimpleNamespace(state="22.9", attributes={"unit_of_measurement": "°C"})
            )
            forwarder._handle_state_change(event)
            assert forwarder._pending_forward_tasks["sensor.living_room_temperature"] is task
            release.set()
            await asyncio.wait_for(task, 3)
            assert writes == [22.3, 22.9]
        finally:
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_events_without_an_entity_id_are_ignored(self):
        coord, _reg = _make_coordinator()
        forwarder = self._forwarder(_make_hass(), coord)

        forwarder._handle_state_change(SimpleNamespace(data={}))

        assert forwarder._pending_forward_tasks == {}

    @pytest.mark.asyncio
    async def test_forward_all_covers_every_configured_circuit(self):
        coord, reg = _make_coordinator()
        hass = _make_hass("21.0")
        forwarder = self._forwarder(hass, coord, entities={"a": "sensor.living_room_temperature", "b": ""})

        await forwarder.async_forward_all()

        coord.async_write_register.assert_awaited_once_with(reg, 21.0)

    @pytest.mark.asyncio
    async def test_values_below_the_register_range_are_skipped(self):
        coord, _reg = _make_coordinator()
        forwarder = self._forwarder(_make_hass("5.0"), coord)

        await forwarder.async_forward_entity("sensor.living_room_temperature")

        coord.async_write_register.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_failed_write_is_reported_and_not_remembered(self):
        coord, _reg = _make_coordinator()
        coord.async_write_register = AsyncMock(side_effect=RuntimeError("write rejected"))
        forwarder = self._forwarder(_make_hass("22.0"), coord)

        await forwarder.async_forward_entity("sensor.living_room_temperature")

        assert forwarder._last_written == {}

    @pytest.mark.asyncio
    async def test_run_cancels_pending_work_when_cancelled(self):
        coord, _reg = _make_coordinator()
        hass = _make_hass("22.0")
        unsub = MagicMock()
        forwarder = self._forwarder(hass, coord)

        with patch(
            "custom_components.idm_heatpump.room_temp_forwarding.async_track_state_change_event",
            return_value=unsub,
        ):
            task = asyncio.get_running_loop().create_task(forwarder.async_run())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        unsub.assert_called_once()
        assert forwarder._pending_forward_tasks == {}


class TestHumidityForwarding:
    def _forwarder(self, hass, coordinator, entity_id="sensor.living_room_humidity"):
        from custom_components.idm_heatpump.room_temp_forwarding import (
            HumidityForwarder,
            HumidityForwardingConfig,
        )

        return HumidityForwarder(
            hass,
            coordinator,
            HumidityForwardingConfig(entity_id=entity_id, interval=300, tolerance=1.0),
        )

    def _coordinator(self, *, min_val=0, max_val=100):
        reg = RegisterDef(
            1655,
            DataType.FLOAT,
            "ext_humidity",
            unit="%",
            writable=True,
            min_val=min_val,
            max_val=max_val,
        )
        coord = MagicMock()
        coord.get_register = MagicMock(side_effect=lambda name: reg if name == "ext_humidity" else None)
        coord.async_write_register = AsyncMock()
        return coord, reg

    @pytest.mark.asyncio
    async def test_missing_register_skips_forwarding(self):
        coord, _reg = self._coordinator()
        coord.get_register = MagicMock(return_value=None)
        forwarder = self._forwarder(_make_hass("55"), coord)

        await forwarder.async_forward()

        coord.async_write_register.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_values_outside_the_register_range_are_skipped(self):
        coord, _reg = self._coordinator(min_val=20, max_val=80)
        below = self._forwarder(_make_hass("5"), coord)
        above = self._forwarder(_make_hass("95"), coord)

        await below.async_forward()
        await above.async_forward()

        coord.async_write_register.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_failed_write_is_reported_and_not_remembered(self):
        coord, _reg = self._coordinator()
        coord.async_write_register = AsyncMock(side_effect=RuntimeError("write rejected"))
        forwarder = self._forwarder(_make_hass("55"), coord)

        await forwarder.async_forward()

        assert forwarder._last_written is None

    @pytest.mark.asyncio
    async def test_state_changes_are_debounced_into_one_write(self):
        coord, reg = self._coordinator()
        hass = _make_hass("55")
        hass.async_create_task.side_effect = asyncio.ensure_future
        forwarder = self._forwarder(hass, coord)
        forwarder._debounce_seconds = 0

        event = SimpleNamespace(data={"entity_id": "sensor.living_room_humidity"})
        forwarder._handle_state_change(event)
        first = forwarder._pending_forward_task
        forwarder._handle_state_change(event)

        assert forwarder._pending_forward_task is first
        await asyncio.wait_for(first, 2)

        assert first is not None and not first.cancelled()
        coord.async_write_register.assert_awaited_once_with(reg, 55.0)

    @pytest.mark.asyncio
    async def test_sensor_event_during_write_is_not_cancelled_and_forwards_latest_state(self):
        """A burst while the Modbus write is in flight must not cancel it (#493)."""
        coord, _reg = self._coordinator()
        hass = _make_hass("55")
        hass.async_create_task.side_effect = asyncio.ensure_future
        forwarder = self._forwarder(hass, coord)
        forwarder._debounce_seconds = 0
        started = asyncio.Event()
        release = asyncio.Event()
        writes: list[float] = []

        async def write(_reg, value):
            writes.append(value)
            if len(writes) == 1:
                started.set()
                await release.wait()

        coord.async_write_register = AsyncMock(side_effect=write)

        event = SimpleNamespace(data={"entity_id": "sensor.living_room_humidity"})
        forwarder._handle_state_change(event)
        task = forwarder._pending_forward_task
        try:
            await asyncio.wait_for(started.wait(), 2)
            hass.states.get = MagicMock(
                return_value=SimpleNamespace(state="60", attributes={"unit_of_measurement": "%"})
            )
            forwarder._handle_state_change(event)
            assert forwarder._pending_forward_task is task
            release.set()
            await asyncio.wait_for(task, 3)
            assert writes == [55.0, 60.0]
        finally:
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_events_without_an_entity_id_are_ignored(self):
        coord, _reg = self._coordinator()
        forwarder = self._forwarder(_make_hass("55"), coord)

        forwarder._handle_state_change(SimpleNamespace(data={}))

        assert forwarder._pending_forward_task is None

    @pytest.mark.asyncio
    async def test_run_cancels_pending_work_when_cancelled(self):
        coord, _reg = self._coordinator()
        unsub = MagicMock()
        forwarder = self._forwarder(_make_hass("55"), coord)

        with patch(
            "custom_components.idm_heatpump.room_temp_forwarding.async_track_state_change_event",
            return_value=unsub,
        ):
            task = asyncio.get_running_loop().create_task(forwarder.async_run())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        unsub.assert_called_once()
        assert forwarder._pending_forward_task is None


@pytest.mark.asyncio
async def test_run_cancels_and_awaits_pending_debounce_tasks():
    """Unload cancels owned debounce tasks and awaits them (#500 shape)."""
    coord, _reg = _make_coordinator()
    hass = _make_hass("22.0")
    hass.async_create_task.side_effect = asyncio.ensure_future
    forwarder = TestForwardingLifecycle()._forwarder(hass, coord)
    forwarder._debounce_seconds = 30  # keep the debounce task pending
    unsub = MagicMock()
    with patch(
        "custom_components.idm_heatpump.room_temp_forwarding.async_track_state_change_event",
        return_value=unsub,
    ):
        run_task = asyncio.get_running_loop().create_task(forwarder.async_run())
        await asyncio.sleep(0)
        forwarder._handle_state_change(SimpleNamespace(data={"entity_id": "sensor.living_room_temperature"}))
        pending = forwarder._pending_forward_tasks.get("sensor.living_room_temperature")
        assert pending is not None and not pending.done()

        run_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run_task

        assert pending.cancelled()
        assert forwarder._pending_forward_tasks == {}


@pytest.mark.asyncio
async def test_humidity_run_cancels_and_awaits_its_pending_task():
    coord, _reg = TestHumidityForwarding()._coordinator()
    hass = _make_hass("55")
    hass.async_create_task.side_effect = asyncio.ensure_future
    forwarder = TestHumidityForwarding()._forwarder(hass, coord)
    forwarder._debounce_seconds = 30
    unsub = MagicMock()
    with patch(
        "custom_components.idm_heatpump.room_temp_forwarding.async_track_state_change_event",
        return_value=unsub,
    ):
        run_task = asyncio.get_running_loop().create_task(forwarder.async_run())
        await asyncio.sleep(0)
        forwarder._handle_state_change(SimpleNamespace(data={"entity_id": "sensor.living_room_humidity"}))
        pending = forwarder._pending_forward_task
        assert pending is not None and not pending.done()

        run_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run_task

        assert pending.cancelled()
        assert forwarder._pending_forward_task is None


@pytest.mark.asyncio
async def test_connection_outage_is_reported_once_until_recovery(caplog):
    """Retries during a Modbus outage must not repeat the warning per pass."""
    coord, _reg = _make_coordinator()
    hass = _make_hass("22.0")
    forwarder = TestForwardingLifecycle()._forwarder(hass, coord)
    lost = OSError("could not connect to 192.0.2.9:5020")
    coord.async_write_register = AsyncMock(side_effect=lost)
    with caplog.at_level("DEBUG"):
        for _ in range(3):
            await forwarder.async_forward_entity("sensor.living_room_temperature")

    assert caplog.text.count("Could not forward room temperature") == 1  # user-facing line once
    outage_lines = [r for r in caplog.records if "Could not forward room temperature" in r.getMessage()]
    # Gray, not red: connection blips that self-heal must not read as errors.
    assert outage_lines[0].levelname == "INFO"
    assert caplog.text.count("still paused") == 2

    coord.async_write_register.side_effect = None
    hass.states.get = MagicMock(return_value=SimpleNamespace(state="22.9", attributes={"unit_of_measurement": "°C"}))
    with caplog.at_level("DEBUG"):
        await forwarder.async_forward_entity("sensor.living_room_temperature")
        coord.async_write_register.side_effect = lost
        hass.states.get = MagicMock(
            return_value=SimpleNamespace(state="23.5", attributes={"unit_of_measurement": "°C"})
        )
        await forwarder.async_forward_entity("sensor.living_room_temperature")

    assert caplog.text.count("Could not forward room temperature") == 2


@pytest.mark.asyncio
async def test_humidity_connection_outage_is_reported_once(caplog):
    coord, _reg = TestHumidityForwarding()._coordinator()
    forwarder = TestHumidityForwarding()._forwarder(_make_hass("55"), coord)
    lost = OSError("could not connect to 192.0.2.9:5020")
    coord.async_write_register = AsyncMock(side_effect=lost)
    with caplog.at_level("DEBUG"):
        for _ in range(3):
            await forwarder.async_forward()

    assert caplog.text.count("Could not forward humidity") == 1
    humidity_lines = [r for r in caplog.records if "Could not forward humidity" in r.getMessage()]
    # Gray, not red: connection blips that self-heal must not read as errors.
    assert humidity_lines[0].levelname == "INFO"
    assert caplog.text.count("still paused") == 2


@pytest.mark.asyncio
async def test_forward_all_deduplicates_shared_entity_across_circuits():
    """Sharing one room sensor across circuits A and B must write each circuit only once per pass."""
    reg_a = RegisterDef(1650, DataType.FLOAT, "hc_a_ext_room_temp", unit="°C", writable=True)
    reg_b = RegisterDef(1652, DataType.FLOAT, "hc_b_ext_room_temp", unit="°C", writable=True)
    coord = MagicMock()
    coord.get_register = MagicMock(
        side_effect=lambda name: {"hc_a_ext_room_temp": reg_a, "hc_b_ext_room_temp": reg_b}.get(name)
    )
    coord.async_write_register = AsyncMock()
    hass = _make_hass("21.5")
    forwarder = RoomTempForwarder(
        hass,
        coord,
        RoomTempForwardingConfig(
            entities={"a": "sensor.shared_room", "b": "sensor.shared_room"},
            interval=300,
            tolerance=0.0,
        ),
    )

    await forwarder.async_forward_all()

    assert coord.async_write_register.await_count == 2
    coord.async_write_register.assert_any_await(reg_a, 21.5)
    coord.async_write_register.assert_any_await(reg_b, 21.5)


@pytest.mark.asyncio
async def test_write_cooldown_is_logged_at_debug_for_room_temp_and_humidity(caplog):
    """A write-cooldown rejection from a manual write must log at DEBUG, not WARNING."""
    from custom_components.idm_heatpump.room_temp_forwarding import (
        HumidityForwarder,
        HumidityForwardingConfig,
    )

    cooldown_err = ValueError("Cooldown active for register 1650 (2.1s remaining)")
    coord, _reg = _make_coordinator()
    coord.async_write_register = AsyncMock(side_effect=cooldown_err)
    rt_forwarder = TestForwardingLifecycle()._forwarder(_make_hass("22.0"), coord)

    h_coord, _h_reg = TestHumidityForwarding()._coordinator()
    h_coord.async_write_register = AsyncMock(side_effect=cooldown_err)
    h_forwarder = HumidityForwarder(
        _make_hass("55"),
        h_coord,
        HumidityForwardingConfig(entity_id="sensor.humidity", interval=300, tolerance=1.0),
    )

    with caplog.at_level("DEBUG"):
        await rt_forwarder.async_forward_entity("sensor.living_room_temperature")
        await h_forwarder.async_forward()

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert warnings == []
    assert any("write cooldown active" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# Multi-source averaging, offsets, sentinel, season window and controls
# ---------------------------------------------------------------------------


def _make_coordinator_with_sentinel(*, sentinel=(-1.0,)):
    reg = RegisterDef(
        1650,
        DataType.FLOAT,
        "hc_a_ext_room_temp",
        unit="°C",
        writable=True,
        min_val=15,
        max_val=30,
        sentinel_values=sentinel,
    )
    coord = MagicMock()
    coord.get_register = MagicMock(side_effect=lambda name: reg if name == reg.name else None)
    coord.async_write_register = AsyncMock()
    return coord, reg


def _multi_source_hass(states: dict[str, str]):
    hass = MagicMock()

    def get(entity_id):
        state = states.get(entity_id)
        if state is None:
            return None
        return SimpleNamespace(state=state, attributes={})

    hass.states.get = MagicMock(side_effect=get)
    return hass


class TestSeasonWindow:
    def test_no_window_is_always_in_season(self):
        from datetime import date

        from custom_components.idm_heatpump.room_temp_forwarding import date_in_season

        assert date_in_season(date(2026, 7, 1), None) is True

    def test_regular_window(self):
        from datetime import date

        from custom_components.idm_heatpump.room_temp_forwarding import SeasonWindow, date_in_season

        window = SeasonWindow((10, 1), (4, 30))
        assert date_in_season(date(2026, 11, 19), window) is True
        assert date_in_season(date(2026, 10, 1), window) is True
        assert date_in_season(date(2026, 4, 30), window) is True
        assert date_in_season(date(2026, 7, 1), window) is False

    def test_wrapping_window_covers_both_sides_of_the_year_end(self):
        from datetime import date

        from custom_components.idm_heatpump.room_temp_forwarding import SeasonWindow, date_in_season

        window = SeasonWindow((10, 1), (4, 30))
        assert date_in_season(date(2026, 2, 15), window) is True
        assert date_in_season(date(2026, 12, 31), window) is True
        assert date_in_season(date(2026, 1, 1), window) is True
        assert date_in_season(date(2026, 9, 30), window) is False
        assert date_in_season(date(2026, 5, 1), window) is False

    def test_single_day_window(self):
        from datetime import date

        from custom_components.idm_heatpump.room_temp_forwarding import SeasonWindow, date_in_season

        window = SeasonWindow((3, 15), (3, 15))
        assert date_in_season(date(2026, 3, 15), window) is True
        assert date_in_season(date(2026, 3, 14), window) is False
        assert date_in_season(date(2026, 3, 16), window) is False

    def test_from_options_requires_month_and_day(self):
        from custom_components.idm_heatpump.const import (
            CONF_ROOM_TEMP_FORWARDING_SEASON_END_DAY,
            CONF_ROOM_TEMP_FORWARDING_SEASON_END_MONTH,
            CONF_ROOM_TEMP_FORWARDING_SEASON_START_DAY,
            CONF_ROOM_TEMP_FORWARDING_SEASON_START_MONTH,
        )
        from custom_components.idm_heatpump.room_temp_forwarding import season_window_from_options

        keys = (
            CONF_ROOM_TEMP_FORWARDING_SEASON_START_MONTH,
            CONF_ROOM_TEMP_FORWARDING_SEASON_START_DAY,
            CONF_ROOM_TEMP_FORWARDING_SEASON_END_MONTH,
            CONF_ROOM_TEMP_FORWARDING_SEASON_END_DAY,
        )
        assert season_window_from_options({}) is None
        assert season_window_from_options(dict.fromkeys(keys, 0)) is None
        assert season_window_from_options({keys[0]: 13, keys[1]: 1, keys[2]: 4, keys[3]: 30}) is None
        assert season_window_from_options({keys[0]: 10, keys[1]: 32, keys[2]: 4, keys[3]: 30}) is None
        window = season_window_from_options({keys[0]: 10, keys[1]: 1, keys[2]: 4, keys[3]: 30})
        assert window is not None
        assert window.start == (10, 1)
        assert window.end == (4, 30)

    def test_from_options_clamps_february_30(self):
        from datetime import date

        from custom_components.idm_heatpump.const import (
            CONF_ROOM_TEMP_FORWARDING_SEASON_END_DAY,
            CONF_ROOM_TEMP_FORWARDING_SEASON_END_MONTH,
            CONF_ROOM_TEMP_FORWARDING_SEASON_START_DAY,
            CONF_ROOM_TEMP_FORWARDING_SEASON_START_MONTH,
        )
        from custom_components.idm_heatpump.room_temp_forwarding import date_in_season, season_window_from_options

        window = season_window_from_options(
            {
                CONF_ROOM_TEMP_FORWARDING_SEASON_START_MONTH: 2,
                CONF_ROOM_TEMP_FORWARDING_SEASON_START_DAY: 30,
                CONF_ROOM_TEMP_FORWARDING_SEASON_END_MONTH: 3,
                CONF_ROOM_TEMP_FORWARDING_SEASON_END_DAY: 10,
            }
        )
        assert window is not None
        assert window.start[0] == 2
        assert window.start[1] <= 29
        assert date_in_season(date(2026, 2, 28), window) is True


class TestNormalizeSourcesAndOffsets:
    def test_normalize_sources_accepts_all_shapes(self):
        from custom_components.idm_heatpump.room_temp_forwarding import normalize_sources

        assert normalize_sources("sensor.one") == ["sensor.one"]
        assert normalize_sources("  sensor.one  ") == ["sensor.one"]
        assert normalize_sources(["sensor.one", "sensor.two"]) == ["sensor.one", "sensor.two"]
        assert normalize_sources(("sensor.one", " sensor.one ", "")) == ["sensor.one"]
        assert normalize_sources("") == []
        assert normalize_sources([]) == []
        assert normalize_sources(None) == []
        assert normalize_sources(5) == []

    def test_offsets_from_options_clamps_and_skips_junk(self):
        from custom_components.idm_heatpump.const import CONF_ROOM_TEMP_FORWARDING_OFFSETS
        from custom_components.idm_heatpump.room_temp_forwarding import offsets_from_options

        assert offsets_from_options({}) == {}
        assert offsets_from_options({CONF_ROOM_TEMP_FORWARDING_OFFSETS: "junk"}) == {}
        assert offsets_from_options({CONF_ROOM_TEMP_FORWARDING_OFFSETS: {"a": 1.5, "b": 0.0}}) == {"a": 1.5}
        clamped = offsets_from_options({CONF_ROOM_TEMP_FORWARDING_OFFSETS: {"a": 99.0, "b": -99.0}})
        assert clamped == {"a": 5.0, "b": -5.0}
        assert offsets_from_options({CONF_ROOM_TEMP_FORWARDING_OFFSETS: {"a": "warm", "b": "2"}}) == {"b": 2.0}
        assert offsets_from_options({CONF_ROOM_TEMP_FORWARDING_OFFSETS: {"a": float("nan")}}) == {}


class TestMultiSourceAveraging:
    async def test_two_sensors_are_averaged_and_rounded(self):
        coord, reg = _make_coordinator()
        hass = _multi_source_hass({"sensor.one": "21.54", "sensor.two": "22.33"})
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.one", "sensor.two"]}, interval=300, tolerance=0.2),
        )
        await forwarder.async_forward_all()
        coord.async_write_register.assert_awaited_once_with(reg, 21.9)

    async def test_offset_is_added_after_averaging(self):
        coord, reg = _make_coordinator()
        hass = _multi_source_hass({"sensor.one": "20.0", "sensor.two": "21.0"})
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(
                entities={"a": ["sensor.one", "sensor.two"]},
                interval=300,
                tolerance=0.2,
                offsets={"a": -1.5},
            ),
        )
        await forwarder.async_forward_all()
        # (20.0 + 21.0) / 2 = 20.5, then the -1.5 K offset applies.
        coord.async_write_register.assert_awaited_once_with(reg, 19.0)

    async def test_offset_pushing_out_of_bounds_is_skipped_with_a_warning(self, caplog):
        coord, _reg = _make_coordinator()
        hass = _multi_source_hass({"sensor.one": "29.5"})
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(
                entities={"a": ["sensor.one"]},
                interval=300,
                tolerance=0.2,
                offsets={"a": 5.0},
            ),
        )
        with caplog.at_level("WARNING"):
            await forwarder.async_forward_all()
        coord.async_write_register.assert_not_awaited()
        assert any("is above" in record.getMessage() for record in caplog.records)

    async def test_legacy_single_entity_string_still_forwards(self):
        coord, reg = _make_coordinator()
        hass = _multi_source_hass({"sensor.one": "21.5"})
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": "sensor.one"}, interval=300, tolerance=0.2),
        )
        await forwarder.async_forward_all()
        coord.async_write_register.assert_awaited_once_with(reg, 21.5)

    async def test_unavailable_sources_are_excluded_from_the_average(self):
        coord, reg = _make_coordinator()
        hass = _multi_source_hass({"sensor.one": "21.0", "sensor.two": "unknown"})
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.one", "sensor.two"]}, interval=300, tolerance=0.2),
        )
        await forwarder.async_forward_all()
        coord.async_write_register.assert_awaited_once_with(reg, 21.0)

    async def test_all_sources_unavailable_writes_the_documented_sentinel(self):
        coord, reg = _make_coordinator_with_sentinel()
        hass = _multi_source_hass({"sensor.one": "unavailable", "sensor.two": None})
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.one", "sensor.two"]}, interval=300, tolerance=0.2),
        )
        await forwarder.async_forward_all()
        coord.async_write_register.assert_awaited_once_with(reg, -1.0)
        assert forwarder._last_written["a"] == -1.0

    async def test_no_sentinel_documented_means_no_write(self):
        coord, _reg = _make_coordinator_with_sentinel(sentinel=None)
        hass = _multi_source_hass({"sensor.one": "unavailable"})
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.one"]}, interval=300, tolerance=0.2),
        )
        await forwarder.async_forward_all()
        coord.async_write_register.assert_not_awaited()

    async def test_recovery_from_sentinel_rewrites_the_value(self):
        coord, reg = _make_coordinator_with_sentinel()
        hass = _multi_source_hass({"sensor.one": "unavailable"})
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.one"]}, interval=300, tolerance=0.2),
        )
        await forwarder.async_forward_all()
        assert coord.async_write_register.await_args.args == (reg, -1.0)

        _multi_source_hass({"sensor.one": "22.0"})
        forwarder._hass = _multi_source_hass({"sensor.one": "22.0"})
        await forwarder.async_forward_all()
        assert coord.async_write_register.await_args.args == (reg, 22.0)

    async def test_disabled_source_is_excluded_from_the_average(self):
        coord, reg = _make_coordinator()
        hass = _multi_source_hass({"sensor.one": "30.0", "sensor.two": "20.0"})
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.one", "sensor.two"]}, interval=300, tolerance=0.2),
        )
        # Disabling one side of a 30/20 average re-forwards the circuit at
        # once; only sensor.two contributes.
        await forwarder.async_set_source_enabled("a", "sensor.one", False)
        coord.async_write_register.assert_awaited_once_with(reg, 20.0)

    async def test_switching_the_last_source_off_writes_the_sentinel(self):
        coord, reg = _make_coordinator_with_sentinel()
        hass = _multi_source_hass({"sensor.one": "21.0"})
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.one"]}, interval=300, tolerance=0.2),
        )
        coord.async_write_register.reset_mock()
        await forwarder.async_set_source_enabled("a", "sensor.one", False)
        coord.async_write_register.assert_awaited_once_with(reg, -1.0)


class TestForwardingControls:
    def _forwarder(self, hass, coord, **config_kwargs):
        return RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.one"]}, interval=300, tolerance=0.2, **config_kwargs),
            persist_key="idm_heatpump.room_forwarding.test",
        )

    async def test_master_switch_off_stops_writes_and_on_resumes_immediately(self):
        coord, _reg = _make_coordinator()
        hass = _multi_source_hass({"sensor.one": "21.5"})
        forwarder = self._forwarder(hass, coord)
        assert forwarder.master_enabled is True
        assert forwarder.forwarding_active is True

        await forwarder.async_set_master_enabled(False)
        coord.async_write_register.reset_mock()
        await forwarder.async_forward_all()
        coord.async_write_register.assert_not_awaited()
        assert forwarder.forwarding_active is False

        coord.async_write_register.reset_mock()
        await forwarder.async_set_master_enabled(True)
        coord.async_write_register.assert_awaited_once()

    async def test_out_of_season_writes_nothing_even_with_master_on(self, monkeypatch):
        from datetime import date

        from custom_components.idm_heatpump import room_temp_forwarding as module
        from custom_components.idm_heatpump.room_temp_forwarding import SeasonWindow

        class _FixedDate(date):
            @classmethod
            def today(cls):
                return cls(2026, 12, 24)

        monkeypatch.setattr(module, "date", _FixedDate)
        coord, _reg = _make_coordinator()
        hass = _multi_source_hass({"sensor.one": "21.5"})
        forwarder = self._forwarder(hass, coord, season=SeasonWindow((7, 1), (8, 31)))
        coord.async_write_register.reset_mock()
        await forwarder.async_forward_all()
        coord.async_write_register.assert_not_awaited()
        assert forwarder.master_enabled is True
        assert forwarder.forwarding_active is False
        assert forwarder.season_active(date(2026, 7, 15)) is True

    async def test_explicit_date_respects_the_season_window(self):
        from datetime import date

        from custom_components.idm_heatpump.room_temp_forwarding import SeasonWindow

        coord, _reg = _make_coordinator()
        hass = _multi_source_hass({"sensor.one": "21.5"})
        forwarder = self._forwarder(hass, coord, season=SeasonWindow((1, 1), (12, 31)))
        assert forwarder.season_active(date(2026, 6, 1)) is True
        narrow = self._forwarder(hass, coord, season=SeasonWindow((6, 1), (6, 30)))
        assert narrow.season_active(date(2026, 6, 15)) is True
        assert narrow.season_active(date(2026, 7, 15)) is False

    async def test_controls_persist_and_restore(self):
        from homeassistant.helpers.storage import Store

        coord, _reg = _make_coordinator()
        hass = _multi_source_hass({"sensor.one": "21.5", "sensor.two": "22.5"})
        forwarder = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.one", "sensor.two"]}, interval=300, tolerance=0.2),
            persist_key="idm_heatpump.room_forwarding.persist_test",
        )
        await forwarder.async_set_master_enabled(False)
        await forwarder.async_set_source_enabled("a", "sensor.two", False)

        restored = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.one", "sensor.two"]}, interval=300, tolerance=0.2),
            persist_key="idm_heatpump.room_forwarding.persist_test",
        )
        # The storage stub keeps its data per Store instance; simulate the
        # on-disk persistence by handing the saved document to the new store.
        restored._store.data = forwarder._store.data
        await restored.async_load_controls()
        assert restored.master_enabled is False
        assert restored.source_enabled("a", "sensor.one") is True
        assert restored.source_enabled("a", "sensor.two") is False
        assert isinstance(restored._store, Store)

    async def test_load_controls_drops_sources_that_are_no_longer_configured(self):
        coord, _reg = _make_coordinator()
        hass = _multi_source_hass({})
        original = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.old"], "b": ["sensor.keep"]}, interval=300, tolerance=0.2),
            persist_key="idm_heatpump.room_forwarding.prune_test",
        )
        original._disabled_sources = {("a", "sensor.old"), ("b", "sensor.keep")}
        await original._async_save_controls()

        changed = RoomTempForwarder(
            hass,
            coord,
            RoomTempForwardingConfig(entities={"b": ["sensor.keep"]}, interval=300, tolerance=0.2),
            persist_key="idm_heatpump.room_forwarding.prune_test",
        )
        changed._store.data = original._store.data
        await changed.async_load_controls()
        assert changed._disabled_sources == {("b", "sensor.keep")}

    async def test_load_controls_without_a_store_is_a_noop(self):
        coord, _reg = _make_coordinator()
        forwarder = RoomTempForwarder(
            _multi_source_hass({"sensor.one": "21.5"}),
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.one"]}, interval=300, tolerance=0.2),
        )
        await forwarder.async_load_controls()
        assert forwarder.master_enabled is True

    async def test_load_controls_survives_a_broken_store(self, caplog):
        coord, _reg = _make_coordinator()
        forwarder = self._forwarder(_multi_source_hass({}), coord)
        forwarder._store.async_load = AsyncMock(side_effect=RuntimeError("boom"))
        with caplog.at_level("WARNING"):
            await forwarder.async_load_controls()
        assert forwarder.master_enabled is True
        assert any("Could not load persisted" in record.getMessage() for record in caplog.records)

    async def test_save_controls_survives_a_broken_store(self, caplog):
        coord, _reg = _make_coordinator()
        forwarder = self._forwarder(_multi_source_hass({}), coord)
        forwarder._store.async_save = AsyncMock(side_effect=RuntimeError("boom"))
        with caplog.at_level("WARNING"):
            await forwarder.async_set_master_enabled(False)
        assert forwarder.master_enabled is False
        assert any("Could not persist" in record.getMessage() for record in caplog.records)

    async def test_unknown_source_switch_is_ignored(self):
        coord, _reg = _make_coordinator()
        forwarder = self._forwarder(_multi_source_hass({}), coord)
        await forwarder.async_set_source_enabled("a", "sensor.unknown", False)
        assert forwarder.source_enabled("a", "sensor.unknown") is True


class TestRoomForwardingEntities:
    def _coordinator_with_entry(self):
        coord, _reg = _make_coordinator()
        coord.config_entry = SimpleNamespace(entry_id="test_entry")
        return coord

    def _forwarder(self, coord):
        return RoomTempForwarder(
            _multi_source_hass({"sensor.one": "21.0", "sensor.two": "22.0"}),
            coord,
            RoomTempForwardingConfig(entities={"a": ["sensor.one", "sensor.two"]}, interval=300, tolerance=0.2),
            persist_key="idm_heatpump.room_forwarding.entity_test",
        )

    def test_factory_builds_master_and_source_switches(self):
        from custom_components.idm_heatpump.room_forwarding_entities import (
            room_forwarding_switch_entities,
        )

        coord = self._coordinator_with_entry()
        entities = room_forwarding_switch_entities(coord, self._forwarder(coord))
        keys = [type(entity).__name__ for entity in entities]
        assert keys.count("IdmRoomForwardingMasterSwitch") == 1
        assert keys.count("IdmRoomForwardingSourceSwitch") == 2

    async def test_master_switch_reflects_and_drives_the_forwarder(self):
        from custom_components.idm_heatpump.room_forwarding_entities import (
            IdmRoomForwardingMasterSwitch,
        )

        coord = self._coordinator_with_entry()
        forwarder = self._forwarder(coord)
        switch = IdmRoomForwardingMasterSwitch(coord, forwarder)
        assert switch.is_on is True
        assert switch.available is True
        assert switch._attr_unique_id.endswith("room_temp_forwarding_active")
        assert switch.extra_state_attributes["season_start"] is None
        assert switch.extra_state_attributes["in_season"] is True
        assert switch.extra_state_attributes["forwarding_active"] is True

        await switch.async_turn_off()
        assert forwarder.master_enabled is False
        assert switch.extra_state_attributes["forwarding_active"] is False
        await switch.async_turn_on()
        assert forwarder.master_enabled is True

    async def test_master_switch_attributes_render_the_season_window(self):
        from custom_components.idm_heatpump.room_forwarding_entities import (
            IdmRoomForwardingMasterSwitch,
        )
        from custom_components.idm_heatpump.room_temp_forwarding import SeasonWindow

        coord = self._coordinator_with_entry()
        forwarder = RoomTempForwarder(
            _multi_source_hass({"sensor.one": "21.0"}),
            coord,
            RoomTempForwardingConfig(
                entities={"a": ["sensor.one"]},
                interval=300,
                tolerance=0.2,
                season=SeasonWindow((10, 1), (4, 30)),
            ),
            persist_key="idm_heatpump.room_forwarding.entity_test",
        )
        switch = IdmRoomForwardingMasterSwitch(coord, forwarder)
        attributes = switch.extra_state_attributes
        assert attributes["season_start"] == "10-01"
        assert attributes["season_end"] == "04-30"
        assert attributes["in_season"] in (True, False)  # today decides; labels are asserted above

    async def test_source_switch_reflects_and_drives_the_forwarder(self):
        from custom_components.idm_heatpump.room_forwarding_entities import (
            IdmRoomForwardingSourceSwitch,
        )

        coord = self._coordinator_with_entry()
        forwarder = self._forwarder(coord)
        switch = IdmRoomForwardingSourceSwitch(coord, forwarder, "a", "sensor.one")
        assert switch.is_on is True
        assert switch.available is True
        assert switch._attr_translation_placeholders == {"circuit": "A", "source": "sensor.one"}
        assert switch._attr_unique_id.endswith("room_temp_source_a_sensor_one")

        await switch.async_turn_off()
        assert forwarder.source_enabled("a", "sensor.one") is False
        await switch.async_turn_on()
        assert forwarder.source_enabled("a", "sensor.one") is True
