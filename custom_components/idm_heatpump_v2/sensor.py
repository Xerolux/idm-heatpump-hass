"""Sensor platform for IDM Heatpump."""

from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_TECHNICIAN_CODES, DOMAIN, MANUFACTURER, MODEL, UNUSED_VALUE
from .coordinator import IdmCoordinator
from .modbus_client import DataType
from .technician_codes import calculate_codes


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
    if entry.options.get(CONF_TECHNICIAN_CODES, False):
        entities += [
            IdmTechnicianCodeSensor(coordinator, "level_1"),
            IdmTechnicianCodeSensor(coordinator, "level_2"),
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


class IdmTechnicianCodeSensor(CoordinatorEntity[IdmCoordinator], SensorEntity):
    """Sensor that shows the current Fachmann Ebene access code."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:key-variant"

    _NAMES = {
        "level_1": "Fachmann Ebene 1",
        "level_2": "Fachmann Ebene 2",
    }

    def __init__(self, coordinator: IdmCoordinator, level: str) -> None:
        super().__init__(coordinator)
        self._level = level
        self._attr_unique_id = (
            f"{coordinator.client.host}:{coordinator.client.port}_technician_{level}"
        )
        self._attr_name = self._NAMES[level]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
        self._cancel_timer = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Refresh every 60 seconds so the code is always current
        self._cancel_timer = async_track_time_interval(
            self.hass, self._async_refresh, timedelta(seconds=60)
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None

    @callback
    def _async_refresh(self, _now=None) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        return calculate_codes()[self._level]

    @property
    def available(self) -> bool:
        return True
