"""Tests for IdmCoordinator."""

import asyncio
import contextlib
import logging
import socket
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from idm_heatpump import (
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_17,
    MODEL_NAVIGATOR_20,
    DataType,
    IdmConnectionError,
    IdmDeviceError,
    IdmModbusError,
    IdmModelInfo,
    IdmTransportError,
    IllegalAddressError,
    RegisterDef,
)

from custom_components.idm_heatpump.const import UNUSED_VALUE
from custom_components.idm_heatpump.coordinator import (
    IdmCoordinator,
    _friendly_communication_error,
    _is_illegal_address_error,
    _repair_issue_for_error,
    navigator_family,
)
from custom_components.idm_heatpump.web_data import (
    IdmWebAuthenticationFailed,
    IdmWebSensorValue,
    IdmWebSupplement,
)


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
        polling_jitter_percent=kwargs.get("polling_jitter_percent", 0),
        unused_module_suggestion_seconds=kwargs.get("unused_module_suggestion_seconds", 86400.0),
        write_cooldown_seconds=kwargs.get("write_cooldown_seconds", 5.0),
    )
    registers = kwargs.get("registers")
    if registers is not None:
        coord._registers = registers
        # Rebuild the derived name index and room-mode subset so tests that set
        # registers directly exercise the same cached lookups as production.
        coord._register_by_name = {reg.name: reg for reg in registers}
        from custom_components.idm_heatpump.coordinator import _is_zone_room_mode_register

        coord._room_mode_registers = [reg for reg in registers if _is_zone_room_mode_register(reg)]
    # Production absorbs short connection outages in a quiet window before
    # escalating (see TestQuietOutageWindow). The rest of this suite tests
    # the escalation semantics directly, so it opts out of the window here;
    # the quiet behaviour itself is covered with the period set explicitly.
    coord._quiet_outage_period = 0.0
    return coord, client


def test_energy_statistics_keep_power_registers_when_raw_entities_are_disabled(
    mock_hass, mock_config_entry, monkeypatch
):
    from types import SimpleNamespace

    from custom_components.idm_heatpump import polling_plan
    from custom_components.idm_heatpump.energy_statistics import EnergyStatistics

    coordinator, _ = _make_coordinator(mock_hass, mock_config_entry)
    coordinator.attach_energy_statistics(EnergyStatistics(mock_hass, "entry", 30))
    monkeypatch.setattr(
        polling_plan.er,
        "async_entries_for_config_entry",
        lambda *_: [SimpleNamespace(unique_id="entry_energy_electrical_total", disabled_by=None)],
    )
    required = polling_plan.build_required_register_names(
        object(),
        "entry",
        {"power_consumption_hp", "thermal_power_flow_sensor", "unrelated"},
        coordinator.externally_required_registers,
    )
    assert required == {"power_consumption_hp", "thermal_power_flow_sensor"}


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

    def test_detects_navigator_17(self):
        assert navigator_family("Navigator 1.7") == "navigator_17"
        assert navigator_family("IDM Navigator 1.7") == "navigator_17"
        assert navigator_family("navigator 1.7") == "navigator_17"

    def test_navigator_10_is_not_the_1_7_family(self):
        assert navigator_family("Navigator 10") != "navigator_17"

    def test_returns_none_when_both_20_and_10_mentioned(self):
        assert navigator_family("Navigator 2.0 vs Navigator 10") is None

    def test_returns_none_for_unknown_model(self):
        assert navigator_family("Terra SWM") is None
        assert navigator_family("SomeOther Model") is None


class TestCoordinatorInit:
    def test_model_info_is_synchronized_to_client(self, mock_hass, mock_config_entry):
        client = MagicMock()
        model_info = IdmModelInfo(
            model_name=MODEL_NAVIGATOR_20,
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )

        _make_coordinator(mock_hass, mock_config_entry, client=client, model_info=model_info)

        client.set_model_info.assert_called_once_with(model_info)

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

    def test_client_diagnostics_include_transport_details(self, mock_hass, mock_config_entry):
        from idm_heatpump import IdmClientDiagnostics

        client = MagicMock()
        # The API returns its own dataclass here, not a mapping; a mock that
        # returned a dict hid that the production path reads dataclass fields.
        client.get_diagnostics.return_value = IdmClientDiagnostics(
            navigator_type="Navigator 10",
            modbus_connected=True,
            firmware=None,
            last_error=None,
            permanently_failed_registers=(),
            connection_suspect=False,
            batch_unsafe_registers=(),
        )
        client.transport_diagnostics.return_value = {
            "endpoint": {"host": "**REDACTED**"},
            "capabilities": {
                "source": "modbus_connection.tmodbus",
                "supports_shared_connection": False,
            },
        }
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        diagnostics = coord.client_diagnostics()

        assert diagnostics["modbus_connected"] is True
        assert diagnostics["transport"]["endpoint"]["host"] == "**REDACTED**"
        assert diagnostics["transport"]["capabilities"]["source"] == "modbus_connection.tmodbus"

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
    def test_illegal_address_marker_attribute_is_recognized(self):
        assert _is_illegal_address_error(IllegalAddressError("device rejected request"))

    @pytest.mark.parametrize(
        ("error", "issue_id"),
        [
            (IdmConnectionError("connection lost"), "cannot_connect"),
            (
                IdmConnectionError(
                    "Modbus Error: [Connection] Failed to connect [Errno 111] Connect call failed ('192.0.2.11', 5020)"
                ),
                "modbus_connection_refused",
            ),
            (socket.gaierror("name or service not known"), "host_not_found"),
            (ConnectionRefusedError("connection refused"), "modbus_connection_refused"),
            (TimeoutError("timed out"), "modbus_timeout"),
            (IdmTransportError("No response received after 0 retries"), "modbus_timeout"),
            (IdmDeviceError("no response from slave 2"), "wrong_slave_id"),
            (IdmDeviceError("ExceptionResponse(exception_code=1) illegal function"), "incompatible_firmware"),
            (Exception("timeout"), "modbus_timeout"),
        ],
    )
    def test_classifies_communication_errors(self, error, issue_id):
        assert _repair_issue_for_error(error) == issue_id

    def test_connection_refused_message_is_actionable(self):
        message = _friendly_communication_error(
            "modbus_connection_refused",
            "192.0.2.11",
            5020,
            IdmConnectionError("connect call failed"),
        )

        assert "192.0.2.11:5020" in message
        assert "refused the Modbus TCP connection" in message
        assert "Modbus TCP is enabled" in message

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (IdmConnectionError("connection reset by peer"), "was interrupted"),
            (IdmConnectionError("No route to host (Errno 113)"), "no working network route"),
            (IdmDeviceError("Modbus response CRC error"), "response that could not be read"),
        ],
    )
    def test_generic_communication_errors_are_actionable(self, error, expected):
        message = _friendly_communication_error("cannot_connect", "192.0.2.11", 502, error)

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
        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="probe_float")
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True, registers=[reg])
        # FLOAT datatype default sentinel is -1.0 (SENT-01).
        assert coord.is_register_unused(reg.name, UNUSED_VALUE) is True

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
        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="probe_float")
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True, registers=[reg])
        # UNUSED_VALUE is -1.0; FLOAT default sentinel.
        assert coord.is_register_unused(reg.name, -1.0) is True

    def test_65535_is_unused(self, mock_hass, mock_config_entry):
        reg = RegisterDef(address=1200, datatype=DataType.UINT16, name="probe_uint16")
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True, registers=[reg])
        # UINT16 default sentinel is 65535 (SENT-01).
        assert coord.is_register_unused(reg.name, 65535) is True

    def test_255_is_unused(self, mock_hass, mock_config_entry):
        reg = RegisterDef(address=1201, datatype=DataType.UCHAR, name="probe_uchar")
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True, registers=[reg])
        # UCHAR default sentinel is 255 (SENT-01).
        assert coord.is_register_unused(reg.name, 255) is True

    def test_register_metadata_sentinel_is_unused(self, mock_hass, mock_config_entry):
        reg = RegisterDef(
            address=1714,
            datatype=DataType.UCHAR,
            name="external_pump_demand",
        )
        reg.sentinel_values = (254,)
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
        reg = RegisterDef(address=1202, datatype=DataType.INT16, name="probe_int16")
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True, registers=[reg])
        # INT16 default sentinel includes -32768 (SENT-01).
        assert coord.is_register_unused(reg.name, -32768) is True

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
        reg = RegisterDef(
            address=1104,
            datatype=DataType.INT16,
            name="charging_pump_status",
            sentinel_values=(-32768, 65535, 255),
        )
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True, registers=[reg])
        assert coord.is_register_unused(reg.name, -32768) is True
        assert coord.is_register_unused(reg.name, float("nan")) is True
        assert coord.is_register_unused(reg.name, None) is True

    def test_battery_soc_negative_one_is_unused(self, mock_hass, mock_config_entry):
        # battery_soc: -1 bedeutet "nicht verfügbar" → weiterhin unused.
        reg = RegisterDef(address=1658, datatype=DataType.INT16, name="battery_soc", sentinel_values=(-1,))
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True, registers=[reg])
        assert coord.is_register_unused(reg.name, -1) is True

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
        assert mock_ir.async_delete_issue.call_count == 8

    async def test_empty_data_raises_update_failed(self, mock_hass, mock_config_entry):
        from homeassistant.helpers.update_coordinator import UpdateFailed

        client = MagicMock()
        client.read_batch = AsyncMock(return_value={})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        with (
            patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir,
            pytest.raises(UpdateFailed, match="returned no usable register data"),
        ):
            await coord._async_update_data()

        assert mock_ir.async_create_issue.call_args.args[2] == "no_data_received_test_entry_id"

    async def test_exception_raises_update_failed(self, mock_hass, mock_config_entry):
        from homeassistant.helpers.update_coordinator import UpdateFailed

        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=IdmConnectionError("connection lost"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir, pytest.raises(UpdateFailed):
            await coord._async_update_data()
        mock_ir.async_create_issue.assert_called_once()

    def _degrade_web_alive(self, coord) -> None:
        """Put the coordinator into the web-supplement-alive state."""
        from datetime import UTC, datetime

        coord._web_pin = "1234"
        coord._web_alive = True
        coord._last_web_success = datetime.now(UTC)

    async def test_modbus_failure_with_web_alive_creates_the_calm_degraded_issue(self, mock_hass, mock_config_entry):
        from homeassistant.helpers.update_coordinator import UpdateFailed

        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=IdmConnectionError("connection lost"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )
        self._degrade_web_alive(coord)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir, pytest.raises(UpdateFailed):
            await coord._async_update_data()

        assert mock_ir.async_create_issue.call_args.args[2] == "modbus_degraded_web_active_test_entry_id"

    async def test_modbus_failure_without_web_keeps_the_regular_issue(self, mock_hass, mock_config_entry):
        from homeassistant.helpers.update_coordinator import UpdateFailed

        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=IdmConnectionError("connection lost"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir, pytest.raises(UpdateFailed):
            await coord._async_update_data()

        assert mock_ir.async_create_issue.call_args.args[2] != "modbus_degraded_web_active_test_entry_id"

    async def test_degraded_failure_logs_error_once_then_debug(self, mock_hass, mock_config_entry, caplog):
        import logging

        from homeassistant.helpers.update_coordinator import UpdateFailed

        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=IdmConnectionError("connection lost"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )
        self._degrade_web_alive(coord)

        with patch("custom_components.idm_heatpump.coordinator.ir"), pytest.raises(UpdateFailed):
            await coord._async_update_data()
        with patch("custom_components.idm_heatpump.coordinator.ir"), pytest.raises(UpdateFailed):
            await coord._async_update_data()

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1

    async def test_successful_poll_after_degradation_clears_the_calm_issue(self, mock_hass, mock_config_entry):
        from homeassistant.helpers.update_coordinator import UpdateFailed

        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=IdmConnectionError("connection lost"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )
        self._degrade_web_alive(coord)

        with patch("custom_components.idm_heatpump.coordinator.ir"), pytest.raises(UpdateFailed):
            await coord._async_update_data()

        client.read_batch = AsyncMock(return_value={"temp": 22.5})
        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir2:
            await coord._async_update_data()

        deleted = [call.args[2] for call in mock_ir2.async_delete_issue.call_args_list]
        assert "modbus_degraded_web_active_test_entry_id" in deleted

    async def test_unexpected_exception_propagates_uncaught(self, mock_hass, mock_config_entry):
        """A programming bug (not a communication error) must not be misclassified as cannot_connect."""
        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=ValueError("boom"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir, pytest.raises(ValueError, match="boom"):
            await coord._async_update_data()
        mock_ir.async_create_issue.assert_not_called()

    async def test_register_the_library_isolated_is_dropped_from_the_next_poll(self, mock_hass, mock_config_entry):
        """A register the API isolated is not offered to read_batch again.

        idm-heatpump-api answers an Illegal Data Address inside read_batch: it
        marks the register permanently failed and returns the rest of the
        group, so the exception never reaches the coordinator. What the
        coordinator owes is the skip-list, so the dead address is not part of
        the next request.
        """
        good_a = RegisterDef(address=1000, datatype=DataType.UCHAR, name="good_a")
        unsupported = RegisterDef(address=4108, datatype=DataType.FLOAT, name="power_limit_hp")
        good_b = RegisterDef(address=4122, datatype=DataType.FLOAT, name="good_b")
        calls: list[list[str]] = []

        async def read_batch(registers):
            calls.append([reg.name for reg in registers])
            return {reg.name: 1 for reg in registers if reg.name != "power_limit_hp"}

        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=read_batch)
        client.get_unsupported_registers = MagicMock(return_value=("power_limit_hp",))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[good_a, unsupported, good_b],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            data = await coord._async_update_data()

        assert data == {"good_a": 1, "good_b": 1}
        assert coord.unsupported_registers == {"power_limit_hp"}

        calls.clear()
        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
        assert calls == [["good_a", "good_b"]]

    async def test_unsupported_register_is_explained_in_the_log_once(self, mock_hass, mock_config_entry, caplog):
        """The user learns why an entity disappeared, and learns it only once.

        The API reports an unsupported register at debug level only, so without
        this line a default installation had nothing in its log explaining a
        permanently unavailable entity. It is a log line and not a repair
        issue: the controller not implementing an address is normal for a model
        or firmware without that function, and a repair card asking for action
        that does not exist reads like a defect.
        """
        unsupported = RegisterDef(address=4108, datatype=DataType.FLOAT, name="power_limit_hp")

        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"good_a": 1})
        client.get_unsupported_registers = MagicMock(return_value=("power_limit_hp",))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="good_a"), unsupported],
        )

        with caplog.at_level(logging.INFO, logger="custom_components.idm_heatpump.coordinator"):
            with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
                await coord._async_update_data()

            messages = [record.getMessage() for record in caplog.records]
            explained = [text for text in messages if "power_limit_hp" in text and "4108" in text]
            assert len(explained) == 1
            assert "needs no action" in explained[0]

            # No repair issue: nothing about this is actionable.
            assert mock_ir.async_create_issue.call_count == 0

            # A second poll re-reports the same name from the library; the
            # register is already known, so the user is not told again.
            caplog.clear()
            await coord._async_update_data()
            assert not [
                record.getMessage()
                for record in caplog.records
                if "power_limit_hp" in record.getMessage() and "4108" in record.getMessage()
            ]

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

    async def test_no_unsupported_registers_leaves_the_skip_list_empty(self, mock_hass, mock_config_entry):
        """A healthy plant reports nothing unsupported and raises no issue."""
        good = RegisterDef(address=1000, datatype=DataType.UCHAR, name="good_a")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"good_a": 1})
        client.get_unsupported_registers = MagicMock(return_value=())
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, registers=[good])

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            await coord._async_update_data()

        assert coord.unsupported_registers == set()
        issue_ids = [call.args[2] for call in mock_ir.async_create_issue.call_args_list]
        assert not any(issue_id.startswith("register_not_supported") for issue_id in issue_ids)

    @pytest.mark.parametrize(
        "error",
        [
            IdmConnectionError("connection lost"),
            IdmModbusError("Modbus response CRC error"),
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

        with (
            patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir,
            pytest.raises(Exception, match="IDM device"),
        ):
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
        client.read_register = AsyncMock(side_effect=IdmDeviceError("Illegal Data Address exception_code=2"))
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
        client.read_register = AsyncMock(side_effect=IdmTransportError("No response received"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[room_mode, later_room_mode],
        )

        with (
            patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir,
            pytest.raises(Exception, match="did not respond in time"),
        ):
            await coord._async_update_data()

        assert mock_ir.async_create_issue.call_args.args[2] == "modbus_timeout_test_entry_id"
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
                RegisterDef(address=1000, datatype=DataType.FLOAT, name="dead"),
                RegisterDef(address=1001, datatype=DataType.FLOAT, name="alive"),
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
                RegisterDef(address=1000, datatype=DataType.FLOAT, name="dead"),
                RegisterDef(address=1001, datatype=DataType.FLOAT, name="alive"),
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
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "cannot_connect_test_entry_id")

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

        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "cannot_connect_test_entry_id")
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "host_not_found_test_entry_id")
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "modbus_connection_refused_test_entry_id")
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "modbus_timeout_test_entry_id")
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "wrong_slave_id_test_entry_id")
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "incompatible_firmware_test_entry_id")

    async def test_issue_created_on_failure(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=TimeoutError("timeout"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir, pytest.raises(Exception):  # noqa: B017
            await coord._async_update_data()
        mock_ir.async_create_issue.assert_called_once()
        call_kwargs = mock_ir.async_create_issue.call_args
        assert call_kwargs is not None

    async def test_wrong_slave_id_issue_created_on_no_response(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=IdmDeviceError("no response from slave 3"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir, pytest.raises(Exception):  # noqa: B017
            await coord._async_update_data()

        assert mock_ir.async_create_issue.call_args.args[2] == "wrong_slave_id_test_entry_id"
        assert mock_ir.async_create_issue.call_args.kwargs["translation_key"] == "wrong_slave_id"

    async def test_incompatible_firmware_issue_created_on_illegal_function(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=IdmDeviceError("ExceptionResponse(exception_code=1)"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.UCHAR, name="temp")],
        )

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir, pytest.raises(Exception):  # noqa: B017
            await coord._async_update_data()

        assert mock_ir.async_create_issue.call_args.args[2] == "incompatible_firmware_test_entry_id"
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


class TestQuietOutageWindow:
    """Short connection outages stay quiet before the coordinator escalates.

    Inside the window a connection-class poll failure returns the last
    snapshot without a repair issue, without UpdateFailed and without an
    error line; connection-class write failures fold into the same window.
    _make_coordinator disables the window for the rest of the suite, so
    these tests re-enable it explicitly.
    """

    def _degrade_web_alive(self, coord) -> None:
        from datetime import UTC, datetime

        coord._web_pin = "1234"
        coord._web_alive = True
        coord._last_web_success = datetime.now(UTC)

    async def test_failure_inside_window_returns_last_snapshot_without_issue(
        self, mock_hass, mock_config_entry, caplog
    ):
        import logging

        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 20.0})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, registers=[reg])
        with patch("custom_components.idm_heatpump.coordinator.ir"):
            # async_refresh would store the poll result on the coordinator;
            # calling the data callback directly skips that, so do it by hand.
            coord.data = await coord._async_update_data()
        client.read_batch = AsyncMock(side_effect=IdmConnectionError("connection lost"))
        coord._quiet_outage_period = 300.0

        with (
            patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir,
            caplog.at_level(logging.INFO),
        ):
            result = await coord._async_update_data()

        assert result["temp"] == 20.0
        mock_ir.async_create_issue.assert_not_called()
        assert "retrying quietly" in caplog.text
        assert "created repair issue" not in caplog.text

    async def test_repeat_failures_inside_window_stay_at_debug_without_issue(
        self, mock_hass, mock_config_entry, caplog
    ):
        import logging

        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=IdmConnectionError("connection lost"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")],
        )
        coord._quiet_outage_period = 300.0

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir, caplog.at_level(logging.DEBUG):
            await coord._async_update_data()
            await coord._async_update_data()
            await coord._async_update_data()

        mock_ir.async_create_issue.assert_not_called()
        assert caplog.text.count("retrying quietly") == 1
        assert caplog.text.count("still down") == 2
        assert "created repair issue" not in caplog.text

    async def test_window_expiry_escalates_once_with_error_and_issue(self, mock_hass, mock_config_entry, caplog):
        import logging

        from homeassistant.helpers.update_coordinator import UpdateFailed

        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=IdmConnectionError("connection lost"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")],
        )
        coord._quiet_outage_period = 300.0

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir, caplog.at_level(logging.DEBUG):
            await coord._async_update_data()
            assert coord._outage_started is not None
            # Force the window to have elapsed; the next poll must escalate.
            coord._outage_started -= 400.0
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()
            assert mock_ir.async_create_issue.call_args.args[2] == "cannot_connect_test_entry_id"
            assert caplog.text.count("created repair issue") == 1
            # Further failures keep the issue but do not repeat the error.
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()
            assert caplog.text.count("created repair issue") == 1

            # Recovery after escalation logs the escalated wording (an issue
            # had been raised), not the short-outage one.
            client.read_batch = AsyncMock(return_value={"temp": 21.0})
            await coord._async_update_data()
            assert "recovered after" in caplog.text
            assert "raised no repair issue" not in caplog.text

    async def test_web_alive_short_outage_raises_no_degraded_issue_until_escalation(self, mock_hass, mock_config_entry):
        from homeassistant.helpers.update_coordinator import UpdateFailed

        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=IdmConnectionError("connection lost"))
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")],
        )
        self._degrade_web_alive(coord)
        coord._quiet_outage_period = 300.0

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            await coord._async_update_data()
            mock_ir.async_create_issue.assert_not_called()

            coord._outage_started -= 400.0
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()
        assert mock_ir.async_create_issue.call_args.args[2] == "modbus_degraded_web_active_test_entry_id"

    async def test_recovery_inside_window_closes_outage_and_next_outage_starts_fresh(
        self, mock_hass, mock_config_entry, caplog
    ):
        import logging

        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 20.0})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, registers=[reg])
        coord._quiet_outage_period = 300.0

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir, caplog.at_level(logging.INFO):
            client.read_batch = AsyncMock(side_effect=IdmConnectionError("connection lost"))
            await coord._async_update_data()
            assert coord._outage_started is not None

            client.read_batch = AsyncMock(return_value={"temp": 21.0})
            await coord._async_update_data()
            assert coord._outage_started is None
            assert "recovered after" in caplog.text
            assert "raised no repair issue" in caplog.text
            mock_ir.async_create_issue.assert_not_called()

            # A later blip is a fresh window: one new quiet line, still no issue.
            client.read_batch = AsyncMock(side_effect=IdmConnectionError("connection lost"))
            await coord._async_update_data()
        assert caplog.text.count("retrying quietly") == 2
        mock_ir.async_create_issue.assert_not_called()

    async def test_successful_write_closes_the_quiet_outage(self, mock_hass, mock_config_entry, caplog):
        import logging

        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")
        write_reg = RegisterDef(address=1002, datatype=DataType.FLOAT, name="temp_set", writable=True)
        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=IdmConnectionError("connection lost"))
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[reg, write_reg],
            write_cooldown_seconds=0,
        )
        coord._quiet_outage_period = 300.0

        with patch("custom_components.idm_heatpump.coordinator.ir"), caplog.at_level(logging.INFO):
            await coord._async_update_data()
            assert coord._outage_started is not None

            await coord.async_write_register(write_reg, 21.0)
        assert coord._outage_started is None
        assert "recovered after" in caplog.text

    async def test_write_failure_inside_window_skips_issue_and_logs_debug(self, mock_hass, mock_config_entry, caplog):
        import logging

        write_reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp_set", writable=True)
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 20.0})
        client.write_register = AsyncMock(side_effect=IdmConnectionError("connection lost"))
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, write_cooldown_seconds=0)
        coord._quiet_outage_period = 300.0

        with (
            patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir,
            caplog.at_level(logging.DEBUG),
            pytest.raises(IdmConnectionError),
        ):
            await coord.async_write_register(write_reg, 21.0)

        mock_ir.async_create_issue.assert_not_called()
        assert "was not delivered during the Modbus outage" in caplog.text
        assert "could not be delivered to the IDM controller" not in caplog.text

    async def test_write_failure_after_escalation_keeps_warning_and_issue(self, mock_hass, mock_config_entry, caplog):
        import logging
        import time as time_module

        write_reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp_set", writable=True)
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 20.0})
        client.write_register = AsyncMock(side_effect=IdmConnectionError("connection lost"))
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, write_cooldown_seconds=0)
        coord._quiet_outage_period = 300.0
        # An outage that already escalated (long outage) keeps the visible path.
        coord._outage_started = time_module.monotonic() - 400.0
        coord._outage_escalated = True

        with (
            patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir,
            caplog.at_level(logging.DEBUG),
            pytest.raises(IdmConnectionError),
        ):
            await coord.async_write_register(write_reg, 21.0)

        mock_ir.async_create_issue.assert_called_once()
        assert "could not be delivered to the IDM controller" in caplog.text

    def test_production_default_quiet_period_is_five_minutes(self):
        from custom_components.idm_heatpump import coordinator as coordinator_module

        assert coordinator_module._QUIET_OUTAGE_PERIOD == 300.0


class TestAsyncWriteRegister:
    async def test_write_cooldown_rejects_second_write_to_same_register(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            write_cooldown_seconds=10,
        )
        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp_set", writable=True)

        await coord.async_write_register(reg, 21.0)
        with pytest.raises(Exception) as err:
            await coord.async_write_register(reg, 22.0)

        assert getattr(err.value, "translation_key", None) == "write_cooldown_active"
        assert client.write_register.await_count == 1

    async def test_zero_write_cooldown_allows_immediate_writes(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            write_cooldown_seconds=0,
        )
        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp_set", writable=True)

        await coord.async_write_register(reg, 21.0)
        await coord.async_write_register(reg, 22.0)

        assert client.write_register.await_count == 2

    async def test_external_power_measurement_cooldown_capped_at_two_seconds(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            write_cooldown_seconds=10.0,
        )
        reg = RegisterDef(address=86, datatype=DataType.FLOAT, name="battery_soc", writable=True)

        current_time = 100.0
        with patch("custom_components.idm_heatpump.coordinator.time.monotonic", side_effect=lambda: current_time):
            await coord.async_write_register(reg, 90)
            assert client.write_register.await_count == 1

            # Still within 2.0 s cooldown -> rejected
            current_time = 101.0
            with pytest.raises(Exception) as err:
                await coord.async_write_register(reg, 91)
            assert getattr(err.value, "translation_key", None) == "write_cooldown_active"
            assert getattr(err.value, "translation_placeholders", {}).get("cooldown") == "2"

            # Past 2.0 s (at 2.5 s elapsed) -> allowed even though configured cooldown is 10.0 s
            current_time = 102.5
            await coord.async_write_register(reg, 92)
            assert client.write_register.await_count == 2

    async def test_external_power_measurement_skips_delayed_refresh_task(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        reg = RegisterDef(address=86, datatype=DataType.FLOAT, name="battery_soc", writable=True)

        await coord.async_write_register(reg, 90)
        assert coord._delayed_refresh_task is None

    async def test_write_with_confirm_false_skips_delayed_refresh_task(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="mode", writable=True)

        await coord.async_write_register(reg, 1, confirm=False)
        assert coord._delayed_refresh_task is None

    async def test_polling_jitter_delays_poll_within_configured_limit(self, mock_hass, mock_config_entry):
        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 20.0})
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[reg],
            polling_jitter_percent=20,
        )

        with (
            patch("custom_components.idm_heatpump.coordinator.random.uniform", return_value=1.25) as uniform,
            patch("custom_components.idm_heatpump.coordinator.asyncio.sleep", new_callable=AsyncMock) as sleep,
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord._async_update_data()

        uniform.assert_called_once_with(0, 2.0)
        sleep.assert_awaited_once_with(1.25)

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

    async def test_write_lifts_sentinel_state_immediately(self, mock_hass, mock_config_entry):
        """#172: a successful write moves a writable control from sentinel to the written value before the next poll."""
        from custom_components.idm_heatpump.const import UNUSED_VALUE

        client = MagicMock()
        client.write_register = AsyncMock()
        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp_set", writable=True)
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, registers=[reg])
        coord.data = {"temp_set": UNUSED_VALUE}

        # Pre-write: the sentinel value is treated as unused.
        assert coord.is_register_unused("temp_set", coord.data["temp_set"]) is True

        await coord.async_write_register(reg, 22.0)

        # Post-write: the optimistic update holds the written value immediately,
        # and is_register_unused no longer classifies it as a sentinel.
        assert coord.data["temp_set"] == 22.0
        assert coord.is_register_unused("temp_set", coord.data["temp_set"]) is False

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

    async def test_write_does_not_cancel_inflight_confirmation_refresh(self, mock_hass, mock_config_entry):
        """#537: a confirmation task already refreshing is left alone.

        Cancelling it inside async_request_refresh makes the DataUpdateCoordinator
        record a silently failed update: last_update_success drops without any
        log line and every entity reports unavailable until the next scheduled
        poll. The write path must only cancel the task while it still sleeps.
        """

        async def slow_refresh():
            await asyncio.sleep(0.2)

        original_refresh = None
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {}
        coord._write_cooldown_seconds = 0.0
        original_refresh = coord.async_request_refresh
        coord.async_request_refresh = slow_refresh

        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="mode", writable=True)
        await coord.async_write_register(reg, 1)
        first_task = coord._delayed_refresh_task
        assert first_task is not None

        # Rush past the 0.5 s sleep so the first confirmation is inside its
        # refresh, then write again: the in-flight task must survive.
        await asyncio.sleep(0.55)
        assert coord._confirmation_refresh_running is True
        await coord.async_write_register(reg, 2)

        assert not first_task.cancelled()
        await first_task
        coord.async_request_refresh = original_refresh

    async def test_write_cancels_sleeping_confirmation_refresh(self, mock_hass, mock_config_entry):
        """A confirmation still in its sleep phase is cancelled as before (#537)."""
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {}
        coord._write_cooldown_seconds = 0.0
        coord.async_request_refresh = AsyncMock()

        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="mode", writable=True)
        await coord.async_write_register(reg, 1)
        first_task = coord._delayed_refresh_task
        assert first_task is not None
        assert coord._confirmation_refresh_running is False

        await coord.async_write_register(reg, 2)

        # The sleep-phase cancellation ends the first task promptly (the
        # coroutine swallows the CancelledError; awaiting still re-raises it
        # to us, which is production-harmless — nothing awaits the old task).
        with contextlib.suppress(asyncio.CancelledError):
            await first_task
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
        with (
            patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir,
            pytest.raises(Exception, match="write rejected"),
        ):
            await coord.async_write_register(reg, 1)

        mock_ir.async_create_issue.assert_called_once_with(
            mock_hass,
            "idm_heatpump",
            "write_rejected_test_entry_id",
            is_fixable=False,
            severity=mock_ir.IssueSeverity.WARNING,
            translation_key="write_rejected",
            translation_placeholders={
                "register": "system_mode",
                "address": "1005",
                "detail": "Exception: write rejected",
            },
        )

    async def test_local_write_guard_does_not_claim_the_device_rejected_it(self, mock_hass, mock_config_entry):
        """A value the library refuses never reaches the controller (#237).

        Raising the "the heat pump rejected the write" repair issue for it sent
        users looking for a device fault that does not exist.
        """
        client = MagicMock()
        client.write_register = AsyncMock()
        client.simulate_write = MagicMock(
            side_effect=ValueError("EEPROM-sensitive register 'system_mode' was written too recently")
        )
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        reg = RegisterDef(address=1005, datatype=DataType.UCHAR, name="system_mode", writable=True)
        with (
            patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir,
            pytest.raises(ValueError, match="too recently"),
        ):
            await coord.async_write_register(reg, 1)

        mock_ir.async_create_issue.assert_not_called()
        client.write_register.assert_not_awaited()
        assert coord.last_write_error is not None
        assert coord.last_write_error["reached_device"] is False
        assert coord.last_write_error["translation_key"] == "write_eeprom_blocked"

    async def test_device_rejection_is_recorded_for_diagnostics(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock(
            side_effect=IdmDeviceError("Modbus write at address 1405 failed: refused (exception_code=4)")
        )
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        reg = RegisterDef(address=1405, datatype=DataType.FLOAT, name="hc_c_room_setpoint_heat_normal", writable=True)
        with (
            patch("custom_components.idm_heatpump.coordinator.ir"),
            pytest.raises(IdmModbusError),
        ):
            await coord.async_write_register(reg, 24.0)

        recorded = coord.last_write_error
        assert recorded is not None
        assert recorded["register"] == "hc_c_room_setpoint_heat_normal"
        assert recorded["address"] == 1405
        assert recorded["value"] == 24.0
        assert recorded["reached_device"] is True
        assert recorded["translation_key"] == "write_rejected_by_device"
        assert "Modbus exception code 4" in recorded["detail"]

    async def test_successful_write_clears_the_last_write_error(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.async_request_refresh = AsyncMock()
        coord._last_write_error = {"register": "system_mode"}

        reg = RegisterDef(address=1005, datatype=DataType.UCHAR, name="system_mode", writable=True)
        await coord.async_write_register(reg, 1)

        assert coord.last_write_error is None

    @pytest.mark.parametrize(
        "error",
        [
            IdmConnectionError("could not connect to example.invalid:5020"),
            IdmTransportError("connection reset"),
            TimeoutError("timed out"),
        ],
    )
    async def test_connection_write_failure_is_not_a_device_rejection(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock, error: Exception
    ) -> None:
        client = MagicMock()
        client.write_register = AsyncMock(side_effect=error)
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        reg = RegisterDef(address=74, datatype=DataType.FLOAT, name="pv_surplus", writable=True)
        with patch("custom_components.idm_heatpump.coordinator.ir") as registry, pytest.raises(type(error)):
            await coord.async_write_register(reg, 0)
        assert registry.async_create_issue.call_args.kwargs["translation_key"] == "write_connection_failed"
        assert registry.async_create_issue.call_args.args[2] == "write_rejected_test_entry_id"

    @pytest.mark.parametrize(
        "placeholders,cleared", [({"address": "74"}, True), ({"address": "86"}, False), (None, False)]
    )
    async def test_recovered_write_clears_only_the_matching_persisted_issue(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock, placeholders: dict[str, str] | None, cleared: bool
    ) -> None:
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        reg = RegisterDef(address=74, datatype=DataType.FLOAT, name="pv_surplus", writable=True)
        with patch("custom_components.idm_heatpump.coordinator.ir") as registry:
            registry.async_get.return_value.async_get_issue.return_value = SimpleNamespace(
                translation_placeholders=placeholders
            )
            await coord.async_write_register(reg, 0)
        if cleared:
            registry.async_delete_issue.assert_called_once_with(
                mock_hass, "idm_heatpump", "write_rejected_test_entry_id"
            )
        else:
            registry.async_delete_issue.assert_not_called()

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

    async def test_shutdown_runs_the_base_coordinator_shutdown(self, mock_hass, mock_config_entry):
        """The scheduled poll must not outlive the config entry.

        DataUpdateCoordinator.async_shutdown owns the parts this class cannot
        reach: the shutdown flag, the refresh timer and the request debouncer.
        Overriding it without calling up left the timer armed, so the poll it
        scheduled ran after async_unload_entry had disconnected the client.
        """
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)

        await coord.async_shutdown()

        assert coord.shutdown_called is True
        assert coord._shutdown_requested is True

    async def test_refresh_after_shutdown_is_ignored(self, mock_hass, mock_config_entry):
        """A refresh requested after shutdown must not reach the closed client."""
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)

        await coord.async_shutdown()
        await coord.async_request_refresh()

        assert coord.refresh_requests == 0

    async def test_shutdown_closes_the_web_client_pool(self, mock_hass, mock_config_entry):
        """The persistent Navigator web connection is released on unload."""
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        # IdmWebClientPool defines __slots__, so the pool is replaced rather
        # than patched in place.
        pool = MagicMock()
        pool.close = AsyncMock()
        coord._web_client_pool = pool

        await coord.async_shutdown()

        pool.close.assert_awaited_once()


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
            "web_authentication_failed_test_entry_id",
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
            "web_timeout_test_entry_id",
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
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "web_authentication_failed_test_entry_id")
        mock_ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "web_supplement_failed_test_entry_id")
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
        coord, client = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 2.0",
            firmware_version=None,
            model_info=model_info,
            web_pin="1234",
        )
        client.set_model_info.reset_mock()
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
        client.set_model_info.assert_called_once_with(coord.model_info)

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

    async def test_web_refresh_conflict_warning_logged_once(self, mock_hass, mock_config_entry, caplog):
        """The recurring web model-conflict warning is logged once, not per poll (#381)."""
        model_info = IdmModelInfo(
            model_name=MODEL_NAVIGATOR_10,
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
            model_name="Navigator 10",
            model_info=model_info,
            web_pin="1234",
        )
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        # Navigator 2.0 Pro scenario: firmware without NAV10 prefix, so the
        # conflict is never auto-corrected and used to warn on every web poll.
        supplement = IdmWebSupplement(
            navigator_version="Navigator 2.0",
            software_version="20.24-311-gfbf39bd77",
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
            caplog.at_level(logging.WARNING, logger="custom_components.idm_heatpump.coordinator"),
        ):
            await coord.async_refresh_web_supplement()
            await coord.async_refresh_web_supplement()

        messages = [
            record.getMessage()
            for record in caplog.records
            if "Ignoring conflicting IDM web Navigator model" in record.getMessage()
        ]
        assert len(messages) == 1
        assert "Navigator 2.0" in messages[0]
        assert "Navigator 10" in messages[0]

        # A changed conflicting pair is a new situation and warns again.
        coord._web_model_conflict_logged = ("Navigator 2.0", "Some other model")
        caplog.clear()
        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
            caplog.at_level(logging.WARNING, logger="custom_components.idm_heatpump.coordinator"),
        ):
            await coord.async_refresh_web_supplement()

        messages = [
            record.getMessage()
            for record in caplog.records
            if "Ignoring conflicting IDM web Navigator model" in record.getMessage()
        ]
        assert len(messages) == 1

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
        coord, client = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 2.0 / 10",
            model_info=model_info,
            web_pin="1234",
        )
        client.set_model_info.reset_mock()
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
        client.set_model_info.assert_called_once_with(coord.model_info)

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

    async def test_web_model_correction_syncs_device_registry(self, mock_hass, mock_config_entry):
        """A runtime model correction must reach the already-registered device (#192).

        entry_id-scoped registration only happens once, when platforms are set
        up; a later retroactive correction from the web supplement does not by
        itself trigger a reload, so without an explicit registry sync the HA
        device page would keep showing the original (possibly wrong) model
        indefinitely while diagnostics already reflects the correction.
        """
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 2.0 / 10",
            model_info=None,
            web_pin="1234",
        )
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        coord._hierarchy_device_ids = {("idm_heatpump", mock_config_entry.entry_id): "registry-device-1"}
        supplement = IdmWebSupplement(navigator_version="Navigator 10")

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
            patch("custom_components.idm_heatpump.coordinator.dr") as mock_dr,
        ):
            await coord.async_refresh_web_supplement()

        mock_registry = mock_dr.async_get.return_value
        mock_registry.async_update_device.assert_called_once_with("registry-device-1", model="Navigator 10")

    async def test_web_refresh_without_model_change_skips_device_registry_sync(self, mock_hass, mock_config_entry):
        """No registry write when the corrected model matches what was already stored."""
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 10",
            model_info=None,
            web_pin="1234",
        )
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        coord._hierarchy_device_ids = {("idm_heatpump", mock_config_entry.entry_id): "registry-device-1"}
        supplement = IdmWebSupplement(navigator_version="Navigator 10")

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
            patch("custom_components.idm_heatpump.coordinator.dr") as mock_dr,
        ):
            await coord.async_refresh_web_supplement()

        mock_dr.async_get.return_value.async_update_device.assert_not_called()

    async def test_web_refresh_newly_available_serial_syncs_device_registry(self, mock_hass, mock_config_entry):
        """A newly available myidm_id alone (model/firmware unchanged) still syncs the registry."""
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 10",
            model_info=None,
            web_pin="1234",
        )
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        coord._hierarchy_device_ids = {("idm_heatpump", mock_config_entry.entry_id): "registry-device-1"}
        supplement = IdmWebSupplement(navigator_version="Navigator 10", myidm_id="ABC123")

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                return_value=supplement,
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
            patch("custom_components.idm_heatpump.coordinator.dr") as mock_dr,
        ):
            await coord.async_refresh_web_supplement()

        mock_dr.async_get.return_value.async_update_device.assert_called_once_with(
            "registry-device-1", model="Navigator 10", serial_number="ABC123"
        )

    async def test_web_model_correction_without_registered_device_is_a_noop(self, mock_hass, mock_config_entry):
        """Missing hierarchy device id (e.g. device not yet precreated) must not raise."""
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
            patch("custom_components.idm_heatpump.coordinator.dr") as mock_dr,
        ):
            await coord.async_refresh_web_supplement()

        assert coord.model_name == "Navigator 10"
        mock_dr.async_get.return_value.async_update_device.assert_not_called()


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
                RegisterDef(address=1000, datatype=DataType.FLOAT, name="x"),
                RegisterDef(address=1001, datatype=DataType.FLOAT, name="y"),
                RegisterDef(address=1002, datatype=DataType.FLOAT, name="z"),
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


class TestModelConflictSummary:
    """#170: read-only detection-source summary for diagnostics (no I/O, no selection)."""

    def test_no_conflict_when_families_match(self, mock_hass, mock_config_entry):
        from custom_components.idm_heatpump.const import CONF_DETECTED_NAVIGATOR_VERSION

        mock_config_entry.data = {CONF_DETECTED_NAVIGATOR_VERSION: "Navigator 10"}
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, model_name="Navigator 10")
        summary = coord.model_conflict_summary
        assert summary["selected_family"] == "navigator_10"
        assert summary["stored_family"] == "navigator_10"
        assert summary["conflict"] is False

    def test_conflict_when_stored_and_modbus_disagree(self, mock_hass, mock_config_entry):
        from custom_components.idm_heatpump.const import CONF_DETECTED_NAVIGATOR_VERSION

        mock_config_entry.data = {CONF_DETECTED_NAVIGATOR_VERSION: "Navigator 20"}
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, model_name="Navigator 10")
        summary = coord.model_conflict_summary
        assert summary["conflict"] is True
        assert summary["selected_family"] == "navigator_10"
        assert summary["stored_family"] == "navigator_20"

    def test_manual_override_exposed(self, mock_hass, mock_config_entry):
        from custom_components.idm_heatpump.const import CONF_DETECTED_NAVIGATOR_VERSION, CONF_MODEL_OVERRIDE

        mock_config_entry.data = {
            CONF_DETECTED_NAVIGATOR_VERSION: "Navigator 10",
            CONF_MODEL_OVERRIDE: "navigator_10",
        }
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, model_name="Navigator 10")
        summary = coord.model_conflict_summary
        assert summary["manual_override"] == "navigator_10"

    def test_no_conflict_when_stored_missing(self, mock_hass, mock_config_entry):
        # Generic model name → navigator_family None → never conflicts.
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, model_name="Navigator 2.0 / 10")
        mock_config_entry.data = {}
        summary = coord.model_conflict_summary
        assert summary["selected_family"] is None
        assert summary["conflict"] is False


class TestWebVariantModelConflict:
    """#192: the connected web client is evidence about the controller generation.

    The nav10 client speaks a WebSocket on port 61220, the nav20 client local
    HTTP with CSRF handling, so the one that answered identifies the generation.
    Weighing only the Modbus and stored families reported "conflict: false" for
    a Navigator 2.0 that Modbus detection had labelled Navigator 10 — the exact
    case this summary exists to surface.
    """

    def test_web_variant_contradicting_the_model_is_a_conflict(self, mock_hass, mock_config_entry):
        from custom_components.idm_heatpump.const import CONF_DETECTED_NAVIGATOR_VERSION

        mock_config_entry.data = {CONF_DETECTED_NAVIGATOR_VERSION: "Navigator 10"}
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, model_name="Navigator 10")
        coord._web_variant = "nav20"

        summary = coord.model_conflict_summary

        assert summary["selected_family"] == "navigator_10"
        assert summary["stored_family"] == "navigator_10"
        assert summary["web_variant"] == "nav20"
        assert summary["expected_web_variant"] == "nav10"
        assert summary["web_variant_conflict"] is True
        assert summary["conflict"] is True

    def test_matching_web_variant_is_not_a_conflict(self, mock_hass, mock_config_entry):
        from custom_components.idm_heatpump.const import CONF_DETECTED_NAVIGATOR_VERSION

        mock_config_entry.data = {CONF_DETECTED_NAVIGATOR_VERSION: "Navigator 10"}
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, model_name="Navigator 10")
        coord._web_variant = "nav10"

        summary = coord.model_conflict_summary

        assert summary["web_variant_conflict"] is False
        assert summary["conflict"] is False

    def test_navigator_pro_on_the_nav10_client_is_not_a_conflict(self, mock_hass, mock_config_entry):
        """Navigator Pro answers the nav10 client, so that pairing is agreement."""
        from custom_components.idm_heatpump.const import CONF_DETECTED_NAVIGATOR_VERSION

        mock_config_entry.data = {CONF_DETECTED_NAVIGATOR_VERSION: "Navigator Pro"}
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, model_name="Navigator Pro")
        coord._web_variant = "nav10"

        summary = coord.model_conflict_summary

        assert summary["expected_web_variant"] == "nav10"
        assert summary["web_variant_conflict"] is False
        assert summary["conflict"] is False

    def test_no_web_variant_leaves_the_verdict_unchanged(self, mock_hass, mock_config_entry):
        from custom_components.idm_heatpump.const import CONF_DETECTED_NAVIGATOR_VERSION

        mock_config_entry.data = {CONF_DETECTED_NAVIGATOR_VERSION: "Navigator 10"}
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, model_name="Navigator 10")
        coord._web_variant = None

        summary = coord.model_conflict_summary

        assert summary["web_variant_conflict"] is False
        assert summary["conflict"] is False

    def test_ambiguous_families_do_not_invent_a_web_conflict(self, mock_hass, mock_config_entry):
        """Families that already disagree must not also be read as a variant conflict."""
        from custom_components.idm_heatpump.const import CONF_DETECTED_NAVIGATOR_VERSION

        mock_config_entry.data = {CONF_DETECTED_NAVIGATOR_VERSION: "Navigator 2.0"}
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, model_name="Navigator 10")
        coord._web_variant = "nav20"

        summary = coord.model_conflict_summary

        assert summary["expected_web_variant"] is None
        assert summary["web_variant_conflict"] is False
        # The family disagreement itself is still reported.
        assert summary["conflict"] is True


class TestScanIntervalSelfDiagnosis:
    """Polls that saturate their own interval must be reported, not absorbed."""

    _ISSUE_ID = "scan_interval_too_low_test_entry_id"

    def _poll(self, coord, mock_ir, duration: float, times: int = 1) -> None:
        for _ in range(times):
            coord._evaluate_poll_duration(duration)

    def test_single_slow_poll_does_not_warn(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            self._poll(coord, mock_ir, 9.5)

        mock_ir.async_create_issue.assert_not_called()

    def test_sustained_slow_polls_create_the_issue_once(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            self._poll(coord, mock_ir, 9.5, times=25)

        mock_ir.async_create_issue.assert_called_once()
        assert mock_ir.async_create_issue.call_args.args[2] == self._ISSUE_ID
        placeholders = mock_ir.async_create_issue.call_args.kwargs["translation_placeholders"]
        assert placeholders["duration"] == "9.5"
        assert placeholders["interval"] == "10"

    def test_fast_polls_below_the_ratio_never_warn(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            self._poll(coord, mock_ir, 7.9, times=50)

        mock_ir.async_create_issue.assert_not_called()

    def test_occasional_slow_poll_does_not_accumulate(self, mock_hass, mock_config_entry):
        """A slow poll every other cycle must not add up to a warning."""
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            for _ in range(30):
                coord._evaluate_poll_duration(9.5)
                coord._evaluate_poll_duration(1.0)

        mock_ir.async_create_issue.assert_not_called()

    def test_issue_clears_only_after_a_sustained_fast_streak(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            self._poll(coord, mock_ir, 9.5, times=10)
            mock_ir.async_create_issue.assert_called_once()

            # A short recovery must not clear the issue yet (no flapping).
            self._poll(coord, mock_ir, 1.0, times=9)
            mock_ir.async_delete_issue.assert_not_called()

            self._poll(coord, mock_ir, 1.0)
            mock_ir.async_delete_issue.assert_called_once_with(mock_hass, "idm_heatpump", self._ISSUE_ID)

    def test_issue_is_raised_again_after_recovery(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            self._poll(coord, mock_ir, 9.5, times=10)
            self._poll(coord, mock_ir, 1.0, times=10)
            self._poll(coord, mock_ir, 9.5, times=10)

        assert mock_ir.async_create_issue.call_count == 2

    def test_web_only_entries_without_interval_are_skipped(self, mock_hass, mock_config_entry):
        """Web-only mode disables the Modbus interval; nothing to compare against."""
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        coord.update_interval = None

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            self._poll(coord, mock_ir, 60.0, times=50)

        mock_ir.async_create_issue.assert_not_called()

    async def test_successful_poll_feeds_the_evaluation(self, mock_hass, mock_config_entry):
        """The metric comes from the real poll path, not only from unit calls."""
        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 21.0})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, registers=[reg])

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()

        assert coord._fast_poll_streak == 1
        assert coord._slow_poll_streak == 0


def test_register_map_names_stay_complete_when_polling_narrows(mock_hass, mock_config_entry):
    """The full configured register map stays queryable after a polling-plan narrowing."""
    registers = [
        RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp"),
        RegisterDef(address=1002, datatype=DataType.FLOAT, name="dhw_temp"),
        RegisterDef(address=1004, datatype=DataType.FLOAT, name="hp_flow_temp"),
    ]
    coord, _ = _make_coordinator(mock_hass, mock_config_entry, registers=registers)

    assert coord.register_map_names == {"outdoor_temp", "dhw_temp", "hp_flow_temp"}

    coord.set_active_registers(registers[:1], total=len(registers))

    assert coord.active_registers == tuple(registers[:1])
    assert coord.register_map_names == {"outdoor_temp", "dhw_temp", "hp_flow_temp"}


async def test_unused_solar_module_raises_a_suggestion_issue(mock_hass, mock_config_entry):
    """A solar block that only ever reports unused earns the module-off suggestion."""
    registers = [
        RegisterDef(address=1850, datatype=DataType.FLOAT, name="solar_collector_temp"),
        RegisterDef(address=1002, datatype=DataType.FLOAT, name="solar_charging_temp"),
        RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp"),
    ]
    client = MagicMock()
    client.read_batch = AsyncMock(
        return_value={"solar_collector_temp": -1.0, "solar_charging_temp": -1.0, "outdoor_temp": 20.0}
    )
    coord, _ = _make_coordinator(
        mock_hass,
        mock_config_entry,
        client=client,
        registers=registers,
        unused_module_suggestion_seconds=0.0,
    )

    with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
        mock_ir.async_get.return_value.async_get_issue.return_value = None
        # The first poll starts the clock, the second crosses the threshold.
        await coord._async_update_data()
        mock_ir.async_create_issue.assert_not_called()
        await coord._async_update_data()

    mock_ir.async_create_issue.assert_called_once()
    issue_id = mock_ir.async_create_issue.call_args.args[2]
    assert issue_id == f"solar_module_unused_{mock_config_entry.entry_id}"
    assert mock_ir.async_create_issue.call_args.kwargs["is_fixable"] is True
    assert mock_ir.async_create_issue.call_args.kwargs["data"] == {"entry_id": mock_config_entry.entry_id}


async def test_live_solar_values_withdraw_the_suggestion(mock_hass, mock_config_entry):
    """A single live solar register clears the timer and deletes the issue."""
    registers = [
        RegisterDef(address=1850, datatype=DataType.FLOAT, name="solar_collector_temp"),
        RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp"),
    ]
    client = MagicMock()
    client.read_batch = AsyncMock(return_value={"solar_collector_temp": -1.0, "outdoor_temp": 20.0})
    coord, _ = _make_coordinator(
        mock_hass,
        mock_config_entry,
        client=client,
        registers=registers,
        unused_module_suggestion_seconds=0.0,
    )

    with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
        mock_ir.async_get_issue.return_value = MagicMock()
        await coord._async_update_data()
        client.read_batch = AsyncMock(return_value={"solar_collector_temp": 55.0, "outdoor_temp": 20.0})
        await coord._async_update_data()

        # The coordinator also clears stale communication issues on a good
        # poll, so the solar deletion is asserted as one call among them.
        mock_ir.async_delete_issue.assert_any_call(
            mock_hass, "idm_heatpump", f"solar_module_unused_{mock_config_entry.entry_id}"
        )
        assert coord._solar_unused_since is None


async def test_dismissed_solar_suggestion_stays_away(mock_hass, mock_config_entry):
    """After choosing to keep the module, polls no longer re-raise the issue."""
    registers = [
        RegisterDef(address=1850, datatype=DataType.FLOAT, name="solar_collector_temp"),
        RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp"),
    ]
    client = MagicMock()
    client.read_batch = AsyncMock(return_value={"solar_collector_temp": -1.0, "outdoor_temp": 20.0})
    coord, _ = _make_coordinator(
        mock_hass,
        mock_config_entry,
        client=client,
        registers=registers,
        unused_module_suggestion_seconds=0.0,
    )
    coord.dismiss_solar_suggestion()

    with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
        mock_ir.async_get.return_value.async_get_issue.return_value = None
        await coord._async_update_data()
        await coord._async_update_data()

    mock_ir.async_create_issue.assert_not_called()


class TestTransientZeroGuard:
    """Single-poll zeros on lifetime kWh counters must not reach HA.

    A same-generation controller was observed answering one poll with 0.0 on
    a monotonic energy counter (kodebach/hacs-idm-heatpump#322); Home
    Assistant then books the whole lifetime counter as fresh consumption in
    utility_meter and long-term statistics. The guard holds the value
    unavailable for exactly one poll.
    """

    def _coordinator(self, mock_hass, mock_config_entry):
        return _make_coordinator(mock_hass, mock_config_entry)[0]

    def test_transient_zero_on_lifetime_counter_is_suppressed(self, mock_hass, mock_config_entry):
        coordinator = self._coordinator(mock_hass, mock_config_entry)
        coordinator.data = {"energy_heating": 40482.83, "outdoor_temp": 7.0}

        data = {"energy_heating": 0.0, "outdoor_temp": 7.1}
        coordinator._suppress_transient_counter_zeros(data)

        assert "energy_heating" not in data
        assert data["outdoor_temp"] == 7.1
        assert coordinator.transient_zero_suppressed == 1

    def test_second_consecutive_zero_passes_as_real_reset(self, mock_hass, mock_config_entry):
        coordinator = self._coordinator(mock_hass, mock_config_entry)
        # First poll already suppressed the key, so the previous snapshot no
        # longer carries it - the second zero is a genuine device-side reset.
        coordinator.data = {"outdoor_temp": 7.0}

        data = {"energy_heating": 0.0}
        coordinator._suppress_transient_counter_zeros(data)

        assert data["energy_heating"] == 0.0
        assert coordinator.transient_zero_suppressed == 0

    def test_zero_without_a_previous_value_passes(self, mock_hass, mock_config_entry):
        coordinator = self._coordinator(mock_hass, mock_config_entry)
        coordinator.data = {}

        data = {"energy_dhw": 0.0}
        coordinator._suppress_transient_counter_zeros(data)

        assert data["energy_dhw"] == 0.0

    def test_non_counter_register_zero_is_never_touched(self, mock_hass, mock_config_entry):
        coordinator = self._coordinator(mock_hass, mock_config_entry)
        coordinator.data = {"power_consumption_hp": 1.5}

        data = {"power_consumption_hp": 0.0}
        coordinator._suppress_transient_counter_zeros(data)

        assert data["power_consumption_hp"] == 0.0
        assert coordinator.transient_zero_suppressed == 0

    def test_normal_counter_progress_is_untouched(self, mock_hass, mock_config_entry):
        coordinator = self._coordinator(mock_hass, mock_config_entry)
        coordinator.data = {"energy_heating": 40482.83}

        data = {"energy_heating": 40484.52}
        coordinator._suppress_transient_counter_zeros(data)

        assert data["energy_heating"] == 40484.52
        assert coordinator.transient_zero_suppressed == 0

    def test_web_lifetime_counter_zero_is_suppressed(self, mock_hass, mock_config_entry):
        coordinator = self._coordinator(mock_hass, mock_config_entry)
        coordinator._web_supplement = IdmWebSupplement(
            sensor_values={"heat_quantity_heating_total": IdmWebSensorValue("40482.83", 40482.83, "kWh")}
        )
        incoming = IdmWebSupplement(
            sensor_values={
                "heat_quantity_heating_total": IdmWebSensorValue("0", 0.0, "kWh"),
                "heat_quantity_heating_today": IdmWebSensorValue("0", 0.0, "kWh"),
            }
        )

        guarded = coordinator._suppress_transient_web_counter_zeros(incoming)

        # The lifetime total is held unavailable for one poll ...
        assert "heat_quantity_heating_total" not in guarded.sensor_values
        # ... while today's counter legitimately returns to zero and passes.
        assert "heat_quantity_heating_today" in guarded.sensor_values
        assert coordinator.transient_zero_suppressed == 1

    def test_web_second_consecutive_zero_passes(self, mock_hass, mock_config_entry):
        coordinator = self._coordinator(mock_hass, mock_config_entry)
        coordinator._web_supplement = IdmWebSupplement(
            sensor_values={
                "heat_quantity_heating_total": IdmWebSensorValue("0", 0.0, "kWh"),
            }
        )
        incoming = IdmWebSupplement(sensor_values={"heat_quantity_heating_total": IdmWebSensorValue("0", 0.0, "kWh")})

        guarded = coordinator._suppress_transient_web_counter_zeros(incoming)

        assert "heat_quantity_heating_total" in guarded.sensor_values
        assert coordinator.transient_zero_suppressed == 0

    def test_web_guard_keeps_other_fields_of_the_supplement(self, mock_hass, mock_config_entry):
        coordinator = self._coordinator(mock_hass, mock_config_entry)
        coordinator._web_supplement = IdmWebSupplement(
            navigator_version="Navigator 10",
            sensor_values={"heat_quantity_heating_total": IdmWebSensorValue("500.0", 500.0, "kWh")},
        )
        incoming = IdmWebSupplement(
            navigator_version="Navigator 10",
            values={"heat_quantity_heating_total": "0"},
            sensor_values={"heat_quantity_heating_total": IdmWebSensorValue("0", 0.0, "kWh")},
        )

        guarded = coordinator._suppress_transient_web_counter_zeros(incoming)

        assert guarded.navigator_version == "Navigator 10"
        assert "heat_quantity_heating_total" not in guarded.values
        assert "heat_quantity_heating_total" not in guarded.sensor_values


class TestWebWriteMethods:
    """The web-only write path routes through the pooled web client."""

    def _coordinator_with_pool(self, mock_hass, mock_config_entry, client):
        coordinator, _ = _make_coordinator(mock_hass, mock_config_entry)
        pool = MagicMock()
        pool.get.return_value = (client, "nav10")
        coordinator._web_client_pool = pool
        coordinator.async_refresh_web_supplement = AsyncMock()
        return coordinator

    async def test_set_system_mode_uses_the_pooled_client_and_reads_back(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.set_system_mode = AsyncMock()
        coordinator = self._coordinator_with_pool(mock_hass, mock_config_entry, client)

        await coordinator.async_web_set_system_mode(4)

        client.set_system_mode.assert_awaited_once_with(4)
        coordinator.async_refresh_web_supplement.assert_awaited_once()

    async def test_set_dhw_setpoint_uses_the_pooled_client_and_reads_back(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.save_dhw_setpoint = AsyncMock()
        coordinator = self._coordinator_with_pool(mock_hass, mock_config_entry, client)

        await coordinator.async_web_set_dhw_setpoint(49.0)

        client.save_dhw_setpoint.assert_awaited_once_with(49.0)
        coordinator.async_refresh_web_supplement.assert_awaited_once()

    async def test_acknowledge_uses_the_pooled_client_and_reads_back(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.acknowledge_all_notifications = AsyncMock()
        coordinator = self._coordinator_with_pool(mock_hass, mock_config_entry, client)

        await coordinator.async_web_acknowledge_notifications()

        client.acknowledge_all_notifications.assert_awaited_once()
        coordinator.async_refresh_web_supplement.assert_awaited_once()

    async def test_missing_web_session_raises_a_home_assistant_error(self, mock_hass, mock_config_entry):
        from homeassistant.exceptions import HomeAssistantError

        coordinator, _ = _make_coordinator(mock_hass, mock_config_entry)
        pool = MagicMock()
        pool.get.return_value = None
        coordinator._web_client_pool = pool

        try:
            await coordinator.async_web_set_system_mode(1)
        except HomeAssistantError:
            pass
        else:
            raise AssertionError("a missing web session must raise HomeAssistantError")


class TestWebRegisterBridge:
    """Web-only snapshots feed register-keyed consumers (web register bridge)."""

    def _web_only_coordinator(self, mock_hass, mock_config_entry, supplement):
        coordinator, _ = _make_coordinator(mock_hass, mock_config_entry)
        # web-only operation: no scheduler-driven Modbus polling
        coordinator.update_interval = None
        coordinator._web_supplement = supplement
        coordinator._web_metadata_data = MagicMock(return_value={})
        return coordinator

    def test_bridges_web_values_under_register_names(self, mock_hass, mock_config_entry):
        supplement = SimpleNamespace(
            sensor_values={
                "flow_temperature": SimpleNamespace(native_value=35.1),
                "return_temperature": SimpleNamespace(native_value=30.2),
                "outside_air_temperature": SimpleNamespace(native_value=12.0),
                "water_temp_top": SimpleNamespace(native_value=52.0),
                "compressor_1": SimpleNamespace(native_value=1),
                "flow_temp_HK_A": SimpleNamespace(native_value=33.0),
                "room_temperature_HK_D": SimpleNamespace(native_value=21.4),
                "hotgas_temperature": SimpleNamespace(native_value="31.0C"),
            },
            heating_circuits=(),
            dhw_setpoint=None,
        )
        coordinator = self._web_only_coordinator(mock_hass, mock_config_entry, supplement)

        bridged = coordinator._web_register_bridge_data()

        assert bridged["hp_flow_temp"] == 35.1
        assert bridged["hp_return_temp"] == 30.2
        assert bridged["outdoor_temp"] == 12.0
        assert bridged["dhw_temp_top"] == 52.0
        assert bridged["compressor_status_1"] == 1
        assert bridged["hc_a_flow_temp"] == 33.0
        assert bridged["hc_d_room_temp"] == 21.4
        # Values without a register alias stay out; non-numeric values too.
        assert "hotgas_temperature" not in bridged

    def test_bridges_flow_setpoints_and_dhw_setpoint(self, mock_hass, mock_config_entry):
        supplement = SimpleNamespace(
            sensor_values={},
            heating_circuits=(
                SimpleNamespace(hc_id="A", flow_setpoint=28.5),
                SimpleNamespace(hc_id="D", flow_setpoint=None),
            ),
            dhw_setpoint=SimpleNamespace(value=48),
        )
        coordinator = self._web_only_coordinator(mock_hass, mock_config_entry, supplement)

        bridged = coordinator._web_register_bridge_data()

        assert bridged["hc_a_setpoint_flow_temp"] == 28.5
        assert bridged["dhw_setpoint"] == 48
        assert "hc_d_setpoint_flow_temp" not in bridged

    async def test_web_refresh_replaces_snapshot_in_web_only(self, mock_hass, mock_config_entry):
        from custom_components.idm_heatpump.web_data import IdmWebSensorValue, IdmWebSupplement

        supplement = IdmWebSupplement(
            web_variant="nav10",
            navigator_version="Navigator 10",
            sensor_values={"flow_temperature": IdmWebSensorValue("35.0", 35.0)},
        )
        coordinator, _ = _make_coordinator(mock_hass, mock_config_entry)
        coordinator.update_interval = None
        coordinator._web_pin = "1234"
        coordinator._web_host = "192.0.2.10"
        coordinator._web_client_pool = MagicMock()
        coordinator._web_client_pool.get.return_value = None
        coordinator._web_variant = "nav10"

        async def fake_read(*args, **kwargs):
            return supplement

        import custom_components.idm_heatpump.coordinator as coord_module

        original = coord_module.async_read_web_supplement
        coord_module.async_read_web_supplement = fake_read
        try:
            coordinator.data = {"stale_register": 1.0}
            await coordinator.async_refresh_web_supplement()
        finally:
            coord_module.async_read_web_supplement = original

        # Stale values are gone; the bridge supplies register-named data plus
        # the web metadata block.
        assert coordinator.data["hp_flow_temp"] == 35.0
        assert "stale_register" not in coordinator.data


class TestRegisterNamedWebWrites:
    """async_write_register routes register-named writes to the web path."""

    def _web_only(self, mock_hass, mock_config_entry, supplement):
        coordinator, _ = _make_coordinator(mock_hass, mock_config_entry)
        coordinator.update_interval = None
        coordinator._web_supplement = supplement
        coordinator._web_write_client = MagicMock()
        coordinator.async_refresh_web_supplement = AsyncMock()
        return coordinator

    def _supplement(self):
        from custom_components.idm_heatpump.web_data import IdmWebSupplement

        return IdmWebSupplement(
            web_variant="nav10",
            heating_circuits=(
                SimpleNamespace(
                    hc_id="A",
                    mode_parameter_id="HKA01",
                    setpoint_normal=SimpleNamespace(parameter_id="HKA04", value=21.5, min_value=15, max_value=30),
                ),
            ),
            dhw_setpoint=SimpleNamespace(value=48),
        )

    async def test_system_mode_write_routes_to_the_web_client(self, mock_hass, mock_config_entry):
        supplement = self._supplement()
        coordinator = self._web_only(mock_hass, mock_config_entry, supplement)
        client = coordinator._web_write_client.return_value
        client.set_system_mode = AsyncMock()

        from idm_heatpump import DataType, RegisterDef

        reg = RegisterDef(address=1005, datatype=DataType.UCHAR, name="system_mode", writable=True)
        result = await coordinator.async_write_register(reg, 4)

        assert result == 4
        client.set_system_mode.assert_awaited_once_with(4)

    async def test_dhw_setpoint_write_routes_to_the_web_client(self, mock_hass, mock_config_entry):
        supplement = self._supplement()
        coordinator = self._web_only(mock_hass, mock_config_entry, supplement)
        client = coordinator._web_write_client.return_value
        client.save_dhw_setpoint = AsyncMock()

        from idm_heatpump import DataType, RegisterDef

        reg = RegisterDef(address=1018, datatype=DataType.FLOAT, name="dhw_setpoint", writable=True)
        await coordinator.async_write_register(reg, 49.0)

        client.save_dhw_setpoint.assert_awaited_once_with(49.0)

    async def test_circuit_mode_and_setpoint_route_with_validation(self, mock_hass, mock_config_entry):
        supplement = self._supplement()
        coordinator = self._web_only(mock_hass, mock_config_entry, supplement)
        client = coordinator._web_write_client.return_value
        client.save_heatingcircuit_parameter = AsyncMock()

        from idm_heatpump import DataType, RegisterDef

        mode = RegisterDef(address=1393, datatype=DataType.UCHAR, name="hc_a_mode", writable=True)
        await coordinator.async_write_register(mode, 3)
        setpoint = RegisterDef(
            address=1379, datatype=DataType.FLOAT, name="hc_a_room_setpoint_heat_normal", writable=True
        )
        await coordinator.async_write_register(setpoint, 22.0)

        assert client.save_heatingcircuit_parameter.await_args_list[0].args == ("HKA01", 3.0)
        second = client.save_heatingcircuit_parameter.await_args_list[1]
        assert second.args == ("HKA04", 22.0)
        assert second.kwargs == {"min_value": 15, "max_value": 30}

    async def test_acknowledge_routes_to_the_web_client(self, mock_hass, mock_config_entry):
        supplement = self._supplement()
        coordinator = self._web_only(mock_hass, mock_config_entry, supplement)
        client = coordinator._web_write_client.return_value
        client.acknowledge_all_notifications = AsyncMock()

        from idm_heatpump import DataType, RegisterDef

        reg = RegisterDef(address=1999, datatype=DataType.UCHAR, name="error_acknowledge", writable=True)
        await coordinator.async_write_register(reg, 1)

        client.acknowledge_all_notifications.assert_awaited_once()

    async def test_unmapped_register_falls_through_to_modbus(self, mock_hass, mock_config_entry):
        supplement = self._supplement()
        coordinator = self._web_only(mock_hass, mock_config_entry, supplement)
        coordinator._web_write_client = MagicMock()

        from idm_heatpump import DataType, RegisterDef

        reg = RegisterDef(address=4108, datatype=DataType.FLOAT, name="power_limit_hp", writable=True)
        # The Modbus path runs (its write fails in the stub client) - the
        # important part is that no web write happened.
        # The stub client accepts the Modbus write; what matters is that no
        # web write was attempted for an unmapped register.
        await coordinator.async_write_register(reg, 5.0)
        client = coordinator._web_write_client.return_value
        client.set_system_mode.assert_not_called()
        client.save_dhw_setpoint.assert_not_called()
        client.acknowledge_all_notifications.assert_not_called()


class TestConnectionStateLogging:
    """One INFO line per transport transition - the support log must answer
    'since when does the web path not answer' without spamming."""

    def _web_coordinator(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            web_pin="1234",
            web_host="192.0.2.10",
        )
        coord.update_interval = None  # web-only entry shape
        return coord

    def test_initial_state_is_logged_once(self, mock_hass, mock_config_entry, caplog):
        import logging as _logging

        coordinator = self._web_coordinator(mock_hass, mock_config_entry)
        with caplog.at_level(_logging.INFO, logger="custom_components.idm_heatpump.coordinator"):
            coordinator._log_connection_state_change()
            coordinator._log_connection_state_change()

        lines = [r.message for r in caplog.records if "connection state" in r.message]
        assert lines == ["IDM connection state: Web only"]

    def test_web_down_and_recovery_is_logged_as_transition(self, mock_hass, mock_config_entry, caplog):
        import logging as _logging

        coordinator, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            web_pin="1234",
            web_host="192.0.2.10",
        )
        # modbus entry (update_interval set) with the web path up
        coordinator._web_alive = True
        coordinator._log_connection_state_change()  # initial: Modbus + Web
        with caplog.at_level(_logging.INFO, logger="custom_components.idm_heatpump.coordinator"):
            coordinator._web_alive = False
            coordinator._log_connection_state_change()
            coordinator._web_alive = True
            coordinator._log_connection_state_change()

        lines = [r.message for r in caplog.records if "connection state" in r.message]
        assert lines == [
            "IDM connection state changed: Modbus + Web -> Modbus only",
            "IDM connection state changed: Modbus only -> Modbus + Web",
        ]


class TestGetRegisterFallback:
    """The name index only carries entity-backed registers; action registers
    (write-only, no entity) must still resolve through the model's own map."""

    def _nav10_coordinator(self, mock_hass, mock_config_entry):
        coord, _registers = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_info=IdmModelInfo(
                model_name=MODEL_NAVIGATOR_10,
                active_heating_circuits=["A", "D"],
                zone_modules=0,
                has_solar=False,
                has_isc=False,
                has_pv=False,
                has_cascade=False,
            ),
        )
        # entity descriptions never contained the write-only acknowledge register
        coord._register_by_name.pop("error_acknowledge", None)
        return coord

    def test_write_only_register_resolves_via_the_model_map(self, mock_hass, mock_config_entry):
        coordinator = self._nav10_coordinator(mock_hass, mock_config_entry)

        register = coordinator.get_register("error_acknowledge")

        assert register is not None
        assert register.address == 1999
        assert register.writable is True

    def test_resolved_register_is_cached_in_the_index(self, mock_hass, mock_config_entry):
        coordinator = self._nav10_coordinator(mock_hass, mock_config_entry)

        first = coordinator.get_register("error_acknowledge")
        coordinator._register_by_name["error_acknowledge"] = first
        second = coordinator.get_register("error_acknowledge")

        assert second is first

    def test_unknown_model_stays_strict(self, mock_hass, mock_config_entry):
        coordinator, _ = _make_coordinator(mock_hass, mock_config_entry)
        coordinator._model_info = None
        coordinator._register_by_name.pop("error_acknowledge", None)

        assert coordinator.get_register("error_acknowledge") is None

    def test_navigator_17_shadows_the_acknowledge_coil(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_info=IdmModelInfo(
                model_name=MODEL_NAVIGATOR_17,
                active_heating_circuits=["A"],
                zone_modules=0,
                has_solar=False,
                has_isc=False,
                has_pv=False,
                has_cascade=False,
            ),
        )
        coord._register_by_name.pop("error_acknowledge", None)

        register = coord.get_register("error_acknowledge")

        assert register is not None
        assert register.address == 3000


class TestNavigatorFamilySeparatorCollapsing:
    """Mixed human/slug model names must normalize before family detection."""

    def test_repeated_separators_collapse_to_one(self):
        # "Navigator--10" normalizes to "navigator__10" before collapsing.
        assert navigator_family("Navigator--10") == "navigator_10"
        assert navigator_family("IDM Navigator__Pro") == "navigator_pro"
        assert navigator_family("navigator  2.0") == "navigator_20"

    def test_collapsing_does_not_invent_a_family(self):
        assert navigator_family("Some--Unknown") is None


class TestExternalRegisterDemand:
    """Non-entity consumers declare the registers they need polled."""

    def test_demand_round_trip_notifies_the_polling_plan(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.externally_required_registers == frozenset()

        manager = MagicMock()
        coord.attach_entity_aware_polling_manager(manager)
        assert coord.entity_aware_polling_manager is manager

        release = coord.register_required_registers("knx_bridge", frozenset({"hp_flow_temp"}))
        assert coord.externally_required_registers == frozenset({"hp_flow_temp"})
        manager.schedule_replan.assert_called_once()

        release()
        assert coord.externally_required_registers == frozenset()
        assert manager.schedule_replan.call_count == 2

    def test_releasing_an_already_released_owner_stays_silent(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        manager = MagicMock()
        coord.attach_entity_aware_polling_manager(manager)
        release = coord.register_required_registers("knx_bridge", frozenset({"hp_flow_temp"}))
        manager.schedule_replan.reset_mock()

        release()
        release()  # the owner is gone; the second release must not re-plan

        assert manager.schedule_replan.call_count == 1


class TestCoordinatorDiagnosticSurfaces:
    """The surfaces diagnostics and sensors read stay consistent with the poll."""

    async def test_poll_statistics_reflect_one_successful_poll(self, mock_hass, mock_config_entry):
        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 20.0})
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[reg],
            polling_jitter_percent=7,
            write_cooldown_seconds=12.0,
        )
        coord.set_active_registers([reg], total=1)

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()

        stats = coord.poll_statistics
        assert stats.total_polls == 1
        assert stats.total_failures == 0
        assert stats.consecutive_failures == 0
        assert stats.last_success is not None
        assert stats.last_duration is not None
        assert stats.planned_registers == 1
        assert stats.known_registers == 1
        assert stats.jitter_percent == 7
        assert stats.write_cooldown_seconds == 12.0

    def test_alias_map_and_hierarchy_ids_are_exposed(self, mock_hass, mock_config_entry):
        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, registers=[reg])
        assert coord.alias_map == {}
        coord._alias_map = {1000: ["temp", "temp_set"]}
        assert coord.alias_map == {1000: ["temp", "temp_set"]}

        assert coord.hierarchy_device_ids == {}
        coord.set_hierarchy_device_ids({("idm_heatpump", "test_entry_id"): "registry-device-1"})
        assert coord.hierarchy_device_ids == {("idm_heatpump", "test_entry_id"): "registry-device-1"}

    def test_dhw_boost_manager_attach_and_read(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.dhw_boost_manager is None
        manager = MagicMock()
        coord.attach_dhw_boost_manager(manager)
        assert coord.dhw_boost_manager is manager

    def test_web_accessors_before_any_web_poll(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            web_pin="1234",
            web_host="192.0.2.9",
        )
        assert coord.web_enabled is True
        assert coord.web_host == "192.0.2.9"
        assert coord.web_alive is None
        assert coord.web_last_success is None

        without_pin, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert without_pin.web_enabled is False

    def test_web_value_accessors_without_a_supplement(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.web_value_keys == ()
        assert coord.missing_web_core_values == ()
        assert coord._web_register_bridge_data() == {}


class TestModelConflictSummaryFallbacks:
    """The summary stays usable when the config entry data is unusable."""

    def test_non_dict_entry_data_is_treated_as_empty(self, mock_hass, mock_config_entry):
        mock_config_entry.data = None
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, model_name="Navigator 10")

        summary = coord.model_conflict_summary

        assert summary["selected_family"] == "navigator_10"
        assert summary["stored_family"] is None
        assert summary["manual_override"] is None
        assert summary["conflict"] is False

    def test_navigator_17_family_implies_no_web_variant(self, mock_hass, mock_config_entry):
        """The 1.x family has no local web access, so no variant is expected."""
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, model_name="Navigator 1.7")

        summary = coord.model_conflict_summary

        assert summary["selected_family"] == "navigator_17"
        assert summary["expected_web_variant"] is None
        assert summary["web_variant_conflict"] is False


class TestAnalysisAndStatisticsHooks:
    """Attached analyses receive each successful snapshot and never break the poll."""

    def _polling_coordinator(self, mock_hass, mock_config_entry):
        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 20.0})
        return _make_coordinator(mock_hass, mock_config_entry, client=client, registers=[reg])

    async def test_poll_feeds_the_attached_operation_analysis(self, mock_hass, mock_config_entry):
        coord, _ = self._polling_coordinator(mock_hass, mock_config_entry)
        analysis = SimpleNamespace(process_snapshot=MagicMock())
        coord.attach_operation_analysis(analysis)
        assert coord.operation_analysis is analysis

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            data = await coord._async_update_data()

        analysis.process_snapshot.assert_called_once_with(data, coord.unused_registers)

    async def test_operation_analysis_failure_does_not_break_the_poll(self, mock_hass, mock_config_entry, caplog):
        coord, _ = self._polling_coordinator(mock_hass, mock_config_entry)
        analysis = SimpleNamespace(process_snapshot=MagicMock(side_effect=RuntimeError("analysis bug")))
        coord.attach_operation_analysis(analysis)

        with (
            patch("custom_components.idm_heatpump.coordinator.ir"),
            caplog.at_level(logging.WARNING, logger="custom_components.idm_heatpump.coordinator"),
        ):
            data = await coord._async_update_data()

        assert data["temp"] == 20.0
        assert any("Could not update IDM operation analysis" in record.getMessage() for record in caplog.records)

    async def test_poll_feeds_the_attached_energy_statistics(self, mock_hass, mock_config_entry):
        coord, _ = self._polling_coordinator(mock_hass, mock_config_entry)
        statistics = SimpleNamespace(
            required_registers=frozenset({"power_consumption_hp"}),
            process_snapshot=MagicMock(),
        )
        coord.attach_energy_statistics(statistics)
        assert coord.energy_statistics is statistics

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            data = await coord._async_update_data()

        statistics.process_snapshot.assert_called_once_with(data)

    async def test_energy_statistics_failure_does_not_break_the_poll(self, mock_hass, mock_config_entry, caplog):
        coord, _ = self._polling_coordinator(mock_hass, mock_config_entry)
        statistics = SimpleNamespace(
            required_registers=frozenset({"power_consumption_hp"}),
            process_snapshot=MagicMock(side_effect=RuntimeError("statistics bug")),
        )
        coord.attach_energy_statistics(statistics)

        with (
            patch("custom_components.idm_heatpump.coordinator.ir"),
            caplog.at_level(logging.WARNING, logger="custom_components.idm_heatpump.coordinator"),
        ):
            data = await coord._async_update_data()

        assert data["temp"] == 20.0
        assert any("Could not update IDM energy statistics" in record.getMessage() for record in caplog.records)


class TestRoomModeValidationScheduling:
    """Individual room-mode validation is throttled and fails loudly."""

    def _room_mode_coordinator(self, mock_hass, mock_config_entry, read_register):
        room_mode = RegisterDef(address=2025, datatype=DataType.UCHAR, name="zm1_room3_mode")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={room_mode.name: 3})
        client.read_register = read_register
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            client=client,
            registers=[room_mode],
        )
        return coord, room_mode

    async def test_validation_runs_on_the_first_poll_then_skips_most(self, mock_hass, mock_config_entry):
        client_read = AsyncMock(return_value=3)
        coord, room_mode = self._room_mode_coordinator(mock_hass, mock_config_entry, client_read)

        data = {room_mode.name: 3}
        await coord._async_refresh_zone_room_modes(data)
        assert client_read.await_count == 1

        # The second call is inside the validation interval: no individual read.
        await coord._async_refresh_zone_room_modes(data)
        assert client_read.await_count == 1

    async def test_cancellation_during_individual_read_propagates(self, mock_hass, mock_config_entry):
        import asyncio

        coord, room_mode = self._room_mode_coordinator(
            mock_hass,
            mock_config_entry,
            AsyncMock(side_effect=asyncio.CancelledError()),
        )

        with pytest.raises(asyncio.CancelledError):
            await coord._async_refresh_zone_room_modes({room_mode.name: 3})

    async def test_transport_error_during_individual_read_propagates(self, mock_hass, mock_config_entry):
        coord, room_mode = self._room_mode_coordinator(
            mock_hass,
            mock_config_entry,
            AsyncMock(side_effect=OSError("connection reset")),
        )

        with pytest.raises(OSError, match="connection reset"):
            await coord._async_refresh_zone_room_modes({room_mode.name: 3})


class TestResilientReadGuards:
    async def test_fully_unsupported_register_set_short_circuits_the_read(self, mock_hass, mock_config_entry):
        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp")
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 1.0})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, registers=[reg])
        coord._unsupported_registers = {"temp"}

        assert await coord._async_read_registers_resilient([reg]) == {}
        client.read_batch.assert_not_awaited()


class TestSolarSuggestionTiming:
    """The unused-solar suggestion waits for its window and never duplicates itself."""

    def _solar_coordinator(self, mock_hass, mock_config_entry, window):
        registers = [
            RegisterDef(address=1850, datatype=DataType.FLOAT, name="solar_collector_temp"),
            RegisterDef(address=1851, datatype=DataType.FLOAT, name="solar_charging_temp"),
        ]
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            registers=registers,
            unused_module_suggestion_seconds=window,
        )
        coord._unused_registers = {"solar_collector_temp", "solar_charging_temp"}
        return coord

    def test_no_suggestion_before_the_window_elapses(self, mock_hass, mock_config_entry):
        import time

        coord = self._solar_coordinator(mock_hass, mock_config_entry, window=3600.0)
        coord._solar_unused_since = time.monotonic() - 60.0

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            mock_ir.async_get.return_value.async_get_issue.return_value = None
            coord._evaluate_unused_solar_suggestion()

        mock_ir.async_create_issue.assert_not_called()

    def test_existing_issue_is_not_recreated(self, mock_hass, mock_config_entry):
        import time

        coord = self._solar_coordinator(mock_hass, mock_config_entry, window=0.0)
        coord._solar_unused_since = time.monotonic() - 60.0

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            mock_ir.async_get.return_value.async_get_issue.return_value = object()
            coord._evaluate_unused_solar_suggestion()

        mock_ir.async_create_issue.assert_not_called()


class TestScanIntervalGuardEdges:
    def test_zero_interval_disables_the_evaluation(self, mock_hass, mock_config_entry):
        """A zero interval has no idle time to protect; the metric is meaningless."""
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        coord.update_interval = timedelta(0)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            coord._evaluate_poll_duration(0.0)
            coord._evaluate_poll_duration(9.9)

        mock_ir.async_create_issue.assert_not_called()
        assert coord._slow_poll_streak == 0
        assert coord._fast_poll_streak == 0


class TestWebRefreshGuards:
    async def test_refresh_without_a_web_pin_is_a_noop(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        coord._refresh_web_supplement_inner = AsyncMock()

        await coord.async_refresh_web_supplement()

        coord._refresh_web_supplement_inner.assert_not_awaited()

    async def test_none_supplement_marks_the_web_path_dead(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            web_pin="1234",
            web_host="192.0.2.10",
        )

        with (
            patch("custom_components.idm_heatpump.coordinator.async_read_web_supplement", return_value=None),
            patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir,
        ):
            await coord.async_refresh_web_supplement()

        assert coord.last_web_error == "No web supplement data returned"
        assert coord.web_alive is False
        assert coord.web_supplement is None
        mock_ir.async_create_issue.assert_not_called()

    async def test_authentication_failure_blocks_further_web_polling(self, mock_hass, mock_config_entry):
        """A refused PIN must stop web polling so the controller never locks out."""
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            web_pin="1234",
            web_host="192.0.2.10",
        )

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.async_read_web_supplement",
                side_effect=IdmWebAuthenticationFailed("PIN rejected"),
            ),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.web_auth_blocked is True


class TestWebDifferentialCircuitsReport:
    def test_a_change_is_published_with_a_reload_hint(self, mock_hass, mock_config_entry, caplog):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.web_differential_circuits == frozenset()

        with caplog.at_level(logging.INFO, logger="custom_components.idm_heatpump.coordinator"):
            coord.set_web_differential_circuits(frozenset({"hk2"}))

        assert coord.web_differential_circuits == frozenset({"hk2"})
        assert any(
            "differential heating circuits" in record.getMessage() and "HK2" in record.getMessage()
            for record in caplog.records
        )

        # An unchanged detection stays quiet.
        caplog.clear()
        coord.set_web_differential_circuits(frozenset({"hk2"}))
        assert not caplog.records


class TestWebCounterGuardProgress:
    def test_positive_progress_on_a_web_lifetime_counter_passes(self, mock_hass, mock_config_entry):
        """A counter moving forward is normal progress, never a transient zero."""
        coordinator, _ = _make_coordinator(mock_hass, mock_config_entry)
        coordinator._web_supplement = IdmWebSupplement(
            sensor_values={"heat_quantity_heating_total": IdmWebSensorValue("500.0", 500.0, "kWh")}
        )
        incoming = IdmWebSupplement(
            sensor_values={"heat_quantity_heating_total": IdmWebSensorValue("501.5", 501.5, "kWh")}
        )

        guarded = coordinator._suppress_transient_web_counter_zeros(incoming)

        assert guarded is incoming
        assert coordinator.transient_zero_suppressed == 0


class TestWebRegisterBridgeGuards:
    def test_non_numeric_value_on_a_mapped_name_is_not_bridged(self, mock_hass, mock_config_entry):
        supplement = SimpleNamespace(
            sensor_values={
                "flow_temperature": SimpleNamespace(native_value="35.0C"),
                "outside_air_temperature": SimpleNamespace(native_value=12.0),
            },
            heating_circuits=(),
            dhw_setpoint=None,
        )
        coordinator, _ = _make_coordinator(mock_hass, mock_config_entry)
        coordinator._web_supplement = supplement

        bridged = coordinator._web_register_bridge_data()

        assert "hp_flow_temp" not in bridged
        assert bridged["outdoor_temp"] == 12.0


class TestGetRegisterEdgeCases:
    def test_unknown_name_on_a_known_model_stays_none(self, mock_hass, mock_config_entry):
        """The model map is authoritative, but it cannot invent registers."""
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_info=IdmModelInfo(
                model_name=MODEL_NAVIGATOR_10,
                active_heating_circuits=["A"],
                zone_modules=0,
                has_solar=False,
                has_isc=False,
                has_pv=False,
                has_cascade=False,
            ),
        )

        assert coord.get_register("totally_unknown_register") is None
        assert "totally_unknown_register" not in coord._register_by_name


class TestModelInfoFallbackMutation:
    """dataclasses.replace only works on dataclasses; a foreign model_info
    object falls back to an in-place mutation instead of failing the poll."""

    async def test_non_dataclass_model_info_is_mutated_on_model_agreement(self, mock_hass, mock_config_entry):
        coord, client = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 2.0 / 10",
            model_info=SimpleNamespace(model_name="Unknown Controller"),
            web_pin="1234",
        )
        client.set_model_info.reset_mock()
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(navigator_version="Navigator 10")

        with (
            patch("custom_components.idm_heatpump.coordinator.async_read_web_supplement", return_value=supplement),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.model_name == "Navigator 10"
        assert coord.model_info is not None
        assert coord.model_info.model_name == "Navigator 10"
        client.set_model_info.assert_called_once_with(coord.model_info)

    async def test_non_dataclass_model_info_is_mutated_on_nav10_correction(self, mock_hass, mock_config_entry):
        coord, client = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 2.0",
            model_info=SimpleNamespace(model_name="Navigator 2.0"),
            web_pin="1234",
        )
        client.set_model_info.reset_mock()
        coord.data = {}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(navigator_version="Navigator 10", software_version="NAV10_20.24")

        with (
            patch("custom_components.idm_heatpump.coordinator.async_read_web_supplement", return_value=supplement),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.model_name == "Navigator 10"
        assert coord.model_info is not None
        assert coord.model_info.model_name == "Navigator 10"
        assert coord.firmware_version == "NAV10_20.24"
        client.set_model_info.assert_called_once_with(coord.model_info)


class TestPersistWebDetectionGuards:
    def test_missing_config_entry_skips_persistence(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        coord.config_entry = None

        coord._persist_web_detection(IdmWebSupplement(navigator_version="Navigator 10"), False)

        mock_hass.config_entries.async_update_entry.assert_not_called()

    def test_non_dict_entry_data_skips_persistence(self, mock_hass, mock_config_entry):
        mock_config_entry.data = None
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)

        coord._persist_web_detection(IdmWebSupplement(navigator_version="Navigator 10"), False)

        mock_hass.config_entries.async_update_entry.assert_not_called()

    def test_a_failing_entry_update_is_logged_and_swallowed(self, mock_hass, mock_config_entry, caplog):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        mock_hass.config_entries.async_update_entry = MagicMock(side_effect=RuntimeError("store closed"))

        with caplog.at_level(logging.DEBUG, logger="custom_components.idm_heatpump.coordinator"):
            coord._persist_web_detection(IdmWebSupplement(navigator_version="Navigator 10"), False)

        assert any(
            "Failed to persist retroactive IDM web detection" in record.getMessage() for record in caplog.records
        )


class TestWriteValidationSurfaces:
    async def test_locally_refused_write_is_reported_as_blocked_before_sending(
        self, mock_hass, mock_config_entry, caplog
    ):
        client = MagicMock()
        client.write_register = AsyncMock()
        client.simulate_write = MagicMock(side_effect=ValueError("Value 900 is out of range"))
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        reg = RegisterDef(address=1405, datatype=DataType.FLOAT, name="hc_c_room_setpoint_heat_normal", writable=True)
        with (
            caplog.at_level(logging.WARNING, logger="custom_components.idm_heatpump.coordinator"),
            pytest.raises(ValueError, match="out of range"),
        ):
            await coord.async_write_register(reg, 900.0)

        assert any("blocked before it was sent" in record.getMessage() for record in caplog.records)
        client.write_register.assert_not_awaited()
        assert coord.last_write_error is not None
        assert coord.last_write_error["translation_key"] == "write_out_of_range"
        assert coord.last_write_error["reached_device"] is False

    def test_simulate_write_delegates_with_custom_registers(self, mock_hass, mock_config_entry):
        client = MagicMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        reg = RegisterDef(address=5000, datatype=DataType.FLOAT, name="custom_reg", writable=True)

        coord.simulate_write(reg, 7.5, dry_run=False, allow_custom_register=True)

        client.simulate_write.assert_called_once_with(reg, 7.5, dry_run=False, allow_custom_register=True)

    async def test_modbus_write_can_target_a_custom_register(self, mock_hass, mock_config_entry):
        import asyncio

        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        reg = RegisterDef(address=5000, datatype=DataType.FLOAT, name="custom_reg", writable=True)

        await coord.async_write_register(reg, 7.5, allow_custom_register=True)

        client.write_register.assert_awaited_once_with(reg, 7.5, allow_custom_register=True)
        # End the confirmation task deterministically instead of sleeping 0.5 s.
        task = coord._delayed_refresh_task
        assert task is not None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestWebWriteHelpers:
    async def test_heating_circuit_parameter_write_uses_the_pooled_client(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.save_heatingcircuit_parameter = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        pool = MagicMock()
        pool.get.return_value = (client, "nav10")
        coord._web_client_pool = pool
        coord.async_refresh_web_supplement = AsyncMock()

        await coord.async_web_set_heatingcircuit_parameter("HKA04", 21.5, min_value=15.0, max_value=30.0)

        client.save_heatingcircuit_parameter.assert_awaited_once_with("HKA04", 21.5, min_value=15.0, max_value=30.0)
        coord.async_refresh_web_supplement.assert_awaited_once()

    def test_register_named_write_without_a_supplement_is_unhandled(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)

        assert coord._web_write_register_by_name("system_mode", 1) is False
        assert coord._pending_web_writes == []

    def test_circuit_mode_write_without_a_mode_parameter_is_unhandled(self, mock_hass, mock_config_entry):
        supplement = IdmWebSupplement(
            heating_circuits=(SimpleNamespace(hc_id="A", mode_parameter_id=None, setpoint_normal=None),)
        )
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_supplement=supplement)

        assert coord._web_write_register_by_name("hc_a_mode", 3) is False
        assert coord._pending_web_writes == []

    def test_circuit_setpoint_write_without_a_parameter_is_unhandled(self, mock_hass, mock_config_entry):
        supplement = IdmWebSupplement(
            heating_circuits=(SimpleNamespace(hc_id="A", mode_parameter_id="HKA01", setpoint_normal=None),)
        )
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, web_supplement=supplement)

        assert coord._web_write_register_by_name("hc_a_room_setpoint_heat_normal", 21.0) is False
        assert coord._pending_web_writes == []

    async def test_flush_without_pending_writes_touches_no_client(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        coord._web_write_client = MagicMock()

        await coord._async_flush_web_writes()

        coord._web_write_client.assert_not_called()


class TestConfirmationTaskCreation:
    async def test_the_entry_background_task_hook_is_used_when_available(self, mock_hass, mock_config_entry):
        """A real ConfigEntry offers async_create_background_task; the entry owns the task."""
        import asyncio

        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        created: dict[str, str] = {}

        class _EntryWithBackgroundTasks:
            entry_id = "test_entry_id"

            @staticmethod
            def async_create_background_task(entry, hass, target, name):
                created["name"] = name
                return asyncio.create_task(target)

        coord.config_entry = _EntryWithBackgroundTasks()
        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="mode", writable=True)

        await coord.async_write_register(reg, 1)

        assert created["name"] == "idm_heatpump_write_confirmation_test_entry_id"
        task = coord._delayed_refresh_task
        assert task is not None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestMainDeviceRegistrySync:
    def test_firmware_and_model_are_pushed_to_the_registered_device(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            model_name="Navigator 10",
            firmware_version="NAV10_20.24",
        )
        coord.set_hierarchy_device_ids({("idm_heatpump", "test_entry_id"): "registry-device-1"})

        with patch("custom_components.idm_heatpump.coordinator.dr") as mock_dr:
            coord._sync_main_device_registry()

        mock_dr.async_get.return_value.async_update_device.assert_called_once_with(
            "registry-device-1", model="Navigator 10", sw_version="NAV10_20.24"
        )

    def test_sync_without_a_config_entry_is_a_noop(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        coord.config_entry = None

        with patch("custom_components.idm_heatpump.coordinator.dr") as mock_dr:
            coord._sync_main_device_registry()  # must not raise

        mock_dr.async_get.assert_not_called()


class TestDeviceInfo:
    def test_device_info_reflects_metadata_and_is_cached(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            firmware_version="NAV10_20.24",
            web_supplement=IdmWebSupplement(myidm_id="MYIDM42"),
        )

        info = coord.device_info()

        assert info["identifiers"] == {("idm_heatpump", "test_entry_id")}
        assert info["name"] == "IDM Test"
        assert info["model"] == "Navigator 2.0 / 10"
        assert info["sw_version"] == "NAV10_20.24"
        assert info["serial_number"] == "MYIDM42"

        # The cached object is returned unchanged until metadata changes.
        assert coord.device_info() is info
        coord._invalidate_device_info_cache()
        assert coord.device_info() is not info
        assert coord.device_info()["model"] == "Navigator 2.0 / 10"


class TestDeviceHierarchyFlag:
    def test_hierarchy_flag_defaults_off_and_can_be_enabled(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.device_hierarchy_enabled is False

        client = MagicMock()
        client.read_batch = AsyncMock(return_value={})
        enabled = IdmCoordinator(
            hass=mock_hass,
            config_entry=mock_config_entry,
            client=client,
            scan_interval=timedelta(seconds=10),
            sensor_descriptions=[],
            binary_sensor_descriptions=[],
            number_descriptions=[],
            select_descriptions=[],
            switch_descriptions=[],
            device_hierarchy_enabled=True,
        )
        assert enabled.device_hierarchy_enabled is True


class TestSetupRegistersFromDescriptions:
    def test_entity_descriptions_drive_the_register_collection(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        desc_reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="desc_flow_temp")
        descriptions = [{"key": "desc_flow_temp"}]

        with (
            patch(
                "custom_components.idm_heatpump.coordinator.collect_registers_from_descriptions",
                return_value=[desc_reg],
            ) as mock_collect,
            patch(
                "custom_components.idm_heatpump.coordinator.collect_aliases_from_descriptions",
                return_value={1000: ["desc_flow_temp"]},
            ) as mock_aliases,
        ):
            coord.setup_registers(["a"], 0, {}, descriptions=descriptions)

        mock_collect.assert_called_once_with(descriptions)
        mock_aliases.assert_called_once_with(descriptions)
        assert coord.registers_count == 1
        assert coord._register_by_name["desc_flow_temp"] is desc_reg


class TestWebNotPresentFallback:
    """Web values fill registers whose Modbus reading is the not-present pattern (#516)."""

    def _coordinator_with_web(self, mock_hass, mock_config_entry, sensor_values, registers=()):
        from custom_components.idm_heatpump.web_data import IdmWebSupplement

        client = MagicMock()
        client.read_batch = AsyncMock(return_value={})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        # Auto mode: a live poll interval and the register map the fallback
        # consults for not-present sentinels.
        coord.update_interval = timedelta(seconds=10)
        coord._register_by_name = {reg.name: reg for reg in registers}
        coord._web_supplement = IdmWebSupplement(sensor_values=sensor_values)
        return coord

    def test_flowmeter_fills_the_no_twt_spurious_zero(self, mock_hass, mock_config_entry):
        """The reporter's case: Modbus 0.0 from the -1.0 pattern, web 33.9."""
        from custom_components.idm_heatpump.web_data import IdmWebSensorValue

        coord = self._coordinator_with_web(
            mock_hass,
            mock_config_entry,
            {"flowmeter": IdmWebSensorValue("33.9", 33.9, "l/min")},
            registers=(
                RegisterDef(address=1072, datatype=DataType.UCHAR, name="heat_sink_flow_rate"),
                RegisterDef(address=1070, datatype=DataType.FLOAT, name="heat_sink_flow_temp"),
            ),
        )
        data = {
            "heat_sink_flow_rate": 0.0,
            "heat_sink_flow_temp": -1.0,
        }
        result = coord._apply_web_not_present_fallback(data)
        assert result["heat_sink_flow_rate"] == 33.9

    def test_float_sentinel_flow_rate_filled_from_web(self, mock_hass, mock_config_entry):
        """After the 1072 FLOAT re-typing (#516) not-present plants decode -1.0.

        The FLOAT datatype default sentinel classifies the reading as not
        present directly, without the spurious-zero signature detour, so the
        web flowmeter still fills the register.
        """
        from custom_components.idm_heatpump.web_data import IdmWebSensorValue

        coord = self._coordinator_with_web(
            mock_hass,
            mock_config_entry,
            {"flowmeter": IdmWebSensorValue("33.9", 33.9, "l/min")},
            registers=(
                RegisterDef(address=1072, datatype=DataType.FLOAT, name="heat_sink_flow_rate"),
                RegisterDef(address=1070, datatype=DataType.FLOAT, name="heat_sink_flow_temp"),
            ),
        )
        data = {
            "heat_sink_flow_rate": -1.0,
            "heat_sink_flow_temp": -1.0,
        }
        result = coord._apply_web_not_present_fallback(data)
        assert result["heat_sink_flow_rate"] == 33.9

    def test_real_modbus_value_wins_over_web(self, mock_hass, mock_config_entry):
        from custom_components.idm_heatpump.web_data import IdmWebSensorValue

        coord = self._coordinator_with_web(
            mock_hass,
            mock_config_entry,
            {"flowmeter": IdmWebSensorValue("33.9", 33.9, "l/min")},
        )
        data = {"heat_sink_flow_rate": 12.4, "heat_sink_flow_temp": 22.5}
        result = coord._apply_web_not_present_fallback(data)
        assert result["heat_sink_flow_rate"] == 12.4

    def test_twt_idle_zero_is_not_replaced(self, mock_hass, mock_config_entry):
        """A real sensor's legitimate idle zero stays a Modbus measurement."""
        from custom_components.idm_heatpump.web_data import IdmWebSensorValue

        coord = self._coordinator_with_web(
            mock_hass,
            mock_config_entry,
            {"flowmeter": IdmWebSensorValue("33.9", 33.9, "l/min")},
        )
        data = {"heat_sink_flow_rate": 0.0, "heat_sink_flow_temp": 21.8}
        result = coord._apply_web_not_present_fallback(data)
        assert result["heat_sink_flow_rate"] == 0.0

    def test_sentinel_register_filled_from_web(self, mock_hass, mock_config_entry):
        from custom_components.idm_heatpump.web_data import IdmWebSensorValue

        coord = self._coordinator_with_web(
            mock_hass,
            mock_config_entry,
            {"outside_air_temperature": IdmWebSensorValue("7.5", 7.5, "°C")},
            registers=(RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp"),),
        )
        data = {"outdoor_temp": -1.0}
        result = coord._apply_web_not_present_fallback(data)
        assert result["outdoor_temp"] == 7.5

    def test_no_web_supplement_is_a_noop(self, mock_hass, mock_config_entry):
        client = MagicMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord._web_supplement = None
        data = {"heat_sink_flow_rate": 0.0}
        assert coord._apply_web_not_present_fallback(data) is data

    def test_web_fallback_registers_tracked_and_cleared_on_real_modbus_read(self, mock_hass, mock_config_entry):
        from custom_components.idm_heatpump.web_data import IdmWebSensorValue

        coord = self._coordinator_with_web(
            mock_hass,
            mock_config_entry,
            {"outside_air_temperature": IdmWebSensorValue("7.5", 7.5, "°C")},
            registers=(RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp"),),
        )
        data = {"outdoor_temp": -1.0}
        coord._apply_web_not_present_fallback(data)
        assert coord.web_fallback_registers == {"outdoor_temp"}

        # A subsequent Modbus poll with a real value clears the fallback mark.
        real = {"outdoor_temp": 8.2}
        coord._apply_web_not_present_fallback(real, from_modbus_poll=True)
        assert coord.web_fallback_registers == set()

    async def test_web_refresh_fills_not_present_sentinel_and_clears_unused_immediately(
        self, mock_hass, mock_config_entry
    ):
        from custom_components.idm_heatpump.web_data import IdmWebSensorValue

        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp")
        coord, _ = _make_coordinator(
            mock_hass,
            mock_config_entry,
            web_pin="1234",
            hide_unused=True,
            registers=[reg],
        )
        coord.update_interval = timedelta(seconds=10)
        coord.data = {"outdoor_temp": -1.0}
        coord._unused_registers = {"outdoor_temp"}
        coord.async_update_listeners = MagicMock()
        supplement = IdmWebSupplement(
            navigator_version="Navigator 10",
            sensor_values={"outside_air_temperature": IdmWebSensorValue("7.5", 7.5, "°C")},
        )

        with (
            patch("custom_components.idm_heatpump.coordinator.async_read_web_supplement", return_value=supplement),
            patch("custom_components.idm_heatpump.coordinator.ir"),
        ):
            await coord.async_refresh_web_supplement()

        assert coord.data["outdoor_temp"] == 7.5
        assert "outdoor_temp" not in coord.unused_registers
        assert "outdoor_temp" in coord.web_fallback_registers

    async def test_third_write_cancels_second_sleeping_confirmation_while_first_refreshes(
        self, mock_hass, mock_config_entry
    ):
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        reg1 = RegisterDef(address=1000, datatype=DataType.UCHAR, name="mode1", writable=True)
        reg2 = RegisterDef(address=1001, datatype=DataType.UCHAR, name="mode2", writable=True)
        reg3 = RegisterDef(address=1002, datatype=DataType.UCHAR, name="mode3", writable=True)

        refresh_started = asyncio.Event()
        refresh_release = asyncio.Event()

        async def _slow_refresh() -> None:
            refresh_started.set()
            await refresh_release.wait()

        coord.async_request_refresh = AsyncMock(side_effect=_slow_refresh)

        real_sleep = asyncio.sleep

        async def _fast_first_sleep(delay: float) -> None:
            if not refresh_started.is_set():
                await real_sleep(0)
            else:
                await real_sleep(10)

        with patch("custom_components.idm_heatpump.coordinator.asyncio.sleep", side_effect=_fast_first_sleep):
            await coord.async_write_register(reg1, 1)
            task1 = coord._delayed_refresh_task
            assert task1 is not None
            await asyncio.wait_for(refresh_started.wait(), 1.0)
            assert task1 in coord._refreshing_confirmation_tasks

            # Second write while task1 is refreshing: task1 is NOT cancelled, task2 starts sleeping.
            await coord.async_write_register(reg2, 2)
            task2 = coord._delayed_refresh_task
            assert task2 is not None and task2 is not task1
            await real_sleep(0)
            assert not task1.cancelled()
            assert not task2.done()

            # Third write while task1 is STILL refreshing and task2 is sleeping:
            # task2 MUST be cancelled in its sleep phase (catching CancelledError and exiting without refreshing)!
            await coord.async_write_register(reg3, 3)
            task3 = coord._delayed_refresh_task
            assert task3 is not None and task3 is not task2
            await real_sleep(0)
            assert task2.done()
            assert coord.async_request_refresh.await_count == 1
            assert not task1.cancelled()

            refresh_release.set()
            await task1
            await coord.async_shutdown()
            assert task3.done()
