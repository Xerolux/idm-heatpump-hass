"""Calculated sensors derived from one IDM coordinator snapshot."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature

from .coordinator import IdmCoordinator
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id


@dataclass(frozen=True)
class CalculatedSensorDefinition:
    """Metadata and calculation function for one derived sensor."""

    key: str
    name: str
    sources: tuple[str, ...]
    calculate: Callable[[Mapping[str, Any]], float | None]
    icon: str
    suggested_display_precision: int = 1
    native_unit_of_measurement: str | None = UnitOfTemperature.CELSIUS
    device_class: SensorDeviceClass | None = SensorDeviceClass.TEMPERATURE


def _temperature(data: Mapping[str, Any], key: str) -> float | None:
    """Return one finite, plausible decoded temperature."""
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or not -100.0 <= numeric <= 200.0:
        return None
    return numeric


def _difference(first_key: str, second_key: str) -> Callable[[Mapping[str, Any]], float | None]:
    """Build a signed temperature-difference calculation."""

    def calculate(data: Mapping[str, Any]) -> float | None:
        first = _temperature(data, first_key)
        second = _temperature(data, second_key)
        if first is None or second is None:
            return None
        return round(first - second, 2)

    return calculate


# COP source registers verified against a live Navigator 10 (issue #135):
#   power_consumption_hp (4122) and thermal_power_flow_sensor (4126) are
# implemented and return plausible values. The road-map rule "no estimated
# values as measurements" (issue #135) is enforced inside _cop: while the
# heat pump is idle both sources report 0 kW and COP is suppressed (None).
_COP_ELECTRIC_POWER_REGISTER = "power_consumption_hp"
_COP_THERMAL_POWER_REGISTER = "thermal_power_flow_sensor"
# Very low electrical input (<50 W) indicates standby/commissioning rather
# than real operation; refuse to emit a (misleading) high COP ratio in that
# band. Real heating operation reads in the kW range.
_COP_MIN_RELEVANT_POWER_KW = 0.05


def _power(data: Mapping[str, Any], key: str) -> float | None:
    """Return one finite, plausible decoded power value in kW."""
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0.0:
        return None
    return numeric


def _cop(data: Mapping[str, Any]) -> float | None:
    """Coefficient of Performance = thermal power / electrical power.

    Returns None unless both source values are present, finite, and above
    the meaningful-operation threshold. This deliberately produces "no
    value" while the heat pump is idle (P_el = 0) so COP never exposes an
    estimated or division-by-zero value — see issue #135.
    """
    electric = _power(data, _COP_ELECTRIC_POWER_REGISTER)
    thermal = _power(data, _COP_THERMAL_POWER_REGISTER)
    if electric is None or thermal is None:
        return None
    if electric <= 0.0 or thermal <= 0.0:
        return None
    if electric < _COP_MIN_RELEVANT_POWER_KW:
        return None
    return round(thermal / electric, 2)


CALCULATED_SENSOR_DEFINITIONS: tuple[CalculatedSensorDefinition, ...] = (
    CalculatedSensorDefinition(
        key="calculated_hp_temperature_delta",
        name="Wärmepumpen-Spreizung",
        sources=("hp_flow_temp", "hp_return_temp"),
        calculate=_difference("hp_flow_temp", "hp_return_temp"),
        icon="mdi:thermometer-lines",
    ),
    CalculatedSensorDefinition(
        key="calculated_heat_source_temperature_delta",
        name="Wärmequellen-Spreizung",
        sources=("heat_source_inlet_temp", "heat_source_outlet_temp"),
        calculate=_difference("heat_source_inlet_temp", "heat_source_outlet_temp"),
        icon="mdi:thermometer-water",
    ),
    CalculatedSensorDefinition(
        key="calculated_dhw_setpoint_deviation",
        name="Warmwasser-Abweichung Ist zu Soll",
        sources=("dhw_temp_top", "dhw_setpoint"),
        calculate=_difference("dhw_temp_top", "dhw_setpoint"),
        icon="mdi:water-thermometer-outline",
    ),
    CalculatedSensorDefinition(
        key="calculated_cop",
        name="Jahresarbeitszahl (COP, momentan)",
        sources=(_COP_ELECTRIC_POWER_REGISTER, _COP_THERMAL_POWER_REGISTER),
        calculate=_cop,
        icon="mdi:gauge",
        suggested_display_precision=2,
        # COP is a dimensionless ratio: no unit and no device class.
        native_unit_of_measurement=None,
        device_class=None,
    ),
)


def _definition_supported(coordinator: IdmCoordinator, definition: CalculatedSensorDefinition) -> bool:
    """Return whether all required source registers exist on this installation."""
    data = coordinator.data
    if not data:
        return False
    unused = coordinator.unused_registers
    return all(source in data and source not in unused for source in definition.sources)


def calculated_sensor_entities(coordinator: IdmCoordinator) -> list[IdmCalculatedSensor]:
    """Create only calculated sensors supported by the detected installation."""
    return [
        IdmCalculatedSensor(coordinator, definition)
        for definition in CALCULATED_SENSOR_DEFINITIONS
        if _definition_supported(coordinator, definition)
    ]


class IdmCalculatedSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Sensor calculated exclusively from the current coordinator snapshot."""

    def __init__(self, coordinator: IdmCoordinator, definition: CalculatedSensorDefinition) -> None:
        super().__init__(coordinator)
        self._definition = definition
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, definition.key)
        self.entity_description = SensorEntityDescription(
            key=definition.key,
            name=definition.name,
            native_unit_of_measurement=definition.native_unit_of_measurement,
            device_class=definition.device_class,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=definition.suggested_display_precision,
            icon=definition.icon,
        )

    def _calculate(self) -> float | None:
        data = self.coordinator.data
        if not data:
            return None
        if any(source in self.coordinator.unused_registers for source in self._definition.sources):
            return None
        return self._definition.calculate(data)

    @property
    def available(self) -> bool:
        return super().available and self._calculate() is not None

    @property
    def native_value(self) -> float | None:
        return self._calculate()
