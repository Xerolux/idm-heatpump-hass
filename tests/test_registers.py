"""Tests for register definitions and description builders."""

import pytest

from custom_components.idm_heatpump.registers import (
    HK_CONST_ADDR,
    HK_MODE_ADDR,
    HK_OFFSET,
    ZONE_BASE_ADDRESSES,
    collect_all_registers,
    get_all_binary_sensor_descriptions,
    get_all_number_descriptions,
    get_all_select_descriptions,
    get_all_sensor_descriptions,
    get_all_switch_descriptions,
)
from custom_components.idm_heatpump.modbus_client import DataType, RegisterDef


class TestCollectAllRegisters:
    def test_returns_list_of_register_defs(self):
        regs = collect_all_registers(["a"], 0, {})
        assert isinstance(regs, list)
        assert all(isinstance(r, RegisterDef) for r in regs)

    def test_more_circuits_more_registers(self):
        regs_one = collect_all_registers(["a"], 0, {})
        regs_two = collect_all_registers(["a", "b"], 0, {})
        assert len(regs_two) > len(regs_one)

    def test_zones_add_registers(self):
        regs_no_zone = collect_all_registers(["a"], 0, {})
        regs_with_zone = collect_all_registers(["a"], 1, {0: 2})
        assert len(regs_with_zone) > len(regs_no_zone)

    def test_unique_addresses(self):
        regs = collect_all_registers(["a", "b", "c"], 0, {})
        addresses = [r.address for r in regs]
        assert len(addresses) == len(set(addresses)), "Duplicate register addresses found"

    def test_unique_addresses_all_circuits_and_zones(self):
        regs = collect_all_registers(["a", "b", "c", "d", "e", "f", "g"], 3, {0: 2, 1: 3, 2: 1})
        addresses = [r.address for r in regs]
        assert len(addresses) == len(set(addresses)), "Duplicate register addresses found"

    def test_all_circuits(self):
        regs = collect_all_registers(["a", "b", "c", "d", "e", "f", "g"], 2, {0: 3, 1: 2})
        assert len(regs) > 0

    def test_float_registers_consume_two_addresses(self):
        """FLOAT registers have size=2 and must not cause address collisions."""
        regs = collect_all_registers(["a"], 0, {})
        float_regs = [r for r in regs if r.datatype == DataType.FLOAT]
        assert all(r.size == 2 for r in float_regs)

    def test_non_float_registers_have_size_one(self):
        regs = collect_all_registers(["a"], 0, {})
        for r in regs:
            if r.datatype != DataType.FLOAT:
                assert r.size == 1, f"Register {r.name} (type {r.datatype}) should have size 1"

    def test_cascade_flag_adds_numbers(self):
        without = get_all_number_descriptions(["a"], 0, {}, enable_cascade=False)
        with_cascade = get_all_number_descriptions(["a"], 0, {}, enable_cascade=True)
        assert len(with_cascade) > len(without)

    def test_all_descriptions_have_register_key(self):
        for getter in [
            get_all_sensor_descriptions,
            get_all_binary_sensor_descriptions,
            get_all_number_descriptions,
            get_all_select_descriptions,
            get_all_switch_descriptions,
        ]:
            descs = getter(["a"], 0, {})
            for desc in descs:
                assert "register" in desc, f"Description missing 'register' key: {desc}"

    def test_all_descriptions_have_description_key(self):
        for getter in [
            get_all_sensor_descriptions,
            get_all_binary_sensor_descriptions,
            get_all_number_descriptions,
            get_all_select_descriptions,
            get_all_switch_descriptions,
        ]:
            descs = getter(["a"], 0, {})
            for desc in descs:
                assert "description" in desc, f"Description missing 'description' key: {desc}"


class TestHkOffsets:
    """Validate that heating circuit (HK) addresses use correct offsets."""

    def test_hk_offset_values(self):
        assert HK_OFFSET["a"] == 0
        assert HK_OFFSET["b"] == 2
        assert HK_OFFSET["c"] == 4
        assert HK_OFFSET["d"] == 6
        assert HK_OFFSET["e"] == 8
        assert HK_OFFSET["f"] == 10
        assert HK_OFFSET["g"] == 12

    def test_hk_mode_addresses_sequential(self):
        """Each circuit's mode register is 1 higher than the previous."""
        circuits = ["a", "b", "c", "d", "e", "f", "g"]
        base = HK_MODE_ADDR["a"]
        for i, c in enumerate(circuits):
            assert HK_MODE_ADDR[c] == base + i, f"HK_MODE_ADDR[{c}] is wrong"

    def test_hk_const_addresses_sequential(self):
        """Each circuit's const register is 1 higher than the previous."""
        circuits = ["a", "b", "c", "d", "e", "f", "g"]
        base = HK_CONST_ADDR["a"]
        for i, c in enumerate(circuits):
            assert HK_CONST_ADDR[c] == base + i, f"HK_CONST_ADDR[{c}] is wrong"

    def test_select_circuit_a_address(self):
        """Circuit 'a' select (HK mode) address from _hk_selects is 1393."""
        descs_a = get_all_select_descriptions(["a"], 0, {})
        # HK a mode select is at 1393 (base = 1393 + ord('a')-ord('a') = 1393+0)
        hk_mode_selects = [
            d for d in descs_a if d["register"].name == "hk_a_mode"
        ]
        assert len(hk_mode_selects) == 1
        assert hk_mode_selects[0]["register"].address == 1393

    def test_select_circuit_b_address_incremented(self):
        """Circuit 'b' select address is base + 1."""
        descs = get_all_select_descriptions(["a", "b"], 0, {})
        hk_b_selects = [d for d in descs if d["register"].name == "hk_b_mode"]
        assert len(hk_b_selects) == 1
        assert hk_b_selects[0]["register"].address == 1394


class TestZoneAddresses:
    """Validate zone register addresses follow the documented formula."""

    def test_zone_base_addresses_formula(self):
        """Zone n starts at 2000 + 65*(n-1)."""
        for i in range(10):
            assert ZONE_BASE_ADDRESSES[i] == 2000 + 65 * i

    def test_zone1_mode_sensor_address(self):
        descs = get_all_sensor_descriptions(["a"], 1, {0: 1})
        zone1_mode = [d for d in descs if d["register"].name == "zone1_mode"]
        assert len(zone1_mode) == 1
        assert zone1_mode[0]["register"].address == 2000

    def test_zone2_mode_sensor_address(self):
        descs = get_all_sensor_descriptions(["a"], 2, {0: 1, 1: 1})
        zone2_mode = [d for d in descs if d["register"].name == "zone2_mode"]
        assert len(zone2_mode) == 1
        assert zone2_mode[0]["register"].address == 2065  # 2000 + 65*1

    def test_zone1_room1_temp_address(self):
        """Room 1 temperature is at zone_base + 2."""
        descs = get_all_sensor_descriptions(["a"], 1, {0: 1})
        room1_temp = [d for d in descs if d["register"].name == "zone1_room1_temp"]
        assert len(room1_temp) == 1
        assert room1_temp[0]["register"].address == 2002  # 2000 + 2

    def test_zone1_room2_temp_address(self):
        """Room 2 temperature offset is +7 from room 1."""
        descs = get_all_sensor_descriptions(["a"], 1, {0: 2})
        room2_temp = [d for d in descs if d["register"].name == "zone1_room2_temp"]
        assert len(room2_temp) == 1
        assert room2_temp[0]["register"].address == 2009  # 2000 + 2 + 7

    def test_zone_count_zero_no_zone_registers(self):
        base_regs = collect_all_registers(["a"], 0, {})
        zone_regs = [r for r in base_regs if r.name.startswith("zone")]
        assert len(zone_regs) == 0, \
            f"No zone registers expected when zone_count=0, found: {[r.name for r in zone_regs]}"

    def test_max_zones_and_rooms(self):
        """10 zones with 8 rooms each should not produce address collisions."""
        zone_rooms = {i: 8 for i in range(10)}
        regs = collect_all_registers(["a"], 10, zone_rooms)
        addresses = [r.address for r in regs]
        assert len(addresses) == len(set(addresses)), "Duplicate addresses with max zones/rooms"


class TestRegisterIntegrity:
    """Validate structural integrity of all register definitions."""

    def test_all_registers_have_valid_datatypes(self):
        regs = collect_all_registers(["a", "b"], 1, {0: 2})
        valid_types = set(DataType)
        for r in regs:
            assert r.datatype in valid_types, f"Invalid datatype for {r.name}: {r.datatype}"

    def test_writable_registers_have_names(self):
        all_descs = (
            get_all_number_descriptions(["a"], 0, {})
            + get_all_select_descriptions(["a"], 0, {})
            + get_all_switch_descriptions(["a"], 0, {})
        )
        for desc in all_descs:
            reg = desc["register"]
            assert reg.writable, f"Entity description register {reg.name} should be writable"
            assert reg.name, f"Writable register at {reg.address} has no name"

    def test_sensor_registers_are_readonly(self):
        descs = get_all_sensor_descriptions(["a"], 0, {})
        for desc in descs:
            reg = desc["register"]
            assert not reg.writable, f"Sensor register {reg.name} should be read-only"

    def test_binary_sensor_registers_are_readonly(self):
        descs = get_all_binary_sensor_descriptions(["a"], 0, {})
        for desc in descs:
            reg = desc["register"]
            assert not reg.writable, f"Binary sensor register {reg.name} should be read-only"

    def test_enum_options_not_none_for_select(self):
        descs = get_all_select_descriptions(["a"], 0, {})
        for desc in descs:
            reg = desc["register"]
            assert reg.enum_options is not None, \
                f"Select register {reg.name} must have enum_options"

    def test_switch_registers_are_bool(self):
        descs = get_all_switch_descriptions(["a"], 0, {})
        for desc in descs:
            reg = desc["register"]
            assert reg.datatype == DataType.BOOL, \
                f"Switch register {reg.name} should be BOOL, got {reg.datatype}"

    def test_number_registers_have_min_max(self):
        """All number entity registers should define min/max bounds."""
        from custom_components.idm_heatpump.registers import _number  # noqa: F401
        descs = get_all_number_descriptions(["a"], 0, {})
        for desc in descs:
            reg = desc["register"]
            assert reg.min_val is not None, f"Number register {reg.name} missing min_val"
            assert reg.max_val is not None, f"Number register {reg.name} missing max_val"
            assert reg.min_val < reg.max_val, \
                f"Number register {reg.name}: min ({reg.min_val}) >= max ({reg.max_val})"

    def test_description_keys_unique_per_platform(self):
        """Each platform's description keys must be unique."""
        for name, getter in [
            ("sensor", get_all_sensor_descriptions),
            ("binary_sensor", get_all_binary_sensor_descriptions),
            ("number", get_all_number_descriptions),
            ("select", get_all_select_descriptions),
            ("switch", get_all_switch_descriptions),
        ]:
            descs = getter(["a", "b"], 1, {0: 2})
            keys = [d["description"].key for d in descs]
            assert len(keys) == len(set(keys)), \
                f"Duplicate description keys in {name} platform: {[k for k in keys if keys.count(k) > 1]}"


class TestGetAllSensorDescriptions:
    def test_returns_list(self):
        descs = get_all_sensor_descriptions(["a"], 0, {})
        assert isinstance(descs, list)

    def test_each_has_register(self):
        descs = get_all_sensor_descriptions(["a"], 0, {})
        for desc in descs:
            assert "register" in desc or "description" in desc

    def test_more_circuits_more_sensors(self):
        one = get_all_sensor_descriptions(["a"], 0, {})
        two = get_all_sensor_descriptions(["a", "b"], 0, {})
        assert len(two) > len(one)

    def test_zones_add_sensors(self):
        no_zone = get_all_sensor_descriptions(["a"], 0, {})
        with_zone = get_all_sensor_descriptions(["a"], 1, {0: 2})
        assert len(with_zone) > len(no_zone)

    def test_more_rooms_more_sensors(self):
        one_room = get_all_sensor_descriptions(["a"], 1, {0: 1})
        two_rooms = get_all_sensor_descriptions(["a"], 1, {0: 2})
        assert len(two_rooms) > len(one_room)


class TestGetAllBinarySensorDescriptions:
    def test_returns_list(self):
        descs = get_all_binary_sensor_descriptions(["a"], 0, {})
        assert isinstance(descs, list)
        assert len(descs) > 0

    def test_each_has_register(self):
        descs = get_all_binary_sensor_descriptions(["a"], 0, {})
        for desc in descs:
            assert "register" in desc or "description" in desc

    def test_zones_add_binary_sensors(self):
        no_zone = get_all_binary_sensor_descriptions(["a"], 0, {})
        with_zone = get_all_binary_sensor_descriptions(["a"], 1, {0: 2})
        assert len(with_zone) > len(no_zone)


class TestGetAllNumberDescriptions:
    def test_returns_list(self):
        descs = get_all_number_descriptions(["a"], 0, {})
        assert isinstance(descs, list)
        assert len(descs) > 0

    def test_more_circuits_more_numbers(self):
        one = get_all_number_descriptions(["a"], 0, {})
        two = get_all_number_descriptions(["a", "b"], 0, {})
        assert len(two) > len(one)

    def test_cascade_adds_numbers(self):
        without = get_all_number_descriptions(["a"], 0, {}, enable_cascade=False)
        with_c = get_all_number_descriptions(["a"], 0, {}, enable_cascade=True)
        assert len(with_c) > len(without)


class TestGetAllSelectDescriptions:
    def test_returns_list(self):
        descs = get_all_select_descriptions(["a"], 0, {})
        assert isinstance(descs, list)
        assert len(descs) > 0

    def test_more_circuits_more_selects(self):
        one = get_all_select_descriptions(["a"], 0, {})
        two = get_all_select_descriptions(["a", "b"], 0, {})
        assert len(two) > len(one)

    def test_all_selects_have_enum_options(self):
        descs = get_all_select_descriptions(["a", "b"], 1, {0: 2})
        for desc in descs:
            assert desc["register"].enum_options, \
                f"Select {desc['description'].key} has no enum_options"


class TestGetAllSwitchDescriptions:
    def test_returns_list(self):
        descs = get_all_switch_descriptions(["a"], 0, {})
        assert isinstance(descs, list)

    def test_same_regardless_of_circuits(self):
        """Switches are not circuit-specific."""
        one = get_all_switch_descriptions(["a"], 0, {})
        two = get_all_switch_descriptions(["a", "b", "c"], 0, {})
        assert len(one) == len(two)

    def test_switch_count_is_four(self):
        """There are exactly 4 GLT switches defined."""
        descs = get_all_switch_descriptions(["a"], 0, {})
        assert len(descs) == 4

    def test_switch_addresses_are_sequential(self):
        """GLT switches are at 1710, 1711, 1712, 1713."""
        descs = get_all_switch_descriptions(["a"], 0, {})
        addresses = sorted(d["register"].address for d in descs)
        assert addresses == [1710, 1711, 1712, 1713]
