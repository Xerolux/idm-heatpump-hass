"""Cloud consent, privacy, protocol validation and durable spending bounds."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError

from custom_components.idm_heatpump import ai_advisor as ai
from custom_components.idm_heatpump import ai_cloud as cloud
from custom_components.idm_heatpump.config_flow import IdmHeatpumpOptionsFlow, _build_guided_field_schema
from custom_components.idm_heatpump.diagnostics import TO_REDACT
from tests.test_ai_advisor import manager


def options(provider="zai"):
    return {
        **cloud.CLOUD_DEFAULTS,
        cloud.CONF_AI_PROVIDER: provider,
        cloud.CONF_AI_CLOUD_CONSENT: True,
        cloud.CONF_AI_CLOUD_MODEL: "test-model",
        cloud.CONF_AI_ZAI_KEY: "test-zai-secret",
        cloud.CONF_AI_OPENAI_KEY: "test-openai-secret",
    }


def task_options():
    return options("ha_task") | {cloud.CONF_AI_TASK_ENTITY: "ai_task.selected_reporter", cloud.CONF_AI_CLOUD_MODEL: ""}


@pytest.mark.parametrize("entity", ["", "conversation.assistant", None, "ai_task.bad/name"])
def test_task_requires_explicit_valid_entity(entity):
    with pytest.raises(cloud.AdvisorError, match="ai_task_entity_required"):
        cloud.validate_cloud(task_options() | {cloud.CONF_AI_TASK_ENTITY: entity})


async def test_native_task_has_no_ha_tools_attachments_or_implicit_default():
    with patch.object(
        cloud.ai_task, "async_generate_data", AsyncMock(return_value=SimpleNamespace(data=" Report "))
    ) as call:
        assert await cloud.async_ha_task_report(MagicMock(), task_options(), "de", {"host": "SECRET"}) == "Report"
    assert call.call_args.kwargs["entity_id"] == "ai_task.selected_reporter"
    assert call.call_args.kwargs["llm_api"] is None
    assert call.call_args.kwargs["attachments"] is None
    assert "SECRET" not in call.call_args.kwargs["instructions"]
    assert "conversation_id" not in call.call_args.kwargs


@pytest.mark.parametrize(
    "data", [None, {}, "", " ", "x" * 6001], ids=["none", "dict", "empty", "whitespace", "oversize"]
)
async def test_native_task_validates_returned_text(data):
    with (
        patch.object(cloud.ai_task, "async_generate_data", AsyncMock(return_value=SimpleNamespace(data=data))),
        pytest.raises(cloud.AdvisorError, match="ai_invalid_response"),
    ):
        await cloud.async_ha_task_report(MagicMock(), task_options(), "en", {})


@pytest.mark.parametrize(
    "error", [HomeAssistantError("SECRET"), TimeoutError(), KeyError("not_loaded"), ValueError("SECRET provider error")]
)
async def test_native_task_errors_are_sanitized(error):
    with (
        patch.object(cloud.ai_task, "async_generate_data", AsyncMock(side_effect=error)),
        pytest.raises(cloud.AdvisorError, match="ai_unavailable"),
    ):
        await cloud.async_ha_task_report(MagicMock(), task_options(), "en", {})


async def test_native_task_uses_same_persisted_budget_and_report_guard():
    obj = manager()
    obj._options.update(task_options())
    obj._store.async_load = AsyncMock(return_value=None)
    await obj.async_load()
    with (
        patch.object(ai, "async_ha_task_report", AsyncMock(return_value="Report")) as generate,
        patch.object(ai, "async_cloud_report", AsyncMock()) as direct,
    ):
        await obj.async_generate()
    generate.assert_awaited_once()
    direct.assert_not_awaited()
    assert obj.cloud_requests == 1
    assert obj.reports["daily"]["provider"] == "ha_task"


async def test_guided_ha_task_needs_no_duplicate_key_model_or_local_url():
    flow = IdmHeatpumpOptionsFlow()
    flow.config_entry = MagicMock(options={}, title="IDM")
    await flow.async_step_init()
    await flow.async_step_guided_mode({"setup_level": "standard"})
    await flow.async_step_guided_choose({"selected_features": ["ai_advisor"]})
    await flow.async_step_guided_toggle({ai.CONF_AI_ADVISOR: True})
    values = {
        cloud.CONF_AI_PROVIDER: "ha_task",
        cloud.CONF_AI_CLOUD_CONSENT: True,
        cloud.CONF_AI_TASK_ENTITY: "ai_task.reporter",
    }
    assert (await flow.async_step_guided_detail(values))["step_id"] == "guided_review"


def response(provider="zai"):
    if provider == "openai":
        return {
            "status": "completed",
            "output": [
                {"type": "reasoning"},
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "Report"}],
                },
            ],
        }
    return {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "Report"}}]}


@pytest.mark.parametrize(
    "change",
    [
        {cloud.CONF_AI_PROVIDER: "evil"},
        {cloud.CONF_AI_CLOUD_CONSENT: False},
        {cloud.CONF_AI_CLOUD_MODEL: ""},
        {cloud.CONF_AI_CLOUD_MODEL: "https://evil"},
        {cloud.CONF_AI_CLOUD_LIMIT: True},
        {cloud.CONF_AI_CLOUD_LIMIT: 0},
        {cloud.CONF_AI_CLOUD_LIMIT: 1.5},
        {cloud.CONF_AI_CLOUD_LIMIT: float("nan")},
        {cloud.CONF_AI_ZAI_KEY: ""},
        {cloud.CONF_AI_ZAI_KEY: "x\r\nx"},
        {cloud.CONF_AI_ZAI_KEY: 123},
    ],
)
def test_invalid_settings_fail_closed(change):
    with pytest.raises(cloud.AdvisorError):
        cloud.validate_cloud(options() | change)


def test_projection_drops_identifiers_strings_and_lifetime_counters():
    obj = manager()
    facts = obj.build_facts("daily", 1700000000)
    facts["current"].update(outdoor_temp="SECRET", host="SECRET", total_electrical_kwh=999999)
    facts.update(purpose="SECRET", learning="SECRET", period=None, health_checks_current=None)
    projected = cloud.cloud_facts(facts)
    assert "SECRET" not in json.dumps(projected)
    assert "999999" not in json.dumps(projected)
    assert projected["current"]["outdoor_temp"] is None
    assert all(value == "unknown" for value in projected["health_checks_current"].values())
    facts["health_checks_current"] = {check.key: i % 2 == 0 for i, check in enumerate(cloud.HEALTH_CHECKS)}
    assert set(cloud.cloud_facts(facts)["health_checks_current"].values()) == {"issue_detected", "not_detected"}
    assert set(cloud.CLOUD_KEYS) <= TO_REDACT


@pytest.mark.parametrize("provider", ["openai", "zai"])
async def test_request_is_fixed_bounded_stateless_and_provider_key_bound(provider):
    session = MagicMock()
    reply = MagicMock(status=200)

    async def chunks(*args):
        yield json.dumps(response(provider)).encode()

    reply.content.iter_chunked = chunks
    session.post.return_value.__aenter__ = AsyncMock(return_value=reply)
    with patch.object(cloud.aiohttp, "ClientSession") as factory:
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        assert await cloud.async_cloud_report(options(provider), "de", {"host": "SECRET"}) == "Report"
    assert factory.call_args.kwargs["trust_env"] is False
    call = session.post.call_args
    assert call.args[0] == cloud.ENDPOINTS[provider]
    assert call.kwargs["allow_redirects"] is False
    assert call.kwargs["headers"]["Authorization"] == f"Bearer test-{provider}-secret"
    body = call.kwargs["json"]
    assert "SECRET" not in json.dumps(body)
    assert "tools" not in body
    if provider == "openai":
        assert body["store"] is False and body["max_output_tokens"] == 2048
    else:
        assert body["max_tokens"] == 2048


@pytest.mark.parametrize(
    "provider,data",
    [
        ("openai", {}),
        ("openai", {"status": "incomplete"}),
        ("openai", {"status": "completed", "output": [{"type": "function_call"}]}),
        (
            "openai",
            {
                "status": "completed",
                "output": [
                    {"type": "message", "role": "assistant", "status": "completed", "content": [{"type": "refusal"}]}
                ],
            },
        ),
        ("zai", {"choices": []}),
        ("zai", {"choices": [{"finish_reason": "length"}]}),
        ("zai", {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "tool_calls": [1]}}]}),
        ("zai", {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": ""}}]}),
    ],
)
def test_reject_incomplete_tools_refusals_malformed(provider, data):
    with pytest.raises(cloud.AdvisorError, match="ai_invalid_response"):
        cloud.parse_cloud_response(provider, data)


@pytest.mark.parametrize(
    "status,raw,error",
    [
        (401, b"SECRET", "ai_cloud_auth_failed"),
        (403, b"SECRET", "ai_cloud_auth_failed"),
        (429, b"SECRET", "ai_cloud_rate_limited"),
        (302, b"SECRET", "ai_server_error"),
        (200, b"oversized", "ai_invalid_response"),
        (200, b"[]", "ai_invalid_response"),
        (200, b"invalid", "ai_invalid_response"),
    ],
)
async def test_bounded_errors_never_include_server_data(status, raw, error):
    session = MagicMock()
    reply = MagicMock(status=status)

    async def chunks(*args):
        yield b"x" * 65537 if raw == b"oversized" else raw

    reply.content.iter_chunked = chunks
    session.post.return_value.__aenter__ = AsyncMock(return_value=reply)
    with patch.object(cloud.aiohttp, "ClientSession") as factory:
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        with pytest.raises(cloud.AdvisorError, match=error):
            await cloud.async_cloud_report(options(), "en", {})


async def test_network_failure_and_language():
    with (
        patch.object(cloud.aiohttp, "ClientSession", side_effect=aiohttp.ClientError("SECRET")),
        pytest.raises(cloud.AdvisorError, match="ai_unavailable"),
    ):
        await cloud.async_cloud_report(options(), "en", {})
    with pytest.raises(cloud.AdvisorError, match="invalid_ai_language"):
        await cloud.async_cloud_report(options(), "xx", {})


async def test_budget_reserved_before_request_and_survives_restart():
    obj = manager()
    obj._options.update(options() | {cloud.CONF_AI_CLOUD_LIMIT: 1})
    obj._store.async_load = AsyncMock(return_value=None)
    await obj.async_load()
    obj._store.async_save = AsyncMock()
    with patch.object(ai, "async_cloud_report", AsyncMock(return_value="Report")) as generate:
        await obj.async_generate()
        obj._store.async_save.assert_awaited_once()
        generate.assert_awaited_once()
        assert obj.cloud_requests == 1
        assert "secret" not in json.dumps(obj.storage_payload())
        restarted = manager()
        restarted._options.update(obj._options)
        restarted._store.async_load = AsyncMock(return_value=obj.storage_payload())
        await restarted.async_load()
        with pytest.raises(cloud.AdvisorError, match="ai_cloud_daily_limit_reached"):
            await restarted.async_generate()
        assert generate.await_count == 1


@pytest.mark.parametrize("loaded", [False, True])
async def test_budget_storage_failure_prevents_network(loaded):
    obj = manager()
    obj._options.update(options())
    obj._cloud_budget_loaded = loaded
    obj._store.async_save = AsyncMock(side_effect=OSError("SECRET"))
    with patch.object(ai, "async_cloud_report", AsyncMock()) as generate:
        with pytest.raises(cloud.AdvisorError, match="ai_cloud_budget_unavailable"):
            await obj.async_generate()
        generate.assert_not_awaited()


async def test_corrupt_budget_disables_cloud():
    obj = manager()
    obj._store.async_load = AsyncMock(return_value={"cloud_requests": "bad"})
    await obj.async_load()
    assert obj._cloud_budget_loaded is False
    obj._store.async_load = AsyncMock(return_value=obj.storage_payload())
    await obj.async_load()
    assert obj._cloud_budget_loaded is False


@pytest.mark.parametrize("model,disabled", [("glm-4.7-flash", True), ("glm-5.3", False)])
async def test_thinking_parameter_is_only_used_for_supported_models(model, disabled):
    session = MagicMock()
    reply = MagicMock(status=200)

    async def chunks(*args):
        yield json.dumps(response()).encode()

    reply.content.iter_chunked = chunks
    session.post.return_value.__aenter__ = AsyncMock(return_value=reply)
    with patch.object(cloud.aiohttp, "ClientSession") as factory:
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        await cloud.async_cloud_report(options() | {cloud.CONF_AI_CLOUD_MODEL: model}, "en", {})
    body = session.post.call_args.kwargs["json"]
    assert (body.get("thinking") == {"type": "disabled"}) is disabled


async def test_guided_cloud_key_retention_removal_and_no_prefill():
    flow = IdmHeatpumpOptionsFlow()
    flow.config_entry = MagicMock(options=options(), title="IDM")
    await flow.async_step_init()
    await flow.async_step_guided_mode({"setup_level": "standard"})
    await flow.async_step_guided_choose({"selected_features": ["ai_advisor"]})
    result = await flow.async_step_guided_toggle({ai.CONF_AI_ADVISOR: True})
    assert result["step_id"] == "guided_detail"
    schema = _build_guided_field_schema(flow._options, cloud.CLOUD_KEYS).schema
    for key in cloud.CLOUD_KEYS:
        marker = next(m for m in schema if m.schema == key)
        assert marker.default is vol.UNDEFINED
    values = options() | {cloud.CONF_AI_ZAI_KEY: "", cloud.CONF_AI_OPENAI_KEY: "-"}
    assert (await flow.async_step_guided_detail(values))["step_id"] == "guided_review"
    assert flow._options[cloud.CONF_AI_ZAI_KEY] == "test-zai-secret"
    assert flow._options[cloud.CONF_AI_OPENAI_KEY] == ""
