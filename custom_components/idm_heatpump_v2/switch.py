"""Switch platform for IDM Heatpump."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, UNUSED_VALUE
from .coordinator import IdmCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [
        IdmSwitch(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in coordinator.switch_descriptions
    ]
    async_add_entities(entities)


class IdmSwitch(CoordinatorEntity[IdmCoordinator], SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: IdmCoordinator, reg, entity_desc) -> None:
        super().__init__(coordinator)
        self._register = reg
        self.entity_description = entity_desc
        self._attr_unique_id = (
            f"{coordinator.client.host}:{coordinator.client.port}_{reg.name}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if not self.coordinator.data or self._register.name not in self.coordinator.data:
            return False
        if self.coordinator.hide_unused:
            value = self.coordinator.data.get(self._register.name)
            if isinstance(value, float) and abs(value - UNUSED_VALUE) < 0.01:
                return False
        return True

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
