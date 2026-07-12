"""Button platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from idm_heatpump import DataType, RegisterDef

from .const import DOMAIN, REGISTER_ADDRESS_ERROR_ACKNOWLEDGE
from .coordinator import IdmCoordinator
from .error_messages import classify_write_error, write_error_placeholders
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IDM button platform."""
    coordinator: IdmCoordinator = entry.runtime_data.coordinator

    entities = [IdmAcknowledgeErrorsButton(coordinator)]
    async_add_entities(entities)


class IdmAcknowledgeErrorsButton(CoordinatorEntity[IdmCoordinator], ButtonEntity):
    """Button to acknowledge errors on the heat pump."""

    _attr_has_entity_name = True
    _attr_translation_key = "acknowledge_errors"
    _attr_icon = "mdi:alert-circle-check"

    def __init__(self, coordinator: IdmCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_acknowledge_errors"
        from .entity import build_device_info

        self._attr_device_info = build_device_info(coordinator)
        self._register = RegisterDef(
            address=REGISTER_ADDRESS_ERROR_ACKNOWLEDGE,
            datatype=DataType.UCHAR,
            name="error_acknowledge",
            writable=True,
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.async_write_register(self._register, 1)
            _LOGGER.debug("Acknowledged errors via button")
        except Exception as err:
            translation_key = classify_write_error(err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=translation_key,
                translation_placeholders=write_error_placeholders(self._register.name),
            ) from err
