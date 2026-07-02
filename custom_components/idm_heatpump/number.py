"""Number platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import logging

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from idm_heatpump import RegisterDef

from .const import DOMAIN
from .coordinator import IdmCoordinator
from .entity import IdmEntity
from .adapter_glt import is_glt_measurement

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = entry.runtime_data.coordinator
    entities = [
        IdmNumber(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in coordinator.number_descriptions
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
        try:
            await self.coordinator.async_write_register(self._register, value)
        except Exception as err:
            _LOGGER.error("Failed to write %s = %s: %s", self._register.name, value, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"error": str(err)},
            ) from err
