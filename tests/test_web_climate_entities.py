"""Tests for the web-only climate and water-heater entities and the
register-named web write routing (KNX command path, Phase 4 slices 3+5)."""

from __future__ import annotations

from dataclasses import replace as dc_replace
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.climate import HVACAction, HVACMode
from idm_heatpump import IdmWebHeatingCircuitValue

from custom_components.idm_heatpump.web_climate_entities import (
    web_climate_entities,
    web_water_heater_entities,
)
from custom_components.idm_heatpump.web_data import IdmWebSupplement
from tests.test_web_control_entities import _circuit, _setpoint_parameter


def _coordinator():
    coordinator = MagicMock()
    supplement = IdmWebSupplement(
        web_variant="nav10",
        sensor_values={},
        dhw_setpoint=_setpoint_parameter(48.0),
        freshwater=MagicMock(
            temperature_top=MagicMock(numeric_value=56.3),
        ),
        heating_circuits=(
            _circuit("A", mode_value=2, setpoint=21.5),
            _circuit("D", mode_value=0, setpoint=22.0, param="HKD"),
        ),
    )
    coordinator.web_supplement = supplement
    coordinator.data = {"dhw_temp_top": 56.3}
    coordinator.async_web_set_heatingcircuit_parameter = AsyncMock()
    coordinator.async_web_set_dhw_setpoint = AsyncMock()
    entry = coordinator.config_entry
    entry.entry_id = "web_climate_entry"
    entry.options = {"connection_mode": "web_only"}
    entry.data = {}
    return coordinator


def _circuit_a_with(**changes):
    """Return heating circuit A with individual fields replaced."""
    return dc_replace(_circuit("A"), **changes)


def _supplement_with_circuits(coordinator, *circuits):
    """Point the coordinator's supplement at a new circuit tuple."""
    coordinator.web_supplement = dc_replace(coordinator.web_supplement, heating_circuits=tuple(circuits))


class TestWebClimateEntities:
    def test_one_climate_entity_per_circuit(self):
        entities = web_climate_entities(_coordinator())
        assert len(entities) == 2

    def test_state_comes_from_the_circuit_detail(self):
        climate = web_climate_entities(_coordinator())[0]

        assert climate.native_current_temperature == 21.4
        assert climate.native_target_temperature == 21.5
        assert climate.hvac_mode is HVACMode.HEAT
        assert climate.hvac_action is HVACAction.IDLE  # mode on, pump off

    def test_off_circuit_reports_off(self):
        climates = {c._hc_id: c for c in web_climate_entities(_coordinator())}
        climate_d = climates["d"]

        assert climate_d.hvac_mode is HVACMode.OFF
        assert climate_d.hvac_action is HVACAction.OFF

    async def test_set_temperature_routes_through_the_web_write(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]

        await climate.async_set_temperature(temperature=22.0)

        coordinator.async_web_set_heatingcircuit_parameter.assert_awaited_once_with(
            "HKA04", 22.0, min_value=15.0, max_value=30.0
        )

    async def test_set_hvac_mode_off_writes_mode_zero(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]

        await climate.async_set_hvac_mode(HVACMode.OFF)

        coordinator.async_web_set_heatingcircuit_parameter.assert_awaited_once_with("HKA01", 0.0)

    async def test_set_hvac_mode_heat_restores_last_non_off_mode(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]
        assert climate.hvac_mode is HVACMode.HEAT  # caches _last_heat_mode

        await climate.async_set_hvac_mode(HVACMode.OFF)
        coordinator.async_web_set_heatingcircuit_parameter.reset_mock()
        await climate.async_set_hvac_mode(HVACMode.HEAT)

        coordinator.async_web_set_heatingcircuit_parameter.assert_awaited_once_with("HKA01", 2.0)


class TestWebWaterHeater:
    def test_entity_exists_with_current_and_target(self):
        heater = web_water_heater_entities(_coordinator())[0]

        assert heater.native_current_temperature == 56.3
        assert heater.native_target_temperature == 48.0
        assert heater.min_temp == 30.0
        assert heater.max_temp == 60.0

    async def test_set_temperature_routes_through_the_web_write(self):
        coordinator = _coordinator()
        heater = web_water_heater_entities(coordinator)[0]

        await heater.async_set_temperature(temperature=49.0)

        coordinator.async_web_set_dhw_setpoint.assert_awaited_once_with(49.0)

    def test_falls_back_to_the_bridged_register_value(self):
        coordinator = _coordinator()
        coordinator.web_supplement = dc_replace(
            coordinator.web_supplement,
            freshwater=MagicMock(temperature_top=MagicMock(numeric_value=None)),
        )
        heater = web_water_heater_entities(coordinator)[0]

        assert heater.native_current_temperature == 56.3


class TestWebClimateEntityCreationGates:
    def test_no_entities_outside_web_only_mode(self):
        coordinator = _coordinator()
        coordinator.config_entry.options = {"connection_mode": "auto"}

        assert web_climate_entities(coordinator) == []
        assert web_water_heater_entities(coordinator) == []

    def test_no_entities_on_another_web_variant(self):
        coordinator = _coordinator()
        coordinator.web_supplement = dc_replace(coordinator.web_supplement, web_variant="nav20")

        assert web_climate_entities(coordinator) == []
        assert web_water_heater_entities(coordinator) == []

    def test_no_water_heater_without_a_dhw_setpoint(self):
        coordinator = _coordinator()
        coordinator.web_supplement = dc_replace(coordinator.web_supplement, dhw_setpoint=None)

        assert web_water_heater_entities(coordinator) == []

    def test_differential_circuit_gets_no_climate_card(self):
        coordinator = _coordinator()
        coordinator.config_entry.options = {
            "connection_mode": "web_only",
            "heating_circuits": ["a", "d"],
            "differential_circuits": ["a"],
        }

        climates = {c._hc_id: c for c in web_climate_entities(coordinator)}

        assert "a" not in climates
        assert "d" in climates


class TestWebClimateAvailability:
    def test_available_while_the_circuit_exists(self):
        climate = web_climate_entities(_coordinator())[0]

        assert climate.available is True

    def test_unavailable_once_the_web_supplement_is_gone(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]
        coordinator.web_supplement = None

        assert climate.available is False
        assert climate._circuit() is None
        assert climate.native_current_temperature is None
        assert climate.native_target_temperature is None
        assert climate.hvac_mode is None
        assert climate.hvac_action is None

    def test_unavailable_when_the_circuit_disappears(self):
        coordinator = _coordinator()
        climates = {c._hc_id: c for c in web_climate_entities(coordinator)}
        _supplement_with_circuits(coordinator, _circuit("D", mode_value=0, setpoint=22.0, param="HKD"))

        assert climates["a"]._circuit() is None
        assert climates["a"].available is False
        assert climates["d"].available is True

    def test_device_info_is_the_main_device(self):
        coordinator = _coordinator()
        main_info = {"identifiers": {("idm_heatpump", "web_climate_entry")}}
        coordinator.device_info = MagicMock(return_value=main_info)

        assert web_climate_entities(coordinator)[0].device_info is main_info
        assert web_water_heater_entities(coordinator)[0].device_info is main_info


class TestWebClimateStateGuards:
    def test_current_temperature_none_when_the_room_value_is_missing(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]
        _supplement_with_circuits(coordinator, _circuit_a_with(room_temperature=None))

        assert climate.native_current_temperature is None

    def test_current_temperature_none_for_a_boolean_room_value(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]
        _supplement_with_circuits(coordinator, _circuit_a_with(room_temperature=True))

        assert climate.native_current_temperature is None

    def test_current_temperature_converts_integer_readings(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]
        _supplement_with_circuits(coordinator, _circuit_a_with(room_temperature=21))

        assert climate.native_current_temperature == 21.0

    def test_target_temperature_none_when_the_setpoint_value_is_missing(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]
        _supplement_with_circuits(
            coordinator,
            _circuit_a_with(setpoint_normal=IdmWebHeatingCircuitValue(parameter_id="HKA04")),
        )

        assert climate.native_target_temperature is None

    def test_target_temperature_adopts_the_device_declared_bounds(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]
        _supplement_with_circuits(coordinator, _circuit("A", setpoint=21.5, minimum=16.0, maximum=24.0))

        assert climate.native_target_temperature == 21.5
        assert climate._attr_min_hvac_setpoint == 16.0
        assert climate._attr_max_hvac_setpoint == 24.0

    def test_hvac_mode_and_action_none_without_a_mode_value(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]
        _supplement_with_circuits(coordinator, _circuit_a_with(mode_value=None))

        assert climate.hvac_mode is None
        assert climate.hvac_action is None

    def test_hvac_action_heating_while_the_pump_runs(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]
        _supplement_with_circuits(coordinator, _circuit_a_with(pump_active=True))

        assert climate.hvac_action is HVACAction.HEATING


class TestWebClimateStep:
    def _climate_with_increment(self, increment):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]
        _supplement_with_circuits(
            coordinator,
            _circuit_a_with(
                setpoint_normal=IdmWebHeatingCircuitValue(parameter_id="HKA04", value=21.5, increment=increment)
            ),
        )
        return climate

    def test_step_comes_from_the_device_increment(self):
        assert self._climate_with_increment("0.5").target_temperature_step == 0.5

    def test_step_tolerates_padded_string_increments(self):
        assert self._climate_with_increment(" 0.5 ").target_temperature_step == 0.5

    def test_step_falls_back_without_an_increment(self):
        assert self._climate_with_increment(None).target_temperature_step == 0.1

    def test_step_falls_back_on_a_non_numeric_increment(self):
        assert self._climate_with_increment("auto").target_temperature_step == 0.1

    def test_step_falls_back_on_a_non_positive_increment(self):
        assert self._climate_with_increment("0").target_temperature_step == 0.1


class TestWebClimateWriteGuards:
    async def test_set_temperature_without_a_temperature_is_ignored(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]

        await climate.async_set_temperature()

        coordinator.async_web_set_heatingcircuit_parameter.assert_not_awaited()

    async def test_set_temperature_without_a_setpoint_parameter_is_ignored(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]
        _supplement_with_circuits(coordinator, _circuit_a_with(setpoint_normal=None))

        await climate.async_set_temperature(temperature=22.0)

        coordinator.async_web_set_heatingcircuit_parameter.assert_not_awaited()

    async def test_set_hvac_mode_without_a_mode_parameter_is_ignored(self):
        coordinator = _coordinator()
        climate = web_climate_entities(coordinator)[0]
        _supplement_with_circuits(coordinator, _circuit_a_with(mode_parameter_id=None))

        await climate.async_set_hvac_mode(HVACMode.HEAT)

        coordinator.async_web_set_heatingcircuit_parameter.assert_not_awaited()


class TestWebWaterHeaterState:
    def test_available_while_the_supplement_exists(self):
        heater = web_water_heater_entities(_coordinator())[0]

        assert heater.available is True

    def test_unavailable_once_the_web_supplement_is_gone(self):
        coordinator = _coordinator()
        heater = web_water_heater_entities(coordinator)[0]
        coordinator.web_supplement = None

        assert heater.available is False
        # The last bridged register value still answers for the temperature.
        assert heater.native_current_temperature == 56.3
        assert heater.native_target_temperature is None

    def test_current_temperature_none_without_any_source(self):
        coordinator = _coordinator()
        heater = web_water_heater_entities(coordinator)[0]
        coordinator.web_supplement = dc_replace(
            coordinator.web_supplement,
            freshwater=MagicMock(temperature_top=MagicMock(numeric_value=None)),
        )
        coordinator.data = {}

        assert heater.native_current_temperature is None

    def test_target_temperature_none_without_a_value(self):
        coordinator = _coordinator()
        heater = web_water_heater_entities(coordinator)[0]
        coordinator.web_supplement = dc_replace(
            coordinator.web_supplement, dhw_setpoint=_setpoint_parameter(value=None)
        )

        assert heater.native_target_temperature is None

    def test_target_temperature_high_follows_the_target(self):
        heater = web_water_heater_entities(_coordinator())[0]

        assert heater.native_target_temperature_high == heater.native_target_temperature == 48.0

    async def test_set_temperature_without_a_temperature_is_ignored(self):
        coordinator = _coordinator()
        heater = web_water_heater_entities(coordinator)[0]

        await heater.async_set_temperature()

        coordinator.async_web_set_dhw_setpoint.assert_not_awaited()
