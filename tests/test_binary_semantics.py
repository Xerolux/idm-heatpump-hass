"""Tests for IDM binary sensor semantics."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump import binary_semantics
from custom_components.idm_heatpump.binary_semantics import (
    binary_value_is_on,
    infer_binary_device_class,
)
from custom_components.idm_heatpump.binary_sensor import IdmBinarySensor


def _register(**overrides):
    values = {
        "name": "compressor_status_1",
        "sentinel_values": (),
        "binary_on_values": None,
        "binary_off_values": None,
        "binary_on_value": None,
        "binary_off_value": None,
        "binary_bitmask": None,
        "binary_inverted": False,
        "binary_active_low": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _coordinator(value):
    coordinator = MagicMock()
    coordinator.data = {"compressor_status_1": value}
    coordinator.last_update_success = True
    coordinator.unused_registers = set()
    coordinator.config_entry.entry_id = "entry"
    coordinator.config_entry.title = "IDM"
    coordinator.model_name = "Navigator 10"
    coordinator.firmware_version = None
    coordinator.myidm_id = None
    return coordinator


def test_infer_problem_device_class():
    assert infer_binary_device_class("hp_sum_alarm") == BinarySensorDeviceClass.PROBLEM
    assert infer_binary_device_class("failure_eheating") == BinarySensorDeviceClass.PROBLEM


def test_infer_operating_device_classes():
    assert infer_binary_device_class("compressor_status_1") == BinarySensorDeviceClass.RUNNING
    assert infer_binary_device_class("heating_demand") == BinarySensorDeviceClass.HEAT
    assert infer_binary_device_class("cooling_demand") == BinarySensorDeviceClass.COLD
    assert infer_binary_device_class("controller_connected") == BinarySensorDeviceClass.CONNECTIVITY


def test_zero_and_one_decode_normally():
    register = _register()
    assert binary_value_is_on(register, 0) is False
    assert binary_value_is_on(register, 1) is True


def test_negative_value_is_never_treated_as_on():
    assert binary_value_is_on(_register(), -1) is False


def test_sentinel_value_is_off():
    assert binary_value_is_on(_register(sentinel_values=(255,)), 255) is False


def test_explicit_on_and_off_values_take_precedence():
    register = _register(binary_on_values={2}, binary_off_values={1})
    assert binary_value_is_on(register, 2) is True
    assert binary_value_is_on(register, 1) is False


def test_bitmask_metadata_is_supported():
    register = _register(binary_bitmask=0b0100)
    assert binary_value_is_on(register, 0b0100) is True
    assert binary_value_is_on(register, 0b0010) is False


def test_active_low_metadata_is_supported():
    register = _register(binary_active_low=True)
    assert binary_value_is_on(register, 0) is True
    assert binary_value_is_on(register, 1) is False


def test_known_text_values_are_supported():
    register = _register()
    assert binary_value_is_on(register, "running") is True
    assert binary_value_is_on(register, "off") is False
    assert binary_value_is_on(register, "unexpected") is False


def test_optional_library_metadata_is_used(monkeypatch):
    metadata = SimpleNamespace(
        on_values=(7,),
        off_values=(3,),
        bitmask=None,
        inverted=False,
        device_class="problem",
    )
    monkeypatch.setattr(binary_semantics, "_GET_LIBRARY_BINARY_METADATA", lambda _name: metadata)
    register = _register(name="custom_status")

    assert binary_value_is_on(register, 7) is True
    assert binary_value_is_on(register, 3) is False
    assert infer_binary_device_class("custom_status") == BinarySensorDeviceClass.PROBLEM


def test_register_local_metadata_overrides_library_metadata(monkeypatch):
    metadata = SimpleNamespace(
        on_values=(7,),
        off_values=(3,),
        bitmask=None,
        inverted=False,
        device_class="running",
    )
    monkeypatch.setattr(binary_semantics, "_GET_LIBRARY_BINARY_METADATA", lambda _name: metadata)
    register = _register(binary_on_values={2}, binary_off_values={1, 7})

    assert binary_value_is_on(register, 2) is True
    assert binary_value_is_on(register, 7) is False
    assert binary_value_is_on(register, 1) is False


def test_binary_entity_does_not_turn_on_for_minus_one():
    register = RegisterDef(
        address=1100,
        datatype=DataType.UCHAR,
        name="compressor_status_1",
        binary=True,
    )
    entity = IdmBinarySensor(_coordinator(-1), register, MagicMock())
    assert entity.is_on is False


def test_device_class_inference_covers_every_semantic_group():
    assert infer_binary_device_class("evu_lock") == BinarySensorDeviceClass.LOCK
    assert infer_binary_device_class("defrost_active") == BinarySensorDeviceClass.COLD
    assert infer_binary_device_class("dhw_demand") == BinarySensorDeviceClass.HEAT
    assert infer_binary_device_class("variable_input") is None


def test_unhashable_values_are_never_on():
    """A decoded list can never be compared against the sentinel set."""
    assert binary_value_is_on(_register(sentinel_values=(0,)), ["unexpected"]) is False


def test_a_non_numeric_value_with_a_bitmask_is_off():
    assert binary_value_is_on(_register(binary_bitmask=0x02), "not a number") is False


def test_boolean_values_are_used_directly():
    assert binary_value_is_on(_register(), True) is True
    assert binary_value_is_on(_register(), False) is False


def test_non_finite_numbers_are_off():
    assert binary_value_is_on(_register(), float("nan")) is False
    assert binary_value_is_on(_register(), float("inf")) is False


def test_unknown_text_is_off():
    assert binary_value_is_on(_register(), "vielleicht") is False


def test_other_objects_fall_back_to_truthiness():
    assert binary_value_is_on(_register(), object()) is True


def test_collection_metadata_is_normalized():
    assert binary_value_is_on(_register(binary_on_values=[3]), 3) is True
    assert binary_value_is_on(_register(binary_on_value=3), 3) is True


def test_library_metadata_is_optional(monkeypatch):
    """The integration still runs against an API without the binary catalog."""
    monkeypatch.setattr(binary_semantics, "_GET_LIBRARY_BINARY_METADATA", None)

    assert binary_semantics._library_metadata("compressor_status_1") is None
    assert binary_value_is_on(_register(), 1) is True
