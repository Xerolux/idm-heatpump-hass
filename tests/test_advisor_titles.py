"""Tests for localized advisor recommendation titles (0.27/WP3)."""

from __future__ import annotations

import pytest

from custom_components.idm_heatpump.advisor_titles import (
    TITLE_TEXTS,
    localized_title,
    render_title,
)
from custom_components.idm_heatpump.predictive_advisor import (
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
    recommendation_from_dict,
)


class TestRenderTitle:
    def test_every_key_renders_both_languages(self) -> None:
        assert TITLE_TEXTS, "the table must not be empty"
        for key, (german, english) in TITLE_TEXTS.items():
            assert render_title(key, None, "de") == german, key
            assert render_title(key, None, "en") == english, key

    def test_unknown_key_answers_none(self) -> None:
        assert render_title("no_such_key", {"a": "1"}, "de") is None

    def test_placeholders_fill_in_both_languages(self) -> None:
        values = {"circuit": "A", "curve": "0.30", "recommended": "0.32"}

        english = render_title("advisor_heating_curve_review", values, "en")
        german = render_title("advisor_heating_curve_review", values, "de")

        assert english == "Review heating curve HC A: 0.30 -> 0.32"
        assert german == "Heizkurve HK A prüfen: 0,30 → 0,32"

    def test_german_swaps_decimal_commas_only_in_values(self) -> None:
        english = render_title("advisor_dhw_window_price", {"window": "14:00-16:00", "heat_cost": "0.235"}, "en")
        german = render_title("advisor_dhw_window_price", {"window": "14:00-16:00", "heat_cost": "0.235"}, "de")

        assert "0.235 €/kWh" in english
        assert "14:00-16:00" in german
        assert "0,235 €/kWh" in german

    def test_localized_title_falls_back_to_the_stored_english_title(self) -> None:
        assert localized_title("unknown_key", {}, "Fallback title", "de") == "Fallback title"


class TestRecommendationCarriesTheKey:
    def _recommendation(self, **overrides: object) -> Recommendation:
        payload: dict[str, object] = {
            "id": "heating_curve_a_2026-11-10",
            "category": RecommendationCategory.HEATING_CURVE,
            "severity": RecommendationSeverity.HINT,
            "title": "Review heating curve HC A: 0.30 -> 0.32",
            "title_key": "advisor_heating_curve_review",
            "title_values": {"circuit": "A", "curve": "0.30", "recommended": "0.32"},
        }
        payload.update(overrides)
        return Recommendation(**payload)  # type: ignore[arg-type]

    def test_summary_keeps_english_and_adds_the_localized_title(self) -> None:
        record = self._recommendation()

        summary = record.summary("de")

        assert summary["title"] == "Review heating curve HC A: 0.30 -> 0.32"
        assert summary["title_localized"] == "Heizkurve HK A prüfen: 0,30 → 0,32"

        assert record.summary("en")["title_localized"] == "Review heating curve HC A: 0.30 -> 0.32"

    def test_legacy_records_without_a_key_fall_back_to_their_title(self) -> None:
        record = self._recommendation(title_key="", title_values={})

        assert record.summary("de")["title_localized"] == record.title

    def test_persistence_round_trips_key_and_values(self) -> None:
        record = self._recommendation()

        restored = recommendation_from_dict(record.to_dict())

        assert restored is not None
        assert restored.title_key == "advisor_heating_curve_review"
        assert restored.title_values == {"circuit": "A", "curve": "0.30", "recommended": "0.32"}
        assert restored.summary("de")["title_localized"] == "Heizkurve HK A prüfen: 0,30 → 0,32"

    def test_legacy_stored_records_parse_without_the_new_fields(self) -> None:
        legacy = {
            "id": "anomaly_flow_rate_low_2026-11-10",
            "category": "anomaly",
            "severity": "warning",
            "title": "Heat-circle flow is 40% below its 10-day baseline",
            "description": "",
            "current_value": None,
            "recommended_value": None,
            "unit": None,
            "confidence": 0.7,
            "reasons": ["heat_circle_flow_below_baseline"],
            "created_at": "2026-11-10T08:00:00+00:00",
            "status": "new",
            "refreshed_at": "2026-11-10T08:00:00+00:00",
        }

        restored = recommendation_from_dict(legacy)

        assert restored is not None
        assert restored.title_key == ""
        assert restored.title_values == {}
        assert restored.summary("de")["title_localized"] == restored.title

    def test_malformed_new_fields_are_sanitized(self) -> None:
        payload = self._recommendation().to_dict()
        payload["title_key"] = 42
        payload["title_values"] = ["not", "a", "mapping"]

        restored = recommendation_from_dict(payload)

        assert restored is not None
        assert restored.title_key == "42"
        assert restored.title_values == {}

    def test_content_equality_includes_the_localization_fields(self) -> None:
        base = self._recommendation()
        same = self._recommendation()
        changed = self._recommendation(title_values={"circuit": "A", "curve": "0.30", "recommended": "0.34"})

        from custom_components.idm_heatpump.predictive_advisor import _same_recommendation_content

        assert _same_recommendation_content(base, same)
        assert not _same_recommendation_content(base, changed)


@pytest.mark.parametrize(
    ("key", "values"),
    [
        ("anomaly_flow_rate_low", {"percent": "40", "days": "10"}),
        ("anomaly_flow_rate_low_heating", {"percent": "40", "days": "10"}),
        ("anomaly_flow_rate_low_dhw", {"percent": "40", "days": "10"}),
        ("anomaly_spread_high", {}),
        ("anomaly_spread_high_k", {"delta": "2.5"}),
        ("anomaly_compressor_starts", {"percent": "60", "days": "12"}),
        ("anomaly_dhw_charge_long", {"percent": "35"}),
        ("advisor_dhw_window_pv", {"window": "13:00-15:00", "pv_kwh": "4.2"}),
        ("advisor_dhw_window_conflict", {}),
    ],
)
def test_every_template_renders_with_its_documented_placeholders(key: str, values: dict[str, str]) -> None:
    german = render_title(key, values, "de")
    english = render_title(key, values, "en")

    assert german and german != english, "localized titles must differ from the English data field"
    for value in values.values():
        expected_de = value.replace(".", ",")
        assert expected_de in german
        assert value in english
