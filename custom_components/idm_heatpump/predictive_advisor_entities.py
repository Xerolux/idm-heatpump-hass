"""Home Assistant entities for the read-only predictive advisor."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .advisor_engine import AdvisorEngine
from .advisor_operation_reason import OperationReason, compose_operation_reason
from .coordinator import IdmCoordinator
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id
from .ha_compat import BinarySensorDeviceClass
from .polling_plan import ensure_entity_aware_polling
from .predictive_advisor import (
    ADVISOR_STAGES,
    PredictiveAdvisor,
    confidence_level,
)


def runtime_predictive_advisor(runtime_data: Any) -> PredictiveAdvisor | None:
    """Return only a real advisor, never a truthy MagicMock or legacy placeholder."""
    advisor = getattr(runtime_data, "predictive_advisor", None)
    return advisor if isinstance(advisor, PredictiveAdvisor) else None


def runtime_advisor_engine(runtime_data: Any) -> AdvisorEngine | None:
    """Return only a real engine, never a truthy MagicMock."""
    engine = getattr(runtime_data, "advisor_engine", None)
    return engine if isinstance(engine, AdvisorEngine) else None


def predictive_advisor_sensor_entities(
    coordinator: IdmCoordinator,
    advisor: PredictiveAdvisor | None,
) -> list[IdmAdvisorStatusSensor | IdmAdvisorRecommendationSensor]:
    """Create the advisor status and recommendation sensors."""
    if advisor is None:
        return []
    ensure_entity_aware_polling(coordinator)
    return [IdmAdvisorStatusSensor(coordinator, advisor), IdmAdvisorRecommendationSensor(coordinator, advisor)]


def predictive_advisor_binary_entities(
    coordinator: IdmCoordinator,
    advisor: PredictiveAdvisor | None,
) -> list[IdmAdvisorOptimizationBinarySensor]:
    """Create the optimization-available binary sensor."""
    if advisor is None:
        return []
    return [IdmAdvisorOptimizationBinarySensor(coordinator, advisor)]


def predictive_advisor_producer_entities(
    coordinator: IdmCoordinator,
    advisor: PredictiveAdvisor | None,
    engine: AdvisorEngine | None,
) -> list[AdvisorProducerEntity]:
    """Create the producer-backed advisor sensors (roadmap phases 2-9)."""
    if advisor is None or engine is None:
        return []
    ensure_entity_aware_polling(coordinator)
    entities: list[AdvisorProducerEntity] = [
        IdmAdvisorConfidenceSensor(coordinator, advisor),
        IdmAdvisorOperationReasonSensor(coordinator, engine),
        IdmAdvisorHealthScoreSensor(coordinator, engine),
        IdmAdvisorEfficiencySensor(coordinator, engine),
        IdmAdvisorExpectedCopSensor(coordinator, engine),
        IdmAdvisorBuildingHeatLossSensor(coordinator, engine),
        IdmAdvisorBuildingInertiaSensor(coordinator, engine),
        IdmAdvisorOptimalFlowSensor(coordinator, engine),
        IdmAdvisorDhwWindowSensor(coordinator, engine),
        IdmAdvisorHeatDemandSensor(coordinator, engine),
        IdmAdvisorPlanSensor(coordinator, engine),
    ]
    entities.extend(IdmAdvisorCurveSensor(coordinator, engine, circuit) for circuit in engine.circuits)
    return entities


def predictive_advisor_anomaly_binary(
    coordinator: IdmCoordinator,
    advisor: PredictiveAdvisor | None,
    engine: AdvisorEngine | None,
) -> list[IdmAdvisorAnomalyBinarySensor]:
    """Create the anomaly binary sensor (binary_sensor platform)."""
    if advisor is None or engine is None:
        return []
    return [IdmAdvisorAnomalyBinarySensor(coordinator, engine)]


class IdmAdvisorStatusSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Observation stage, capabilities and data quality of the advisor."""

    def __init__(self, coordinator: IdmCoordinator, advisor: PredictiveAdvisor) -> None:
        super().__init__(coordinator)
        self._advisor = advisor
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_status")
        self._attr_options = list(ADVISOR_STAGES)
        self.entity_description = SensorEntityDescription(
            key="advisor_status",
            translation_key="advisor_status",
            icon="mdi:progress-clock",
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.ENUM,
        )

    @property
    def native_value(self) -> str | None:
        return self._advisor.stage if self._advisor.first_observed is not None else None

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "observation_days": self._advisor.observation_days,
            "recommendations_allowed_after_days": 7,
            "long_term_baselines_after_days": 30,
            "confidence": self._advisor.confidence,
            "data_usable_fraction": self._advisor.usable_fraction,
            "capabilities": self._advisor.capabilities.as_dict(),
            "data_quality": self._advisor.quality_summary(),
            "active_recommendations": [rec.id for rec in self._advisor.active_recommendations],
            "history_entries": len(self._advisor.history),
            "event": "idm_advisor_recommendation",
            "write_actions": False,
        }


class IdmAdvisorRecommendationSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Active advisor recommendations with their full, explainable payloads."""

    def __init__(self, coordinator: IdmCoordinator, advisor: PredictiveAdvisor) -> None:
        super().__init__(coordinator)
        self._advisor = advisor
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_recommendations")
        self.entity_description = SensorEntityDescription(
            key="advisor_recommendations",
            translation_key="advisor_recommendations",
            icon="mdi:playlist-check",
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> int:
        return self._advisor.recommendation_count

    @property
    def available(self) -> bool:
        return super().available and self._advisor.first_observed is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "recommendations": [rec.summary() for rec in self._advisor.active_recommendations],
            "history": [rec.summary() for rec in list(self._advisor.history)[-20:]],
            "event": "idm_advisor_recommendation",
            "write_actions": False,
        }


class IdmAdvisorOptimizationBinarySensor(IdmCoordinatorEntityBase, BinarySensorEntity):
    """On while at least one unhandled advisor recommendation is active."""

    def __init__(self, coordinator: IdmCoordinator, advisor: PredictiveAdvisor) -> None:
        super().__init__(coordinator)
        self._advisor = advisor
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_optimization_available")
        self.entity_description = BinarySensorEntityDescription(
            key="advisor_optimization_available",
            translation_key="advisor_optimization_available",
            icon="mdi:thumb-up-outline",
        )

    @property
    def is_on(self) -> bool:
        return self._advisor.optimization_available

    @property
    def available(self) -> bool:
        return super().available and self._advisor.first_observed is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "unhandled_recommendations": [
                rec.id for rec in self._advisor.active_recommendations if rec.status in ("new", "viewed")
            ],
            "write_actions": False,
        }


# ----------------------------------------------------------------------
# Producer entities (roadmap phases 2-9)
# ----------------------------------------------------------------------


def _coordinator_number(coordinator: IdmCoordinator, key: str) -> float | None:
    value = coordinator.data.get(key) if isinstance(coordinator.data, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


class IdmAdvisorConfidenceSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Framework-level confidence in percent with the documented level."""

    def __init__(self, coordinator: IdmCoordinator, advisor: PredictiveAdvisor) -> None:
        super().__init__(coordinator)
        self._advisor = advisor
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_confidence")
        self.entity_description = SensorEntityDescription(
            key="advisor_confidence",
            translation_key="advisor_confidence",
            icon="mdi:gauge",
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement="%",
        )

    @property
    def native_value(self) -> int | None:
        if self._advisor.first_observed is None:
            return None
        return round(self._advisor.confidence * 100)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "level": str(confidence_level(self._advisor.confidence)),
            "formula": "60% observation coverage (14 days) + 40% usable samples",
            "write_actions": False,
        }


class IdmAdvisorOperationReasonSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Why the heat pump runs right now, with the numbers behind it."""

    def __init__(self, coordinator: IdmCoordinator, engine: AdvisorEngine) -> None:
        super().__init__(coordinator)
        self._engine = engine
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_operation_reason")
        self.entity_description = SensorEntityDescription(
            key="advisor_operation_reason",
            translation_key="advisor_operation_reason",
            icon="mdi:help-circle-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    def _reason(self) -> OperationReason | None:
        data = self.coordinator.data
        if not isinstance(data, dict):
            return None
        return compose_operation_reason(
            data,
            demand_reason=self._engine.demand_reason_label,
            circuits=self._engine.circuits,
        )

    @property
    def native_value(self) -> str | None:
        reason = self._reason()
        return reason.label if reason is not None else None

    @property
    def available(self) -> bool:
        return super().available and self._reason() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        reason = self._reason()
        if reason is None:
            return {"write_actions": False}
        return {**reason.details, "explanation": reason.explanation, "mode": reason.mode_label, "write_actions": False}


class IdmAdvisorAnomalyBinarySensor(IdmCoordinatorEntityBase, BinarySensorEntity):
    """On while the advisor holds at least one anomaly recommendation."""

    def __init__(self, coordinator: IdmCoordinator, engine: AdvisorEngine) -> None:
        super().__init__(coordinator)
        self._engine = engine
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_anomaly_detected")
        self.entity_description = BinarySensorEntityDescription(
            key="advisor_anomaly_detected",
            translation_key="advisor_anomaly_detected",
            icon="mdi:alert-circle-check-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
        )

    @property
    def is_on(self) -> bool:
        return self._engine.anomaly_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"findings": self._engine.anomaly_findings, "write_actions": False}


class IdmAdvisorHealthScoreSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Plant health score with its documented component composition."""

    def __init__(self, coordinator: IdmCoordinator, engine: AdvisorEngine) -> None:
        super().__init__(coordinator)
        self._engine = engine
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_health_score")
        self.entity_description = SensorEntityDescription(
            key="advisor_health_score",
            translation_key="advisor_health_score",
            icon="mdi:heart-pulse",
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> int | None:
        score = self._engine.health["score"]
        return score if isinstance(score, int) else None

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        health = self._engine.health
        return {
            "components": health["components"],
            "composition": "100 - 30 per warning / 12 per hint finding per domain; mean of available domains",
            "write_actions": False,
        }


class IdmAdvisorEfficiencySensor(IdmCoordinatorEntityBase, SensorEntity):
    """Efficiency score: observed COP vs. the learned COP map."""

    def __init__(self, coordinator: IdmCoordinator, engine: AdvisorEngine) -> None:
        super().__init__(coordinator)
        self._engine = engine
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_efficiency_score")
        self.entity_description = SensorEntityDescription(
            key="advisor_efficiency_score",
            translation_key="advisor_efficiency_score",
            icon="mdi:leaf",
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> int | None:
        score = self._engine.efficiency["score"]
        return score if isinstance(score, int) else None

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        efficiency = self._engine.efficiency
        return {
            "expected_cop": efficiency["expected_cop"],
            "observed_cop_7d": efficiency["observed_cop"],
            "deviation_percent": efficiency["deviation_percent"],
            "write_actions": False,
        }


class IdmAdvisorExpectedCopSensor(IdmCoordinatorEntityBase, SensorEntity):
    """COP the learned map expects at the current operating point."""

    def __init__(self, coordinator: IdmCoordinator, engine: AdvisorEngine) -> None:
        super().__init__(coordinator)
        self._engine = engine
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_expected_cop")
        self.entity_description = SensorEntityDescription(
            key="advisor_expected_cop",
            translation_key="advisor_expected_cop",
            icon="mdi:medal-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            suggested_display_precision=2,
        )

    @property
    def native_value(self) -> float | None:
        cop = self._engine.efficiency["expected_cop"]
        return float(cop) if isinstance(cop, (int, float)) else None

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        efficiency = self._engine.efficiency
        return {
            "learned_hours": efficiency["expected_cop_hours"],
            "deviation_percent": efficiency["deviation_percent"],
            "write_actions": False,
        }


class IdmAdvisorBuildingHeatLossSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Building heat loss from the thermal-power regression."""

    def __init__(self, coordinator: IdmCoordinator, engine: AdvisorEngine) -> None:
        super().__init__(coordinator)
        self._engine = engine
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_building_heat_loss")
        self.entity_description = SensorEntityDescription(
            key="advisor_building_heat_loss",
            translation_key="advisor_building_heat_loss",
            icon="mdi:home-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement="W/K",
            suggested_display_precision=1,
        )

    @property
    def native_value(self) -> float | None:
        return self._engine.analytics.heat_loss_w_per_k

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {**self._engine.analytics.building_model, "write_actions": False}


class IdmAdvisorBuildingInertiaSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Thermal inertia estimate from observed cooldown episodes."""

    def __init__(self, coordinator: IdmCoordinator, engine: AdvisorEngine) -> None:
        super().__init__(coordinator)
        self._engine = engine
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_building_thermal_inertia")
        self.entity_description = SensorEntityDescription(
            key="advisor_building_thermal_inertia",
            translation_key="advisor_building_thermal_inertia",
            icon="mdi:timer-sand",
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement="kWh/K",
            suggested_display_precision=1,
        )

    @property
    def native_value(self) -> float | None:
        return self._engine.analytics.thermal_inertia_kwh_per_k

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {**self._engine.analytics.building_model, "write_actions": False}


class IdmAdvisorOptimalFlowSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Flow temperature the learned building curve needs right now."""

    def __init__(self, coordinator: IdmCoordinator, engine: AdvisorEngine) -> None:
        super().__init__(coordinator)
        self._engine = engine
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_optimal_flow_temp")
        self.entity_description = SensorEntityDescription(
            key="advisor_optimal_flow_temp",
            translation_key="advisor_optimal_flow_temp",
            icon="mdi:thermometer-lines",
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            suggested_display_precision=1,
        )

    @property
    def native_value(self) -> float | None:
        outdoor = _coordinator_number(self.coordinator, "outdoor_temp")
        if outdoor is None:
            return None
        return self._engine.analytics.optimal_flow_temp(outdoor)

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None


class IdmAdvisorCurveSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Per-circuit heating-curve recommendation state."""

    def __init__(self, coordinator: IdmCoordinator, engine: AdvisorEngine, circuit: str) -> None:
        super().__init__(coordinator)
        self._engine = engine
        self._circuit = circuit
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, f"advisor_hc_{circuit}_curve_recommendation")
        self._attr_translation_placeholders = {"circuit": circuit.upper()}
        self.entity_description = SensorEntityDescription(
            key=f"advisor_hc_{circuit}_curve_recommendation",
            translation_key="advisor_curve_recommendation",
            icon="mdi:chart-bell-curve",
            entity_category=EntityCategory.DIAGNOSTIC,
            suggested_display_precision=2,
        )

    @property
    def native_value(self) -> float | None:
        recommendation = self._engine.curve_recommendations.get(self._circuit)
        return recommendation["recommended"] if recommendation else None

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        recommendation = self._engine.curve_recommendations.get(self._circuit)
        return {**(recommendation or {}), "write_actions": False}


class IdmAdvisorDhwWindowSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Recommended hot-water charging window from PV or price forecasts."""

    def __init__(self, coordinator: IdmCoordinator, engine: AdvisorEngine) -> None:
        super().__init__(coordinator)
        self._engine = engine
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_dhw_recommendation")
        self.entity_description = SensorEntityDescription(
            key="advisor_dhw_recommendation",
            translation_key="advisor_dhw_recommendation",
            icon="mdi:water-boiler",
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> str | None:
        window = self._engine.dhw_window
        if window is None:
            return None
        start = datetime.fromisoformat(window["start"])
        end = start + timedelta(hours=int(window.get("hours", 3)))
        return f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {**(self._engine.dhw_window or {}), "write_actions": False}


class IdmAdvisorHeatDemandSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Predicted thermal heat demand for the next 24 hours."""

    def __init__(self, coordinator: IdmCoordinator, engine: AdvisorEngine) -> None:
        super().__init__(coordinator)
        self._engine = engine
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_predicted_heat_demand")
        self.entity_description = SensorEntityDescription(
            key="advisor_predicted_heat_demand",
            translation_key="advisor_predicted_heat_demand",
            icon="mdi:radiator",
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.ENERGY,
            native_unit_of_measurement="kWh",
            suggested_display_precision=1,
        )

    @property
    def native_value(self) -> float | None:
        plan = self._engine.plan or {}
        value = plan.get("predicted_heat_demand_kwh")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        plan = self._engine.plan or {}
        return {
            "expected_pv_kwh": plan.get("expected_pv_kwh"),
            "indoor_reference": "measured room temperature, 21 C fallback",
            "write_actions": False,
        }


class IdmAdvisorPlanSensor(IdmCoordinatorEntityBase, SensorEntity):
    """The joined 24-hour plan summary."""

    def __init__(self, coordinator: IdmCoordinator, engine: AdvisorEngine) -> None:
        super().__init__(coordinator)
        self._engine = engine
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "advisor_next_24h")
        self._attr_options = ["ok", "attention"]
        self.entity_description = SensorEntityDescription(
            key="advisor_next_24h",
            translation_key="advisor_next_24h",
            icon="mdi:calendar-clock",
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.ENUM,
        )

    @property
    def native_value(self) -> str | None:
        plan = self._engine.plan
        if plan is None:
            return None
        return "attention" if plan.get("dhw_window_conflicts_with_expensive_hours") else "ok"

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {**(self._engine.plan or {}), "write_actions": False}


AdvisorProducerEntity = (
    IdmAdvisorConfidenceSensor
    | IdmAdvisorOperationReasonSensor
    | IdmAdvisorHealthScoreSensor
    | IdmAdvisorEfficiencySensor
    | IdmAdvisorExpectedCopSensor
    | IdmAdvisorBuildingHeatLossSensor
    | IdmAdvisorBuildingInertiaSensor
    | IdmAdvisorOptimalFlowSensor
    | IdmAdvisorCurveSensor
    | IdmAdvisorDhwWindowSensor
    | IdmAdvisorHeatDemandSensor
    | IdmAdvisorPlanSensor
)
