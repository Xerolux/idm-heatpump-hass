"""Sensor platform for IDM Heatpump."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_TECHNICIAN_CODES, DOMAIN, MANUFACTURER, MODEL
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import IdmCoordinator
from .entity import IdmEntity
from .modbus_client import DataType

def _decode_bitflag(value: int, options: dict[int, str]) -> str:
    """Decode a bitfield value into a human-readable 'Flag1|Flag2' string."""
    if value == 0:
        return options.get(0, "Aus")
    active = [label for bit, label in options.items() if bit != 0 and (value & bit) == bit]
    return "|".join(active) if active else f"Unbekannt ({value})"
from .technician_codes import calculate_codes

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = entry.runtime_data.coordinator
    entities = [
        IdmSensor(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in coordinator.sensor_descriptions
        if not (
            desc_info["register"].enum_options
            and desc_info["register"].datatype == DataType.UCHAR
            and desc_info["register"].writable
        )
    ]
    if entry.options.get(CONF_TECHNICIAN_CODES, False):
        entities += [
            IdmTechnicianCodeSensor(coordinator, "level_1"),
            IdmTechnicianCodeSensor(coordinator, "level_2"),
        ]
    async_add_entities(entities)


class IdmSensor(IdmEntity, SensorEntity):

    @property
    def native_value(self) -> str | float | int | None:
        value = self.coordinator.data.get(self._register.name)
        if value is None:
            return None
        if self._register.enum_options:
            if self._register.datatype == DataType.BITFLAG:
                return _decode_bitflag(int(value), self._register.enum_options)
            return self._register.enum_options.get(value, f"Unbekannt ({value})")
        return value


class IdmTechnicianCodeSensor(CoordinatorEntity[IdmCoordinator], SensorEntity):
    """Sensor that shows the current Fachmann Ebene access code."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:key-variant"
    _attr_entity_registry_enabled_default = True

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
        self._cancel_timer: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._cancel_timer = async_track_time_interval(
            self.hass, self._async_refresh, timedelta(seconds=60)
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None

    @callback
    def _async_refresh(self, _now: object = None) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        return calculate_codes()[self._level]

    @property
    def available(self) -> bool:
        return True
