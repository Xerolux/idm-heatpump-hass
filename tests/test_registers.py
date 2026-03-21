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
from custom_components.idm_heatpump.modbus_client import RegisterDef


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

    def test_all_circuits(self):
        regs = collect_all_registers(["a", "b", "c", "d", "e", "f", "g"], 2, {0: 3, 1: 2})
        assert len(regs) > 0


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


class TestGetAllBinarySensorDescriptions:
    def test_returns_list(self):
        descs = get_all_binary_sensor_descriptions(["a"], 0, {})
        assert isinstance(descs, list)
        assert len(descs) > 0

    def test_each_has_register(self):
        descs = get_all_binary_sensor_descriptions(["a"], 0, {})
        for desc in descs:
            assert "register" in desc or "description" in desc


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

    def test_same_regardless_of_circuits(self):
        """Switches are not circuit-specific."""
        one = get_all_switch_descriptions(["a"], 0, {})
        two = get_all_switch_descriptions(["a", "b", "c"], 0, {})
        assert len(one) == len(two)
