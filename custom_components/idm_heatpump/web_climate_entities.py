"""Home Assistant climate and water-heater entities for the web-only mode.

The underlying data and write paths are the Phase 4 web controls
(operating mode, per-circuit mode and room setpoint, hot-water setpoint);
these entities present them as the standard Home Assistant cards. Every
write is the same range-validated web write the select/number entities
use.
"""

from __future__ import annotations

import math
from typing import Any, Final

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import HVACAction, HVACMode
from homeassistant.components.water_heater import (
    STATE_HEAT_PUMP,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import IdmCoordinator
from .device_hierarchy import build_subdevice_info
from .entity import build_entity_unique_id
from .web_control_entities import _web_control_active


def _circuit_state(coordinator: IdmCoordinator, hc_id: str) -> Any:
    supplement = coordinator.web_supplement
    if supplement is None:
        return None
    for circuit in supplement.heating_circuits or ():
        if str(getattr(circuit, "hc_id", "")).lower() == hc_id.lower():
            return circuit
    return None


def web_climate_entities(coordinator: IdmCoordinator) -> list[IdmWebHeatingCircuitClimate]:
    """Create one climate entity per configured circuit for a web-only entry."""
    if not _web_control_active(coordinator):
        return []
    supplement = coordinator.web_supplement
    circuits = supplement.heating_circuits if supplement is not None else ()
    from .differential_circuits import configured_differential_circuits

    differential = configured_differential_circuits(coordinator)
    return [
        IdmWebHeatingCircuitClimate(coordinator, str(getattr(c, "hc_id", "")).lower())
        for c in circuits or ()
        if getattr(c, "setpoint_normal", None) is not None
        and getattr(c, "mode_parameter_id", None)
        and str(getattr(c, "hc_id", "")).lower() not in differential
    ]


def web_water_heater_entities(coordinator: IdmCoordinator) -> list[IdmWebWaterHeater]:
    """Create the hot-water card for a web-only entry."""
    if not _web_control_active(coordinator):
        return []
    supplement = coordinator.web_supplement
    if supplement is None or supplement.dhw_setpoint is None:
        return []
    return [IdmWebWaterHeater(coordinator)]


class _IdmWebClimateEntityBase(CoordinatorEntity[IdmCoordinator]):
    _attr_has_entity_name = True
    _hierarchy_key: str | None = None

    @property
    def available(self) -> bool:
        return (
            self.coordinator.web_supplement is not None
            and getattr(self.coordinator, "web_alive", True) is not False
        )

    @property
    def device_info(self) -> DeviceInfo:
        from .entity import build_device_info

        if self._hierarchy_key and (subdevice := build_subdevice_info(self.coordinator, self._hierarchy_key)):
            return subdevice
        return build_device_info(self.coordinator)


class IdmWebHeatingCircuitClimate(_IdmWebClimateEntityBase, ClimateEntity):
    """One heating circuit as a climate card, web-only."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: IdmCoordinator, hc_id: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry is not None
        self._hc_id = hc_id
        self._hierarchy_key = f"hc_{hc_id}_mode"
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        self._attr_unique_id = build_entity_unique_id(entry.entry_id, f"web_climate_hc_{hc_id}")
        self._attr_translation_key = "web_hc_climate"
        self._attr_translation_placeholders = {"circuit": hc_id.upper()}
        self._last_heat_mode = 2

    def _circuit(self) -> Any:
        return _circuit_state(self.coordinator, self._hc_id)

    @property
    def available(self) -> bool:
        return super().available and self._circuit() is not None

    @property
    def min_temp(self) -> float:
        setpoint = getattr(self._circuit(), "setpoint_normal", None)
        minimum = getattr(setpoint, "min_value", None)
        if not isinstance(minimum, bool) and isinstance(minimum, (int, float)) and math.isfinite(float(minimum)):
            return float(minimum)
        return 15.0

    @property
    def max_temp(self) -> float:
        setpoint = getattr(self._circuit(), "setpoint_normal", None)
        maximum = getattr(setpoint, "max_value", None)
        if not isinstance(maximum, bool) and isinstance(maximum, (int, float)) and math.isfinite(float(maximum)):
            return float(maximum)
        return 30.0

    @property
    def native_current_temperature(self) -> float | None:
        value = getattr(self._circuit(), "room_temperature", None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None

    @property
    def native_target_temperature(self) -> float | None:
        setpoint = getattr(self._circuit(), "setpoint_normal", None)
        value = getattr(setpoint, "value", None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None

    @property
    def target_temperature_step(self) -> float:
        raw_increment = getattr(getattr(self._circuit(), "setpoint_normal", None), "increment", None)
        if isinstance(raw_increment, str):
            raw_increment = raw_increment.strip()
        try:
            step = float(raw_increment)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            step = 0.1
        return step if math.isfinite(step) and step > 0 else 0.1

    @property
    def hvac_mode(self) -> HVACMode | None:
        value = getattr(self._circuit(), "mode_value", None)
        if value is None or isinstance(value, bool):
            return None
        try:
            mode_int = int(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if mode_int == 0:
            return HVACMode.OFF
        self._last_heat_mode = mode_int
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        circuit = self._circuit()
        value = getattr(circuit, "mode_value", None)
        pump = getattr(circuit, "pump_active", None)
        if value is None or isinstance(value, bool):
            return None
        try:
            mode_int = int(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if mode_int == 0:
            return HVACAction.OFF
        return HVACAction.HEATING if pump is True else HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        setpoint = getattr(self._circuit(), "setpoint_normal", None)
        parameter = getattr(setpoint, "parameter_id", None)
        if not parameter:
            return
        await self.coordinator.async_web_set_heatingcircuit_parameter(
            parameter,
            float(temperature),
            min_value=getattr(setpoint, "min_value", None),
            max_value=getattr(setpoint, "max_value", None),
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        parameter = getattr(self._circuit(), "mode_parameter_id", None)
        if not parameter:
            return
        mode = 0 if hvac_mode == HVACMode.OFF else self._last_heat_mode or 2
        await self.coordinator.async_web_set_heatingcircuit_parameter(parameter, float(mode))

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)


_WEB_OPERATION_LIST: Final[list[str]] = [STATE_HEAT_PUMP]


class IdmWebWaterHeater(_IdmWebClimateEntityBase, WaterHeaterEntity):
    """The hot-water storage as a water-heater card, web-only."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_current_operation = STATE_HEAT_PUMP
    _attr_operation_list = _WEB_OPERATION_LIST
    _hierarchy_key = "dhw_setpoint"

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry is not None
        self._attr_unique_id = build_entity_unique_id(entry.entry_id, "web_water_heater")
        self._attr_translation_key = "web_water_heater"

    @property
    def available(self) -> bool:
        return super().available and self._setpoint() is not None

    def _current_temperature_value(self) -> float | None:
        supplement = self.coordinator.web_supplement
        freshwater = getattr(supplement, "freshwater", None) if supplement is not None else None
        top = getattr(getattr(freshwater, "temperature_top", None), "numeric_value", None)
        if isinstance(top, bool) or not isinstance(top, (int, float)) or not math.isfinite(float(top)):
            unused = getattr(self.coordinator, "unused_registers", ())
            data = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
            top = data.get("dhw_temp_top") if "dhw_temp_top" not in unused else None
            if top == -1.0:
                return None
        if isinstance(top, bool) or not isinstance(top, (int, float)):
            return None
        numeric = float(top)
        return numeric if math.isfinite(numeric) else None

    @property
    def native_current_temperature(self) -> float | None:
        return self._current_temperature_value()

    @property
    def min_temp(self) -> float:
        setpoint = self._setpoint()
        minimum = getattr(setpoint, "min_value", None)
        if not isinstance(minimum, bool) and isinstance(minimum, (int, float)) and math.isfinite(float(minimum)):
            return float(minimum)
        return 30.0

    @property
    def max_temp(self) -> float:
        setpoint = self._setpoint()
        maximum = getattr(setpoint, "max_value", None)
        if not isinstance(maximum, bool) and isinstance(maximum, (int, float)) and math.isfinite(float(maximum)):
            return float(maximum)
        return 60.0

    def _setpoint(self) -> Any:
        supplement = self.coordinator.web_supplement
        return getattr(supplement, "dhw_setpoint", None) if supplement is not None else None

    @property
    def native_target_temperature(self) -> float | None:
        value = getattr(self._setpoint(), "value", None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.async_web_set_dhw_setpoint(float(temperature))
