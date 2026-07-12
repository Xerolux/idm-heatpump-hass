"""Climate platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import logging
from typing import Any
import re

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.components.climate.const import (
    PRESET_ECO,
    PRESET_COMFORT,
    PRESET_NONE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from idm_heatpump import RegisterDef

from .const import CircuitMode, RoomMode, HeatPumpStatus
from .coordinator import IdmCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_HC_REGEX = re.compile(r"^hc_([a-g])_")
_ZM_ROOM_REGEX = re.compile(r"^zm(\d+)_room(\d+)_")

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IDM climate platform."""
    coordinator: IdmCoordinator = entry.runtime_data.coordinator
    
    entities: list[ClimateEntity] = []

    # Find heating circuits
    circuits = set()
    for reg in coordinator._registers:
        match = _HC_REGEX.search(reg.name)
        if match:
            circuits.add(match.group(1))
            
    for circuit in circuits:
        mode_reg = coordinator.get_register(f"hc_{circuit}_mode")
        target_reg = coordinator.get_register(f"hc_{circuit}_room_setpoint_heat_normal")
        current_reg = coordinator.get_register(f"hc_{circuit}_room_temp")
        
        if mode_reg and target_reg:
            entities.append(IdmHeatingCircuitClimate(coordinator, circuit, mode_reg, target_reg, current_reg))

    # Find zone rooms
    zone_rooms = set()
    for reg in coordinator._registers:
        match = _ZM_ROOM_REGEX.search(reg.name)
        if match:
            zone_rooms.add((int(match.group(1)), int(match.group(2))))

    for zone, room in zone_rooms:
        prefix = f"zm{zone}_room{room}"
        mode_reg = coordinator.get_register(f"{prefix}_mode")
        target_reg = coordinator.get_register(f"{prefix}_setpoint")
        current_reg = coordinator.get_register(f"{prefix}_temp")
        
        if mode_reg and target_reg and current_reg:
            entities.append(IdmZoneRoomClimate(coordinator, zone, room, mode_reg, target_reg, current_reg))

    if entities:
        async_add_entities(entities)


class IdmClimateBase(CoordinatorEntity[IdmCoordinator], ClimateEntity):
    """Base class for IDM climate entities."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: IdmCoordinator,
        mode_reg: RegisterDef,
        target_reg: RegisterDef,
        current_reg: RegisterDef | None,
        unique_id: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._mode_reg = mode_reg
        self._target_reg = target_reg
        self._current_reg = current_reg
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_id}"
        self._attr_device_info = coordinator.device_info
        
        self._attr_min_temp = float(self._target_reg.min_value) if hasattr(self._target_reg, "min_value") else 10.0
        self._attr_max_temp = float(self._target_reg.max_value) if hasattr(self._target_reg, "max_value") else 35.0

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if not self._current_reg or not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self._current_reg.name)
        return float(val) if val is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self._target_reg.name)
        return float(val) if val is not None else None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
            
        if self._target_reg.name in self.coordinator.data:
            self.coordinator.data[self._target_reg.name] = temp
            self.async_write_ha_state()

        try:
            await self.coordinator.client.write_register(self._target_reg, temp)
            _LOGGER.debug("Set %s target temperature to %s", self._attr_unique_id, temp)
        except Exception as err:
            _LOGGER.error("Failed to set target temperature: %s", err)
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        raise NotImplementedError()


class IdmHeatingCircuitClimate(IdmClimateBase):
    """Climate entity for a heating circuit."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL]
    _attr_preset_modes = [PRESET_NONE, PRESET_ECO]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON

    def __init__(
        self,
        coordinator: IdmCoordinator,
        circuit: str,
        mode_reg: RegisterDef,
        target_reg: RegisterDef,
        current_reg: RegisterDef | None,
    ) -> None:
        """Initialize the heating circuit climate."""
        super().__init__(
            coordinator, mode_reg, target_reg, current_reg, f"climate_hc_{circuit}"
        )
        self._circuit = circuit.upper()
        self._attr_translation_key = "heating_circuit"
        self._attr_translation_placeholders = {"circuit": self._circuit}

    @property
    def hvac_mode(self) -> HVACMode | None:
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self._mode_reg.name)
        if val == CircuitMode.OFF:
            return HVACMode.OFF
        if val == CircuitMode.TIMED:
            return HVACMode.AUTO
        if val in (CircuitMode.NORMAL, CircuitMode.ECO, CircuitMode.MANUAL_HEAT):
            return HVACMode.HEAT
        if val == CircuitMode.MANUAL_COOL:
            return HVACMode.COOL
        return None

    @property
    def preset_mode(self) -> str | None:
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self._mode_reg.name)
        if val == CircuitMode.ECO:
            return PRESET_ECO
        if val in (CircuitMode.NORMAL, CircuitMode.MANUAL_HEAT):
            return PRESET_NONE
        return None

    @property
    def hvac_action(self) -> HVACAction | None:
        if not self.coordinator.data:
            return None
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        
        status_val = self.coordinator.data.get("heatpump_status")
        if status_val is not None:
            status = HeatPumpStatus(status_val)
            if HeatPumpStatus.HEATING in status:
                return HVACAction.HEATING
            if HeatPumpStatus.COOLING in status:
                return HVACAction.COOLING
        return HVACAction.IDLE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            val = CircuitMode.OFF
        elif hvac_mode == HVACMode.AUTO:
            val = CircuitMode.TIMED
        elif hvac_mode == HVACMode.HEAT:
            val = CircuitMode.NORMAL
        elif hvac_mode == HVACMode.COOL:
            val = CircuitMode.MANUAL_COOL
        else:
            return
            
        if self._mode_reg.name in self.coordinator.data:
            self.coordinator.data[self._mode_reg.name] = val
            self.async_write_ha_state()

        try:
            await self.coordinator.client.write_register(self._mode_reg, val)
        except Exception:
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_ECO:
            val = CircuitMode.ECO
        else:
            val = CircuitMode.NORMAL
            
        if self._mode_reg.name in self.coordinator.data:
            self.coordinator.data[self._mode_reg.name] = val
            self.async_write_ha_state()

        try:
            await self.coordinator.client.write_register(self._mode_reg, val)
        except Exception:
            await self.coordinator.async_request_refresh()


class IdmZoneRoomClimate(IdmClimateBase):
    """Climate entity for a zone module room."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT]
    _attr_preset_modes = [PRESET_NONE, PRESET_ECO, PRESET_COMFORT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON

    def __init__(
        self,
        coordinator: IdmCoordinator,
        zone: int,
        room: int,
        mode_reg: RegisterDef,
        target_reg: RegisterDef,
        current_reg: RegisterDef,
    ) -> None:
        """Initialize the zone room climate."""
        super().__init__(
            coordinator, mode_reg, target_reg, current_reg, f"climate_zm{zone}_room{room}"
        )
        self._zone = zone
        self._room = room
        self._attr_translation_key = "zone_room"
        self._attr_translation_placeholders = {"zone": str(zone), "room": str(room)}

    @property
    def hvac_mode(self) -> HVACMode | None:
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self._mode_reg.name)
        if val == RoomMode.OFF:
            return HVACMode.OFF
        if val == RoomMode.AUTOMATIC:
            return HVACMode.AUTO
        if val in (RoomMode.NORMAL, RoomMode.ECO, RoomMode.COMFORT):
            return HVACMode.HEAT
        return None

    @property
    def preset_mode(self) -> str | None:
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self._mode_reg.name)
        if val == RoomMode.ECO:
            return PRESET_ECO
        if val == RoomMode.COMFORT:
            return PRESET_COMFORT
        if val == RoomMode.NORMAL:
            return PRESET_NONE
        return None

    @property
    def hvac_action(self) -> HVACAction | None:
        if not self.coordinator.data:
            return None
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        # We assume heating if target > current + some tolerance, else idle
        target = self.target_temperature
        current = self.current_temperature
        if target is not None and current is not None and target > current + 0.2:
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            val = RoomMode.OFF
        elif hvac_mode == HVACMode.AUTO:
            val = RoomMode.AUTOMATIC
        elif hvac_mode == HVACMode.HEAT:
            val = RoomMode.NORMAL
        else:
            return
            
        if self._mode_reg.name in self.coordinator.data:
            self.coordinator.data[self._mode_reg.name] = val
            self.async_write_ha_state()

        try:
            await self.coordinator.client.write_register(self._mode_reg, val)
        except Exception:
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_ECO:
            val = RoomMode.ECO
        elif preset_mode == PRESET_COMFORT:
            val = RoomMode.COMFORT
        else:
            val = RoomMode.NORMAL
            
        if self._mode_reg.name in self.coordinator.data:
            self.coordinator.data[self._mode_reg.name] = val
            self.async_write_ha_state()

        try:
            await self.coordinator.client.write_register(self._mode_reg, val)
        except Exception:
            await self.coordinator.async_request_refresh()
