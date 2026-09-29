"""Tests for the Navigator 10 system-controller entities (performance, weather, iON, energyflow)."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from idm_heatpump import (
    IdmWebEnergyflow,
    IdmWebIon,
    IdmWebPerformance,
    IdmWebWeatherDay,
    IdmWebWeatherDetail,
)

from custom_components.idm_heatpump.web_data import IdmWebSupplement
from custom_components.idm_heatpump.web_system_entities import (
    web_system_binary_entities,
    web_system_sensor_entities,
)


def _supplement() -> IdmWebSupplement:
    return IdmWebSupplement(
        web_variant="nav10",
        performance=IdmWebPerformance(
            consumption_power=1.45,
            consumption_source=2,
            consumption_battery=False,
            environment_power=0.32,
            environment_source=2,
            environment_temperature_in=17.5,
            production_flow_temperature=52.3,
            heating_rod=False,
            mode=0,
            system_mode=1,
        ),
        weather=IdmWebWeatherDetail(
            today=IdmWebWeatherDay(
                date="29.09.2026",
                day_of_week="N2_TODAY",
                cloud_cover=0.47,
                rain_probability=0.0,
                sun_seconds=40991,
                symbol=1,
                temperature=18.0,
                temperature_min=9.0,
                temperature_max=25.0,
                temperature_avg_label="14°C/16.0h",
                wind_speed_min=0.7,
                wind_speed_max=2.8,
            ),
            forecasts=(
                IdmWebWeatherDay(date="30.09.2026", day_of_week="N2_WE", temperature=17.0),
                IdmWebWeatherDay(date="01.10.2026", day_of_week="N2_TH", temperature=18.0),
            ),
        ),
        ion=IdmWebIon(
            active=False,
            enabled_setting_id="CE001",
            enabled_value=0,
            subscription_status=-1,
        ),
        energyflow=IdmWebEnergyflow(
            grid_power=12.997,
            pv_power=5.694,
            house_power=None,
            signal=16,
            type=4,
        ),
    )


def _coordinator(supplement: IdmWebSupplement | None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.web_supplement = supplement
    coordinator.last_update_success = True
    coordinator.config_entry.entry_id = "test_entry"
    return coordinator


@pytest.fixture
def nav10_coordinator():
    return _coordinator(_supplement())


class TestEntityCreation:
    def test_no_entities_without_nav10_supplement(self) -> None:
        coordinator = _coordinator(None)

        assert web_system_sensor_entities(coordinator) == []
        assert web_system_binary_entities(coordinator) == []

    def test_no_entities_for_nav20_variant(self) -> None:
        coordinator = _coordinator(IdmWebSupplement(web_variant="nav20"))

        assert web_system_sensor_entities(coordinator) == []
        assert web_system_binary_entities(coordinator) == []

    def test_entities_created_before_frames_land(self) -> None:
        coordinator = _coordinator(IdmWebSupplement(web_variant="nav10"))

        sensors = web_system_sensor_entities(coordinator)
        binaries = web_system_binary_entities(coordinator)

        assert len(sensors) == 5
        assert len(binaries) == 2
        assert all(entity.available is False for entity in sensors)
        assert all(entity.available is False for entity in binaries)

    def test_sensor_keys_and_unique_ids(self, nav10_coordinator) -> None:
        sensors = web_system_sensor_entities(nav10_coordinator)

        assert {s.entity_description.key for s in sensors} == {
            "web_hp_power_consumption",
            "web_hp_power_environment",
            "web_energyflow_grid",
            "web_energyflow_pv",
            "web_weather_forecast",
        }
        for sensor in sensors:
            assert sensor._attr_unique_id is not None
            assert sensor._attr_unique_id.startswith(nav10_coordinator.config_entry.entry_id)
            assert sensor._attr_unique_id.endswith(sensor.entity_description.key)


class TestPerformanceEntities:
    def test_consumption_power_sensor(self, nav10_coordinator) -> None:
        sensor = next(
            s
            for s in web_system_sensor_entities(nav10_coordinator)
            if s.entity_description.key == "web_hp_power_consumption"
        )

        assert sensor.available is True
        assert sensor.native_value == pytest.approx(1.45)
        assert sensor._attr_native_unit_of_measurement == "kW"
        attributes = sensor.extra_state_attributes
        assert attributes["performance_mode"] == 0
        assert attributes["system_mode"] == 1
        assert attributes["production_flow_temperature"] == pytest.approx(52.3)
        assert attributes["consumption_battery"] is False

    def test_environment_power_sensor(self, nav10_coordinator) -> None:
        sensor = next(
            s
            for s in web_system_sensor_entities(nav10_coordinator)
            if s.entity_description.key == "web_hp_power_environment"
        )

        assert sensor.native_value == pytest.approx(0.32)
        assert sensor.extra_state_attributes["environment_temperature_in"] == pytest.approx(17.5)

    def test_heating_rod_binary_sensor(self, nav10_coordinator) -> None:
        entity = next(
            b for b in web_system_binary_entities(nav10_coordinator) if b.entity_description.key == "web_hp_heating_rod"
        )

        assert entity.is_on is False
        assert entity.available is True


class TestEnergyflowEntities:
    def test_grid_and_pv_power(self, nav10_coordinator) -> None:
        sensors = {s.entity_description.key: s for s in web_system_sensor_entities(nav10_coordinator)}

        assert sensors["web_energyflow_grid"].native_value == pytest.approx(12.997)
        assert sensors["web_energyflow_pv"].native_value == pytest.approx(5.694)
        attributes = sensors["web_energyflow_grid"].extra_state_attributes
        assert attributes["signal"] == 16
        assert attributes["type"] == 4
        assert "house_power" not in attributes  # removed in firmware 20.24-1580

    def test_house_power_attribute_on_older_firmware(self, nav10_coordinator) -> None:
        nav10_coordinator.web_supplement = replace(
            nav10_coordinator.web_supplement,
            energyflow=IdmWebEnergyflow(grid_power=0.024, pv_power=0.493, house_power=0.469),
        )

        sensors = {s.entity_description.key: s for s in web_system_sensor_entities(nav10_coordinator)}
        assert sensors["web_energyflow_grid"].extra_state_attributes["house_power"] == pytest.approx(0.469)


class TestWeatherEntity:
    def test_state_is_today_temperature(self, nav10_coordinator) -> None:
        sensor = next(
            s
            for s in web_system_sensor_entities(nav10_coordinator)
            if s.entity_description.key == "web_weather_forecast"
        )

        assert sensor.available is True
        assert sensor.native_value == pytest.approx(18.0)
        attributes = sensor.extra_state_attributes
        assert attributes["today"]["date"] == "29.09.2026"
        assert attributes["today"]["sun_seconds"] == 40991
        assert [day["date"] for day in attributes["forecast"]] == [
            "30.09.2026",
            "01.10.2026",
        ]

    def test_unavailable_without_today(self, nav10_coordinator) -> None:
        nav10_coordinator.web_supplement = replace(
            nav10_coordinator.web_supplement,
            weather=IdmWebWeatherDetail(forecasts=(IdmWebWeatherDay(date="30.09.2026"),)),
        )

        sensor = next(
            s
            for s in web_system_sensor_entities(nav10_coordinator)
            if s.entity_description.key == "web_weather_forecast"
        )
        assert sensor.available is True  # frame landed
        assert sensor.native_value is None  # but today is absent


class TestIonEntity:
    def test_ion_status(self, nav10_coordinator) -> None:
        entity = next(
            b for b in web_system_binary_entities(nav10_coordinator) if b.entity_description.key == "web_ion_active"
        )

        assert entity.is_on is False
        assert entity.available is True
        attributes = entity.extra_state_attributes
        assert attributes["enabled_setting_id"] == "CE001"
        assert attributes["subscription_status"] == -1
