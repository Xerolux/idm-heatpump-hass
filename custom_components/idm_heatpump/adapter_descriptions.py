"""Home Assistant EntityDescription helpers for IDM register metadata."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfTemperature

from idm_heatpump import RegisterDef

from .adapter_metadata import entity_enabled_by_default
from .binary_semantics import infer_binary_device_class as infer_binary_device_class  # noqa: PLC0414

# Compatibility export used by tests and downstream consumers that inspect the
# legacy keyword table. Actual inference lives in binary_semantics and prefers
# explicit idm-heatpump-api metadata before falling back to these semantics.
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

_UNIT_DC_SC_MAP: dict[str, tuple[SensorDeviceClass, SensorStateClass]] = {
    UnitOfEnergy.KILO_WATT_HOUR: (
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "kWh": (SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    UnitOfPower.KILO_WATT: (SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "kW": (SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    UnitOfTemperature.CELSIUS: (
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
    ),
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

_UNIT_PRECISION_MAP: dict[str, int] = {
    UnitOfTemperature.CELSIUS: 1,
    "°C": 1,
    UnitOfPower.KILO_WATT: 2,
    "kW": 2,
    "W": 0,
    UnitOfEnergy.KILO_WATT_HOUR: 1,
    "kWh": 1,
    "L/min": 1,
    PERCENTAGE: 0,
    "bar": 2,
    "V": 1,
    "h": 0,
}


def infer_suggested_display_precision(unit: str | None) -> int | None:
    """Return suggested display precision for a given unit string."""
    if unit is None:
        return None
    return _UNIT_PRECISION_MAP.get(unit)


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
    # Explicit ``enabled_by_default`` metadata wins for user-facing core
    # measurements. When the key is absent, fall back to the conservative
    # generated profile so rare technical registers stay disabled by default
    # even when they reach this path with an (incomplete) metadata dict.
    if "enabled_by_default" in meta:
        enabled_default = bool(meta["enabled_by_default"])
    else:
        enabled_default = entity_enabled_by_default(reg.name)

    return SensorEntityDescription(
        key=reg.name,
        name=meta.get("name") or fallback_name,
        native_unit_of_measurement=unit,
        device_class=device_class,
        state_class=state_class,
        suggested_display_precision=infer_suggested_display_precision(unit),
        icon=meta.get("icon"),
        entity_category=meta.get("entity_category"),
        entity_registry_enabled_default=enabled_default,
    )
