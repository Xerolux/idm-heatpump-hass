"""Sensor platform for IDM Navigator Heatpump."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, UNUSED_VALUE
from .coordinator import IdmCoordinator
from .modbus_client import DataType


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [
        IdmSensor(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in coordinator.sensor_descriptions
        if not (
            desc_info["register"].enum_options
            and desc_info["register"].datatype == DataType.UCHAR
        )
    ]
    async_add_entities(entities)


class IdmSensor(CoordinatorEntity[IdmCoordinator], SensorEntity):
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
    def native_value(self):
        value = self.coordinator.data.get(self._register.name)
        if value is not None and self._register.enum_options:
            return self._register.enum_options.get(value, f"Unknown ({value})")
        return value
