"""Switch platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import IdmCoordinator
from .entity import IdmEntity, should_add_entity
from .registers import sort_entity_descriptions

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

    async def _async_turn(self, state: bool) -> None:
        action = "on" if state else "off"
        await self._async_write_register(state, action_label=f"turn {action} {self._register.name}")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_turn(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_turn(False)
