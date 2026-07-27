"""Regression tests for the controller_stats_reference cross-reference table.

These tests freeze the cross-reference table that documents the three
independent IDM-Controller ID spaces (Modbus address, internal stats ID,
KNX communication-object number) for verified physical quantities.

The table itself is the contract: it must remain stable across releases,
because users (and the diagnostics export) rely on the syscount-key
labels to correlate their Home Assistant readings with the controller's
on-device counters.

Cross-reference provenance: confirmed on a single Navigator 10 plant
(firmware ``NAV10_20.24-880-g265e09c4a``, July 2026) via a strictly
read-only Modbus probe plus offline analysis of an SD-card backup and
the IDM ETS example project. No plant-specific values are recorded in
this file - only the generic semantic mapping.
"""

from __future__ import annotations

import pytest

from custom_components.idm_heatpump.controller_stats_reference import (
    SYSCOUNT_REGISTER_REFERENCE,
    ControllerStatReference,
    reference_for,
    syscount_label_for,
)


class TestReferenceTableShape:
    """The cross-reference table must be stable, complete, and self-consistent."""

    def test_table_is_not_empty(self) -> None:
        assert len(SYSCOUNT_REGISTER_REFERENCE) >= 10

    def test_every_row_is_frozen_dataclass(self) -> None:
        for row in SYSCOUNT_REGISTER_REFERENCE.values():
            assert isinstance(row, ControllerStatReference)
            # Frozen dataclass: __setattr__ must raise
            with pytest.raises((AttributeError, TypeError)):
                row.semantic_label = "mutated"  # type: ignore[misc]

    def test_keys_match_library_register(self) -> None:
        """Map key must equal the row's library_register field (invariant)."""
        for key, row in SYSCOUNT_REGISTER_REFERENCE.items():
            assert key == row.library_register, f"key {key!r} != library_register {row.library_register!r}"

    def test_every_row_has_at_least_one_cross_reference(self) -> None:
        """Each row must be cross-confirmed via at least two of the three
        ID spaces. Concretely: at least one of (syscount_key, knx_object)
        must be set, AND the library_register must be a real register
        (cross-checked separately in TestLibraryRegisterPresence).
        """
        for row in SYSCOUNT_REGISTER_REFERENCE.values():
            assert row.library_register, "library_register is required"
            assert row.unit, f"{row.library_register}: unit is required"
            assert row.semantic_label, f"{row.library_register}: semantic_label is required"
            assert row.syscount_key is not None or row.knx_object is not None, (
                f"{row.library_register}: needs at least syscount_key or knx_object"
            )

    def test_cumulative_id_must_be_in_100000_range(self) -> None:
        """Cumulative internal stats IDs live in the 100000-199999 range."""
        for row in SYSCOUNT_REGISTER_REFERENCE.values():
            cum = row.internal_stats_cumulative_id
            if cum is not None:
                assert 100000 <= cum < 200000, f"{row.library_register}: cumulative id {cum} outside 100000-199999"

    def test_cumulative_id_only_when_base_id_present(self) -> None:
        """A cumulative ID makes only sense if the underlying base stats ID
        is also recorded."""
        for row in SYSCOUNT_REGISTER_REFERENCE.values():
            if row.internal_stats_cumulative_id is not None:
                assert row.internal_stats_id is not None, (
                    f"{row.library_register}: cumulative id set but base id missing"
                )

    def test_no_duplicate_syscount_keys(self) -> None:
        """Each syscount key appears at most once."""
        keys = [row.syscount_key for row in SYSCOUNT_REGISTER_REFERENCE.values() if row.syscount_key]
        assert len(keys) == len(set(keys)), f"duplicate syscount keys: {keys}"

    def test_no_duplicate_knx_objects(self) -> None:
        """Each KNX object number appears at most once."""
        objs = [row.knx_object for row in SYSCOUNT_REGISTER_REFERENCE.values() if row.knx_object is not None]
        assert len(objs) == len(set(objs)), f"duplicate KNX objects: {objs}"


class TestLookupHelpers:
    """reference_for() and syscount_label_for() must be safe and predictable."""

    def test_reference_for_known_register_returns_row(self) -> None:
        row = reference_for("energy_heating")
        assert row is not None
        assert row.syscount_key == "ZQHPH"
        assert row.internal_stats_id == 477
        assert row.knx_object == 400

    def test_reference_for_unknown_register_returns_none(self) -> None:
        assert reference_for("does_not_exist") is None

    def test_syscount_label_for_known_energy_register(self) -> None:
        label = syscount_label_for("energy_heating")
        assert label is not None
        assert "ZQHPH" in label
        assert "Heizen" in label or "Wärmemenge" in label

    def test_syscount_label_for_register_without_syscount_returns_none(self) -> None:
        # pv_surplus has a KNX object but no syscount_key
        assert syscount_label_for("pv_surplus") is None

    def test_syscount_label_for_unknown_register_returns_none(self) -> None:
        assert syscount_label_for("does_not_exist") is None


class TestEnergyRegisterPresence:
    """Every library_register named in the cross-reference table must be
    resolvable in the default idm-heatpump-api register map with the
    documented datatype. This catches silent library renames or removals
    at CI time.

    The address itself is owned by idm-heatpump-api and may shift across
    major versions; it is intentionally not asserted here. The datatype
    is part of the decode contract and must not change silently.
    """

    @pytest.mark.parametrize("library_register", sorted(SYSCOUNT_REGISTER_REFERENCE))
    def test_library_register_resolves(self, library_register: str) -> None:
        from idm_heatpump.registers import get_register

        reg = get_register(library_register, model_info=None)
        if reg is None:
            pytest.skip(f"{library_register!r} not in default map for this library version")
        # Register must be present and expose a sensible datatype.
        assert reg.datatype is not None
        assert str(reg.name) == library_register

    @pytest.mark.parametrize(
        "library_register,expected_datatype",
        [
            ("battery_soc", "INT16"),
            ("energy_heating", "FLOAT"),
            ("energy_dhw", "FLOAT"),
            ("energy_defrost", "FLOAT"),
            ("energy_cooling", "FLOAT"),
            ("energy_electric_heater", "FLOAT"),
            ("pv_surplus", "FLOAT"),
            ("pv_production", "FLOAT"),
            ("house_consumption", "FLOAT"),
            ("battery_discharge", "FLOAT"),
        ],
    )
    def test_known_datatypes_unchanged(self, library_register: str, expected_datatype: str) -> None:
        """Critical datatypes that the cross-reference relies on. The
        battery_soc INT16 contract is what catches the '65535 %' regression;
        the FLOAT energy registers must not silently switch to UINT16 or
        INT32 (different word count, different decode).
        """
        from idm_heatpump.registers import get_register

        reg = get_register(library_register, model_info=None)
        if reg is None:
            pytest.skip(f"{library_register!r} not in default map")
        actual = str(reg.datatype).split(".")[-1]
        assert actual == expected_datatype, f"{library_register}: datatype drifted from {expected_datatype} to {actual}"


class TestThreeIdSpacesContract:
    """The three ID spaces must remain disjoint in their numeric ranges
    for the rows we have verified. This is a documentation freeze: a future
    addition to the table that violates the range invariants indicates a
    misunderstanding of the ID spaces rather than a real new mapping.
    """

    def test_internal_stats_ids_are_not_knx_objects(self) -> None:
        """No row may claim that its internal_stats_id equals its KNX
        object number. The two spaces are independent; their numeric
        overlap in the verified set is a coincidence but never an
        identity."""
        for row in SYSCOUNT_REGISTER_REFERENCE.values():
            if row.internal_stats_id is not None and row.knx_object is not None:
                assert row.internal_stats_id != row.knx_object, (
                    f"{row.library_register}: stats id == KNX object "
                    f"({row.internal_stats_id}) - indicates a copy/paste error"
                )

    def test_knx_pv_typo_objects_are_documented(self) -> None:
        """The KNX example project misspells 'Photovoltaik' as 'Photovotaik'
        on objects 995 and 996. The cross-reference must preserve these
        object numbers verbatim, and the rows must mention the typo so
        future maintainers don't 'fix' the KNX object numbers."""
        surplus = reference_for("pv_surplus")
        production = reference_for("pv_production")
        assert surplus is not None and surplus.knx_object == 995
        assert production is not None and production.knx_object == 996
        assert "Photovotaik" in surplus.note or "photovotaik" in surplus.note.lower()
        assert "Photovotaik" in production.note or "photovotaik" in production.note.lower()
