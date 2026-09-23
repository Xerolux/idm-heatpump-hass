"""Tests for the opt-in IDM device hierarchy."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import EntityDescription
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump import async_migrate_entry
from custom_components.idm_heatpump.config_flow import IdmHeatpumpConfigFlow
from custom_components.idm_heatpump.const import CONF_DEVICE_HIERARCHY, DOMAIN
from custom_components.idm_heatpump.coordinator import IdmCoordinator
from custom_components.idm_heatpump.device_hierarchy import (
    build_subdevice_info,
    precreate_main_device,
    resolve_device_scope,
)
from custom_components.idm_heatpump.entity import IdmCoordinatorEntityBase, IdmEntity


def _coordinator(*, enabled: bool = True) -> MagicMock:
    coordinator = MagicMock(spec=IdmCoordinator)
    coordinator.device_hierarchy_enabled = enabled
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "entry"
    coordinator.config_entry.title = "IDM"
    coordinator.model_name = "Navigator 10"
    coordinator.firmware_version = None
    coordinator.myidm_id = None
    coordinator.data = {"hc_b_flow_temp": 30.0}
    coordinator.unused_registers = set()
    coordinator.last_update_success = True
    coordinator.hierarchy_device_ids = {
        (DOMAIN, "entry"): "main-device-id",
        (DOMAIN, "entry_zone_module_2"): "zone-module-2-device-id",
    }
    # build_device_info delegates to the coordinator, and
    # set_hierarchy_device_ids has to land where hierarchy_device_ids reads, so
    # the mock gets the real implementations of both.
    coordinator._device_info_cache = None
    coordinator.device_info = lambda: IdmCoordinator.device_info(coordinator)
    coordinator.set_hierarchy_device_ids = lambda ids, _c=coordinator: setattr(_c, "hierarchy_device_ids", dict(ids))
    return coordinator


def test_resolves_heating_circuit_register_and_web_keys() -> None:
    assert resolve_device_scope("hc_b_flow_temp").primary == "B"
    assert resolve_device_scope("flow_temp_HK_D").primary == "D"
    assert resolve_device_scope("web_pump_heating_circuitA").primary == "A"


def test_resolves_zone_module_and_room_before_generic_zone_match() -> None:
    room = resolve_device_scope("zm3_room6_temp")
    module = resolve_device_scope("zm3_mode_heat_cool")

    assert room is not None
    assert room.kind == "zone_room"
    assert room.primary == "3"
    assert room.secondary == 6
    assert module is not None
    assert module.kind == "zone_module"
    assert module.primary == "3"


def test_unknown_entity_remains_on_main_device() -> None:
    assert resolve_device_scope("outdoor_temp") is None
    assert build_subdevice_info(_coordinator(), "outdoor_temp") is None


@pytest.mark.parametrize(
    ("key", "device_suffix"),
    [
        ("health_report", "health"),
        ("health_communication", "health"),
        ("weather_preheat_advice", "comfort"),
        ("heating_curve_advice", "comfort"),
        ("analysis_heat_pump_cycles_recorded", "analytics"),
        ("energy_cop_total", "analytics"),
        ("idm_api_version", "diagnostics"),
        ("modbus_consecutive_failures", "diagnostics"),
    ],
)
def test_nonregister_feature_entity_uses_its_subdevice(key: str, device_suffix: str) -> None:
    coordinator = _coordinator()
    entity = IdmCoordinatorEntityBase(coordinator)
    entity.entity_description = EntityDescription(key=key)

    assert entity.device_info["identifiers"] == {(DOMAIN, f"entry_module_{device_suffix}")}


def test_feature_devices_are_precreated_from_read_only_options() -> None:
    from custom_components.idm_heatpump.device_hierarchy import expected_subdevice_identifiers

    coordinator = _coordinator()
    coordinator.active_registers = []
    coordinator.web_supplement = None
    coordinator.config_entry.options = MappingProxyType({"health_monitor": True, "weather_preheat_advisory": True})

    assert expected_subdevice_identifiers(coordinator) == {
        (DOMAIN, "entry_module_analytics"),
        (DOMAIN, "entry_module_health"),
        (DOMAIN, "entry_module_comfort"),
        (DOMAIN, "entry_module_diagnostics"),
    }


@pytest.mark.parametrize(
    ("entity_key", "expected_kind", "expected_name"),
    [
        ("energy_cop_today", "analytics", "iDM Analytics"),
        ("analysis_heat_pump_cycles_today", "analytics", "iDM Analytics"),
        ("health_low_cop", "health", "iDM Health Monitor"),
        ("heating_curve_advice", "comfort", "iDM Comfort"),
    ],
)
def test_optional_feature_entities_have_separate_device_groups(
    entity_key: str, expected_kind: str, expected_name: str
) -> None:
    scope = resolve_device_scope(entity_key)
    assert scope is not None
    assert scope.kind == expected_kind

    info = build_subdevice_info(_coordinator(), entity_key)
    assert info is not None
    assert info["name"] == expected_name
    assert info["parent_device_id"] == "main-device-id"


def test_disabled_hierarchy_never_returns_subdevice() -> None:
    assert build_subdevice_info(_coordinator(enabled=False), "hc_a_flow_temp") is None
    assert build_subdevice_info(_coordinator(enabled=False), "zm1_room1_temp") is None


def test_heating_circuit_is_a_child_of_the_main_device() -> None:
    """A heating circuit is a logical part of the controller, not a device behind it."""
    info = build_subdevice_info(_coordinator(), "hc_b_flow_temp")

    assert info is not None
    assert info["identifiers"] == {(DOMAIN, "entry_heating_circuit_b")}
    assert info["name"] == "Heizkreis B"
    assert info["parent_device_id"] == "main-device-id"
    # A child device carries no hardware metadata of its own; Home Assistant
    # rejects these fields outright.
    assert "via_device_id" not in info
    assert "manufacturer" not in info
    assert "model" not in info


def test_zone_module_stays_an_ordinary_device_behind_the_controller() -> None:
    """A zone module is separate hardware, so the link is connectivity, not composition."""
    info = build_subdevice_info(_coordinator(), "zm2_mode_heat_cool")

    assert info is not None
    assert info["identifiers"] == {(DOMAIN, "entry_zone_module_2")}
    assert info["name"] == "Zonenmodul 2"
    assert info["via_device_id"] == "main-device-id"
    assert info["model"] == "Zonenmodul"
    assert "parent_device_id" not in info


def test_zone_room_is_a_child_of_its_zone_module() -> None:
    info = build_subdevice_info(_coordinator(), "zm2_room4_setpoint")

    assert info is not None
    assert info["identifiers"] == {(DOMAIN, "entry_zone_module_2_room_4")}
    assert info["name"] == "Zonenmodul 2 Raum 4"
    assert info["parent_device_id"] == "zone-module-2-device-id"
    assert "via_device_id" not in info


def test_hierarchy_falls_back_to_via_device_links_without_child_device_support() -> None:
    """Home Assistant 2026.8 has no child devices; the hierarchy still has to work."""
    with patch(
        "custom_components.idm_heatpump.device_hierarchy.child_devices_supported",
        return_value=False,
    ):
        circuit = build_subdevice_info(_coordinator(), "hc_b_flow_temp")
        room = build_subdevice_info(_coordinator(), "zm2_room4_setpoint")

    assert circuit is not None
    assert circuit["via_device_id"] == "main-device-id"
    assert circuit["model"] == "Heizkreis"
    assert "parent_device_id" not in circuit

    assert room is not None
    assert room["via_device_id"] == "zone-module-2-device-id"
    assert "parent_device_id" not in room


def test_child_device_falls_back_to_an_unlinked_device_when_the_parent_is_unknown() -> None:
    """A missing parent must not produce a child device without ``parent_device_id``.

    Home Assistant requires the parent to exist, so the entity is attached to an
    ordinary unlinked device this round; the next reload precreates the parent
    and the device is converted into a child, keeping its id.
    """
    coordinator = _coordinator()
    coordinator.hierarchy_device_ids = {}

    info = build_subdevice_info(coordinator, "hc_b_flow_temp")

    assert info is not None
    assert "parent_device_id" not in info
    assert "via_device_id" not in info
    assert info["identifiers"] == {(DOMAIN, "entry_heating_circuit_b")}


def test_register_entity_keeps_unique_id_when_moved_to_subdevice() -> None:
    coordinator = _coordinator()
    register = RegisterDef(
        address=1352,
        datatype=DataType.FLOAT,
        name="hc_b_flow_temp",
        unit="°C",
    )
    entity = IdmEntity(coordinator, register, EntityDescription(key=register.name))

    assert entity._attr_unique_id == "entry_hc_b_flow_temp"
    assert entity.device_info["identifiers"] == {(DOMAIN, "entry_heating_circuit_b")}


@pytest.mark.asyncio
async def test_migration_keeps_existing_installations_on_single_device() -> None:
    hass = MagicMock()
    entry = MagicMock()
    entry.version = 1
    entry.minor_version = 2
    entry.options = {"scan_interval": 10}

    assert await async_migrate_entry(hass, entry) is True

    update = hass.config_entries.async_update_entry.call_args.kwargs
    assert update["minor_version"] == 3
    assert update["options"][CONF_DEVICE_HIERARCHY] is False
    assert update["options"]["scan_interval"] == 10


@pytest.mark.asyncio
async def test_migration_preserves_explicit_hierarchy_choice() -> None:
    hass = MagicMock()
    entry = MagicMock()
    entry.version = 1
    entry.minor_version = 2
    entry.options = {CONF_DEVICE_HIERARCHY: True}

    assert await async_migrate_entry(hass, entry) is True

    update = hass.config_entries.async_update_entry.call_args.kwargs
    assert update["options"][CONF_DEVICE_HIERARCHY] is True


def test_new_config_entries_use_new_minor_version() -> None:
    assert IdmHeatpumpConfigFlow.MINOR_VERSION == 3


def test_missing_hierarchy_device_id_omits_via_device_id_link() -> None:
    """A subdevice built before precreate_main_device has run stays linkable.

    ``via_device_id`` is simply absent rather than crashing or pointing at a
    stale/guessed ID; the next precreate pass fills it in.
    """
    coordinator = _coordinator()
    coordinator.hierarchy_device_ids = {}

    info = build_subdevice_info(coordinator, "hc_b_flow_temp")

    assert info is not None
    assert "via_device_id" not in info


def _stub_registry() -> Any:
    """Return a fresh instance of the device-registry stub from ``conftest``.

    The stub enforces the constraints Home Assistant enforces — a parent must
    already be registered, a child device can't be a parent, reparenting is
    rejected — so precreate order is genuinely tested rather than assumed.
    """
    return type(dr.async_get(MagicMock()))()


def _precreate(coordinator: MagicMock, registry: Any) -> None:
    with patch(
        "custom_components.idm_heatpump.device_hierarchy.dr.async_get",
        return_value=registry,
    ):
        precreate_main_device(MagicMock(), coordinator)


def _hierarchy_coordinator() -> MagicMock:
    coordinator = _coordinator()
    coordinator.active_registers = [
        RegisterDef(address=1352, datatype=DataType.FLOAT, name="hc_b_flow_temp", unit="°C"),
        RegisterDef(address=2000, datatype=DataType.FLOAT, name="zm2_room4_setpoint", unit="°C"),
    ]
    coordinator.web_supplement = None
    coordinator.hierarchy_device_ids = {}
    return coordinator


def test_precreate_registers_the_main_device_then_modules_then_children() -> None:
    coordinator = _hierarchy_coordinator()
    registry = _stub_registry()

    _precreate(coordinator, registry)

    ids = coordinator.hierarchy_device_ids
    main_id = ids[(DOMAIN, "entry")]
    circuit_id = ids[(DOMAIN, "entry_heating_circuit_b")]
    module_id = ids[(DOMAIN, "entry_zone_module_2")]
    room_id = ids[(DOMAIN, "entry_zone_module_2_room_4")]

    assert len({main_id, circuit_id, module_id, room_id}) == 4
    # Composition hangs below the part it belongs to...
    assert registry.devices[circuit_id].parent_device_id == main_id
    assert registry.devices[room_id].parent_device_id == module_id
    # ...while the zone module stays an ordinary device linked by connectivity.
    assert registry.devices[module_id].parent_device_id is None


def test_precreate_converts_an_existing_subdevice_and_keeps_its_device_id() -> None:
    """Upgrading from a ``via_device_id`` hierarchy must not orphan entities.

    Home Assistant converts a device whose identifiers already exist into a
    child device and preserves its id, so entity links, areas and automations
    survive the switch.
    """
    coordinator = _hierarchy_coordinator()
    registry = _stub_registry()
    existing = registry.async_get_or_create(
        config_entry_id="entry",
        identifiers={(DOMAIN, "entry_heating_circuit_b")},
    )
    existing_id = existing.id

    _precreate(coordinator, registry)

    assert coordinator.hierarchy_device_ids[(DOMAIN, "entry_heating_circuit_b")] == existing_id
    assert registry.devices[existing_id].parent_device_id == coordinator.hierarchy_device_ids[(DOMAIN, "entry")]


def test_precreate_without_child_device_support_creates_ordinary_devices() -> None:
    coordinator = _hierarchy_coordinator()
    registry = _stub_registry()

    with patch(
        "custom_components.idm_heatpump.device_hierarchy.child_devices_supported",
        return_value=False,
    ):
        _precreate(coordinator, registry)

    ids = coordinator.hierarchy_device_ids
    assert set(ids) == {
        (DOMAIN, "entry"),
        (DOMAIN, "entry_heating_circuit_b"),
        (DOMAIN, "entry_zone_module_2"),
        (DOMAIN, "entry_zone_module_2_room_4"),
        # ``error_acknowledge`` is always offered, so the diagnostics module is
        # always justified.
        (DOMAIN, "entry_module_diagnostics"),
    }
    assert all(registry.devices[device_id].parent_device_id is None for device_id in ids.values())


# ---------------------------------------------------------------------------
# PV subdevice group (issue #353)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entity_key", "expected_suffix"),
    [
        ("pv_surplus", "pv"),
        ("pv_production", "pv"),
        ("pv_target_value", "pv"),
        ("smart_grid_status", "pv"),
        ("calculated_pv_surplus_operation", "pv"),
        ("web_demand_reason", "pv"),
        ("web_demand_reason_pv", "pv"),
        ("outdoor_temp", None),
        ("house_consumption", None),
        ("battery_soc", None),
        ("calculated_cop", "analytics"),
    ],
)
def test_pv_scope_routes_pv_entities_to_one_group(entity_key: str, expected_suffix: str) -> None:
    scope = resolve_device_scope(entity_key)
    if expected_suffix is None:
        assert scope is None
        return
    assert scope is not None
    assert scope.kind == expected_suffix

    info = build_subdevice_info(_coordinator(), entity_key)
    assert info is not None
    assert info["identifiers"] == {(DOMAIN, f"entry_module_{expected_suffix}")}
    if expected_suffix == "pv":
        assert info["name"] == "Photovoltaik"


def _register_named(name: str) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(name=name)


def test_pv_subdevice_is_a_child_of_the_main_device() -> None:
    from custom_components.idm_heatpump.device_hierarchy import SubdevicePlacement, expected_subdevices

    coordinator = _coordinator()
    coordinator.active_registers = [_register_named("pv_surplus")]
    coordinator.web_supplement = None

    expected = expected_subdevices(coordinator)
    placement = expected.get((DOMAIN, "entry_module_pv"))
    assert isinstance(placement, SubdevicePlacement)
    assert placement.kind == "pv"
    assert placement.is_child_device is True
    assert placement.parent == (DOMAIN, "entry")


def test_pv_subdevice_seeds_only_when_entities_can_exist() -> None:
    from custom_components.idm_heatpump.device_hierarchy import expected_subdevice_identifiers

    with_pv = _coordinator()
    with_pv.active_registers = [_register_named("pv_surplus")]
    with_pv.web_supplement = None
    assert (DOMAIN, "entry_module_pv") in expected_subdevice_identifiers(with_pv)

    without_pv = _coordinator()
    without_pv.active_registers = [_register_named("outdoor_temp")]
    without_pv.web_supplement = None
    assert (DOMAIN, "entry_module_pv") not in expected_subdevice_identifiers(without_pv)

    nav10_web = _coordinator()
    nav10_web.active_registers = [_register_named("outdoor_temp")]
    nav10_web.web_supplement = MagicMock(web_variant="nav10")
    assert (DOMAIN, "entry_module_pv") in expected_subdevice_identifiers(nav10_web)
