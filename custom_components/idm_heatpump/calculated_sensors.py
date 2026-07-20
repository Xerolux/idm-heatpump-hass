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
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
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
