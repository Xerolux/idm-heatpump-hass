"""Tests for Home Assistant repair flows."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers import issue_registry as ir

from custom_components.idm_heatpump.const import (
    CONF_DETECTED_NAVIGATOR_VERSION,
    CONF_DETECTED_SOFTWARE_VERSION,
    CONF_DETECTED_WEB_VARIANT,
    CONF_WEB_ENABLED,
    CONF_WEB_PIN,
)
from custom_components.idm_heatpump.repairs import async_create_fix_flow
from custom_components.idm_heatpump.web_data import IdmWebAuthenticationFailed


@pytest.fixture
def repair_entry(mock_config_entry):
    mock_config_entry.options = {**mock_config_entry.options, CONF_WEB_ENABLED: True}
    mock_config_entry.data = {**mock_config_entry.data, CONF_WEB_PIN: ""}
    return mock_config_entry


@pytest.mark.asyncio
async def test_web_pin_missing_repair_requires_a_choice(mock_hass, repair_entry) -> None:
    mock_hass.config_entries.async_entries.return_value = [repair_entry]
    flow = await async_create_fix_flow(mock_hass, "web_pin_missing", {"entry_id": repair_entry.entry_id})

    result = await flow.async_step_init()

    assert result["type"] == "form"
    assert result["step_id"] == "init"


@pytest.mark.asyncio
async def test_web_pin_missing_repair_disables_web_supplement(mock_hass, repair_entry) -> None:
    mock_hass.config_entries.async_entries.return_value = [repair_entry]
    flow = await async_create_fix_flow(mock_hass, "web_pin_missing", {"entry_id": repair_entry.entry_id})

    result = await flow.async_step_disable_web({})

    assert result["type"] == "create_entry"
    mock_hass.config_entries.async_update_entry.assert_called_once()
    _, kwargs = mock_hass.config_entries.async_update_entry.call_args
    assert kwargs["data"][CONF_WEB_PIN] == ""
    assert kwargs["options"][CONF_WEB_ENABLED] is False
    ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "web_pin_missing")
    ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "web_authentication_failed")
    mock_hass.config_entries.async_reload.assert_awaited_once_with(repair_entry.entry_id)


@pytest.mark.asyncio
async def test_web_pin_missing_repair_sets_valid_pin(mock_hass, repair_entry) -> None:
    mock_hass.config_entries.async_entries.return_value = [repair_entry]
    flow = await async_create_fix_flow(mock_hass, "web_pin_missing", {"entry_id": repair_entry.entry_id})
    supplement = SimpleNamespace(
        navigator_version="Navigator 10",
        software_version="NAV10_20.24",
        web_variant="nav10",
    )

    with patch(
        "custom_components.idm_heatpump.repairs.async_read_web_supplement",
        new=AsyncMock(return_value=supplement),
    ) as read_web:
        result = await flow.async_step_set_pin({CONF_WEB_PIN: " 1234 "})

    assert result["type"] == "create_entry"
    read_web.assert_awaited_once_with("192.168.1.100", "1234")
    _, kwargs = mock_hass.config_entries.async_update_entry.call_args
    assert kwargs["data"][CONF_WEB_PIN] == "1234"
    assert kwargs["data"][CONF_DETECTED_NAVIGATOR_VERSION] == "Navigator 10"
    assert kwargs["data"][CONF_DETECTED_SOFTWARE_VERSION] == "NAV10_20.24"
    assert kwargs["data"][CONF_DETECTED_WEB_VARIANT] == "nav10"
    assert kwargs["options"][CONF_WEB_ENABLED] is True
    ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "web_pin_missing")
    ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "web_authentication_failed")


@pytest.mark.asyncio
async def test_web_authentication_repair_uses_same_pin_flow(mock_hass, repair_entry) -> None:
    mock_hass.config_entries.async_entries.return_value = [repair_entry]
    flow = await async_create_fix_flow(
        mock_hass,
        "web_authentication_failed",
        {"entry_id": repair_entry.entry_id},
    )

    result = await flow.async_step_init()

    assert result["type"] == "form"
    assert result["step_id"] == "init"


@pytest.mark.asyncio
async def test_web_pin_missing_repair_rejects_invalid_pin(mock_hass, repair_entry) -> None:
    mock_hass.config_entries.async_entries.return_value = [repair_entry]
    flow = await async_create_fix_flow(mock_hass, "web_pin_missing", {"entry_id": repair_entry.entry_id})

    with patch(
        "custom_components.idm_heatpump.repairs.async_read_web_supplement",
        new=AsyncMock(side_effect=IdmWebAuthenticationFailed),
    ):
        result = await flow.async_step_set_pin({CONF_WEB_PIN: "0000"})

    assert result["type"] == "form"
    assert result["step_id"] == "set_pin"
    assert result["errors"][CONF_WEB_PIN] == "invalid_web_pin"
    mock_hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("web_result", [None, TimeoutError("web timeout")])
async def test_web_pin_repair_rejects_unreachable_web_interface(mock_hass, repair_entry, web_result) -> None:
    mock_hass.config_entries.async_entries.return_value = [repair_entry]
    flow = await async_create_fix_flow(mock_hass, "web_authentication_failed", {"entry_id": repair_entry.entry_id})
    read_result = (
        AsyncMock(side_effect=web_result) if isinstance(web_result, Exception) else AsyncMock(return_value=web_result)
    )

    with patch("custom_components.idm_heatpump.repairs.async_read_web_supplement", new=read_result):
        result = await flow.async_step_set_pin({CONF_WEB_PIN: "1234"})

    assert result["type"] == "form"
    assert result["errors"]["base"] == "web_cannot_connect"
    mock_hass.config_entries.async_update_entry.assert_not_called()
