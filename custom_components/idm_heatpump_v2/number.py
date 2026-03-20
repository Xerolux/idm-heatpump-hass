"""Number platform for IDM Navigator Heatpump."""

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IdmCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = []
    for desc_info in coordinator.number_descriptions:
        reg = desc_info["register"]
        entity_desc = desc_info["description"]
        entities.append(IdmNumber(coordinator, reg, entity_desc))
    async_add_entities(entities)


class IdmNumber(NumberEntity):
    def __init__(self, coordinator: IdmCoordinator, reg, entity_desc) -> None:
        self._coordinator = coordinator
        self._register = reg
        self.entity_description = entity_desc
        self._attr_unique_id = f"{coordinator.client.host}:{coordinator.client.port}_{reg.name}"
        self._attr_has_entity_name = True

    @property
    def available(self) -> bool:
        return self._register.name in self._coordinator.data

    @property
    def native_value(self) -> float | None:
        value = self._coordinator.data.get(self._register.name)
        if value is None:
            return None
        return float(value)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._coordinator.config_entry.entry_id)},
            "name": self._coordinator.config_entry.title,
            "manufacturer": "iDM Energiesysteme",
            "model": "Navigator 2.0",
        }

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self._coordinator.async_write_register(self._register, value)
        except Exception as err:
            _LOGGER.error("Failed to write %s = %s: %s", self._register.name, value, err)
            raise HomeAssistantError(
                f"Failed to set {self.entity_description.name}: {err}"
            ) from err

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
