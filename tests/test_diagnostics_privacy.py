"""Privacy and completeness guard for the diagnostics export.

The roadmap keeps "check diagnostics for completeness and privacy" as a
recurring manual review item. This module turns it into an automated
regression guard: the export is built from a coordinator whose every private
field carries a unique marker, and the serialized result must not contain a
single one of them — while still carrying the fields support actually needs to
diagnose a plant.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from custom_components.idm_heatpump.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)

# Every value that must never appear anywhere in the export, each unique so a
# leak points straight at its source field.
PRIVATE_HOST = "192.168.178.42"
PRIVATE_WEB_HOST = "navigator.private.example"
PRIVATE_PIN = "135791"
PRIVATE_MYIDM_ID = "IDM-ABC-99887766"
PRIVATE_SERIAL = "SN-55443322"

PRIVATE_MARKERS = (
    PRIVATE_HOST,
    PRIVATE_WEB_HOST,
    PRIVATE_PIN,
    PRIVATE_MYIDM_ID,
    PRIVATE_SERIAL,
)

# Fields support relies on when triaging a report. Losing one silently would
# make diagnostics useless, so completeness is asserted alongside privacy.
REQUIRED_DATA_KEYS = (
    "scan_interval",
    "registers_count",
    "last_update_success",
    "communication",
    "model_name",
    "firmware_version",
    "versions",
    "model_info",
    "model_conflict",
    "client_diagnostics",
    "web_supplement",
    "unused_registers",
    "unsupported_registers",
)
REQUIRED_COMMUNICATION_KEYS = (
    "last_poll_success",
    "last_poll_duration_seconds",
    "consecutive_failures",
    "total_polls",
    "total_failures",
    "active_registers",
    "total_registers_in_plan",
    "polling_jitter_percent",
    "write_cooldown_seconds",
)


def _private_coordinator(entry: MagicMock) -> MagicMock:
    """Build a coordinator whose every private field carries a leak marker."""
    coord = MagicMock()
    coord.update_interval = timedelta(seconds=30)
    coord.registers_count = 120
    coord.last_update_success = False
    coord._last_poll_success = datetime(2026, 8, 17, 6, 30, tzinfo=UTC)
    coord._last_poll_duration = 4.5
    coord._consecutive_poll_failures = 3
    coord._total_poll_count = 900
    coord._total_poll_failures = 12
    coord._polling_plan_active_count = 90
    coord._polling_plan_total_count = 120
    coord._polling_jitter_percent = 5
    coord._write_cooldown_seconds = 5.0
    coord.model_name = "Navigator 10"
    coord.firmware_version = "NAV10_20.24-880-g265e09c4a"
    coord.model_info = None
    coord.unused_registers = {"hc_b_flow_temp"}
    coord.unsupported_registers = {"power_limit_hp"}
    coord.sensor_descriptions = [1, 2, 3]
    coord.binary_sensor_descriptions = [1]
    coord.number_descriptions = [1]
    coord.select_descriptions = [1]
    coord.switch_descriptions = []
    coord.data = {}

    # Web supplement: the error text embeds host and PIN the way a real client
    # error would ("cannot authenticate to http://<host>/?pin=<pin>").
    coord.web_enabled = True
    coord.web_supplement = MagicMock()
    coord.last_web_error = (
        f"IdmWebAuthenticationFailed: login rejected by http://{PRIVATE_WEB_HOST}:61220/?pin={PRIVATE_PIN}"
    )
    coord.web_value_keys = ("navigator_version", "software_version")
    coord.missing_web_core_values = ()

    # Client diagnostics: host/port keys plus a free-text transport error.
    coord.client_diagnostics = MagicMock(
        return_value={
            "host": PRIVATE_HOST,
            "port": 502,
            "slave_id": 1,
            "connected": False,
            "last_error": f"ModbusConnectionError: could not connect to {PRIVATE_HOST}:502",
            "transport": {
                "backend": "tmodbus",
                "owns_socket": True,
                "supports_shared_connection": False,
                "host": PRIVATE_HOST,
                "web_host": PRIVATE_WEB_HOST,
            },
        }
    )
    coord.model_conflict_summary = {
        "selected_family": "navigator_10",
        "stored_family": "navigator_10",
        "web_variant": "nav10",
        "software_version": "NAV10_20.24-880-g265e09c4a",
        "manual_override": "auto",
        "conflict": False,
        # A future summary field must not become a leak channel unnoticed.
        "myidm_id": PRIVATE_MYIDM_ID,
    }

    entry.data = {
        "host": PRIVATE_HOST,
        "port": 502,
        "slave_id": 1,
        "web_host": PRIVATE_WEB_HOST,
        "web_pin": PRIVATE_PIN,
        "name": "IDM Wärmepumpe",
    }
    entry.as_dict = MagicMock(
        return_value={
            "entry_id": "test_entry_id",
            "title": "IDM Wärmepumpe",
            "data": dict(entry.data),
            "options": {"scan_interval": 30},
        }
    )
    entry.runtime_data = MagicMock()
    entry.runtime_data.coordinator = coord
    return coord


class TestDiagnosticsPrivacy:
    async def test_no_private_value_reaches_the_export(self, mock_hass, mock_config_entry):
        _private_coordinator(mock_config_entry)

        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)

        serialized = json.dumps(result, default=str)
        for marker in PRIVATE_MARKERS:
            assert marker not in serialized, f"diagnostics export leaked {marker}"

    async def test_free_text_errors_are_reduced_to_a_category(self, mock_hass, mock_config_entry):
        """Error messages stay useful without carrying the connection details."""
        _private_coordinator(mock_config_entry)

        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)

        assert result["data"]["client_diagnostics"]["last_error"] == "ModbusConnectionError"
        assert result["data"]["web_supplement"]["last_error"] == "IdmWebAuthenticationFailed"

    async def test_export_stays_complete_for_support(self, mock_hass, mock_config_entry):
        """Redaction must not strip the fields a support triage depends on."""
        _private_coordinator(mock_config_entry)

        result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)

        data = result["data"]
        for key in REQUIRED_DATA_KEYS:
            assert key in data, f"diagnostics lost the {key} section"
        for key in REQUIRED_COMMUNICATION_KEYS:
            assert key in data["communication"], f"diagnostics lost communication.{key}"
        # Non-private transport facts must survive redaction: they are the
        # reason the section exists.
        assert result["data"]["client_diagnostics"]["transport"]["backend"] == "tmodbus"
        assert result["data"]["client_diagnostics"]["transport"]["owns_socket"] is True

    def test_redaction_list_covers_every_private_config_key(self):
        """Guard the redaction list itself against silent shrinkage."""
        assert {"host", "port", "slave_id", "web_host", "web_pin"} <= TO_REDACT
        assert {"myidm_id", "serial_number", "serial"} <= TO_REDACT
