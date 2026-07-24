"""Tests for IdmEntity base class."""

import math
from unittest.mock import MagicMock

from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump.const import DOMAIN, MANUFACTURER, MODEL, UNUSED_VALUE
from custom_components.idm_heatpump.coordinator import IdmCoordinator
from custom_components.idm_heatpump.entity import IdmEntity


def _make_register(name="temp", address=100):
    return RegisterDef(
        address=address,
        datatype=DataType.FLOAT,
        name=name,
        writable=False,
    )


def _make_coordinator(hide_unused=True, data=None, last_update_success=True, firmware_version=None):
    coord = MagicMock(spec=IdmCoordinator)
    coord.hide_unused = hide_unused
    coord.data = data if data is not None else {}
    coord.last_update_success = last_update_success
    coord.client = MagicMock()
    coord.client.host = "192.168.1.100"
    coord.client.port = 502
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "test_entry_id"
    coord.config_entry.title = "IDM Test"
    coord.model_name = MODEL
    coord.firmware_version = firmware_version
    coord.myidm_id = None

    def _is_unused(register_name, value):
        if not hide_unused:
            return False
        if value is None:
            return True
        if isinstance(value, (int, float)):
            if abs(value - UNUSED_VALUE) < 0.01:
                return True
            if value == 65535 or value == 255:
                return True
            if value == -32768:
                return True
            if isinstance(value, float) and (math.isnan(value) or abs(value) == float("inf")):
                return True
        return False

    coord.is_register_unused = MagicMock(side_effect=_is_unused)

    # Mirror the real coordinator: unused_registers is a precomputed set that
    # _async_update_data populates from is_register_unused(). The IdmEntity
    # available property consumes this set directly (O(1)) instead of recomputing.
    unused_set: set[str] = set()
    if isinstance(coord.data, dict):
        for register_name, value in coord.data.items():
            if _is_unused(register_name, value):
                unused_set.add(register_name)
    coord.unused_registers = unused_set
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
        assert entity._attr_unique_id == "test_entry_id_outdoor_temp"

    def test_unique_id_ignores_connection_settings(self):
        coord = _make_coordinator()
        coord.client.host = "10.0.0.1"
        coord.client.port = 1502
        reg = _make_register(name="mode", address=200)
        entity = _make_entity(coordinator=coord, reg=reg)
        assert entity._attr_unique_id == "test_entry_id_mode"

    def test_device_info_has_domain_identifier(self):
        entity = _make_entity()
        assert (DOMAIN, "test_entry_id") in entity.device_info["identifiers"]

    def test_device_info_has_manufacturer(self):
        entity = _make_entity()
        assert entity.device_info["manufacturer"] == MANUFACTURER

    def test_device_info_has_model(self):
        entity = _make_entity()
        assert entity.device_info["model"] == MODEL

    def test_device_info_uses_entry_title(self):
        coord = _make_coordinator()
        coord.config_entry.title = "My Heat Pump"
        entity = _make_entity(coordinator=coord)
        assert entity.device_info["name"] == "My Heat Pump"

    def test_device_info_uses_detected_model(self):
        coord = _make_coordinator()
        coord.model_name = "Navigator 10"
        entity = _make_entity(coordinator=coord)
        assert entity.device_info["model"] == "Navigator 10"

    def test_device_info_has_sw_version_when_firmware_known(self):
        coord = _make_coordinator(firmware_version="1.2.3")
        entity = _make_entity(coordinator=coord)
        assert entity.device_info["sw_version"] == "1.2.3"

    def test_device_info_omits_sw_version_when_firmware_unknown(self):
        coord = _make_coordinator(firmware_version=None)
        entity = _make_entity(coordinator=coord)
        assert "sw_version" not in entity.device_info

    def test_device_info_has_serial_number_when_myidm_id_known(self):
        coord = _make_coordinator()
        coord.myidm_id = "m129236"
        entity = _make_entity(coordinator=coord)
        assert entity.device_info["serial_number"] == "m129236"

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


class TestBuildDeviceInfoCache:
    """Verify build_device_info memoizes DeviceInfo (perf commit 9a6b5ff)."""

    def _make_cacheable_coordinator(self, model_name=MODEL, firmware_version=None, myidm_id=None, title="IDM Test"):
        coord = MagicMock(spec=IdmCoordinator)
        coord.model_name = model_name
        coord.firmware_version = firmware_version
        coord.myidm_id = myidm_id
        coord.config_entry = MagicMock()
        coord.config_entry.entry_id = "test_entry_id"
        coord.config_entry.title = title
        # Real attribute (not a MagicMock child) so the cache contract is exercised.
        coord._device_info_cache = None
        return coord

    def test_caches_and_returns_same_object_on_second_call(self):
        from custom_components.idm_heatpump.entity import build_device_info

        coord = self._make_cacheable_coordinator(firmware_version="1.0")
        first = build_device_info(coord)
        second = build_device_info(coord)
        assert first is second
        # Cache is populated with a key derived from model/firmware/myidm/title.
        cached_key, cached_info = coord._device_info_cache
        assert cached_info is first
        assert cached_key == ("Navigator 2.0 / 10", "1.0", None, "IDM Test")

    def test_cache_invalidated_returns_rebuilt_object(self):
        from custom_components.idm_heatpump.entity import build_device_info

        coord = self._make_cacheable_coordinator(model_name="Navigator 2.0 / 10")
        first = build_device_info(coord)
        # Simulate model metadata change + cache invalidation (as the coordinator
        # does in _invalidate_device_info_cache after a web supplement update).
        coord.model_name = "Navigator 10"
        coord._device_info_cache = None
        rebuilt = build_device_info(coord)
        assert rebuilt is not first
        assert rebuilt["model"] == "Navigator 10"


class TestIdmEntityAvailable:
    def test_unavailable_when_coordinator_unavailable(self):
        coord = _make_coordinator(data={"temp": 22.0}, last_update_success=False)
        entity = _make_entity(coordinator=coord, reg=_make_register("temp"))
        # Coordinator base class returns False when last_update_success is False
        # We simulate this by patching super().available
        # Actually in our stub, available is based on last_update_success
        coord.last_update_success = False

        # Patch the super().available call via the parent class
        from unittest import mock

        from homeassistant.helpers.update_coordinator import CoordinatorEntity

        with mock.patch.object(
            CoordinatorEntity,
            "available",
            new_callable=lambda: property(lambda self: self.coordinator.last_update_success),
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
        assert entity._attr_unique_id == "test_entry_id_temp"

    def test_unused_entity_keeps_stable_unique_id_for_history(self):
        coord = _make_coordinator(
            data={"room_temp": UNUSED_VALUE},
            last_update_success=True,
            hide_unused=True,
        )
        entity = _make_entity(coordinator=coord, reg=_make_register("room_temp"))

        assert entity.available is False
        assert entity._attr_unique_id == "test_entry_id_room_temp"

    def test_unused_entity_becomes_available_again_without_unique_id_change(self):
        coord = _make_coordinator(
            data={"room_temp": UNUSED_VALUE},
            last_update_success=True,
            hide_unused=True,
        )
        entity = _make_entity(coordinator=coord, reg=_make_register("room_temp"))
        original_unique_id = entity._attr_unique_id

        assert entity.available is False
        # Simulate a successful poll that produces a real value. The real
        # coordinator recomputes unused_registers in _async_update_data, so we
        # mirror that here: a non-sentinel value means the register leaves the
        # unused set.
        coord.data = {"room_temp": 21.5}
        coord.unused_registers = set()

        assert entity.available is True
        assert entity._attr_unique_id == original_unique_id

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

    def test_unavailable_when_value_is_65535(self):
        coord = _make_coordinator(data={"sensor": 65535}, last_update_success=True, hide_unused=True)
        entity = _make_entity(coordinator=coord, reg=_make_register("sensor"))
        assert entity.available is False

    def test_unavailable_when_value_is_255(self):
        coord = _make_coordinator(data={"sensor": 255}, last_update_success=True, hide_unused=True)
        entity = _make_entity(coordinator=coord, reg=_make_register("sensor"))
        assert entity.available is False

    def test_unavailable_when_value_is_minus_32768(self):
        coord = _make_coordinator(data={"sensor": -32768}, last_update_success=True, hide_unused=True)
        entity = _make_entity(coordinator=coord, reg=_make_register("sensor"))
        assert entity.available is False

    def test_available_when_hide_unused_false_and_65535(self):
        coord = _make_coordinator(data={"sensor": 65535}, last_update_success=True, hide_unused=False)
        entity = _make_entity(coordinator=coord, reg=_make_register("sensor"))
        assert entity.available is True

    def test_normal_positive_value_available(self):
        coord = _make_coordinator(data={"sensor": 42.5}, last_update_success=True, hide_unused=True)
        entity = _make_entity(coordinator=coord, reg=_make_register("sensor"))
        assert entity.available is True
