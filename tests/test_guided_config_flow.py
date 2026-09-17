"""The three guided setup depths keep feature access and saved options intact."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.idm_heatpump import config_flow as flow_module
from custom_components.idm_heatpump.config_flow import (
    _GUIDED_FEATURES,
    _GUIDED_LEVELS,
    IdmHeatpumpConfigFlow,
    IdmHeatpumpOptionsFlow,
    _build_guided_field_schema,
    _build_setup_review_schema,
    _guided_detail_keys,
)
from custom_components.idm_heatpump.const import (
    CONF_COMFORT_SCHEDULE,
    CONF_COMFORT_WINDOWS,
    CONF_HEALTH_MONITOR,
    CONF_KNX_BRIDGE,
    CONF_KNX_GROUPS,
    CONF_MODBUS_TIMEOUT,
    CONF_ROOM_TEMP_FORWARDING,
    CONF_ROOM_TEMP_FORWARDING_ENTITIES,
    CONF_SCAN_INTERVAL,
    CONF_SETUP_LEVEL,
    CONF_STORAGE_TEMP_FORWARDING_ENTITIES,
    CONF_WEATHER_ENTITY,
    CONF_WEATHER_PREHEAT,
    CONF_ZONE_COUNT,
    CONF_ZONE_ROOMS,
)


def _options_flow(options: dict[str, object] | None = None) -> IdmHeatpumpOptionsFlow:
    flow = IdmHeatpumpOptionsFlow()
    flow.config_entry = MagicMock(title="IDM", options=options or {})
    return flow


def _markers(schema: vol.Schema) -> dict[str, vol.Marker]:
    return {str(getattr(marker, "key", getattr(marker, "schema", marker))): marker for marker in schema.schema}


def test_all_setup_levels_offer_the_same_functions() -> None:
    schema = _build_setup_review_schema({})
    assert "profile" in schema.schema
    assert _GUIDED_LEVELS == ("standard", "advanced", "expert")
    for language in ("strings", "translations/en", "translations/de"):
        data = json.loads(Path(f"custom_components/idm_heatpump/{language}.json").read_text(encoding="utf-8"))
        assert set(data["selector"]["guided_features"]["options"]) == set(_GUIDED_FEATURES)
        assert set(data["selector"]["guided_level"]["options"]) == {"standard", "advanced", "expert"}
        for root in ("config", "options"):
            assert {"guided_mode", "guided_choose", "guided_toggle", "guided_detail", "guided_review"} <= set(
                data[root]["step"]
            )


def test_wizard_reuses_validated_fields_and_reaches_every_option() -> None:
    assert CONF_SCAN_INTERVAL in _markers(_build_guided_field_schema({}, (CONF_SCAN_INTERVAL,)))
    assert CONF_HEALTH_MONITOR in _markers(_build_guided_field_schema({}, (CONF_HEALTH_MONITOR,)))
    assert CONF_MODBUS_TIMEOUT not in _guided_detail_keys("modbus", "standard")
    assert CONF_MODBUS_TIMEOUT in _guided_detail_keys("modbus", "advanced")
    assert len(_guided_detail_keys("modbus", "expert")) > len(_guided_detail_keys("modbus", "advanced"))


def test_guided_fields_accept_home_assistant_section_schema() -> None:
    nested = vol.Schema({vol.Optional(CONF_HEALTH_MONITOR): bool})
    schema = MagicMock()
    schema.schema = {vol.Optional("features"): MagicMock(schema=nested)}
    with patch.object(flow_module, "_build_options_schema", return_value=schema):
        assert CONF_HEALTH_MONITOR in _markers(_build_guided_field_schema({}, (CONF_HEALTH_MONITOR,)))


async def test_mapping_step_returns_to_next_selected_feature() -> None:
    flow = _options_flow()
    await flow.async_step_init()
    await flow.async_step_guided_mode({CONF_SETUP_LEVEL: "standard"})
    await flow.async_step_guided_choose({"selected_features": ["room_forwarding"]})
    result = await flow.async_step_guided_toggle({CONF_ROOM_TEMP_FORWARDING: True})
    assert result["step_id"] == "room_temp_forwarding"
    with patch.object(flow, "_async_guided_next", return_value={"step_id": "guided_toggle"}) as next_step:
        result = await flow._async_continue_optional_steps("room_temp_forwarding")
    assert result["step_id"] == "guided_toggle"
    next_step.assert_awaited_once()


async def test_health_only_reconfigure_skips_unchanged_knx() -> None:
    flow = IdmHeatpumpConfigFlow()
    entry = MagicMock()
    entry.data = {"host": "192.168.1.100", "name": "IDM"}
    entry.options = {CONF_KNX_BRIDGE: True, CONF_KNX_GROUPS: ["energy"], CONF_HEALTH_MONITOR: False}
    entry.title = "IDM"
    with (
        patch.object(flow, "_get_reconfigure_entry", return_value=entry),
        patch.object(flow, "async_update_and_abort", return_value={"type": "abort"}) as update,
    ):
        result = await flow.async_step_features()
        assert result["step_id"] == "guided_mode"
        result = await flow.async_step_guided_mode({CONF_SETUP_LEVEL: "standard"})
        assert result["step_id"] == "guided_choose"
        result = await flow.async_step_guided_choose({"selected_features": ["health"]})
        assert result["step_id"] == "guided_toggle"
        result = await flow.async_step_guided_toggle({CONF_HEALTH_MONITOR: True})
        assert result["step_id"] == "guided_review"
        result = await flow.async_step_guided_review({"save_configuration": True})
        assert result["step_id"] == "feature_notice"
        result = await flow.async_step_feature_notice({"confirm_new_features": True})
    assert result["type"] == "abort"
    assert update.call_args.kwargs["options"][CONF_KNX_BRIDGE] is True
    assert update.call_args.kwargs["options"][CONF_HEALTH_MONITOR] is True
    assert update.call_args.kwargs["options"][CONF_SETUP_LEVEL] == "standard"


async def test_switching_levels_keeps_hidden_values_and_disabled_sensor_mapping() -> None:
    options = {
        CONF_MODBUS_TIMEOUT: 17.0,
        CONF_ROOM_TEMP_FORWARDING: True,
        CONF_ROOM_TEMP_FORWARDING_ENTITIES: {"a": "sensor.living"},
        CONF_STORAGE_TEMP_FORWARDING_ENTITIES: {"dhw_top": "sensor.tank"},
    }
    flow = _options_flow(options)
    await flow.async_step_init()
    await flow.async_step_guided_mode({CONF_SETUP_LEVEL: "standard"})
    result = await flow.async_step_guided_choose({"selected_features": ["room_forwarding"]})
    assert result["step_id"] == "guided_toggle"
    result = await flow.async_step_guided_toggle({CONF_ROOM_TEMP_FORWARDING: False})
    assert result["step_id"] == "guided_review"
    result = await flow.async_step_guided_review({"save_configuration": True})
    assert result["type"] == "create_entry"
    assert result["data"][CONF_MODBUS_TIMEOUT] == 17.0
    assert result["data"][CONF_ROOM_TEMP_FORWARDING_ENTITIES] == {"a": "sensor.living"}
    assert result["data"][CONF_STORAGE_TEMP_FORWARDING_ENTITIES] == {"dhw_top": "sensor.tank"}


async def test_initial_setup_guides_to_summary_then_feature_notice() -> None:
    flow = IdmHeatpumpConfigFlow()
    flow._data = {"name": "IDM", "host": "192.168.1.100"}
    result = await flow.async_step_setup_review({"profile": "advanced"})
    assert result["step_id"] == "guided_choose"
    result = await flow.async_step_guided_choose({"selected_features": []})
    assert result["step_id"] == "guided_review"
    rejected = await flow.async_step_guided_review({"save_configuration": False})
    assert rejected["errors"] == {"base": "guided_review_required"}
    result = await flow.async_step_guided_review({"save_configuration": True})
    assert result["step_id"] == "feature_notice"


async def test_plant_zones_are_configured_and_cleared() -> None:
    flow = _options_flow({CONF_ZONE_COUNT: 0})
    await flow.async_step_init()
    await flow.async_step_guided_mode({CONF_SETUP_LEVEL: "standard"})
    await flow.async_step_guided_choose({"selected_features": ["plant"]})
    result = await flow.async_step_guided_detail({"heating_circuits": ["a"], CONF_ZONE_COUNT: 1})
    assert result["step_id"] == "zones"
    result = await flow.async_step_zones({"zone_0_rooms": 3})
    assert result["step_id"] == "guided_review"
    assert flow._options[CONF_ZONE_ROOMS] == {0: 3}

    flow = _options_flow({CONF_ZONE_COUNT: 1, CONF_ZONE_ROOMS: {0: 3}})
    await flow.async_step_init()
    await flow.async_step_guided_mode({CONF_SETUP_LEVEL: "standard"})
    await flow.async_step_guided_choose({"selected_features": ["plant"]})
    result = await flow.async_step_guided_detail({"heating_circuits": ["a"], CONF_ZONE_COUNT: 0})
    assert result["step_id"] == "guided_review"
    assert flow._options[CONF_ZONE_ROOMS] == {}


async def test_weather_requires_entity_and_comfort_windows_are_validated() -> None:
    flow = _options_flow()
    await flow.async_step_init()
    await flow.async_step_guided_mode({CONF_SETUP_LEVEL: "standard"})
    await flow.async_step_guided_choose({"selected_features": ["weather"]})
    assert (await flow.async_step_guided_toggle({CONF_WEATHER_PREHEAT: True}))["step_id"] == "guided_detail"
    result = await flow.async_step_guided_detail({})
    assert result["errors"] == {CONF_WEATHER_ENTITY: "weather_entity_required"}
    result = await flow.async_step_guided_detail({CONF_WEATHER_ENTITY: "weather.home"})
    assert result["step_id"] == "guided_review"

    flow = _options_flow()
    await flow.async_step_init()
    await flow.async_step_guided_mode({CONF_SETUP_LEVEL: "advanced"})
    await flow.async_step_guided_choose({"selected_features": ["comfort"]})
    assert (await flow.async_step_guided_toggle({CONF_COMFORT_SCHEDULE: True}))["step_id"] == "guided_detail"
    result = await flow.async_step_guided_detail({CONF_COMFORT_WINDOWS: "a,06:00,09:00,21\na,08:00,10:00,22"})
    assert result["errors"] == {CONF_COMFORT_WINDOWS: "invalid_comfort_windows"}


@pytest.mark.parametrize("level", ["standard", "advanced", "expert"])
async def test_every_level_can_enable_every_switch(level: str) -> None:
    for feature, (toggle, _, _, _) in _GUIDED_FEATURES.items():
        if toggle is None:
            continue
        flow = _options_flow()
        await flow.async_step_init()
        await flow.async_step_guided_mode({CONF_SETUP_LEVEL: level})
        result = await flow.async_step_guided_choose({"selected_features": [feature]})
        assert result["step_id"] == "guided_toggle"
        assert toggle in _markers(_build_guided_field_schema(flow._options, (toggle,)))
