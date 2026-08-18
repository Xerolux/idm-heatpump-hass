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

    # BL-003: source is present and finite, so the sensor stays available and
    # reports 'unknown' rather than the out-of-range delta.
    assert sensor.native_value is None
    assert sensor.available is True


def test_boolean_source_is_not_treated_as_temperature():
    coordinator = _coordinator({"hp_flow_temp": True, "hp_return_temp": 30.0})
    sensor = _entities_by_key(coordinator)["calculated_hp_temperature_delta"]

    assert sensor.native_value is None


def test_entity_metadata_and_unique_id():
    sensor = _entities_by_key(_coordinator({"hp_flow_temp": 35.0, "hp_return_temp": 30.0}))[
        "calculated_hp_temperature_delta"
    ]

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


def test_cop_is_thermal_over_electric_when_both_positive():
    coordinator = _coordinator(
        {
            "power_consumption_hp": 2.0,
            "thermal_power_flow_sensor": 8.0,
        }
    )
    sensor = _entities_by_key(coordinator)["calculated_cop"]

    assert sensor.native_value == 4.0
    assert sensor.available is True


def test_cop_suppressed_when_heat_pump_is_idle():
    """Issue #135 / BL-003: P_el = 0 (standby) yields state 'unknown', never
    division-by-zero. The sensor stays available (sources present) and reports
    no value while the heat pump is idle."""
    coordinator = _coordinator(
        {
            "power_consumption_hp": 0.0,
            "thermal_power_flow_sensor": 0.0,
        }
    )
    sensor = _entities_by_key(coordinator)["calculated_cop"]

    assert sensor.native_value is None
    assert sensor.available is True


def test_cop_suppressed_when_only_one_source_is_zero():
    coordinator = _coordinator(
        {
            "power_consumption_hp": 2.0,
            "thermal_power_flow_sensor": 0.0,
        }
    )
    sensor = _entities_by_key(coordinator)["calculated_cop"]

    assert sensor.native_value is None
    assert sensor.available is True


def test_cop_suppressed_below_meaningful_power_threshold():
    """Standby/commissioning band (<50 W) must not produce a misleading high COP."""
    coordinator = _coordinator(
        {
            "power_consumption_hp": 0.02,
            "thermal_power_flow_sensor": 0.1,
        }
    )
    sensor = _entities_by_key(coordinator)["calculated_cop"]

    assert sensor.native_value is None


def test_cop_handles_missing_and_nan_sources():
    # Missing source values -> unavailable
    coordinator = _coordinator({})
    assert "calculated_cop" not in _entities_by_key(coordinator)

    # NaN sentinel (unused register) -> treated as missing
    nan_coordinator = _coordinator(
        {
            "power_consumption_hp": math.nan,
            "thermal_power_flow_sensor": 1.0,
        }
    )
    sensor = _entities_by_key(nan_coordinator)["calculated_cop"]
    assert sensor.native_value is None
    assert sensor.available is False


def test_cop_entity_is_dimensionless():
    sensor = _entities_by_key(
        _coordinator(
            {
                "power_consumption_hp": 2.0,
                "thermal_power_flow_sensor": 8.0,
            }
        )
    )["calculated_cop"]

    assert sensor.entity_description.native_unit_of_measurement is None
    assert sensor.entity_description.device_class is None
    assert sensor.entity_description.state_class == SensorStateClass.MEASUREMENT
    assert sensor.entity_description.suggested_display_precision == 2
    assert sensor._attr_unique_id == "test_entry_calculated_cop"


def test_cop_not_registered_when_source_registers_unused():
    """If the installation reports a COP source register as unused, hide the sensor."""
    coordinator = _coordinator(
        {
            "power_consumption_hp": 2.0,
            "thermal_power_flow_sensor": 8.0,
        },
        unused={"thermal_power_flow_sensor"},
    )

    assert "calculated_cop" not in _entities_by_key(coordinator)


def _flow_deviation_key(circuit: str) -> str:
    return f"calculated_hc_{circuit}_flow_deviation"


def test_flow_deviation_is_actual_minus_requested_setpoint():
    """Positive = the circuit runs above the flow setpoint it was asked for."""
    coordinator = _coordinator({"hc_a_flow_temp": 34.5, "hc_a_setpoint_flow_temp": 32.0})

    sensor = _entities_by_key(coordinator)[_flow_deviation_key("a")]

    assert sensor.native_value == 2.5
    assert sensor.available is True


def test_flow_deviation_is_negative_when_the_circuit_falls_short():
    coordinator = _coordinator({"hc_b_flow_temp": 28.0, "hc_b_setpoint_flow_temp": 32.0})

    sensor = _entities_by_key(coordinator)[_flow_deviation_key("b")]

    assert sensor.native_value == -4.0


def test_flow_deviation_created_for_every_configured_circuit_only():
    """Registers exist only for configured circuits, so only those get a sensor."""
    coordinator = _coordinator(
        {
            "hc_a_flow_temp": 34.0,
            "hc_a_setpoint_flow_temp": 32.0,
            "hc_c_flow_temp": 30.0,
            "hc_c_setpoint_flow_temp": 30.0,
        }
    )

    keys = set(_entities_by_key(coordinator))

    assert _flow_deviation_key("a") in keys
    assert _flow_deviation_key("c") in keys
    assert _flow_deviation_key("b") not in keys


def test_flow_deviation_needs_both_source_registers():
    coordinator = _coordinator({"hc_a_flow_temp": 34.0})

    assert _flow_deviation_key("a") not in _entities_by_key(coordinator)


def test_flow_deviation_survives_a_restart_while_the_circuit_is_idle():
    """An idle circuit reports the 0.0 sentinel; the entity must still exist.

    Creating it only when the plant happens to be running would make the
    entity's existence depend on the moment Home Assistant restarts.
    """
    coordinator = _coordinator(
        {"hc_a_flow_temp": 0.0, "hc_a_setpoint_flow_temp": 0.0},
        unused={"hc_a_flow_temp", "hc_a_setpoint_flow_temp"},
    )

    sensor = _entities_by_key(coordinator)[_flow_deviation_key("a")]

    assert sensor.available is False
    assert sensor.native_value is None


def test_flow_deviation_becomes_available_once_the_circuit_runs():
    coordinator = _coordinator(
        {"hc_a_flow_temp": 0.0, "hc_a_setpoint_flow_temp": 0.0},
        unused={"hc_a_flow_temp", "hc_a_setpoint_flow_temp"},
    )
    sensor = _entities_by_key(coordinator)[_flow_deviation_key("a")]

    coordinator.data = {"hc_a_flow_temp": 33.0, "hc_a_setpoint_flow_temp": 31.5}
    coordinator.unused_registers = set()

    assert sensor.available is True
    assert sensor.native_value == 1.5


def test_flow_deviation_is_suppressed_while_the_circuit_requests_nothing():
    """An idle circuit reports setpoint 0.0 — that must not become a deviation.

    0.0 is a normal operating state, not a declared sentinel, so the coordinator
    does not mark the register unused. Subtracting it published the measured
    flow temperature as if the circuit were overshooting by 26 K.
    """
    coordinator = _coordinator({"hc_d_flow_temp": 26.2, "hc_d_setpoint_flow_temp": 0.0})

    sensor = _entities_by_key(coordinator)[_flow_deviation_key("d")]

    # Sources are present and readable, so the entity stays available and
    # reports 'unknown' rather than dropping out entirely.
    assert sensor.available is True
    assert sensor.native_value is None


def test_flow_deviation_returns_once_the_circuit_requests_heat_again():
    coordinator = _coordinator({"hc_d_flow_temp": 26.2, "hc_d_setpoint_flow_temp": 0.0})
    sensor = _entities_by_key(coordinator)[_flow_deviation_key("d")]

    coordinator.data = {"hc_d_flow_temp": 33.0, "hc_d_setpoint_flow_temp": 35.0}

    assert sensor.native_value == -2.0


def test_flow_deviation_keeps_a_genuine_zero_deviation():
    """Flow exactly on setpoint is a real reading and must not be suppressed."""
    coordinator = _coordinator({"hc_a_flow_temp": 32.0, "hc_a_setpoint_flow_temp": 32.0})

    sensor = _entities_by_key(coordinator)[_flow_deviation_key("a")]

    assert sensor.native_value == 0.0


def test_flow_deviation_metadata():
    coordinator = _coordinator({"hc_a_flow_temp": 34.0, "hc_a_setpoint_flow_temp": 32.0})

    sensor = _entities_by_key(coordinator)[_flow_deviation_key("a")]

    assert sensor.entity_description.name == "Heizkreis A Vorlauf-Abweichung"
    assert sensor.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert sensor.entity_description.device_class == SensorDeviceClass.TEMPERATURE
    assert sensor.entity_description.state_class == SensorStateClass.MEASUREMENT
    assert sensor._attr_unique_id == "test_entry_calculated_hc_a_flow_deviation"


def test_unconfigured_circuit_sentinel_stays_unavailable():
    """A circuit that is not configured reports -1.0 permanently."""
    coordinator = _coordinator(
        {"hc_g_flow_temp": -1.0, "hc_g_setpoint_flow_temp": -1.0},
        unused={"hc_g_flow_temp", "hc_g_setpoint_flow_temp"},
    )

    sensor = _entities_by_key(coordinator)[_flow_deviation_key("g")]

    assert sensor.available is False


def test_flow_deviation_joins_its_heating_circuit_subdevice():
    """With hierarchy enabled the sensor belongs next to its circuit's values."""
    coordinator = _coordinator({"hc_a_flow_temp": 34.0, "hc_a_setpoint_flow_temp": 32.0})
    coordinator.device_hierarchy_enabled = True

    sensor = _entities_by_key(coordinator)[_flow_deviation_key("a")]

    assert sensor.device_info["name"] == "Heizkreis A"


def test_flow_deviation_stays_on_the_main_device_without_hierarchy():
    coordinator = _coordinator({"hc_a_flow_temp": 34.0, "hc_a_setpoint_flow_temp": 32.0})
    coordinator.device_hierarchy_enabled = False

    sensor = _entities_by_key(coordinator)[_flow_deviation_key("a")]

    assert sensor.device_info["name"] == coordinator.config_entry.title


def test_existing_calculated_sensors_keep_the_main_device():
    """Moving an already-registered entity to another device is out of scope."""
    coordinator = _coordinator(
        {
            "hp_flow_temp": 35.0,
            "hp_return_temp": 30.0,
            "dhw_temp_top": 48.0,
            "dhw_setpoint": 52.0,
        }
    )
    coordinator.device_hierarchy_enabled = True

    entities = _entities_by_key(coordinator)

    for key in ("calculated_hp_temperature_delta", "calculated_dhw_setpoint_deviation"):
        assert entities[key].device_info["name"] == coordinator.config_entry.title
