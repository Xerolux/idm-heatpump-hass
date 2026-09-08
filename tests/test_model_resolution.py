"""Tests for the Navigator model resolution rules.

These rules decide which register map a controller gets, so they matter for
every entity. Before they were extracted they could only be reached through
the whole ``async_setup_entry`` path with heavy mocks; here each case is one
call.
"""

from __future__ import annotations

import logging

import pytest
from idm_heatpump import MODEL_NAVIGATOR_10, MODEL_NAVIGATOR_20, MODEL_NAVIGATOR_PRO, IdmModelInfo

from custom_components.idm_heatpump.const import (
    CONF_DETECTED_NAVIGATOR_VERSION,
    CONF_DETECTED_SOFTWARE_VERSION,
    CONF_DETECTED_WEB_VARIANT,
    CONF_MODEL_OVERRIDE,
    MODEL,
    MODEL_OVERRIDE_AUTO,
    MODEL_OVERRIDE_NAVIGATOR_10,
    MODEL_OVERRIDE_NAVIGATOR_20,
    MODEL_OVERRIDE_NAVIGATOR_PRO,
)
from custom_components.idm_heatpump.model_resolution import (
    DetectionResult,
    PlantShape,
    StoredDetection,
    model_info_from_name,
    model_name_for_override,
    plan_web_read,
    plant_shape,
    resolve_model,
    resolved_model_override,
)
from custom_components.idm_heatpump.web_data import IdmWebSupplement

NAV10 = "Navigator 10"
NAV20 = "Navigator 2.0"
PLANT = PlantShape(circuits=("a",), zone_count=0, enable_cascade=False)


def _info(model_name: str) -> IdmModelInfo:
    return model_info_from_name(model_name, PLANT)


def _web(model_name: str = "", software_version: str = "", web_variant: str | None = None) -> IdmWebSupplement:
    return IdmWebSupplement(
        navigator_version=model_name,
        software_version=software_version,
        web_variant=web_variant,
    )


def _resolve(**kwargs):
    """Resolve with sensible defaults so each test states only what it varies."""
    fresh = kwargs.pop("fresh", DetectionResult(model_name=NAV20, model_info=_info(NAV20)))
    stored = kwargs.pop("stored", StoredDetection())
    web = kwargs.pop("web", None)
    override = kwargs.pop("override", None)
    plant = kwargs.pop("plant", PLANT)
    assert not kwargs, f"unexpected keyword(s): {sorted(kwargs)}"
    return resolve_model(fresh, stored, web, override, plant)


class TestOverrideMapping:
    def test_known_override_values_map_to_library_names(self):
        assert model_name_for_override(MODEL_OVERRIDE_NAVIGATOR_10) == MODEL_NAVIGATOR_10
        assert model_name_for_override(MODEL_OVERRIDE_NAVIGATOR_20) == MODEL_NAVIGATOR_20
        assert model_name_for_override(MODEL_OVERRIDE_NAVIGATOR_PRO) == MODEL_NAVIGATOR_PRO

    def test_automatic_and_unknown_keep_detection(self):
        assert model_name_for_override(MODEL_OVERRIDE_AUTO) is None
        assert model_name_for_override("something else") is None

    @pytest.mark.parametrize(
        ("stored_value", "expected"),
        [
            ({}, None),
            ({CONF_MODEL_OVERRIDE: MODEL_OVERRIDE_AUTO}, None),
            ({CONF_MODEL_OVERRIDE: "   "}, None),
            ({CONF_MODEL_OVERRIDE: 42}, None),
            ({CONF_MODEL_OVERRIDE: MODEL_OVERRIDE_NAVIGATOR_10}, MODEL_NAVIGATOR_10),
            ({CONF_MODEL_OVERRIDE: f"  {MODEL_OVERRIDE_NAVIGATOR_10}  "}, MODEL_NAVIGATOR_10),
        ],
    )
    def test_entry_data_is_read_defensively(self, stored_value, expected):
        assert resolved_model_override(stored_value) == expected


class TestModelInfoFromName:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            (NAV20, MODEL_NAVIGATOR_20),
            (NAV10, MODEL_NAVIGATOR_10),
            ("Navigator Pro", MODEL_NAVIGATOR_PRO),
            # Generic, ambiguous and unknown all fall back to Navigator 2.0:
            # its register map is the one an older controller survives.
            (MODEL, MODEL_NAVIGATOR_20),
            ("Some Unknown Controller", MODEL_NAVIGATOR_20),
        ],
    )
    def test_name_decides_the_register_map(self, name, expected):
        assert model_info_from_name(name, PLANT).model_name == expected

    def test_plant_shape_reaches_the_model_info(self):
        info = model_info_from_name(NAV10, plant_shape(["a", "b"], 2, True))

        assert info.active_heating_circuits == ["A", "B"]
        assert info.zone_modules == 2
        assert info.has_cascade is True


class TestStoredDetection:
    def test_reads_and_cleans_the_entry_data(self):
        stored = StoredDetection.from_entry_data(
            {
                CONF_DETECTED_NAVIGATOR_VERSION: f"  {NAV10}  ",
                CONF_DETECTED_SOFTWARE_VERSION: " NAV10_20.24 ",
                CONF_DETECTED_WEB_VARIANT: "nav10",
            }
        )

        assert stored == StoredDetection(NAV10, "NAV10_20.24", "nav10")

    @pytest.mark.parametrize("variant", ["", "  ", "bogus", None, 7])
    def test_an_unusable_variant_is_dropped(self, variant):
        stored = StoredDetection.from_entry_data({CONF_DETECTED_WEB_VARIANT: variant})

        assert stored.web_variant is None

    def test_blank_strings_read_as_absent(self):
        stored = StoredDetection.from_entry_data(
            {CONF_DETECTED_NAVIGATOR_VERSION: "   ", CONF_DETECTED_SOFTWARE_VERSION: ""}
        )

        assert stored == StoredDetection()


class TestFreshDetectionAlone:
    def test_without_any_other_source_the_probe_wins(self):
        resolution = _resolve(fresh=DetectionResult(model_name=NAV10, model_info=_info(NAV10)))

        assert resolution.model_name == NAV10
        assert resolution.model_info.model_name == MODEL_NAVIGATOR_10
        assert resolution.data_updates == {}
        assert resolution.data_removals == frozenset()

    def test_a_failed_probe_still_yields_a_usable_register_map(self):
        """detect_model() may return nothing; setup must not depend on it."""
        resolution = _resolve(fresh=DetectionResult(model_name=MODEL, model_info=None))

        assert resolution.model_info.model_name == MODEL_NAVIGATOR_20

    def test_the_library_info_is_preferred_within_the_same_family(self):
        richer = _info(NAV10)
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV10, model_info=_info(NAV10), client_model_info=richer)
        )

        assert resolution.model_info is richer

    def test_the_library_info_fills_in_when_the_probe_returned_none(self):
        richer = _info(NAV10)
        resolution = _resolve(fresh=DetectionResult(model_name=NAV10, model_info=None, client_model_info=richer))

        assert resolution.model_info is richer


class TestStoredAgainstFresh:
    def test_a_matching_stored_model_is_kept_verbatim(self):
        """The stored name may be more specific than the probe's family."""
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV10, model_info=_info(NAV10)),
            stored=StoredDetection(navigator_version="Navigator 10 Pro-ish label"),
        )

        assert resolution.model_name == "Navigator 10 Pro-ish label"
        assert resolution.data_updates == {}

    def test_a_conflicting_stored_model_is_corrected_and_persisted(self):
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV10, model_info=_info(NAV10)),
            stored=StoredDetection(navigator_version=NAV20, software_version="OLD", web_variant="nav20"),
        )

        assert resolution.model_name == NAV10
        assert resolution.data_updates[CONF_DETECTED_NAVIGATOR_VERSION] == NAV10
        # The stored firmware and variant belonged to the wrong model.
        assert CONF_DETECTED_SOFTWARE_VERSION in resolution.data_removals
        assert CONF_DETECTED_WEB_VARIANT in resolution.data_removals

    def test_a_stored_model_is_trusted_when_the_probe_returned_no_info(self):
        resolution = _resolve(
            fresh=DetectionResult(model_name=MODEL, model_info=None),
            stored=StoredDetection(navigator_version=NAV10),
        )

        assert resolution.model_name == NAV10
        assert resolution.data_updates == {}

    def test_a_stored_firmware_survives_an_agreeing_model(self):
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV10, firmware_version=None, model_info=_info(NAV10)),
            stored=StoredDetection(navigator_version=NAV10, software_version="NAV10_20.24"),
        )

        assert resolution.firmware_version == "NAV10_20.24"

    def test_nothing_is_persisted_without_probe_info_to_correct_against(self):
        """A conflict the probe cannot vouch for must not rewrite stored data."""
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV10, model_info=None),
            stored=StoredDetection(navigator_version=NAV20),
        )

        assert resolution.data_updates == {}


class TestOverrideWins:
    def test_the_override_decides_the_model_and_the_register_map(self):
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV20, model_info=_info(NAV20)),
            override=MODEL_NAVIGATOR_10,
        )

        assert resolution.model_name == MODEL_NAVIGATOR_10
        assert resolution.model_info.model_name == MODEL_NAVIGATOR_10

    def test_a_stored_model_never_overrules_the_user(self):
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV20, model_info=_info(NAV20)),
            stored=StoredDetection(navigator_version=NAV20),
            override=MODEL_NAVIGATOR_10,
        )

        assert resolution.model_name == MODEL_NAVIGATOR_10
        assert resolution.data_updates == {}, "an override is a choice, not a stale detection"

    def test_the_web_may_contribute_firmware_but_not_the_model(self):
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV20, model_info=_info(NAV20)),
            web=_web(model_name=NAV10, software_version="NAV10_20.24"),
            override=MODEL_NAVIGATOR_20,
        )

        assert resolution.model_name == MODEL_NAVIGATOR_20
        assert resolution.firmware_version == "NAV10_20.24"

    def test_the_library_info_never_overrules_the_user(self):
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV20, model_info=_info(NAV20), client_model_info=_info(NAV20)),
            override=MODEL_NAVIGATOR_10,
        )

        assert resolution.model_info.model_name == MODEL_NAVIGATOR_10


class TestWebAgainstModbus:
    def test_an_agreeing_web_supplement_contributes_its_firmware(self):
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV10, model_info=_info(NAV10)),
            web=_web(model_name=NAV10, software_version="NAV10_20.24"),
        )

        assert resolution.model_name == NAV10
        assert resolution.firmware_version == "NAV10_20.24"

    def test_a_nav10_firmware_string_corrects_a_failed_modbus_probe(self):
        """Some Navigator 10 firmwares refuse register 4108, so the probe says 2.0.

        The nav10 web client can only have connected to a Navigator 10, and the
        firmware prefix confirms it, so the web evidence wins.
        """
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV20, model_info=_info(NAV20)),
            web=_web(model_name=NAV10, software_version="NAV10_20.24-880", web_variant="nav10"),
        )

        assert resolution.model_name == NAV10
        assert resolution.model_info.model_name == MODEL_NAVIGATOR_10
        assert resolution.data_updates[CONF_DETECTED_NAVIGATOR_VERSION] == NAV10
        assert resolution.data_updates[CONF_DETECTED_WEB_VARIANT] == "nav10"

    def test_a_conflicting_web_model_without_that_evidence_is_ignored(self):
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV20, model_info=_info(NAV20)),
            web=_web(model_name=NAV10, software_version="something else"),
        )

        assert resolution.model_name == NAV20
        assert resolution.model_info.model_name == MODEL_NAVIGATOR_20
        # Still recorded, so the stored value stops claiming the wrong model.
        assert resolution.data_updates[CONF_DETECTED_NAVIGATOR_VERSION] == NAV20

    def test_a_conflict_is_ignored_when_the_probe_returned_no_info(self):
        """Without probe info there is nothing for the web to contradict."""
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV20, model_info=None),
            web=_web(model_name=NAV10, software_version="NAV10_20.24"),
        )

        assert resolution.model_name == NAV10, "merge_model_info takes the web model"

    def test_no_web_supplement_changes_nothing(self):
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV10, firmware_version="fw", model_info=_info(NAV10)),
            web=None,
        )

        assert resolution.model_name == NAV10
        assert resolution.firmware_version == "fw"


class TestWebReadPlan:
    def test_the_hint_is_the_modbus_model(self):
        plan = plan_web_read(DetectionResult(model_name=NAV10, model_info=_info(NAV10)), StoredDetection())

        assert plan.model_hint == NAV10

    def test_an_override_becomes_the_hint(self):
        plan = plan_web_read(
            DetectionResult(model_name=NAV20, model_info=_info(NAV20)),
            StoredDetection(),
            MODEL_NAVIGATOR_10,
        )

        assert plan.model_hint == MODEL_NAVIGATOR_10

    def test_a_known_variant_locks_the_protocol(self):
        plan = plan_web_read(
            DetectionResult(model_name=NAV10, model_info=_info(NAV10)),
            StoredDetection(navigator_version=NAV10, web_variant="nav10"),
        )

        assert plan.preferred_variant == "nav10"
        assert plan.allow_variant_fallback is False

    def test_a_variant_stored_with_a_contradicted_model_is_not_trusted(self):
        """The stored variant belongs to a model the probe just disproved."""
        plan = plan_web_read(
            DetectionResult(model_name=NAV10, model_info=_info(NAV10)),
            StoredDetection(navigator_version=NAV20, web_variant="nav20"),
        )

        assert plan.preferred_variant is None
        assert plan.allow_variant_fallback is True


class TestLogging:
    def test_decisions_are_reported_rather_than_made_silently(self):
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV10, model_info=_info(NAV10)),
            stored=StoredDetection(navigator_version=NAV20),
        )

        levels = {level for level, _message, _args in resolution.log_lines}
        assert logging.INFO in levels
        assert all(isinstance(args, tuple) for _level, _message, args in resolution.log_lines)

    def test_an_override_is_reported_at_warning_level(self):
        """A silently active override is how a user ends up with the wrong map."""
        resolution = _resolve(override=MODEL_NAVIGATOR_10)

        assert any(level == logging.WARNING for level, _message, _args in resolution.log_lines)

    def test_every_message_can_be_formatted_with_its_arguments(self):
        resolution = _resolve(
            fresh=DetectionResult(model_name=NAV20, model_info=_info(NAV20)),
            stored=StoredDetection(navigator_version=NAV10, software_version="old", web_variant="nav10"),
            web=_web(model_name=NAV10, software_version="NAV10_20.24", web_variant="nav10"),
        )

        for _level, message, args in resolution.log_lines:
            message % args
