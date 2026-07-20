"""Binary sensor platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .binary_semantics import binary_value_is_on
from .coordinator import IdmCoordinator
from .entity import IdmEntity, should_add_entity
from .operation_entities import (
    IdmShortCycleBinarySensor,
    runtime_operation_analysis,
    short_cycle_binary_entities,
)
from .registers import sort_entity_descriptions
from .web_binary_sensors import IdmWebBinarySensor, web_binary_sensor_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = entry.runtime_data.coordinator
    entities: list[IdmBinarySensor | IdmWebBinarySensor | IdmShortCycleBinarySensor] = [
        IdmBinarySensor(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in sort_entity_descriptions(coordinator.binary_sensor_descriptions)
        if should_add_entity(coordinator, desc_info["register"])
    ]
    entities += short_cycle_binary_entities(
        coordinator,
        runtime_operation_analysis(entry.runtime_data),
    )
    if coordinator.web_enabled:
        entities += web_binary_sensor_entities(coordinator)
    async_add_entities(entities)


class IdmBinarySensor(IdmEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool:
        if not self.coordinator.data:
            return False
        value = self.coordinator.data.get(self._register.name)
        return binary_value_is_on(self._register, value)
