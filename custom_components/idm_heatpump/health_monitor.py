"""Optional diagnostic health checks for IDM installations."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory

from .calculated_sensors import _cop
from .coordinator import IdmCoordinator
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id


@dataclass(frozen=True)
class HealthCheck:
    """One conservative diagnostic check."""

    key: str
    label: str
    evaluate: Callable[[IdmCoordinator, Any], bool | None]
    icon: str


def _communication(coordinator: IdmCoordinator, _analysis: Any) -> bool | None:
    stats = coordinator.poll_statistics
    return stats.consecutive_failures >= 3


def _many_starts(coordinator: IdmCoordinator, analysis: Any) -> bool | None:
    if analysis is None or not analysis.supports_compressor:
        return None
    return bool(analysis.compressor_starts_last_hours(2) >= 6)


def _low_cop(coordinator: IdmCoordinator, _analysis: Any) -> bool | None:
    if not coordinator.data:
        return None
    cop = _cop(coordinator.data)
    return cop is not None and cop < 2.0


def _dhw_not_reaching_target(coordinator: IdmCoordinator, _analysis: Any) -> bool | None:
    data = coordinator.data
    if not data or "dhw_temp_top" not in data or "dhw_setpoint" not in data:
        return None
    try:
        current = float(data["dhw_temp_top"])
        target = float(data["dhw_setpoint"])
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (current, target)) or target in (-1.0, 0.0):
        return None
    return current < target - 5.0


def _implausible_sensor(coordinator: IdmCoordinator, _analysis: Any) -> bool | None:
    data = coordinator.data
    if not data:
        return None
    candidates = [value for key, value in data.items() if "temp" in key or "temperature" in key]
    numeric = []
    for value in candidates:
        if isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number not in (-1.0, 0.0):
            numeric.append(number)
    return any(value < -50.0 or value > 130.0 for value in numeric)


def _long_defrost(_coordinator: IdmCoordinator, analysis: Any) -> bool | None:
    """Flag only a currently observed defrost longer than 45 minutes."""
    if analysis is None or not hasattr(analysis, "current_defrost_minutes"):
        return None
    duration = analysis.current_defrost_minutes()
    if duration is None:
        return None
    return bool(duration > 45.0)


HEALTH_CHECKS: tuple[HealthCheck, ...] = (
    HealthCheck("health_communication", "Communication problem", _communication, "mdi:lan-disconnect"),
    HealthCheck("health_many_compressor_starts", "Too many compressor starts", _many_starts, "mdi:restart-alert"),
    HealthCheck("health_low_cop", "COP unusually low", _low_cop, "mdi:gauge-low"),
    HealthCheck(
        "health_dhw_not_reaching_target", "DHW does not reach target", _dhw_not_reaching_target, "mdi:water-alert"
    ),
    HealthCheck("health_implausible_sensor", "Implausible sensor value", _implausible_sensor, "mdi:alert-circle"),
    HealthCheck("health_long_defrost", "Defrost cycle unusually long", _long_defrost, "mdi:snowflake-alert"),
)


def health_binary_entities(coordinator: IdmCoordinator, analysis: Any = None) -> list[IdmHealthBinarySensor]:
    """Create optional problem entities; they never write to the heat pump."""
    return [IdmHealthBinarySensor(coordinator, check, analysis) for check in HEALTH_CHECKS]


class IdmHealthBinarySensor(IdmCoordinatorEntityBase, BinarySensorEntity):
    """One health issue represented as a problem binary sensor."""

    def __init__(self, coordinator: IdmCoordinator, check: HealthCheck, analysis: Any) -> None:
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self._check = check
        self._analysis = analysis
        self._attr_unique_id = build_entity_unique_id(coordinator.config_entry.entry_id, check.key)
        self.entity_description = BinarySensorEntityDescription(
            key=check.key,
            translation_key=check.key,
            icon=check.icon,
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def is_on(self) -> bool | None:
        return self._check.evaluate(self.coordinator, self._analysis)

    @property
    def available(self) -> bool:
        return super().available and self.is_on is not None


class IdmHealthReportSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Human-readable current diagnostic report with machine-readable details."""

    def __init__(self, coordinator: IdmCoordinator, analysis: Any = None) -> None:
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self._analysis = analysis
        self._attr_unique_id = build_entity_unique_id(coordinator.config_entry.entry_id, "health_report")
        self._attr_options = ["ok", "problem"]
        self.entity_description = SensorEntityDescription(
            key="health_report",
            translation_key="health_report",
            icon="mdi:file-document-alert-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.ENUM,
        )

    @property
    def native_value(self) -> str:
        active = [check.label for check in HEALTH_CHECKS if check.evaluate(self.coordinator, self._analysis)]
        return "problem" if active else "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        active_checks = [check.key for check in HEALTH_CHECKS if check.evaluate(self.coordinator, self._analysis)]
        return {
            "active_checks": active_checks,
            "report_version": 1,
            "report_purpose": "installer_diagnostic_summary",
            "summary": "problem" if active_checks else "ok",
            "communication_failures": self.coordinator.poll_statistics.consecutive_failures,
            "last_update_success": self.coordinator.last_update_success,
            "model": self.coordinator.model_name,
            "firmware": self.coordinator.firmware_version,
            "diagnostic_scope": "current_snapshot_and_persisted_operation_analysis",
            "write_actions": False,
        }


def health_report_entities(coordinator: IdmCoordinator, analysis: Any = None) -> list[IdmHealthReportSensor]:
    return [IdmHealthReportSensor(coordinator, analysis)]
