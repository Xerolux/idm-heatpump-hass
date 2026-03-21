"""Tests for diagnostics support."""

from unittest.mock import MagicMock
from datetime import timedelta

import pytest

from custom_components.idm_heatpump.diagnostics import async_get_config_entry_diagnostics
from custom_components.idm_heatpump.const import DOMAIN


def _make_hass_with_coordinator(mock_hass, mock_config_entry):
    coord = MagicMock()
    coord.update_interval = timedelta(seconds=10)
    coord.registers_count = 42
    coord.last_update_success = True
    coord.sensor_descriptions = [1, 2, 3]
    coord.binary_sensor_descriptions = [1]
    coord.number_descriptions = [1, 2]
    coord.select_descriptions = [1, 2, 3, 4]
    coord.switch_descriptions = []

    # Use runtime_data (new architecture)
    mock_config_entry.runtime_data = MagicMock()
    mock_config_entry.runtime_data.coordinator = coord
    return coord


class TestDiagnostics:
    async def test_returns_dict(self, mock_hass, mock_config_entry):
        _make_hass_with_coordinator(mock_hass, mock_config_entry)
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        assert isinstance(result, dict)

    async def test_contains_entry_key(self, mock_hass, mock_config_entry):
        _make_hass_with_coordinator(mock_hass, mock_config_entry)
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        assert "entry" in result

    async def test_contains_data_key(self, mock_hass, mock_config_entry):
        _make_hass_with_coordinator(mock_hass, mock_config_entry)
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        assert "data" in result

    async def test_data_contains_coordinator_info(self, mock_hass, mock_config_entry):
        _make_hass_with_coordinator(mock_hass, mock_config_entry)
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        data = result["data"]
        assert data["scan_interval"] == 10.0
        assert data["registers_count"] == 42
        assert data["last_update_success"] is True
        assert data["sensor_count"] == 3
        assert data["binary_sensor_count"] == 1
        assert data["number_count"] == 2
        assert data["select_count"] == 4
        assert data["switch_count"] == 0

    async def test_sensitive_fields_redacted(self, mock_hass, mock_config_entry):
        """host and port should not appear in entry diagnostics."""
        mock_config_entry.as_dict = MagicMock(return_value={
            "data": {"host": "192.168.1.100", "port": 502, "name": "IDM"},
            "options": {},
        })
        _make_hass_with_coordinator(mock_hass, mock_config_entry)
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        entry_data = result["entry"].get("data", {})
        assert "host" not in entry_data
        assert "port" not in entry_data

    async def test_coordinator_counts_match(self, mock_hass, mock_config_entry):
        coord = _make_hass_with_coordinator(mock_hass, mock_config_entry)
        coord.sensor_descriptions = list(range(10))
        coord.switch_descriptions = [1, 2]
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        assert result["data"]["sensor_count"] == 10
        assert result["data"]["switch_count"] == 2
