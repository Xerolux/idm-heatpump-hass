"""Differential circuit semantics, entity migration and polling (#429)."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.idm_heatpump.calculated_sensors import (
    calculated_sensor_entities,
    differential_temperature_entities,
)
from custom_components.idm_heatpump.config_flow import _build_guided_field_schema, _build_options_schema
from custom_components.idm_heatpump.const import CONF_DIFFERENTIAL_CIRCUITS, CONF_HEATING_CIRCUITS
from custom_components.idm_heatpump.coordinator import IdmCoordinator
from custom_components.idm_heatpump.device_hierarchy import (
    DeviceScope,
    _subdevice_labels,
    cleanup_deconfigured_heating_circuit_entities,
    shorten_legacy_differential_entity_ids,
)
from custom_components.idm_heatpump.differential_circuits import (
    configured_differential_circuits,
    differential_circuits,
    differential_register_translation,
    register_allowed,
    web_detected_differential_circuits,
    web_value_allowed,
)
from custom_components.idm_heatpump.polling_plan import _entity_dependencies
from custom_components.idm_heatpump.registers import (
    get_all_number_descriptions,
    get_all_select_descriptions,
    get_all_sensor_descriptions,
)
from custom_components.idm_heatpump.sensor import IdmSensor, _web_sensor_definitions
from custom_components.idm_heatpump.web_climate_entities import web_climate_entities
from custom_components.idm_heatpump.web_control_entities import web_control_heatingcircuit_entities


@pytest.fixture
def differential_coordinator(mock_hass, mock_config_entry, monkeypatch):
    # The unit harness's entity descriptions accept arbitrary kwargs but are
    # not dataclasses; the real-HA smoke test covers frozen dataclass cloning.
    monkeypatch.setattr(
        "custom_components.idm_heatpump.differential_circuits.replace",
        lambda description, **changes: type(description)(**{**vars(description), **changes}),
    )
    mock_config_entry.options = {CONF_HEATING_CIRCUITS: ["a", "d"], CONF_DIFFERENTIAL_CIRCUITS: ["d"]}
    sensors = get_all_sensor_descriptions(["a", "d"], 0, {})
    numbers = get_all_number_descriptions(["a", "d"], 0, {})
    selects = get_all_select_descriptions(["a", "d"], 0, {})
    coordinator = IdmCoordinator(
        mock_hass,
        mock_config_entry,
        MagicMock(),
        timedelta(seconds=30),
        sensors,
        [],
        numbers,
        selects,
        [],
    )
    coordinator.setup_registers(["a", "d"], 0, {}, descriptions=sensors + numbers + selects)
    coordinator.data = {"hc_d_flow_temp": 41.83, "hc_d_room_temp": 22.63, "hc_d_active_mode": 255}
    coordinator.last_update_success = True
    return coordinator


@pytest.mark.parametrize(
    "options,expected",
    [
        ({}, set()),
        ({CONF_HEATING_CIRCUITS: ["a", "d"], CONF_DIFFERENTIAL_CIRCUITS: ["D", "g", "bad"]}, {"d"}),
        ({CONF_DIFFERENTIAL_CIRCUITS: "d"}, set()),
        ({CONF_HEATING_CIRCUITS: None, CONF_DIFFERENTIAL_CIRCUITS: ["d"]}, set()),
    ],
)
def test_selection_requires_installed_circuit(options, expected):
    assert differential_circuits(options) == expected
    assert configured_differential_circuits(SimpleNamespace(config_entry=SimpleNamespace(options=options))) == expected


def test_absent_entry_or_non_mapping_options():
    assert configured_differential_circuits(object()) == set()
    assert configured_differential_circuits(SimpleNamespace(config_entry=SimpleNamespace(options=None))) == set()


def test_filters_controls_and_preserves_raw_ids(differential_coordinator):
    coordinator = differential_coordinator
    names = coordinator.register_map_names
    assert {name for name in names if name.startswith("hc_d_")} == {
        "hc_d_flow_temp",
        "hc_d_room_temp",
        "hc_d_active_mode",
    }
    assert "hc_a_heating_curve" in names
    assert not any(
        d["register"].name.startswith("hc_d_")
        for d in coordinator.number_descriptions + coordinator.select_descriptions
    )
    for desc in coordinator.sensor_descriptions:
        if desc["register"].name.startswith("hc_d_"):
            entity = IdmSensor(coordinator, desc["register"], desc["description"])
            assert entity._attr_unique_id == f"{coordinator.config_entry.entry_id}_{desc['register'].name}"
            assert entity._attr_translation_placeholders == {"circuit": "D"}
            assert entity.entity_description.translation_key in {
                "hc_storage_temp",
                "hc_reference_temp",
                "hc_differential_status",
            }
    assert differential_register_translation("hc_a_flow_temp", frozenset({"d"})) is None
    assert register_allowed("hc_d_flow_temp", frozenset({"d"}))
    assert not register_allowed("hc_d_ext_room_temp", frozenset({"d"}))


@pytest.mark.parametrize("raw,expected", [(0, "off"), (1, "heating"), (2, "cooling"), (255, "standby"), (99, None)])
def test_contextual_status(differential_coordinator, raw, expected):
    coordinator = differential_coordinator
    desc = next(d for d in coordinator.sensor_descriptions if d["register"].name == "hc_d_active_mode")
    entity = IdmSensor(coordinator, desc["register"], desc["description"])
    coordinator.data["hc_d_active_mode"] = raw
    assert entity.native_value == expected
    assert entity.available
    if expected:
        assert expected in entity.entity_description.options


def test_difference_and_polling(differential_coordinator):
    coordinator = differential_coordinator
    (entity,) = differential_temperature_entities(coordinator)
    assert entity.native_value == -19.2
    assert entity.entity_description.native_unit_of_measurement == "K"
    assert entity.available
    assert _entity_dependencies("hc_d_temperature_difference") == {"hc_d_room_temp", "hc_d_flow_temp"}
    coordinator.data["hc_d_setpoint_flow_temp"] = 60
    assert not any(
        e.entity_description.key == "calculated_hc_d_flow_deviation" for e in calculated_sensor_entities(coordinator)
    )
    coordinator.data["hc_d_room_temp"] = float("nan")
    assert entity.native_value is None
    assert not entity.available
    coordinator.data["hc_d_room_temp"] = 22.63
    coordinator._unused_registers = {"hc_d_room_temp"}
    assert entity.native_value is None
    coordinator.data.pop("hc_d_room_temp")
    assert differential_temperature_entities(coordinator) == []


def test_option_in_full_and_guided_forms():
    for schema in (
        _build_options_schema({}),
        _build_guided_field_schema({}, (CONF_HEATING_CIRCUITS, CONF_DIFFERENTIAL_CIRCUITS)),
    ):
        marker = next(k for k in schema.schema if k.schema == CONF_DIFFERENTIAL_CIRCUITS)
        assert marker.default() == []


def test_web_controls_suppressed_but_pump_kept(differential_coordinator):
    coordinator = differential_coordinator
    assert not web_value_allowed("mixer_heating_circuitD", frozenset({"d"}))
    assert web_value_allowed("pump_heating_circuitD", frozenset({"d"}))
    assert not any(d.key in {"mixer_heating_circuitD", "flow_temp_HK_D"} for d in _web_sensor_definitions(coordinator))
    coordinator._web_supplement = SimpleNamespace(
        heating_circuits=[SimpleNamespace(hc_id="d", setpoint_normal=object(), mode_parameter_id="mode_d")]
    )
    with (
        patch("custom_components.idm_heatpump.web_control_entities._web_control_active", return_value=True),
        patch("custom_components.idm_heatpump.web_climate_entities._web_control_active", return_value=True),
    ):
        assert web_control_heatingcircuit_entities(coordinator) == []
        assert web_climate_entities(coordinator) == []
    # The circuit type rides on the model only — the name is the slug every
    # new entity ID of the device is prefixed with (#429).
    assert _subdevice_labels(coordinator, DeviceScope("heating_circuit", "D")) == (
        "Heizkreis D",
        "Differential temperature control",
    )


def test_registry_migration_is_entry_scoped(differential_coordinator):
    coordinator = differential_coordinator
    prefix = coordinator.config_entry.entry_id + "_"
    keys = [
        "hc_d_flow_temp",
        "hc_d_room_temp",
        "hc_d_active_mode",
        "hc_d_temperature_difference",
        "hc_d_heating_curve",
        "climate_hc_d",
        "calculated_hc_d_flow_deviation",
        "web_hc_d_room_setpoint",
        "web_hc_d_mode",
        "web_climate_hc_d",
        "web_mixer_heating_circuitD",
        "web_pump_heating_circuitD",
        "hc_a_heating_curve",
    ]
    entities = [SimpleNamespace(unique_id=prefix + key, entity_id=key) for key in keys]
    entities.append(SimpleNamespace(unique_id="foreign_hc_d_heating_curve", entity_id="foreign"))
    registry = MagicMock()
    with (
        patch("custom_components.idm_heatpump.device_hierarchy.er.async_get", return_value=registry),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.er.async_entries_for_config_entry", return_value=entities
        ),
    ):
        cleanup_deconfigured_heating_circuit_entities(coordinator.hass, coordinator)
        removed = {call.args[0] for call in registry.async_remove.call_args_list}
        assert removed == {
            "hc_d_heating_curve",
            "climate_hc_d",
            "calculated_hc_d_flow_deviation",
            "web_hc_d_room_setpoint",
            "web_hc_d_mode",
            "web_climate_hc_d",
            "web_mixer_heating_circuitD",
        }
        registry.reset_mock()
        coordinator.config_entry.options[CONF_DIFFERENTIAL_CIRCUITS] = []
        cleanup_deconfigured_heating_circuit_entities(coordinator.hass, coordinator)
        registry.async_remove.assert_called_once_with("hc_d_temperature_difference")


def _patch_entity_registry(entities: list[Any]) -> MagicMock:
    registry = MagicMock()
    patcher_get = patch("custom_components.idm_heatpump.device_hierarchy.er.async_get", return_value=registry)
    patcher_entries = patch(
        "custom_components.idm_heatpump.device_hierarchy.er.async_entries_for_config_entry",
        return_value=entities,
    )
    patcher_get.start()
    patcher_entries.start()
    return registry


def test_legacy_differential_entity_ids_shortened(differential_coordinator):
    """IDs registered under the suffixed device name lose only that segment."""
    coordinator = differential_coordinator
    entry_id = coordinator.config_entry.entry_id
    entities = [
        # German-rendered difference sensor, exactly as b1 registered it (#429).
        SimpleNamespace(
            unique_id=f"{entry_id}_hc_d_temperature_difference",
            entity_id="sensor.heizkreis_d_differenztemperaturgeregelt_temperaturdifferenz_hk_d",
        ),
        # English rendering proves the shortening is language-agnostic.
        SimpleNamespace(
            unique_id=f"{entry_id}_hc_d_flow_temp",
            entity_id="sensor.heizkreis_d_differenztemperaturgeregelt_temperature_difference_hc_d",
        ),
        # Entities without the legacy segment keep their IDs.
        SimpleNamespace(
            unique_id=f"{entry_id}_hc_d_room_temp",
            entity_id="sensor.heizkreis_d_raumtemperatur_hk_d",
        ),
        SimpleNamespace(
            unique_id=f"{entry_id}_hc_a_flow_temp",
            entity_id="sensor.heizkreis_a_vorlauftemperatur_hk_a",
        ),
    ]
    registry = _patch_entity_registry(entities)
    try:
        shorten_legacy_differential_entity_ids(coordinator.hass, coordinator)
    finally:
        patch.stopall()
    renames = {call.args[0]: call.kwargs["new_entity_id"] for call in registry.async_update_entity.call_args_list}
    assert renames == {
        "sensor.heizkreis_d_differenztemperaturgeregelt_temperaturdifferenz_hk_d": (
            "sensor.heizkreis_d_temperaturdifferenz_hk_d"
        ),
        "sensor.heizkreis_d_differenztemperaturgeregelt_temperature_difference_hc_d": (
            "sensor.heizkreis_d_temperature_difference_hc_d"
        ),
    }


def test_legacy_differential_entity_ids_conflict_keeps_long_id(differential_coordinator):
    """A short ID owned by another entity wins; the long one keeps working."""
    coordinator = differential_coordinator
    entry_id = coordinator.config_entry.entry_id
    entities = [
        SimpleNamespace(
            unique_id=f"{entry_id}_hc_d_temperature_difference",
            entity_id="sensor.heizkreis_d_differenztemperaturgeregelt_temperaturdifferenz_hk_d",
        ),
    ]
    registry = _patch_entity_registry(entities)
    registry.async_update_entity.side_effect = ValueError("Entity with this ID is already registered")
    try:
        shorten_legacy_differential_entity_ids(coordinator.hass, coordinator)
    finally:
        patch.stopall()


def test_legacy_differential_entity_ids_noop_without_differential_circuits(differential_coordinator):
    coordinator = differential_coordinator
    coordinator.config_entry.options[CONF_DIFFERENTIAL_CIRCUITS] = []
    coordinator.set_web_differential_circuits(frozenset())
    registry = _patch_entity_registry(
        [
            SimpleNamespace(
                unique_id="x", entity_id="sensor.heizkreis_d_differenztemperaturgeregelt_temperaturdifferenz_hk_d"
            )
        ]
    )
    try:
        shorten_legacy_differential_entity_ids(coordinator.hass, coordinator)
    finally:
        patch.stopall()
    registry.async_update_entity.assert_not_called()


class TestWebDetection:
    """Differential circuits detected from the web system/overview frame."""

    def _overview(self, *types: int | None) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(
            heating_circuits=tuple(
                SimpleNamespace(circuit_id=letter, type=circuit_type) for letter, circuit_type in zip("abcdefg", types)
            )
        )

    def test_detects_only_differential_circuits(self) -> None:
        overview = self._overview(2, 4, None, 0, 3, 4, 2)

        assert web_detected_differential_circuits(overview) == frozenset({"b", "f"})

    def test_no_overview_detects_nothing(self) -> None:
        assert web_detected_differential_circuits(None) == frozenset()
        assert web_detected_differential_circuits(object()) == frozenset()

    def test_malformed_circuit_entries_are_ignored(self) -> None:
        from types import SimpleNamespace

        overview = SimpleNamespace(heating_circuits=(object(), "nonsense", None))

        assert web_detected_differential_circuits(overview) == frozenset()

    def test_configured_set_unions_options_and_web_detection(self) -> None:
        from types import SimpleNamespace

        entry = SimpleNamespace(options={CONF_DIFFERENTIAL_CIRCUITS: ["a"], CONF_HEATING_CIRCUITS: ["a", "b"]})
        coordinator = SimpleNamespace(config_entry=entry, web_differential_circuits=frozenset({"b"}))

        assert configured_differential_circuits(coordinator) == frozenset({"a", "b"})

    def test_web_detection_applies_without_any_option(self) -> None:
        from types import SimpleNamespace

        entry = SimpleNamespace(options={CONF_HEATING_CIRCUITS: ["a", "d"]})
        coordinator = SimpleNamespace(config_entry=entry, web_differential_circuits=frozenset({"d"}))

        assert configured_differential_circuits(coordinator) == frozenset({"d"})
