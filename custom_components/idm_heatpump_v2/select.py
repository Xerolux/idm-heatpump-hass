"""Select platform for IDM Navigator Heatpump."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, UNUSED_VALUE
from .coordinator import IdmCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = []
    for desc_info in coordinator.select_descriptions:
        reg = desc_info["register"]
        entity_desc = desc_info["description"]
        if reg.enum_options:
            entities.append(IdmSelect(coordinator, reg, entity_desc))
    async_add_entities(entities)


class IdmSelect(SelectEntity):
    def __init__(self, coordinator: IdmCoordinator, reg, entity_desc) -> None:
        self._coordinator = coordinator
        self._register = reg
        self._entity_desc = entity_desc
        self._attr_unique_id = f"{coordinator.client.host}:{coordinator.client.port}_{reg.name}"
        self._attr_has_entity_name = True
        self._attr_options = list(reg.enum_options.values())
        self._attr_current_option = None

    @property
    def available(self) -> bool:
        if self._register.name not in self._coordinator.data:
            return False
        if self._coordinator.hide_unused:
            value = self._coordinator.data.get(self._register.name)
            if value is not None and isinstance(value, float):
                if abs(value - UNUSED_VALUE) < 0.01:
                    return False
        return True

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._coordinator.config_entry.entry_id)},
            "name": self._coordinator.config_entry.title,
            "manufacturer": "iDM Energiesysteme",
            "model": "Navigator 2.0",
        }

    def _value_to_option(self, value: int | None) -> str | None:
        if value is None or self._register.enum_options is None:
            return None
        return self._register.enum_options.get(value)

    def _option_to_value(self, option: str) -> int:
        if self._register.enum_options is None:
            raise ValueError("No enum options defined")
        for key, val in self._register.enum_options.items():
            if val == option:
                return key
        raise ValueError(f"Unknown option: {option}")

    async def async_select_option(self, option: str) -> None:
        try:
            value = self._option_to_value(option)
            await self._coordinator.async_write_register(self._register, value)
            self._attr_current_option = option
        except Exception as err:
            _LOGGER.error("Failed to select %s = %s: %s", self._register.name, option, err)
            raise HomeAssistantError(
                f"Failed to set {self._entity_desc.name}: {err}"
            ) from err

    def _handle_coordinator_update(self) -> None:
        raw = self._coordinator.data.get(self._register.name)
        self._attr_current_option = self._value_to_option(raw)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )
        self._handle_coordinator_update()
