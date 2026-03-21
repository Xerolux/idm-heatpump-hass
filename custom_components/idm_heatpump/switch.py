"""Switch platform for IDM Heatpump."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
        IdmSwitch(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in coordinator.switch_descriptions
    ]
    async_add_entities(entities)


class IdmSwitch(IdmEntity, SwitchEntity):

    @property
    def is_on(self) -> bool:
        value = self.coordinator.data.get(self._register.name)
        return bool(value) if value is not None else False

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.async_write_register(self._register, True)
        except Exception as err:
            _LOGGER.error("Failed to turn on %s: %s", self._register.name, err)
            raise HomeAssistantError(
                f"Failed to turn on {self.entity_description.name}: {err}"
            ) from err

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.async_write_register(self._register, False)
        except Exception as err:
            _LOGGER.error("Failed to turn off %s: %s", self._register.name, err)
            raise HomeAssistantError(
                f"Failed to turn off {self.entity_description.name}: {err}"
            ) from err
