"""Water heater platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import logging
from typing import Any

from homeassistant.components.water_heater import (
    STATE_HEAT_PUMP,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import IdmCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IDM water heater platform."""
    coordinator: IdmCoordinator = entry.runtime_data.coordinator

    # Check if we have DHW registers at all
    dhw_current_reg = coordinator.get_register("dhw_temp_top")
    dhw_target_reg = coordinator.get_register("dhw_setpoint")

    if dhw_current_reg and dhw_target_reg:
        async_add_entities([IdmWaterHeater(coordinator, dhw_current_reg, dhw_target_reg)])
    else:
        _LOGGER.debug("No DHW registers found; not setting up water_heater platform")


class IdmWaterHeater(CoordinatorEntity[IdmCoordinator], WaterHeaterEntity):
    """Representation of the IDM Domestic Hot Water."""

    _attr_has_entity_name = True
    _attr_translation_key = "water_heater"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_operation_list = [STATE_HEAT_PUMP]
    _attr_current_operation = STATE_HEAT_PUMP

    def __init__(
        self,
        coordinator: IdmCoordinator,
        current_reg: Any,
        target_reg: Any,
    ) -> None:
        """Initialize the water heater."""
        super().__init__(coordinator)
        self._current_reg = current_reg
        self._target_reg = target_reg
        assert coordinator.config_entry is not None
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_water_heater"
        from .entity import build_device_info

        self._attr_device_info = build_device_info(coordinator)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if not self.coordinator.data:
            return None
        # Use top sensor as representative
        val = self.coordinator.data.get(self._current_reg.name)
        return float(val) if val is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self._target_reg.name)
        return float(val) if val is not None else None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        # RegisterDef exposes bounds as min_val/max_val, not min_value/max_value.
        return min_val if (min_val := self._target_reg.min_val) is not None else 30.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return max_val if (max_val := self._target_reg.max_val) is not None else 65.0

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature.

        Routed through the coordinator's centralized write path so it inherits
        optimistic updates (with alias handling), the write_rejected repair
        issue on failure, and the scheduled background refresh.
        """
        temp = kwargs.get("temperature")
        if temp is None:
            return

        await self.coordinator.async_write_register(self._target_reg, temp)
        _LOGGER.debug("Set water heater target temperature to %s", temp)
