"""Tests for small Home Assistant adapter helper modules."""

from custom_components.idm_heatpump.adapter_enums import (
    get_bitflag_de_labels,
    get_slug_map_and_key,
)
from custom_components.idm_heatpump.adapter_glt import is_glt_measurement, is_zone_room_measurement
from custom_components.idm_heatpump.adapter_registers import (
    build_filtered_register_map,
    model_info_from_flags,
)

from idm_heatpump.const import MODEL_NAVIGATOR_20


def test_enum_slug_helpers_keep_stable_translation_keys() -> None:
    system_slugs, system_key = get_slug_map_and_key("system_mode")
    room_slugs, room_key = get_slug_map_and_key("zm1_room2_mode")
    circuit_slugs, circuit_key = get_slug_map_and_key("hc_a_mode")

    assert system_key == "system_mode"
    assert system_slugs is not None
    assert system_slugs[1] == "automatic"
    assert room_key == "room_mode"
    assert room_slugs is not None
    assert room_slugs[1] == "automatic"
    assert circuit_key == "circuit_mode"
    assert circuit_slugs is not None
    assert circuit_slugs[255] == "not_configured"


def test_bitflag_label_helper_returns_german_operating_mode_labels() -> None:
    labels = get_bitflag_de_labels("hp_operating_mode")

    assert labels is not None
    assert labels[1] == "Heizbetrieb"
    assert get_bitflag_de_labels("unknown") is None


def test_glt_measurement_classification() -> None:
    assert is_glt_measurement("pv_surplus")
    assert is_glt_measurement("zm2_room3_humidity")
    assert not is_glt_measurement("pv_target_value")
    assert not is_glt_measurement("hc_a_mode")
    assert is_zone_room_measurement("zm2_room3_temp")
    assert not is_zone_room_measurement("pv_surplus")


def test_model_flag_helper_builds_cascade_aware_navigator_10_info() -> None:
    model_info = model_info_from_flags(["A"], 0, enable_cascade=False)

    assert model_info.active_heating_circuits == ["A"]
    assert model_info.has_cascade is False
    assert "power_limit_hp" in build_filtered_register_map(model_info, ["A"], 0)


def test_filtered_register_map_excludes_navigator_10_only_registers_for_navigator_20() -> None:
    model_info = model_info_from_flags(["A"], 0, enable_cascade=False)
    model_info.model_name = MODEL_NAVIGATOR_20

    assert "power_limit_hp" not in build_filtered_register_map(model_info, ["A"], 0)
