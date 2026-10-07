"""Tests for the once-per-update what's-new notice and the advisor toggle."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.idm_heatpump import async_setup_entry, whats_new
from custom_components.idm_heatpump.whats_new import (
    LAST_RUN_VERSION_DATA_KEY,
    WHATS_NEW_ISSUE_ID,
    WHATS_NEW_LEARN_MORE_URL,
    async_note_release,
    ensure_whats_new_issue,
)


def test_notice_issue_parameters() -> None:
    hass = MagicMock()
    ensure_whats_new_issue(hass)
    create = whats_new.ir.async_create_issue
    # The stubbed module-level helper is shared across the whole suite, so
    # assert on our issue's calls instead of a global count.
    calls = [c for c in create.call_args_list if c.args[2] == WHATS_NEW_ISSUE_ID]
    assert calls
    call = calls[-1]
    assert call.args[1] == "idm_heatpump"
    assert call.args[2] == WHATS_NEW_ISSUE_ID
    kwargs = call.kwargs
    assert kwargs["is_fixable"] is False
    assert kwargs["is_persistent"] is True
    assert kwargs["severity"] is whats_new.ir.IssueSeverity.WARNING
    assert kwargs["translation_key"] == WHATS_NEW_ISSUE_ID
    assert kwargs["learn_more_url"] == WHATS_NEW_LEARN_MORE_URL


def test_superseded_notices_are_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(whats_new, "_SUPERSEDED_IDS", ("whats_new_0_20_0",))
    hass = MagicMock()
    ensure_whats_new_issue(hass)
    delete = whats_new.ir.async_delete_issue
    assert delete.call_args.args == (hass, "idm_heatpump", "whats_new_0_20_0")


async def test_notice_fires_exactly_once_per_update(mock_hass: Any) -> None:
    """An installed update fires the notice once and stamps the version.

    Every later setup of the same release (restart, reload) is a no-op.
    """
    entry = SimpleNamespace(data={"host": "h", "last_run_version": "0.20.1"})
    mock_hass.config_entries.async_update_entry = AsyncMock()

    with patch.object(whats_new, "ensure_whats_new_issue") as ensure:
        await async_note_release(mock_hass, entry, "0.21.0")  # type: ignore[arg-type]
    ensure.assert_called_once()
    mock_hass.config_entries.async_update_entry.assert_awaited_once()
    written = mock_hass.config_entries.async_update_entry.await_args.kwargs["data"]
    assert written[LAST_RUN_VERSION_DATA_KEY] == "0.21.0"

    # Same release again: nothing at all happens.
    entry_after_update = SimpleNamespace(data={"host": "h", "last_run_version": "0.21.0"})
    with patch.object(whats_new, "ensure_whats_new_issue") as ensure:
        await async_note_release(mock_hass, entry_after_update, "0.21.0")  # type: ignore[arg-type]
    ensure.assert_not_called()
    mock_hass.config_entries.async_update_entry.assert_awaited_once()  # still one write


async def test_fresh_install_is_stamped_without_a_notice(mock_hass: Any) -> None:
    entry = SimpleNamespace(data={"host": "h"})
    mock_hass.config_entries.async_update_entry = AsyncMock()
    with patch.object(whats_new, "ensure_whats_new_issue") as ensure:
        await async_note_release(mock_hass, entry, "0.21.0")  # type: ignore[arg-type]
    ensure.assert_not_called()  # a new user did not update anything
    written = mock_hass.config_entries.async_update_entry.await_args.kwargs["data"]
    assert written[LAST_RUN_VERSION_DATA_KEY] == "0.21.0"


async def test_stampless_pre_existing_entry_is_an_update(mock_hass: Any) -> None:
    """0.20.1 installations never got a stamp: they are updates, not fresh.

    The release introducing the notice is the only one that needs the
    ``created_at`` heuristic; from the next release on the stamp decides.
    """
    old_entry = SimpleNamespace(data={"host": "h"}, created_at=datetime(2026, 9, 1, tzinfo=UTC))
    fresh_entry = SimpleNamespace(data={"host": "h2"}, created_at=datetime.now(UTC))
    mock_hass.config_entries.async_update_entry = AsyncMock()

    with patch.object(whats_new, "ensure_whats_new_issue") as ensure:
        await async_note_release(mock_hass, old_entry, "0.21.0-b1")  # type: ignore[arg-type]
    ensure.assert_called_once()

    with patch.object(whats_new, "ensure_whats_new_issue") as ensure:
        await async_note_release(mock_hass, fresh_entry, "0.21.0-b1")  # type: ignore[arg-type]
    ensure.assert_not_called()  # created minutes ago: a fresh install


async def test_missing_version_is_a_noop(mock_hass: Any) -> None:
    entry = SimpleNamespace(data={"host": "h"})
    mock_hass.config_entries.async_update_entry = AsyncMock()
    with patch.object(whats_new, "ensure_whats_new_issue") as ensure:
        await async_note_release(mock_hass, entry, None)  # type: ignore[arg-type]
    ensure.assert_not_called()
    mock_hass.config_entries.async_update_entry.assert_not_awaited()


def _make_entry(options: dict[str, Any], data: dict[str, Any]) -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "test_id"
    entry.title = "IDM Test"
    entry.data = data
    entry.options = {
        "scan_interval": 10,
        "heating_circuits": ["a"],
        "zone_count": 0,
        "zone_rooms": {},
        "hide_unused_registers": True,
        **options,
    }
    entry.runtime_data = None
    entry.add_update_listener = MagicMock(return_value=lambda: None)
    entry.async_on_unload = MagicMock()
    return entry


async def _setup_with_patches(mock_hass: Any, entry: MagicMock, ensure: Any) -> bool:
    mock_client = AsyncMock()
    mock_client.connect = AsyncMock()
    mock_client.host = "192.168.1.100"
    mock_client.port = 502
    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.setup_registers = MagicMock()
    with ExitStack() as stack:
        for context in (
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
            patch("custom_components.idm_heatpump.whats_new.ensure_whats_new_issue", new=ensure),
        ):
            stack.enter_context(context)
        result: bool = await async_setup_entry(mock_hass, entry)
    return result


async def test_setup_fires_notice_only_on_update_transition(mock_hass: Any) -> None:
    """Entry last ran 0.20.1, the running version is 0.5.0: notice fires."""
    entry = _make_entry(options={}, data={"host": "h", "port": 502, "slave_id": 1, "last_run_version": "0.20.1"})
    ensure = MagicMock()
    assert await _setup_with_patches(mock_hass, entry, ensure) is True
    ensure.assert_called_once()
    assert entry.runtime_data.predictive_advisor is not None


async def test_setup_skips_notice_on_same_or_fresh_version(mock_hass: Any) -> None:
    """Fresh install and same-version setups never fire the notice."""
    for data in (
        {"host": "h", "port": 502, "slave_id": 1},
        {"host": "h", "port": 502, "slave_id": 1, "last_run_version": "0.5.0"},
    ):
        entry = _make_entry(options={}, data=dict(data))
        ensure = MagicMock()
        assert await _setup_with_patches(mock_hass, entry, ensure) is True
        ensure.assert_not_called()  # stamping may run, the notice never fires


async def test_setup_skips_advisor_and_notice_when_disabled(mock_hass: Any) -> None:
    """predictive_advisor=False creates no advisor runtime and no notice."""
    entry = _make_entry(
        options={"feature_profile": "smart", "predictive_advisor": False},
        data={"host": "h", "port": 502, "slave_id": 1, "last_run_version": "0.20.1"},
    )
    ensure = MagicMock()
    assert await _setup_with_patches(mock_hass, entry, ensure) is True
    ensure.assert_not_called()
    assert entry.runtime_data.predictive_advisor is None
    assert entry.runtime_data.advisor_engine is None
