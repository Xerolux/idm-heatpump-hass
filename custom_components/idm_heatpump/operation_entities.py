"""Home Assistant entities for persisted IDM operating analysis."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime

from .coordinator import IdmCoordinator
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id
from .operation_analysis import OperationAnalysis

AnalysisValue = int | float | datetime | None


@dataclass(frozen=True)
class OperationSensorDefinition:
    """Metadata and value function for one operating-analysis sensor."""

    key: str
    name: str
    value: Callable[[OperationAnalysis], AnalysisValue]
    icon: str
    source: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    enabled_by_default: bool = True
    precision: int | None = None


_OPERATION_SENSOR_DEFINITIONS: tuple[OperationSensorDefinition, ...] = (
    OperationSensorDefinition(
        key="analysis_heat_pump_cycles_recorded",
        name="Wärmepumpentakte erfasst",
        value=lambda analysis: analysis.total_compressor_starts,
        icon="mdi:counter",
        source="compressor",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    OperationSensorDefinition(
        key="analysis_heat_pump_cycles_today",
        name="Wärmepumpentakte heute",
        value=lambda analysis: analysis.compressor_starts_today(),
        icon="mdi:calendar-today",
        source="compressor",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OperationSensorDefinition(
        key="analysis_heat_pump_cycles_2h",
        name="Wärmepumpentakte letzte 2 Stunden",
        value=lambda analysis: analysis.compressor_starts_last_hours(2),
        icon="mdi:history",
        source="compressor",
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    OperationSensorDefinition(
        key="analysis_heat_pump_cycles_4h",
        name="Wärmepumpentakte letzte 4 Stunden",
        value=lambda analysis: analysis.compressor_starts_last_hours(4),
        icon="mdi:history",
        source="compressor",
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    OperationSensorDefinition(
        key="analysis_current_cycle_duration",
        name="Aktuelle Taktlaufzeit",
        value=lambda analysis: analysis.current_cycle_minutes(),
        icon="mdi:timer-play-outline",
        source="compressor",
        unit=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        precision=1,
    ),
    OperationSensorDefinition(
        key="analysis_average_cycle_duration",
        name="Durchschnittliche Taktlaufzeit",
        value=lambda analysis: analysis.average_cycle_minutes(),
        icon="mdi:timer-sand-complete",
        source="compressor",
        unit=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        precision=1,
    ),
    OperationSensorDefinition(
        key="analysis_last_compressor_start",
        name="Letzter Verdichterstart",
        value=lambda analysis: analysis.last_compressor_start,
        icon="mdi:clock-start",
        source="compressor",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    OperationSensorDefinition(
        key="analysis_last_cycle_duration",
        name="Letzte Taktlaufzeit",
        value=lambda analysis: (
            round(analysis.last_cycle_duration / 60.0, 1) if analysis.last_cycle_duration is not None else None
        ),
        icon="mdi:timer-check-outline",
        source="compressor",
        unit=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        precision=1,
        enabled_by_default=False,
    ),
    OperationSensorDefinition(
        key="analysis_defrost_starts_recorded",
        name="Abtauvorgänge erfasst",
        value=lambda analysis: analysis.total_defrost_starts,
        icon="mdi:snowflake-melt",
        source="mode",
        state_class=SensorStateClass.TOTAL_INCREASING,
        enabled_by_default=False,
    ),
    OperationSensorDefinition(
        key="analysis_defrost_starts_today",
        name="Abtauvorgänge heute",
        value=lambda analysis: analysis.defrost_starts_today(),
        icon="mdi:snowflake-melt",
        source="mode",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OperationSensorDefinition(
        key="analysis_last_defrost_start",
        name="Letzter Abtaustart",
        value=lambda analysis: analysis.last_defrost_start,
        icon="mdi:snowflake-clock",
        source="mode",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    OperationSensorDefinition(
        key="analysis_time_since_last_defrost",
        name="Zeit seit letztem Abtaustart",
        value=lambda analysis: analysis.minutes_since_last_defrost(),
        icon="mdi:timer-snowflake",
        source="mode",
        unit=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        precision=1,
    ),
    *(
        OperationSensorDefinition(
            key=f"analysis_operating_share_{mode}",
            name=f"Betriebsanteil {label}",
            value=lambda analysis, mode=mode: analysis.operating_share(mode),
            icon=icon,
            source="mode",
            unit=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            enabled_by_default=False,
            precision=1,
        )
        for mode, label, icon in (
            ("heating", "Heizen", "mdi:radiator"),
            ("dhw", "Warmwasser", "mdi:water-boiler"),
            ("cooling", "Kühlen", "mdi:snowflake"),
            ("defrost", "Abtauen", "mdi:snowflake-melt"),
        )
    ),
)


def runtime_operation_analysis(runtime_data: Any) -> OperationAnalysis | None:
    """Return only a real tracker, never a truthy MagicMock or legacy placeholder."""
    analysis = getattr(runtime_data, "operation_analysis", None)
    return analysis if isinstance(analysis, OperationAnalysis) else None


def operation_sensor_entities(
    coordinator: IdmCoordinator,
    analysis: OperationAnalysis | None,
) -> list[IdmOperationSensor]:
    """Create analysis sensors only for verified source registers."""
    if analysis is None:
        return []
    return [
        IdmOperationSensor(coordinator, analysis, definition)
        for definition in _OPERATION_SENSOR_DEFINITIONS
        if (definition.source == "compressor" and analysis.supports_compressor)
        or (definition.source == "mode" and analysis.supports_operating_mode)
    ]


class IdmOperationSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Sensor backed by the restart-safe operation analysis tracker."""

    def __init__(
        self,
        coordinator: IdmCoordinator,
        analysis: OperationAnalysis,
        definition: OperationSensorDefinition,
    ) -> None:
        super().__init__(coordinator)
        self._analysis = analysis
        self._definition = definition
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, definition.key)
        self.entity_description = SensorEntityDescription(
            key=definition.key,
            name=definition.name,
            icon=definition.icon,
            native_unit_of_measurement=definition.unit,
            device_class=definition.device_class,
            state_class=definition.state_class,
            entity_registry_enabled_default=definition.enabled_by_default,
            suggested_display_precision=definition.precision,
        )

    @property
    def native_value(self) -> AnalysisValue:
        return self._definition.value(self._analysis)

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes: dict[str, Any] = {
            "recording_scope": "observed_since_feature_activation",
            "compressor_counting_method": "aggregate_any_compressor_off_to_on",
        }
        if self._definition.key.startswith("analysis_compressor"):
            attributes["completed_cycles_used_for_average"] = len(self._analysis.completed_cycle_durations)
        return attributes


def short_cycle_binary_entities(
    coordinator: IdmCoordinator,
    analysis: OperationAnalysis | None,
) -> list[IdmShortCycleBinarySensor]:
    """Create the short-cycle warning only for verified compressor sources."""
    if analysis is None or not analysis.supports_compressor:
        return []
    return [IdmShortCycleBinarySensor(coordinator, analysis)]


class IdmShortCycleBinarySensor(IdmCoordinatorEntityBase, BinarySensorEntity):
    """Problem sensor indicating that the last fully observed cycle was short."""

    def __init__(self, coordinator: IdmCoordinator, analysis: OperationAnalysis) -> None:
        super().__init__(coordinator)
        self._analysis = analysis
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(
            entry_id,
            "analysis_last_cycle_short",
        )
        self.entity_description = BinarySensorEntityDescription(
            key="analysis_last_cycle_short",
            name="Letzter Verdichtertakt zu kurz",
            icon="mdi:timer-alert-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
        )

    @property
    def is_on(self) -> bool | None:
        return self._analysis.last_cycle_was_short

    @property
    def available(self) -> bool:
        return super().available and self.is_on is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        duration = self._analysis.last_cycle_duration
        return {
            "threshold_minutes": self._analysis.short_cycle_minutes,
            "last_cycle_minutes": round(duration / 60.0, 1) if duration is not None else None,
            "last_cycle_ended": self._analysis.last_cycle_ended,
        }
