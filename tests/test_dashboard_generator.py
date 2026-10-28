"""Tests for the plant dashboard generator service."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ServiceValidationError

from custom_components.idm_heatpump.dashboard_generator import (
    PlantDashboardBuilder,
    build_plant_dashboard,
)
from custom_components.idm_heatpump.services import _handle_generate_dashboard


def _registry(entities: dict[tuple[str, str], str]) -> Any:
    """Fake the entity-registry lookup the handler builds."""

    def lookup(unique_id: str, domain: str) -> str | None:
        return entities.get((domain, unique_id))

    return lookup


def _full_plant() -> dict[tuple[str, str], str]:
    entry = "test_entry"
    entities: dict[tuple[str, str], str] = {
        ("sensor", f"{entry}_outdoor_temp"): "sensor.outdoor",
        ("sensor", f"{entry}_hp_flow_temp"): "sensor.flow",
        ("sensor", f"{entry}_hp_return_temp"): "sensor.return",
        ("sensor", f"{entry}_hp_operating_mode"): "sensor.mode",
        ("sensor", f"{entry}_power_consumption_hp"): "sensor.power",
        ("sensor", f"{entry}_calculated_cop"): "sensor.cop",
        ("sensor", f"{entry}_dhw_temp_top"): "sensor.dhw",
        ("climate", f"{entry}_climate_hc_a"): "climate.heating_a",
        ("climate", f"{entry}_climate_hc_c"): "climate.heating_c",
        ("sensor", f"{entry}_hc_a_flow_temp"): "sensor.hc_a_flow",
        ("sensor", f"{entry}_hc_a_room_temp"): "sensor.hc_a_room",
        ("water_heater", f"{entry}_water_heater"): "water_heater.dhw",
        ("button", f"{entry}_dhw_boost_start"): "button.boost_start",
        ("button", f"{entry}_dhw_boost_cancel"): "button.boost_cancel",
        ("sensor", f"{entry}_energy_electrical_total"): "sensor.energy_electrical",
        ("sensor", f"{entry}_energy_thermal_total"): "sensor.energy_thermal",
        ("sensor", f"{entry}_energy_cop_total"): "sensor.energy_cop",
        ("sensor", f"{entry}_connection_mode"): "sensor.connection_mode",
        ("sensor", f"{entry}_web_last_success"): "sensor.web_last_success",
        ("button", f"{entry}_connection_reload"): "button.connection_reload",
        ("button", f"{entry}_acknowledge_errors"): "button.acknowledge",
    }
    return entities


def test_builder_skips_missing_entities_and_views() -> None:
    dashboard = PlantDashboardBuilder("test_entry", _registry({}), ["a"]).build()
    assert dashboard["views"] == []
    with pytest.raises(ValueError):
        build_plant_dashboard("test_entry", _registry({}), ["a"])


def test_builder_composes_all_views_for_full_plant() -> None:
    dashboard = build_plant_dashboard("test_entry", _registry(_full_plant()), ["a", "c"])
    paths = [view["path"] for view in dashboard["views"]]
    assert paths == ["idm-overview", "idm-heating", "idm-hot-water", "idm-energy", "idm-diagnostics"]

    overview = dashboard["views"][0]
    overview_entities = [
        entity for card in overview["cards"] if card["type"] == "entities" for entity in card["entities"]
    ]
    assert "sensor.outdoor" in overview_entities
    assert "sensor.dhw" in overview_entities

    heating = dashboard["views"][1]
    thermostats = [card["entity"] for card in heating["cards"] if card["type"] == "thermostat"]
    assert thermostats == ["climate.heating_a", "climate.heating_c"]

    hot_water = dashboard["views"][2]
    hot_water_entities = [entity for card in hot_water["cards"] for entity in card.get("entities", [])]
    assert "water_heater.dhw" in hot_water_entities
    assert "button.boost_start" in hot_water_entities

    diagnostics = dashboard["views"][4]
    diagnostics_entities = diagnostics["cards"][0]["entities"]
    assert "sensor.connection_mode" in diagnostics_entities
    assert "button.acknowledge" in diagnostics_entities


def test_builder_prefers_register_entities_over_web() -> None:
    entry = "test_entry"
    entities = {
        ("climate", f"{entry}_climate_hc_a"): "climate.register_a",
        ("water_heater", f"{entry}_water_heater"): "water_heater.register",
    }
    dashboard = build_plant_dashboard(entry, _registry(entities), ["a"])
    heating = dashboard["views"][0]
    assert [card["entity"] for card in heating["cards"] if card["type"] == "thermostat"] == ["climate.register_a"]
    hot_water = dashboard["views"][1]
    assert hot_water["cards"][0]["entities"] == ["water_heater.register"]


def test_builder_falls_back_to_web_climate() -> None:
    entry = "test_entry"
    entities = {("climate", f"{entry}_web_climate_hc_a"): "climate.web_a"}
    dashboard = build_plant_dashboard(entry, _registry(entities), ["a"])
    heating = dashboard["views"][0]
    assert [card["entity"] for card in heating["cards"] if card["type"] == "thermostat"] == ["climate.web_a"]


def _make_call(entry_id: str) -> Any:
    call = MagicMock()
    call.data = {"entry_id": entry_id}
    return call


def _make_hass(entry: Any) -> Any:
    hass = MagicMock()
    hass.config_entries.async_get_entry.return_value = entry
    return hass


def _loaded_entry(circuits: list[str] | None = None) -> Any:
    entry = MagicMock()
    entry.domain = "idm_heatpump"
    entry.entry_id = "test_entry"
    entry.state = ConfigEntryState.LOADED
    entry.options = {"heating_circuits": circuits} if circuits is not None else {}
    entry.data = {}
    return entry


async def test_handler_returns_dashboard_and_yaml() -> None:
    entry = _loaded_entry(["a"])
    hass = _make_hass(entry)
    with patch(
        "homeassistant.helpers.entity_registry.async_get",
        return_value=MagicMock(
            async_get_entity_id=lambda domain, platform, unique_id: {
                ("sensor", f"{entry.entry_id}_outdoor_temp"): "sensor.outdoor",
                ("sensor", f"{entry.entry_id}_hp_flow_temp"): "sensor.flow",
            }.get((domain, unique_id)),
        ),
    ):
        response = await _handle_generate_dashboard(hass, _make_call("test_entry"))

    assert "dashboard" in response and "dashboard_yaml" in response
    dashboard = response["dashboard"]
    assert dashboard["views"], "overview needs at least one sensor card"
    assert "sensor.outdoor" in response["dashboard_yaml"]
    assert "lovelace" in response["dashboard_yaml"]  # registration snippet included


async def test_handler_rejects_unloaded_entry() -> None:
    entry = _loaded_entry()
    entry.state = ConfigEntryState.NOT_LOADED
    hass = _make_hass(entry)
    with pytest.raises(ServiceValidationError):
        await _handle_generate_dashboard(hass, _make_call("test_entry"))


async def test_handler_rejects_empty_plant() -> None:
    hass = _make_hass(_loaded_entry(["a"]))
    with (
        patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=MagicMock(async_get_entity_id=lambda domain, platform, unique_id: None),
        ),
        pytest.raises(ServiceValidationError),
    ):
        await _handle_generate_dashboard(hass, _make_call("test_entry"))
