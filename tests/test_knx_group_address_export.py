"""Tests for the ETS group address generator.

The generator's output is imported into ETS by hand, so a malformed file is
noticed late and by a user, not by CI. These tests pin the parts ETS is
strict about: the export namespace, the nesting of group ranges inside the
address ranges they claim, and the ``DPST-x-y`` spelling of datapoint types.
"""

import csv
import importlib.util
import io
import pathlib
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NS = "{http://knx.org/xml/ga-export/01}"


def _load_generator():
    spec = importlib.util.spec_from_file_location("_gen_knx_ga", ROOT / "scripts" / "generate_knx_group_addresses.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_gen_knx_ga"] = module
    spec.loader.exec_module(module)
    return module


gen = _load_generator()


def _xml(base="8/0/0", **kwargs):
    kwargs.setdefault("profile", "full")
    kwargs.setdefault("groups", None)
    kwargs.setdefault("registers", None)
    objects = gen.selected_objects(**kwargs)
    rows = gen.rows(base, objects, prefix="WP")
    return gen.render_xml(rows, project_name="Wärmepumpe"), rows


class TestDatapointTypes:
    @pytest.mark.parametrize(
        ("dpt", "expected"),
        [
            ("9.001", "DPST-9-1"),
            ("9.024", "DPST-9-24"),
            ("14.031", "DPST-14-31"),
            ("5.010", "DPST-5-10"),
            ("7.001", "DPST-7-1"),
            ("8.001", "DPST-8-1"),
            (None, "DPST-1-1"),
        ],
    )
    def test_converts_to_the_ets_spelling(self, dpt, expected):
        assert gen.dpt_attribute(dpt) == expected

    def test_every_catalogue_dpt_converts(self):
        for obj in gen.KNX_OBJECTS:
            value = gen.dpt_attribute(obj.dpt)
            assert value.startswith(("DPT-", "DPST-")), obj


class TestNames:
    def test_every_object_gets_a_name(self):
        for obj in gen.KNX_OBJECTS:
            name = gen.object_name(obj.register)
            assert name and name != obj.register, obj.register

    def test_extra_names_cover_what_the_integration_table_misses(self):
        """Every name is curated, not machine-derived from the register name.

        Checked by origin rather than by shape: a curated name is allowed to
        coincide with what the fallback would have produced (``Smart Grid
        Status`` does), so comparing the strings would flag it wrongly.
        """
        uncovered = [
            obj.register
            for obj in gen.KNX_OBJECTS
            if obj.register not in gen.EXTRA_NAMES
            and obj.register not in gen._names._GERMAN_NAMES
            and not gen._names._ZONE_ROOM_NAME_RE.match(obj.register)
        ]
        assert uncovered == []


class TestXmlStructure:
    def test_parses_and_uses_the_export_namespace(self):
        xml, _ = _xml()
        root = ET.fromstring(xml)
        assert root.tag == f"{NS}GroupAddress-Export"

    def test_addresses_sit_inside_the_range_they_are_nested_in(self):
        """ETS rejects a group address outside its parent range."""
        xml, _ = _xml()
        root = ET.fromstring(xml)
        for main in root.findall(f"{NS}GroupRange"):
            main_start, main_end = int(main.get("RangeStart")), int(main.get("RangeEnd"))
            for middle in main.findall(f"{NS}GroupRange"):
                start, end = int(middle.get("RangeStart")), int(middle.get("RangeEnd"))
                assert main_start <= start <= end <= main_end
                for address in middle.findall(f"{NS}GroupAddress"):
                    main_g, mid_g, sub = (int(part) for part in address.get("Address").split("/"))
                    raw = (main_g << 11) + (mid_g << 8) + sub
                    assert start <= raw <= end, address.get("Address")

    def test_no_range_starts_at_the_broadcast_address(self):
        xml, _ = _xml(base="0/0/1")
        root = ET.fromstring(xml)
        for group_range in root.iter(f"{NS}GroupRange"):
            assert int(group_range.get("RangeStart")) >= 1

    def test_every_object_appears_exactly_once(self):
        xml, rows = _xml()
        root = ET.fromstring(xml)
        addresses = [a.get("Address") for a in root.iter(f"{NS}GroupAddress")]
        assert len(addresses) == len(rows) == len(gen.KNX_OBJECTS)
        assert len(set(addresses)) == len(addresses)

    def test_names_and_dpts_are_present_on_every_address(self):
        xml, _ = _xml()
        root = ET.fromstring(xml)
        for address in root.iter(f"{NS}GroupAddress"):
            assert address.get("Name")
            assert address.get("DPTs")

    def test_special_characters_are_escaped(self):
        """German names carry umlauts and the middle groups a '·' separator."""
        xml, _ = _xml()
        ET.fromstring(xml)  # would raise on malformed markup
        assert "Außentemperatur" in xml

    def test_addresses_follow_base_plus_object_number(self):
        _, rows = _xml(base="11/0/0", profile="compact")
        by_register = {row["register"]: row for row in rows}
        assert by_register["outdoor_temp"]["address"] == "11/0/1"
        assert by_register["hc_a_mode"]["address"] == "11/0/222"


class TestSelection:
    def test_full_profile_is_the_whole_catalogue(self):
        assert len(gen.selected_objects(profile="full", groups=None, registers=None)) == len(gen.KNX_OBJECTS)

    def test_compact_profile_is_a_subset(self):
        objects = gen.selected_objects(profile="compact", groups=None, registers=None)
        assert 0 < len(objects) < len(gen.KNX_OBJECTS)
        assert {obj.register for obj in objects} == set(gen.COMPACT_REGISTERS)

    def test_compact_registers_all_exist(self):
        known = {obj.register for obj in gen.KNX_OBJECTS}
        assert set(gen.COMPACT_REGISTERS) <= known

    def test_groups_filter(self):
        objects = gen.selected_objects(profile="full", groups=["solar"], registers=None)
        assert {obj.group for obj in objects} == {"solar"}

    def test_unknown_group_is_rejected(self):
        with pytest.raises(SystemExit):
            gen.selected_objects(profile="full", groups=["nope"], registers=None)

    def test_unknown_register_is_rejected(self):
        with pytest.raises(SystemExit):
            gen.selected_objects(profile="full", groups=None, registers=["nope"])


class TestCsv:
    def test_is_parsable_and_carries_every_row(self):
        _, rows = _xml(profile="compact")
        text = gen.render_csv(rows, project_name="Wärmepumpe")
        parsed = list(csv.DictReader(io.StringIO(text), delimiter=";"))
        assert len(parsed) == len(rows)
        assert parsed[0]["Gruppenadresse"]
        assert parsed[0]["DPT"]
        assert parsed[0]["Richtung"] in ("lesen", "lesen/schreiben")

    def test_direction_matches_the_catalogue(self):
        _, rows = _xml(profile="compact")
        text = gen.render_csv(rows, project_name="Wärmepumpe")
        parsed = {r["Register"]: r["Richtung"] for r in csv.DictReader(io.StringIO(text), delimiter=";")}
        assert parsed["outdoor_temp"] == "lesen"
        assert parsed["hc_a_mode"] == "lesen/schreiben"


class TestBaseAddress:
    def test_rejects_an_unusable_base(self):
        with pytest.raises(gen.InvalidGroupAddressError):
            gen.rows("0/0/0", gen.KNX_OBJECTS, prefix="WP")

    def test_rejects_a_base_without_room_for_the_catalogue(self):
        with pytest.raises(gen.InvalidGroupAddressError):
            gen.rows("31/7/255", gen.KNX_OBJECTS, prefix="WP")
