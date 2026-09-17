"""Read-only weather and heating-curve recommendations."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory

from .entity import IdmCoordinatorEntityBase, build_entity_unique_id

_LOGGER = logging.getLogger(__name__)


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
        result: str | None = self._evaluator(self.coordinator)
        return result

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


class WeatherForecastAdvisorySensor(ComfortAdvisorySensor):
    """Read actual hourly forecasts through the selected HA weather entity."""

    def __init__(self, hass: Any, coordinator: Any, weather_entity: str, threshold: float) -> None:
        self._hass = hass
        self._weather_entity = weather_entity
        self._threshold = threshold
        self._recommendation: str | None = None
        self._forecast_task: asyncio.Task[None] | None = None
        super().__init__(
            coordinator, "weather_preheat_advice", "mdi:weather-partly-snowy-rainy", lambda _: self._recommendation
        )

    async def async_refresh_forecast(self, *, now: datetime | None = None) -> None:
        """Fail closed if the provider has no usable forecast for six hours."""
        try:
            result = await self._hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": self._weather_entity, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
        except Exception:
            _LOGGER.warning("IDM weather forecast is unavailable", exc_info=True)
            self._recommendation = None
            return
        item = result.get(self._weather_entity) if isinstance(result, Mapping) else None
        forecast = item.get("forecast") if isinstance(item, Mapping) else None
        if not isinstance(forecast, list):
            self._recommendation = None
            return
        current = (now or datetime.now(UTC)).astimezone(UTC)
        horizon = current + timedelta(hours=6)
        temperatures: list[float] = []
        for entry in forecast:
            if not isinstance(entry, Mapping):
                continue
            try:
                at = datetime.fromisoformat(str(entry.get("datetime")))
            except ValueError:
                continue
            if at.tzinfo is None:
                continue
            at = at.astimezone(UTC)
            value = _number(entry.get("temperature"))
            if current <= at <= horizon and value is not None:
                temperatures.append(value)
        self._recommendation = (
            ("preheat" if min(temperatures) <= self._threshold else "normal") if temperatures else None
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._forecast_task = self._hass.async_create_task(self._poll_forecast())

    async def async_will_remove_from_hass(self) -> None:
        if self._forecast_task is not None:
            self._forecast_task.cancel()
            try:
                await self._forecast_task
            except asyncio.CancelledError:
                pass
            self._forecast_task = None
        await super().async_will_remove_from_hass()

    async def _poll_forecast(self) -> None:
        while True:
            await self.async_refresh_forecast()
            self.async_write_ha_state()
            await asyncio.sleep(1800)


def weather_preheat_advisory(
    hass: Any, coordinator: Any, weather_entity: str, threshold: float
) -> WeatherForecastAdvisorySensor:
    return WeatherForecastAdvisorySensor(hass, coordinator, weather_entity, threshold)
