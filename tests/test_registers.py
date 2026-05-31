"""Tests for register definitions and description builders."""

import pytest

from custom_components.idm_heatpump.registers import (
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
        regs = collect_all_registers(["a"], 0, {})
        float_regs = [r for r in regs if r.datatype == DataType.FLOAT]
        assert all(r.size == 2 for r in float_regs)

    def test_non_float_registers_have_size_one(self):
        regs = collect_all_registers(["a"], 0, {})
        for r in regs:
            if r.datatype != DataType.FLOAT:
                assert r.size == 1, f"Register {r.name} (type {r.datatype}) should have size 1"

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


class TestHkAddresses:
    """Validate heating circuit selects use library naming (hc_X_mode)."""

    def test_select_circuit_a_exists(self):
        descs_a = get_all_select_descriptions(["a"], 0, {})
        matches = [d for d in descs_a if d["register"].name == "hc_a_mode"]
        assert len(matches) == 1

    def test_select_circuit_b_exists(self):
        descs = get_all_select_descriptions(["a", "b"], 0, {})
        matches = [d for d in descs if d["register"].name == "hc_b_mode"]
        assert len(matches) == 1

    def test_all_seven_circuit_selects_exist(self):
        descs = get_all_select_descriptions(
            ["a", "b", "c", "d", "e", "f", "g"], 0, {}
        )
        for c in ["a", "b", "c", "d", "e", "f", "g"]:
            name = f"hc_{c}_mode"
            matches = [d for d in descs if d["register"].name == name]
            assert len(matches) == 1, f"No select for circuit {c}"


class TestZoneAddresses:
    """Validate zone register addresses from the library (zm prefix)."""

    def test_zone1_registers_created(self):
        descs = get_all_sensor_descriptions(["a"], 1, {0: 1})
        zone1 = [d for d in descs if d["register"].name.startswith("zm1_")]
        assert len(zone1) > 0

    def test_zone2_registers_created(self):
        descs = get_all_sensor_descriptions(["a"], 2, {0: 1, 1: 1})
        zone2 = [d for d in descs if d["register"].name.startswith("zm2_")]
        assert len(zone2) > 0

    def test_zone_count_zero_no_zone_registers(self):
        base_regs = collect_all_registers(["a"], 0, {})
        zone_regs = [r for r in base_regs if r.name.startswith("zm")]
        assert len(zone_regs) == 0, \
            f"No zone registers expected when zone_count=0, found: {[r.name for r in zone_regs]}"

    def test_zone_sensors_include_room_temps(self):
        descs = get_all_sensor_descriptions(["a"], 1, {0: 2})
        room_temps = [
            d for d in descs
            if d["register"].name.startswith("zm1_room") and "temp" in d["register"].name
        ]
        assert len(room_temps) > 0


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


class TestGetAllBinarySensorDescriptions:
    def test_returns_list(self):
        descs = get_all_binary_sensor_descriptions(["a"], 0, {})
        assert isinstance(descs, list)


class TestGetAllNumberDescriptions:
    def test_returns_list(self):
        descs = get_all_number_descriptions(["a"], 0, {})
        assert isinstance(descs, list)
        assert len(descs) > 0

    def test_more_circuits_more_numbers(self):
        one = get_all_number_descriptions(["a"], 0, {})
        two = get_all_number_descriptions(["a", "b"], 0, {})
        assert len(two) > len(one)


class TestGetAllSelectDescriptions:
    def test_returns_list(self):
        descs = get_all_select_descriptions(["a"], 0, {})
        assert isinstance(descs, list)
        assert len(descs) > 0

    def test_more_circuits_more_selects(self):
        one = get_all_select_descriptions(["a"], 0, {})
        two = get_all_select_descriptions(["a", "b"], 0, {})
        assert len(two) > len(one)


class TestGetAllSwitchDescriptions:
    def test_returns_list(self):
        descs = get_all_switch_descriptions(["a"], 0, {})
        assert isinstance(descs, list)
        assert len(descs) > 0

    def test_switch_addresses_are_sequential(self):
        descs = get_all_switch_descriptions(["a"], 0, {})
        addrs = sorted(d["register"].address for d in descs)
        assert len(addrs) == 4
        assert addrs == [1710, 1711, 1712, 1713]
