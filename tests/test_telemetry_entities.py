"""Consent gates and complete firmware-entity removal."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from test_telemetry import make_telemetry

from custom_components.idm_heatpump.const import CONF_TELEMETRY, CONF_TELEMETRY_POLICY
from custom_components.idm_heatpump.telemetry import TELEMETRY_POLICY
from custom_components.idm_heatpump.telemetry_entities import IdmTelemetryFirmwareSensor, firmware_sensor_entities


def test_sensor_is_absent_and_only_its_old_registry_entry_is_removed_without_consent():
    entry = MagicMock(entry_id="test-entry", options={})
    registry = MagicMock()
    registry.async_get_entity_id.return_value = "sensor.idm_latest_reported_firmware"
    with patch("custom_components.idm_heatpump.telemetry_entities.er.async_get", return_value=registry):
        assert firmware_sensor_entities(MagicMock(), entry, MagicMock()) == []
    registry.async_remove.assert_called_once_with("sensor.idm_latest_reported_firmware")


def test_enabled_sensor_uses_only_the_opt_in_telemetry_result():
    telemetry, entry, coordinator = make_telemetry()
    coordinator.config_entry = entry
    entry.runtime_data = SimpleNamespace(telemetry=telemetry)
    entry.options[CONF_TELEMETRY_POLICY] = TELEMETRY_POLICY
    sensors = firmware_sensor_entities(MagicMock(), entry, coordinator)
    assert len(sensors) == 1
    sensor = sensors[0]
    assert not sensor.available and sensor.native_value is None
    telemetry.firmware_result = {
        "latest_firmware": "T_NAV10_20.24-1581",
        "newer_observed": True,
        "source": "community_telemetry",
    }
    assert sensor.available and sensor.native_value == "T_NAV10_20.24-1581"
    assert sensor.extra_state_attributes["newer_observed"] is True
    entry.runtime_data.telemetry = None
    assert sensor.extra_state_attributes == {"status": "not_ready"}


async def test_disabling_removes_the_registry_entity_immediately():
    telemetry, entry, coordinator = make_telemetry()
    coordinator.config_entry = entry
    entry.runtime_data = SimpleNamespace(telemetry=telemetry)
    sensor = IdmTelemetryFirmwareSensor(coordinator)
    sensor.entity_id = "sensor.idm_latest_reported_firmware"
    registry = MagicMock(entities={sensor.entity_id: MagicMock()})
    entry.options[CONF_TELEMETRY] = False
    with patch("custom_components.idm_heatpump.telemetry_entities.er.async_get", return_value=registry):
        await sensor._async_options_updated(MagicMock(), entry)
    registry.async_remove.assert_called_once_with(sensor.entity_id)
    registry.entities = {}
    sensor.async_remove = AsyncMock()
    with patch("custom_components.idm_heatpump.telemetry_entities.er.async_get", return_value=registry):
        await sensor._async_options_updated(MagicMock(), entry)
    sensor.async_remove.assert_awaited_once()


def test_valid_catalog_without_matching_reports_is_unknown_with_explanation():
    telemetry, entry, coordinator = make_telemetry()
    coordinator.config_entry = entry
    entry.runtime_data = SimpleNamespace(telemetry=telemetry)
    sensor = IdmTelemetryFirmwareSensor(coordinator)
    telemetry.firmware_result = {
        "status": "no_matching_observations",
        "model_scope": "controller_series_only",
        "latest_firmware": None,
    }
    assert sensor.available
    assert sensor.native_value is None
    assert sensor.extra_state_attributes["status"] == "no_matching_observations"
