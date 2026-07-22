"""Tests for IdmCoordinator."""

import socket
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.idm_heatpump.coordinator import (
    IdmCoordinator,
    _friendly_communication_error,
    _repair_issue_for_error,
    navigator_family,
)
from custom_components.idm_heatpump.web_data import (
    IdmWebAuthenticationFailed,
    IdmWebSensorValue,
    IdmWebSupplement,
)
from idm_heatpump import (
    MODEL_NAVIGATOR_20,
    DataType,
    IdmModelInfo,
    RegisterDef,
)
from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException
from custom_components.idm_heatpump.const import UNUSED_VALUE


def _make_coordinator(mock_hass, mock_config_entry, client=None, **kwargs):
    if client is None:
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={})
        client.write_register = AsyncMock()
    coord = IdmCoordinator(
        hass=mock_hass,
        config_entry=mock_config_entry,
        client=client,
        scan_interval=timedelta(seconds=10),
        sensor_descriptions=kwargs.get("sensor_descriptions", []),
        binary_sensor_descriptions=kwargs.get("binary_sensor_descriptions", []),
        number_descriptions=kwargs.get("number_descriptions", []),
        select_descriptions=kwargs.get("select_descriptions", []),
        switch_descriptions=kwargs.get("switch_descriptions", []),
        hide_unused=kwargs.get("hide_unused", True),
        model_name=kwargs.get("model_name", "Navigator 2.0 / 10"),
        firmware_version=kwargs.get("firmware_version"),
        model_info=kwargs.get("model_info"),
        web_pin=kwargs.get("web_pin"),
        web_host=kwargs.get("web_host"),
        web_supplement=kwargs.get("web_supplement"),
        web_variant=kwargs.get("web_variant"),
    )
    registers = kwargs.get("registers")
    if registers is not None:
        coord._registers = registers
        # Rebuild the derived name index and room-mode subset so tests that set
        # registers directly exercise the same cached lookups as production.
        coord._register_by_name = {reg.name: reg for reg in registers}
        from custom_components.idm_heatpump.coordinator import _is_zone_room_mode_register

        coord._room_mode_registers = [reg for reg in registers if _is_zone_room_mode_register(reg)]
    return coord, client


class TestNavigatorFamily:
    def test_returns_none_for_non_string(self):
        assert navigator_family(None) is None
        assert navigator_family(123) is None

    def test_returns_none_for_generic_model(self):
        assert navigator_family("Navigator 2.0 / 10") is None

    def test_detects_navigator_20(self):
        assert navigator_family("Navigator 2.0") == "navigator_20"
        assert navigator_family("IDM Navigator 2.0") == "navigator_20"
        assert navigator_family("navigator 2.0") == "navigator_20"

    def test_detects_navigator_10(self):
        assert navigator_family("Navigator 10") == "navigator_10"
        assert navigator_family("IDM Navigator 10") == "navigator_10"
        assert navigator_family("NAVIGATOR 10") == "navigator_10"

    def test_detects_navigator_pro(self):
        assert navigator_family("Navigator Pro") == "navigator_pro"

    def test_returns_none_when_both_20_and_10_mentioned(self):
        assert navigator_family("Navigator 2.0 vs Navigator 10") is None

    def test_returns_none_for_unknown_model(self):
        assert navigator_family("Terra SWM") is None
        assert navigator_family("SomeOther Model") is None


class TestCoordinatorInit:
    def test_properties_match_init(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            sensor_descriptions=[{"key": "s1"}],
            binary_sensor_descriptions=[{"key": "b1"}],
            number_descriptions=[{"key": "n1"}, {"key": "n2"}],
            select_descriptions=[],
            switch_descriptions=[{"key": "sw1"}],
            hide_unused=False,
        )
        assert len(coord.sensor_descriptions) == 1
        assert len(coord.binary_sensor_descriptions) == 1
        assert len(coord.number_descriptions) == 2
        assert len(coord.select_descriptions) == 0
        assert len(coord.switch_descriptions) == 1
        assert coord.hide_unused is False

    def test_update_interval(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.update_interval == timedelta(seconds=10)

    def test_client_stored(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        assert coord.client is client

    def test_config_entry_stored(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.config_entry is mock_config_entry

    def test_initial_web_supplement_caches_navigator_pro_variant(self, mock_hass, mock_config_entry):
        supplement = IdmWebSupplement(navigator_version="Navigator Pro")
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_supplement=supplement)

        assert coord.web_variant == "nav10"

    def test_initial_web_supplement_uses_heatpump_model_for_variant(self, mock_hass, mock_config_entry):
        supplement = IdmWebSupplement(heatpump_model="Navigator 2.0")
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_supplement=supplement)

        assert coord.web_variant == "nav20"


class TestRepairIssueClassification:
    @pytest.mark.parametrize(
        ("error", "issue_id"),
        [
            (ConnectionException("connection lost"), "cannot_connect"),
            (
                ConnectionException(
                    "Modbus Error: [Connection] Failed to connect [Errno 111] "
                    "Connect call failed ('192.168.178.196', 5020)"
                ),
                "modbus_connection_refused",
            ),
            (socket.gaierror("name or service not known"), "host_not_found"),
            (ConnectionRefusedError("connection refused"), "modbus_connection_refused"),
            (TimeoutError("timed out"), "modbus_timeout"),
            (ModbusIOException("No response received after 0 retries"), "modbus_timeout"),
            (ModbusException("no response from slave 2"), "wrong_slave_id"),
            (ModbusException("ExceptionResponse(exception_code=1) illegal function"), "incompatible_firmware"),
            (Exception("timeout"), "modbus_timeout"),
        ],
    )
    def test_classifies_communication_errors(self, error, issue_id):
        assert _repair_issue_for_error(error) == issue_id

    def test_connection_refused_message_is_actionable(self):
        message = _friendly_communication_error(
            "modbus_connection_refused",
            "192.168.178.196",
            5020,
            ConnectionException("connect call failed"),
        )

        assert "192.168.178.196:5020" in message
        assert "refused the Modbus TCP connection" in message
        assert "Modbus TCP is enabled" in message

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (ConnectionException("connection reset by peer"), "was interrupted"),
            (ConnectionException("No route to host (Errno 113)"), "no working network route"),
            (ModbusException("Modbus response CRC error"), "response that could not be read"),
        ],
    )
    def test_generic_communication_errors_are_actionable(self, error, expected):
        message = _friendly_communication_error("cannot_connect", "192.168.178.196", 502, error)

        assert expected in message


class TestSetupRegisters:
    def test_registers_count(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        with patch(
            "custom_components.idm_heatpump.coordinator.collect_all_registers",
            return_value=[MagicMock(), MagicMock(), MagicMock()],
        ):
            coord.setup_registers(["a"], 0, {})
        assert coord.registers_count == 3

    def test_empty_registers(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        with patch(
            "custom_components.idm_heatpump.coordinator.collect_all_registers",
            return_value=[],
        ):
            coord.setup_registers(["a"], 0, {})
        assert coord.registers_count == 0

    def test_detected_model_is_forwarded_to_register_collection(self, mock_hass, mock_config_entry):
        model_info = MagicMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        with (
            patch(
                "custom_components.idm_heatpump.coordinator.collect_all_registers",
                return_value=[],
            ) as mock_collect,
            patch(
                "custom_components.idm_heatpump.coordinator.collect_alias_map",
                return_value={},
            ) as mock_aliases,
        ):
            coord.setup_registers(["a"], 0, {}, model_info=model_info)

        mock_collect.assert_called_once_with(["a"], 0, {}, False, model_info=model_info)
        mock_aliases.assert_called_once_with(["a"], 0, {}, False, model_info=model_info)

    def test_register_by_name_cache_is_built(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        reg_a = RegisterDef(address=1000, datatype=DataType.UCHAR, name="reg_a")
        reg_b = RegisterDef(address=1001, datatype=DataType.UCHAR, name="reg_b")
        with patch(
            "custom_components.idm_heatpump.coordinator.collect_all_registers",
            return_value=[reg_a, reg_b],
        ):
            coord.setup_registers(["a"], 0, {})
        assert coord._register_by_name == {"reg_a": reg_a, "reg_b": reg_b}


class TestIsRegisterUnused:
    def test_unused_value_is_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", UNUSED_VALUE) is True

    def test_none_is_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", None) is True

    def test_normal_value_is_not_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", 20.0) is False

    def test_hide_unused_false_never_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=False)
        assert coord.is_register_unused("x", UNUSED_VALUE) is False
        assert coord.is_register_unused("x", None) is False

    def test_zero_is_not_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", 0.0) is False

    def test_negative_one_is_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        # UNUSED_VALUE is -1.0
        assert coord.is_register_unused("x", -1.0) is True

    def test_65535_is_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", 65535) is True

    def test_255_is_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", 255) is True

    def test_register_metadata_sentinel_is_unused(self, mock_hass, mock_config_entry):
        reg = RegisterDef(
            address=1714,
            datatype=DataType.UCHAR,
            name="external_pump_demand",
        )
        setattr(reg, "sentinel_values", (254,))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            hide_unused=True,
            registers=[reg],
        )

        assert coord.is_register_unused(reg.name, 254) is True
        assert coord.is_register_unused(reg.name, 50) is False

    def test_undeclared_254_is_not_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)

        assert coord.is_register_unused("x", 254) is False

    def test_documented_enum_value_255_is_not_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        coord._registers = [
            RegisterDef(
                address=1200,
                datatype=DataType.UCHAR,
                name="hc_a_mode",
                enum_options={0: "Off", 1: "Automatic", 255: "Not configured"},
            )
        ]
        assert coord.is_register_unused("hc_a_mode", 255) is False

    def test_minus_32768_is_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", -32768) is True

    def test_nan_is_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", float("nan")) is True

    def test_inf_is_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", float("inf")) is True

    def test_normal_int_is_not_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", 42) is False

    def test_negative_power_value_is_not_unused_when_not_sentinel(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("pv_power", -42.5) is False

    def test_pump_status_negative_one_means_off(self, mock_hass, mock_config_entry):
        # Bei Pumpen-Statusregistern bedeutet -1 laut iDM-Doku "Aus" — gültig.
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        for name in (
            "charging_pump_status",
            "brine_pump_status",
            "heat_source_pump_status",
            "isc_cold_storage_pump_status",
            "isc_recooling_pump_status",
            "heat_sink_charging_pump_signal",
            "booster_a_source_pump",
            "booster_a_charging_pump",
            "booster_b_source_pump",
            "booster_b_charging_pump",
        ):
            assert coord.is_register_unused(name, -1) is False, name
            assert coord.is_register_unused(name, -1.0) is False, name
            assert coord.is_register_unused(name, 50) is False, name

    def test_pump_status_real_sentinels_still_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("charging_pump_status", -32768) is True
        assert coord.is_register_unused("charging_pump_status", float("nan")) is True
        assert coord.is_register_unused("charging_pump_status", None) is True

    def test_battery_soc_negative_one_is_unused(self, mock_hass, mock_config_entry):
        # battery_soc: -1 bedeutet "nicht verfügbar" → weiterhin unused.
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("battery_soc", -1) is True

    def test_get_register_uses_name_index(self, mock_hass, mock_config_entry):
        """get_register resolves registers via the O(1) name index (9a6b5ff)."""
        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="flow_temp")
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, registers=[reg])
        assert coord.get_register("flow_temp") is reg
        assert coord.get_register("nonexistent") is None

    def test_is_register_unused_resolves_register_via_name_cache(self, mock_hass, mock_config_entry):
        """is_register_unused uses _register_by_name so enum options are honored (9a6b5ff)."""
        enum_reg = RegisterDef(
            address=1000,
            datatype=DataType.UCHAR,
            name="hc_a_mode",
            enum_options={0: "off", 255: "not_configured"},
        )
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True, registers=[enum_reg])
        # 255 is normally an unused sentinel, but for an enum register it is a
        # documented value, so it must NOT be treated as unused. This verifies
        # the register is found via the name cache and its enum_options read.
        assert coord.is_register_unused("hc_a_mode", 255) is False


class TestAsyncUpdateData:
    async def test_successful_update(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 22.5, "mode": 1})
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[
                RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp"),
                RegisterDef(address=1001, datatype=DataType.UCHAR, name="mode"),
            ],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            data = await coord._async_update_data()

        assert data["temp"] == 22.5
        assert data["mode"] == 1
        assert mock_ir.async_delete_issue.call_count == 7

    async def test_empty_data_raises_update_failed(self, mock_hass, mock_config_entry):
        from homeassistant.helpers.update_coordinator import UpdateFailed

        client = MagicMock()
        client.read_batch = AsyncMock(return_value={})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            with pytest.raises(UpdateFailed, match="returned no usable register data"):
                await coord._async_update_data()

        assert mock_ir.async_create_issue.call_args.args[2] == "no_data_received"

    async def test_exception_raises_update_failed(self, mock_hass, mock_config_entry):
        from homeassistant.helpers.update_coordinator import UpdateFailed

        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=Exception("connection lost"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()
        mock_ir.async_create_issue.assert_called_once()

    async def test_illegal_address_is_isolated_and_skipped(self, mock_hass, mock_config_entry):
        good_a = RegisterDef(address=1000, datatype=DataType.UCHAR, name="good_a")
        unsupported = RegisterDef(address=4108, datatype=DataType.FLOAT, name="power_limit_hp")
        good_b = RegisterDef(address=4122, datatype=DataType.FLOAT, name="good_b")
        calls: list[list[str]] = []

        async def read_batch(registers):
            calls.append([reg.name for reg in registers])
            if any(reg.name == "power_limit_hp" for reg in registers):
                raise ModbusException(
                    "Modbus error reading address 4108: "
                    "ExceptionResponse(dev_id=1, function_code=132, exception_code=2)"
                )
            return {reg.name: 1 for reg in registers}

        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=read_batch)
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord._registers = [good_a, unsupported, good_b]

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            data = await coord._async_update_data()

        assert data == {"good_a": 1, "good_b": 1}
        assert coord.unsupported_registers == {"power_limit_hp"}

        calls.clear()
        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
        assert calls == [["good_a", "good_b"]]

    async def test_illegal_address_creates_register_not_supported_issue(self, mock_hass, mock_config_entry):
        unsupported = RegisterDef(address=4108, datatype=DataType.FLOAT, name="power_limit_hp")

        client = MagicMock()
        client.read_batch = AsyncMock(
            side_effect=ModbusException("Modbus error reading address 4108: ExceptionResponse(exception_code=2)")
        )
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord._registers = [unsupported]

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            with pytest.raises(Exception):
                await coord._async_update_data()

        mock_ir.async_create_issue.assert_any_call(
            mock_hass,
            "idm_heatpump",
            "register_not_supported_power_limit_hp",
            is_fixable=False,
            severity=mock_ir.IssueSeverity.WARNING,
            translation_key="register_not_supported",
            translation_placeholders={"register": "power_limit_hp", "address": "4108"},
        )

    async def test_library_unsupported_registers_are_merged_into_skip_list(self, mock_hass, mock_config_entry):
        """Registers flagged unsupported by the library are mirrored after each poll.

        The library isolates Illegal-Data-Address registers inside read_batch
        and exposes them via get_unsupported_registers(). The coordinator must
        merge that set into its own _unsupported_registers so they are skipped
        on the next poll (the zone-room-mode path and the unsupported_registers
        property both rely on it).
        """
        good = RegisterDef(address=1000, datatype=DataType.UCHAR, name="good_a")
        unsupported = RegisterDef(address=4108, datatype=DataType.FLOAT, name="power_limit_hp")

        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"good_a": 1})
        # The library has already isolated power_limit_hp during read_batch.
        client.get_unsupported_registers = MagicMock(return_value=("power_limit_hp",))
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, registers=[good, unsupported])

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()

        assert coord.unsupported_registers == {"power_limit_hp"}

    async def test_merge_unsupported_is_noop_without_library_support(self, mock_hass, mock_config_entry):
        """Older library versions without get_unsupported_registers are tolerated.

        _merge_unsupported_registers uses getattr and must be a no-op rather
        than raising when the method is absent.
        """
        good = RegisterDef(address=1000, datatype=DataType.UCHAR, name="good_a")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"good_a": 1})
        # Simulate an older library: no get_unsupported_registers attribute.
        del client.get_unsupported_registers
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, registers=[good])

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()

        assert coord.unsupported_registers == set()

    @pytest.mark.parametrize(
        "error",
        [
            ConnectionException("connection lost"),
            ModbusException("Modbus response CRC error"),
        ],
    )
    async def test_non_address_modbus_errors_remain_fatal(
        self,
        mock_hass,
        mock_config_entry,
        error,
    ):
        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=error)
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord._registers = [RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")]

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            with pytest.raises(Exception, match="IDM device"):
                await coord._async_update_data()
        mock_ir.async_create_issue.assert_called_once()

    async def test_zone_room_modes_are_refreshed_individually(self, mock_hass, mock_config_entry):
        room_mode = RegisterDef(
            address=2025,
            datatype=DataType.UCHAR,
            name="zm1_room3_mode",
            enum_options={0: "off", 1: "automatic", 2: "eco", 3: "normal", 4: "comfort"},
        )
        room_temp = RegisterDef(address=2020, datatype=DataType.FLOAT, name="zm1_room3_temp")
        system_mode = RegisterDef(address=1005, datatype=DataType.UCHAR, name="system_mode")
        client = MagicMock()
        client.read_batch = AsyncMock(
            return_value={
                "zm1_room3_temp": 21.5,
                "zm1_room3_mode": 255,
                "system_mode": 1,
            }
        )
        client.read_register = AsyncMock(return_value=3)
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[room_temp, room_mode, system_mode],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            data = await coord._async_update_data()

        assert data["zm1_room3_mode"] == 3
        assert data["zm1_room3_temp"] == 21.5
        assert data["system_mode"] == 1
        client.read_register.assert_awaited_once_with(room_mode)
        client.mark_batch_unsafe.assert_called_once_with(room_mode)
        assert "zm1_room3_mode" not in coord.unused_registers

    async def test_batch_unsafe_zone_room_mode_is_not_read_twice(self, mock_hass, mock_config_entry):
        room_mode = RegisterDef(
            address=2025,
            datatype=DataType.UCHAR,
            name="zm1_room3_mode",
            enum_options={0: "off", 1: "automatic", 2: "eco", 3: "normal", 4: "comfort"},
        )
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={room_mode.name: 3})
        client.get_batch_unsafe_registers = MagicMock(return_value=(room_mode.name,))
        client.read_register = AsyncMock()
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[room_mode],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            data = await coord._async_update_data()

        assert data[room_mode.name] == 3
        client.read_register.assert_not_awaited()

    async def test_unsupported_zone_room_mode_does_not_break_poll(self, mock_hass, mock_config_entry):
        room_mode = RegisterDef(address=2025, datatype=DataType.UCHAR, name="zm1_room3_mode")
        good = RegisterDef(address=1000, datatype=DataType.UCHAR, name="good")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={room_mode.name: 2, good.name: 7})
        client.read_register = AsyncMock(side_effect=ModbusException("Illegal Data Address exception_code=2"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[room_mode, good],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            data = await coord._async_update_data()

        assert data == {good.name: 7}
        assert room_mode.name in coord.unsupported_registers

    async def test_zone_room_mode_transport_error_uses_poll_repair_flow(self, mock_hass, mock_config_entry):
        room_mode = RegisterDef(address=2025, datatype=DataType.UCHAR, name="zm1_room3_mode")
        later_room_mode = RegisterDef(address=2026, datatype=DataType.UCHAR, name="zm1_room4_mode")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={room_mode.name: 2, later_room_mode.name: 3})
        client.read_register = AsyncMock(side_effect=ModbusIOException("No response received"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[room_mode, later_room_mode],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            with pytest.raises(Exception, match="did not respond in time"):
                await coord._async_update_data()

        assert mock_ir.async_create_issue.call_args.args[2] == "modbus_timeout"
        assert client.read_register.await_count == 1

    async def test_invalid_zone_room_mode_is_omitted_without_losing_other_data(self, mock_hass, mock_config_entry):
        room_mode = RegisterDef(address=2025, datatype=DataType.UCHAR, name="zm1_room3_mode")
        good = RegisterDef(address=1000, datatype=DataType.UCHAR, name="good")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={room_mode.name: 2, good.name: 7})
        client.read_register = AsyncMock(side_effect=ValueError("invalid room mode"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[room_mode, good],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            data = await coord._async_update_data()

        assert data == {good.name: 7}

    async def test_alias_primary_map_is_cached(self, mock_hass, mock_config_entry):
        primary = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 22.5})
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[primary],
        )
        # Alias names share the same Modbus address but are not duplicated in _registers.
        coord._alias_map = {1000: ["temp", "temp_set"]}

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            data = await coord._async_update_data()

        assert data["temp_set"] == 22.5
        assert coord._alias_primary_map == {1000: "temp"}

    async def test_modbus_update_preserves_latest_web_metadata(self, mock_hass, mock_config_entry):
        register = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 22.5})
        supplement = IdmWebSupplement(
            navigator_version="Navigator 10",
            software_version="NAV10_20.24",
        )
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[register],
            web_supplement=supplement,
        )

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            data = await coord._async_update_data()

        assert data == {
            "temp": 22.5,
            "web_navigator_version": "Navigator 10",
            "web_software_version": "NAV10_20.24",
        }

    async def test_unused_registers_tracked(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"dead": UNUSED_VALUE, "alive": 5.0})
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            hide_unused=True,
            registers=[
                RegisterDef(address=1000, datatype=DataType.UCHAR, name="dead"),
                RegisterDef(address=1001, datatype=DataType.UCHAR, name="alive"),
            ],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
        assert "dead" in coord.unused_registers
        assert "alive" not in coord.unused_registers

    async def test_unused_registers_are_recomputed_each_update(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(
            side_effect=[
                {"dead": UNUSED_VALUE, "alive": 5.0},
                {"dead": 5.0, "alive": 5.5},
            ]
        )
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            hide_unused=True,
            registers=[
                RegisterDef(address=1000, datatype=DataType.UCHAR, name="dead"),
                RegisterDef(address=1001, datatype=DataType.UCHAR, name="alive"),
            ],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
            assert "dead" in coord.unused_registers
            await coord._async_update_data()
            assert "dead" not in coord.unused_registers

    async def test_issue_deleted_on_success(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 20.0})
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            await coord._async_update_data()
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "cannot_connect")

    async def test_connectivity_issues_deleted_on_success(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 20.0})
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            await coord._async_update_data()

        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "cannot_connect")
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "host_not_found")
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "modbus_connection_refused")
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "modbus_timeout")
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "wrong_slave_id")
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "incompatible_firmware")

    async def test_issue_created_on_failure(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=Exception("timeout"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            with pytest.raises(Exception):
                await coord._async_update_data()
        mock_ir.async_create_issue.assert_called_once()
        call_kwargs = mock_ir.async_create_issue.call_args
        assert call_kwargs is not None

    async def test_wrong_slave_id_issue_created_on_no_response(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=ModbusException("no response from slave 3"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            with pytest.raises(Exception):
                await coord._async_update_data()

        assert mock_ir.async_create_issue.call_args.args[2] == "wrong_slave_id"
        assert mock_ir.async_create_issue.call_args.kwargs["translation_key"] == "wrong_slave_id"

    async def test_incompatible_firmware_issue_created_on_illegal_function(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=ModbusException("ExceptionResponse(exception_code=1)"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            with pytest.raises(Exception):
                await coord._async_update_data()

        assert mock_ir.async_create_issue.call_args.args[2] == "incompatible_firmware"
        assert mock_ir.async_create_issue.call_args.kwargs["translation_key"] == "incompatible_firmware"

    async def test_zone_room_modes_read_individually_for_multiple_zones(self, mock_hass, mock_config_entry):
        """Multiple zone-room mode registers are each read individually (b0e7c43)."""
        registers = [
            RegisterDef(
                address=2000 + i,
                datatype=DataType.UCHAR,
                name=f"zm{zone}_room{room}_mode",
                enum_options={0: "off", 1: "on"},
            )
            for i, (zone, room) in enumerate((z, r) for z in (1, 2) for r in (1, 2, 3))
        ]
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={reg.name: 0 for reg in registers})
        # read_register returns a distinct value per register so we can verify
        # each register was read individually and mapped back correctly.
        client.read_register = AsyncMock(side_effect=[zone * 10 + room for zone in (1, 2) for room in (1, 2, 3)])
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, registers=registers)

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            data = await coord._async_update_data()

        # Each room-mode register is read once via read_register.
        assert client.read_register.await_count == 6
        for zone in (1, 2):
            for room in (1, 2, 3):
                assert data[f"zm{zone}_room{room}_mode"] == zone * 10 + room

    async def test_zone_room_mode_register_subset_cached_at_setup(self, mock_hass, mock_config_entry):
        """Room-mode register subset is computed once at setup (P4), not per poll."""
        registers = [
            RegisterDef(address=2000, datatype=DataType.UCHAR, name="system_mode"),
            RegisterDef(address=2001, datatype=DataType.FLOAT, name="zm1_room1_temp"),
            RegisterDef(address=2002, datatype=DataType.UCHAR, name="zm1_room1_mode"),
            RegisterDef(address=2003, datatype=DataType.UCHAR, name="zm2_room3_mode"),
        ]
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, registers=registers)
        cached_names = [reg.name for reg in coord._room_mode_registers]
        assert cached_names == ["zm1_room1_mode", "zm2_room3_mode"]

    async def test_alias_primary_map_built_once_reused_across_updates(self, mock_hass, mock_config_entry):
        """The alias-primary map is lazily built and reused on subsequent updates (9a6b5ff)."""
        primary = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 22.5})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, registers=[primary])
        coord._alias_map = {1000: ["temp", "temp_set"]}

        assert coord._alias_primary_map is None
        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
        first_map = coord._alias_primary_map
        assert first_map == {1000: "temp"}

        # Second update must reuse the same map object (identity check).
        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
        assert coord._alias_primary_map is first_map


class TestAsyncWriteRegister:
    async def test_write_updates_data_optimistically(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {"temp_set": 20.0}

        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp_set", writable=True)
        await coord.async_write_register(reg, 22.0)

        assert coord.data["temp_set"] == 22.0
        client.simulate_write.assert_called_once_with(reg, 22.0, dry_run=True)
        client.write_register.assert_called_once_with(reg, 22.0)

    async def test_write_updates_all_register_aliases_optimistically(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord._alias_map = {1000: ["temp", "temp_set"]}
        coord.data = {"temp": 20.0, "temp_set": 20.0}

        alias_reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp_set", writable=True)
        await coord.async_write_register(alias_reg, 22.0)

        assert coord.data["temp"] == 22.0
        assert coord.data["temp_set"] == 22.0

    async def test_write_triggers_delayed_refresh(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {}
        coord.async_request_refresh = AsyncMock()

        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="mode", writable=True)
        await coord.async_write_register(reg, 1)

        # Await the delayed refresh task directly instead of sleeping 0.6s for a
        # 0.5s delay (which is flaky on slow CI runners). Deterministic + fast.
        assert coord._delayed_refresh_task is not None
        await coord._delayed_refresh_task
        coord.async_request_refresh.assert_called_once()

    async def test_write_no_data_initializes(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = None
        coord.async_request_refresh = AsyncMock()

        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="mode", writable=True)
        # Should not crash even if data is None
        await coord.async_write_register(reg, 1)
        # Await the delayed refresh task directly (see test above for rationale).
        assert coord._delayed_refresh_task is not None
        await coord._delayed_refresh_task
        coord.async_request_refresh.assert_called_once()

    async def test_write_calls_async_update_listeners(self, mock_hass, mock_config_entry):
        """async_update_listeners() is called on every write for optimistic updates."""
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {"val": 0}
        coord.async_request_refresh = AsyncMock()
        coord.async_update_listeners = MagicMock()

        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="val", writable=True)
        await coord.async_write_register(reg, 5)
        coord.async_update_listeners.assert_called_once()

    async def test_write_failure_creates_write_rejected_issue(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock(side_effect=Exception("write rejected"))
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        reg = RegisterDef(address=1005, datatype=DataType.UCHAR, name="system_mode", writable=True)
        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            with pytest.raises(Exception, match="write rejected"):
                await coord.async_write_register(reg, 1)

        mock_ir.async_create_issue.assert_called_once_with(
            mock_hass,
            "idm_heatpump",
            "write_rejected",
            is_fixable=False,
            severity=mock_ir.IssueSeverity.WARNING,
            translation_key="write_rejected",
            translation_placeholders={"register": "system_mode", "address": "1005"},
        )

    async def test_multiple_writes_update_data_and_listeners(self, mock_hass, mock_config_entry):
        """Multiple consecutive writes each update data and notify listeners."""
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {"a": 0, "b": 0}
        coord.async_request_refresh = AsyncMock()
        coord.async_update_listeners = MagicMock()

        reg_a = RegisterDef(address=1000, datatype=DataType.UCHAR, name="a", writable=True)
        reg_b = RegisterDef(address=1001, datatype=DataType.UCHAR, name="b", writable=True)
        await coord.async_write_register(reg_a, 3)
        await coord.async_write_register(reg_b, 7)

        assert coord.data["a"] == 3
        assert coord.data["b"] == 7
        assert coord.async_update_listeners.call_count == 2

    async def test_write_failure_propagates(self, mock_hass, mock_config_entry):
        """If client.write_register raises, async_write_register propagates the exception."""
        client = MagicMock()
        client.write_register = AsyncMock(side_effect=Exception("write error"))
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {"x": 0}
        coord.async_request_refresh = AsyncMock()

        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="x", writable=True)
        with pytest.raises(Exception, match="write error"):
            await coord.async_write_register(reg, 1)

    async def test_shutdown_cancels_delayed_refresh_task(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {}
        coord.async_request_refresh = AsyncMock()

        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="mode", writable=True)
        await coord.async_write_register(reg, 1)
        assert coord._delayed_refresh_task is not None

        await coord.async_shutdown()

        assert coord._delayed_refresh_task.done()
        coord.async_request_refresh.assert_not_awaited()


class TestAsyncRefreshWebSupplement:
    async def test_web_authentication_failure_creates_specific_repair_issue(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            web_pin="1234",
            web_host="192.0.2.103",
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                side_effect=IdmWebAuthenticationFailed("PIN rejected"),
            ),
            patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir,
        ):
            await coord.async_refresh_web_supplement()

        assert coord.last_web_error == "IdmWebAuthenticationFailed: PIN rejected"
        mock_ir.async_create_issue.assert_called_once_with(
            mock_hass,
            "idm_heatpump",
            "web_authentication_failed",
            is_fixable=True,
            severity=mock_ir.IssueSeverity.WARNING,
            translation_key="web_authentication_failed",
            data={"entry_id": mock_config_entry.entry_id},
            translation_placeholders={"host": "192.0.2.103"},
        )

    async def test_web_refresh_failure_creates_repair_issue(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            web_pin="1234",
            web_host="192.0.2.103",
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                side_effect=TimeoutError("websocket timeout"),
            ) as read_web,
            patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir,
        ):
            await coord.async_refresh_web_supplement()

        read_web.assert_awaited_once()
        # The coordinator now passes a persistent client_pool so TCP+auth
        # overhead is paid once per session instead of every poll.
        call_kwargs = read_web.await_args.kwargs
        assert call_kwargs["model_hint"] == "Navigator 2.0 / 10"
        assert call_kwargs["preferred_variant"] is None
        assert call_kwargs["client_pool"] is coord._web_client_pool
        assert call_kwargs["allow_variant_fallback"] is True
        assert coord.last_web_error == "TimeoutError: websocket timeout"
        mock_ir.async_create_issue.assert_called_once_with(
            mock_hass,
            "idm_heatpump",
            "web_timeout",
            is_fixable=False,
            severity=mock_ir.IssueSeverity.WARNING,
            translation_key="web_timeout",
            translation_placeholders={"host": "192.0.2.103"},
        )

    async def test_web_refresh_success_updates_data_and_deletes_repair_issue(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_pin="1234")
        coord.data = {}
        previous_data = coord.data
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(
            navigator_version="Navigator 10",
            software_version="NAV10_20.24",
            heatpump_model="iPump",
            sensor_values={"hotgas_temperature": IdmWebSensorValue("44.7°C", 44.7, "°C")},
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir,
        ):
            await coord.async_refresh_web_supplement()

        assert coord.last_web_error is None
        assert coord.web_supplement is supplement
        assert coord.model_name == "Navigator 10"
        assert coord.firmware_version == "NAV10_20.24"
        assert coord.web_value_keys == ("hotgas_temperature",)
        assert coord.missing_web_core_values == ("navigator_version", "software_version", "heatpump_model")
        assert coord.data["web_navigator_version"] == "Navigator 10"
        assert coord.data["web_software_version"] == "NAV10_20.24"
        assert coord.data is not previous_data
        assert previous_data == {}
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "web_authentication_failed")
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "web_supplement_failed")
        coord.async_update_listeners.assert_called_once()

    async def test_web_refresh_merges_into_live_modbus_snapshot(self, mock_hass, mock_config_entry):
        """Web merge must re-read self.data after await so concurrent Modbus wins."""
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_pin="1234")
        coord.data = {"hp_flow_temp": 35.0}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(
            navigator_version="Navigator 10",
            software_version="NAV10_20.24",
            heatpump_model="iPump",
        )

        async def _read_web(*args, **kwargs):
            # Simulate a concurrent Modbus poll completing while web I/O runs.
            coord.data = {"hp_flow_temp": 36.5, "hp_return_temp": 30.0}
            return supplement

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                side_effect=_read_web,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.data["hp_flow_temp"] == 36.5
        assert coord.data["hp_return_temp"] == 30.0
        assert coord.data["web_navigator_version"] == "Navigator 10"

    async def test_web_refresh_web_firmware_prefix_overrides_weak_modbus_detection(self, mock_hass, mock_config_entry):
        """Web firmware NAV10 prefix corrects a weak Modbus Navigator 2.0 detection."""
        model_info = IdmModelInfo(
            model_name=MODEL_NAVIGATOR_20,
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 2.0",
            firmware_version=None,
            model_info=model_info,
            web_pin="1234",
        )
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(
            navigator_version="Navigator 10",
            software_version="NAV10_20.24",
            sensor_values={"navigator_version": IdmWebSensorValue("Navigator 10", "Navigator 10")},
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.model_name == "Navigator 10"
        assert coord.firmware_version == "NAV10_20.24"
        assert coord.web_supplement is supplement
        assert coord.data["web_navigator_version"] == "Navigator 10"

    async def test_web_refresh_success_reports_missing_core_values(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_pin="1234")
        supplement = IdmWebSupplement(
            navigator_version="Navigator 10",
            sensor_values={"navigator_version": IdmWebSensorValue("Navigator 10", "Navigator 10")},
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.web_value_keys == ("navigator_version",)
        assert coord.missing_web_core_values == ("software_version", "heatpump_model")

    async def test_web_refresh_persists_retroactive_navigator_detection(self, mock_hass, mock_config_entry):
        """Retroactively detected model/firmware must be persisted for reloads."""
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_pin="1234")
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(
            navigator_version="Navigator 10",
            software_version="NAV10_20.24",
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        mock_hass.config_entries.async_update_entry.assert_called_once()
        _, kwargs = mock_hass.config_entries.async_update_entry.call_args
        assert kwargs["data"]["detected_navigator_version"] == "Navigator 10"
        assert kwargs["data"]["detected_software_version"] == "NAV10_20.24"

    async def test_web_refresh_persists_when_firmware_prefix_resolves_conflict(self, mock_hass, mock_config_entry):
        """Persistence happens when NAV10 firmware prefix resolves a model conflict."""
        model_info = IdmModelInfo(
            model_name=MODEL_NAVIGATOR_20,
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 2.0",
            model_info=model_info,
            web_pin="1234",
        )
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(
            navigator_version="Navigator 10",
            software_version="NAV10_20.24",
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        mock_hass.config_entries.async_update_entry.assert_called_once()
        _, kwargs = mock_hass.config_entries.async_update_entry.call_args
        assert kwargs["data"]["detected_navigator_version"] == "Navigator 10"
        assert kwargs["data"]["detected_software_version"] == "NAV10_20.24"

    async def test_web_refresh_does_not_persist_on_conflict_without_firmware_prefix(self, mock_hass, mock_config_entry):
        """No persistence when web model conflicts without NAV10 firmware prefix."""
        model_info = IdmModelInfo(
            model_name=MODEL_NAVIGATOR_20,
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 2.0",
            model_info=model_info,
            web_pin="1234",
        )
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(
            navigator_version="Navigator 10",
            software_version="20.24",
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        mock_hass.config_entries.async_update_entry.assert_not_called()

    async def test_web_refresh_does_not_persist_unchanged_values(self, mock_hass, mock_config_entry):
        """No persistence when stored values already match the web detection."""
        mock_config_entry.data = {
            **mock_config_entry.data,
            "detected_navigator_version": "Navigator 10",
            "detected_software_version": "NAV10_20.24",
            "detected_web_variant": "nav10",
        }
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_pin="1234")
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(
            navigator_version="Navigator 10",
            software_version="NAV10_20.24",
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        mock_hass.config_entries.async_update_entry.assert_not_called()

    async def test_web_refresh_updates_model_info_when_undetected(self, mock_hass, mock_config_entry):
        """model_info with a generic/unknown name gets updated from web detection."""
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 2.0 / 10",
            model_info=None,
            web_pin="1234",
        )
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(navigator_version="Navigator 10")

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        # model_info stays None (nothing to update), but model_name is set
        assert coord.model_name == "Navigator 10"
        assert coord.model_info is None

    async def test_web_refresh_updates_generic_model_info_name(self, mock_hass, mock_config_entry):
        """model_info with a non-definitive name is updated to the web-detected model."""
        from idm_heatpump import MODEL_UNKNOWN

        model_info = IdmModelInfo(
            model_name=MODEL_UNKNOWN,
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 2.0 / 10",
            model_info=model_info,
            web_pin="1234",
        )
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(navigator_version="Navigator 10")

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.model_name == "Navigator 10"
        assert coord.model_info is not None
        assert coord.model_info.model_name == "Navigator 10"

    async def test_web_refresh_caches_navigator20_variant(self, mock_hass, mock_config_entry):
        """After a successful Nav 2.0 web read, the variant is cached for future polls."""
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_pin="1234")
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(navigator_version="Navigator 2.0", software_version="2.35")

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ) as read_web,
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.web_variant == "nav20"
        # First call: no cached variant
        _, kwargs = read_web.call_args
        assert kwargs.get("preferred_variant") is None

        # Second poll: cached variant is passed
        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ) as read_web2,
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        _, kwargs2 = read_web2.call_args
        assert kwargs2.get("preferred_variant") == "nav20"
        assert kwargs2.get("allow_variant_fallback") is False

    async def test_web_refresh_uses_stored_variant_even_without_snapshot(self, mock_hass, mock_config_entry):
        """A persisted factory choice remains locked when the initial web read failed."""
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            web_pin="1234",
            web_variant="nav20",
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                side_effect=TimeoutError("HTTP timeout"),
            ) as read_web,
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        kwargs = read_web.await_args.kwargs
        assert kwargs["preferred_variant"] == "nav20"
        assert kwargs["allow_variant_fallback"] is False

    async def test_web_refresh_caches_navigator10_variant(self, mock_hass, mock_config_entry):
        """After a successful Nav 10 web read, the variant is cached for future polls."""
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_pin="1234")
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(navigator_version="Navigator 10")

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.web_variant == "nav10"

    async def test_web_refresh_caches_navigator_pro_variant(self, mock_hass, mock_config_entry):
        """Navigator Pro uses the Nav 10 WebSocket web access variant."""
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_pin="1234")
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(navigator_version="Navigator Pro")

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.web_variant == "nav10"

    async def test_web_refresh_uses_heatpump_model_for_variant(self, mock_hass, mock_config_entry):
        """The cache also works when the web API exposes heatpump_model only."""
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_pin="1234")
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(heatpump_model="Navigator 2.0")

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.web_variant == "nav20"

    async def test_web_refresh_does_not_override_modbus_without_firmware_prefix(self, mock_hass, mock_config_entry):
        """Modbus still wins when web firmware lacks a NAV10 prefix."""
        model_info = IdmModelInfo(
            model_name=MODEL_NAVIGATOR_20,
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 2.0",
            firmware_version=None,
            model_info=model_info,
            web_pin="1234",
        )
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(
            navigator_version="Navigator 10",
            software_version="20.24",
            sensor_values={"navigator_version": IdmWebSensorValue("Navigator 10", "Navigator 10")},
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.model_name == "Navigator 2.0"
        assert coord.firmware_version is None
        assert coord.web_supplement is supplement
        assert coord.data["web_navigator_version"] == "Navigator 10"


class TestCoordinatorProperties:
    def test_client_property(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        assert coord.client is client

    def test_hide_unused_property(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.hide_unused is True
        coord2, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=False)
        assert coord2.hide_unused is False

    def test_registers_count_initial_zero(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.registers_count == 0

    def test_unused_registers_initially_empty(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.unused_registers == set()

    def test_unsupported_registers_initially_empty(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.unsupported_registers == set()


class TestSetupRegistersWithCascade:
    def test_cascade_registers_included(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        with patch(
            "custom_components.idm_heatpump.coordinator.collect_all_registers",
            return_value=[MagicMock()],
        ) as mock_collect:
            coord.setup_registers(["a"], 0, {}, enable_cascade=True)
        mock_collect.assert_called_once_with(["a"], 0, {}, True)

    def test_cascade_false_by_default(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        with patch(
            "custom_components.idm_heatpump.coordinator.collect_all_registers",
            return_value=[],
        ) as mock_collect:
            coord.setup_registers(["a"], 0, {})
        # Default enable_cascade=False
        mock_collect.assert_called_once_with(["a"], 0, {}, False)


class TestUnusedRegistersAccumulation:
    async def test_unused_registers_accumulate_across_updates(self, mock_hass, mock_config_entry):
        """Unused registers from different updates accumulate in the set."""
        client = MagicMock()
        client.read_batch = AsyncMock(
            side_effect=[
                {"x": UNUSED_VALUE, "y": 5.0},
                {"x": UNUSED_VALUE, "z": UNUSED_VALUE},
            ]
        )
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            hide_unused=True,
            registers=[
                RegisterDef(address=1000, datatype=DataType.UCHAR, name="x"),
                RegisterDef(address=1001, datatype=DataType.UCHAR, name="y"),
                RegisterDef(address=1002, datatype=DataType.UCHAR, name="z"),
            ],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
        assert "x" in coord.unused_registers
        assert "y" not in coord.unused_registers

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
        assert "z" in coord.unused_registers
        assert "x" in coord.unused_registers  # still there from first update

    async def test_unused_registers_not_tracked_when_hide_unused_false(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"x": UNUSED_VALUE, "y": 5.0})
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            hide_unused=False,
            registers=[
                RegisterDef(address=1000, datatype=DataType.UCHAR, name="x"),
                RegisterDef(address=1001, datatype=DataType.UCHAR, name="y"),
            ],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
        assert "x" not in coord.unused_registers
