"""Tests for the KNX bridge.

The bridge never talks to a bus itself: it calls the Home Assistant KNX
integration's services and listens for its events. These tests therefore
assert on the service calls and on what an incoming ``knx_event`` writes
back into the heat pump.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump.knx_bridge import (
    EVENT_KNX,
    KNX_DOMAIN,
    KnxBridge,
    KnxBridgeConfig,
    _coerce_incoming,
    _coerce_outgoing,
    _retry_delay_from_write_error,
)

OUTDOOR = RegisterDef(1000, DataType.FLOAT, "outdoor_temp", unit="°C")
SYSTEM_MODE = RegisterDef(1005, DataType.UCHAR, "system_mode", writable=True)
HC_A_MODE = RegisterDef(1393, DataType.UCHAR, "hc_a_mode", writable=True)
DEMAND_HEATING = RegisterDef(1710, DataType.BOOL, "demand_heating", writable=True)
ACK = RegisterDef(1999, DataType.UCHAR, "error_acknowledge", writable=True, write_only=True)
HC_D_SETPOINT = RegisterDef(
    1407,
    DataType.FLOAT,
    "hc_d_room_setpoint_heat_normal",
    writable=True,
    eeprom_sensitive=True,
)

REGISTERS = {reg.name: reg for reg in (OUTDOOR, SYSTEM_MODE, HC_A_MODE, DEMAND_HEATING, ACK)}


def _make_hass(*, knx_loaded=True):
    hass = MagicMock()
    hass.config.components = {"idm_heatpump"} | ({KNX_DOMAIN} if knx_loaded else set())
    hass.services.has_service = MagicMock(return_value=knx_loaded)
    hass.services.async_call = AsyncMock()
    hass.bus.async_listen = MagicMock(return_value=MagicMock())
    hass.async_create_task = MagicMock(side_effect=lambda coro: asyncio.ensure_future(coro))
    return hass


def _make_coordinator(data=None, *, registers=REGISTERS):
    coordinator = MagicMock()
    coordinator.data = data if data is not None else {"outdoor_temp": 7.5, "system_mode": 1, "hc_a_mode": 2}
    coordinator.get_register = MagicMock(side_effect=registers.get)
    coordinator.is_register_unused = MagicMock(return_value=False)
    coordinator.async_add_listener = MagicMock(return_value=MagicMock())
    coordinator.async_write_register = AsyncMock()
    return coordinator


def _config(**kwargs):
    defaults = {
        "base_address": "8/0/0",
        "groups": ("system", "heat_pump", "heating_circuits", "glt"),
        "send_gap": 0.0,
        "write_debounce": 0.0,
        "write_cooldown": 0.0,
        "eeprom_write_interval": 0.0,
    }
    defaults.update(kwargs)
    return KnxBridgeConfig(**defaults)


async def _drain(bridge):
    """Let the send worker empty its queue."""
    for _ in range(200):
        if bridge._queue.empty():
            break
        await asyncio.sleep(0)
    await asyncio.sleep(0)


class TestPayloadCoercion:
    @pytest.mark.parametrize(
        ("value", "dpt", "expected"),
        [
            (7.5, "9.001", 7.5),
            (7.5, "7.001", 8),
            (2, "5.010", 2),
            (True, None, 1),
            (0, None, 0),
            (float("nan"), "9.001", None),
            (float("inf"), "9.001", None),
            (None, "9.001", None),
            ("Heizen", "7.001", None),
        ],
    )
    def test_outgoing(self, value, dpt, expected):
        assert _coerce_outgoing(value, dpt) == expected

    @pytest.mark.parametrize(
        ("value", "register", "expected"),
        [
            (7.5, OUTDOOR, 7.5),
            (2.4, SYSTEM_MODE, 2),
            (1, DEMAND_HEATING, True),
            (0, DEMAND_HEATING, False),
            ((1,), DEMAND_HEATING, True),
            ("nope", OUTDOOR, None),
            (float("nan"), OUTDOOR, None),
        ],
    )
    def test_incoming(self, value, register, expected):
        assert _coerce_incoming(value, register) == expected

    def test_production_config_uses_a_write_quiet_period(self):
        assert KnxBridgeConfig(base_address="8/0/0").write_debounce > 0


class TestWriteRetryDelay:
    def test_reads_the_home_assistant_cooldown_placeholder(self):
        err = HomeAssistantError(
            translation_key="write_cooldown_active",
            translation_placeholders={"remaining": "2.3"},
        )
        assert _retry_delay_from_write_error(err) == 2.3

    def test_reads_the_api_eeprom_guard_message(self):
        err = ValueError("EEPROM-sensitive register was written too recently (try again in 25.5s)")
        assert _retry_delay_from_write_error(err, eeprom_fallback=60.0) == 25.5

    def test_uses_the_configured_eeprom_interval_as_a_safe_fallback(self):
        err = ValueError("EEPROM write cycle protection is active")
        assert _retry_delay_from_write_error(err, eeprom_fallback=60.0) == 60.0

    def test_does_not_retry_a_device_or_connection_error(self):
        assert _retry_delay_from_write_error(RuntimeError("bus off"), eeprom_fallback=60.0) is None


class TestStart:
    async def test_stays_idle_and_raises_a_repair_issue_without_knx(self):
        hass = _make_hass(knx_loaded=False)
        bridge = KnxBridge(hass, _make_coordinator(), _config(), entry_id="entry")
        await bridge.async_start()
        hass.services.async_call.assert_not_called()
        assert bridge.group_addresses == {}

    async def test_resolves_only_registers_the_controller_exposes(self):
        hass = _make_hass()
        bridge = KnxBridge(hass, _make_coordinator(), _config(send_enabled=False, receive_enabled=False), entry_id="e")
        await bridge.async_start()
        assert bridge.group_addresses == {
            "outdoor_temp": "8/0/1",
            "system_mode": "8/0/4",
            "hc_a_mode": "8/0/222",
            # Write-only: reachable from the bus, never published to it.
            "error_acknowledge": "8/1/243",
        }

    async def test_registers_writable_objects_for_events(self):
        hass = _make_hass()
        bridge = KnxBridge(hass, _make_coordinator(), _config(send_enabled=False), entry_id="e")
        await bridge.async_start()
        registered = [c for c in hass.services.async_call.call_args_list if c.args[1] == "event_register"]
        addresses = {address for call in registered for address in call.args[2]["address"]}
        assert addresses == {"8/0/4", "8/0/222", "8/1/243"}
        hass.bus.async_listen.assert_called_once()
        assert hass.bus.async_listen.call_args.args[0] == EVENT_KNX
        await bridge.async_stop()

    async def test_stop_deregisters_the_addresses(self):
        hass = _make_hass()
        bridge = KnxBridge(hass, _make_coordinator(), _config(send_enabled=False), entry_id="e")
        await bridge.async_start()
        hass.services.async_call.reset_mock()
        await bridge.async_stop()
        removals = [c for c in hass.services.async_call.call_args_list if c.args[2].get("remove")]
        assert removals


class TestSending:
    async def test_sends_every_readable_value_on_the_first_update(self):
        hass = _make_hass()
        bridge = KnxBridge(hass, _make_coordinator(), _config(receive_enabled=False), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        sends = {c.args[2]["address"]: c.args[2] for c in hass.services.async_call.call_args_list}
        assert sends["8/0/1"] == {"address": "8/0/1", "type": "9.001", "payload": 7.5}
        assert sends["8/0/4"] == {"address": "8/0/4", "type": "5.010", "payload": 1}
        # Write-only registers carry no value and must never be published.
        assert "8/1/243" not in sends
        await bridge.async_stop()

    async def test_repeats_nothing_while_values_hold_still(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = KnxBridge(hass, coordinator, _config(receive_enabled=False), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        hass.services.async_call.reset_mock()

        bridge._handle_coordinator_update()
        await _drain(bridge)
        hass.services.async_call.assert_not_called()
        await bridge.async_stop()

    async def test_small_moves_stay_inside_the_tolerance(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = KnxBridge(hass, coordinator, _config(receive_enabled=False, tolerance=0.5), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        hass.services.async_call.reset_mock()

        coordinator.data = dict(coordinator.data, outdoor_temp=7.7)
        bridge._handle_coordinator_update()
        await _drain(bridge)
        assert not [c for c in hass.services.async_call.call_args_list if c.args[2]["address"] == "8/0/1"]

        coordinator.data = dict(coordinator.data, outdoor_temp=9.0)
        bridge._handle_coordinator_update()
        await _drain(bridge)
        assert [c for c in hass.services.async_call.call_args_list if c.args[2]["address"] == "8/0/1"]
        await bridge.async_stop()

    async def test_skips_values_the_controller_reports_as_unused(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        coordinator.is_register_unused = MagicMock(side_effect=lambda name, value: name == "outdoor_temp")
        bridge = KnxBridge(hass, coordinator, _config(receive_enabled=False), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        assert not [c for c in hass.services.async_call.call_args_list if c.args[2]["address"] == "8/0/1"]
        await bridge.async_stop()


class TestReceiving:
    def _event(self, destination, value, *, direction="Incoming", telegramtype="GroupValueWrite"):
        event = MagicMock()
        event.data = {
            "destination": destination,
            "value": value,
            "direction": direction,
            "telegramtype": telegramtype,
        }
        return event

    async def _started(self, hass, coordinator):
        bridge = KnxBridge(hass, coordinator, _config(send_enabled=False), entry_id="e")
        await bridge.async_start()
        return bridge

    async def test_writes_an_incoming_command_to_the_register(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = await self._started(hass, coordinator)

        bridge._handle_knx_event(self._event("8/0/222", 3))
        await asyncio.sleep(0)
        coordinator.async_write_register.assert_awaited_once_with(HC_A_MODE, 3)
        await bridge.async_stop()

    async def test_ignores_a_command_that_matches_the_current_value(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = await self._started(hass, coordinator)

        bridge._handle_knx_event(self._event("8/0/222", 2))
        await asyncio.sleep(0)
        coordinator.async_write_register.assert_not_awaited()
        await bridge.async_stop()

    async def test_rapid_setpoints_are_coalesced_to_the_newest_value(self):
        hass = _make_hass()
        registers = dict(REGISTERS, **{HC_D_SETPOINT.name: HC_D_SETPOINT})
        coordinator = _make_coordinator({HC_D_SETPOINT.name: 22.0}, registers=registers)
        bridge = KnxBridge(
            hass,
            coordinator,
            _config(send_enabled=False, write_debounce=0.02),
            entry_id="e",
        )
        await bridge.async_start()

        bridge._handle_knx_event(self._event("8/0/232", 22.5))
        await asyncio.sleep(0.005)
        bridge._handle_knx_event(self._event("8/0/232", 23.0))
        await asyncio.sleep(0.04)

        coordinator.async_write_register.assert_awaited_once_with(HC_D_SETPOINT, 23.0)
        await bridge.async_stop()

    async def test_return_to_current_value_cancels_a_pending_change(self):
        hass = _make_hass()
        registers = dict(REGISTERS, **{HC_D_SETPOINT.name: HC_D_SETPOINT})
        coordinator = _make_coordinator({HC_D_SETPOINT.name: 22.0}, registers=registers)
        bridge = KnxBridge(
            hass,
            coordinator,
            _config(send_enabled=False, write_debounce=0.02),
            entry_id="e",
        )
        await bridge.async_start()

        bridge._handle_knx_event(self._event("8/0/232", 23.0))
        await asyncio.sleep(0.005)
        bridge._handle_knx_event(self._event("8/0/232", 22.0))
        await asyncio.sleep(0.04)

        coordinator.async_write_register.assert_not_awaited()
        await bridge.async_stop()

    async def test_general_cooldown_keeps_the_command_queued(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        cooldown = HomeAssistantError(
            translation_key="write_cooldown_active",
            translation_placeholders={"remaining": "0.01"},
        )
        coordinator.async_write_register = AsyncMock(side_effect=[cooldown, None])
        bridge = await self._started(hass, coordinator)

        bridge._handle_knx_event(self._event("8/0/222", 3))
        await asyncio.sleep(0.14)

        assert coordinator.async_write_register.await_count == 2
        coordinator.async_write_register.assert_awaited_with(HC_A_MODE, 3)
        await bridge.async_stop()

    async def test_eeprom_cooldown_retries_the_newest_pending_setpoint(self):
        hass = _make_hass()
        registers = dict(REGISTERS, **{HC_D_SETPOINT.name: HC_D_SETPOINT})
        coordinator = _make_coordinator({HC_D_SETPOINT.name: 22.0}, registers=registers)
        eeprom_guard = ValueError("EEPROM-sensitive register was written too recently (try again in 0.01s)")
        coordinator.async_write_register = AsyncMock(side_effect=[eeprom_guard, None])
        bridge = KnxBridge(hass, coordinator, _config(send_enabled=False), entry_id="e")
        await bridge.async_start()

        bridge._handle_knx_event(self._event("8/0/232", 22.5))
        await asyncio.sleep(0)
        bridge._handle_knx_event(self._event("8/0/232", 23.0))
        await asyncio.sleep(0.14)

        assert coordinator.async_write_register.await_args_list[0].args == (HC_D_SETPOINT, 22.5)
        assert coordinator.async_write_register.await_args_list[1].args == (HC_D_SETPOINT, 23.0)
        await bridge.async_stop()

    async def test_successful_eeprom_write_delays_the_next_knx_value(self):
        hass = _make_hass()
        registers = dict(REGISTERS, **{HC_D_SETPOINT.name: HC_D_SETPOINT})
        coordinator = _make_coordinator({HC_D_SETPOINT.name: 22.0}, registers=registers)
        bridge = KnxBridge(
            hass,
            coordinator,
            _config(send_enabled=False, eeprom_write_interval=0.02),
            entry_id="e",
        )
        await bridge.async_start()

        bridge._handle_knx_event(self._event("8/0/232", 22.5))
        await asyncio.sleep(0)
        bridge._handle_knx_event(self._event("8/0/232", 23.0))
        await asyncio.sleep(0.01)
        assert coordinator.async_write_register.await_count == 1

        await asyncio.sleep(0.13)
        assert coordinator.async_write_register.await_args_list[1].args == (HC_D_SETPOINT, 23.0)
        await bridge.async_stop()

    async def test_stop_cancels_a_debounced_write(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = KnxBridge(
            hass,
            coordinator,
            _config(send_enabled=False, write_debounce=10.0),
            entry_id="e",
        )
        await bridge.async_start()

        bridge._handle_knx_event(self._event("8/0/222", 3))
        await asyncio.sleep(0)
        await bridge.async_stop()

        coordinator.async_write_register.assert_not_awaited()

    async def test_ignores_outgoing_telegrams(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = await self._started(hass, coordinator)

        bridge._handle_knx_event(self._event("8/0/222", 3, direction="Outgoing"))
        await asyncio.sleep(0)
        coordinator.async_write_register.assert_not_awaited()
        await bridge.async_stop()

    async def test_ignores_addresses_outside_the_catalogue(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = await self._started(hass, coordinator)

        bridge._handle_knx_event(self._event("1/1/1", 3))
        await asyncio.sleep(0)
        coordinator.async_write_register.assert_not_awaited()
        await bridge.async_stop()

    async def test_ignores_read_only_objects(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = await self._started(hass, coordinator)

        bridge._handle_knx_event(self._event("8/0/1", 12.0))
        await asyncio.sleep(0)
        coordinator.async_write_register.assert_not_awaited()
        await bridge.async_stop()

    async def test_does_not_write_back_a_value_it_just_sent(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = KnxBridge(hass, coordinator, _config(), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)

        # hc_a_mode was just published as 2; a mirror echoing it back must
        # not turn into another write to the heat pump.
        bridge._handle_knx_event(self._event("8/0/222", 2))
        await asyncio.sleep(0)
        coordinator.async_write_register.assert_not_awaited()

        bridge._handle_knx_event(self._event("8/0/222", 4))
        await asyncio.sleep(0)
        coordinator.async_write_register.assert_awaited_once_with(HC_A_MODE, 4)
        await bridge.async_stop()

    async def test_a_failing_write_does_not_escape_the_handler(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        coordinator.async_write_register = AsyncMock(side_effect=RuntimeError("bus off"))
        bridge = await self._started(hass, coordinator)

        bridge._handle_knx_event(self._event("8/0/222", 3))
        await asyncio.sleep(0)
        await bridge.async_stop()


class TestReadRequests:
    """A KNX device asking for a value must get an answer.

    Without this a push-button refreshing its display after a restart, or a
    visualisation coming back up, stays blank until the next change happens
    to be sent. The BAOS gateway this bridge replaces answers read requests,
    so the bridge has to as well.
    """

    def _read(self, destination, *, direction="Incoming"):
        event = MagicMock()
        event.data = {
            "destination": destination,
            "value": None,
            "direction": direction,
            "telegramtype": "GroupValueRead",
        }
        return event

    def _responses(self, hass):
        return [
            call.args[2]
            for call in hass.services.async_call.call_args_list
            if call.args[1] == "send" and call.args[2].get("response")
        ]

    async def test_answers_with_the_current_value(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = KnxBridge(hass, coordinator, _config(), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        hass.services.async_call.reset_mock()

        bridge._handle_read_request("8/0/1")
        await asyncio.sleep(0)
        assert self._responses(hass) == [{"address": "8/0/1", "response": True, "type": "9.001", "payload": 7.5}]
        await bridge.async_stop()

    async def test_answers_from_the_coordinator_not_the_last_telegram(self):
        """The reply carries what the heat pump reads now."""
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = KnxBridge(hass, coordinator, _config(), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        coordinator.data = dict(coordinator.data, outdoor_temp=3.25)
        hass.services.async_call.reset_mock()

        bridge._handle_read_request("8/0/1")
        await asyncio.sleep(0)
        assert self._responses(hass)[0]["payload"] == 3.25
        await bridge.async_stop()

    async def test_a_read_is_routed_through_the_event_handler(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = KnxBridge(hass, coordinator, _config(), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        hass.services.async_call.reset_mock()

        bridge._handle_knx_event(self._read("8/0/1"))
        await asyncio.sleep(0)
        assert len(self._responses(hass)) == 1
        await bridge.async_stop()

    async def test_a_read_never_writes_to_the_heat_pump(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = KnxBridge(hass, coordinator, _config(), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)

        bridge._handle_knx_event(self._read("8/0/222"))
        await asyncio.sleep(0)
        coordinator.async_write_register.assert_not_awaited()
        await bridge.async_stop()

    async def test_ignores_our_own_outgoing_read(self):
        hass = _make_hass()
        bridge = KnxBridge(hass, _make_coordinator(), _config(), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        hass.services.async_call.reset_mock()

        bridge._handle_knx_event(self._read("8/0/1", direction="Outgoing"))
        await asyncio.sleep(0)
        assert self._responses(hass) == []
        await bridge.async_stop()

    async def test_stays_quiet_when_answering_is_switched_off(self):
        hass = _make_hass()
        bridge = KnxBridge(hass, _make_coordinator(), _config(respond_to_read=False), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        hass.services.async_call.reset_mock()

        bridge._handle_knx_event(self._read("8/0/1"))
        await asyncio.sleep(0)
        assert self._responses(hass) == []
        await bridge.async_stop()

    async def test_stays_quiet_when_sending_is_switched_off(self):
        """Receive-only means the bridge puts nothing on the bus at all."""
        hass = _make_hass()
        bridge = KnxBridge(hass, _make_coordinator(), _config(send_enabled=False), entry_id="e")
        await bridge.async_start()
        hass.services.async_call.reset_mock()

        bridge._handle_knx_event(self._read("8/0/1"))
        await asyncio.sleep(0)
        assert self._responses(hass) == []
        await bridge.async_stop()

    async def test_write_only_registers_carry_no_answer(self):
        hass = _make_hass()
        bridge = KnxBridge(hass, _make_coordinator(), _config(), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        hass.services.async_call.reset_mock()

        # error_acknowledge: reachable from the bus, but it holds no value.
        bridge._handle_read_request("8/1/243")
        await asyncio.sleep(0)
        assert self._responses(hass) == []
        await bridge.async_stop()

    async def test_unused_values_are_not_answered(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        coordinator.is_register_unused = MagicMock(side_effect=lambda name, value: name == "outdoor_temp")
        bridge = KnxBridge(hass, coordinator, _config(), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        hass.services.async_call.reset_mock()

        bridge._handle_read_request("8/0/1")
        await asyncio.sleep(0)
        assert self._responses(hass) == []
        await bridge.async_stop()

    async def test_unknown_addresses_are_ignored(self):
        hass = _make_hass()
        bridge = KnxBridge(hass, _make_coordinator(), _config(), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        hass.services.async_call.reset_mock()

        bridge._handle_read_request("1/1/1")
        await asyncio.sleep(0)
        assert self._responses(hass) == []
        await bridge.async_stop()

    async def test_read_only_objects_are_registered_for_events(self):
        """A read request only reaches us if its address is registered."""
        hass = _make_hass()
        bridge = KnxBridge(hass, _make_coordinator(), _config(), entry_id="e")
        await bridge.async_start()
        registered = [c for c in hass.services.async_call.call_args_list if c.args[1] == "event_register"]
        addresses = {a for call in registered for a in call.args[2]["address"]}
        # 8/0/1 is read-only and would not be registered without this.
        assert "8/0/1" in addresses
        await bridge.async_stop()

    async def test_only_writable_objects_are_registered_without_answering(self):
        hass = _make_hass()
        bridge = KnxBridge(hass, _make_coordinator(), _config(respond_to_read=False), entry_id="e")
        await bridge.async_start()
        registered = [c for c in hass.services.async_call.call_args_list if c.args[1] == "event_register"]
        addresses = {a for call in registered for a in call.args[2]["address"]}
        assert "8/0/1" not in addresses
        assert "8/0/222" in addresses
        await bridge.async_stop()


class TestResilienceAndEdges:
    """Failure paths: none of them may take the bridge or the entry down."""

    async def test_periodic_resend_repeats_unchanged_values(self):
        """A visualisation without its own cache needs the value again."""
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = KnxBridge(hass, coordinator, _config(receive_enabled=False, resend_interval=1), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        hass.services.async_call.reset_mock()

        # Nothing changed, but the resend window has passed.
        bridge._last_full_send -= 2
        bridge._handle_coordinator_update()
        await _drain(bridge)
        assert [c for c in hass.services.async_call.call_args_list if c.args[2]["address"] == "8/0/1"]
        await bridge.async_stop()

    async def test_start_warns_and_stays_idle_without_servable_objects(self):
        hass = _make_hass()
        coordinator = _make_coordinator(data={})
        coordinator.get_register = MagicMock(return_value=None)
        bridge = KnxBridge(hass, coordinator, _config(), entry_id="e")
        await bridge.async_start()
        assert bridge.group_addresses == {}
        hass.bus.async_listen.assert_not_called()

    async def test_a_failing_event_registration_does_not_abort_start(self):
        hass = _make_hass()
        hass.services.async_call = AsyncMock(side_effect=RuntimeError("knx down"))
        bridge = KnxBridge(hass, _make_coordinator(), _config(send_enabled=False), entry_id="e")
        await bridge.async_start()
        assert bridge.group_addresses  # resolved despite the failure
        hass.bus.async_listen.assert_called_once_with(EVENT_KNX, bridge._handle_knx_event)
        await bridge.async_stop()

    async def test_retries_event_registration_after_knx_finishes_starting(self, monkeypatch):
        monkeypatch.setattr(
            "custom_components.idm_heatpump.knx_bridge.KNX_EVENT_REGISTRATION_RETRY_SECONDS",
            0.01,
        )
        hass = _make_hass()
        hass.services.async_call = AsyncMock(
            side_effect=[
                HomeAssistantError(translation_domain="knx", translation_key="integration_not_loaded"),
                None,
                None,
                None,
                None,
            ]
        )
        bridge = KnxBridge(hass, _make_coordinator(), _config(send_enabled=False), entry_id="e")

        await bridge.async_start()
        assert bridge._registration_worker is not None
        await asyncio.sleep(0.03)

        registrations = [
            call
            for call in hass.services.async_call.call_args_list
            if call.args[1] == "event_register" and not call.args[2].get("remove")
        ]
        assert len(registrations) == 3
        assert [call.args[2]["type"] for call in registrations].count("5.010") == 2
        assert [call.args[2]["type"] for call in registrations].count("7.001") == 1
        assert bridge._registration_worker.done()
        assert bridge._registration_worker.exception() is None
        assert len(bridge._registered_event_groups) == 2
        await bridge.async_stop()

    async def test_a_failing_send_does_not_kill_the_worker(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        hass.services.async_call = AsyncMock(side_effect=RuntimeError("bus off"))
        bridge = KnxBridge(hass, coordinator, _config(receive_enabled=False), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)

        # The worker survived and keeps draining after the failure.
        coordinator.data = dict(coordinator.data, outdoor_temp=11.0)
        bridge._handle_coordinator_update()
        await _drain(bridge)
        assert bridge._queue.empty()
        await bridge.async_stop()

    async def test_a_failing_read_answer_is_swallowed(self):
        hass = _make_hass()
        bridge = KnxBridge(hass, _make_coordinator(), _config(), entry_id="e")
        await bridge.async_start()
        await _drain(bridge)
        hass.services.async_call = AsyncMock(side_effect=RuntimeError("bus off"))

        bridge._handle_read_request("8/0/1")
        await asyncio.sleep(0)
        await bridge.async_stop()

    async def test_a_write_to_a_read_only_register_is_refused(self):
        """The catalogue says writable, the register does not."""
        hass = _make_hass()
        coordinator = _make_coordinator()
        read_only = RegisterDef(1393, DataType.UCHAR, "hc_a_mode")
        coordinator.get_register = MagicMock(
            side_effect=lambda name: read_only if name == "hc_a_mode" else REGISTERS.get(name)
        )
        bridge = KnxBridge(hass, coordinator, _config(send_enabled=False), entry_id="e")
        await bridge.async_start()

        event = MagicMock()
        event.data = {
            "destination": "8/0/222",
            "value": 3,
            "direction": "Incoming",
            "telegramtype": "GroupValueWrite",
        }
        bridge._handle_knx_event(event)
        await asyncio.sleep(0)
        coordinator.async_write_register.assert_not_awaited()
        await bridge.async_stop()

    async def test_an_undecodable_payload_is_ignored(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = KnxBridge(hass, coordinator, _config(send_enabled=False), entry_id="e")
        await bridge.async_start()

        event = MagicMock()
        event.data = {
            "destination": "8/0/222",
            "value": "not a number",
            "direction": "Incoming",
            "telegramtype": "GroupValueWrite",
        }
        bridge._handle_knx_event(event)
        await asyncio.sleep(0)
        coordinator.async_write_register.assert_not_awaited()
        await bridge.async_stop()

    async def test_a_group_value_response_is_never_written(self):
        hass = _make_hass()
        coordinator = _make_coordinator()
        bridge = KnxBridge(hass, coordinator, _config(send_enabled=False), entry_id="e")
        await bridge.async_start()

        event = MagicMock()
        event.data = {
            "destination": "8/0/222",
            "value": 3,
            "direction": "Incoming",
            "telegramtype": "GroupValueResponse",
        }
        bridge._handle_knx_event(event)
        await asyncio.sleep(0)
        coordinator.async_write_register.assert_not_awaited()
        await bridge.async_stop()

    def test_no_group_filter_means_the_whole_catalogue(self):
        from custom_components.idm_heatpump.knx_bridge import _catalogue_objects
        from custom_components.idm_heatpump.knx_catalog import KNX_OBJECTS

        assert len(_catalogue_objects(None)) == len(KNX_OBJECTS)
        assert {o.group for o in _catalogue_objects(("solar",))} == {"solar"}

    def test_outgoing_coercion_survives_an_unconvertible_object(self):
        assert _coerce_outgoing(object(), "9.001") is None

    def test_incoming_coercion_takes_a_bool(self):
        assert _coerce_incoming(True, SYSTEM_MODE) == 1
