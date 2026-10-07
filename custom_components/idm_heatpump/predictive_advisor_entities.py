"""Home Assistant entities for the read-only predictive advisor."""

from __future__ import annotations

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

from .coordinator import IdmCoordinator
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id
from .polling_plan import ensure_entity_aware_polling
from .predictive_advisor import ADVISOR_STAGES, PredictiveAdvisor


def runtime_predictive_advisor(runtime_data: Any) -> PredictiveAdvisor | None:
    """Return only a real advisor, never a truthy MagicMock or legacy placeholder."""
    advisor = getattr(runtime_data, "predictive_advisor", None)
    return advisor if isinstance(advisor, PredictiveAdvisor) else None


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
