"""Tests for optional IDM module devices in the hierarchy."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.idm_heatpump.const import DOMAIN
from custom_components.idm_heatpump.coordinator import IdmCoordinator
from custom_components.idm_heatpump.device_hierarchy import (
    build_subdevice_info,
    expected_subdevice_identifiers,
    resolve_device_scope,
)


def _coordinator(*, registers: tuple[str, ...] = ()) -> MagicMock:
    coordinator = MagicMock(spec=IdmCoordinator)
    coordinator.device_hierarchy_enabled = True
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "entry"
    coordinator._registers = [MagicMock(name=key) for key in registers]
    for register, key in zip(coordinator._registers, registers, strict=True):
        register.name = key
    coordinator.web_supplement = None
    return coordinator


def test_optional_module_scopes_are_resolved_from_verified_prefixes() -> None:
    assert resolve_device_scope("solar_collector_temp").kind == "solar"
    assert resolve_device_scope("isc_mode").kind == "isc"
    assert resolve_device_scope("cascade_power_heating").kind == "cascade"


def test_auxiliary_heat_scope_covers_modbus_and_web_keys() -> None:
    for key in (
        "bivalence_state",
        "booster_fault",
        "failure_eheating",
        "heat_generator_2nd",
        "runtime_second_heat_generator_hours",
        "switch_cycles_second_heat_generator",
    ):
        scope = resolve_device_scope(key)
        assert scope is not None
        assert scope.kind == "auxiliary_heat"


def test_optional_module_devices_are_linked_to_navigator() -> None:
    coordinator = _coordinator()

    solar = build_subdevice_info(coordinator, "solar_collector_temp")
    isc = build_subdevice_info(coordinator, "isc_mode")
    cascade = build_subdevice_info(coordinator, "cascade_power_heating")
    auxiliary = build_subdevice_info(coordinator, "failure_eheating")

    assert solar is not None
    assert solar["identifiers"] == {(DOMAIN, "entry_module_solar")}
    assert solar["name"] == "Solaranlage"
    assert solar["via_device"] == (DOMAIN, "entry")

    assert isc is not None
    assert isc["identifiers"] == {(DOMAIN, "entry_module_isc")}
    assert isc["via_device"] == (DOMAIN, "entry")

    assert cascade is not None
    assert cascade["identifiers"] == {(DOMAIN, "entry_module_cascade")}
    assert cascade["via_device"] == (DOMAIN, "entry")

    assert auxiliary is not None
    assert auxiliary["identifiers"] == {(DOMAIN, "entry_module_auxiliary_heat")}
    assert auxiliary["via_device"] == (DOMAIN, "entry")


def test_expected_modules_are_created_only_when_sources_exist() -> None:
    coordinator = _coordinator(
        registers=(
            "solar_collector_temp",
            "isc_mode",
            "cascade_power_heating",
            "bivalence_state",
        )
    )

    assert expected_subdevice_identifiers(coordinator) == {
        (DOMAIN, "entry_module_solar"),
        (DOMAIN, "entry_module_isc"),
        (DOMAIN, "entry_module_cascade"),
        (DOMAIN, "entry_module_auxiliary_heat"),
    }


def test_unrelated_entities_remain_on_main_device() -> None:
    coordinator = _coordinator()

    assert resolve_device_scope("outdoor_temp") is None
    assert build_subdevice_info(coordinator, "outdoor_temp") is None
