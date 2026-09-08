"""Water heater platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — unofficial community integration for IDM Navigator 2.0 / 10 heat pumps
# Created by Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# SPDX-License-Identifier: MIT
import logging
import math
from typing import Any, Final

from homeassistant.components.water_heater import (
    STATE_HEAT_PUMP,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from idm_heatpump import RegisterDef

from .adapter_metadata import native_step_for_register
from .coordinator import IdmCoordinator
from .device_hierarchy import build_subdevice_info
from .entity import async_write_translated, build_device_info

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


_OPERATION_LIST: Final[list[str]] = [STATE_HEAT_PUMP]


class IdmWaterHeater(CoordinatorEntity[IdmCoordinator], WaterHeaterEntity):
    """Representation of the IDM Domestic Hot Water."""

    _attr_has_entity_name = True
    _attr_translation_key = "water_heater"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_current_operation = STATE_HEAT_PUMP

    def __init__(
        self,
        coordinator: IdmCoordinator,
        current_reg: Any,
        target_reg: Any,
    ) -> None:
        """Initialize the water heater."""
        super().__init__(coordinator)
        self._attr_operation_list = _OPERATION_LIST
        self._current_reg = current_reg
        self._target_reg = target_reg
        assert coordinator.config_entry is not None
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_water_heater"
        self._attr_target_temperature_step = native_step_for_register(self._target_reg)

    @property
    def device_info(self) -> DeviceInfo:
        return build_subdevice_info(self.coordinator, self._target_reg.name) or build_device_info(self.coordinator)

    @property
    def available(self) -> bool:
        """Hide the entity when DHW registers report unused sentinels."""
        if not super().available:
            return False
        data = self.coordinator.data
        if not data:
            return False
        for reg in (self._current_reg, self._target_reg):
            if reg.name not in data:
                return False
            if reg.name in self.coordinator.unused_registers:
                return False
        return True

    def _usable_temperature(self, reg: RegisterDef) -> float | None:
        """Return one register value that is safe to publish as a temperature.

        An unused or non-finite reading must not reach the state machine: the
        water heater card rendered the API's unset sentinel as a real storage
        temperature. The coordinator's per-poll unused set is the authority, so
        no sentinel literal is repeated here.
        """
        data = self.coordinator.data
        if not data:
            return None
        value = data.get(reg.name)
        if value is None or reg.name in self.coordinator.unused_registers:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if math.isfinite(numeric) else None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        # Use top sensor as representative
        return self._usable_temperature(self._current_reg)

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._usable_temperature(self._target_reg)

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

        await async_write_translated(
            self.coordinator,
            self._target_reg,
            temp,
            action_label="set the water heater target temperature for",
        )
        _LOGGER.debug("Set water heater target temperature to %s", temp)
