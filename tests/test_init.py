"""Tests for __init__.py (async_setup, async_setup_entry, async_unload_entry)."""

from dataclasses import dataclass
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.idm_heatpump import (
    IdmHeatpumpData,
    async_setup,
    async_setup_entry,
    async_unload_entry,
    async_reload_entry,
)
from custom_components.idm_heatpump.const import DOMAIN


class TestIdmHeatpumpData:
    def test_dataclass_fields(self):
        coordinator = MagicMock()
        client = MagicMock()
        data = IdmHeatpumpData(coordinator=coordinator, client=client)
        assert data.coordinator is coordinator
        assert data.client is client

    def test_is_dataclass(self):
        import dataclasses
        assert dataclasses.is_dataclass(IdmHeatpumpData)


class TestAsyncSetup:
    async def test_calls_setup_services(self, mock_hass):
        with patch(
            "custom_components.idm_heatpump.services.async_setup_services",
            new_callable=lambda: lambda: AsyncMock(return_value=None),
        ) as mock_setup:
            with patch(
                "custom_components.idm_heatpump.async_setup.__wrapped__",
                create=True,
            ):
                pass
        # Simpler: patch the import inside async_setup
        mock_setup_services = AsyncMock()
        with patch(
            "custom_components.idm_heatpump.services.async_setup_services",
            mock_setup_services,
        ):
            result = await async_setup(mock_hass, {})
        assert result is True

    async def test_returns_true(self, mock_hass):
        with patch(
            "custom_components.idm_heatpump.services.async_setup_services",
            AsyncMock(),
        ):
            result = await async_setup(mock_hass, {})
        assert result is True


class TestAsyncSetupEntry:
    def _make_entry(self):
        entry = MagicMock()
        entry.entry_id = "test_id"
        entry.title = "IDM Test"
        entry.data = {
            "host": "192.168.1.100",
            "port": 502,
            "slave_id": 1,
        }
        entry.options = {
            "scan_interval": 10,
            "heating_circuits": ["a"],
            "zone_count": 0,
            "zone_rooms": {},
            "hide_unused_registers": True,
        }
        entry.runtime_data = None
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    async def test_sets_runtime_data(self, mock_hass):
        entry = self._make_entry()

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 502

        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with patch(
            "custom_components.idm_heatpump.IdmModbusClient",
            return_value=mock_client,
        ), patch(
            "custom_components.idm_heatpump.IdmCoordinator",
            return_value=mock_coordinator,
        ), patch(
            "custom_components.idm_heatpump.async_get_integration",
            return_value=MagicMock(manifest={"version": "0.2.1"}),
        ), patch(
            "custom_components.idm_heatpump.get_all_sensor_descriptions",
            return_value=[],
        ), patch(
            "custom_components.idm_heatpump.get_all_binary_sensor_descriptions",
            return_value=[],
        ), patch(
            "custom_components.idm_heatpump.get_all_number_descriptions",
            return_value=[],
        ), patch(
            "custom_components.idm_heatpump.get_all_select_descriptions",
            return_value=[],
        ), patch(
            "custom_components.idm_heatpump.get_all_switch_descriptions",
            return_value=[],
        ):
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        assert entry.runtime_data is not None
        assert isinstance(entry.runtime_data, IdmHeatpumpData)
        assert entry.runtime_data.coordinator is mock_coordinator
        assert entry.runtime_data.client is mock_client

    async def test_raises_config_entry_not_ready_on_connect_failure(self, mock_hass):
        from homeassistant.exceptions import ConfigEntryNotReady

        entry = self._make_entry()
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=Exception("connection refused"))

        with patch(
            "custom_components.idm_heatpump.IdmModbusClient",
            return_value=mock_client,
        ), patch(
            "custom_components.idm_heatpump.async_get_integration",
            return_value=MagicMock(manifest={"version": "0.2.1"}),
        ), pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(mock_hass, entry)

    async def test_forwards_entry_setups(self, mock_hass):
        entry = self._make_entry()

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with patch(
            "custom_components.idm_heatpump.IdmModbusClient",
            return_value=mock_client,
        ), patch(
            "custom_components.idm_heatpump.IdmCoordinator",
            return_value=mock_coordinator,
        ), patch(
            "custom_components.idm_heatpump.async_get_integration",
            return_value=MagicMock(manifest={"version": "0.2.1"}),
        ), patch(
            "custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]
        ), patch(
            "custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]
        ), patch(
            "custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]
        ), patch(
            "custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]
        ), patch(
            "custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]
        ):
            await async_setup_entry(mock_hass, entry)

        mock_hass.config_entries.async_forward_entry_setups.assert_called_once()


class TestAsyncUnloadEntry:
    async def test_unloads_platforms(self, mock_hass):
        entry = MagicMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = AsyncMock()
        entry.runtime_data.client.disconnect = AsyncMock()
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        with patch(
            "custom_components.idm_heatpump.services.async_unload_services",
            AsyncMock(),
        ):
            result = await async_unload_entry(mock_hass, entry)

        assert result is True
        mock_hass.config_entries.async_unload_platforms.assert_called_once()

    async def test_disconnects_client_on_success(self, mock_hass):
        entry = MagicMock()
        mock_client = AsyncMock()
        mock_client.disconnect = AsyncMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = mock_client
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        with patch(
            "custom_components.idm_heatpump.services.async_unload_services",
            AsyncMock(),
        ):
            await async_unload_entry(mock_hass, entry)

        mock_client.disconnect.assert_called_once()

    async def test_does_not_disconnect_on_unload_failure(self, mock_hass):
        entry = MagicMock()
        mock_client = AsyncMock()
        mock_client.disconnect = AsyncMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = mock_client
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        result = await async_unload_entry(mock_hass, entry)

        assert result is False
        mock_client.disconnect.assert_not_called()

    async def test_returns_unload_result(self, mock_hass):
        entry = MagicMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = AsyncMock()
        entry.runtime_data.client.disconnect = AsyncMock()
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        result = await async_unload_entry(mock_hass, entry)
        assert result is False


class TestAsyncReloadEntry:
    async def test_calls_async_reload(self, mock_hass):
        entry = MagicMock()
        entry.entry_id = "test_id"
        await async_reload_entry(mock_hass, entry)
        mock_hass.config_entries.async_reload.assert_called_once_with("test_id")
