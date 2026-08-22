"""Tests for controlled cleanup of IDM hierarchy devices."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump.const import DOMAIN
from custom_components.idm_heatpump.coordinator import IdmCoordinator
from custom_components.idm_heatpump.device_hierarchy import (
    cleanup_deconfigured_heating_circuit_entities,
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
        patch(
            "custom_components.idm_heatpump.device_hierarchy.er.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.er.async_entries_for_device",
            return_value=[MagicMock()],
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


def _entity(unique_id: str, entity_id: str) -> MagicMock:
    entity = MagicMock()
    entity.unique_id = unique_id
    entity.entity_id = entity_id
    return entity


def _circuit_coordinator(circuits: list[str]) -> MagicMock:
    coordinator = MagicMock(spec=IdmCoordinator)
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "entry"
    coordinator.config_entry.options = {"heating_circuits": circuits}
    coordinator._registers = []
    return coordinator


def _run_entity_cleanup(coordinator: MagicMock, entities: list[MagicMock]) -> MagicMock:
    registry = MagicMock()
    with (
        patch(
            "custom_components.idm_heatpump.device_hierarchy.er.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.er.async_entries_for_config_entry",
            return_value=entities,
        ),
    ):
        cleanup_deconfigured_heating_circuit_entities(MagicMock(), coordinator)
    return registry


def test_entities_of_deconfigured_circuits_are_removed() -> None:
    """Unchecking a circuit must not leave permanently unavailable entities behind."""
    coordinator = _circuit_coordinator(["a", "d"])
    entities = [
        _entity("entry_hc_a_flow_temp", "sensor.a_flow"),
        _entity("entry_hc_d_heating_curve", "number.d_curve"),
        _entity("entry_hc_b_heating_curve", "number.b_curve"),
        _entity("entry_hc_g_mode", "select.g_mode"),
        # Calculated sensors of a circuit go the same way as its registers.
        _entity("entry_calculated_hc_b_flow_deviation", "sensor.calc_b"),
        _entity("entry_calculated_hc_d_flow_deviation", "sensor.calc_d"),
    ]

    registry = _run_entity_cleanup(coordinator, entities)

    removed = {call.args[0] for call in registry.async_remove.call_args_list}
    assert removed == {"number.b_curve", "select.g_mode", "sensor.calc_b"}


def test_cleanup_keeps_entities_that_are_not_heating_circuit_registers() -> None:
    """Only heating-circuit registers are in scope — nothing else is touched."""
    coordinator = _circuit_coordinator(["a"])
    entities = [
        _entity("entry_pv_surplus", "sensor.pv"),
        _entity("entry_web_compressor_1", "binary_sensor.compressor"),
        _entity("other_entry_hc_b_flow_temp", "sensor.foreign"),
    ]

    registry = _run_entity_cleanup(coordinator, entities)

    registry.async_remove.assert_not_called()


def test_cleanup_is_a_no_op_without_a_config_entry() -> None:
    coordinator = _circuit_coordinator(["a"])
    coordinator.config_entry = None

    registry = _run_entity_cleanup(coordinator, [])

    registry.async_remove.assert_not_called()


def test_cleanup_detaches_expected_subdevices_that_never_got_an_entity() -> None:
    """A pre-created sub-device without entities shows up as 'Unnamed device'.

    Sub-devices are created before the platforms so ``via_device`` links
    resolve; their name only arrives with the first entity. One that never gets
    an entity would otherwise linger unnamed and empty.
    """
    coordinator = _coordinator(enabled=True, register_names=("hc_a_flow_temp", "cascade_req_heating_temp"))
    registry = MagicMock()
    populated = _device((DOMAIN, "entry_heating_circuit_a"), "populated")
    empty = _device((DOMAIN, "entry_module_cascade"), "empty")
    main = _device((DOMAIN, "entry"), "main")

    def _entries_for_device(_registry, device_id, include_disabled_entities=False):
        return [] if device_id == "empty" else [MagicMock()]

    with (
        patch(
            "custom_components.idm_heatpump.device_hierarchy.dr.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.dr.async_entries_for_config_entry",
            return_value=[populated, empty, main],
        ),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.er.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.er.async_entries_for_device",
            side_effect=_entries_for_device,
        ),
    ):
        cleanup_stale_hierarchy_devices(MagicMock(), coordinator)

    registry.async_update_device.assert_called_once_with("empty", remove_config_entry_id="entry")


def test_cleanup_keeps_a_subdevice_whose_entities_are_all_disabled() -> None:
    """Disabled entities are still the user's entities — the device stays."""
    coordinator = _coordinator(enabled=True, register_names=("hc_a_flow_temp",))
    registry = MagicMock()
    device = _device((DOMAIN, "entry_heating_circuit_a"), "circuit_a")

    with (
        patch(
            "custom_components.idm_heatpump.device_hierarchy.dr.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.dr.async_entries_for_config_entry",
            return_value=[device],
        ),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.er.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.er.async_entries_for_device",
            return_value=[MagicMock()],
        ) as entries_for_device,
    ):
        cleanup_stale_hierarchy_devices(MagicMock(), coordinator)

    registry.async_update_device.assert_not_called()
    assert entries_for_device.call_args.kwargs["include_disabled_entities"] is True


def test_cleanup_stale_web_sensor_entities():
    """Old sensor-domain entities for keys migrated to binary_sensor must be removed."""
    from custom_components.idm_heatpump.device_hierarchy import cleanup_stale_web_sensor_entities

    coordinator = _circuit_coordinator(["a"])
    entities = [
        _entity("entry_web_failure_eheating", "sensor.eheating"),
        _entity("entry_web_dewpoint_humidity_alarm", "sensor.dewpoint"),
        _entity("entry_web_compressor_1", "sensor.comp1"),
        _entity("entry_web_outside_air_temperature", "sensor.outside_temp"),
        _entity("other_entry_web_failure_eheating", "sensor.other_eheating"),
    ]
    for ent in entities[:3]:
        ent.domain = "sensor"
    entities[3].domain = "sensor"  # not in WEB_BINARY_VALUE_KEYS
    entities[4].domain = "sensor"  # different entry

    registry = MagicMock()
    with (
        patch(
            "custom_components.idm_heatpump.device_hierarchy.er.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.er.async_entries_for_config_entry",
            return_value=entities,
        ),
    ):
        cleanup_stale_web_sensor_entities(MagicMock(), coordinator)

    removed = {call.args[0] for call in registry.async_remove.call_args_list}
    assert removed == {"sensor.eheating", "sensor.dewpoint", "sensor.comp1"}
