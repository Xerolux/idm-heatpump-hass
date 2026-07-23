"""Button platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from idm_heatpump import DataType, RegisterDef

from .const import DOMAIN, REGISTER_ADDRESS_ERROR_ACKNOWLEDGE
from .coordinator import IdmCoordinator
from .dhw_boost import DhwBoostError, DhwBoostManager, async_get_dhw_boost_manager
from .dhw_boost_services import (
    async_setup_dhw_boost_services,
    async_unload_dhw_boost_services,
)
from .device_hierarchy import build_subdevice_info
from .entity import build_device_info
from .error_messages import classify_write_error, write_error_placeholders

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IDM button platform."""
    coordinator: IdmCoordinator = entry.runtime_data.coordinator

    entities: list[ButtonEntity] = [IdmAcknowledgeErrorsButton(coordinator)]
    mode_register = coordinator.get_register("system_mode")
    setpoint_register = coordinator.get_register("dhw_setpoint")
    temperature_register = coordinator.get_register("dhw_temp_top")
    if (
        isinstance(mode_register, RegisterDef)
        and mode_register.writable
        and isinstance(setpoint_register, RegisterDef)
        and setpoint_register.writable
        and isinstance(temperature_register, RegisterDef)
    ):
        boost = await async_get_dhw_boost_manager(coordinator)
        await async_setup_dhw_boost_services(hass)
        entities.extend(
            [
                IdmDhwBoostStartButton(coordinator, boost),
                IdmDhwBoostCancelButton(coordinator, boost),
            ]
        )
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
        mapped = coordinator.get_register("error_acknowledge")
        if isinstance(mapped, RegisterDef) and mapped.writable:
            self._register = mapped
            self._allow_custom_register = False
        else:
            self._register = RegisterDef(
                address=REGISTER_ADDRESS_ERROR_ACKNOWLEDGE,
                datatype=DataType.UCHAR,
                name="error_acknowledge",
                writable=True,
            )
            self._allow_custom_register = True

    @property
    def device_info(self) -> DeviceInfo:
        return build_subdevice_info(self.coordinator, self._register.name) or build_device_info(self.coordinator)

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.async_write_register(
                self._register,
                1,
                allow_custom_register=self._allow_custom_register,
            )
            _LOGGER.debug("Acknowledged errors via button")
        except Exception as err:
            translation_key = classify_write_error(err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=translation_key,
                translation_placeholders=write_error_placeholders(self._register.name),
            ) from err


class _IdmDhwBoostButtonBase(
    CoordinatorEntity[IdmCoordinator],
    ButtonEntity,
):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IdmCoordinator,
        manager: DhwBoostManager,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._manager = manager
        assert coordinator.config_entry is not None
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        return build_subdevice_info(self.coordinator, "dhw_boost") or build_device_info(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._manager.state_attributes


class IdmDhwBoostStartButton(_IdmDhwBoostButtonBase):
    """Start DHW boost with the safe default target and timeout."""

    _attr_name = "Warmwasser-Boost starten"
    _attr_icon = "mdi:water-boiler-alert"

    def __init__(self, coordinator: IdmCoordinator, manager: DhwBoostManager) -> None:
        super().__init__(coordinator, manager, "dhw_boost_start")

    async def async_press(self) -> None:
        try:
            await self._manager.async_start(
                target_temperature=self._manager.default_target_temperature,
                timeout_minutes=self._manager.default_timeout_minutes,
            )
        except DhwBoostError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_will_remove_from_hass(self) -> None:
        await self._manager.async_shutdown()
        config_entry = self.coordinator.config_entry
        if config_entry is not None:
            await async_unload_dhw_boost_services(
                self.coordinator.hass,
                str(config_entry.entry_id),
            )
        await super().async_will_remove_from_hass()


class IdmDhwBoostCancelButton(_IdmDhwBoostButtonBase):
    """Cancel DHW boost and restore the exact previous values."""

    _attr_name = "Warmwasser-Boost abbrechen"
    _attr_icon = "mdi:water-boiler-off"

    def __init__(self, coordinator: IdmCoordinator, manager: DhwBoostManager) -> None:
        super().__init__(coordinator, manager, "dhw_boost_cancel")

    @property
    def available(self) -> bool:
        return super().available and self._manager.active

    async def async_press(self) -> None:
        try:
            await self._manager.async_cancel()
        except DhwBoostError as err:
            raise HomeAssistantError(str(err)) from err
