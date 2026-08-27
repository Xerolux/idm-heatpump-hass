"""Tests for the KNX bridge.

The bridge never talks to a bus itself: it calls the Home Assistant KNX
integration's services and listens for its events. These tests therefore
assert on the service calls and on what an incoming ``knx_event`` writes
back into the heat pump.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump.knx_bridge import (
    EVENT_KNX,
    KNX_DOMAIN,
    KnxBridge,
    KnxBridgeConfig,
    _coerce_incoming,
    _coerce_outgoing,
)

OUTDOOR = RegisterDef(1000, DataType.FLOAT, "outdoor_temp", unit="°C")
SYSTEM_MODE = RegisterDef(1005, DataType.UCHAR, "system_mode", writable=True)
HC_A_MODE = RegisterDef(1393, DataType.UCHAR, "hc_a_mode", writable=True)
DEMAND_HEATING = RegisterDef(1710, DataType.BOOL, "demand_heating", writable=True)
ACK = RegisterDef(1999, DataType.UCHAR, "error_acknowledge", writable=True, write_only=True)

REGISTERS = {reg.name: reg for reg in (OUTDOOR, SYSTEM_MODE, HC_A_MODE, DEMAND_HEATING, ACK)}


def _make_hass(*, knx_loaded=True):
    hass = MagicMock()
    hass.config.components = {"idm_heatpump"} | ({KNX_DOMAIN} if knx_loaded else set())
    hass.services.has_service = MagicMock(return_value=knx_loaded)
    hass.services.async_call = AsyncMock()
    hass.bus.async_listen = MagicMock(return_value=MagicMock())
    hass.async_create_task = MagicMock(side_effect=lambda coro: asyncio.ensure_future(coro))
    return hass


def _make_coordinator(data=None):
    coordinator = MagicMock()
    coordinator.data = data if data is not None else {"outdoor_temp": 7.5, "system_mode": 1, "hc_a_mode": 2}
    coordinator.get_register = MagicMock(side_effect=REGISTERS.get)
    coordinator.is_register_unused = MagicMock(return_value=False)
    coordinator.async_add_listener = MagicMock(return_value=MagicMock())
    coordinator.async_write_register = AsyncMock()
    return coordinator


def _config(**kwargs):
    defaults = {
        "base_address": "8/0/0",
        "groups": ("system", "heat_pump", "heating_circuits", "glt"),
        "send_gap": 0.0,
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
