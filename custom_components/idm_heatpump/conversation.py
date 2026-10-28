"""Conversation platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — unofficial community integration for IDM Navigator 2.0 / 10 heat pumps
# Created by Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# SPDX-License-Identifier: MIT
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .assist_agent import IdmHeatpumpConversationEntity
from .coordinator import IdmCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Expose the deterministic local Assist agent for this entry."""
    coordinator: IdmCoordinator = entry.runtime_data.coordinator
    advisor = getattr(entry.runtime_data, "predictive_advisor", None)
    async_add_entities([IdmHeatpumpConversationEntity(coordinator, advisor)])
