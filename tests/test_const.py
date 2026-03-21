"""Tests for constants and enums in const.py."""

import pytest

from custom_components.idm_heatpump_v2.const import (
    DOMAIN,
    HEATING_CIRCUITS,
    MAX_ROOM_COUNT,
    MAX_ZONE_COUNT,
    UNUSED_VALUE,
    CircuitMode,
    HeatPumpStatus,
    RoomMode,
    SmartGridStatus,
    SolarMode,
    SystemMode,
)


class TestDomain:
    def test_domain_value(self):
        assert DOMAIN == "idm_heatpump_v2"

    def test_unused_value(self):
        assert UNUSED_VALUE == -1.0

    def test_heating_circuits(self):
        assert HEATING_CIRCUITS == ["a", "b", "c", "d", "e", "f", "g"]
        assert len(HEATING_CIRCUITS) == 7

    def test_max_zone_count(self):
        assert MAX_ZONE_COUNT == 10

    def test_max_room_count(self):
        assert MAX_ROOM_COUNT == 8


class TestSystemMode:
    def test_values(self):
        assert SystemMode.STANDBY == 0
        assert SystemMode.AUTOMATIC == 1
        assert SystemMode.AWAY == 2
        assert SystemMode.HOLIDAY == 3
        assert SystemMode.HOT_WATER_ONLY == 4
        assert SystemMode.HEATING_COOLING_ONLY == 5

    def test_is_int_enum(self):
        import enum
        assert issubclass(SystemMode, enum.IntEnum)


class TestCircuitMode:
    def test_values(self):
        assert CircuitMode.OFF == 0
        assert CircuitMode.TIMED == 1
        assert CircuitMode.NORMAL == 2
        assert CircuitMode.ECO == 3
        assert CircuitMode.MANUAL_HEAT == 4
        assert CircuitMode.MANUAL_COOL == 5


class TestRoomMode:
    def test_values(self):
        assert RoomMode.OFF == 0
        assert RoomMode.AUTOMATIC == 1
        assert RoomMode.ECO == 2
        assert RoomMode.NORMAL == 3
        assert RoomMode.COMFORT == 4


class TestSolarMode:
    def test_values(self):
        assert SolarMode.AUTO == 0
        assert SolarMode.WATER == 1
        assert SolarMode.HEATING == 2
        assert SolarMode.WATER_HEATING == 3
        assert SolarMode.SOURCE_POOL == 4


class TestSmartGridStatus:
    def test_values(self):
        assert SmartGridStatus.GRID_BLOCKED_SOLAR_OFF == 0
        assert SmartGridStatus.GRID_ALLOWED_SOLAR_OFF == 1
        assert SmartGridStatus.GRID_UNUSED_SOLAR_ON == 2
        assert SmartGridStatus.GRID_BLOCKED_SOLAR_ON == 4


class TestHeatPumpStatus:
    def test_values(self):
        assert HeatPumpStatus.OFF == 0
        assert HeatPumpStatus.HEATING == 1
        assert HeatPumpStatus.COOLING == 2
        assert HeatPumpStatus.WATER == 4
        assert HeatPumpStatus.DEFROSTING == 8

    def test_is_int_flag(self):
        import enum
        assert issubclass(HeatPumpStatus, enum.IntFlag)

    def test_flag_combination(self):
        combined = HeatPumpStatus.HEATING | HeatPumpStatus.WATER
        assert HeatPumpStatus.HEATING in combined
        assert HeatPumpStatus.WATER in combined
        assert HeatPumpStatus.COOLING not in combined
