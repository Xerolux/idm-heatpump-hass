"""Number platform for IDM Navigator Heatpump."""

import logging

from homeassistant.components.number import NumberEntity, NumberMode
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
        IdmNumber(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in coordinator.number_descriptions
    ]
    async_add_entities(entities)


class IdmNumber(CoordinatorEntity[IdmCoordinator], NumberEntity):
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
    def native_value(self) -> float | None:
        value = self.coordinator.data.get(self._register.name)
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.coordinator.async_write_register(self._register, value)
        except Exception as err:
            _LOGGER.error("Failed to write %s = %s: %s", self._register.name, value, err)
            raise HomeAssistantError(
                f"Failed to set {self.entity_description.name}: {err}"
            ) from err
