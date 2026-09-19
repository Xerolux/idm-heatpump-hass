"""Read-only AI boundaries, period coverage, failure handling and HA lifecycle."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError

from custom_components.idm_heatpump import ai_advisor as ai
from custom_components.idm_heatpump.ai_advisor_entities import IdmAiReportButton, IdmAiReportSensor
from custom_components.idm_heatpump.config_flow import IdmHeatpumpOptionsFlow
from custom_components.idm_heatpump.services import _handle_generate_ai_report


def coordinator():
    entry = SimpleNamespace(
        entry_id="test",
        options={ai.CONF_AI_ADVISOR: True, ai.CONF_AI_UNVERIFIED_TEXT: True, ai.CONF_AI_URL: "http://127.0.0.1:11434"},
    )
    entry.runtime_data = SimpleNamespace(ai_advisor=None)
    return SimpleNamespace(
        config_entry=entry,
        last_update_success=True,
        data={"outdoor_temp": 5.0, "dhw_temp_top": 45.0, "dhw_setpoint": 50.0, "web_pin": "SECRET"},
        energy_statistics=SimpleNamespace(total_electrical_kwh=10.0, total_thermal_kwh=30.0),
        operation_analysis=None,
        poll_statistics=SimpleNamespace(consecutive_failures=0, last_success=datetime.now(UTC)),
    )


def manager():
    coord = coordinator()
    result = ai.AiAdvisor(SimpleNamespace(), coord.config_entry, coord)
    coord.config_entry.runtime_data.ai_advisor = result
    return result


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://8.8.8.8",
        "http://169.254.169.254",
        "http://0.0.0.0",
        "http://127.0.0.1:0",
        "http://user:pass@127.0.0.1",
        "http://127.0.0.1/path",
        "http://127.0.0.1?q=1",
        "http://127.0.0.1#x",
        "http://127.0.0.1:bad",
        "file:///etc/passwd",
    ],
)
def test_reject_nonlocal_or_ambiguous_endpoints(url):
    with pytest.raises(ai.AdvisorError, match="invalid_ai_endpoint"):
        ai.validate_settings(url, "gemma3:4b", "de")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434/",
        "http://192.168.1.20:11434",
        "https://10.0.0.1",
        "http://[::1]:11434",
        "http://[fd00::1]:11434",
    ],
)
def test_accept_literal_local_endpoints(url):
    assert ai.validate_settings(url, "gemma3:4b", "en") == url.rstrip("/")


@pytest.mark.parametrize(
    ("model", "language", "error"),
    [("x:cloud", "de", "invalid_ai_model"), ("", "en", "invalid_ai_model"), ("x", "fr", "invalid_ai_language")],
)
def test_model_and_language_validation(model, language, error):
    with pytest.raises(ai.AdvisorError, match=error):
        ai.validate_settings("http://127.0.0.1", model, language)


def test_snapshot_has_numeric_allowlist_and_no_private_data():
    coord = coordinator()
    coord.data.update(hp_flow_temp=float("nan"), hp_return_temp=True, dhw_temp_top=65535)
    coord.poll_statistics.last_success = datetime.fromtimestamp(100, UTC)
    snapshot = ai.capture_sample(coord, 100)
    assert "SECRET" not in json.dumps(snapshot)
    assert snapshot["hp_flow_temp"] is None
    assert snapshot["hp_return_temp"] is None
    assert snapshot["dhw_temp_top"] is None
    coord.last_update_success = False
    assert ai.capture_sample(coord, 200)["total_electrical_kwh"] is None


def test_period_integrates_only_valid_counter_intervals():
    coord = coordinator()
    coord.poll_statistics.last_success = datetime.fromtimestamp(100, UTC)
    first = ai.capture_sample(coord, 100)
    coord.energy_statistics.total_electrical_kwh += 1
    coord.energy_statistics.total_thermal_kwh += 4
    second = ai.capture_sample(coord, 400)
    summary = ai.summarize_period([first, second], 0, 1000)
    assert summary["electrical_kwh_observed"] == 1
    assert summary["cop_observed"] == 4
    assert summary["energy_counter_coverage_percent"] == 30
    for changed in ({"at": 2000}, {"connected": False}, {"total_electrical_kwh": None}, {"total_electrical_kwh": 0}):
        assert ai.summarize_period([first, second | changed], 0, 3000)["cop_observed"] is None
    assert ai.summarize_period([], 0, 100)["outdoor_c_min"] is None


async def test_history_is_bounded_persistent_and_allowlisted():
    obj = manager()
    now = time.time()
    obj._store.data = {
        "records": [
            None,
            {},
            {"at": now - 15 * 86400},
            ai.capture_sample(obj._coordinator, now - 600) | {"pin": "SECRET"},
        ]
    }
    await obj.async_load()
    assert len(obj.records) == 1
    assert "SECRET" not in json.dumps(obj.records)
    obj.observe(now)
    obj.observe(now + 10)
    assert len(obj.records) == 2
    facts = obj.build_facts("weekly", now)
    assert facts["period"]["energy_counter_coverage_percent"] < 1
    assert len(facts["health_checks_current"]) == 8
    obj._coordinator.last_update_success = False
    assert all(v is None for v in obj.build_facts("health", now)["health_checks_current"].values())
    await obj.async_stop()
    obj.observe(now + 600)
    assert len(obj.records) == 2
    await obj.async_stop()


async def test_history_storage_errors_are_nonfatal(caplog):
    obj = manager()
    obj._store.async_load = AsyncMock(side_effect=OSError("SECRET"))
    obj._store.async_save = AsyncMock(side_effect=OSError("SECRET"))
    await obj.async_load()
    await obj.async_stop()
    assert "SECRET" not in caplog.text


async def test_generate_is_opt_in_bounded_and_preserves_last_success():
    obj = manager()
    with patch.object(ai, "async_local_report", AsyncMock(return_value="Report")) as generate:
        result = await obj.async_generate()
        assert result["report"] == "Report"
        assert obj.status == "ready"
        assert "SECRET" not in json.dumps(generate.call_args.args[3])
        with pytest.raises(ai.AdvisorError, match="ai_cooldown"):
            await obj.async_generate()
        obj._last_request = -1e20
        generate.side_effect = ai.AdvisorError("ai_unavailable")
        with pytest.raises(ai.AdvisorError, match="ai_unavailable"):
            await obj.async_generate("efficiency")
        assert obj.report == "Report" and obj.status == "error"
    obj._options[ai.CONF_AI_ADVISOR] = False
    with pytest.raises(ai.AdvisorError, match="ai_disabled"):
        await obj.async_generate()
    obj._options[ai.CONF_AI_ADVISOR] = True
    with pytest.raises(ai.AdvisorError, match="ai_invalid_report_type"):
        await obj.async_generate("write_register")


async def test_busy_request_and_unload_cancel_generation():
    obj = manager()
    started = asyncio.Event()

    async def pending(*args):
        started.set()
        await asyncio.Event().wait()

    with patch.object(ai, "async_local_report", pending):
        task = asyncio.create_task(obj.async_generate())
        await started.wait()
        with pytest.raises(ai.AdvisorError, match="ai_busy"):
            await obj.async_generate()
        await obj.async_stop()
        assert task.cancelled()
        assert obj.status == "idle"


LOCAL_MODEL = {
    "details": {"format": "gguf"},
    "model_info": {"general.architecture": "gemma3"},
    "capabilities": ["completion"],
}
VALID_RESPONSE = {"done": True, "done_reason": "stop", "message": {"content": "Local report"}}


@pytest.mark.parametrize("language", ["de", "en"])
async def test_local_request_has_no_tools_or_device_identifiers(language):
    with patch.object(ai, "_post", AsyncMock(side_effect=[LOCAL_MODEL, VALID_RESPONSE])) as post:
        assert await ai.async_local_report("http://127.0.0.1", "gemma3:4b", language, {"n": 1}) == "Local report"
    assert post.call_args_list[0].args[1].endswith("/api/show")
    body = post.call_args.args[2]
    assert "tools" not in body
    assert body["stream"] is False
    assert json.loads(body["messages"][1]["content"]) == {"n": 1}


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        LOCAL_MODEL | {"remote_host": "ollama.com"},
        LOCAL_MODEL | {"remote_model": "remote"},
        LOCAL_MODEL | {"details": None},
    ],
)
async def test_reject_remote_model_before_sending_facts(metadata):
    with (
        patch.object(ai, "_post", AsyncMock(return_value=metadata)) as post,
        pytest.raises(ai.AdvisorError, match="ai_local_model_required"),
    ):
        await ai.async_local_report("http://127.0.0.1", "x", "de", {"private_plant_data": 1})
    assert post.await_count == 1
    assert "private_plant_data" not in str(post.call_args)


@pytest.mark.parametrize(
    "response",
    [
        {},
        VALID_RESPONSE | {"done": False},
        VALID_RESPONSE | {"done_reason": "length"},
        VALID_RESPONSE | {"message": {"content": "x", "tool_calls": [1]}},
        VALID_RESPONSE | {"message": {"content": " "}},
        VALID_RESPONSE | {"message": {"content": "x" * 6001}},
    ],
)
async def test_reject_invalid_and_tool_responses(response):
    with (
        patch.object(ai, "_post", AsyncMock(side_effect=[LOCAL_MODEL, response])),
        pytest.raises(ai.AdvisorError, match="ai_invalid_response"),
    ):
        await ai.async_local_report("http://127.0.0.1", "x", "de", {})


@pytest.mark.parametrize("error", [TimeoutError(), aiohttp.ClientError("SECRET")])
async def test_network_error_is_sanitized(error):
    with (
        patch.object(ai, "_post", AsyncMock(side_effect=error)),
        pytest.raises(ai.AdvisorError, match="^ai_unavailable$"),
    ):
        await ai.async_local_report("http://127.0.0.1", "x", "de", {})


@pytest.mark.parametrize(
    ("status", "body", "error"),
    ids=["valid", "redirect", "oversized", "invalid-json", "not-object", "error"],
    argvalues=[
        (200, b'{"ok":true}', None),
        (302, b"", "ai_server_error"),
        (200, b"x" * 65537, "ai_invalid_response"),
        (200, b"bad", "ai_invalid_response"),
        (200, b"[]", "ai_invalid_response"),
        (200, b'{"error":"secret"}', "ai_invalid_response"),
    ],
)
async def test_http_response_bounds_and_redirects(status, body, error):
    async def chunks(_size):
        yield body

    response = SimpleNamespace(status=status, content=SimpleNamespace(iter_chunked=chunks))
    context = AsyncMock()
    context.__aenter__.return_value = response
    session = MagicMock()
    session.post.return_value = context
    if error:
        with pytest.raises(ai.AdvisorError, match=error):
            await ai._post(session, "http://127.0.0.1/api/chat", {})
    else:
        assert await ai._post(session, "http://127.0.0.1/api/chat", {}) == {"ok": True}
    assert session.post.call_args.kwargs["allow_redirects"] is False


async def test_explicit_service_entry_and_report_button(mock_hass):
    obj = manager()
    entry = obj._coordinator.config_entry
    entry.domain, entry.state = "idm_heatpump", ConfigEntryState.LOADED
    mock_hass.config_entries.async_get_entry.return_value = entry
    obj.async_generate = AsyncMock(return_value={"report": "test"})
    call = SimpleNamespace(data={"entry_id": "test", "report_type": "weekly"})
    assert await _handle_generate_ai_report(mock_hass, call) == {"report": "test"}
    button = IdmAiReportButton(obj._coordinator, "daily")
    await button.async_press()
    obj.async_generate.assert_awaited_with("daily")
    obj.async_generate.side_effect = ai.AdvisorError("ai_busy")
    with pytest.raises(HomeAssistantError):
        await _handle_generate_ai_report(mock_hass, call)
    with pytest.raises(HomeAssistantError):
        await button.async_press()
    entry.runtime_data.ai_advisor = None
    with pytest.raises(HomeAssistantError):
        await button.async_press()
    with pytest.raises(HomeAssistantError):
        await _handle_generate_ai_report(mock_hass, call)
    mock_hass.config_entries.async_get_entry.return_value = None
    with pytest.raises(HomeAssistantError):
        await _handle_generate_ai_report(mock_hass, call)


async def test_sensor_report_attributes_and_teardown():
    obj = manager()
    sensor = IdmAiReportSensor(obj._coordinator, obj)
    assert sensor.available and sensor.native_value == "idle"
    assert sensor.extra_state_attributes["read_only"]
    obj.async_stop = AsyncMock()
    sensor.async_write_ha_state = MagicMock()
    sensor.hass = MagicMock()
    with (
        patch(
            "custom_components.idm_heatpump.ai_advisor_entities.IdmCoordinatorEntityBase.async_added_to_hass",
            new=AsyncMock(),
            create=True,
        ),
        patch(
            "custom_components.idm_heatpump.ai_advisor_entities.IdmCoordinatorEntityBase._handle_coordinator_update",
            create=True,
        ),
    ):
        await sensor.async_added_to_hass()
        sensor._handle_coordinator_update()
    # Collection is driven by the entry-level coordinator listener, not by the
    # entity: a coordinator update must not observe anything here.
    assert len(obj.records) == 0
    obj.on_update()
    sensor.async_write_ha_state.assert_called_once()
    with patch(
        "custom_components.idm_heatpump.ai_advisor_entities.IdmCoordinatorEntityBase.async_will_remove_from_hass",
        new=AsyncMock(),
        create=True,
    ):
        await sensor.async_will_remove_from_hass()
    # Removing or disabling the entity must not stop the entry-level adviser;
    # it only detaches the state-write callback.
    obj.async_stop.assert_not_awaited()
    obj.on_update()
    sensor.async_write_ha_state.assert_called_once()


async def test_guided_opt_in_validates_local_endpoint():
    flow = IdmHeatpumpOptionsFlow()
    flow.config_entry = MagicMock(options={}, title="IDM")
    await flow.async_step_init()
    await flow.async_step_guided_mode({"setup_level": "standard"})
    await flow.async_step_guided_choose({"selected_features": ["ai_advisor"]})
    result = await flow.async_step_guided_toggle({ai.CONF_AI_ADVISOR: True})
    assert result["step_id"] == "guided_detail"
    values = {
        ai.CONF_AI_UNVERIFIED_TEXT: True,
        ai.CONF_AI_URL: "http://example.com",
        ai.CONF_AI_MODEL: "gemma3:4b",
        ai.CONF_AI_LANGUAGE: "de",
    }
    result = await flow.async_step_guided_detail(values)
    assert result["errors"]["base"] == "invalid_ai_endpoint"
    values[ai.CONF_AI_URL] = "http://127.0.0.1:11434/"
    result = await flow.async_step_guided_detail(values)
    assert result["step_id"] == "guided_review"
    assert flow._options[ai.CONF_AI_URL] == "http://127.0.0.1:11434"
    assert (await flow.async_step_guided_review({"save_configuration": True}))["step_id"] == "feature_notice"


async def test_model_metadata_has_a_separate_bounded_budget():
    with patch.object(ai, "_post", AsyncMock(side_effect=[LOCAL_MODEL, VALID_RESPONSE])) as post:
        await ai.async_local_report("http://127.0.0.1", "gemma3:4b", "en", {})
    assert post.call_args_list[0].kwargs["max_bytes"] == 1048576
    assert "max_bytes" not in post.call_args_list[1].kwargs


def test_stale_data_and_start_counts_are_explicit():
    obj = manager()
    now = time.time()
    obj._coordinator.operation_analysis = MagicMock()
    obj._coordinator.operation_analysis.compressor_starts_last_hours.return_value = 4
    with patch.object(ai, "HEALTH_CHECKS", ()):
        assert obj.build_facts("daily", now)["compressor_starts_last_24_hours"] == 4
    assert ai.capture_sample(obj._coordinator, now + 901)["connected"] is False
    assert ai.capture_sample(obj._coordinator, now - 901)["connected"] is False


async def test_partial_setup_cancels_optional_adviser():
    from custom_components.idm_heatpump import _async_cancel_entry_tasks

    obj = manager()
    obj.async_stop = AsyncMock()
    await _async_cancel_entry_tasks(SimpleNamespace(ai_advisor=obj))
    obj.async_stop.assert_awaited_once()


async def test_larger_model_request_keeps_bounded_http_deadlines():
    async def post(session, url, payload, **kwargs):
        assert session.timeout.total == 300
        assert session.timeout.connect == 10
        return LOCAL_MODEL if url.endswith("/api/show") else VALID_RESPONSE

    with patch.object(ai, "_post", post):
        assert await ai.async_local_report("http://127.0.0.1", "gemma3:12b", "de", {}) == "Local report"


async def test_report_deadline_cancels_stalled_inference():
    cancelled = asyncio.Event()

    async def stalled(session, url, payload, **kwargs):
        if url.endswith("/api/show"):
            return LOCAL_MODEL
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with (
        patch.object(ai, "_REPORT_TIMEOUT", 0.01),
        patch.object(ai, "_post", stalled),
        pytest.raises(ai.AdvisorError, match="ai_unavailable"),
    ):
        await ai.async_local_report("http://127.0.0.1", "gemma3:12b", "de", {})
    assert cancelled.is_set()
