"""Navigator 1.0/1.7 holding-block entities: selects, numbers, naming.

The official RW holding table of ma_de_812049 Rev.1 (API 2.4.0) is exposed
through the same library adapters as the shared family. These tests pin the
entity surface for the 1.x map: the mode selects with their own enum slugs,
the writable numbers with the officially documented ranges, and the German
naming of the registers that are new with that table.
"""

import pytest
from idm_heatpump import MODEL_NAVIGATOR_17, IdmModelInfo, build_register_map

from custom_components.idm_heatpump.adapter_enums import get_slug_map_and_key
from custom_components.idm_heatpump.adapter_names import _get_german_name
from custom_components.idm_heatpump.library_adapter import (
    get_library_numbers,
    get_library_selects,
)


def _navigator_17_model_info(*, has_pv: bool = True) -> IdmModelInfo:
    return IdmModelInfo(
        model_name=MODEL_NAVIGATOR_17,
        active_heating_circuits=[],
        zone_modules=0,
        has_solar=False,
        has_isc=False,
        has_pv=has_pv,
        has_cascade=False,
    )


def _selects() -> dict[str, dict]:
    return {item["description"].key: item for item in get_library_selects(model_info=_navigator_17_model_info())}


def _numbers() -> dict[str, dict]:
    return {item["description"].key: item for item in get_library_numbers(model_info=_navigator_17_model_info())}


def test_1_7_holding_modes_become_selects() -> None:
    selects = _selects()
    assert "system_mode_17" in selects
    assert "solar_operating_mode_17" in selects
    for letter in "abcdefg":
        assert f"hc_{letter}_operating_mode" in selects


def test_1_7_selects_use_their_own_enum_slugs() -> None:
    slugs, key = get_slug_map_and_key("system_mode_17")
    assert slugs == {0: "standby", 1: "automatic", 2: "hot_water", 3: "hot_water_once"}
    assert key == "system_mode_17"

    # All circuits share one translation key with a {circuit} placeholder.
    slugs_a, key_a = get_slug_map_and_key("hc_a_operating_mode")
    _slugs_g, key_g = get_slug_map_and_key("hc_g_operating_mode")
    assert slugs_a == {0: "off", 1: "time_program", 2: "normal", 3: "eco", 4: "heating_only"}
    assert key_a == key_g == "hc_operating_mode"

    slugs, key = get_slug_map_and_key("solar_operating_mode_17")
    assert slugs == {
        0: "automatic",
        1: "domestic_water",
        2: "heat_storage",
        3: "domestic_water_and_heat_storage",
        4: "heat_source_pool",
    }
    assert key == "solar_operating_mode_17"

    # The 1.7 value sets must not leak into the shared family's slug maps.
    _, shared_key = get_slug_map_and_key("system_mode")
    assert shared_key == "system_mode"
    assert get_slug_map_and_key("system_mode")[0] != slugs


def test_1_7_select_options_are_translated() -> None:
    """Every slug of the new selects has an English and German state label."""
    import json
    from pathlib import Path

    translations = Path("custom_components/idm_heatpump/translations")
    en = json.loads((translations / "en.json").read_text(encoding="utf-8"))["entity"]["select"]
    de = json.loads((translations / "de.json").read_text(encoding="utf-8"))["entity"]["select"]

    for register_name in ("system_mode_17", "solar_operating_mode_17", "hc_a_operating_mode"):
        slugs, key = get_slug_map_and_key(register_name)
        for slug in slugs.values():
            assert slug in en[key]["state"], f"en.json select.{key}.{slug} missing"
            assert slug in de[key]["state"], f"de.json select.{key}.{slug} missing"


def test_1_7_holding_numbers_carry_official_ranges() -> None:
    numbers = _numbers()
    expected = {
        "bivalence_point_1_17": (-20.0, 20.0),
        "bivalence_point_2_17": (-20.0, 20.0),
        "external_demand_temp_heating": (20.0, 65.0),
        "external_demand_temp_cooling": (10.0, 25.0),
        "dhw_setpoint": (35.0, 60.0),
        "hc_a_room_setpoint_heat_normal": (15.0, 30.0),
        "hc_g_room_setpoint_heat_eco": (10.0, 25.0),
        "hc_a_heating_curve": (0.1, 3.5),
        "hc_g_heating_limit": (0.0, 50.0),
        "hc_a_setpoint_flow_constant": (20.0, 90.0),
        "hc_g_cooling_limit": (0.0, 36.0),
        "hc_a_setpoint_flow_cooling": (8.0, 30.0),
        "hc_g_room_setpoint_cool_normal": (15.0, 30.0),
    }
    for name, (min_val, max_val) in expected.items():
        assert name in numbers, name
        desc = numbers[name]["description"]
        assert desc.native_min_value == min_val, name
        assert desc.native_max_value == max_val, name


def test_1_7_dhw_setpoint_is_the_captured_float_pair() -> None:
    """FW030 (issue #364): a float spanning 2152-2153, not a single word.

    Firmware N1.MLj answers 2152/2153 with (0, 0x4238) = 46.0 degC; the
    number entity must carry the library's FLOAT register so reads and
    writes use the pair, and the half-step FLOAT default while the library
    provides no explicit step.
    """
    reg_map = build_register_map(model_info=_navigator_17_model_info())
    dhw = reg_map["dhw_setpoint"]
    assert dhw.address == 2152
    assert dhw.size == 2

    numbers = _numbers()
    desc = numbers["dhw_setpoint"]["description"]
    assert desc.native_step == 0.5
    assert (desc.native_min_value, desc.native_max_value) == (35.0, 60.0)


def test_1_7_heating_curve_step_is_the_controller_grid() -> None:
    """The curve steps by 0.05 (issue #364: a plant runs 0.35, UI steps 0.05)."""
    numbers = _numbers()
    for letter in "abcdefg":
        desc = numbers[f"hc_{letter}_heating_curve"]["description"]
        assert desc.native_step == 0.05
        assert round((0.35 - desc.native_min_value) / desc.native_step, 6).is_integer()


def test_1_7_holding_registers_are_not_sensors() -> None:
    """Writable holding parameters expose controls, not sensor duplicates."""
    from custom_components.idm_heatpump.library_adapter import get_library_sensors

    sensors = {item["description"].key for item in get_library_sensors(model_info=_navigator_17_model_info())}
    for name in ("system_mode_17", "hc_a_operating_mode", "dhw_setpoint", "bivalence_point_1_17"):
        assert name not in sensors, name


async def test_1_7_water_heater_uses_dhw_temp_and_the_float_setpoint() -> None:
    """The 1.x family gets the water heater card since FW030 works (b16).

    The shared family reports dhw_temp_top; the 1.x map offers the tank
    temperature (dhw_temp) instead, and its dhw_setpoint became the captured
    float pair in b14. The entity must pick up both and carry the register's
    documented bounds.
    """
    from unittest.mock import AsyncMock, MagicMock

    from custom_components.idm_heatpump.water_heater import IdmWaterHeater, async_setup_entry

    reg_map = build_register_map(model_info=_navigator_17_model_info())
    coordinator = MagicMock()
    coordinator.get_register = MagicMock(side_effect=lambda name: reg_map.get(name))
    coordinator.async_write_register = AsyncMock()
    entry = MagicMock()
    entry.runtime_data.coordinator = coordinator

    added: list = []
    await async_setup_entry(MagicMock(), entry, MagicMock(side_effect=added.extend))

    assert len(added) == 1
    entity = added[0]
    assert isinstance(entity, IdmWaterHeater)
    assert entity._current_reg.name == "dhw_temp"
    assert entity._target_reg.name == "dhw_setpoint"
    assert (entity.min_temp, entity.max_temp) == (35.0, 60.0)
    # The float setpoint carries no library step hint, so the half-step
    # default applies.
    assert entity._attr_target_temperature_step == 0.5


def test_1_7_new_registers_have_german_names() -> None:
    assert _get_german_name("system_mode_17") == "Betriebsart System"
    assert _get_german_name("hc_a_operating_mode") == "Betriebsart HK A"
    # The per-circuit fan-out derives B-G from the A entry.
    assert _get_german_name("hc_g_operating_mode") == "Betriebsart HK G"
    assert _get_german_name("bivalence_point_1_17") == "Bivalenzpunkt 1"
    assert _get_german_name("bivalence_point_2_17") == "Bivalenzpunkt 2"
    assert _get_german_name("external_demand_temp_heating") == "Externe Anforderungstemperatur Heizen"
    assert _get_german_name("external_demand_temp_cooling") == "Externe Anforderungstemperatur Kühlen"
    assert _get_german_name("solar_operating_mode_17") == "Betriebsart Solar"


def test_1_7_map_registers_exist_in_library_map() -> None:
    reg_map = build_register_map(model_info=_navigator_17_model_info())
    for name in (
        "system_mode_17",
        "hc_g_operating_mode",
        "solar_operating_mode_17",
        "bivalence_point_2_17",
        "external_demand_temp_heating",
        "dhw_setpoint",
    ):
        assert name in reg_map, name
    # The holding block is independent of the PV supplement.
    without_pv = build_register_map(model_info=_navigator_17_model_info(has_pv=False))
    assert "system_mode_17" in without_pv
    assert "pv_surplus" not in without_pv


@pytest.mark.parametrize(
    ("register_name", "expected_key"),
    [
        ("system_mode_17", "system_mode_17"),
        ("hc_a_operating_mode", "hc_operating_mode"),
        ("hc_g_operating_mode", "hc_operating_mode"),
        ("solar_operating_mode_17", "solar_operating_mode_17"),
        ("bivalence_point_1_17", "bivalence_point_1_17"),
    ],
)
def test_1_7_translation_keys_resolve(register_name: str, expected_key: str) -> None:
    from custom_components.idm_heatpump.entity_names import translation_key_for_register

    assert translation_key_for_register(register_name) == expected_key


# ---------------------------------------------------------------------------
# FC01/FC05 coil block (3000-3003) of ma_de_812049 Rev.1
# ---------------------------------------------------------------------------


def test_1_7_momentary_coils_never_become_entities() -> None:
    """c3001-c3003 are momentary command bits, not status (issue #319 report).

    The controller executes the request as soon as the bit is set and the bit
    immediately falls back to 0 — a binary sensor built from it can never turn
    on and only adds a pointless coil poll. None of the three may become a
    binary sensor or a numeric sensor on any idm-heatpump-api version: the
    exclusion is the integration's own until the API map drops them.
    """
    from custom_components.idm_heatpump.library_adapter import (
        get_library_binary_sensors,
        get_library_sensors,
    )

    model_info = _navigator_17_model_info()
    binary = {item["description"].key for item in get_library_binary_sensors(model_info=model_info)}
    sensors = {item["description"].key for item in get_library_sensors(model_info=model_info)}
    for name in ("demand_heating_17", "demand_cooling_17", "demand_dhw_17"):
        assert name not in binary, name
        assert name not in sensors, name


async def test_1_7_dhw_priority_button_writes_coil_3003() -> None:
    """c3003 (Vorrangladung anfordern) is a button writing ON exactly once.

    A switch would also write 0, and a momentary command bit must never be
    reset by the integration. The button resolves the register by name from
    the detected model map, exactly like the acknowledge button for c3000.
    """
    from dataclasses import replace
    from unittest.mock import AsyncMock, MagicMock

    from custom_components.idm_heatpump.button import async_setup_entry

    reg_map = dict(build_register_map(model_info=_navigator_17_model_info()))
    reg_map["demand_dhw_17"] = replace(reg_map["demand_dhw_17"], writable=True, write_only=True)
    coordinator = MagicMock()
    coordinator.get_register = MagicMock(side_effect=lambda name: reg_map.get(name))
    coordinator.async_write_register = AsyncMock()
    entry = MagicMock()
    entry.runtime_data.coordinator = coordinator

    added: list = []
    await async_setup_entry(MagicMock(), entry, MagicMock(side_effect=added.extend))

    buttons = [e for e in added if getattr(e, "_attr_translation_key", None) == "dhw_priority_charge"]
    assert len(buttons) == 1
    button = buttons[0]
    assert button._register.name == "demand_dhw_17"
    assert button._register.address == 3003

    await button.async_press()
    coordinator.async_write_register.assert_awaited_once()
    reg, value = coordinator.async_write_register.await_args.args
    assert reg is button._register
    assert value == 1


async def test_1_7_dhw_priority_button_requires_writable_coil() -> None:
    """The button gate is the register's writability, not the api version:
    a map modelling c3003 read-only (idm-heatpump-api before the write-only
    command) yields no button — the entity appears exactly with the map that
    marks the coil writable."""
    from dataclasses import replace
    from unittest.mock import AsyncMock, MagicMock

    from custom_components.idm_heatpump.button import async_setup_entry

    reg_map = dict(build_register_map(model_info=_navigator_17_model_info()))
    reg_map["demand_dhw_17"] = replace(reg_map["demand_dhw_17"], writable=False, write_only=False)
    coordinator = MagicMock()
    coordinator.get_register = MagicMock(side_effect=lambda name: reg_map.get(name))
    coordinator.async_write_register = AsyncMock()
    entry = MagicMock()
    entry.runtime_data.coordinator = coordinator

    added: list = []
    await async_setup_entry(MagicMock(), entry, MagicMock(side_effect=added.extend))
    assert not [e for e in added if getattr(e, "_attr_translation_key", None) == "dhw_priority_charge"]


def test_1_7_acknowledge_register_is_the_coil() -> None:
    """The 1.x acknowledge is coil c3000 (FC05), and it reuses the shared
    error_acknowledge name so the button and service resolve it by name."""
    from idm_heatpump import RegisterType

    reg_map = build_register_map(model_info=_navigator_17_model_info())
    reg = reg_map["error_acknowledge"]
    assert reg.address == 3000
    assert reg.register_type is RegisterType.COIL
    assert reg.writable is True
    assert reg.write_only is True


async def test_1_7_acknowledge_button_writes_coil_3000() -> None:
    """The acknowledge button on a Navigator 1.7 targets c3000 through the
    model map — not the synthetic holding-register fallback of the shared
    family (issue #319)."""
    from unittest.mock import AsyncMock, MagicMock

    from custom_components.idm_heatpump.button import IdmAcknowledgeErrorsButton, async_setup_entry

    reg_map = build_register_map(model_info=_navigator_17_model_info())
    coordinator = MagicMock()
    coordinator.get_register = MagicMock(side_effect=lambda name: reg_map.get(name))
    coordinator.async_write_register = AsyncMock()
    entry = MagicMock()
    entry.runtime_data.coordinator = coordinator

    added: list = []
    await async_setup_entry(MagicMock(), entry, MagicMock(side_effect=added.extend))

    buttons = [e for e in added if isinstance(e, IdmAcknowledgeErrorsButton)]
    assert len(buttons) == 1
    button = buttons[0]
    assert button._register.name == "error_acknowledge"
    assert button._register.address == 3000

    await button.async_press()
    coordinator.async_write_register.assert_awaited_once()
    reg, value = coordinator.async_write_register.await_args.args
    assert reg is button._register
    assert value == 1
    # No custom-register bypass: model availability stays validated.
    assert not coordinator.async_write_register.await_args.kwargs.get("allow_custom_register")


def test_1_7_coil_registers_have_german_names() -> None:
    assert _get_german_name("error_acknowledge") == "Fehlerquittierung"
