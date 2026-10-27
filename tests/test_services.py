"""Tests for service handlers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.idm_heatpump.const import DOMAIN
from custom_components.idm_heatpump.services import (
    _encoded_registers_from_safety_result,
    _get_coordinator,
    _handle_acknowledge_errors,
    _handle_export_ai_dashboard,
    _handle_export_knx_group_addresses,
    _handle_generate_ai_report,
    _handle_set_controller_clock,
    _handle_set_external_climate,
    _handle_set_external_power,
    _handle_set_system_mode,
    _handle_snooze_anomaly,
    _handle_unsnooze_anomaly,
    _handle_write_register,
    async_setup_services,
)


def _make_coordinator_in_hass(mock_hass, entry_id: str = "entry-1"):
    from homeassistant.config_entries import ConfigEntryState

    from custom_components.idm_heatpump.coordinator import IdmCoordinator

    coord = MagicMock(spec=IdmCoordinator)
    coord.async_write_register = AsyncMock()
    coord.get_register = MagicMock(return_value=None)
    coord.client = MagicMock()
    coord.client.write_register = AsyncMock()

    entry = MagicMock()
    entry.state = ConfigEntryState.LOADED
    entry.entry_id = entry_id
    entry.runtime_data = MagicMock()
    entry.runtime_data.coordinator = coord
    coord.config_entry = entry

    mock_hass.config_entries.async_entries = MagicMock(return_value=[entry])
    return coord


class TestWriteSafetyHelpers:
    def test_extracts_tuple_encoded_registers_from_api_result(self):
        result = MagicMock()
        result.encoded_registers = (1, 2, 65535)

        assert _encoded_registers_from_safety_result(result) == [1, 2, 65535]

    def test_extracts_sequence_encoded_registers_from_mapping(self):
        assert _encoded_registers_from_safety_result({"encoded_registers": (42,)}) == [42]

    def test_ignores_text_encoded_registers(self):
        assert _encoded_registers_from_safety_result({"encoded_registers": "42"}) is None


class TestSetupServices:
    async def test_registers_services(self, mock_hass):
        await async_setup_services(mock_hass)
        # Core services, two DHW boost actions, the read-only AI action and
        # the two advisor-anomaly snooze actions.
        assert mock_hass.services.async_register.call_count == 13

    async def test_skips_if_already_registered(self, mock_hass):
        mock_hass.services.has_service = MagicMock(return_value=True)
        await async_setup_services(mock_hass)
        mock_hass.services.async_register.assert_not_called()


class TestServiceLifecycleInvariants:
    """Regression coverage for #171: domain services outlive entry unload/reload."""

    async def test_setup_registers_each_service_exactly_once(self, mock_hass):
        await async_setup_services(mock_hass)
        registered = {(c.args[0], c.args[1]) for c in mock_hass.services.async_register.call_args_list}
        assert registered == {
            (DOMAIN, "set_system_mode"),
            (DOMAIN, "acknowledge_errors"),
            (DOMAIN, "write_register"),
            (DOMAIN, "set_external_climate"),
            (DOMAIN, "set_external_power"),
            (DOMAIN, "export_knx_group_addresses"),
            (DOMAIN, "start_dhw_boost"),
            (DOMAIN, "cancel_dhw_boost"),
            (DOMAIN, "generate_ai_report"),
            (DOMAIN, "export_ai_dashboard"),
            (DOMAIN, "set_controller_clock"),
            (DOMAIN, "snooze_anomaly"),
            (DOMAIN, "unsnooze_anomaly"),
        }

    async def test_setup_is_idempotent_when_already_registered(self, mock_hass):
        await async_setup_services(mock_hass)
        first_count = mock_hass.services.async_register.call_count
        # A second setup (e.g. after a reload) must not duplicate registrations.
        mock_hass.services.has_service = MagicMock(return_value=True)
        await async_setup_services(mock_hass)
        assert mock_hass.services.async_register.call_count == first_count


class TestGetCoordinator:
    async def test_returns_coordinator(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {}
        result = await _get_coordinator(mock_hass, call)
        assert result is coord

    async def test_raises_when_no_entries(self, mock_hass):
        mock_hass.config_entries.async_entries = MagicMock(return_value=[])
        call = MagicMock()
        call.data = {}
        with pytest.raises(ServiceValidationError):
            await _get_coordinator(mock_hass, call)

    async def test_raises_when_entry_not_loaded(self, mock_hass):
        from homeassistant.config_entries import ConfigEntryState

        entry = MagicMock()
        entry.state = ConfigEntryState.NOT_LOADED
        mock_hass.config_entries.async_entries = MagicMock(return_value=[entry])
        call = MagicMock()
        call.data = {}
        with pytest.raises(ServiceValidationError):
            await _get_coordinator(mock_hass, call)

    async def test_raises_when_no_runtime_data(self, mock_hass):
        from homeassistant.config_entries import ConfigEntryState

        class _BrokenRuntime:
            @property
            def coordinator(self):
                raise AttributeError("no coordinator")

        entry = MagicMock()
        entry.state = ConfigEntryState.LOADED
        entry.runtime_data = _BrokenRuntime()
        mock_hass.config_entries.async_entries = MagicMock(return_value=[entry])
        call = MagicMock()
        call.data = {}
        with pytest.raises(ServiceValidationError):
            await _get_coordinator(mock_hass, call)

    async def test_uses_entry_id_when_multiple_entries_loaded(self, mock_hass):
        from homeassistant.config_entries import ConfigEntryState

        from custom_components.idm_heatpump.coordinator import IdmCoordinator

        coord1 = MagicMock(spec=IdmCoordinator)
        coord2 = MagicMock(spec=IdmCoordinator)

        entry1 = MagicMock()
        entry1.state = ConfigEntryState.LOADED
        entry1.entry_id = "entry-a"
        entry1.runtime_data = MagicMock()
        entry1.runtime_data.coordinator = coord1

        entry2 = MagicMock()
        entry2.state = ConfigEntryState.LOADED
        entry2.entry_id = "entry-b"
        entry2.runtime_data = MagicMock()
        entry2.runtime_data.coordinator = coord2

        mock_hass.config_entries.async_entries = MagicMock(return_value=[entry1, entry2])

        call = MagicMock()
        call.data = {"entry_id": "entry-b"}
        result = await _get_coordinator(mock_hass, call)
        assert result is coord2

    async def test_raises_when_entry_id_not_loaded(self, mock_hass):
        from homeassistant.config_entries import ConfigEntryState

        entry = MagicMock()
        entry.state = ConfigEntryState.LOADED
        entry.entry_id = "entry-a"
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = MagicMock()
        mock_hass.config_entries.async_entries = MagicMock(return_value=[entry])

        call = MagicMock()
        call.data = {"entry_id": "does-not-exist"}
        with pytest.raises(ServiceValidationError):
            await _get_coordinator(mock_hass, call)

    async def test_raises_when_multiple_entries_without_entry_id(self, mock_hass):
        from homeassistant.config_entries import ConfigEntryState

        from custom_components.idm_heatpump.coordinator import IdmCoordinator

        coord1 = MagicMock(spec=IdmCoordinator)
        entry1 = MagicMock()
        entry1.state = ConfigEntryState.LOADED
        entry1.entry_id = "entry-a"
        entry1.runtime_data = MagicMock()
        entry1.runtime_data.coordinator = coord1

        entry2 = MagicMock()
        entry2.state = ConfigEntryState.LOADED
        entry2.entry_id = "entry-b"
        entry2.runtime_data = MagicMock()
        entry2.runtime_data.coordinator = MagicMock()

        mock_hass.config_entries.async_entries = MagicMock(return_value=[entry1, entry2])
        call = MagicMock()
        call.data = {}
        with pytest.raises(ServiceValidationError) as exc_info:
            await _get_coordinator(mock_hass, call)
        assert exc_info.value.translation_key == "multiple_entries_select_entry"


class TestSetSystemMode:
    @pytest.mark.parametrize(
        "mode_str,expected_val",
        [
            ("standby", 0),
            ("automatik", 1),
            ("automatic", 1),
            ("abwesend", 2),
            ("away", 2),
            ("urlaub", 3),
            ("holiday", 3),
            ("nur warmwasser", 4),
            ("hot water only", 4),
            ("nur heizung/kuehlung", 5),
            ("heating/cooling only", 5),
        ],
    )
    async def test_valid_modes(self, mock_hass, mode_str, expected_val):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"mode": mode_str}
        await _handle_set_system_mode(mock_hass, call)
        coord.async_write_register.assert_called_once()
        reg, val = coord.async_write_register.call_args[0]
        assert val == expected_val
        assert reg.address == 1005

    async def test_web_only_entry_routes_through_the_web_interface(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.async_web_set_system_mode = AsyncMock()
        coord.config_entry.options = {"connection_mode": "web_only"}
        coord.config_entry.data = {}
        call = MagicMock()
        call.data = {"mode": "hot water only"}

        await _handle_set_system_mode(mock_hass, call)

        coord.async_web_set_system_mode.assert_awaited_once_with(4)
        coord.async_write_register.assert_not_called()

    async def test_modbus_entry_keeps_the_register_path(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.async_web_set_system_mode = AsyncMock()
        coord.config_entry.options = {"connection_mode": "modbus_web"}
        coord.config_entry.data = {}
        call = MagicMock()
        call.data = {"mode": "standby"}

        await _handle_set_system_mode(mock_hass, call)

        coord.async_write_register.assert_called_once()
        coord.async_web_set_system_mode.assert_not_called()

    async def test_invalid_mode_raises(self, mock_hass):
        _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"mode": "invalid_mode_xyz"}
        with pytest.raises(ServiceValidationError):
            await _handle_set_system_mode(mock_hass, call)

    async def test_mode_case_insensitive(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"mode": "AUTOMATIK"}
        await _handle_set_system_mode(mock_hass, call)
        coord.async_write_register.assert_called_once()
        _, val = coord.async_write_register.call_args[0]
        assert val == 1

    async def test_write_error_is_translated(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.async_write_register = AsyncMock(side_effect=Exception("connection lost"))
        call = MagicMock()
        call.data = {"mode": "automatic"}

        with pytest.raises(HomeAssistantError) as exc_info:
            await _handle_set_system_mode(mock_hass, call)

        assert exc_info.value.translation_key == "write_connection_failed"


def _shared_acknowledge_register():
    """The Navigator 2.0/10 acknowledge: holding register 1999."""
    from idm_heatpump import DataType, RegisterDef

    return RegisterDef(
        address=1999,
        datatype=DataType.UCHAR,
        name="error_acknowledge",
        writable=True,
        write_only=True,
    )


class TestSetControllerClock:
    async def test_sets_clock_through_the_pooled_web_client(self, mock_hass):
        from datetime import datetime as dt

        coord = _make_coordinator_in_hass(mock_hass)
        coord.web_supplement = MagicMock()
        coord.web_supplement.web_variant = "nav10"
        client = MagicMock()
        client.set_datetime = AsyncMock()
        coord._web_write_client = MagicMock(return_value=client)
        coord.async_refresh_web_supplement = AsyncMock()
        call = MagicMock()
        call.data = {}

        await _handle_set_controller_clock(mock_hass, call)

        client.set_datetime.assert_awaited_once()
        moment = client.set_datetime.await_args.args[0]
        assert isinstance(moment, dt)
        coord.async_refresh_web_supplement.assert_awaited_once()

    async def test_without_web_supplement_is_rejected(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.web_supplement = None
        call = MagicMock()
        call.data = {}

        with pytest.raises(ServiceValidationError):
            await _handle_set_controller_clock(mock_hass, call)

    async def test_explicit_datetime_string_is_parsed(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.web_supplement = MagicMock()
        coord.web_supplement.web_variant = "nav20"
        client = MagicMock()
        client.set_datetime = AsyncMock()
        coord._web_write_client = MagicMock(return_value=client)
        coord.async_refresh_web_supplement = AsyncMock()
        call = MagicMock()
        call.data = {"datetime": "2026-09-29T12:30:00"}

        await _handle_set_controller_clock(mock_hass, call)

        moment = client.set_datetime.await_args.args[0]
        assert moment.year == 2026 and moment.hour == 12

    async def test_invalid_datetime_string_is_rejected(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.web_supplement = MagicMock()
        coord.web_supplement.web_variant = "nav10"
        call = MagicMock()
        call.data = {"datetime": "not-a-date"}

        with pytest.raises(ServiceValidationError):
            await _handle_set_controller_clock(mock_hass, call)


class TestAcknowledgeErrorsWebRouting:
    async def test_web_only_entry_acknowledges_through_the_web_interface(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.async_web_acknowledge_notifications = AsyncMock()
        coord.config_entry.options = {"connection_mode": "web_only"}
        coord.config_entry.data = {}
        call = MagicMock()
        call.data = {}

        await _handle_acknowledge_errors(mock_hass, call)

        coord.async_web_acknowledge_notifications.assert_awaited_once()
        coord.async_write_register.assert_not_called()


class TestAcknowledgeErrors:
    async def test_writes_error_register(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.get_register = MagicMock(return_value=_shared_acknowledge_register())
        call = MagicMock()
        await _handle_acknowledge_errors(mock_hass, call)
        coord.async_write_register.assert_called_once()
        reg, val = coord.async_write_register.call_args[0]
        assert reg.address == 1999
        assert reg.register_type.value == "input"
        assert val == 1
        # The model map's own register is written without the custom-register
        # bypass — model availability stays validated.
        assert coord.async_write_register.call_args.kwargs.get("allow_custom_register") is False

    async def test_write_error_is_translated(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.get_register = MagicMock(return_value=_shared_acknowledge_register())
        coord.async_write_register = AsyncMock(side_effect=Exception("connection lost"))
        call = MagicMock()

        with pytest.raises(HomeAssistantError) as exc_info:
            await _handle_acknowledge_errors(mock_hass, call)

        assert exc_info.value.translation_key == "write_connection_failed"

    async def test_missing_register_raises_validation_error(self, mock_hass):
        """No acknowledge in the detected map: a translated refusal instead of
        the former synthetic fallback that wrote the undocumented 1999."""
        _make_coordinator_in_hass(mock_hass)
        call = MagicMock()

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_acknowledge_errors(mock_hass, call)

        assert exc_info.value.translation_key == "error_acknowledge_unavailable"

    async def test_read_only_register_raises_validation_error(self, mock_hass):
        from idm_heatpump import DataType, RegisterDef

        coord = _make_coordinator_in_hass(mock_hass)
        coord.get_register = MagicMock(
            return_value=RegisterDef(address=1999, datatype=DataType.UCHAR, name="error_acknowledge")
        )
        call = MagicMock()

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_acknowledge_errors(mock_hass, call)

        assert exc_info.value.translation_key == "error_acknowledge_unavailable"


class TestWriteRegister:
    async def test_requires_acknowledge_risk(self, mock_hass):
        _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"address": 1000, "value": 5, "acknowledge_risk": False}
        with pytest.raises(ServiceValidationError):
            await _handle_write_register(mock_hass, call)

    async def test_requires_acknowledge_risk_missing(self, mock_hass):
        _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        # acknowledge_risk key is absent; get returns None, which is not True
        call.data = {"address": 1000, "value": 5, "acknowledge_risk": None}
        with pytest.raises(ServiceValidationError):
            await _handle_write_register(mock_hass, call)

    async def test_missing_address_raises_service_validation_error(self, mock_hass):
        """hass.services.async_register is called without a schema=, so
        services.yaml's required: true is UI-only, not server-enforced; a
        caller omitting a required field must get a translated
        ServiceValidationError, not an unhandled KeyError.
        """
        _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"value": 5, "acknowledge_risk": True}
        with pytest.raises(ServiceValidationError):
            await _handle_write_register(mock_hass, call)

    async def test_missing_value_raises_service_validation_error(self, mock_hass):
        _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"address": 1000, "acknowledge_risk": True}
        with pytest.raises(ServiceValidationError):
            await _handle_write_register(mock_hass, call)

    async def test_non_numeric_address_raises_service_validation_error(self, mock_hass):
        _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"address": "not-a-number", "value": 5, "acknowledge_risk": True}
        with pytest.raises(ServiceValidationError):
            await _handle_write_register(mock_hass, call)

    async def test_writes_int_value(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"address": 1000, "value": "42", "acknowledge_risk": True}
        result = await _handle_write_register(mock_hass, call)
        reg = coord.async_write_register.call_args.args[0]
        coord.async_write_register.assert_awaited_once_with(
            reg,
            42,
            allow_custom_register=True,
        )
        assert result["success"] is True
        assert result["address"] == 1000

    async def test_writes_float_value(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {
            "address": 1000,
            "value": "22.5",
            "datatype": "float",
            "acknowledge_risk": True,
        }
        result = await _handle_write_register(mock_hass, call)
        coord.async_write_register.assert_awaited_once()
        assert result["success"] is True

    async def test_raises_on_write_error(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.async_write_register = AsyncMock(side_effect=Exception("write failed"))
        call = MagicMock()
        call.data = {"address": 1000, "value": 1, "acknowledge_risk": True}
        with pytest.raises(HomeAssistantError):
            await _handle_write_register(mock_hass, call)

    async def test_write_error_creates_write_rejected_issue(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.async_write_register = AsyncMock(side_effect=Exception("write failed"))
        call = MagicMock()
        call.data = {"address": 1000, "value": 1, "acknowledge_risk": True}

        with patch("custom_components.idm_heatpump.services.ir") as mock_ir, pytest.raises(HomeAssistantError):
            await _handle_write_register(mock_hass, call)

        mock_ir.async_create_issue.assert_called_once_with(
            mock_hass,
            "idm_heatpump",
            "write_rejected_entry-1",
            is_fixable=False,
            severity=mock_ir.IssueSeverity.WARNING,
            translation_key="write_rejected",
            translation_placeholders={
                "register": "manual_1000",
                "address": "1000",
                "detail": "Exception: write failed",
            },
        )

    async def test_returns_value_in_result(self, mock_hass):
        _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"address": 2000, "value": "100", "acknowledge_risk": True}
        result = await _handle_write_register(mock_hass, call)
        assert result["value"] == "100"
        assert result["address"] == 2000

    async def test_non_numeric_string_is_rejected(self, mock_hass):
        _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"address": 1000, "value": "not_a_number", "acknowledge_risk": True}
        with pytest.raises(ServiceValidationError):
            await _handle_write_register(mock_hass, call)

    @pytest.mark.parametrize(
        "datatype_str,expected_type",
        [
            ("uint16", "UINT16"),
            ("UINT16", "UINT16"),  # case-insensitive
            ("int16", "INT16"),
            ("INT16", "INT16"),
            ("float", "FLOAT"),
            ("FLOAT", "FLOAT"),
            ("uchar", "UCHAR"),
            ("bool", "BOOL"),
        ],
    )
    async def test_all_valid_datatypes(self, mock_hass, datatype_str, expected_type):
        _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {
            "address": 1000,
            "value": "0",
            "acknowledge_risk": True,
            "datatype": datatype_str,
        }
        result = await _handle_write_register(mock_hass, call)
        assert result["success"] is True

    async def test_invalid_datatype_raises(self, mock_hass):
        _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {
            "address": 1000,
            "value": "0",
            "acknowledge_risk": True,
            "datatype": "hexfloat",  # invalid
        }
        with pytest.raises(ServiceValidationError):
            await _handle_write_register(mock_hass, call)

    async def test_default_datatype_is_uint16(self, mock_hass):
        _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        # Use a MagicMock that supports .get() naturally
        data = MagicMock()
        data.__getitem__ = lambda self, k: {"address": 1000, "value": "5", "acknowledge_risk": True}[k]
        data.get = lambda k, d=None: {"address": 1000, "value": "5", "acknowledge_risk": True}.get(k, d)
        call.data = data
        result = await _handle_write_register(mock_hass, call)
        assert result["success"] is True


class TestGetCoordinatorMultipleDevices:
    async def test_first_loaded_entry_used(self, mock_hass):
        """With multiple entries, the first LOADED one is used."""
        from homeassistant.config_entries import ConfigEntryState

        from custom_components.idm_heatpump.coordinator import IdmCoordinator

        coord1 = MagicMock(spec=IdmCoordinator)
        coord1.async_write_register = AsyncMock()
        coord2 = MagicMock(spec=IdmCoordinator)
        coord2.async_write_register = AsyncMock()

        entry1 = MagicMock()
        entry1.state = ConfigEntryState.LOADED
        entry1.runtime_data = MagicMock()
        entry1.runtime_data.coordinator = coord1

        entry2 = MagicMock()
        entry2.state = ConfigEntryState.LOADED
        entry2.runtime_data = MagicMock()
        entry2.runtime_data.coordinator = coord2

        mock_hass.config_entries.async_entries = MagicMock(return_value=[entry1, entry2])
        call = MagicMock()
        call.data = {}
        with pytest.raises(ServiceValidationError) as exc_info:
            await _get_coordinator(mock_hass, call)
        assert exc_info.value.translation_key == "multiple_entries_select_entry"

    async def test_skips_not_loaded_entries(self, mock_hass):
        """NOT_LOADED entries are skipped; uses next LOADED entry."""
        from homeassistant.config_entries import ConfigEntryState

        from custom_components.idm_heatpump.coordinator import IdmCoordinator

        coord2 = MagicMock(spec=IdmCoordinator)
        coord2.async_write_register = AsyncMock()

        entry1 = MagicMock()
        entry1.state = ConfigEntryState.NOT_LOADED

        entry2 = MagicMock()
        entry2.state = ConfigEntryState.LOADED
        entry2.runtime_data = MagicMock()
        entry2.runtime_data.coordinator = coord2

        mock_hass.config_entries.async_entries = MagicMock(return_value=[entry1, entry2])
        call = MagicMock()
        call.data = {}
        result = await _get_coordinator(mock_hass, call)
        assert result is coord2


class TestSetExternalClimate:
    def _setup_registers(self, coord):
        from idm_heatpump import DataType, RegisterDef

        registers = {
            "hc_a_ext_room_temp": RegisterDef(1812, DataType.FLOAT, "hc_a_ext_room_temp", unit="°C", writable=True),
            "hc_b_ext_room_temp": RegisterDef(1912, DataType.FLOAT, "hc_b_ext_room_temp", unit="°C", writable=True),
            "ext_humidity": RegisterDef(1692, DataType.FLOAT, "ext_humidity", unit="%", writable=True),
        }
        coord.get_register.side_effect = registers.get
        return registers

    async def test_writes_room_temperature_and_humidity(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        self._setup_registers(coord)
        call = MagicMock()
        call.data = {"heating_circuit": "A", "room_temperature": 23.1, "humidity": 58.4}

        await _handle_set_external_climate(mock_hass, call)

        assert coord.async_write_register.await_count == 2
        temp_call, humidity_call = coord.async_write_register.await_args_list
        assert temp_call.args[0].name == "hc_a_ext_room_temp"
        assert temp_call.args[1] == 23.1
        assert humidity_call.args[0].name == "ext_humidity"
        assert humidity_call.args[1] == 58.4

    async def test_humidity_is_optional(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        self._setup_registers(coord)
        call = MagicMock()
        call.data = {"heating_circuit": "b", "room_temperature": "21.5"}

        await _handle_set_external_climate(mock_hass, call)

        coord.async_write_register.assert_awaited_once()
        reg, value = coord.async_write_register.await_args.args
        assert reg.name == "hc_b_ext_room_temp"
        assert value == 21.5

    @pytest.mark.parametrize(
        "data",
        [
            {"heating_circuit": "Z", "room_temperature": 20},
            {"heating_circuit": "A", "room_temperature": -20.1},
            {"heating_circuit": "A", "room_temperature": 60.1},
            {"heating_circuit": "A", "room_temperature": 20, "humidity": -0.1},
            {"heating_circuit": "A", "room_temperature": 20, "humidity": 100.1},
            {"heating_circuit": "A", "room_temperature": "nan"},
        ],
    )
    async def test_validates_inputs(self, mock_hass, data):
        coord = _make_coordinator_in_hass(mock_hass)
        self._setup_registers(coord)
        call = MagicMock()
        call.data = data

        with pytest.raises(ServiceValidationError):
            await _handle_set_external_climate(mock_hass, call)

        coord.async_write_register.assert_not_awaited()

    async def test_requires_known_writable_library_register(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.get_register.return_value = None
        call = MagicMock()
        call.data = {"heating_circuit": "A", "room_temperature": 23.1}

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_set_external_climate(mock_hass, call)

        assert exc_info.value.translation_key == "write_not_supported"
        coord.async_write_register.assert_not_awaited()

    async def test_write_error_is_translated(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        self._setup_registers(coord)
        coord.async_write_register = AsyncMock(side_effect=Exception("connection lost"))
        call = MagicMock()
        call.data = {"heating_circuit": "A", "room_temperature": 23.1}

        with pytest.raises(HomeAssistantError) as exc_info:
            await _handle_set_external_climate(mock_hass, call)

        assert exc_info.value.translation_key == "write_connection_failed"


class TestSetExternalPower:
    def _setup_registers(self, coord):
        from idm_heatpump import DataType, RegisterDef

        registers = {
            "pv_surplus": RegisterDef(1650, DataType.FLOAT, "pv_surplus", unit="kW", writable=True),
            "pv_production": RegisterDef(1652, DataType.FLOAT, "pv_production", unit="kW", writable=True),
            "house_consumption": RegisterDef(
                1654,
                DataType.FLOAT,
                "house_consumption",
                unit="kW",
                writable=True,
                min_val=0,
            ),
            "battery_discharge": RegisterDef(1656, DataType.FLOAT, "battery_discharge", unit="kW", writable=True),
            "battery_soc": RegisterDef(1658, DataType.INT16, "battery_soc", unit="%", writable=True),
            "electric_heater_power": RegisterDef(
                1660, DataType.FLOAT, "electric_heater_power", unit="kW", writable=True
            ),
        }
        coord.get_register.side_effect = registers.get
        return registers

    async def test_writes_only_supplied_measurements(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        self._setup_registers(coord)
        call = MagicMock()
        call.data = {"pv_surplus": 1.537, "house_consumption": "0.386", "battery_soc": 72}

        await _handle_set_external_power(mock_hass, call)

        assert coord.async_write_register.await_count == 3
        assert [(args.args[0].name, args.args[1]) for args in coord.async_write_register.await_args_list] == [
            ("pv_surplus", 1.537),
            ("house_consumption", 0.386),
            ("battery_soc", 72.0),
        ]

    @pytest.mark.parametrize(
        "data,translation_key",
        [
            ({}, "external_power_no_values"),
            ({"pv_surplus": None}, "external_power_no_values"),
            ({"pv_surplus": "nan"}, "invalid_value"),
            ({"pv_production": "inf"}, "invalid_value"),
            ({"battery_soc": -1}, "external_power_battery_soc_out_of_range"),
            ({"battery_soc": 101}, "external_power_battery_soc_out_of_range"),
            ({"battery_soc": 72.5}, "external_power_battery_soc_out_of_range"),
            ({"house_consumption": -0.1}, "write_out_of_range"),
        ],
    )
    async def test_validates_all_inputs_before_writing(self, mock_hass, data, translation_key):
        coord = _make_coordinator_in_hass(mock_hass)
        self._setup_registers(coord)
        call = MagicMock()
        call.data = data

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_set_external_power(mock_hass, call)

        assert exc_info.value.translation_key == translation_key
        coord.async_write_register.assert_not_awaited()

    async def test_validates_all_registers_before_writing(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        registers = self._setup_registers(coord)
        del registers["battery_soc"]
        call = MagicMock()
        call.data = {"pv_surplus": 1.5, "battery_soc": 72}

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_set_external_power(mock_hass, call)

        assert exc_info.value.translation_key == "write_not_supported"
        coord.async_write_register.assert_not_awaited()

    async def test_write_error_is_translated(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        self._setup_registers(coord)
        coord.async_write_register = AsyncMock(side_effect=Exception("connection lost"))
        call = MagicMock()
        call.data = {"pv_surplus": 1.5}

        with pytest.raises(HomeAssistantError) as exc_info:
            await _handle_set_external_power(mock_hass, call)

        assert exc_info.value.translation_key == "write_connection_failed"


class TestExportKnxGroupAddresses:
    """The ETS export answers for the objects this controller exposes."""

    def _coordinator(self, mock_hass, *, options=None):
        from idm_heatpump import DataType, RegisterDef

        registers = {
            "outdoor_temp": RegisterDef(1000, DataType.FLOAT, "outdoor_temp", unit="°C"),
            "hc_a_mode": RegisterDef(1393, DataType.UCHAR, "hc_a_mode", writable=True),
            "solar_mode": RegisterDef(1856, DataType.UCHAR, "solar_mode", writable=True),
            "error_acknowledge": RegisterDef(1999, DataType.UCHAR, "error_acknowledge", writable=True, write_only=True),
        }
        coordinator = _make_coordinator_in_hass(mock_hass)
        coordinator.data = {"outdoor_temp": 7.5, "hc_a_mode": 2, "solar_mode": 1}
        coordinator.get_register = MagicMock(side_effect=registers.get)
        coordinator.config_entry.options = options or {}
        return coordinator

    def _call(self, data=None):
        call = MagicMock()
        call.data = data or {}
        return call

    async def test_answers_with_the_exposed_objects(self, mock_hass):
        self._coordinator(mock_hass)
        response = await _handle_export_knx_group_addresses(mock_hass, self._call({"knx_base_address": "8/0/0"}))

        assert response["base_address"] == "8/0/0"
        by_register = {row["register"]: row for row in response["objects"]}
        assert by_register["outdoor_temp"]["group_address"] == "8/0/1"
        assert by_register["outdoor_temp"]["dpt"] == "9.001"
        assert by_register["outdoor_temp"]["writable"] is False
        assert by_register["hc_a_mode"]["group_address"] == "8/0/222"
        assert by_register["hc_a_mode"]["writable"] is True
        assert response["count"] == len(response["objects"])

    async def test_includes_write_only_registers(self, mock_hass):
        """error_acknowledge carries no value but is reachable from the bus."""
        self._coordinator(mock_hass)
        response = await _handle_export_knx_group_addresses(mock_hass, self._call())
        assert "error_acknowledge" in {row["register"] for row in response["objects"]}

    async def test_falls_back_to_the_configured_options(self, mock_hass):
        self._coordinator(mock_hass, options={"knx_base_address": "1/0/0", "knx_groups": ["solar"]})
        response = await _handle_export_knx_group_addresses(mock_hass, self._call())

        assert response["base_address"] == "1/0/0"
        assert {row["register"] for row in response["objects"]} == {"solar_mode"}
        assert response["objects"][0]["group_address"] == "1/1/197"

    async def test_a_single_group_may_arrive_as_a_bare_string(self, mock_hass):
        """A YAML call can pass one group unwrapped; str must not be iterated."""
        self._coordinator(mock_hass)
        response = await _handle_export_knx_group_addresses(mock_hass, self._call({"knx_groups": "solar"}))
        assert {row["register"] for row in response["objects"]} == {"solar_mode"}

    async def test_rejects_an_unusable_base_address(self, mock_hass):
        self._coordinator(mock_hass)
        with pytest.raises(ServiceValidationError):
            await _handle_export_knx_group_addresses(mock_hass, self._call({"knx_base_address": "0/0/0"}))

    async def test_survives_a_coordinator_without_a_config_entry(self, mock_hass):
        coordinator = self._coordinator(mock_hass)
        coordinator.config_entry = None
        response = await _handle_export_knx_group_addresses(mock_hass, self._call())
        assert response["base_address"] == "8/0/0"


class TestServiceSchemas:
    """The schemas must accept every documented call and reject bad shapes.

    These assertions only mean something against the real voluptuous, which
    ships with Home Assistant and is what CI installs; the fallback stub used
    in a checkout without it validates by returning its input.
    """

    def _real_voluptuous(self):
        import voluptuous as vol

        return not vol.__name__.startswith("builtins") and hasattr(vol, "MultipleInvalid")

    def test_target_fields_are_accepted(self):
        """Services declared with target: receive entity_id and friends."""
        from custom_components.idm_heatpump.services import _SET_SYSTEM_MODE_SCHEMA

        result = _SET_SYSTEM_MODE_SCHEMA({"entity_id": ["sensor.idm_outdoor_temp"], "mode": "automatic"})
        assert result["mode"] == "automatic"

    def test_write_register_accepts_a_documented_call(self):
        from custom_components.idm_heatpump.services import _WRITE_REGISTER_SCHEMA

        result = _WRITE_REGISTER_SCHEMA(
            {
                "address": 1005,
                "value": "1",
                "datatype": "uchar",
                "acknowledge_risk": True,
            }
        )
        assert result["address"] == 1005

    def test_write_register_rejects_an_address_outside_the_modbus_range(self):
        import voluptuous as vol

        from custom_components.idm_heatpump.services import _WRITE_REGISTER_SCHEMA

        if not self._real_voluptuous():
            pytest.skip("the fallback voluptuous stub does not validate")
        with pytest.raises(vol.Invalid):
            _WRITE_REGISTER_SCHEMA({"address": 999999, "value": "1", "acknowledge_risk": True})

    def test_external_climate_coerces_numbers(self):
        from custom_components.idm_heatpump.services import _SET_EXTERNAL_CLIMATE_SCHEMA

        result = _SET_EXTERNAL_CLIMATE_SCHEMA({"heating_circuit": "A", "room_temperature": "21.5"})
        assert result["room_temperature"] == 21.5

    def test_external_climate_rejects_a_non_numeric_temperature(self):
        import voluptuous as vol

        from custom_components.idm_heatpump.services import _SET_EXTERNAL_CLIMATE_SCHEMA

        if not self._real_voluptuous():
            pytest.skip("the fallback voluptuous stub does not validate")
        with pytest.raises(vol.Invalid):
            _SET_EXTERNAL_CLIMATE_SCHEMA({"heating_circuit": "A", "room_temperature": "warm"})

    def test_every_documented_field_is_in_its_schema(self):
        """services.yaml and the schemas must describe the same fields."""
        import pathlib as _pathlib

        import yaml

        import custom_components.idm_heatpump.services as services_module

        documented = yaml.safe_load(
            (_pathlib.Path(services_module.__file__).parent / "services.yaml").read_text(encoding="utf-8")
        )
        schemas = {
            "set_system_mode": services_module._SET_SYSTEM_MODE_SCHEMA,
            "write_register": services_module._WRITE_REGISTER_SCHEMA,
            "set_external_climate": services_module._SET_EXTERNAL_CLIMATE_SCHEMA,
            "set_external_power": services_module._SET_EXTERNAL_POWER_SCHEMA,
            "export_knx_group_addresses": services_module._EXPORT_KNX_SCHEMA,
        }
        for service, schema in schemas.items():
            fields = set(documented[service].get("fields", {}))
            known = {str(getattr(marker, "schema", getattr(marker, "key", marker))) for marker in schema.schema}
            missing = fields - known
            assert not missing, f"{service} documents fields its schema would reject: {sorted(missing)}"


class TestWriteSafetyHelpersNone:
    def test_none_safety_result_yields_none(self):
        """A write without a dry-run plan (None result) answers no registers."""
        assert _encoded_registers_from_safety_result(None) is None


class TestGetCoordinatorEntityTargets:
    """Target-based routing: entity_id lists and bare strings resolve the
    owning config entry through the entity registry."""

    def _registry(self, entries):
        class _Registry:
            def __init__(self):
                self.lookups = []

            def async_get(self, entity_id):
                self.lookups.append(entity_id)
                return entries.get(entity_id)

        return _Registry()

    def _registry_entry(self, config_entry_id):
        entry = MagicMock()
        entry.config_entry_id = config_entry_id
        return entry

    def _loaded_entry(self, entry_id, coordinator):
        from homeassistant.config_entries import ConfigEntryState

        entry = MagicMock()
        entry.state = ConfigEntryState.LOADED
        entry.entry_id = entry_id
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = coordinator
        return entry

    def _coordinator(self):
        from custom_components.idm_heatpump.coordinator import IdmCoordinator

        return MagicMock(spec=IdmCoordinator)

    async def test_entity_id_list_resolves_the_owning_entry(self, mock_hass):
        from custom_components.idm_heatpump.coordinator import IdmCoordinator

        coord_a = MagicMock(spec=IdmCoordinator)
        coord_b = MagicMock(spec=IdmCoordinator)
        mock_hass.config_entries.async_entries = MagicMock(
            return_value=[self._loaded_entry("entry-a", coord_a), self._loaded_entry("entry-b", coord_b)]
        )
        registry = self._registry({"sensor.idm_b": self._registry_entry("entry-b")})

        call = MagicMock()
        call.data = {"entity_id": ["sensor.unknown", "sensor.idm_b"]}

        with patch("homeassistant.helpers.entity_registry.async_get", return_value=registry):
            result = await _get_coordinator(mock_hass, call)

        assert result is coord_b
        # An unknown entity in the list is skipped, not fatal.
        assert registry.lookups == ["sensor.unknown", "sensor.idm_b"]

    async def test_registry_entries_without_config_entry_are_skipped(self, mock_hass):
        coord_a = self._coordinator()
        mock_hass.config_entries.async_entries = MagicMock(return_value=[self._loaded_entry("entry-a", coord_a)])
        registry = self._registry(
            {"sensor.orphan": self._registry_entry(None), "sensor.idm_a": self._registry_entry("entry-a")}
        )

        call = MagicMock()
        call.data = {"entity_id": ["sensor.orphan", "sensor.idm_a"]}

        with patch("homeassistant.helpers.entity_registry.async_get", return_value=registry):
            result = await _get_coordinator(mock_hass, call)

        assert result is coord_a

    async def test_bare_entity_id_string_resolves_the_owning_entry(self, mock_hass):
        coord_a = self._coordinator()
        coord_b = self._coordinator()
        mock_hass.config_entries.async_entries = MagicMock(
            return_value=[self._loaded_entry("entry-a", coord_a), self._loaded_entry("entry-b", coord_b)]
        )
        registry = self._registry({"sensor.idm_a": self._registry_entry("entry-a")})

        call = MagicMock()
        call.data = {"entity_id": "sensor.idm_a"}

        with patch("homeassistant.helpers.entity_registry.async_get", return_value=registry):
            result = await _get_coordinator(mock_hass, call)

        assert result is coord_a

    async def test_entity_id_pointing_at_an_unloaded_entry_is_rejected(self, mock_hass):
        coord_a = self._coordinator()
        mock_hass.config_entries.async_entries = MagicMock(return_value=[self._loaded_entry("entry-a", coord_a)])
        registry = self._registry({"sensor.other_plant": self._registry_entry("entry-zzz")})

        call = MagicMock()
        call.data = {"entity_id": "sensor.other_plant"}

        with (
            patch("homeassistant.helpers.entity_registry.async_get", return_value=registry),
            pytest.raises(ServiceValidationError) as exc_info,
        ):
            await _get_coordinator(mock_hass, call)

        assert exc_info.value.translation_key == "entry_not_loaded"

    async def test_blank_entry_id_is_treated_as_absent(self, mock_hass):
        """An entry_id of only whitespace falls back to the ambient entry."""
        coord = self._coordinator()
        mock_hass.config_entries.async_entries = MagicMock(return_value=[self._loaded_entry("entry-a", coord)])

        call = MagicMock()
        call.data = {"entry_id": "   "}

        result = await _get_coordinator(mock_hass, call)
        assert result is coord

    async def test_requested_entry_with_broken_runtime_data_is_rejected(self, mock_hass):
        from homeassistant.config_entries import ConfigEntryState

        class _BrokenRuntime:
            @property
            def coordinator(self):
                raise AttributeError("no coordinator")

        entry = MagicMock()
        entry.state = ConfigEntryState.LOADED
        entry.entry_id = "entry-a"
        entry.runtime_data = _BrokenRuntime()
        mock_hass.config_entries.async_entries = MagicMock(return_value=[entry])

        call = MagicMock()
        call.data = {"entry_id": "entry-a"}

        with pytest.raises(ServiceValidationError) as exc_info:
            await _get_coordinator(mock_hass, call)

        assert exc_info.value.translation_key == "entry_not_loaded"


class TestTranslatedWriteErrorPassThrough:
    """Already-translated HomeAssistantErrors must not be re-wrapped."""

    async def test_homeassistant_errors_are_reraised_unchanged(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        sentinel = HomeAssistantError(translation_domain=DOMAIN, translation_key="write_out_of_range")
        coord.async_write_register = AsyncMock(side_effect=sentinel)
        call = MagicMock()
        call.data = {"mode": "automatic"}

        with pytest.raises(HomeAssistantError) as exc_info:
            await _handle_set_system_mode(mock_hass, call)

        assert exc_info.value is sentinel

    async def test_write_register_reraises_homeassistant_errors_without_an_issue(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        sentinel = HomeAssistantError(translation_domain=DOMAIN, translation_key="write_out_of_range")
        coord.async_write_register = AsyncMock(side_effect=sentinel)
        call = MagicMock()
        call.data = {"address": 1000, "value": 1, "acknowledge_risk": True}

        with (
            patch("custom_components.idm_heatpump.services.ir") as mock_ir,
            pytest.raises(HomeAssistantError) as exc_info,
        ):
            await _handle_write_register(mock_hass, call)

        assert exc_info.value is sentinel
        # The write_rejected issue is reserved for untranslated failures.
        mock_ir.async_create_issue.assert_not_called()


class TestWebOnlyDetection:
    async def test_coordinator_without_config_entry_is_not_web_only(self, mock_hass):
        from custom_components.idm_heatpump.services import _entry_is_web_only

        coord = _make_coordinator_in_hass(mock_hass)
        coord.config_entry = None

        assert _entry_is_web_only(coord) is False

    async def test_missing_config_entry_keeps_the_register_path(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.config_entry = None
        coord.async_web_set_system_mode = AsyncMock()
        call = MagicMock()
        call.data = {"mode": "standby"}

        await _handle_set_system_mode(mock_hass, call)

        coord.async_write_register.assert_called_once()
        coord.async_web_set_system_mode.assert_not_called()


class TestWriteRegisterEncodedRegisters:
    async def test_response_echoes_encoded_registers_from_a_mapping_result(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.async_write_register = AsyncMock(return_value={"encoded_registers": [5, 6]})
        call = MagicMock()
        call.data = {"address": 1000, "value": 1, "acknowledge_risk": True}

        result = await _handle_write_register(mock_hass, call)

        assert result["encoded_registers"] == [5, 6]

    async def test_response_echoes_encoded_registers_from_an_object_result(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        safety_result = MagicMock()
        safety_result.encoded_registers = (7,)
        coord.async_write_register = AsyncMock(return_value=safety_result)
        call = MagicMock()
        call.data = {"address": 1000, "value": 1, "acknowledge_risk": True}

        result = await _handle_write_register(mock_hass, call)

        assert result["encoded_registers"] == [7]


class TestExternalClimateFloatCoercion:
    async def test_missing_room_temperature_is_rejected(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"heating_circuit": "A", "room_temperature": None}

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_set_external_climate(mock_hass, call)

        assert exc_info.value.translation_key == "invalid_value"
        coord.async_write_register.assert_not_awaited()

    @pytest.mark.parametrize(
        "room_temperature",
        ["not-a-number", object()],
        ids=["non_numeric_string", "non_numeric_object"],
    )
    async def test_unconvertible_room_temperature_is_rejected(self, mock_hass, room_temperature):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"heating_circuit": "A", "room_temperature": room_temperature}

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_set_external_climate(mock_hass, call)

        assert exc_info.value.translation_key == "invalid_value"
        coord.async_write_register.assert_not_awaited()


class TestExportKnxGroupAddressesGroupFallback:
    """A knx_groups value that is neither a string nor a sequence falls back
    to every documented group instead of answering with nothing."""

    async def test_unusable_groups_value_exports_all_groups(self, mock_hass):
        from idm_heatpump import DataType, RegisterDef

        registers = {
            "outdoor_temp": RegisterDef(1000, DataType.FLOAT, "outdoor_temp", unit="°C"),
            "hc_a_mode": RegisterDef(1393, DataType.UCHAR, "hc_a_mode", writable=True),
            "solar_mode": RegisterDef(1856, DataType.UCHAR, "solar_mode", writable=True),
            "error_acknowledge": RegisterDef(1999, DataType.UCHAR, "error_acknowledge", writable=True, write_only=True),
        }
        coordinator = _make_coordinator_in_hass(mock_hass)
        coordinator.get_register = MagicMock(side_effect=registers.get)
        coordinator.config_entry.options = {}

        call = MagicMock()
        call.data = {"knx_groups": 7}

        response = await _handle_export_knx_group_addresses(mock_hass, call)

        assert {row["register"] for row in response["objects"]} == set(registers)
        assert response["count"] == len(registers)


# ---------------------------------------------------------------------------
# AI report service: explicit entry resolution, no fallback to another plant
# ---------------------------------------------------------------------------


def _ai_entry(entry_id: str = "entry-1", *, manager: object | None = "create", domain: str = DOMAIN, state=None):
    """Build an entry whose runtime data carries a real AiAdvisor.

    ``manager="create"`` builds a genuine instance (the handler isinstance-checks
    it); any other value is stored verbatim so rejection paths can be exercised.
    """
    from types import SimpleNamespace

    from homeassistant.config_entries import ConfigEntryState

    from custom_components.idm_heatpump.ai_advisor import AiAdvisor

    entry = SimpleNamespace(entry_id=entry_id, domain=domain, state=state or ConfigEntryState.LOADED, options={})
    coordinator = SimpleNamespace(config_entry=entry)
    if manager == "create":
        manager = AiAdvisor(SimpleNamespace(), entry, coordinator)
    entry.runtime_data = SimpleNamespace(ai_advisor=manager, coordinator=coordinator)
    return entry


def _ai_call(entry_id: str = "entry-1", **data):
    call = MagicMock()
    call.data = {"entry_id": entry_id, **data}
    return call


class TestGenerateAiReport:
    async def test_unknown_entry_is_rejected(self, mock_hass):
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=None)

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_generate_ai_report(mock_hass, _ai_call("missing"))

        assert exc_info.value.translation_key == "ai_disabled"

    async def test_foreign_domain_entry_is_rejected(self, mock_hass):
        entry = _ai_entry(domain="other_integration")
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=entry)

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_generate_ai_report(mock_hass, _ai_call())

        assert exc_info.value.translation_key == "ai_disabled"

    async def test_not_loaded_entry_is_rejected(self, mock_hass):
        from homeassistant.config_entries import ConfigEntryState

        entry = _ai_entry(state=ConfigEntryState.SETUP_ERROR)
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=entry)

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_generate_ai_report(mock_hass, _ai_call())

        assert exc_info.value.translation_key == "ai_disabled"

    async def test_entry_without_a_loaded_manager_is_rejected(self, mock_hass):
        entry = _ai_entry(manager=None)
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=entry)

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_generate_ai_report(mock_hass, _ai_call())

        assert exc_info.value.translation_key == "ai_disabled"

    async def test_returns_the_manager_report(self, mock_hass):
        entry = _ai_entry()
        entry.runtime_data.ai_advisor.async_generate = AsyncMock(return_value={"report": "Measured report"})
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=entry)

        result = await _handle_generate_ai_report(mock_hass, _ai_call(report_type="weekly"))

        assert result == {"report": "Measured report"}
        entry.runtime_data.ai_advisor.async_generate.assert_awaited_once_with("weekly")

    async def test_advisor_error_becomes_a_translated_home_assistant_error(self, mock_hass):
        from custom_components.idm_heatpump.ai_advisor import AdvisorError

        entry = _ai_entry()
        entry.runtime_data.ai_advisor.async_generate = AsyncMock(side_effect=AdvisorError("ai_busy"))
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=entry)

        with pytest.raises(HomeAssistantError) as exc_info:
            await _handle_generate_ai_report(mock_hass, _ai_call())

        assert exc_info.value.translation_key == "ai_busy"
        assert exc_info.value.translation_domain == DOMAIN


class TestExportAiDashboard:
    @staticmethod
    def _registry(entry_id: str, *, include_report: bool = True, include_extras: bool = True):
        """Fake the entity-registry lookups the exporter performs."""

        class _FakeEntityRegistry:
            def __init__(self, unique_ids: dict[str, str]) -> None:
                self._unique_ids = unique_ids

            def async_get_entity_id(self, domain: str, platform: str, unique_id: str) -> str | None:
                return self._unique_ids.get(unique_id)

        unique_ids: dict[str, str] = {}
        if include_report:
            unique_ids[f"{entry_id}_ai_report"] = "sensor.idm_ai_report"
        if include_extras:
            for key in ("ai_learning_status", "ai_storage_used", "ai_coverage", "ai_observed_cop"):
                unique_ids[f"{entry_id}_{key}"] = f"sensor.idm_{key}"
            for kind in ("daily", "weekly", "health", "efficiency"):
                unique_ids[f"{entry_id}_ai_report_{kind}"] = f"button.idm_ai_report_{kind}"
        return _FakeEntityRegistry(unique_ids)

    async def test_unknown_entry_is_rejected(self, mock_hass):
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=None)

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_export_ai_dashboard(mock_hass, _ai_call("missing"))

        assert exc_info.value.translation_key == "ai_disabled"

    async def test_entry_without_a_manager_is_rejected(self, mock_hass):
        from unittest.mock import patch

        entry = _ai_entry(manager=None)
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=entry)

        with (
            patch("homeassistant.helpers.entity_registry.async_get", return_value=self._registry("entry-1")),
            pytest.raises(ServiceValidationError) as exc_info,
        ):
            await _handle_export_ai_dashboard(mock_hass, _ai_call())

        assert exc_info.value.translation_key == "ai_disabled"

    async def test_missing_report_sensor_is_rejected(self, mock_hass):
        from unittest.mock import patch

        entry = _ai_entry()
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=entry)

        with (
            patch(
                "homeassistant.helpers.entity_registry.async_get",
                return_value=self._registry("entry-1", include_report=False),
            ),
            pytest.raises(ServiceValidationError) as exc_info,
        ):
            await _handle_export_ai_dashboard(mock_hass, _ai_call())

        assert exc_info.value.translation_key == "ai_disabled"

    async def test_builds_the_dashboard_from_registered_entity_ids(self, mock_hass):
        from unittest.mock import patch

        entry = _ai_entry()
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=entry)

        with patch("homeassistant.helpers.entity_registry.async_get", return_value=self._registry("entry-1")):
            result = await _handle_export_ai_dashboard(mock_hass, _ai_call())

        assert set(result) == {"dashboard"}
        view = result["dashboard"]["views"][0]
        assert view["path"] == "ai"
        cards = view["cards"]

        assert cards[0]["type"] == "markdown"
        entities_card = cards[1]
        assert entities_card == {
            "type": "entities",
            "entities": [
                "sensor.idm_ai_report",
                "sensor.idm_ai_learning_status",
                "sensor.idm_ai_storage_used",
                "sensor.idm_ai_coverage",
                "sensor.idm_ai_observed_cop",
                "button.idm_ai_report_daily",
                "button.idm_ai_report_weekly",
                "button.idm_ai_report_health",
                "button.idm_ai_report_efficiency",
            ],
        }
        report_cards = [card for card in cards if card["type"] == "markdown" and "title" in card]
        assert [card["title"] for card in report_cards] == ["Daily", "Weekly", "Health", "Efficiency"]
        assert "sensor.idm_ai_report" in report_cards[0]["content"]
        # History graphs only for the metrics that exist.
        history_cards = [card for card in cards if card["type"] == "history-graph"]
        assert [card["entities"] for card in history_cards] == [
            ["sensor.idm_ai_coverage"],
            ["sensor.idm_ai_observed_cop"],
            ["sensor.idm_ai_storage_used"],
        ]

    async def test_omits_metrics_and_buttons_that_are_not_registered(self, mock_hass):
        from unittest.mock import patch

        entry = _ai_entry("entry-2")
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=entry)

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=self._registry("entry-2", include_extras=False),
        ):
            result = await _handle_export_ai_dashboard(mock_hass, _ai_call("entry-2"))

        cards = result["dashboard"]["views"][0]["cards"]
        assert cards[1]["entities"] == ["sensor.idm_ai_report"]
        assert not [card for card in cards if card["type"] == "history-graph"]


def _advisor_entry(entry_id="entry-1", *, advisor=None, domain=DOMAIN, state=None):
    """Build a loaded config entry whose runtime_data carries a predictive advisor."""
    from types import SimpleNamespace

    from homeassistant.config_entries import ConfigEntryState

    entry = SimpleNamespace(entry_id=entry_id, domain=domain, state=state or ConfigEntryState.LOADED, options={})
    entry.runtime_data = SimpleNamespace(predictive_advisor=advisor, coordinator=SimpleNamespace(config_entry=entry))
    return entry


def _real_advisor():
    """Build a genuine PredictiveAdvisor over a minimal coordinator stub."""
    from types import SimpleNamespace

    from custom_components.idm_heatpump.predictive_advisor import PredictiveAdvisor

    coordinator = SimpleNamespace(
        hass=MagicMock(),
        config_entry=SimpleNamespace(entry_id="entry-1", options={}),
        data={},
        web_variant=None,
    )
    return PredictiveAdvisor(coordinator)


class TestSnoozeAnomaly:
    async def test_snoozes_an_advisor_reason(self, mock_hass):
        advisor = _real_advisor()
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=_advisor_entry(advisor=advisor))

        await _handle_snooze_anomaly(mock_hass, _ai_call("entry-1", reason="spread_above_baseline", days=14))

        assert advisor.is_snoozed("spread_above_baseline") is True

    async def test_defaults_to_seven_days(self, mock_hass):
        advisor = _real_advisor()
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=_advisor_entry(advisor=advisor))

        await _handle_snooze_anomaly(mock_hass, _ai_call("entry-1", reason="spread_above_baseline"))

        assert advisor.is_snoozed("spread_above_baseline") is True

    async def test_rejects_unknown_reason(self, mock_hass):
        advisor = _real_advisor()
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=_advisor_entry(advisor=advisor))

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_snooze_anomaly(mock_hass, _ai_call("entry-1", reason="nope"))

        assert exc_info.value.translation_key == "advisor_bad_reason"

    async def test_rejects_missing_advisor(self, mock_hass):
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=_advisor_entry(advisor=None))

        with pytest.raises(ServiceValidationError) as exc_info:
            await _handle_snooze_anomaly(mock_hass, _ai_call("entry-1", reason="spread_above_baseline"))

        assert exc_info.value.translation_key == "advisor_disabled"

    async def test_unsnooze_cancels_early(self, mock_hass):
        advisor = _real_advisor()
        advisor.snooze("spread_above_baseline", 7)
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=_advisor_entry(advisor=advisor))

        await _handle_unsnooze_anomaly(mock_hass, _ai_call("entry-1", reason="spread_above_baseline"))

        assert advisor.is_snoozed("spread_above_baseline") is False
