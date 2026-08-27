"""Tests for the IDM KNX communication-object catalogue.

The catalogue is transcribed from IDM's ETS example project for the
Weinzierl BAOS gateway, so these tests guard the two things a transcription
can get wrong: an object that no longer resolves to a register, and a
group-address calculation that puts an object somewhere else than the
object number says.
"""

import pathlib

import pytest
from idm_heatpump import build_register_map

from custom_components.idm_heatpump.controller_stats_reference import SYSCOUNT_REGISTER_REFERENCE
from custom_components.idm_heatpump.knx_catalog import (
    KNX_OBJECTS,
    MAX_OBJECT_NUMBER,
    OBJECT_GROUPS,
    InvalidGroupAddressError,
    format_group_address,
    object_for_register,
    parse_group_address,
    resolve_group_addresses,
    validate_base_address,
    validate_overrides,
)

FULL_REGISTER_MAP = build_register_map(circuits=list("ABCDEFG"), zone_modules=10, rooms_per_zone=8)


class TestCatalogueIntegrity:
    def test_object_numbers_are_unique(self):
        numbers = [obj.number for obj in KNX_OBJECTS]
        assert len(numbers) == len(set(numbers))

    def test_registers_are_unique(self):
        registers = [obj.register for obj in KNX_OBJECTS]
        assert len(registers) == len(set(registers))

    def test_objects_are_sorted_by_number(self):
        numbers = [obj.number for obj in KNX_OBJECTS]
        assert numbers == sorted(numbers)

    def test_no_object_exceeds_the_documented_maximum(self):
        assert max(obj.number for obj in KNX_OBJECTS) <= MAX_OBJECT_NUMBER

    def test_every_register_exists_in_the_library_map(self):
        missing = [obj.register for obj in KNX_OBJECTS if obj.register not in FULL_REGISTER_MAP]
        assert missing == []

    def test_writable_objects_map_to_writable_registers(self):
        wrong = [obj.register for obj in KNX_OBJECTS if obj.writable and not FULL_REGISTER_MAP[obj.register].writable]
        assert wrong == []

    def test_every_group_is_declared(self):
        assert {obj.group for obj in KNX_OBJECTS} <= set(OBJECT_GROUPS)

    def test_datapoint_types_are_known_main_types(self):
        allowed_prefixes = ("5.", "7.", "8.", "9.", "14.")
        for obj in KNX_OBJECTS:
            if obj.dpt is None:
                continue
            assert obj.dpt.startswith(allowed_prefixes), obj

    def test_agrees_with_the_syscount_cross_reference(self):
        """Both tables carry KNX object numbers; they must not disagree."""
        for register, row in SYSCOUNT_REGISTER_REFERENCE.items():
            if row.knx_object is None:
                continue
            obj = object_for_register(register)
            if obj is None:
                continue
            assert obj.number == row.knx_object, register

    def test_heating_circuit_modes_cover_every_circuit(self):
        for letter in "abcdefg":
            assert object_for_register(f"hc_{letter}_mode") is not None

    def test_zone_modules_are_laid_out_with_a_constant_stride(self):
        """Zone module N sits 47 objects above zone module N-1."""
        for zone in range(2, 11):
            previous = object_for_register(f"zm{zone - 1}_room1_temp")
            current = object_for_register(f"zm{zone}_room1_temp")
            assert current.number - previous.number == 47


class TestGroupAddressParsing:
    @pytest.mark.parametrize(
        ("text", "raw"),
        [
            ("8/0/1", 16385),
            ("8/1/12", 16652),
            ("31/7/255", 65535),
            ("8/1", 16385),
            ("16385", 16385),
        ],
    )
    def test_parses_every_notation(self, text, raw):
        assert parse_group_address(text) == raw

    @pytest.mark.parametrize("text", ["", "  ", "a/b/c", "8/0/256", "32/0/0", "8/8/0", "-1", "0/0/0", "1/2/3/4"])
    def test_rejects_unusable_addresses(self, text):
        with pytest.raises(InvalidGroupAddressError):
            parse_group_address(text)

    def test_formats_back_to_three_levels(self):
        assert format_group_address(16385) == "8/0/1"
        assert format_group_address(65535) == "31/7/255"

    def test_round_trips(self):
        for raw in (1, 2048, 16385, 65535):
            assert parse_group_address(format_group_address(raw)) == raw

    def test_base_address_must_leave_room_for_the_catalogue(self):
        assert validate_base_address("8/0/0") == 16384
        with pytest.raises(InvalidGroupAddressError):
            validate_base_address("31/7/255")


class TestResolveGroupAddresses:
    def test_derives_addresses_from_the_object_number(self):
        resolved = resolve_group_addresses("8/0/0", registers=["outdoor_temp", "hc_a_mode"])
        assert resolved == {"outdoor_temp": "8/0/1", "hc_a_mode": "8/0/222"}

    def test_carries_over_into_the_next_middle_group(self):
        resolved = resolve_group_addresses("8/0/0", registers=["total_heat_energy"])
        # Object 999 -> 16384 + 999 = 17383 -> 8/3/231
        assert resolved == {"total_heat_energy": "8/3/231"}

    def test_covers_the_whole_catalogue_by_default(self):
        assert len(resolve_group_addresses("8/0/0")) == len(KNX_OBJECTS)

    def test_filters_by_group(self):
        resolved = resolve_group_addresses("8/0/0", groups=["solar"])
        assert set(resolved) == {obj.register for obj in KNX_OBJECTS if obj.group == "solar"}

    def test_override_replaces_a_single_address(self):
        resolved = resolve_group_addresses(
            "8/0/0",
            overrides={"outdoor_temp": "1/2/3"},
            registers=["outdoor_temp", "hc_a_mode"],
        )
        assert resolved["outdoor_temp"] == "1/2/3"
        assert resolved["hc_a_mode"] == "8/0/222"

    def test_empty_override_excludes_the_object(self):
        resolved = resolve_group_addresses(
            "8/0/0",
            overrides={"outdoor_temp": "  "},
            registers=["outdoor_temp", "hc_a_mode"],
        )
        assert "outdoor_temp" not in resolved

    def test_rejects_an_unusable_base_address(self):
        with pytest.raises(InvalidGroupAddressError):
            resolve_group_addresses("nonsense")

    def test_every_address_is_distinct(self):
        resolved = resolve_group_addresses("8/0/0")
        assert len(set(resolved.values())) == len(resolved)


class TestValidateOverrides:
    def test_normalizes_and_drops_blanks(self):
        assert validate_overrides({"outdoor_temp": " 1/2/3 ", "hc_a_mode": ""}) == {"outdoor_temp": "1/2/3"}

    def test_rejects_unknown_registers(self):
        with pytest.raises(InvalidGroupAddressError):
            validate_overrides({"not_a_register": "1/2/3"})

    def test_rejects_duplicate_addresses(self):
        with pytest.raises(InvalidGroupAddressError):
            validate_overrides({"outdoor_temp": "1/2/3", "hc_a_mode": "1/2/3"})

    def test_rejects_unparsable_addresses(self):
        with pytest.raises(InvalidGroupAddressError):
            validate_overrides({"outdoor_temp": "99/9/9"})


class TestDocumentationWiring:
    """The KNX page has to reach both documentation surfaces.

    The wiki is mirrored to the GitHub wiki and copied into the GitHub Pages
    site, but the Pages navigation is a hand-maintained list in ``docs.js``.
    A page missing from either one is invisible without anything failing.
    """

    ROOT = pathlib.Path(__file__).resolve().parents[1]

    def test_wiki_page_exists(self):
        assert (self.ROOT / "docs" / "wiki" / "KNX-Bridge.md").is_file()

    def test_page_is_listed_in_the_sidebar(self):
        sidebar = (self.ROOT / "docs" / "wiki" / "_Sidebar.md").read_text(encoding="utf-8")
        assert "(KNX-Bridge)" in sidebar

    def test_page_is_listed_on_the_website(self):
        docs_js = (self.ROOT / "docs" / "public" / "docs" / "docs.js").read_text(encoding="utf-8")
        assert "KNX-Bridge.md" in docs_js

    def test_both_readmes_point_at_the_page(self):
        for name in ("README.md", "README_de.md"):
            readme = (self.ROOT / name).read_text(encoding="utf-8")
            assert "docs/#/knx-bridge" in readme, name
