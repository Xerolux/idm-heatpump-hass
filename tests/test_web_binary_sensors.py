"""Tests for binary sensors backed by Navigator web values."""

from __future__ import annotations

import math
from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from custom_components.idm_heatpump.web_binary_sensors import (
    WEB_BINARY_VALUE_KEYS,
    normalize_web_binary_value,
    web_binary_sensor_entities,
)
from custom_components.idm_heatpump.web_data import IdmWebSensorValue, IdmWebSupplement


def _coordinator(sensor_values: dict[str, IdmWebSensorValue]) -> MagicMock:
    coordinator = MagicMock()
    coordinator.web_supplement = IdmWebSupplement(sensor_values=sensor_values)
    coordinator.last_update_success = True
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.title = "IDM"
    coordinator.model_name = "Navigator 10"
    coordinator.firmware_version = None
    coordinator.myidm_id = None
    return coordinator


def _entities_by_key(coordinator: MagicMock):
    return {entity.entity_description.key: entity for entity in web_binary_sensor_entities(coordinator)}


def test_normalizes_numeric_and_boolean_values():
    assert normalize_web_binary_value(True) is True
    assert normalize_web_binary_value(False) is False
    assert normalize_web_binary_value(1) is True
    assert normalize_web_binary_value(0.0) is False


def test_normalizes_known_text_values():
    for value in ("Ein", "AN", "aktiv", "running", "true", "Ja"):
        assert normalize_web_binary_value(value) is True
    for value in ("Aus", "inaktiv", "stopped", "false", "Nein"):
        assert normalize_web_binary_value(value) is False


def test_unknown_values_remain_unknown():
    assert normalize_web_binary_value(2) is None
    assert normalize_web_binary_value(-1) is None
    assert normalize_web_binary_value(math.nan) is None
    assert normalize_web_binary_value("Automatik") is None
    assert normalize_web_binary_value(None) is None


def test_creates_all_definitions_and_availability_tracks_values():
    entities = _entities_by_key(
        _coordinator(
            {
                "compressor_1": IdmWebSensorValue("Ein", 1.0),
                "high_pressure_error": IdmWebSensorValue("Aus", 0.0),
                "hotgas_temperature": IdmWebSensorValue("72.5°C", 72.5, "°C"),
            }
        )
    )

    assert "web_compressor_1" in entities
    assert "web_high_pressure_error" in entities
    assert len(entities) == len(WEB_BINARY_VALUE_KEYS)
    assert entities["web_compressor_1"].is_on is True
    assert entities["web_compressor_1"].available is True
    assert entities["web_high_pressure_error"].is_on is False
    # Definitions without a current value stay unavailable until web provides them.
    assert entities["web_flow_pump_on"].available is False


def test_problem_sensor_has_diagnostic_metadata():
    sensor = _entities_by_key(_coordinator({"high_pressure_error": IdmWebSensorValue("Ein", 1.0)}))[
        "web_high_pressure_error"
    ]

    assert sensor.entity_description.device_class == BinarySensorDeviceClass.PROBLEM
    assert sensor.entity_description.entity_category == EntityCategory.DIAGNOSTIC
    assert sensor.entity_description.translation_key == "web_high_pressure_error"
    assert sensor._attr_unique_id == "test_entry_web_high_pressure_error"


def test_running_sensor_has_running_device_class():
    sensor = _entities_by_key(_coordinator({"compressor_1": IdmWebSensorValue("Ein", 1.0)}))["web_compressor_1"]

    assert sensor.entity_description.device_class == BinarySensorDeviceClass.RUNNING
    assert sensor.entity_description.entity_category is None


def test_unknown_runtime_value_makes_entity_unavailable():
    coordinator = _coordinator({"compressor_1": IdmWebSensorValue("Automatik", None)})
    sensor = _entities_by_key(coordinator)["web_compressor_1"]

    assert sensor.is_on is None
    assert sensor.available is False


def test_missing_web_supplement_keeps_entities_unavailable():
    coordinator = _coordinator({})
    coordinator.web_supplement = None
    entities = web_binary_sensor_entities(coordinator)

    assert len(entities) == len(WEB_BINARY_VALUE_KEYS)
    assert all(entity.available is False for entity in entities)


def test_web_binary_available_when_modbus_update_failed():
    coordinator = _coordinator({"compressor_1": IdmWebSensorValue("Ein", 1.0)})
    coordinator.last_update_success = False
    sensor = _entities_by_key(coordinator)["web_compressor_1"]

    assert sensor.available is True
    assert sensor.is_on is True


def test_binary_keys_are_unique():
    assert len(WEB_BINARY_VALUE_KEYS) == 15


def test_binary_web_values_are_not_created_as_regular_sensors():
    from custom_components.idm_heatpump.sensor import _web_sensor_definitions

    coordinator = _coordinator(
        {
            "compressor_1": IdmWebSensorValue("Ein", 1.0),
            "high_pressure_error": IdmWebSensorValue("Aus", 0.0),
            "hotgas_temperature": IdmWebSensorValue("72.5°C", 72.5, "°C"),
        }
    )
    coordinator._registers = []

    keys = {definition.key for definition in _web_sensor_definitions(coordinator)}

    assert "compressor_1" not in keys
    assert "high_pressure_error" not in keys
    assert "hotgas_temperature" in keys


def test_camel_case_source_key_uses_normalized_translation_key():
    sensor = _entities_by_key(_coordinator({"pump_heating_circuitA": IdmWebSensorValue("Ein", 1.0)}))[
        "web_pump_heating_circuitA"
    ]

    assert sensor._attr_unique_id == "test_entry_web_pump_heating_circuitA"
    assert sensor.entity_description.translation_key == "web_pump_heating_circuit_a"
