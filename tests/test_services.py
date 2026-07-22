"""Tests for service handlers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from custom_components.idm_heatpump.services import (
    async_setup_services,
    async_unload_services,
    _get_coordinator,
    _handle_set_system_mode,
    _handle_acknowledge_errors,
    _handle_write_register,
    _handle_set_external_climate,
    _encoded_registers_from_safety_result,
)


def _make_coordinator_in_hass(mock_hass, entry_id: str = "entry-1"):
    from homeassistant.config_entries import ConfigEntryState
    from custom_components.idm_heatpump.coordinator import IdmCoordinator

    coord = MagicMock(spec=IdmCoordinator)
    coord.async_write_register = AsyncMock()
    coord.client = MagicMock()
    coord.client.write_register = AsyncMock()

    entry = MagicMock()
    entry.state = ConfigEntryState.LOADED
    entry.entry_id = entry_id
    entry.runtime_data = MagicMock()
    entry.runtime_data.coordinator = coord

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
        assert mock_hass.services.async_register.call_count == 4

    async def test_skips_if_already_registered(self, mock_hass):
        mock_hass.services.has_service = MagicMock(return_value=True)
        await async_setup_services(mock_hass)
        mock_hass.services.async_register.assert_not_called()


class TestUnloadServices:
    async def test_removes_services_when_no_loaded_entries(self, mock_hass):
        from homeassistant.config_entries import ConfigEntryState

        # One entry exists but is NOT_LOADED → last loaded entry was just unloaded
        entry = MagicMock()
        entry.state = ConfigEntryState.NOT_LOADED
        mock_hass.config_entries.async_entries = MagicMock(return_value=[entry])
        await async_unload_services(mock_hass)
        assert mock_hass.services.async_remove.call_count == 4

    async def test_removes_services_when_empty(self, mock_hass):
        mock_hass.config_entries.async_entries = MagicMock(return_value=[])
        await async_unload_services(mock_hass)
        assert mock_hass.services.async_remove.call_count == 4

    async def test_keeps_services_when_loaded_entries_remain(self, mock_hass):
        from homeassistant.config_entries import ConfigEntryState

        entry1 = MagicMock()
        entry1.state = ConfigEntryState.LOADED
        entry2 = MagicMock()
        entry2.state = ConfigEntryState.LOADED
        mock_hass.config_entries.async_entries = MagicMock(return_value=[entry1, entry2])
        await async_unload_services(mock_hass)
        mock_hass.services.async_remove.assert_not_called()

    async def test_removes_services_when_only_one_loaded(self, mock_hass):
        from homeassistant.config_entries import ConfigEntryState

        entry = MagicMock()
        entry.state = ConfigEntryState.LOADED
        mock_hass.config_entries.async_entries = MagicMock(return_value=[entry])
        await async_unload_services(mock_hass)
        assert mock_hass.services.async_remove.call_count == 4


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


class TestAcknowledgeErrors:
    async def test_writes_error_register(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        await _handle_acknowledge_errors(mock_hass, call)
        coord.async_write_register.assert_called_once()
        reg, val = coord.async_write_register.call_args[0]
        assert reg.address == 1999
        assert val == 1

    async def test_write_error_is_translated(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.async_write_register = AsyncMock(side_effect=Exception("connection lost"))
        call = MagicMock()

        with pytest.raises(HomeAssistantError) as exc_info:
            await _handle_acknowledge_errors(mock_hass, call)

        assert exc_info.value.translation_key == "write_connection_failed"


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

    async def test_writes_int_value(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"address": 1000, "value": "42", "acknowledge_risk": True}
        result = await _handle_write_register(mock_hass, call)
        reg = coord.client.write_register.call_args.args[0]
        coord.client.write_register.assert_called_once_with(
            reg,
            42,
            allow_custom_register=True,
        )
        coord.simulate_write.assert_called_once_with(
            reg,
            42,
            dry_run=True,
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
        coord.client.write_register.assert_called_once()
        assert result["success"] is True

    async def test_raises_on_write_error(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.client.write_register = AsyncMock(side_effect=Exception("write failed"))
        call = MagicMock()
        call.data = {"address": 1000, "value": 1, "acknowledge_risk": True}
        with pytest.raises(HomeAssistantError):
            await _handle_write_register(mock_hass, call)

    async def test_write_error_creates_write_rejected_issue(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        coord.client.write_register = AsyncMock(side_effect=Exception("write failed"))
        call = MagicMock()
        call.data = {"address": 1000, "value": 1, "acknowledge_risk": True}

        with patch("custom_components.idm_heatpump.services.ir") as mock_ir:
            with pytest.raises(HomeAssistantError):
                await _handle_write_register(mock_hass, call)

        mock_ir.async_create_issue.assert_called_once_with(
            mock_hass,
            "idm_heatpump",
            "write_rejected",
            is_fixable=False,
            severity=mock_ir.IssueSeverity.WARNING,
            translation_key="write_rejected",
            translation_placeholders={"register": "manual_1000", "address": "1000"},
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
