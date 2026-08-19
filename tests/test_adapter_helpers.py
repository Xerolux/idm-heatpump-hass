"""Tests for small Home Assistant adapter helper modules."""

import json
from pathlib import Path
from unittest.mock import patch

from idm_heatpump import (
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    DataType,
    RegisterDef,
)

from custom_components.idm_heatpump.adapter_enums import (
    get_bitflag_de_labels,
    get_slug_map_and_key,
)
from custom_components.idm_heatpump.adapter_glt import is_glt_measurement, is_zone_room_measurement
from custom_components.idm_heatpump.adapter_registers import (
    build_filtered_register_map,
    model_info_from_flags,
)
from custom_components.idm_heatpump.library_adapter import (
    _numbers_from_register_map,
    get_idm_client,
)

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
            if "state" not in payload:
                continue
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

    with patch("custom_components.idm_heatpump.library_adapter.IdmModbusConnectionClient", side_effect=_fake_client):
        get_idm_client(host="10.0.0.5", port=502, slave_id=1, timeout=15.0, max_retries=2)

    assert captured["timeout"] == 15.0
    assert captured["max_retries"] == 2


def test_get_idm_client_omits_unset_optional_params() -> None:
    """When optional params are None, they must not be forwarded (library defaults take over)."""
    captured: dict = {}

    def _fake_client(*args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    with patch("custom_components.idm_heatpump.library_adapter.IdmModbusConnectionClient", side_effect=_fake_client):
        get_idm_client(host="10.0.0.5")

    assert "timeout" not in captured
    assert "max_retries" not in captured
    assert "message_spacing" not in captured
    assert "connect_delay" not in captured


def test_get_idm_client_forwards_connection_pacing() -> None:
    """Per-entry pacing must reach the library client as connection settings."""
    captured: dict = {}

    def _fake_client(*args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    with patch("custom_components.idm_heatpump.library_adapter.IdmModbusConnectionClient", side_effect=_fake_client):
        get_idm_client(host="10.0.0.5", message_spacing=0.1, connect_delay=2.0)

    assert captured["message_spacing"] == 0.1
    assert captured["connect_delay"] == 2.0


def test_integer_register_numbers_use_whole_number_steps() -> None:
    """Issue #158: UCHAR limits must not offer invalid half-degree values."""
    registers = {
        "hc_a_heating_limit": RegisterDef(
            address=1442,
            datatype=DataType.UCHAR,
            name="hc_a_heating_limit",
            unit="°C",
            writable=True,
            min_val=0,
            max_val=50,
        ),
        "hc_a_cooling_limit": RegisterDef(
            address=1484,
            datatype=DataType.UCHAR,
            name="hc_a_cooling_limit",
            unit="°C",
            writable=True,
            min_val=0,
            max_val=36,
        ),
    }

    descriptions = {item["register"].name: item["description"] for item in _numbers_from_register_map(registers)}

    assert descriptions["hc_a_heating_limit"].native_step == 1.0
    assert descriptions["hc_a_heating_limit"].native_min_value == 0
    assert descriptions["hc_a_heating_limit"].native_max_value == 50
    assert descriptions["hc_a_cooling_limit"].native_step == 1.0
    assert descriptions["hc_a_cooling_limit"].native_min_value == 0
    assert descriptions["hc_a_cooling_limit"].native_max_value == 36


def test_all_integer_register_datatypes_use_whole_number_steps() -> None:
    """Every integer datatype accepted as a Number must reject fractional UI input."""
    datatypes = (
        DataType.UCHAR,
        DataType.INT8,
        DataType.INT16,
        DataType.UINT16,
        DataType.BITFLAG,
    )
    registers = {
        f"integer_{datatype.value.lower()}": RegisterDef(
            address=2000 + index,
            datatype=datatype,
            name=f"integer_{datatype.value.lower()}",
            writable=True,
        )
        for index, datatype in enumerate(datatypes)
    }

    descriptions = _numbers_from_register_map(registers)

    assert len(descriptions) == len(datatypes)
    assert all(item["description"].native_step == 1.0 for item in descriptions)


def test_float_register_number_defaults_and_overrides_remain_unchanged() -> None:
    """Datatype-derived integer steps must preserve float and metadata steps."""
    registers = {
        "dhw_setpoint": RegisterDef(
            address=1250,
            datatype=DataType.FLOAT,
            name="dhw_setpoint",
            writable=True,
        ),
        "power_limit_hp": RegisterDef(
            address=4108,
            datatype=DataType.FLOAT,
            name="power_limit_hp",
            writable=True,
        ),
    }

    descriptions = {item["register"].name: item["description"] for item in _numbers_from_register_map(registers)}

    assert descriptions["dhw_setpoint"].native_step == 0.5
    assert descriptions["power_limit_hp"].native_step == 0.1


def test_heating_curve_step_matches_its_narrow_value_range() -> None:
    """The heating curve spans 0.1-3.5, so the FLOAT default step of 0.5 is unusable."""
    registers = {
        f"hc_{circuit}_heating_curve": RegisterDef(
            address=1429 + index * 2,
            datatype=DataType.FLOAT,
            name=f"hc_{circuit}_heating_curve",
            writable=True,
            min_val=0.1,
            max_val=3.5,
        )
        for index, circuit in enumerate("abcdefg")
    }

    descriptions = {item["register"].name: item["description"] for item in _numbers_from_register_map(registers)}

    for circuit in "abcdefg":
        description = descriptions[f"hc_{circuit}_heating_curve"]
        assert description.native_step == 0.1
        # Common settings such as 0.3 must be reachable from the minimum.
        assert round((0.3 - description.native_min_value) / description.native_step, 6).is_integer()
        # The range itself stays the library's — device knowledge lives in the API.
        assert description.native_min_value == 0.1
        assert description.native_max_value == 3.5


def test_heating_curve_parameters_are_expert_entities_for_new_installations() -> None:
    """Curve-shaping registers must not be created enabled on a fresh install."""
    expert = ("heating_curve", "parallel_shift", "setpoint_flow_constant", "setpoint_flow_cooling")
    comfort = ("room_setpoint_heat_normal", "room_setpoint_heat_eco", "ext_room_temp", "heating_limit")
    registers = {
        f"hc_a_{suffix}": RegisterDef(
            address=1400 + index,
            datatype=DataType.FLOAT,
            name=f"hc_a_{suffix}",
            writable=True,
        )
        for index, suffix in enumerate((*expert, *comfort))
    }

    descriptions = {item["register"].name: item["description"] for item in _numbers_from_register_map(registers)}

    for suffix in expert:
        assert descriptions[f"hc_a_{suffix}"].entity_registry_enabled_default is False, suffix
    for suffix in comfort:
        assert descriptions[f"hc_a_{suffix}"].entity_registry_enabled_default is True, suffix


def test_library_register_limits_are_not_duplicated_in_metadata() -> None:
    """Ranges belong to the API; the overlay may only carry presentation data."""
    from custom_components.idm_heatpump.adapter_metadata import NUMBER_METADATA

    for name, meta in NUMBER_METADATA.items():
        if not name.startswith("hc_"):
            continue
        assert "min" not in meta and "max" not in meta, (
            f"{name} redefines a range that idm-heatpump-api already provides as min_val/max_val"
        )
