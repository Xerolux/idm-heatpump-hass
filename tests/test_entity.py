"""Tests for IdmEntity base class."""

from unittest.mock import MagicMock

import pytest

from custom_components.idm_heatpump_v2.entity import IdmEntity
from custom_components.idm_heatpump_v2.modbus_client import DataType, RegisterDef
from custom_components.idm_heatpump_v2.const import DOMAIN, MANUFACTURER, MODEL, UNUSED_VALUE


def _make_register(name="temp", address=100):
    return RegisterDef(
        address=address,
        datatype=DataType.FLOAT,
        name=name,
        writable=False,
    )


def _make_coordinator(hide_unused=True, data=None, last_update_success=True):
    coord = MagicMock()
    coord.hide_unused = hide_unused
    coord.data = data if data is not None else {}
    coord.last_update_success = last_update_success
    coord.client = MagicMock()
    coord.client.host = "192.168.1.100"
    coord.client.port = 502
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "test_entry_id"
    coord.config_entry.title = "IDM Test"
    return coord


def _make_entity(coordinator=None, reg=None, entity_desc=None):
    if coordinator is None:
        coordinator = _make_coordinator()
    if reg is None:
        reg = _make_register()
    if entity_desc is None:
        entity_desc = MagicMock()
        entity_desc.key = reg.name
    return IdmEntity(coordinator, reg, entity_desc)


class TestIdmEntityInit:
    def test_unique_id_format(self):
        coord = _make_coordinator()
        reg = _make_register(name="outdoor_temp", address=100)
        entity = _make_entity(coordinator=coord, reg=reg)
        assert entity._attr_unique_id == "192.168.1.100:502_outdoor_temp"

    def test_unique_id_uses_host_and_port(self):
        coord = _make_coordinator()
        coord.client.host = "10.0.0.1"
        coord.client.port = 1502
        reg = _make_register(name="mode", address=200)
        entity = _make_entity(coordinator=coord, reg=reg)
        assert entity._attr_unique_id == "10.0.0.1:1502_mode"

    def test_device_info_has_domain_identifier(self):
        entity = _make_entity()
        assert (DOMAIN, "test_entry_id") in entity._attr_device_info["identifiers"]

    def test_device_info_has_manufacturer(self):
        entity = _make_entity()
        assert entity._attr_device_info["manufacturer"] == MANUFACTURER

    def test_device_info_has_model(self):
        entity = _make_entity()
        assert entity._attr_device_info["model"] == MODEL

    def test_device_info_uses_entry_title(self):
        coord = _make_coordinator()
        coord.config_entry.title = "My Heat Pump"
        entity = _make_entity(coordinator=coord)
        assert entity._attr_device_info["name"] == "My Heat Pump"

    def test_entity_description_set(self):
        desc = MagicMock()
        desc.key = "temp"
        entity = _make_entity(entity_desc=desc)
        assert entity.entity_description is desc

    def test_register_stored(self):
        reg = _make_register(name="flow_temp", address=50)
        entity = _make_entity(reg=reg)
        assert entity._register is reg

    def test_has_entity_name_true(self):
        entity = _make_entity()
        assert entity._attr_has_entity_name is True


class TestIdmEntityAvailable:
    def test_unavailable_when_coordinator_unavailable(self):
        coord = _make_coordinator(data={"temp": 22.0}, last_update_success=False)
        entity = _make_entity(coordinator=coord, reg=_make_register("temp"))
        # Coordinator base class returns False when last_update_success is False
        # We simulate this by patching super().available
        # Actually in our stub, available is based on last_update_success
        coord.last_update_success = False

        # Patch the super().available call via the parent class
        from homeassistant.helpers.update_coordinator import CoordinatorEntity
        original_available = CoordinatorEntity.available.fget

        import unittest.mock as mock
        with mock.patch.object(
            CoordinatorEntity, "available", new_callable=lambda: property(lambda self: self.coordinator.last_update_success)
        ):
            assert entity.available is False

    def test_unavailable_when_no_data(self):
        coord = _make_coordinator(data=None, last_update_success=True)
        entity = _make_entity(coordinator=coord, reg=_make_register("temp"))
        assert entity.available is False

    def test_unavailable_when_register_not_in_data(self):
        coord = _make_coordinator(data={"other_key": 5.0}, last_update_success=True)
        entity = _make_entity(coordinator=coord, reg=_make_register("temp"))
        assert entity.available is False

    def test_available_when_data_present(self):
        coord = _make_coordinator(data={"temp": 22.0}, last_update_success=True)
        entity = _make_entity(coordinator=coord, reg=_make_register("temp"))
        assert entity.available is True

    def test_unavailable_when_value_is_unused(self):
        coord = _make_coordinator(
            data={"temp": UNUSED_VALUE},
            last_update_success=True,
            hide_unused=True,
        )
        entity = _make_entity(coordinator=coord, reg=_make_register("temp"))
        assert entity.available is False

    def test_available_when_hide_unused_false_and_unused_value(self):
        coord = _make_coordinator(
            data={"temp": UNUSED_VALUE},
            last_update_success=True,
            hide_unused=False,
        )
        entity = _make_entity(coordinator=coord, reg=_make_register("temp"))
        assert entity.available is True

    def test_available_normal_value_with_hide_unused(self):
        coord = _make_coordinator(
            data={"temp": 22.5},
            last_update_success=True,
            hide_unused=True,
        )
        entity = _make_entity(coordinator=coord, reg=_make_register("temp"))
        assert entity.available is True

    def test_unavailable_with_sentinel_minus_one(self):
        coord = _make_coordinator(
            data={"sensor": -1.0},
            last_update_success=True,
            hide_unused=True,
        )
        entity = _make_entity(coordinator=coord, reg=_make_register("sensor"))
        assert entity.available is False

    def test_available_zero_is_not_unused(self):
        coord = _make_coordinator(
            data={"sensor": 0.0},
            last_update_success=True,
            hide_unused=True,
        )
        entity = _make_entity(coordinator=coord, reg=_make_register("sensor"))
        assert entity.available is True

    def test_available_empty_dict_data_is_unavailable(self):
        coord = _make_coordinator(data={}, last_update_success=True)
        entity = _make_entity(coordinator=coord, reg=_make_register("temp"))
        # Empty dict – key "temp" is not in it
        assert entity.available is False
