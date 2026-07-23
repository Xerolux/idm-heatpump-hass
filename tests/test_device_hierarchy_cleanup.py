"""Tests for controlled cleanup of IDM hierarchy devices."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump.const import DOMAIN
from custom_components.idm_heatpump.coordinator import IdmCoordinator
from custom_components.idm_heatpump.device_hierarchy import (
    cleanup_stale_hierarchy_devices,
    expected_subdevice_identifiers,
)


def _register(name: str) -> RegisterDef:
    return RegisterDef(address=100, datatype=DataType.FLOAT, name=name)


def _coordinator(*, enabled: bool, register_names: tuple[str, ...] = ()) -> MagicMock:
    coordinator = MagicMock(spec=IdmCoordinator)
    coordinator.device_hierarchy_enabled = enabled
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "entry"
    coordinator._registers = [_register(name) for name in register_names]
    coordinator.web_value_keys = ()
    return coordinator


def _device(identifier: tuple[str, str], device_id: str) -> MagicMock:
    device = MagicMock()
    device.id = device_id
    device.identifiers = {identifier}
    return device


def test_expected_identifiers_include_zone_parent_for_room() -> None:
    coordinator = _coordinator(
        enabled=True,
        register_names=("hc_b_flow_temp", "zm2_room4_temp"),
    )

    assert expected_subdevice_identifiers(coordinator) == {
        (DOMAIN, "entry_heating_circuit_b"),
        (DOMAIN, "entry_zone_module_2"),
        (DOMAIN, "entry_zone_module_2_room_4"),
        (DOMAIN, "entry_module_diagnostics"),
    }


def test_disabled_hierarchy_has_no_expected_subdevices() -> None:
    coordinator = _coordinator(enabled=False, register_names=("hc_a_flow_temp",))

    assert expected_subdevice_identifiers(coordinator) == set()


def test_cleanup_detaches_only_stale_hierarchy_devices() -> None:
    coordinator = _coordinator(enabled=True, register_names=("hc_a_flow_temp",))
    registry = MagicMock()
    current = _device((DOMAIN, "entry_heating_circuit_a"), "current")
    stale = _device((DOMAIN, "entry_zone_module_3"), "stale")
    main = _device((DOMAIN, "entry"), "main")
    unrelated = _device(("other", "entry_zone_module_3"), "unrelated")

    with (
        patch(
            "custom_components.idm_heatpump.device_hierarchy.dr.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.dr.async_entries_for_config_entry",
            return_value=[current, stale, main, unrelated],
        ),
    ):
        cleanup_stale_hierarchy_devices(MagicMock(), coordinator)

    registry.async_update_device.assert_called_once_with(
        "stale",
        remove_config_entry_id="entry",
    )


def test_disabling_hierarchy_detaches_all_subdevices_but_not_main() -> None:
    coordinator = _coordinator(enabled=False)
    registry = MagicMock()
    heating = _device((DOMAIN, "entry_heating_circuit_a"), "heating")
    room = _device((DOMAIN, "entry_zone_module_1_room_1"), "room")
    main = _device((DOMAIN, "entry"), "main")

    with (
        patch(
            "custom_components.idm_heatpump.device_hierarchy.dr.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.dr.async_entries_for_config_entry",
            return_value=[heating, room, main],
        ),
    ):
        cleanup_stale_hierarchy_devices(MagicMock(), coordinator)

    assert registry.async_update_device.call_count == 2
    registry.async_update_device.assert_any_call(
        "heating",
        remove_config_entry_id="entry",
    )
    registry.async_update_device.assert_any_call(
        "room",
        remove_config_entry_id="entry",
    )
