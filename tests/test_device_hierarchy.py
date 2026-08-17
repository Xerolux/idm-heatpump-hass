"""Tests for the opt-in IDM device hierarchy."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
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


def test_heating_circuit_device_is_linked_to_main_device() -> None:
    info = build_subdevice_info(_coordinator(), "hc_b_flow_temp")

    assert info is not None
    assert info["identifiers"] == {(DOMAIN, "entry_heating_circuit_b")}
    assert info["name"] == "Heizkreis B"
    assert info["via_device_id"] == "main-device-id"


def test_zone_room_is_linked_through_zone_module() -> None:
    info = build_subdevice_info(_coordinator(), "zm2_room4_setpoint")

    assert info is not None
    assert info["identifiers"] == {(DOMAIN, "entry_zone_module_2_room_4")}
    assert info["name"] == "Zonenmodul 2 Raum 4"
    assert info["via_device_id"] == "zone-module-2-device-id"


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


def test_precreate_main_device_creates_expected_subdevices_and_caches_ids() -> None:
    coordinator = _coordinator()
    coordinator._registers = [
        RegisterDef(address=1352, datatype=DataType.FLOAT, name="hc_b_flow_temp", unit="°C"),
    ]
    coordinator.web_supplement = None
    registry = MagicMock()
    created: dict[tuple[str, str], MagicMock] = {}

    def _get_or_create(*, config_entry_id, identifiers):
        identifier = next(iter(identifiers))
        if identifier not in created:
            device = MagicMock()
            device.id = f"device-{len(created)}"
            created[identifier] = device
        return created[identifier]

    registry.async_get_or_create.side_effect = _get_or_create

    with patch(
        "custom_components.idm_heatpump.device_hierarchy.dr.async_get",
        return_value=registry,
    ):
        precreate_main_device(MagicMock(), coordinator)

    main_id = created[(DOMAIN, "entry")].id
    circuit_id = created[(DOMAIN, "entry_heating_circuit_b")].id

    assert coordinator._hierarchy_device_ids[(DOMAIN, "entry")] == main_id
    assert coordinator._hierarchy_device_ids[(DOMAIN, "entry_heating_circuit_b")] == circuit_id
    assert main_id != circuit_id
