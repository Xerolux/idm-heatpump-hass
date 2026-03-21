"""Tests for service handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.exceptions import HomeAssistantError
from custom_components.idm_heatpump_v2.services import (
    async_setup_services,
    async_unload_services,
    _get_coordinator,
    _handle_set_system_mode,
    _handle_acknowledge_errors,
    _handle_write_register,
)
from custom_components.idm_heatpump_v2.const import DOMAIN


def _make_coordinator_in_hass(mock_hass):
    from custom_components.idm_heatpump_v2.coordinator import IdmCoordinator
    coord = MagicMock(spec=IdmCoordinator)
    coord.async_write_register = AsyncMock()
    coord.client = MagicMock()
    coord.client.write_register = AsyncMock()
    mock_hass.data[DOMAIN] = {"entry1": {"coordinator": coord}}
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
        mock_hass.data[DOMAIN] = {}
        await async_unload_services(mock_hass)
        assert mock_hass.services.async_remove.call_count == 3

    async def test_keeps_services_when_entries_remain(self, mock_hass):
        mock_hass.data[DOMAIN] = {"entry1": {}}
        await async_unload_services(mock_hass)
        mock_hass.services.async_remove.assert_not_called()


class TestGetCoordinator:
    async def test_returns_coordinator(self, mock_hass):
        coord = _make_coordinator_in_hass(mock_hass)
        call = MagicMock()
        result = await _get_coordinator(mock_hass, call)
        assert result is coord

    async def test_raises_when_no_domain_data(self, mock_hass):
        mock_hass.data[DOMAIN] = {}
        call = MagicMock()
        with pytest.raises(HomeAssistantError, match="No IDM heat pump"):
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
        with pytest.raises(HomeAssistantError, match="Invalid mode"):
            await _handle_set_system_mode(mock_hass, call)


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
        with pytest.raises(HomeAssistantError, match="acknowledge the risk"):
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
        with pytest.raises(HomeAssistantError, match="Failed to write"):
            await _handle_write_register(mock_hass, call)
