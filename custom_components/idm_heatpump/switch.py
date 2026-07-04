"""Switch platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import logging

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IdmCoordinator
from .entity import IdmEntity, should_add_entity
from .registers import sort_entity_descriptions

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = entry.runtime_data.coordinator
    entities = [
        IdmSwitch(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in sort_entity_descriptions(coordinator.switch_descriptions)
        if should_add_entity(coordinator, desc_info["register"])
    ]
    async_add_entities(entities)


class IdmSwitch(IdmEntity, SwitchEntity):
    @property
    def is_on(self) -> bool:
        if not self.coordinator.data:
            return False
        value = self.coordinator.data.get(self._register.name)
        return bool(value) if value is not None else False

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.async_write_register(self._register, True)
        except Exception as err:
            _LOGGER.error("Failed to turn on %s: %s", self._register.name, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.async_write_register(self._register, False)
        except Exception as err:
            _LOGGER.error("Failed to turn off %s: %s", self._register.name, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"error": str(err)},
            ) from err
