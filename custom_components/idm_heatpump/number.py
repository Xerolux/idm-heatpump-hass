# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT
from __future__ import annotations
"""Number platform for IDM Heatpump."""

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IdmCoordinator
from .entity import IdmEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = entry.runtime_data.coordinator
    entities = [
        IdmNumber(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in coordinator.number_descriptions
    ]
    async_add_entities(entities)


class IdmNumber(IdmEntity, NumberEntity):

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.get(self._register.name)
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.coordinator.async_write_register(self._register, value)
        except Exception as err:
            _LOGGER.error("Failed to write %s = %s: %s", self._register.name, value, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"error": str(err)},
            ) from err
