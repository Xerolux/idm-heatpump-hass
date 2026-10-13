"""Tests for small Home Assistant adapter helper modules."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
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
from custom_components.idm_heatpump.adapter_glt import (
    is_external_power_measurement,
    is_glt_measurement,
    is_zone_room_measurement,
)
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
    """Option labels live under the entity translation key of the register.

    The keys carry the circuit letter and the zone/room indexes as placeholders,
    so every heating circuit shares one key instead of one key per circuit.
    """
    system_slugs, system_key = get_slug_map_and_key("system_mode")
    room_slugs, room_key = get_slug_map_and_key("zm1_room2_mode")
    circuit_slugs, circuit_key = get_slug_map_and_key("hc_a_mode")
    active_slugs, active_key = get_slug_map_and_key("hc_b_active_mode")

    assert system_key == "system_mode"
    assert system_slugs is not None
    assert system_slugs[1] == "automatic"
    assert room_key == "zone_room_mode"
    assert room_slugs is not None
    assert room_slugs[1] == "automatic"
    assert circuit_key == "hc_mode"
    assert circuit_slugs is not None
    assert circuit_slugs[255] == "not_configured"
    assert active_key == "hc_active_mode"
    assert active_slugs == circuit_slugs


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
    assert is_external_power_measurement("pv_surplus")
    assert is_external_power_measurement("battery_soc")
    assert not is_external_power_measurement("zm2_room3_humidity")
    assert not is_external_power_measurement("hc_a_mode")


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
    """The heating curve spans 0.1-3.5, so the FLOAT default step of 0.5 is unusable.

    The step is device knowledge and comes from the library's
    `RegisterDef.step` hint (0.05 since idm-heatpump-api 2.4.3, issue #364:
    the controller UI steps by 0.05 and a real plant runs 0.35).
    """
    registers = {
        f"hc_{circuit}_heating_curve": RegisterDef(
            address=1429 + index * 2,
            datatype=DataType.FLOAT,
            name=f"hc_{circuit}_heating_curve",
            writable=True,
            min_val=0.1,
            max_val=3.5,
            step=0.05,
        )
        for index, circuit in enumerate("abcdefg")
    }

    descriptions = {item["register"].name: item["description"] for item in _numbers_from_register_map(registers)}

    for circuit in "abcdefg":
        description = descriptions[f"hc_{circuit}_heating_curve"]
        assert description.native_step == 0.05
        # Common settings such as 0.3 and 0.35 must be reachable from the minimum.
        for value in (0.3, 0.35):
            assert round((value - description.native_min_value) / description.native_step, 6).is_integer()
        # The range itself stays the library's — device knowledge lives in the API.
        assert description.native_min_value == 0.1
        assert description.native_max_value == 3.5


def test_library_step_hint_reaches_the_number_entity() -> None:
    """A register with a library step hint must expose it without any overlay."""
    registers = {
        "hinted": RegisterDef(
            address=2000,
            datatype=DataType.FLOAT,
            name="hinted",
            writable=True,
            step=0.25,
        ),
        "unhinted": RegisterDef(
            address=2002,
            datatype=DataType.FLOAT,
            name="unhinted",
            writable=True,
        ),
    }

    descriptions = {item["register"].name: item["description"] for item in _numbers_from_register_map(registers)}

    assert descriptions["hinted"].native_step == 0.25
    assert descriptions["unhinted"].native_step == 0.5


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


def test_coerce_sensor_state_class_passes_none_and_unknown_through() -> None:
    """Neutral state-class strings map to HA enum values; anything else degrades to None."""
    from custom_components.idm_heatpump.library_adapter import _coerce_sensor_state_class

    assert _coerce_sensor_state_class(None) is None
    assert _coerce_sensor_state_class("measurement") == "measurement"
    assert _coerce_sensor_state_class("total_increasing") == "total_increasing"
    assert _coerce_sensor_state_class("bogus_state_class") is None


def test_clone_register_for_room_rejects_non_zone_room_register() -> None:
    """Cloning is only defined for zm<zone>_room<room>_* registers."""
    from custom_components.idm_heatpump.library_adapter import _clone_register_for_room

    reg = RegisterDef(address=100, datatype=DataType.FLOAT, name="pv_surplus")

    with pytest.raises(ValueError, match="not a zone room register"):
        _clone_register_for_room(reg, 7, 120)


def test_clone_register_for_room_supports_non_dataclass_registers() -> None:
    """Older idm-heatpump-api releases ship duck-typed registers without dataclass support.

    ``dataclasses.replace`` rejects those with a TypeError; the clone helper
    must fall back to building a fresh ``RegisterDef`` from the attributes.
    """
    from custom_components.idm_heatpump.library_adapter import _clone_register_for_room

    class _LegacyNonDataclassRegister:
        """Duck-typed register as shipped by pre-dataclass API releases."""

        address = 300
        datatype = DataType.FLOAT
        name = "zm1_room6_temp"
        unit = "°C"
        multiplier = 0.1
        enum_options = None
        writable = True
        binary = False
        write_only = False
        exclude_from_write = None
        icon = None
        min_val = 5.0
        max_val = 35.0
        enabled_by_default = True
        state_class = None

    clone = _clone_register_for_room(_LegacyNonDataclassRegister(), 7, 310)

    assert isinstance(clone, RegisterDef)
    assert clone.name == "zm1_room7_temp"
    assert clone.address == 310
    assert clone.unit == "°C"
    assert clone.multiplier == 0.1
    assert clone.writable is True
    assert clone.min_val == 5.0
    assert clone.max_val == 35.0


def test_get_zone_module_registers_reraises_library_value_error_for_small_room_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A library rejection for a supported room count is a real error, not a trigger to extend."""
    import custom_components.idm_heatpump.library_adapter as adapter

    def _reject(zone_idx: int, room_count: int = 6) -> dict:
        raise ValueError(f"rooms must be 1-6, got {room_count}")

    monkeypatch.setattr(adapter, "_library_get_zone_module_registers", _reject)

    with pytest.raises(ValueError, match="rooms must be 1-6"):
        adapter._get_zone_module_registers(1, 6)


def test_get_library_sensors_skips_write_only_glt_registers(monkeypatch: pytest.MonkeyPatch) -> None:
    """A write-only GLT demand never becomes a sensor, unlike writable GLT measurements."""
    import custom_components.idm_heatpump.library_adapter as adapter

    registers = {
        "outside_air_temperature": RegisterDef(
            address=100,
            datatype=DataType.FLOAT,
            name="outside_air_temperature",
            unit="°C",
        ),
        "pv_production": RegisterDef(
            address=104,
            datatype=DataType.FLOAT,
            name="pv_production",
            writable=True,
        ),
        "pv_surplus": RegisterDef(
            address=106,
            datatype=DataType.FLOAT,
            name="pv_surplus",
            writable=True,
            write_only=True,
        ),
    }
    monkeypatch.setattr(adapter, "build_filtered_register_map", lambda *args, **kwargs: dict(registers))

    names = {item["register"].name for item in adapter.get_library_sensors()}

    assert "outside_air_temperature" in names
    # A writable GLT measurement is dual-exposed as a sensor and a number.
    assert "pv_production" in names
    # A write-only GLT demand is a command target, never a measurement display.
    assert "pv_surplus" not in names


def test_heating_circuit_sensor_generator_survives_library_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """One unknown circuit must not tear down the whole sensor platform setup."""
    import custom_components.idm_heatpump.library_adapter as adapter

    def _explode(circuit: str) -> dict:
        raise RuntimeError(f"unknown circuit {circuit}")

    monkeypatch.setattr(adapter, "get_heating_circuit_registers", _explode)

    assert adapter.get_library_heating_circuit_sensors("z") == []


def test_zone_generators_survive_library_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every per-zone generator degrades to an empty list when the library rejects the zone."""
    import custom_components.idm_heatpump.library_adapter as adapter

    def _reject(zone_idx: int, room_count: int = 6) -> dict:
        raise ValueError(f"zone {zone_idx} not configured")

    monkeypatch.setattr(adapter, "_library_get_zone_module_registers", _reject)

    assert adapter.get_library_zone_sensors(1) == []
    assert adapter.get_library_zone_binary_sensors(1) == []
    assert adapter.get_library_zone_selects(1) == []
    assert adapter.get_library_zone_numbers(1) == []


def test_selects_from_register_map_skips_write_only_registers() -> None:
    """A write-only enum register is an action target, not a selectable state."""
    from custom_components.idm_heatpump.library_adapter import _selects_from_register_map

    registers = {
        "custom_write_trigger": RegisterDef(
            address=200,
            datatype=DataType.UCHAR,
            name="custom_write_trigger",
            writable=True,
            write_only=True,
            enum_options={0: "Idle", 1: "Fire"},
        ),
    }

    assert _selects_from_register_map(registers) == []


def test_selects_from_register_map_falls_back_to_library_options_without_slug_map() -> None:
    """Registers without a translation slug map expose their library labels as options."""
    from custom_components.idm_heatpump.library_adapter import _selects_from_register_map

    registers = {
        "custom_demand_mode": RegisterDef(
            address=200,
            datatype=DataType.UCHAR,
            name="custom_demand_mode",
            writable=True,
            enum_options={0: "Normal", 1: "Boost", 255: "Reserved"},
            exclude_from_write={255},
        ),
        "custom_output_level": RegisterDef(
            address=202,
            datatype=DataType.UCHAR,
            name="custom_output_level",
            writable=True,
            enum_options={0: "Low", 1: "High"},
        ),
    }

    descriptions = {item["register"].name: item["description"] for item in _selects_from_register_map(registers)}

    # exclude_from_write values drop out even without a slug map.
    assert descriptions["custom_demand_mode"].options == ["Normal", "Boost"]
    # Without exclusions the library options pass through in declared order.
    assert descriptions["custom_output_level"].options == ["Low", "High"]


def test_icon_helper_maps_heat_sink_and_percentage_fallbacks() -> None:
    """The icon helper covers the heat-sink and generic percentage branches."""
    from custom_components.idm_heatpump.adapter_descriptions import get_icon_for_register

    assert get_icon_for_register("heat_sink_flow_temp") == "mdi:heat-pump"
    assert get_icon_for_register("heat_sink_return_temp") == "mdi:heat-pump"
    # A name without any known fragment and a percent unit stays a gauge.
    assert get_icon_for_register("some_fill_level", "%") == "mdi:gauge"


def test_name_kwargs_falls_back_to_the_options_translation_key() -> None:
    """An untranslated register keeps its fallback name plus the enum option key.

    A register that a newer idm-heatpump-api release adds before a translation
    exists must still expose selectable option labels through ``options_key``.
    """
    from custom_components.idm_heatpump.adapter_descriptions import name_kwargs

    kwargs = name_kwargs(
        "brand_new_technical_value",
        "Brand new technical value",
        options_key="custom_options_key",
    )

    assert kwargs == {
        "name": "Brand new technical value",
        "translation_key": "custom_options_key",
    }
    # A translated register is named through its own key only.
    assert name_kwargs("outdoor_temp", "Außentemperatur") == {"translation_key": "outdoor_temp"}
