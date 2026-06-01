"""Select platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import logging

from typing import Any

from homeassistant.components.select import SelectEntity
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
        IdmSelect(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in coordinator.select_descriptions
        if desc_info["register"].enum_options
    ]
    async_add_entities(entities)


class IdmSelect(IdmEntity, SelectEntity):
    def __init__(self, coordinator: IdmCoordinator, reg: Any, entity_desc: Any) -> None:
        super().__init__(coordinator, reg, entity_desc)
        if reg.enum_options is not None:
            self._attr_options = list(reg.enum_options.values())
        else:
            self._attr_options = []

    @property
    def current_option(self) -> str | None:
        if not self.coordinator.data:
            return None
        raw = self.coordinator.data.get(self._register.name)
        if raw is None:
            return None
        options = self._register.enum_options
        if options is None:
            return None
        return options.get(int(raw))

    def _option_to_value(self, option: str) -> int:
        options = self._register.enum_options
        if options is None:
            raise ValueError(f"No options defined: {option}")
        for key, val in options.items():
            if val == option:
                return key
        raise ValueError(f"Unknown option: {option}")

    async def async_select_option(self, option: str) -> None:
        try:
            value = self._option_to_value(option)
            await self.coordinator.async_write_register(self._register, value)
        except Exception as err:
            _LOGGER.error(
                "Failed to select %s = %s: %s", self._register.name, option, err
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"error": str(err)},
            ) from err
