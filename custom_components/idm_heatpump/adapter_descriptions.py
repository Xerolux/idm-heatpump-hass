"""Home Assistant EntityDescription helpers for IDM register metadata."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfTemperature

from idm_heatpump import RegisterDef

_UNIT_DC_SC_MAP: dict[str, tuple[SensorDeviceClass, SensorStateClass]] = {
    UnitOfEnergy.KILO_WATT_HOUR: (SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    "kWh": (SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    UnitOfPower.KILO_WATT: (SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "kW": (SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    UnitOfTemperature.CELSIUS: (SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "°C": (SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "L/min": (SensorDeviceClass.VOLUME_FLOW_RATE, SensorStateClass.MEASUREMENT),
}

_DC_STATE_CLASS_MAP: dict[SensorDeviceClass, SensorStateClass] = {
    SensorDeviceClass.ENERGY: SensorStateClass.TOTAL_INCREASING,
    SensorDeviceClass.POWER: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.TEMPERATURE: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.HUMIDITY: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.BATTERY: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.VOLUME_FLOW_RATE: SensorStateClass.MEASUREMENT,
}

_BINARY_DC_KEYWORDS: list[tuple[str, BinarySensorDeviceClass]] = [
    ("fault", BinarySensorDeviceClass.PROBLEM),
    ("alarm", BinarySensorDeviceClass.PROBLEM),
    ("störung", BinarySensorDeviceClass.PROBLEM),
    ("lock", BinarySensorDeviceClass.LOCK),
    ("pump", BinarySensorDeviceClass.RUNNING),
    ("compressor", BinarySensorDeviceClass.RUNNING),
    ("demand", BinarySensorDeviceClass.RUNNING),
    ("relay", BinarySensorDeviceClass.RUNNING),
]


def infer_sensor_classes(
    name: str,
    unit: str | None,
) -> tuple[SensorDeviceClass | None, SensorStateClass | None]:
    """Infer sensor device_class and state_class from neutral register metadata."""
    if unit and unit in _UNIT_DC_SC_MAP:
        return _UNIT_DC_SC_MAP[unit]
    if unit == PERCENTAGE:
        name_lower = name.lower()
        if "humidity" in name_lower or "feuchte" in name_lower:
            return SensorDeviceClass.HUMIDITY, SensorStateClass.MEASUREMENT
        if "soc" in name_lower or "battery" in name_lower:
            return SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT
    return None, None


def infer_binary_device_class(name: str) -> BinarySensorDeviceClass | None:
    """Infer BinarySensorDeviceClass from register-name keywords."""
    name_lower = name.lower()
    for keyword, device_class in _BINARY_DC_KEYWORDS:
        if keyword in name_lower:
            return device_class
    return None


def get_icon_for_register(name: str, unit: str | None = None) -> str:
    """Return a suitable icon for a register."""
    name_lower = name.lower()

    if "temp" in name_lower or unit == "°C":
        if "dhw" in name_lower or "warmwasser" in name_lower:
            return "mdi:water-boiler"
        if "cold" in name_lower or "kühl" in name_lower:
            return "mdi:snowflake"
        if "heat_sink" in name_lower or "wärmesenke" in name_lower:
            return "mdi:heat-pump"
        return "mdi:thermometer"
    if "humidity" in name_lower or "feuchte" in name_lower:
        return "mdi:water-percent"
    if any(fragment in name_lower for fragment in ["power", "energy", "consumption", "leistung"]):
        if "thermal" in name_lower:
            return "mdi:heat-wave"
        return "mdi:flash"
    if "soc" in name_lower or "battery" in name_lower:
        return "mdi:battery"
    if "pump" in name_lower:
        return "mdi:pump"
    if "relay" in name_lower:
        return "mdi:toggle-switch"
    if "valve" in name_lower:
        return "mdi:valve"
    if "solar" in name_lower:
        return "mdi:solar-power"
    if "pv" in name_lower:
        return "mdi:solar-panel"
    if "cascade" in name_lower:
        return "mdi:heat-pump-multiple"
    if any(fragment in name_lower for fragment in ["fault", "alarm", "error", "störung"]):
        return "mdi:alert-circle"
    if any(fragment in name_lower for fragment in ["mode", "status", "betriebsart", "demand"]):
        return "mdi:cog"
    if unit and "%" in unit:
        return "mdi:gauge"
    return "mdi:information-outline"


def make_sensor_description(
    reg: RegisterDef,
    meta: dict[str, Any],
    fallback_name: str,
) -> SensorEntityDescription:
    """Create a SensorEntityDescription from a library register plus HA metadata."""
    device_class: SensorDeviceClass | None = meta.get("device_class")
    unit = meta.get("unit") or reg.unit
    if device_class is None:
        device_class, _ = infer_sensor_classes(reg.name, unit)
    state_class = _DC_STATE_CLASS_MAP.get(device_class) if device_class else None
    return SensorEntityDescription(
        key=reg.name,
        name=meta.get("name") or fallback_name,
        native_unit_of_measurement=unit,
        device_class=device_class,
        state_class=state_class,
        icon=meta.get("icon"),
        entity_category=meta.get("entity_category"),
        entity_registry_enabled_default=meta.get("enabled_by_default", True),
    )
