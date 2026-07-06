"""Tests for small Home Assistant adapter helper modules."""

import json
from pathlib import Path
from unittest.mock import patch

from custom_components.idm_heatpump.adapter_enums import (
    get_bitflag_de_labels,
    get_slug_map_and_key,
)
from custom_components.idm_heatpump.adapter_glt import is_glt_measurement, is_zone_room_measurement
from custom_components.idm_heatpump.adapter_registers import (
    build_filtered_register_map,
    model_info_from_flags,
)
from custom_components.idm_heatpump.library_adapter import get_idm_client

from idm_heatpump import MODEL_NAVIGATOR_10, MODEL_NAVIGATOR_20

ROOT = Path(__file__).resolve().parents[1]


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


def test_enum_translation_keys_are_present_in_english_and_german() -> None:
    strings = json.loads((ROOT / "custom_components" / "idm_heatpump" / "strings.json").read_text(encoding="utf-8"))
    english = json.loads(
        (ROOT / "custom_components" / "idm_heatpump" / "translations" / "en.json").read_text(encoding="utf-8")
    )
    german = json.loads(
        (ROOT / "custom_components" / "idm_heatpump" / "translations" / "de.json").read_text(encoding="utf-8")
    )

    for platform in ("select", "sensor"):
        for key, payload in strings["entity"][platform].items():
            states = set(payload["state"])
            assert set(english["entity"][platform][key]["state"]) == states
            assert set(german["entity"][platform][key]["state"]) == states


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
    model_info = model_info_from_flags(["A"], 0, enable_cascade=False, model_name=MODEL_NAVIGATOR_10)

    assert model_info.active_heating_circuits == ["A"]
    assert model_info.has_cascade is False
    assert model_info.model_name == MODEL_NAVIGATOR_10
    assert "power_limit_hp" in build_filtered_register_map(model_info, ["A"], 0)


def test_model_flag_helper_builds_navigator_20_info_from_explicit_model_name() -> None:
    model_info = model_info_from_flags(["A", "B"], 2, enable_cascade=False, model_name=MODEL_NAVIGATOR_20)

    assert model_info.model_name == MODEL_NAVIGATOR_20
    assert model_info.active_heating_circuits == ["A", "B"]
    assert model_info.zone_modules == 2
    assert model_info.has_cascade is False
    reg_map = build_filtered_register_map(model_info, ["A", "B"], 2)
    assert "power_limit_hp" not in reg_map
    assert "booster_b_source_inlet_temp" not in reg_map


def test_model_flag_helper_accepts_default_model_name() -> None:
    model_info = model_info_from_flags(["A"], 0, enable_cascade=False)

    assert model_info.model_name == MODEL_NAVIGATOR_10


def test_filtered_register_map_excludes_navigator_10_only_registers_for_navigator_20() -> None:
    model_info = model_info_from_flags(["A"], 0, enable_cascade=False, model_name=MODEL_NAVIGATOR_20)

    reg_map = build_filtered_register_map(model_info, ["A"], 0)

    assert "power_limit_hp" not in reg_map
    assert "booster_b_source_inlet_temp" not in reg_map


def test_get_idm_client_forwards_timeout_and_max_retries() -> None:
    """Optional timeout/max_retries must be handed through to the library client."""
    captured: dict = {}

    def _fake_client(*args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    with patch("custom_components.idm_heatpump.library_adapter.LibIdmModbusClient", side_effect=_fake_client):
        get_idm_client(host="10.0.0.5", port=502, slave_id=1, timeout=15.0, max_retries=2)

    assert captured["timeout"] == 15.0
    assert captured["max_retries"] == 2


def test_get_idm_client_omits_unset_optional_params() -> None:
    """When optional params are None, they must not be forwarded (library defaults take over)."""
    captured: dict = {}

    def _fake_client(*args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    with patch("custom_components.idm_heatpump.library_adapter.LibIdmModbusClient", side_effect=_fake_client):
        get_idm_client(host="10.0.0.5")

    assert "timeout" not in captured
    assert "max_retries" not in captured
