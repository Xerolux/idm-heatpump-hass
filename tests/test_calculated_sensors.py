"""Tests for calculated IDM heat-pump sensors."""

from __future__ import annotations

import math
from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature

from custom_components.idm_heatpump.calculated_sensors import calculated_sensor_entities


def _coordinator(data: dict[str, object], unused: set[str] | None = None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.unused_registers = unused or set()
    coordinator.last_update_success = True
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.title = "IDM"
    coordinator.model_name = "Navigator 10"
    coordinator.firmware_version = None
    coordinator.myidm_id = None
    return coordinator


def _entities_by_key(coordinator: MagicMock):
    return {entity.entity_description.key: entity for entity in calculated_sensor_entities(coordinator)}


def test_creates_supported_calculated_sensors():
    entities = _entities_by_key(
        _coordinator(
            {
                "hp_flow_temp": 35.0,
                "hp_return_temp": 30.0,
                "heat_source_inlet_temp": 8.5,
                "heat_source_outlet_temp": 4.0,
                "dhw_temp_top": 48.0,
                "dhw_setpoint": 52.0,
            }
        )
    )

    assert entities["calculated_hp_temperature_delta"].native_value == 5.0
    assert entities["calculated_heat_source_temperature_delta"].native_value == 4.5
    assert entities["calculated_dhw_setpoint_deviation"].native_value == -4.0


def test_registers_only_sensors_with_all_sources_present():
    entities = _entities_by_key(_coordinator({"hp_flow_temp": 35.0, "hp_return_temp": 30.0}))

    assert set(entities) == {"calculated_hp_temperature_delta"}


def test_unused_source_prevents_registration():
    entities = _entities_by_key(
        _coordinator(
            {"hp_flow_temp": 35.0, "hp_return_temp": 30.0},
            unused={"hp_return_temp"},
        )
    )

    assert entities == {}


def test_invalid_value_makes_existing_sensor_unavailable():
    coordinator = _coordinator({"hp_flow_temp": 35.0, "hp_return_temp": 30.0})
    sensor = _entities_by_key(coordinator)["calculated_hp_temperature_delta"]

    coordinator.data["hp_return_temp"] = math.nan

    assert sensor.native_value is None
    assert sensor.available is False


def test_out_of_range_temperature_is_rejected():
    coordinator = _coordinator({"hp_flow_temp": 350.0, "hp_return_temp": 30.0})
    sensor = _entities_by_key(coordinator)["calculated_hp_temperature_delta"]

    assert sensor.native_value is None
    assert sensor.available is False


def test_boolean_source_is_not_treated_as_temperature():
    coordinator = _coordinator({"hp_flow_temp": True, "hp_return_temp": 30.0})
    sensor = _entities_by_key(coordinator)["calculated_hp_temperature_delta"]

    assert sensor.native_value is None


def test_entity_metadata_and_unique_id():
    sensor = _entities_by_key(
        _coordinator({"hp_flow_temp": 35.0, "hp_return_temp": 30.0})
    )["calculated_hp_temperature_delta"]

    assert sensor._attr_unique_id == "test_entry_calculated_hp_temperature_delta"
    assert sensor.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert sensor.entity_description.device_class == SensorDeviceClass.TEMPERATURE
    assert sensor.entity_description.state_class == SensorStateClass.MEASUREMENT
    assert sensor.entity_description.suggested_display_precision == 1


def test_values_are_recalculated_from_latest_snapshot():
    coordinator = _coordinator({"hp_flow_temp": 35.0, "hp_return_temp": 30.0})
    sensor = _entities_by_key(coordinator)["calculated_hp_temperature_delta"]

    assert sensor.native_value == 5.0
    coordinator.data = {"hp_flow_temp": 37.5, "hp_return_temp": 31.0}
    assert sensor.native_value == 6.5
