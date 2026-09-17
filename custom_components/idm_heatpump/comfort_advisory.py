"""Read-only weather and heating-curve recommendations."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.entity import EntityCategory

from .entity import IdmCoordinatorEntityBase, build_entity_unique_id


def _number(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


class ComfortAdvisorySensor(IdmCoordinatorEntityBase, SensorEntity):
    """One read-only recommendation for the dashboard."""

    def __init__(self, coordinator: Any, key: str, icon: str, evaluator: Any) -> None:
        super().__init__(coordinator)
        self._evaluator = evaluator
        self._attr_unique_id = build_entity_unique_id(coordinator.config_entry.entry_id, key)
        self.entity_description = SensorEntityDescription(
            key=key,
            translation_key=key,
            icon=icon,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> str | None:
        return self._evaluator(self.coordinator)

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None


def heating_curve_advisory(coordinator: Any, circuit: str) -> ComfortAdvisorySensor:
    def evaluate(current: Any) -> str | None:
        data = current.data or {}
        flow = _number(data.get(f"hc_{circuit}_flow_temp"))
        target = _number(data.get(f"hc_{circuit}_setpoint_flow_temp"))
        if flow is None or target is None or target in (-1.0, 0.0):
            return None
        deviation = flow - target
        if deviation < -3:
            return "increase"
        if deviation > 3:
            return "decrease"
        return "stable"

    return ComfortAdvisorySensor(
        coordinator,
        "heating_curve_advice",
        "mdi:chart-bell-curve-cumulative",
        evaluate,
    )


def weather_preheat_advisory(
    hass: Any, coordinator: Any, weather_entity: str, threshold: float
) -> ComfortAdvisorySensor:
    def evaluate(_current: Any) -> str | None:
        state = hass.states.get(weather_entity)
        if state is None or getattr(state, "state", None) in {"unknown", "unavailable"}:
            return None
        temperature = _number(getattr(state, "attributes", {}).get("temperature"))
        if temperature is None:
            temperature = _number(getattr(state, "state", None))
        if temperature is None:
            return None
        return "preheat" if temperature <= threshold else "normal"

    return ComfortAdvisorySensor(
        coordinator,
        "weather_preheat_advice",
        "mdi:weather-partly-snowy-rainy",
        evaluate,
    )
