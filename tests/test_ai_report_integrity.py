"""Measurement reports do not require or trust free-form model interpretation."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.idm_heatpump import ai_advisor as ai
from custom_components.idm_heatpump.config_flow import IdmHeatpumpOptionsFlow
from tests.test_ai_advisor import manager
from tests.test_ai_cloud import options


@pytest.mark.parametrize("kind", ai.REPORT_TYPES)
@pytest.mark.parametrize("provider", ["ollama", "ha_task", "openai", "zai"])
async def test_default_report_needs_no_credentials_model_or_budget(kind, provider):
    obj = manager()
    obj._options.pop(ai.CONF_AI_UNVERIFIED_TEXT)
    obj._options["ai_provider"] = provider
    obj._options[ai.CONF_AI_URL] = "invalid"
    obj.cloud_requests = 2
    obj._cloud_budget_loaded = False
    with (
        patch.object(ai, "async_local_report", AsyncMock()) as local,
        patch.object(ai, "async_cloud_report", AsyncMock()) as cloud,
        patch.object(ai, "async_ha_task_report", AsyncMock()) as task,
    ):
        result = await obj.async_generate(kind)
    for call in (local, cloud, task):
        call.assert_not_awaited()
    assert result["quality"]["output_source"] == "facts"
    assert result["quality"]["model_used"] is False
    assert obj.cloud_requests == 2
    assert obj.reports[kind]["provider"] == "facts"
    assert obj.reports[kind]["model"] is None
    assert "ohne KI-Deutung" in result["report"]


@pytest.mark.parametrize("language", ["en", "de"])
def test_facts_preserve_health_semantics_units_and_missing_data(language):
    facts = manager().build_facts("daily", time.time())
    facts["current"].update(total_electrical_kwh=98765.0, outdoor_temp=0.0, dhw_temp_top=None)
    facts["health_checks_current"] = {
        "health_communication": False,
        "health_low_cop": True,
        "health_long_defrost": None,
    }
    text = ai.fact_report(facts, language)
    assert "98765" not in text
    if language == "en":
        assert "Communication: not flagged" in text
        assert "Low COP: flagged" in text
        assert "Long defrost: unknown" in text
        assert "Outdoor temperature: 0.00 °C" in text
        assert "DHW storage top temperature: unavailable" in text
    else:
        assert "Kommunikation: kein Hinweis" in text
        assert "Niedriger COP: auffällig" in text
        assert "Lange Abtauung: nicht beurteilbar" in text
    assert len(text) < 6000


async def test_disabling_prose_replaces_even_current_guard_text_preserving_history():
    obj = manager()
    obj._options[ai.CONF_AI_UNVERIFIED_TEXT] = False
    facts = obj.build_facts("daily", time.time())
    stamp = datetime.now(UTC).isoformat()
    obj._store.data = {
        "reports": {
            "daily": {
                "report": "All checks are unknown. Lifetime counters are today's energy.",
                "facts": facts,
                "generated_at": stamp,
                "quality": {"guard_version": 3, "output_source": "ai"},
                "provider": "ollama",
                "model": "old-model",
            }
        }
    }
    await obj.async_load()
    assert "Lifetime" not in obj.report
    assert obj.reports["daily"]["provider"] == "facts"
    assert obj.reports["daily"]["model"] is None
    assert obj.facts == facts and obj.generated_at == stamp
    await obj.async_stop()
    assert "Lifetime" not in json.dumps(obj._store.data)


async def test_safe_configuration_requires_no_provider_setup():
    flow = IdmHeatpumpOptionsFlow()
    flow.config_entry = MagicMock(options={}, title="IDM")
    await flow.async_step_init()
    await flow.async_step_guided_mode({"setup_level": "standard"})
    await flow.async_step_guided_choose({"selected_features": ["ai_advisor"]})
    await flow.async_step_guided_toggle({ai.CONF_AI_ADVISOR: True})
    result = await flow.async_step_guided_detail({ai.CONF_AI_UNVERIFIED_TEXT: False})
    assert result["step_id"] == "guided_review"


@pytest.mark.parametrize(
    "stored",
    [
        [],
        "corrupt",
        17,
        False,
        {"cloud_day": "bad"},
        {"cloud_day": "2026-02-30"},
        {"cloud_day": "", "cloud_requests": 2},
    ],
)
async def test_nonmapping_storage_never_resets_cloud_spending(stored):
    obj = manager()
    obj._options.update(options())
    obj._store.async_load = AsyncMock(return_value=stored)
    await obj.async_load()
    with (
        patch.object(ai, "async_cloud_report", AsyncMock()) as call,
        pytest.raises(ai.AdvisorError, match="ai_cloud_budget_unavailable"),
    ):
        await obj.async_generate()
    call.assert_not_awaited()


async def test_backward_clock_cannot_reset_daily_limit():
    obj = manager()
    obj._options.update(options())
    obj._store.async_load = AsyncMock(return_value={"cloud_day": "2099-01-01", "cloud_requests": 2})
    await obj.async_load()
    with (
        patch.object(ai, "async_cloud_report", AsyncMock()) as call,
        pytest.raises(ai.AdvisorError, match="ai_cloud_daily_limit_reached"),
    ):
        await obj.async_generate()
    call.assert_not_awaited()
    assert obj.cloud_requests == 2


def test_previous_window_and_learning_keep_distinct_labels():
    facts = manager().build_facts("daily", time.time())
    facts["previous_period"].update(cop_observed=3.21, energy_counter_coverage_percent=80.0)
    facts["learning"] = {"baseline_cop": 4.0, "current_cop": 3.2, "deviation_percent": -20.0}
    text = ai.fact_report(facts, "en")
    assert "Previous window: COP: 3.21" in text
    assert "Previous window: counter coverage: 80.00 %" in text
    assert "Learned baseline COP: 4.00" in text
    assert "Deviation from baseline COP: -20.00 %" in text
