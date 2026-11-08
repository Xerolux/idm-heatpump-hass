"""Consent gates and complete firmware-entity removal."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from test_firmware_observations import make_firmware

from custom_components.idm_heatpump.const import (
    CONF_FIRMWARE_CHECK,
    CONF_FIRMWARE_POLICY,
    CONF_TELEMETRY,
    CONF_TELEMETRY_CONSENT_AT,
    CONF_TELEMETRY_POLICY,
)
from custom_components.idm_heatpump.firmware_observations import FIRMWARE_POLICY
from custom_components.idm_heatpump.telemetry import TELEMETRY_POLICY
from custom_components.idm_heatpump.telemetry_entities import (
    IdmTelemetryFirmwareSensor,
    IdmTelemetryStatusSensor,
    firmware_sensor_entities,
    telemetry_status_sensor_entities,
)


def test_sensor_is_absent_and_only_its_old_registry_entry_is_removed_without_consent():
    entry = MagicMock(entry_id="test-entry", options={})
    registry = MagicMock()
    registry.async_get_entity_id.return_value = "sensor.idm_latest_reported_firmware"
    with patch("custom_components.idm_heatpump.telemetry_entities.er.async_get", return_value=registry):
        assert firmware_sensor_entities(MagicMock(), entry, MagicMock()) == []
    registry.async_remove.assert_called_once_with("sensor.idm_latest_reported_firmware")


def test_telemetry_consent_alone_never_creates_firmware_sensor():
    entry = MagicMock(entry_id="test-entry", options={"telemetry": True, "telemetry_policy": "idm-telemetry-v3"})
    registry = MagicMock()
    with patch("custom_components.idm_heatpump.telemetry_entities.er.async_get", return_value=registry):
        assert firmware_sensor_entities(MagicMock(), entry, MagicMock()) == []


def test_enabled_sensor_uses_only_the_opt_in_telemetry_result():
    telemetry, entry, coordinator = make_firmware()
    coordinator.config_entry = entry
    entry.runtime_data = SimpleNamespace(firmware=telemetry)
    entry.options[CONF_FIRMWARE_POLICY] = FIRMWARE_POLICY
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
    entry.runtime_data.firmware = None
    assert sensor.extra_state_attributes == {"status": "not_ready"}


async def test_disabling_removes_the_registry_entity_immediately():
    telemetry, entry, coordinator = make_firmware()
    coordinator.config_entry = entry
    entry.runtime_data = SimpleNamespace(firmware=telemetry)
    sensor = IdmTelemetryFirmwareSensor(coordinator)
    sensor.entity_id = "sensor.idm_latest_reported_firmware"
    registry = MagicMock(entities={sensor.entity_id: MagicMock()})
    entry.options[CONF_FIRMWARE_CHECK] = False
    with patch("custom_components.idm_heatpump.telemetry_entities.er.async_get", return_value=registry):
        await sensor._async_options_updated(MagicMock(), entry)
    registry.async_remove.assert_called_once_with(sensor.entity_id)
    registry.entities = {}
    sensor.async_remove = AsyncMock()
    with patch("custom_components.idm_heatpump.telemetry_entities.er.async_get", return_value=registry):
        await sensor._async_options_updated(MagicMock(), entry)
    sensor.async_remove.assert_awaited_once()


def test_valid_catalog_without_matching_reports_is_unknown_with_explanation():
    telemetry, entry, coordinator = make_firmware()
    coordinator.config_entry = entry
    entry.runtime_data = SimpleNamespace(firmware=telemetry)
    sensor = IdmTelemetryFirmwareSensor(coordinator)
    telemetry.firmware_result = {
        "status": "no_matching_observations",
        "model_scope": "controller_series_only",
        "latest_firmware": None,
    }
    assert sensor.available
    assert sensor.native_value is None
    assert sensor.extra_state_attributes["status"] == "no_matching_observations"


def _make_status_setup():
    from test_telemetry import make_telemetry

    telemetry, entry, coordinator = make_telemetry()
    coordinator.config_entry = entry
    entry.runtime_data = SimpleNamespace(telemetry=telemetry)
    entry.options[CONF_TELEMETRY_POLICY] = TELEMETRY_POLICY
    entry.options[CONF_TELEMETRY_CONSENT_AT] = "2026-11-05T10:00:00+00:00"
    return telemetry, entry, coordinator


def test_status_sensor_is_absent_without_telemetry_consent():
    entry = MagicMock(entry_id="test-entry", options={"firmware_check": True})
    registry = MagicMock()
    registry.async_get_entity_id.return_value = "sensor.idm_telemetry_report_status"
    with patch("custom_components.idm_heatpump.telemetry_entities.er.async_get", return_value=registry):
        assert telemetry_status_sensor_entities(MagicMock(), entry, MagicMock()) == []
    registry.async_remove.assert_called_once_with("sensor.idm_telemetry_report_status")


def test_status_sensor_follows_local_delivery_without_telemetry_contact():
    telemetry, entry, coordinator = _make_status_setup()
    sensors = telemetry_status_sensor_entities(MagicMock(), entry, coordinator)
    assert len(sensors) == 1
    sensor = sensors[0]
    assert sensor.available
    assert sensor.native_value == "not_sent"
    telemetry._record_result("accepted")
    assert sensor.native_value == "accepted"
    attributes = sensor.extra_state_attributes
    assert attributes["failed_attempts"] == 0
    assert attributes["pending_report"] is False
    assert "not part of the transmitted data" in attributes["availability_note"]
    entry.runtime_data.telemetry = None
    assert not sensor.available
    assert sensor.extra_state_attributes == {"status": "not_ready"}


async def test_disabling_telemetry_removes_the_status_entity_immediately():
    _, entry, coordinator = _make_status_setup()
    sensor = IdmTelemetryStatusSensor(coordinator)
    sensor.entity_id = "sensor.idm_telemetry_report_status"
    registry = MagicMock(entities={sensor.entity_id: MagicMock()})
    entry.options[CONF_TELEMETRY] = False
    with patch("custom_components.idm_heatpump.telemetry_entities.er.async_get", return_value=registry):
        await sensor._async_options_updated(MagicMock(), entry)
    registry.async_remove.assert_called_once_with(sensor.entity_id)


async def test_status_sensor_subscribes_to_delivery_changes():
    telemetry, _, coordinator = _make_status_setup()
    sensor = IdmTelemetryStatusSensor(coordinator)
    sensor.async_write_ha_state = MagicMock()
    sensor.hass = MagicMock()
    await sensor.async_added_to_hass()
    telemetry._record_result("rejected")
    sensor.async_write_ha_state.assert_called_once()
    assert sensor.native_value == "rejected"
