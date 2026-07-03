"""Tests for register definitions and description builders."""

from types import SimpleNamespace

from custom_components.idm_heatpump.registers import (
    _sort_descriptions,
    collect_all_registers,
    get_all_binary_sensor_descriptions,
    get_all_number_descriptions,
    get_all_select_descriptions,
    get_all_sensor_descriptions,
    get_all_switch_descriptions,
    sort_entity_descriptions,
)
from idm_heatpump import IdmModelInfo, RegisterDef
from idm_heatpump.client import DataType
from idm_heatpump.const import MODEL_NAVIGATOR_20


def _make_order_desc(name: str, address: int) -> dict:
    return {
        "register": RegisterDef(address=address, datatype=DataType.FLOAT, name=name),
        "description": SimpleNamespace(key=name, name=name, entity_category=None),
    }


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

    def test_detected_navigator_2_excludes_navigator_10_registers(self):
        model_info = IdmModelInfo(
            model_name=MODEL_NAVIGATOR_20,
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )

        regs = collect_all_registers(["a"], 0, {}, model_info=model_info)

        assert all(reg.address != 4108 for reg in regs)
        assert all(reg.name != "power_limit_hp" for reg in regs)

    def test_description_sorting_uses_functional_blocks(self):
        descs = [
            _make_order_desc("runtime_heating_hours", 1008),
            _make_order_desc("zm1_room1_temp", 1006),
            _make_order_desc("hc_a_flow_temp", 1003),
            _make_order_desc("myidm_id", 1010),
            _make_order_desc("pv_surplus", 1007),
            _make_order_desc("outside_air_temperature", 1005),
            _make_order_desc("cascade_req_heat_temp", 1009),
            _make_order_desc("enable_cooling", 1002),
            _make_order_desc("hotwater_temperature", 1004),
            _make_order_desc("failure_eheating", 1001),
        ]

        ordered_names = [desc["register"].name for desc in sort_entity_descriptions(descs)]

        assert ordered_names == [
            "failure_eheating",
            "enable_cooling",
            "hc_a_flow_temp",
            "hotwater_temperature",
            "outside_air_temperature",
            "zm1_room1_temp",
            "pv_surplus",
            "runtime_heating_hours",
            "cascade_req_heat_temp",
            "myidm_id",
        ]

        assert _sort_descriptions(descs) == sort_entity_descriptions(descs)


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
        descs = get_all_select_descriptions(["a", "b", "c", "d", "e", "f", "g"], 0, {})
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
        assert len(zone_regs) == 0, (
            f"No zone registers expected when zone_count=0, found: {[r.name for r in zone_regs]}"
        )

    def test_zone_sensors_include_room_temps(self):
        descs = get_all_sensor_descriptions(["a"], 1, {0: 2})
        room_temps = [d for d in descs if d["register"].name.startswith("zm1_room") and "temp" in d["register"].name]
        assert len(room_temps) > 0

    def test_zone_room_count_respected_in_numbers(self):
        """Regression test: zone room count must be respected. PR #40 fix."""
        # Configure zone 0 with only 2 rooms
        descs = get_all_number_descriptions(["a"], 1, {0: 2})
        room_regs = {d["register"].name for d in descs if d["register"].name.startswith("zm1_room")}
        # Extract room indices from names like "zm1_room1_temp"
        import re

        room_idxs = sorted({int(re.search(r"room(\d+)", r).group(1)) for r in room_regs})
        # Must contain only rooms 1 and 2 (not 3-6, which library defaults to)
        assert room_idxs == [1, 2], f"Expected rooms [1,2], got {room_idxs}"

    def test_zone_room_count_respected_in_sensors(self):
        """Regression test: sensor room count must also respect zone config. PR #40 fix."""
        descs = get_all_sensor_descriptions(["a"], 1, {0: 3})
        room_regs = {d["register"].name for d in descs if d["register"].name.startswith("zm1_room")}
        import re

        room_idxs = sorted({int(re.search(r"room(\d+)", r).group(1)) for r in room_regs})
        assert room_idxs == [1, 2, 3], f"Expected rooms [1,2,3], got {room_idxs}"


class TestGltDualExposure:
    """GLT-Messwerte (Library 0.3.2): beschreibbare Messwert-Register
    erscheinen sowohl als Sensor als auch als Number (Vorgabe)."""

    PV_BLOCK = [
        "pv_surplus",
        "pv_production",
        "house_consumption",
        "battery_discharge",
        "battery_soc",
        "electric_heater_power",
    ]

    def test_pv_block_dual_exposed(self):
        sensor_names = {d["register"].name for d in get_all_sensor_descriptions(["a"], 0, {})}
        number_names = {d["register"].name for d in get_all_number_descriptions(["a"], 0, {})}
        for name in self.PV_BLOCK:
            assert name in sensor_names, f"{name} fehlt als Sensor"
            assert name in number_names, f"{name} fehlt als Number"

    def test_zone_room_measurements_dual_exposed(self):
        sensor_names = {d["register"].name for d in get_all_sensor_descriptions(["a"], 1, {0: 2})}
        number_names = {d["register"].name for d in get_all_number_descriptions(["a"], 1, {0: 2})}
        for name in ("zm1_room1_temp", "zm1_room1_humidity"):
            assert name in sensor_names, f"{name} fehlt als Sensor"
            assert name in number_names, f"{name} fehlt als Number"

    def test_setpoints_are_number_only(self):
        sensor_names = {d["register"].name for d in get_all_sensor_descriptions(["a"], 1, {0: 2})}
        number_names = {d["register"].name for d in get_all_number_descriptions(["a"], 1, {0: 2})}
        for name in ("pv_target_value", "zm1_room1_setpoint"):
            assert name not in sensor_names, f"{name} sollte kein Sensor sein"
            assert name in number_names, f"{name} fehlt als Number"

    def test_dual_number_names_are_marked_as_vorgabe(self):
        numbers = get_all_number_descriptions(["a"], 0, {})
        for d in numbers:
            if d["register"].name in self.PV_BLOCK:
                assert d["description"].name.endswith("(Vorgabe)"), (
                    f"Number {d['register'].name} braucht den Suffix '(Vorgabe)': {d['description'].name}"
                )

    def test_zone_room_numbers_disabled_by_default(self):
        """Raum-Vorgabe (Vorgabe) ist nur wirksam mit externem/GLT-Raumsensor;
        da der aktive Sensortyp nicht per Modbus auslesbar ist, muss die Number
        standardmäßig deaktiviert sein (PR: entity permissions audit)."""
        numbers = get_all_number_descriptions(["a"], 1, {0: 2})
        checked = set()
        for d in numbers:
            if d["register"].name in ("zm1_room1_temp", "zm1_room1_humidity"):
                assert d["description"].entity_registry_enabled_default is False, (
                    f"{d['register'].name} sollte standardmäßig deaktiviert sein"
                )
                checked.add(d["register"].name)
        assert checked == {"zm1_room1_temp", "zm1_room1_humidity"}

    def test_pv_block_numbers_enabled_by_default(self):
        numbers = get_all_number_descriptions(["a"], 0, {})
        checked = set()
        for d in numbers:
            if d["register"].name in self.PV_BLOCK:
                assert d["description"].entity_registry_enabled_default is True, (
                    f"{d['register'].name} sollte standardmäßig aktiviert sein"
                )
                checked.add(d["register"].name)
        assert checked == set(self.PV_BLOCK)

    def test_power_limit_numbers_disabled_by_default(self):
        numbers = get_all_number_descriptions(["a"], 0, {})
        checked = set()
        for d in numbers:
            if d["register"].name in {"power_limit_hp", "power_limit_cascade"}:
                assert d["description"].entity_registry_enabled_default is False, (
                    f"{d['register'].name} is model-dependent and must not be advertised by default"
                )
                checked.add(d["register"].name)
        assert checked == {"power_limit_hp", "power_limit_cascade"}

    def test_register_changes_from_doc_update(self):
        names = {r.name for r in collect_all_registers(["a"], 0, {})}
        assert "ext_demand_brine_pump_m16" not in names
        assert "ext_demand_groundwater_pump_m15_sw_max" in names
        assert "variable_input" in names
        assert "pv_target_value" in names


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
            assert reg.enum_options is not None, f"Select register {reg.name} must have enum_options"

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
            assert len(keys) == len(set(keys)), (
                f"Duplicate description keys in {name} platform: {[k for k in keys if keys.count(k) > 1]}"
            )


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
