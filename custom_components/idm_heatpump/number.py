"""Number platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from idm_heatpump import RegisterDef

from .coordinator import IdmCoordinator
from .entity import IdmEntity, should_add_entity
from .adapter_glt import is_glt_measurement
from .registers import sort_entity_descriptions

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = entry.runtime_data.coordinator
    entities = [
        IdmNumber(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in sort_entity_descriptions(coordinator.number_descriptions)
        if should_add_entity(coordinator, desc_info["register"])
    ]
    async_add_entities(entities)


class IdmNumber(IdmEntity, NumberEntity):
    def __init__(
        self,
        coordinator: IdmCoordinator,
        reg: RegisterDef,
        entity_desc: NumberEntityDescription,
    ) -> None:
        super().__init__(coordinator, reg, entity_desc)
        if is_glt_measurement(self._register.name):
            # GLT-Messwerte existieren zusätzlich als Sensor mit derselben
            # unique_id-Basis — die Number (Vorgabe) braucht ein Suffix.
            self._attr_unique_id = f"{self._attr_unique_id}_set"

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self._register.name)
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self._async_write_register(value, action_label=f"write {self._register.name}={value}")
