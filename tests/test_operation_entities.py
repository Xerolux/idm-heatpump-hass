"""Tests for Home Assistant operation-analysis entities."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump.coordinator import IdmCoordinator
from custom_components.idm_heatpump.operation_entities import (
    operation_sensor_entities,
    short_cycle_binary_entities,
)


def _coordinator() -> MagicMock:
    coordinator = MagicMock(spec=IdmCoordinator)
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "entry"
    coordinator.config_entry.title = "IDM"
    coordinator.model_name = "Navigator 10"
    coordinator.firmware_version = None
    coordinator.myidm_id = None
    coordinator.last_update_success = True
    coordinator._device_info_cache = None
    return coordinator


def _analysis() -> MagicMock:
    analysis = MagicMock()
    analysis.supports_compressor = True
    analysis.supports_operating_mode = True
    analysis.total_compressor_starts = 12
    analysis.total_defrost_starts = 3
    analysis.completed_cycle_durations = [600.0, 1200.0]
    analysis.last_compressor_start = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    analysis.last_defrost_start = datetime(2026, 7, 20, 7, 0, tzinfo=UTC)
    analysis.last_cycle_duration = 600.0
    analysis.last_cycle_ended = datetime(2026, 7, 20, 8, 10, tzinfo=UTC)
    analysis.short_cycle_minutes = 15
    analysis.last_cycle_was_short = True
    analysis.compressor_starts_today.return_value = 4
    analysis.compressor_starts_last_hours.side_effect = lambda hours: {2: 2, 4: 3}[hours]
    analysis.current_cycle_minutes.return_value = 5.0
    analysis.average_cycle_minutes.return_value = 15.0
    analysis.defrost_starts_today.return_value = 1
    analysis.minutes_since_last_defrost.return_value = 60.0
    analysis.operating_share.side_effect = {
        "heating": 50.0,
        "dhw": 25.0,
        "cooling": 15.0,
        "defrost": 10.0,
    }.get
    return analysis


def _by_key(entities):
    return {entity.entity_description.key: entity for entity in entities}


def test_creates_compressor_and_mode_entities() -> None:
    entities = _by_key(operation_sensor_entities(_coordinator(), _analysis()))

    assert entities["analysis_heat_pump_cycles_recorded"].native_value == 12
    assert entities["analysis_heat_pump_cycles_today"].native_value == 4
    assert entities["analysis_defrost_starts_today"].native_value == 1
    assert entities["analysis_operating_share_heating"].native_value == 50.0


def test_total_start_sensor_is_total_increasing() -> None:
    sensor = _by_key(operation_sensor_entities(_coordinator(), _analysis()))["analysis_heat_pump_cycles_recorded"]

    assert sensor.entity_description.state_class == SensorStateClass.TOTAL_INCREASING
    assert sensor._attr_unique_id == "entry_analysis_heat_pump_cycles_recorded"


def test_duration_and_timestamp_metadata() -> None:
    entities = _by_key(operation_sensor_entities(_coordinator(), _analysis()))

    assert entities["analysis_current_cycle_duration"].entity_description.device_class == SensorDeviceClass.DURATION
    assert entities["analysis_last_compressor_start"].entity_description.device_class == SensorDeviceClass.TIMESTAMP


def test_advanced_window_and_share_sensors_are_disabled_by_default() -> None:
    entities = _by_key(operation_sensor_entities(_coordinator(), _analysis()))

    assert entities["analysis_heat_pump_cycles_2h"].entity_description.entity_registry_enabled_default is False
    assert entities["analysis_operating_share_defrost"].entity_description.entity_registry_enabled_default is False


def test_source_capabilities_filter_entities() -> None:
    analysis = _analysis()
    analysis.supports_compressor = False
    entities = _by_key(operation_sensor_entities(_coordinator(), analysis))

    assert all("compressor" not in key and "cycle" not in key for key in entities)
    assert "analysis_defrost_starts_today" in entities


def test_short_cycle_warning_metadata_and_attributes() -> None:
    sensor = short_cycle_binary_entities(_coordinator(), _analysis())[0]

    assert sensor.is_on is True
    assert sensor.entity_description.device_class == BinarySensorDeviceClass.PROBLEM
    assert sensor._attr_unique_id == "entry_analysis_last_cycle_short"
    assert sensor.extra_state_attributes["threshold_minutes"] == 15
    assert sensor.extra_state_attributes["last_cycle_minutes"] == 10.0


def test_no_entities_without_analysis() -> None:
    assert operation_sensor_entities(_coordinator(), None) == []
    assert short_cycle_binary_entities(_coordinator(), None) == []


def test_no_warning_without_verified_compressor_source() -> None:
    analysis = _analysis()
    analysis.supports_compressor = False

    assert short_cycle_binary_entities(_coordinator(), analysis) == []


def test_register_fixture_documents_verified_sources() -> None:
    compressor = RegisterDef(
        address=1100,
        datatype=DataType.UCHAR,
        name="compressor_status_1",
        binary=True,
    )
    mode = RegisterDef(
        address=1090,
        datatype=DataType.UCHAR,
        name="hp_operating_mode",
    )

    assert compressor.binary is True
    assert mode.address == 1090
