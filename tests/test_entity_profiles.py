"""Tests for the default IDM entity presentation profiles."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import EntityCategory
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump.adapter_descriptions import make_sensor_description
from custom_components.idm_heatpump.adapter_metadata import SENSOR_METADATA


def _description(name: str, unit: str | None = None, state_class: str | None = None):
    register = RegisterDef(
        address=100,
        datatype=DataType.FLOAT,
        name=name,
        unit=unit,
        state_class=state_class,
    )
    return make_sensor_description(register, SENSOR_METADATA[name], name)


def test_core_temperature_is_not_diagnostic():
    description = _description("hp_flow_temp", "°C")

    assert description.entity_category is None
    assert description.device_class == SensorDeviceClass.TEMPERATURE
    assert description.state_class == SensorStateClass.MEASUREMENT


def test_core_energy_is_not_diagnostic():
    description = _description("energy_total", "kWh", "total_increasing")

    assert description.entity_category is None
    assert description.device_class == SensorDeviceClass.ENERGY
    assert description.state_class == SensorStateClass.TOTAL_INCREASING


def test_internal_message_remains_diagnostic():
    description = _description("internal_message")

    assert description.entity_category == EntityCategory.DIAGNOSTIC


def test_technical_pump_signal_remains_disabled_diagnostic():
    description = _description("heat_sink_charging_pump_signal", "%")

    assert description.entity_category == EntityCategory.DIAGNOSTIC
    assert description.entity_registry_enabled_default is False


def test_expected_core_keys_are_explicitly_profiled():
    expected = {
        "outdoor_temp",
        "storage_temp",
        "dhw_temp_bottom",
        "dhw_temp_top",
        "hp_flow_temp",
        "hp_return_temp",
        "heat_source_inlet_temp",
        "heat_source_outlet_temp",
        "energy_heating",
        "energy_dhw",
        "energy_cooling",
        "energy_total",
    }

    assert expected <= SENSOR_METADATA.keys()
    assert all(SENSOR_METADATA[key].get("entity_category") is None for key in expected)
