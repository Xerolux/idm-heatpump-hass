"""Tests for the opt-in IDM device hierarchy."""

from __future__ import annotations

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
from custom_components.idm_heatpump.entity import IdmEntity


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
    coordinator._device_info_cache = None
    coordinator._hierarchy_device_ids = {
        (DOMAIN, "entry"): "main-device-id",
        (DOMAIN, "entry_zone_module_2"): "zone-module-2-device-id",
    }
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
    coordinator._hierarchy_device_ids = {}

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
    coordinator._hierarchy_device_ids = {}

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
    coordinator._registers = [
        RegisterDef(address=1352, datatype=DataType.FLOAT, name="hc_b_flow_temp", unit="°C"),
        RegisterDef(address=2000, datatype=DataType.FLOAT, name="zm2_room4_setpoint", unit="°C"),
    ]
    coordinator.web_supplement = None
    coordinator._hierarchy_device_ids = {}
    return coordinator


def test_precreate_registers_the_main_device_then_modules_then_children() -> None:
    coordinator = _hierarchy_coordinator()
    registry = _stub_registry()

    _precreate(coordinator, registry)

    ids = coordinator._hierarchy_device_ids
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

    assert coordinator._hierarchy_device_ids[(DOMAIN, "entry_heating_circuit_b")] == existing_id
    assert registry.devices[existing_id].parent_device_id == coordinator._hierarchy_device_ids[(DOMAIN, "entry")]


def test_precreate_without_child_device_support_creates_ordinary_devices() -> None:
    coordinator = _hierarchy_coordinator()
    registry = _stub_registry()

    with patch(
        "custom_components.idm_heatpump.device_hierarchy.child_devices_supported",
        return_value=False,
    ):
        _precreate(coordinator, registry)

    ids = coordinator._hierarchy_device_ids
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
