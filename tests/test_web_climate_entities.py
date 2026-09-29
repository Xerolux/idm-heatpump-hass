"""Tests for the web-only climate and water-heater entities and the
register-named web write routing (KNX command path, Phase 4 slices 3+5)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.climate import HVACAction, HVACMode

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


class TestWebClimateEntities:
    def test_one_climate_entity_per_circuit(self):
        entities = web_climate_entities(_coordinator())
        assert len(entities) == 2

    def test_state_comes_from_the_circuit_detail(self):
        climate = web_climate_entities(_coordinator())[0]

        assert climate.current_temperature == 21.4
        assert climate.target_temperature == 21.5
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

        assert heater.current_temperature == 56.3
        assert heater.target_temperature == 48.0
        assert heater.min_temp == 30.0
        assert heater.max_temp == 60.0

    async def test_set_temperature_routes_through_the_web_write(self):
        coordinator = _coordinator()
        heater = web_water_heater_entities(coordinator)[0]

        await heater.async_set_temperature(temperature=49.0)

        coordinator.async_web_set_dhw_setpoint.assert_awaited_once_with(49.0)

    def test_falls_back_to_the_bridged_register_value(self):
        from dataclasses import replace as dc_replace

        coordinator = _coordinator()
        coordinator.web_supplement = dc_replace(
            coordinator.web_supplement,
            freshwater=MagicMock(temperature_top=MagicMock(numeric_value=None)),
        )
        heater = web_water_heater_entities(coordinator)[0]

        assert heater.current_temperature == 56.3
