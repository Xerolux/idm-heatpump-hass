"""Tests for the one-time what's-new notice and the advisor option toggle."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.idm_heatpump import async_setup_entry, whats_new
from custom_components.idm_heatpump.whats_new import (
    WHATS_NEW_ISSUE_ID,
    WHATS_NEW_LEARN_MORE_URL,
    ensure_whats_new_issue,
)


def test_notice_is_created_persistent_and_dismissible(mock_hass: Any) -> None:
    ensure_whats_new_issue(mock_hass)
    create = whats_new.ir.async_create_issue
    assert create.call_count >= 1
    call = create.call_args
    assert call.args[1] == "idm_heatpump"
    assert call.args[2] == WHATS_NEW_ISSUE_ID
    kwargs = call.kwargs
    assert kwargs["is_fixable"] is False
    assert kwargs["is_persistent"] is True
    assert kwargs["severity"] is whats_new.ir.IssueSeverity.WARNING
    assert kwargs["translation_key"] == WHATS_NEW_ISSUE_ID
    assert kwargs["learn_more_url"] == WHATS_NEW_LEARN_MORE_URL


def test_superseded_notices_are_removed(monkeypatch: Any, mock_hass: Any) -> None:
    monkeypatch.setattr(whats_new, "_SUPERSEDED_IDS", ("whats_new_0_20_0",))
    ensure_whats_new_issue(mock_hass)
    delete = whats_new.ir.async_delete_issue
    assert delete.call_args.args == (mock_hass, "idm_heatpump", "whats_new_0_20_0")


async def test_setup_skips_advisor_and_notice_when_disabled(mock_hass: Any) -> None:
    """predictive_advisor=False creates no advisor runtime and no notice."""
    entry = MagicMock()
    entry.entry_id = "test_id"
    entry.title = "IDM Test"
    entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 1}
    entry.options = {
        "scan_interval": 10,
        "heating_circuits": ["a"],
        "zone_count": 0,
        "zone_rooms": {},
        "hide_unused_registers": True,
        "feature_profile": "smart",
        "predictive_advisor": False,
    }
    entry.runtime_data = None
    entry.add_update_listener = MagicMock(return_value=lambda: None)
    entry.async_on_unload = MagicMock()

    mock_client = AsyncMock()
    mock_client.connect = AsyncMock()
    mock_client.host = "192.168.1.100"
    mock_client.port = 502
    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.setup_registers = MagicMock()

    with (
        patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
        patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
        patch(
            "custom_components.idm_heatpump.async_get_integration",
            return_value=MagicMock(manifest={"version": "0.5.0"}),
        ),
        patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
        patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
        patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
        patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
        patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        patch("custom_components.idm_heatpump.ensure_whats_new_issue") as notice,
    ):
        result = await async_setup_entry(mock_hass, entry)

    assert result is True
    notice.assert_not_called()
    assert entry.runtime_data.predictive_advisor is None
    assert entry.runtime_data.advisor_engine is None


async def test_setup_creates_advisor_and_notice_by_default(mock_hass: Any) -> None:
    """Smart profile default: advisor runtime exists and the notice is shown."""
    entry = MagicMock()
    entry.entry_id = "test_id"
    entry.title = "IDM Test"
    entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 1}
    entry.options = {
        "scan_interval": 10,
        "heating_circuits": ["a"],
        "zone_count": 0,
        "zone_rooms": {},
        "hide_unused_registers": True,
    }
    entry.runtime_data = None
    entry.add_update_listener = MagicMock(return_value=lambda: None)
    entry.async_on_unload = MagicMock()

    mock_client = AsyncMock()
    mock_client.connect = AsyncMock()
    mock_client.host = "192.168.1.100"
    mock_client.port = 502
    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.setup_registers = MagicMock()

    with (
        patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
        patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
        patch(
            "custom_components.idm_heatpump.async_get_integration",
            return_value=MagicMock(manifest={"version": "0.5.0"}),
        ),
        patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
        patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
        patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
        patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
        patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        patch("custom_components.idm_heatpump.ensure_whats_new_issue") as notice,
    ):
        result = await async_setup_entry(mock_hass, entry)

    assert result is True
    notice.assert_called_once()
    assert entry.runtime_data.predictive_advisor is not None
    assert entry.runtime_data.advisor_engine is not None
