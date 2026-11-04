"""Shared evidence, restart-safe readback changes and matched optimization review."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.idm_heatpump import advisor_evidence as evidence
from custom_components.idm_heatpump.ai_advisor import fact_report
from custom_components.idm_heatpump.ai_cloud import cloud_facts
from custom_components.idm_heatpump.assist_agent import IdmHeatpumpConversationEntity, _route_intent
from custom_components.idm_heatpump.predictive_advisor import (
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
)
from custom_components.idm_heatpump.predictive_advisor_entities import IdmAdvisorEvidenceSensor
from tests.test_ai_advisor import manager

NOW = 20000 * 86400.0


def _history() -> evidence.AnalysisHistory:
    obj = manager()
    obj._coordinator.unused_registers = set()
    obj._coordinator.data.update(
        hp_operating_mode=1, hc_a_heating_curve=1.0, hc_a_room_temp=21.2, hc_a_room_setpoint_heat_normal=21
    )
    obj._coordinator.operation_analysis = SimpleNamespace(total_compressor_starts=10, supports_compressor=True)
    obj._coordinator.register_required_registers = MagicMock()
    obj._coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    obj._coordinator.config_entry.async_on_unload = MagicMock()
    return evidence.AnalysisHistory(SimpleNamespace(), "test", obj._coordinator, ("a",))


def _records(
    *, after_cop: float = 3.6, after_comfort: float | None = 0.2, after_outdoor: float = 5, after_target: float = 21
) -> list[dict]:
    rows = []
    electric = thermal = 0.0
    for index, offset in enumerate(range(-72 * 3600, 78 * 3600 + 1, 600)):
        electric += 2 / 6
        thermal += (3 if offset <= 0 else after_cop) * 2 / 6
        rows.append(
            {
                "at": NOW + offset,
                "connected": True,
                "mode": 1,
                "total_electrical_kwh": electric,
                "total_thermal_kwh": thermal,
                "outdoor_temp": 5 if offset <= 0 else after_outdoor,
                "compressor_starts_total": index // 12,
                "hc_a_heating_curve": 1.0 if offset <= 0 else 0.98,
                "hc_a_room_setpoint_heat_normal": 21 if offset <= 0 else after_target,
                "hc_a_room_deviation_k": 0.2 if offset <= 0 else after_comfort,
                "room_deviation_abs_k": 0.2 if offset <= 0 else after_comfort,
            }
        )
    return rows


def _review(**kwargs) -> evidence.AnalysisHistory:
    history = _history()
    history.records = _records(**kwargs)
    history.changes = [{"at": NOW, "circuit": "a", "before": 1.0, "after": 0.98}]
    return history


@pytest.mark.parametrize(
    "cop,comfort,status",
    [
        (3.6, 0.2, "observed_improvement"),
        (2.4, 0.2, "observed_deterioration"),
        (3.6, 1.0, "mixed_outcome"),
        (3.0, 0.2, "no_clear_change"),
        (3.0, 1.0, "observed_deterioration"),
        (2.4, -0.01, "observed_deterioration"),
    ],
)
def test_review_reports_observed_outcome_without_causal_claim(cop, comfort, status) -> None:
    history = _review(after_cop=cop, after_comfort=comfort)
    result = history.optimization_review(NOW + 78 * 3600)
    assert result["status"] == status
    assert result["matched_heating_hours"] == pytest.approx(72)
    assert result["cause_verified"] is False
    assert result["cop_change_percent"] == pytest.approx(100 * (cop / 3 - 1), abs=0.1)
    assert result["before_metrics"]["starts_per_hour"] is not None


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"after_outdoor": 15}, "matched_heating_history"),
        ({"after_target": 22}, "room_target_changed"),
        ({"after_comfort": None}, "energy_or_comfort"),
    ],
)
def test_review_leaves_incomparable_or_missing_evidence_open(kwargs, reason) -> None:
    result = _review(**kwargs).optimization_review(NOW + 78 * 3600)
    assert result["status"] in ("not_comparable", "insufficient_data")
    assert result["reason"] == reason
    assert "cop_change_percent" not in result


def test_short_post_period_and_overlapping_changes_do_not_prove_improvement() -> None:
    history = _review()
    assert history.optimization_review(NOW + 24 * 3600)["status"] == "collecting_after"
    history.changes.insert(0, {"at": NOW - 86400, "circuit": "a", "before": 1.1, "after": 1.0})
    assert history.optimization_review(NOW + 78 * 3600)["reason"] == "overlapping_changes"


def test_review_requires_coverage_in_both_windows() -> None:
    history = _review()
    history.records = history.records[400:]
    assert history.optimization_review(NOW + 78 * 3600)["reason"] == "period_coverage"


def test_standby_or_mixed_mode_never_establishes_heating_improvement() -> None:
    history = _review()
    for row in history.records:
        row["mode"] = 5
    assert history.optimization_review(NOW + 78 * 3600)["status"] == "insufficient_data"


def test_recorded_change_and_reversal_within_sampling_interval_are_not_lost() -> None:
    history = _history()
    coordinator = history.coordinator
    coordinator.poll_statistics.last_success = datetime.fromtimestamp(NOW, UTC)
    history.observe(NOW)
    coordinator.data["hc_a_heating_curve"] = 0.98
    history.observe(NOW + 10)
    history.observe(NOW + 20)
    assert len(history.changes) == 1
    coordinator.data["hc_a_heating_curve"] = 1.0
    history.observe(NOW + 30)
    assert [row["after"] for row in history.changes] == [0.98, 1.0]
    assert len(history.records) == 1
    coordinator.last_update_success = False
    history.observe(NOW + 40)
    assert history.records[-1]["connected"] is False


async def test_history_is_allowlisted_restart_safe_and_bounded() -> None:
    history = _history()
    now = time.time()
    history._store.data = {
        "records": [
            None,
            {},
            {"at": now - 30 * 86400},
            {"at": now, "connected": True, "private": "SECRET", "outdoor_temp": 5},
        ],
        "changes": [
            None,
            {"at": now, "circuit": "bad"},
            {"at": now, "circuit": "a", "before": 1, "after": 0.98},
            {"at": now, "circuit": "a", "before": None},
        ],
    }
    await history.async_load()
    assert len(history.records) == len(history.changes) == 1
    assert "SECRET" not in str(history._serialize())
    await history.async_save()
    assert history._store.data["changes"][0]["after"] == 0.98
    history._store.async_load = AsyncMock(side_effect=OSError())
    await history.async_load()


async def test_single_owner_registers_consumers_and_survives_reload() -> None:
    history = _history()
    coordinator = history.coordinator
    entry = coordinator.config_entry
    coordinator.analysis_history = history
    assert await evidence.async_ensure_analysis(SimpleNamespace(), entry, coordinator) is history
    del coordinator.analysis_history
    created = await evidence.async_ensure_analysis(SimpleNamespace(), entry, coordinator)
    assert coordinator.analysis_history is created
    coordinator.register_required_registers.assert_called_once()
    entry.async_on_unload.assert_called_once()
    assert "hc_a_heating_curve" in created.required_registers


def test_one_analysis_is_consumed_by_reports_assist_and_entities() -> None:
    obj = manager()
    history = _review()
    now = NOW + 78 * 3600
    obj._coordinator.analysis_history = history
    shared = history.analysis(now)
    facts = obj.build_facts("daily", now)
    assert facts["analysis"] is shared
    assert facts["period"] is shared["period"]
    assert facts["optimization_review"]["status"] == "observed_improvement"
    for language in ("en", "de"):
        report = fact_report(facts, language)
        assert evidence.render_analysis(shared, language, topic="optimization") in report
        assert len(report) < 6000
    coordinator = history.coordinator
    coordinator.analysis_history = history
    coordinator.last_update_success = True
    agent = IdmHeatpumpConversationEntity(coordinator, None)
    with patch.object(evidence.time, "time", return_value=now):
        assert agent._answer("optimization", "en") == evidence.render_analysis(shared, "en", topic="optimization")
        for key in ("advisor_changes", "advisor_optimization_review"):
            sensor = IdmAdvisorEvidenceSensor(coordinator, key)
            assert sensor.native_value is not None
            assert sensor.extra_state_attributes["write_actions"] is False
    projected = cloud_facts(facts)
    assert projected["optimization_review_status"] == "observed_improvement"
    assert "circuit" not in projected["optimization_review"]


@pytest.mark.parametrize(
    "utterance,intent",
    [
        ("Warum ist der Verbrauch heute höher?", "changes"),
        ("What changed?", "changes"),
        ("Wie entwickelt sich die Taktung?", "cycling"),
        ("Welche Daten fehlen noch?", "data_quality"),
        ("Hat die Änderung geholfen?", "optimization"),
        ("Did it help?", "optimization"),
    ],
)
def test_new_questions_have_dedicated_intents(utterance: str, intent: str) -> None:
    assert _route_intent(utterance) == intent


@pytest.mark.parametrize("language", ["en", "de"])
def test_missing_history_is_explained_for_every_new_question(language: str) -> None:
    history = _history()
    analysis = history.analysis(NOW)
    for topic in ("changes", "cycling", "data_quality", "optimization"):
        assert evidence.render_analysis(analysis, language, topic=topic)
        agent = IdmHeatpumpConversationEntity(history.coordinator, None)
        assert agent._answer(topic, language)


def test_recommendation_explains_values_reasons_and_confidence_in_both_languages() -> None:
    recommendation = Recommendation(
        id="curve",
        category=RecommendationCategory.HEATING_CURVE,
        severity=RecommendationSeverity.HINT,
        title="Review heating curve",
        current_value=1.0,
        recommended_value=0.98,
        confidence=0.75,
        reasons=("room_temperature_above_target",),
    )
    for language in ("en", "de"):
        result = recommendation.summary(language)["explanation"]
        assert result["confidence_percent"] == 75
        assert result["current_value"] == 1.0 and result["suggested_value"] == 0.98
        assert result["first_check"] and result["missing_evidence"]
        assert result["reason_codes"] == ["room_temperature_above_target"]
    assert recommendation.summary("en")["explanation"] != recommendation.summary("de")["explanation"]
    window = Recommendation(
        id="window",
        category=RecommendationCategory.DHW,
        severity=RecommendationSeverity.INFO,
        title="DHW window",
        recommended_value="12:00-15:00",
    )
    agent = IdmHeatpumpConversationEntity(_history().coordinator, SimpleNamespace(active_recommendations=[window]))
    assert "None" not in agent._answer("recommendation", "en")
    assert "12:00-15:00" in agent._answer("recommendation", "en")


def test_period_changes_include_comfort_cycling_and_hot_water_context() -> None:
    history = _review()
    result = history.analysis(NOW + 78 * 3600)
    assert result["comparison"]["status"] == "observed_comparison"
    assert {"compressor_starts_observed", "dhw_share_observed_percent", "room_deviation_abs_k"} <= result[
        "period"
    ].keys()
    assert result["changes"] == []
    assert "keine deutlichen" in evidence.render_analysis(result, "de")
    assert "Previous window" in evidence.render_analysis(result, "en", topic="cycling")


def test_storage_budget_prunes_old_details_and_invalidates_cache(monkeypatch) -> None:
    history = _review()
    history.analysis(NOW + 78 * 3600)
    monkeypatch.setattr(evidence, "_MAX_STORAGE_BYTES", 20_000)
    before = len(history.records)
    payload = history._serialize()
    import json

    assert len(json.dumps(payload, ensure_ascii=True, indent=4).encode()) <= 20_000
    assert len(history.records) < before
    assert not history._cache
    assert history.changes


def test_clock_rollback_and_invalid_readback_do_not_create_changes() -> None:
    history = _history()
    history.coordinator.poll_statistics.last_success = datetime.fromtimestamp(NOW, UTC)
    history.observe(NOW)
    history.coordinator.data["hc_a_heating_curve"] = 0.98
    history.observe(NOW - 60)
    assert history.changes == []
    history.coordinator.data["hc_a_heating_curve"] = -1
    history.observe(NOW + 10)
    assert history.changes == []


def test_cop_improvement_with_worse_cycling_is_mixed() -> None:
    history = _review()
    for index, row in enumerate(history.records):
        if row["at"] > NOW:
            row["compressor_starts_total"] = index
    assert history.optimization_review(NOW + 78 * 3600)["status"] == "mixed_outcome"


def test_nonzero_changes_are_rendered_with_context_and_not_called_savings() -> None:
    history = _review()
    # Contrast the last 24 h with the preceding 24 h, preserving valid counters.
    now = NOW + 48 * 3600
    for row in history.records:
        if row["at"] >= NOW + 24 * 3600:
            row["total_electrical_kwh"] += (row["at"] - NOW - 24 * 3600) / 3600
            row["room_deviation_abs_k"] = 0.5
            row["mode"] = 4
    result = history.analysis(now)
    assert result["changes"]
    text = evidence.render_analysis(result, "en")
    assert "Electrical energy" in text and "outdoor temperature" in text
    assert "does not establish a cause or savings" in text
