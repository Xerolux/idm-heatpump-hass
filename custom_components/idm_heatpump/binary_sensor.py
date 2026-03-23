# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT
from __future__ import annotations
"""Binary sensor platform for IDM Heatpump."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import IdmCoordinator
from .entity import IdmEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = entry.runtime_data.coordinator
    entities = [
        IdmBinarySensor(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in coordinator.binary_sensor_descriptions
    ]
    async_add_entities(entities)


class IdmBinarySensor(IdmEntity, BinarySensorEntity):

    @property
    def is_on(self) -> bool:
        value = self.coordinator.data.get(self._register.name)
        return bool(value) if value is not None else False
