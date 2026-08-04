from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from idm_heatpump import IdmModelInfo

from custom_components.idm_heatpump.diagnostics import async_get_config_entry_diagnostics


def _make_hass_with_coordinator(mock_hass, mock_config_entry):
    coord = MagicMock()
    coord.update_interval = timedelta(seconds=10)
    coord.registers_count = 42
    coord.last_update_success = True
    coord._last_poll_success = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    coord._last_poll_duration = 0.25
    coord._consecutive_poll_failures = 0
    coord._total_poll_count = 12
    coord._total_poll_failures = 1
    coord._polling_plan_active_count = 40
    coord._polling_plan_total_count = 42
    coord._polling_jitter_percent = 10
    coord._write_cooldown_seconds = 30.0
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
    coord.model_conflict_summary = {
        "selected_family": "navigator_10",
        "stored_family": "navigator_10",
        "web_variant": "nav10",
        "software_version": "2.34",
        "manual_override": "auto",
        "conflict": False,
    }
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
        assert data["communication"]["last_poll_duration_seconds"] == 0.25
        assert data["communication"]["polling_jitter_percent"] == 10
        assert data["communication"]["write_cooldown_seconds"] == 30.0
        assert data["model_name"] == "Navigator 10"
        assert data["firmware_version"] == "2.34"
        assert data["versions"]["integration"] == "0.5.0"
        assert isinstance(data["versions"]["idm_heatpump_api"], str)
        assert isinstance(data["versions"]["modbus_connection"], str)
        assert isinstance(data["versions"]["tmodbus"], str)
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
                "data": {
                    "host": "192.168.1.100",
                    "port": 502,
                    "slave_id": 1,
                    "web_host": "192.168.1.101",
                    "web_pin": "1234",
                    "name": "IDM",
                },
                "options": {
                    "host": "192.168.1.100",
                    "port": 502,
                    "slave_id": 1,
                    "web_host": "192.168.1.101",
                    "web_pin": "1234",
                },
            }
        )
        _make_hass_with_coordinator(mock_hass, mock_config_entry)
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        entry_data = result["entry"].get("data", {})
        entry_options = result["entry"].get("options", {})
        assert "host" not in entry_data
        assert "port" not in entry_data
        assert "slave_id" not in entry_data
        assert "web_host" not in entry_data
        assert "web_pin" not in entry_data
        assert "host" not in entry_options
        assert "port" not in entry_options
        assert "slave_id" not in entry_options
        assert "web_host" not in entry_options
        assert "web_pin" not in entry_options

    async def test_web_error_diagnostics_do_not_expose_connection_details(self, mock_hass, mock_config_entry):
        coord = _make_hass_with_coordinator(mock_hass, mock_config_entry)
        coord.last_web_error = "ClientConnectorError: Cannot connect to ws://192.168.1.101:61220/?auth_code=1234"

        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)

        assert result["data"]["web_supplement"]["last_error"] == "ClientConnectorError"

        coord.last_web_error = "ws://192.168.1.101:61220/?auth_code=1234"
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        assert result["data"]["web_supplement"]["last_error"] == "Web supplement error"

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

    async def test_web_only_null_update_interval(self, mock_hass, mock_config_entry):
        coord = _make_hass_with_coordinator(mock_hass, mock_config_entry)
        coord.update_interval = None
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        assert result["data"]["scan_interval"] is None

    async def test_model_conflict_block_present_and_structured(self, mock_hass, mock_config_entry):
        _make_hass_with_coordinator(mock_hass, mock_config_entry)
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        block = result["data"]["model_conflict"]
        assert set(block) == {
            "selected_family",
            "stored_family",
            "web_variant",
            "software_version",
            "manual_override",
            "conflict",
        }
        assert block["selected_family"] == "navigator_10"
        assert block["web_variant"] == "nav10"
        assert block["manual_override"] == "auto"
        assert block["conflict"] is False

    async def test_model_conflict_block_reflects_conflict_and_override(self, mock_hass, mock_config_entry):
        coord = _make_hass_with_coordinator(mock_hass, mock_config_entry)
        coord.model_conflict_summary = {
            "selected_family": "navigator_10",
            "stored_family": "navigator_20",
            "web_variant": "nav20",
            "software_version": "NAV10.2",
            "manual_override": "navigator_10",
            "conflict": True,
        }
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        block = result["data"]["model_conflict"]
        assert block["conflict"] is True
        assert block["stored_family"] == "navigator_20"
        assert block["manual_override"] == "navigator_10"

    async def test_model_conflict_block_redacts_private_data(self, mock_hass, mock_config_entry):
        """No host/PIN/serial/myIDM identifier may appear in diagnostics."""
        mock_config_entry.as_dict = MagicMock(
            return_value={
                "data": {
                    "host": "192.168.1.100",
                    "port": 502,
                    "slave_id": 1,
                    "web_host": "192.168.1.101",
                    "web_pin": "1234",
                    "myidm_id": "IDM-SECRET-123",
                    "serial_number": "SN-456",
                },
            }
        )
        _make_hass_with_coordinator(mock_hass, mock_config_entry)
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        entry_data = result["entry"].get("data", {})
        assert "host" not in entry_data
        assert "web_pin" not in entry_data
        assert "myidm_id" not in entry_data
        assert "serial_number" not in entry_data


class TestControllerStatsCrossReference:
    """The diagnostics export emits a cross-reference between library
    register names and the controller's internal syscount keys / KNX
    object numbers. Lets users correlate HA readings with on-device
    counters without pulling the SD card."""

    async def test_block_present_even_when_data_empty(self, mock_hass, mock_config_entry):
        _make_hass_with_coordinator(mock_hass, mock_config_entry)
        # Default MagicMock.data is a MagicMock that iterates as empty.
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        assert "controller_stats_cross_reference" in result["data"]
        assert result["data"]["controller_stats_cross_reference"] == {}

    async def test_emits_only_registers_present_in_data(self, mock_hass, mock_config_entry):
        coord = _make_hass_with_coordinator(mock_hass, mock_config_entry)
        coord.data = {"energy_heating": 27198.71, "pv_surplus": 7.56, "unrelated_register": 0}
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        block = result["data"]["controller_stats_cross_reference"]
        assert set(block.keys()) == {"energy_heating", "pv_surplus"}
        # Unrelated registers are omitted.
        assert "unrelated_register" not in block

    async def test_row_contains_syscount_key_for_energy_register(self, mock_hass, mock_config_entry):
        coord = _make_hass_with_coordinator(mock_hass, mock_config_entry)
        coord.data = {"energy_heating": 27198.71}
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        row = result["data"]["controller_stats_cross_reference"]["energy_heating"]
        assert row["syscount_key"] == "ZQHPH"
        assert row["internal_stats_id"] == 477
        assert row["knx_object"] == 400
        assert "Heizen" in row["label"] or "Wärmemenge" in row["label"]

    async def test_row_handles_register_without_syscount_key(self, mock_hass, mock_config_entry):
        """pv_surplus has no syscount key but a KNX object number."""
        coord = _make_hass_with_coordinator(mock_hass, mock_config_entry)
        coord.data = {"pv_surplus": 7.56}
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        row = result["data"]["controller_stats_cross_reference"]["pv_surplus"]
        assert row["syscount_key"] is None
        assert row["internal_stats_id"] == 495
        assert row["knx_object"] == 995

    async def test_no_register_values_leak_into_cross_reference(self, mock_hass, mock_config_entry):
        """The cross-reference must emit ONLY labels/keys, never the
        actual sensor value. Values live elsewhere in diagnostics if at all."""
        coord = _make_hass_with_coordinator(mock_hass, mock_config_entry)
        coord.data = {"energy_heating": 27198.71, "pv_surplus": 7.56}
        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
        block = result["data"]["controller_stats_cross_reference"]
        # Each row has exactly the four label fields - nothing else.
        for row in block.values():
            assert set(row.keys()) == {"syscount_key", "internal_stats_id", "knx_object", "label"}
            assert 27198.71 not in row.values()
            assert 7.56 not in row.values()
