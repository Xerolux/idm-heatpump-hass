"""Select platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
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
from .entity import IdmEntity, should_add_entity
from .adapter_enums import get_slug_map_and_key
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
        IdmSelect(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in sort_entity_descriptions(coordinator.select_descriptions)
        if should_add_entity(coordinator, desc_info["register"]) and desc_info["register"].enum_options
    ]
    async_add_entities(entities)


class IdmSelect(IdmEntity, SelectEntity):
    _enum_slug_map: dict[int, str] | None
    _enum_slug_reverse: dict[str, int] | None

    def __init__(self, coordinator: IdmCoordinator, reg: Any, entity_desc: Any) -> None:
        super().__init__(coordinator, reg, entity_desc)
        slug_map, t_key = get_slug_map_and_key(reg.name)
        self._enum_slug_map = slug_map
        self._enum_slug_reverse = {v: k for k, v in slug_map.items()} if slug_map is not None else None

        if slug_map is not None:
            excluded: set[int] = set(getattr(reg, "exclude_from_write", None) or [])
            self._attr_options = [v for k, v in slug_map.items() if k not in excluded]
            self._attr_translation_key = t_key
        elif reg.enum_options is not None:
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
        try:
            int_raw = int(raw)
        except (TypeError, ValueError):
            return None
        if self._enum_slug_map is not None:
            return self._enum_slug_map.get(int_raw)
        options = self._register.enum_options
        if options is None:
            return None
        return options.get(int_raw)

    def _option_to_value(self, option: str) -> int:
        normalized_option = option.casefold()
        if self._enum_slug_reverse is not None:
            if option in self._enum_slug_reverse:
                return self._enum_slug_reverse[option]
            if normalized_option not in self._enum_slug_reverse:
                raise ValueError(f"Unknown option: {option}")
            return self._enum_slug_reverse[normalized_option]
        options = self._register.enum_options
        if options is None:
            raise ValueError(f"No options defined: {option}")
        for key, val in options.items():
            if val == option or str(val).casefold() == normalized_option:
                return key
        raise ValueError(f"Unknown option: {option}")

    async def async_select_option(self, option: str) -> None:
        try:
            value = self._option_to_value(option)
            await self.coordinator.async_write_register(self._register, value)
        except Exception as err:
            _LOGGER.error("Failed to select %s = %s: %s", self._register.name, option, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"error": str(err)},
            ) from err
