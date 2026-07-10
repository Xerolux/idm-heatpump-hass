from datetime import timedelta
from unittest.mock import MagicMock

from idm_heatpump import IdmModelInfo

from custom_components.idm_heatpump.diagnostics import async_get_config_entry_diagnostics


def _make_hass_with_coordinator(mock_hass, mock_config_entry):
    coord = MagicMock()
    coord.update_interval = timedelta(seconds=10)
    coord.registers_count = 42
    coord.last_update_success = True
    coord.model_name = "Navigator 10"
    coord.firmware_version = "2.34"
    coord.web_enabled = True
    coord.web_supplement = MagicMock()
    coord.last_web_error = None
    coord.web_value_keys = ("navigator_version", "software_version")
    coord.missing_web_core_values = ("heatpump_model",)
    coord.model_info = IdmModelInfo(
        model_name="Navigator 10",
        active_heating_circuits=["A", "B"],
        zone_modules=2,
        has_solar=True,
        has_isc=False,
        has_pv=True,
        has_cascade=False,
        features={"heating_circuits", "zone_modules", "solar", "pv"},
    )
    coord.unused_registers = {"room_9_temperature"}
    coord.unsupported_registers = {"power_limit_hp"}
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
        assert data["model_name"] == "Navigator 10"
        assert data["firmware_version"] == "2.34"
        assert data["versions"]["integration"] == "0.5.0"
        assert isinstance(data["versions"]["idm_heatpump_api"], str)
        assert isinstance(data["versions"]["pymodbus"], str)
        assert data["web_supplement"] == {
            "enabled": True,
            "available": True,
            "last_error": None,
            "available_values": ["navigator_version", "software_version"],
            "missing_core_values": ["heatpump_model"],
        }
        assert data["sensor_count"] == 3
        assert data["binary_sensor_count"] == 1
        assert data["number_count"] == 2
        assert data["select_count"] == 4
        assert data["switch_count"] == 0

    async def test_sensitive_fields_redacted(self, mock_hass, mock_config_entry):
        """Network fields should not appear in entry diagnostics."""
        mock_config_entry.as_dict = MagicMock(
            return_value={
                "data": {"host": "192.168.1.100", "port": 502, "slave_id": 1, "name": "IDM"},
                "options": {"host": "192.168.1.100", "port": 502, "slave_id": 1},
            }
        )
        _make_hass_with_coordinator(mock_hass, mock_config_entry)
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        entry_data = result["entry"].get("data", {})
        entry_options = result["entry"].get("options", {})
        assert "host" not in entry_data
        assert "port" not in entry_data
        assert "slave_id" not in entry_data
        assert "host" not in entry_options
        assert "port" not in entry_options
        assert "slave_id" not in entry_options

    async def test_contains_detected_model_details(self, mock_hass, mock_config_entry):
        _make_hass_with_coordinator(mock_hass, mock_config_entry)
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        model_info = result["data"]["model_info"]
        assert model_info == {
            "detected": True,
            "active_heating_circuits": ["A", "B"],
            "zone_modules": 2,
            "features": ["heating_circuits", "pv", "solar", "zone_modules"],
            "capabilities": {
                "solar": True,
                "isc": False,
                "pv": True,
                "cascade": False,
            },
        }
        assert result["data"]["unused_registers"] == ["room_9_temperature"]
        assert result["data"]["unsupported_registers"] == ["power_limit_hp"]

    async def test_handles_missing_model_info(self, mock_hass, mock_config_entry):
        coord = _make_hass_with_coordinator(mock_hass, mock_config_entry)
        coord.model_info = None
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        assert result["data"]["model_info"] == {
            "detected": False,
            "active_heating_circuits": [],
            "zone_modules": 0,
            "features": [],
            "capabilities": {},
        }

    async def test_coordinator_counts_match(self, mock_hass, mock_config_entry):
        coord = _make_hass_with_coordinator(mock_hass, mock_config_entry)
        coord.sensor_descriptions = list(range(10))
        coord.switch_descriptions = [1, 2]
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        assert result["data"]["sensor_count"] == 10
        assert result["data"]["switch_count"] == 2
