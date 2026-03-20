"""Switch platform for IDM Navigator Heatpump."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, HomeAssistantError
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
    for desc_info in coordinator.switch_descriptions:
        reg = desc_info["register"]
        entity_desc = desc_info["description"]
        entities.append(IdmSwitch(coordinator, reg, entity_desc))
    async_add_entities(entities)


class IdmSwitch(SwitchEntity):
    def __init__(self, coordinator: IdmCoordinator, reg, entity_desc) -> None:
        self._coordinator = coordinator
        self._register = reg
        self.entity_description = entity_desc
        self._attr_unique_id = f"{coordinator.client.host}:{coordinator.client.port}_{reg.name}"
        self._attr_has_entity_name = True
        self._attr_is_on = False

    @property
    def available(self) -> bool:
        return self._register.name in self._coordinator.data

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._coordinator.config_entry.entry_id)},
            "name": self._coordinator.config_entry.title,
            "manufacturer": "iDM Energiesysteme",
            "model": "Navigator 2.0",
        }

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self._coordinator.async_write_register(self._register, True)
            self._attr_is_on = True
        except Exception as err:
            _LOGGER.error("Failed to turn on %s: %s", self._register.name, err)
            raise HomeAssistantError(
                f"Failed to turn on {self.entity_description.name}: {err}"
            ) from err

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self._coordinator.async_write_register(self._register, False)
            self._attr_is_on = False
        except Exception as err:
            _LOGGER.error("Failed to turn off %s: %s", self._register.name, err)
            raise HomeAssistantError(
                f"Failed to turn off {self.entity_description.name}: {err}"
            ) from err

    def _handle_coordinator_update(self) -> None:
        raw = self._coordinator.data.get(self._register.name)
        self._attr_is_on = bool(raw) if raw is not None else False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )
        self._handle_coordinator_update()
