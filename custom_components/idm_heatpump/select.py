"""Select platform for IDM Heatpump."""

import logging

from homeassistant.components.select import SelectEntity
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
        IdmSelect(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in coordinator.select_descriptions
        if desc_info["register"].enum_options
    ]
    async_add_entities(entities)


class IdmSelect(IdmEntity, SelectEntity):

    def __init__(self, coordinator: IdmCoordinator, reg, entity_desc) -> None:
        super().__init__(coordinator, reg, entity_desc)
        self._attr_options = list(reg.enum_options.values())

    @property
    def current_option(self) -> str | None:
        raw = self.coordinator.data.get(self._register.name)
        if raw is None:
            return None
        return self._register.enum_options.get(raw)

    def _option_to_value(self, option: str) -> int:
        for key, val in self._register.enum_options.items():
            if val == option:
                return key
        raise ValueError(f"Unknown option: {option}")

    async def async_select_option(self, option: str) -> None:
        try:
            value = self._option_to_value(option)
            await self.coordinator.async_write_register(self._register, value)
        except Exception as err:
            _LOGGER.error("Failed to select %s = %s: %s", self._register.name, option, err)
            raise HomeAssistantError(
                f"Failed to set {self.entity_description.name}: {err}"
            ) from err
