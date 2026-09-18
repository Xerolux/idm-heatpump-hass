"""Storage budget, persistence, scheduler and learning regression tests."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.idm_heatpump import ai_advisor as ai
from custom_components.idm_heatpump.ai_advisor_entities import AI_METRICS, IdmAiMetricSensor, IdmAiReportButton
from custom_components.idm_heatpump.ai_learning import MAX_BUCKETS, LearningHistory
from custom_components.idm_heatpump.const import DOMAIN
from custom_components.idm_heatpump.device_hierarchy import (
    build_subdevice_info,
    expected_subdevices,
    resolve_device_scope,
)
from custom_components.idm_heatpump.services import _handle_export_ai_dashboard
from tests.test_ai_advisor import manager


def sample(at, electric=1.0, thermal=3.0, mode=1, outdoor=5.0):
    return {
        "at": at,
        "connected": True,
        "mode": mode,
        "outdoor_temp": outdoor,
        "total_electrical_kwh": electric,
        "total_thermal_kwh": thermal,
    }


def test_learning_separates_modes_weather_and_excludes_current_day():
    history = LearningHistory()
    now = 20000 * 86400 + 3600
    for day in reversed(range(4)):
        for interval in range(24):
            at = now - day * 86400 + interval * 300
            history.observe(sample(at, 1, 3), sample(at + 300, 2, 6))
    result = history.comparison(sample(now))
    assert result["days"] == 3 and result["hours"] == 6
    assert result["status"] == "ready" and result["baseline_cop"] == 3
    assert result["deviation_percent"] == 0
    assert history.comparison(sample(now, mode=4))["status"] == "collecting"
    assert history.comparison(sample(now, outdoor=15))["status"] == "collecting"
    assert history.comparison(sample(now, mode=None))["status"] == "collecting"
    history.prune(now + 366 * 86400)
    assert not history.buckets


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": 4},
        {"mode": 0},
        {"outdoor_temp": float("nan")},
        {"connected": False},
        {"total_electrical_kwh": 0},
        {"total_thermal_kwh": 1},
        {"total_thermal_kwh": 100},
        {"at": 2000},
        {"outdoor_temp": 40},
        {"at": 0},
    ],
)
def test_learning_rejects_invalid_or_unmatched_intervals(changes):
    history = LearningHistory()
    history.observe(sample(0), sample(300, 2, 6) | changes)
    assert not history.buckets


def test_learning_load_validation_and_bound():
    obj = LearningHistory()
    obj.load(
        {"20000:1:1": [1, 3, 7200, 24], "bad": [1], "20000:4:1": [True, 1, 1, 1], "10000:1:1": [1, 2, 3, 4]},
        20000 * 86400,
    )
    assert list(obj.buckets) == ["20000:1:1"]
    obj.load(None, 20000 * 86400)
    assert len(obj.buckets) <= MAX_BUCKETS


async def test_four_reports_persist_and_invalid_rows_are_ignored():
    obj = manager()
    with patch.object(ai, "async_local_report", AsyncMock(return_value="Report")):
        for kind in ai.REPORT_TYPES:
            obj._last_request = -1e20
            await obj.async_generate(kind)
    await obj.async_stop()
    restored = manager()
    restored._store.data = obj._store.data
    await restored.async_load()
    assert set(restored.reports) == set(ai.REPORT_TYPES)
    assert restored.report == "Report" and restored.status == "ready"
    assert restored.reports["daily"]["quality"]["partial_coverage"] is True
    restored._store.data = {"reports": {"daily": {"report": "bad", "generated_at": "invalid", "facts": {}}}}
    await restored.async_load()


def test_budget_trims_old_details_before_learning_and_reports():
    obj = manager()
    obj._options[ai.CONF_AI_STORAGE] = 5
    obj.records = [sample(i) | {"unused": "x" * 1000} for i in range(10000)]
    obj.learning.buckets = {"20000:1:1": [1, 3, 7200, 24]}
    obj.reports = {"daily": {"report": "latest"}}
    payload = obj.storage_payload()
    assert len(json.dumps(payload, ensure_ascii=True, indent=4).encode()) + 65536 <= 5 * 1024 * 1024
    assert obj.records[0]["at"] > 0 and obj.records[-1]["at"] == 9999
    assert obj.learning.buckets and obj.reports
    assert obj.storage_bytes <= obj.storage_limit
    obj._options[ai.CONF_AI_STORAGE] = 99999
    assert obj.storage_limit == 200 * 1024 * 1024
    obj._options[ai.CONF_AI_STORAGE] = -10
    assert obj.storage_limit == 5 * 1024 * 1024


async def test_observation_learns_only_after_opt_in_and_metrics_are_available():
    obj = manager()
    now = time.time()
    obj._coordinator.data["hp_operating_mode"] = 1
    obj.observe(now)
    obj._options[ai.CONF_AI_LEARNING] = True
    obj._coordinator.poll_statistics.last_success = datetime.fromtimestamp(now + 299, UTC)
    obj._coordinator.energy_statistics.total_electrical_kwh += 1
    obj._coordinator.energy_statistics.total_thermal_kwh += 3
    obj.observe(now + 300)
    assert obj.learning.buckets
    assert obj.build_facts("daily", now + 300)["learning"]["status"] == "collecting"
    for key in AI_METRICS:
        entity = IdmAiMetricSensor(obj._coordinator, obj, key)
        assert entity.available
        assert entity.native_value is not None
    obj._options[ai.CONF_AI_LEARNING] = False
    assert IdmAiMetricSensor(obj._coordinator, obj, "ai_learning_status").native_value == "disabled"


async def test_scheduler_manual_default_and_restart_safe_due_date():
    obj = manager()
    obj.start()
    assert obj._scheduler is None
    obj._options[ai.CONF_AI_INTERVAL] = 24
    obj.start()
    first = obj.next_run
    obj.start()
    assert first == obj.next_run and first > time.time()
    await obj.async_stop()
    restored = manager()
    restored._store.data = obj._store.data
    restored._options[ai.CONF_AI_INTERVAL] = 24
    await restored.async_load()
    restored.start()
    assert restored.next_run == first
    await restored.async_stop()


@pytest.mark.parametrize("error", [None, ai.AdvisorError("ai_unavailable"), OSError()])
async def test_scheduler_advances_before_attempt_without_retry_storm(error):
    obj = manager()
    obj.next_run = 1
    obj.async_generate = AsyncMock(side_effect=error)
    calls = 0

    async def tick(_seconds):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise asyncio.CancelledError

    with patch.object(ai.asyncio, "sleep", tick), pytest.raises(asyncio.CancelledError):
        await obj._schedule_loop(86400)
    obj.async_generate.assert_awaited_once_with("daily")
    assert obj.next_run > time.time()
    assert obj._store.data["next_run"] == obj.next_run


async def test_notification_opt_in_deduplication_recovery_and_failures():
    obj = manager()
    obj._hass.services = SimpleNamespace(async_call=AsyncMock())
    facts = {"health_checks_current": {"health_test": True}}
    await obj._notify(facts)
    obj._hass.services.async_call.assert_not_called()
    obj._options[ai.CONF_AI_NOTIFICATIONS] = True
    await obj._notify(facts)
    await obj._notify(facts)
    obj._hass.services.async_call.assert_awaited_once()
    await obj._notify({"health_checks_current": {}})
    assert obj._notification_signature == ""
    await obj._notify(facts)
    assert obj._hass.services.async_call.await_count == 1
    obj._notification_at = 0
    obj._hass.services.async_call.side_effect = RuntimeError("private")
    await obj._notify(facts)
    assert obj._notification_signature == ""


def test_quality_flags_unsupported_values_without_claiming_truth():
    facts = manager().build_facts("daily", time.time())
    quality = ai.report_quality("Temperature 45 C. Savings 9876 kWh.", facts)
    assert quality["unsupported_numbers"] == [9876]
    assert not quality["model_text_verified"]


def test_ai_has_dedicated_device_even_without_general_hierarchy():
    obj = manager()
    coord = obj._coordinator
    coord.device_hierarchy_enabled = False
    coord.hass = MagicMock()
    coord.device_info = {}
    assert resolve_device_scope("ai_report").kind == "ai"
    assert expected_subdevices(coord)
    with patch("custom_components.idm_heatpump.device_hierarchy._via_device_id", return_value=None):
        info = build_subdevice_info(coord, "ai_report")
        assert "KI-Anlagenberater" in info["name"]
        assert IdmAiReportButton(coord, "daily").device_info == info


async def test_dashboard_resolves_renamed_entities_and_validates_entry(mock_hass):
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.exceptions import ServiceValidationError

    obj = manager()
    entry = obj._coordinator.config_entry
    entry.domain = DOMAIN
    entry.state = ConfigEntryState.LOADED
    mock_hass.config_entries.async_get_entry.return_value = entry
    registry = MagicMock()
    registry.async_get_entity_id.side_effect = lambda domain, platform, uid: domain + ".renamed_" + uid
    call = SimpleNamespace(data={"entry_id": "test"})
    with patch("homeassistant.helpers.entity_registry.async_get", return_value=registry):
        result = await _handle_export_ai_dashboard(mock_hass, call)
        assert len(result["dashboard"]["views"][0]["cards"]) == 9
        assert "renamed_" in json.dumps(result)
        registry.async_get_entity_id.return_value = None
        registry.async_get_entity_id.side_effect = None
        with pytest.raises(ServiceValidationError):
            await _handle_export_ai_dashboard(mock_hass, call)
    entry.runtime_data.ai_advisor = None
    with pytest.raises(ServiceValidationError):
        await _handle_export_ai_dashboard(mock_hass, call)
    mock_hass.config_entries.async_get_entry.return_value = None
    with pytest.raises(ServiceValidationError):
        await _handle_export_ai_dashboard(mock_hass, call)
