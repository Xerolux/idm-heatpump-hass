"""Tests for service handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from custom_components.idm_heatpump.services import (
    async_setup_services,
    async_unload_services,
    _get_coordinator,
    _handle_set_system_mode,
    _handle_acknowledge_errors,
    _handle_write_register,
)
from custom_components.idm_heatpump.const import DOMAIN


def _make_coordinator_in_hass(mock_hass):
    from homeassistant.config_entries import ConfigEntryState
    from custom_components.idm_heatpump.coordinator import IdmCoordinator

    coord = MagicMock(spec=IdmCoordinator)
    coord.async_write_register = AsyncMock()
    coord.client = MagicMock()
    coord.client.write_register = AsyncMock()

    entry = MagicMock()
    entry.state = ConfigEntryState.LOADED
    entry.runtime_data = MagicMock()
    entry.runtime_data.coordinator = coord

    mock_hass.config_entries.async_entries = MagicMock(return_value=[entry])
    return coord


class TestSetupServices:
    async def test_registers_services(self, mock_hass):
        await async_setup_services(mock_hass)
        assert mock_hass.services.async_register.call_count == 3

    async def test_skips_if_already_registered(self, mock_hass):
        mock_hass.services.has_service = MagicMock(return_value=True)
        await async_setup_services(mock_hass)
        mock_hass.services.async_register.assert_not_called()


class TestUnloadServices:
    async def test_removes_services_when_no_entries(self, mock_hass):
        mock_hass.config_entries.async_entries = MagicMock(return_value=[])
        await async_unload_services(mock_hass)
        assert mock_hass.services.async_remove.call_count == 3

    async def test_keeps_services_when_entries_remain(self, mock_hass):
        mock_hass.config_entries.async_entries = MagicMock(return_value=[MagicMock()])
        await async_unload_services(mock_hass)
        mock_hass.services.async_remove.assert_not_called()


class TestGetCoordinator:
    async def test_returns_coordinator(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        result = await _get_coordinator(mock_hass, call)
        assert result is coord

    async def test_raises_when_no_entries(self, mock_hass):
        mock_hass.config_entries.async_entries = MagicMock(return_value=[])
        call = MagicMock()
        with pytest.raises(ServiceValidationError):
            await _get_coordinator(mock_hass, call)

    async def test_raises_when_entry_not_loaded(self, mock_hass):
        from homeassistant.config_entries import ConfigEntryState

        entry = MagicMock()
        entry.state = ConfigEntryState.NOT_LOADED
        mock_hass.config_entries.async_entries = MagicMock(return_value=[entry])
        call = MagicMock()
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
        with pytest.raises(ServiceValidationError):
            await _get_coordinator(mock_hass, call)


class TestSetSystemMode:
    @pytest.mark.parametrize("mode_str,expected_val", [
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
    ])
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


class TestAcknowledgeErrors:
    async def test_writes_error_register(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        await _handle_acknowledge_errors(mock_hass, call)
        coord.async_write_register.assert_called_once()
        reg, val = coord.async_write_register.call_args[0]
        assert reg.address == 1999
        assert val == 1


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
        coord.client.write_register.assert_called_once()
        assert result["success"] is True
        assert result["address"] == 1000

    async def test_writes_float_value(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"address": 1000, "value": "22.5", "acknowledge_risk": True}
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

    async def test_returns_value_in_result(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"address": 2000, "value": "100", "acknowledge_risk": True}
        result = await _handle_write_register(mock_hass, call)
        assert result["value"] == "100"
        assert result["address"] == 2000

    async def test_non_numeric_string_passes_as_is(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        call.data = {"address": 1000, "value": "not_a_number", "acknowledge_risk": True}
        result = await _handle_write_register(mock_hass, call)
        assert result["success"] is True
        assert result["value"] == "not_a_number"
