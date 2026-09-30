"""Home Assistant climate and water-heater entities for the web-only mode.

The underlying data and write paths are the Phase 4 web controls
(operating mode, per-circuit mode and room setpoint, hot-water setpoint);
these entities present them as the standard Home Assistant cards. Every
write is the same range-validated web write the select/number entities
use.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACAction, HVACMode
from homeassistant.components.water_heater import WaterHeaterEntity
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import IdmCoordinator
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

    return [
        IdmWebHeatingCircuitClimate(coordinator, str(getattr(c, "hc_id", "")).lower())
        for c in circuits or ()
        if getattr(c, "setpoint_normal", None) is not None
        and getattr(c, "mode_parameter_id", None)
        and str(getattr(c, "hc_id", "")).lower() not in configured_differential_circuits(coordinator)
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

    @property
    def available(self) -> bool:
        return self.coordinator.web_supplement is not None

    @property
    def device_info(self) -> DeviceInfo:
        from .entity import build_device_info

        return build_device_info(self.coordinator)


class IdmWebHeatingCircuitClimate(_IdmWebClimateEntityBase, ClimateEntity):
    """One heating circuit as a climate card, web-only."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_hvac_setpoint = 15.0
    _attr_max_hvac_setpoint = 30.0

    def __init__(self, coordinator: IdmCoordinator, hc_id: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry is not None
        self._hc_id = hc_id
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
    def current_temperature(self) -> float | None:
        value = getattr(self._circuit(), "room_temperature", None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    @property
    def target_temperature(self) -> float | None:
        setpoint = getattr(self._circuit(), "setpoint_normal", None)
        value = getattr(setpoint, "value", None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        minimum = getattr(setpoint, "min_value", None)
        maximum = getattr(setpoint, "max_value", None)
        if isinstance(minimum, (int, float)):
            self._attr_min_hvac_setpoint = float(minimum)
        if isinstance(maximum, (int, float)):
            self._attr_max_hvac_setpoint = float(maximum)
        return float(value)

    @property
    def target_temperature_step(self) -> float:
        raw_increment = getattr(getattr(self._circuit(), "setpoint_normal", None), "increment", None)
        if isinstance(raw_increment, str):
            raw_increment = raw_increment.strip()
        try:
            step = float(raw_increment)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            step = 0.1
        return step if step > 0 else 0.1

    @property
    def hvac_mode(self) -> HVACMode | None:
        value = getattr(self._circuit(), "mode_value", None)
        if value is None:
            return None
        if int(value) == 0:
            return HVACMode.OFF
        self._last_heat_mode = int(value)
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        circuit = self._circuit()
        value = getattr(circuit, "mode_value", None)
        pump = getattr(circuit, "pump_active", None)
        if value is None:
            return None
        if int(value) == 0:
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


class IdmWebWaterHeater(_IdmWebClimateEntityBase, WaterHeaterEntity):
    """The hot-water storage as a water-heater card, web-only."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list: list[str] | None = None

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry is not None
        self._attr_unique_id = build_entity_unique_id(entry.entry_id, "web_water_heater")
        self._attr_translation_key = "web_water_heater"

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.web_supplement is not None

    def _current_temperature_value(self) -> float | None:
        supplement = self.coordinator.web_supplement
        freshwater = getattr(supplement, "freshwater", None) if supplement is not None else None
        top = getattr(getattr(freshwater, "temperature_top", None), "numeric_value", None)
        if isinstance(top, bool) or not isinstance(top, (int, float)):
            top = self.coordinator.data.get("dhw_temp_top") if isinstance(self.coordinator.data, dict) else None
        if isinstance(top, bool) or not isinstance(top, (int, float)):
            return None
        return float(top)

    @property
    def current_temperature(self) -> float | None:
        return self._current_temperature_value()

    @property
    def min_temp(self) -> float:
        setpoint = self._setpoint()
        minimum = getattr(setpoint, "min_value", None)
        return float(minimum) if isinstance(minimum, (int, float)) else 30.0

    @property
    def max_temp(self) -> float:
        setpoint = self._setpoint()
        maximum = getattr(setpoint, "max_value", None)
        return float(maximum) if isinstance(maximum, (int, float)) else 60.0

    def _setpoint(self) -> Any:
        supplement = self.coordinator.web_supplement
        return getattr(supplement, "dhw_setpoint", None) if supplement is not None else None

    @property
    def target_temperature(self) -> float | None:
        value = getattr(self._setpoint(), "value", None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    @property
    def target_temperature_high(self) -> float | None:
        return self.target_temperature

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.async_web_set_dhw_setpoint(float(temperature))
