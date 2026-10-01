"""Home Assistant entities for the Navigator 10 system controllers.

The performance page, weather tile, iON status and energy-flow widget of the
shipped frontend are backed by four read-only WebSocket controllers
(``system.heatpump.performance``, ``weather``, ``ion``, ``energyflow``);
this module exposes their frames as Home Assistant entities. Every entity
reports unavailable until its frame has landed, instead of being absent from
the device until the next reload.
"""

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
    SensorStateClass,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory  # type: ignore[attr-defined]

from idm_heatpump import (
    IdmWebEnergyflow,
    IdmWebIon,
    IdmWebPerformance,
    IdmWebWeatherDetail,
)

from .coordinator import IdmCoordinator
from .device_hierarchy import build_subdevice_info
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id
from .ha_compat import BinarySensorDeviceClass
from .web_data import IdmWebSupplement


def _nav10_supplement(coordinator: IdmCoordinator) -> IdmWebSupplement | None:
    """Return the web supplement when it speaks the Navigator 10 protocol."""
    supplement = coordinator.web_supplement
    if supplement is None or supplement.web_variant != "nav10":
        return None
    return supplement


def _frame(coordinator: IdmCoordinator, attr: str) -> Any | None:
    """Return a system frame of the Navigator 10 supplement if it has landed."""
    supplement = _nav10_supplement(coordinator)
    if supplement is None:
        return None
    return getattr(supplement, attr, None)


def _performance(coordinator: IdmCoordinator) -> IdmWebPerformance | None:
    frame = _frame(coordinator, "performance")
    return frame if isinstance(frame, IdmWebPerformance) else None


def _weather(coordinator: IdmCoordinator) -> IdmWebWeatherDetail | None:
    frame = _frame(coordinator, "weather")
    return frame if isinstance(frame, IdmWebWeatherDetail) else None


def _ion(coordinator: IdmCoordinator) -> IdmWebIon | None:
    frame = _frame(coordinator, "ion")
    return frame if isinstance(frame, IdmWebIon) else None


def _energyflow(coordinator: IdmCoordinator) -> IdmWebEnergyflow | None:
    frame = _frame(coordinator, "energyflow")
    return frame if isinstance(frame, IdmWebEnergyflow) else None


def web_system_sensor_entities(
    coordinator: IdmCoordinator,
) -> list[WebSystemSensorEntity]:
    """Create the system-controller sensors for a Navigator 10 web supplement."""
    if _nav10_supplement(coordinator) is None:
        return []
    return [
        IdmWebPowerConsumptionSensor(coordinator),
        IdmWebEnvironmentPowerSensor(coordinator),
        IdmWebEnergyflowGridSensor(coordinator),
        IdmWebEnergyflowPvSensor(coordinator),
        IdmWebWeatherForecastSensor(coordinator),
    ]


def web_system_binary_entities(
    coordinator: IdmCoordinator,
) -> list[WebSystemBinaryEntity]:
    """Create the system-controller binary sensors for a Navigator 10 web supplement."""
    if _nav10_supplement(coordinator) is None:
        return []
    return [
        IdmWebHeatingRodBinarySensor(coordinator),
        IdmWebIonActiveBinarySensor(coordinator),
    ]


def _pv_device_info(coordinator: IdmCoordinator, entity_key: str) -> DeviceInfo | None:
    """Place an energy entity on the PV subdevice when the hierarchy is enabled."""
    if subdevice := build_subdevice_info(coordinator, entity_key):
        return subdevice
    return None


class IdmWebPowerConsumptionSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Heat pump electrical power from the performance page."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = "kW"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "web_hp_power_consumption")
        self.entity_description = SensorEntityDescription(
            key="web_hp_power_consumption",
            translation_key="web_hp_power_consumption",
        )

    @property
    def native_value(self) -> float | None:
        performance = _performance(self.coordinator)
        return performance.consumption_power if performance else None

    @property
    def available(self) -> bool:
        return super().available and _performance(self.coordinator) is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        performance = _performance(self.coordinator)
        if performance is None:
            return {}
        return {
            "performance_mode": performance.mode,
            "system_mode": performance.system_mode,
            "consumption_source": performance.consumption_source,
            "consumption_battery": performance.consumption_battery,
            "production_flow_temperature": performance.production_flow_temperature,
        }


class IdmWebEnvironmentPowerSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Source-side (environment) power from the performance page."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = "kW"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "web_hp_power_environment")
        self.entity_description = SensorEntityDescription(
            key="web_hp_power_environment",
            translation_key="web_hp_power_environment",
        )

    @property
    def native_value(self) -> float | None:
        performance = _performance(self.coordinator)
        return performance.environment_power if performance else None

    @property
    def available(self) -> bool:
        return super().available and _performance(self.coordinator) is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        performance = _performance(self.coordinator)
        if performance is None:
            return {}
        return {
            "environment_source": performance.environment_source,
            "environment_temperature_in": performance.environment_temperature_in,
        }


def _energyflow_attributes(flow: IdmWebEnergyflow | None) -> dict[str, Any]:
    if flow is None:
        return {}
    attributes: dict[str, Any] = {
        "signal": flow.signal,
        "type": flow.type,
    }
    if flow.house_power is not None:
        attributes["house_power"] = flow.house_power
    return attributes


class IdmWebEnergyflowGridSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Grid power of the energy-flow widget."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = "kW"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "web_energyflow_grid")
        self.entity_description = SensorEntityDescription(
            key="web_energyflow_grid",
            translation_key="web_energyflow_grid",
        )

    @property
    def device_info(self) -> DeviceInfo:
        return _pv_device_info(self.coordinator, "web_energyflow_grid") or super().device_info

    @property
    def native_value(self) -> float | None:
        flow = _energyflow(self.coordinator)
        return flow.grid_power if flow else None

    @property
    def available(self) -> bool:
        return super().available and _energyflow(self.coordinator) is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _energyflow_attributes(_energyflow(self.coordinator))


class IdmWebEnergyflowPvSensor(IdmCoordinatorEntityBase, SensorEntity):
    """PV power of the energy-flow widget."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = "kW"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "web_energyflow_pv")
        self.entity_description = SensorEntityDescription(
            key="web_energyflow_pv",
            translation_key="web_energyflow_pv",
        )

    @property
    def device_info(self) -> DeviceInfo:
        return _pv_device_info(self.coordinator, "web_energyflow_pv") or super().device_info

    @property
    def native_value(self) -> float | None:
        flow = _energyflow(self.coordinator)
        return flow.pv_power if flow else None

    @property
    def available(self) -> bool:
        return super().available and _energyflow(self.coordinator) is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _energyflow_attributes(_energyflow(self.coordinator))


def _weather_day_attributes(day: Any) -> dict[str, Any]:
    return {
        "date": day.date,
        "day_of_week": day.day_of_week,
        "temperature": day.temperature,
        "temperature_min": day.temperature_min,
        "temperature_max": day.temperature_max,
        "temperature_avg_label": day.temperature_avg_label,
        "cloud_cover": day.cloud_cover,
        "rain_probability": day.rain_probability,
        "sun_seconds": day.sun_seconds,
        "symbol": day.symbol,
        "wind_speed_min": day.wind_speed_min,
        "wind_speed_max": day.wind_speed_max,
    }


class IdmWebWeatherForecastSensor(IdmCoordinatorEntityBase, SensorEntity):
    """The controller's own weather forecast (myiDM service), today plus days.

    The state is today's actual temperature; the attributes carry today and
    each forecast day in full so templates and automations can consume the
    complete forecast without another integration.
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "web_weather_forecast")
        self.entity_description = SensorEntityDescription(
            key="web_weather_forecast",
            translation_key="web_weather_forecast",
            icon="mdi:weather-partly-snowy-rainy",
        )

    @property
    def native_value(self) -> float | None:
        weather = _weather(self.coordinator)
        if weather is None or weather.today is None:
            return None
        return weather.today.temperature

    @property
    def available(self) -> bool:
        return super().available and _weather(self.coordinator) is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        weather = _weather(self.coordinator)
        if weather is None:
            return {}
        attributes: dict[str, Any] = {}
        if weather.today is not None:
            attributes["today"] = _weather_day_attributes(weather.today)
        attributes["forecast"] = [_weather_day_attributes(day) for day in weather.forecasts]
        return attributes


class IdmWebHeatingRodBinarySensor(IdmCoordinatorEntityBase, BinarySensorEntity):
    """Heating-rod state of the performance page."""

    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "web_hp_heating_rod")
        self.entity_description = BinarySensorEntityDescription(
            key="web_hp_heating_rod",
            translation_key="web_hp_heating_rod",
        )

    @property
    def is_on(self) -> bool | None:
        performance = _performance(self.coordinator)
        return performance.heating_rod if performance else None

    @property
    def available(self) -> bool:
        return super().available and _performance(self.coordinator) is not None


class IdmWebIonActiveBinarySensor(IdmCoordinatorEntityBase, BinarySensorEntity):
    """Whether the iON cloud energy optimization is steering the plant."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "web_ion_active")
        self.entity_description = BinarySensorEntityDescription(
            key="web_ion_active",
            translation_key="web_ion_active",
            icon="mdi:cloud-cog",
        )

    @property
    def is_on(self) -> bool | None:
        ion = _ion(self.coordinator)
        return ion.active if ion else None

    @property
    def available(self) -> bool:
        return super().available and _ion(self.coordinator) is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ion = _ion(self.coordinator)
        if ion is None:
            return {}
        return {
            "enabled_setting_id": ion.enabled_setting_id,
            "enabled_value": ion.enabled_value,
            "subscription_status": ion.subscription_status,
        }


WebSystemSensorEntity = (
    IdmWebPowerConsumptionSensor
    | IdmWebEnvironmentPowerSensor
    | IdmWebEnergyflowGridSensor
    | IdmWebEnergyflowPvSensor
    | IdmWebWeatherForecastSensor
)
"""Union of the concrete system-controller sensor classes (for platform lists)."""

WebSystemBinaryEntity = IdmWebHeatingRodBinarySensor | IdmWebIonActiveBinarySensor
"""Union of the concrete system-controller binary-sensor classes."""
