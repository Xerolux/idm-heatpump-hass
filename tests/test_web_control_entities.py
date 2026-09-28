"""Tests for the web-only control entities and the web write routing (Phase 4)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from idm_heatpump import IdmWebHomeOverview, IdmWebSystemMode

from custom_components.idm_heatpump.const import CONNECTION_MODE_WEB_ONLY
from custom_components.idm_heatpump.web_control_entities import (
    web_control_button_entities,
    web_control_select_entities,
)
from custom_components.idm_heatpump.web_data import IdmWebSupplement


def _coordinator(*, connection_mode: str | None = CONNECTION_MODE_WEB_ONLY, variant: str = "nav10"):
    coordinator = MagicMock()
    coordinator.web_supplement = IdmWebSupplement(
        web_variant=variant,
        home_overview=IdmWebHomeOverview(
            system_mode=IdmWebSystemMode(
                value=1,
                options=(-1, 0, 1, 2, 3, 5, 4),
                cooling_configured=False,
            )
        ),
    )
    coordinator.async_web_set_system_mode = AsyncMock()
    coordinator.async_web_acknowledge_notifications = AsyncMock()
    entry = coordinator.config_entry
    entry.entry_id = "web_entry"
    if connection_mode is None:
        entry.options = {}
        entry.data = {}
    else:
        entry.options = {"connection_mode": connection_mode}
        entry.data = {}
    return coordinator


class TestEntityCreation:
    def test_entities_exist_in_web_only_nav10(self):
        coordinator = _coordinator()
        assert len(web_control_select_entities(coordinator)) == 1
        assert len(web_control_button_entities(coordinator)) == 1

    def test_no_entities_in_modbus_modes(self):
        coordinator = _coordinator(connection_mode="auto")
        assert web_control_select_entities(coordinator) == []
        assert web_control_button_entities(coordinator) == []

    def test_no_entities_on_nav20(self):
        coordinator = _coordinator(variant="nav20")
        assert web_control_select_entities(coordinator) == []
        assert web_control_button_entities(coordinator) == []


class TestSystemModeSelect:
    def test_options_follow_the_device_list_without_unknown(self):
        select = web_control_select_entities(_coordinator())[0]

        options = select.options
        assert "automatic" in options
        assert "hot_water_only" in options
        # -1 (unknown) appears in the device list but is not writable.
        assert len([o for o in options]) == 6

    def test_current_option_maps_the_device_value(self):
        select = web_control_select_entities(_coordinator())[0]

        assert select.current_option == "automatic"

    def test_current_option_none_without_overview(self):
        coordinator = _coordinator()
        coordinator.web_supplement = IdmWebSupplement(web_variant="nav10")
        select = web_control_select_entities(coordinator)[0]

        assert select.current_option is None

    async def test_select_option_routes_through_the_web_write(self):
        coordinator = _coordinator()
        select = web_control_select_entities(coordinator)[0]

        await select.async_select_option("hot_water_only")

        coordinator.async_web_set_system_mode.assert_awaited_once_with(4)

    async def test_unknown_option_is_rejected(self):
        coordinator = _coordinator()
        select = web_control_select_entities(coordinator)[0]

        try:
            await select.async_select_option("warp_drive")
        except ValueError:
            pass
        else:
            raise AssertionError("unknown option must raise")
        coordinator.async_web_set_system_mode.assert_not_awaited()


class TestAcknowledgeButton:
    async def test_press_routes_through_the_web_write(self):
        coordinator = _coordinator()
        button = web_control_button_entities(coordinator)[0]

        await button.async_press()

        coordinator.async_web_acknowledge_notifications.assert_awaited_once()
