"""Binary sensor platform for IDM Navigator Heatpump."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IdmCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = []
    for desc_info in coordinator.binary_sensor_descriptions:
        reg = desc_info["register"]
        entity_desc = desc_info["description"]
        entities.append(IdmBinarySensor(coordinator, reg, entity_desc))
    async_add_entities(entities)


class IdmBinarySensor(BinarySensorEntity):
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
    def is_on(self) -> bool:
        value = self._coordinator.data.get(self._register.name)
        if value is None:
            return False
        return bool(value)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._coordinator.config_entry.entry_id)},
            "name": self._coordinator.config_entry.title,
            "manufacturer": "iDM Energiesysteme",
            "model": "Navigator 2.0",
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
