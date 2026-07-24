"""Cross-repo register-to-entity contract tests."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from idm_heatpump import MODEL_NAVIGATOR_10, MODEL_NAVIGATOR_20, IdmModelInfo, build_register_map

from custom_components.idm_heatpump.registers import (
    collect_all_registers,
    get_all_binary_sensor_descriptions,
    get_all_number_descriptions,
    get_all_select_descriptions,
    get_all_sensor_descriptions,
    get_all_switch_descriptions,
)

ALL_CIRCUITS = list("abcdefg")
ALL_ZONE_ROOMS = {idx: 6 for idx in range(10)}


def _navigator_10() -> IdmModelInfo:
    return IdmModelInfo(
        model_name=MODEL_NAVIGATOR_10,
        active_heating_circuits=[c.upper() for c in ALL_CIRCUITS],
        zone_modules=10,
        has_solar=True,
        has_isc=True,
        has_pv=True,
        has_cascade=True,
    )


def _navigator_20() -> IdmModelInfo:
    return IdmModelInfo(
        model_name=MODEL_NAVIGATOR_20,
        active_heating_circuits=["A"],
        zone_modules=0,
        has_solar=False,
        has_isc=False,
        has_pv=False,
        has_cascade=False,
    )


def _platform_descriptions(model_info: IdmModelInfo) -> dict[str, list[dict[str, Any]]]:
    return {
        "sensor": get_all_sensor_descriptions(ALL_CIRCUITS, 10, ALL_ZONE_ROOMS, True, model_info),
        "binary_sensor": get_all_binary_sensor_descriptions(ALL_CIRCUITS, 10, ALL_ZONE_ROOMS, True, model_info),
        "number": get_all_number_descriptions(ALL_CIRCUITS, 10, ALL_ZONE_ROOMS, True, model_info),
        "select": get_all_select_descriptions(ALL_CIRCUITS, 10, ALL_ZONE_ROOMS, True, model_info),
        "switch": get_all_switch_descriptions(ALL_CIRCUITS, 10, ALL_ZONE_ROOMS, True, model_info),
    }


def test_each_entity_description_uses_stable_register_key() -> None:
    for platform, descriptions in _platform_descriptions(_navigator_10()).items():
        keys: set[str] = set()
        for item in descriptions:
            reg = item["register"]
            desc = item["description"]
            assert desc.key == reg.name, f"{platform} description key drifted for {reg.name}"
            assert desc.key not in keys, f"{platform} has duplicate entity key {desc.key}"
            keys.add(desc.key)


def test_entity_descriptions_have_valid_measurement_metadata() -> None:
    descriptions = _platform_descriptions(_navigator_10())

    for item in descriptions["sensor"]:
        reg = item["register"]
        desc = item["description"]
        if reg.unit:
            assert desc.native_unit_of_measurement is not None, reg.name
        if getattr(desc, "device_class", None) is not None:
            assert getattr(desc, "state_class", None) is not None or reg.enum_options, reg.name

    for item in descriptions["number"]:
        desc = item["description"]
        assert desc.native_min_value <= desc.native_max_value, item["register"].name


def test_writable_registers_only_use_write_capable_platforms_or_glt_sensor_dual_exposure() -> None:
    descriptions = _platform_descriptions(_navigator_10())
    sensor_names = {item["register"].name for item in descriptions["sensor"]}
    write_platform_names = {
        item["register"].name for platform in ("number", "select", "switch") for item in descriptions[platform]
    }

    for name, reg in build_register_map(model_info=_navigator_10()).items():
        if not reg.writable or reg.write_only:
            continue
        assert name in write_platform_names, f"{name} is writable but has no write-capable entity"
        if name in sensor_names:
            assert (
                name.startswith("pv_")
                or "_room" in name
                or name
                in {
                    "house_consumption",
                    "battery_discharge",
                    "battery_soc",
                    "electric_heater_power",
                }
            )


def test_address_duplicates_are_documented_aliases_only() -> None:
    registers = collect_all_registers(ALL_CIRCUITS, 10, ALL_ZONE_ROOMS, True, _navigator_10())
    names_by_address: dict[int, list[str]] = defaultdict(list)
    for reg in registers:
        names_by_address[reg.address].append(reg.name)

    duplicates = {address: sorted(names) for address, names in names_by_address.items() if len(set(names)) > 1}

    assert duplicates == {}


def test_navigator_20_excludes_navigator_10_entities() -> None:
    model_info = _navigator_20()
    descriptions = _platform_descriptions(model_info)
    entity_names = {
        item["register"].name for platform_descriptions in descriptions.values() for item in platform_descriptions
    }

    assert "outdoor_temp" in entity_names
    assert "power_limit_hp" not in entity_names
    assert "heat_sink_flow_rate" not in entity_names
