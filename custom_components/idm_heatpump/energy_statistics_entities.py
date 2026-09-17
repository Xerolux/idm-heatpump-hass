"""Home Assistant sensors for persistent IDM energy statistics."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import UnitOfEnergy

from .coordinator import IdmCoordinator
from .energy_statistics import EnergyStatistics
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id


class _Definition:
    def __init__(
        self, key: str, value: Callable[[EnergyStatistics], Any], icon: str, state_class: SensorStateClass
    ) -> None:
        self.key = key
        self.value = value
        self.icon = icon
        self.state_class = state_class


_ENERGY_DEFINITIONS = (
    _Definition(
        "energy_electrical_total", lambda s: s.total_electrical_kwh, "mdi:flash", SensorStateClass.TOTAL_INCREASING
    ),
    _Definition(
        "energy_thermal_total", lambda s: s.total_thermal_kwh, "mdi:heat-wave", SensorStateClass.TOTAL_INCREASING
    ),
    _Definition(
        "energy_electrical_today", lambda s: s.today_electrical_kwh, "mdi:calendar-today", SensorStateClass.MEASUREMENT
    ),
    _Definition(
        "energy_thermal_today", lambda s: s.today_thermal_kwh, "mdi:calendar-today", SensorStateClass.MEASUREMENT
    ),
    _Definition(
        "energy_electrical_month", lambda s: s.month_electrical_kwh, "mdi:calendar-month", SensorStateClass.MEASUREMENT
    ),
    _Definition(
        "energy_thermal_month", lambda s: s.month_thermal_kwh, "mdi:calendar-month", SensorStateClass.MEASUREMENT
    ),
    _Definition("energy_cop_total", lambda s: s.total_cop, "mdi:gauge", SensorStateClass.MEASUREMENT),
    _Definition("energy_cop_today", lambda s: s.today_cop, "mdi:gauge", SensorStateClass.MEASUREMENT),
    _Definition("energy_cop_month", lambda s: s.month_cop, "mdi:gauge", SensorStateClass.MEASUREMENT),
    _Definition("energy_cost_total", lambda s: s.total_cost, "mdi:currency-eur", SensorStateClass.MEASUREMENT),
    _Definition("energy_cost_today", lambda s: s.today_cost, "mdi:currency-eur", SensorStateClass.MEASUREMENT),
    _Definition("energy_cost_month", lambda s: s.month_cost, "mdi:currency-eur", SensorStateClass.MEASUREMENT),
    _Definition("energy_co2_total", lambda s: s.total_co2_kg, "mdi:molecule-co2", SensorStateClass.MEASUREMENT),
    _Definition("energy_co2_month", lambda s: s.month_co2_kg, "mdi:molecule-co2", SensorStateClass.MEASUREMENT),
    _Definition(
        "energy_pv_self_consumed_total",
        lambda s: s.total_pv_self_consumed_kwh,
        "mdi:solar-power",
        SensorStateClass.TOTAL_INCREASING,
    ),
    _Definition(
        "energy_pv_self_consumed_today",
        lambda s: s.today_pv_self_consumed_kwh,
        "mdi:solar-power",
        SensorStateClass.MEASUREMENT,
    ),
    _Definition(
        "energy_pv_self_consumed_month",
        lambda s: s.month_pv_self_consumed_kwh,
        "mdi:solar-power",
        SensorStateClass.MEASUREMENT,
    ),
)


def energy_statistics_entities(coordinator: IdmCoordinator) -> list[IdmEnergyStatisticsSensor]:
    statistics = coordinator.energy_statistics
    if statistics is None:
        return []
    if not {"power_consumption_hp", "thermal_power_flow_sensor"}.issubset(coordinator.data or {}):
        return []
    return [IdmEnergyStatisticsSensor(coordinator, statistics, definition) for definition in _ENERGY_DEFINITIONS]


class IdmEnergyStatisticsSensor(IdmCoordinatorEntityBase, SensorEntity):
    """One persisted energy statistic."""

    def __init__(self, coordinator: IdmCoordinator, statistics: EnergyStatistics, definition: _Definition) -> None:
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self._statistics = statistics
        self._definition = definition
        self._attr_unique_id = build_entity_unique_id(coordinator.config_entry.entry_id, definition.key)
        is_cop = definition.key.startswith("energy_cop_")
        is_cost = definition.key.startswith("energy_cost_")
        is_co2 = definition.key.startswith("energy_co2_")
        self.entity_description = SensorEntityDescription(
            key=definition.key,
            translation_key=definition.key,
            icon=definition.icon,
            native_unit_of_measurement=(
                "€" if is_cost else "kg" if is_co2 else None if is_cop else UnitOfEnergy.KILO_WATT_HOUR
            ),
            device_class=(None if is_cop or is_cost or is_co2 else SensorDeviceClass.ENERGY),
            state_class=definition.state_class,
            suggested_display_precision=2,
        )

    @property
    def native_value(self) -> Any:
        return self._definition.value(self._statistics)

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None
