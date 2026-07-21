"""Home Assistant metadata overlays for IDM Heatpump registers.

SENSOR_METADATA and NUMBER_METADATA add the HA presentation layer (device
class, icon, entity category, enabled-by-default) on top of the pure library
RegisterDef objects. Extracted from library_adapter to keep the metadata
tables separate from the generator logic.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory  # type: ignore[attr-defined]

class EntityProfile(StrEnum):
    """User-facing profile for default entity presentation."""

    BASIC = "basic"
    ADVANCED = "advanced"
    DIAGNOSTIC_EXPERT = "diagnostic_expert"


SENSOR_METADATA: dict[str, dict[str, Any]] = {
    # Core installation measurements. These belong on the main device page and
    # must not be hidden in Home Assistant's diagnostic section.
    "outdoor_temp": {
        "name": "Außentemperatur",
        "icon": "mdi:thermometer",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
    },
    "storage_temp": {
        "name": "Speichertemperatur",
        "icon": "mdi:storage-tank",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
    },
    "dhw_temp_bottom": {
        "name": "Warmwasser unten",
        "icon": "mdi:water-thermometer",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
    },
    "dhw_temp_top": {
        "name": "Warmwasser oben",
        "icon": "mdi:water-thermometer",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
    },
    "hp_flow_temp": {
        "name": "Wärmepumpe Vorlauf",
        "icon": "mdi:thermometer-chevron-up",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
    },
    "hp_return_temp": {
        "name": "Wärmepumpe Rücklauf",
        "icon": "mdi:thermometer-chevron-down",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
    },
    "heat_source_inlet_temp": {
        "name": "Wärmequelle Eintritt",
        "icon": "mdi:thermometer-water",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
    },
    "heat_source_outlet_temp": {
        "name": "Wärmequelle Austritt",
        "icon": "mdi:thermometer-water",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
    },
    "energy_heating": {
        "name": "Wärmemenge Heizen",
        "icon": "mdi:radiator",
    },
    "energy_dhw": {
        "name": "Wärmemenge Warmwasser",
        "icon": "mdi:water-boiler",
    },
    "energy_cooling": {
        "name": "Wärmemenge Kühlen",
        "icon": "mdi:snowflake",
    },
    "energy_total": {
        "name": "Wärmemenge Gesamt",
        "icon": "mdi:heat-pump",
    },
    "internal_message": {
        "name": "Interne Meldung",
        "icon": "mdi:message-alert",
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    # Heat sink / Trennwärmetauscher (Navigator 10 highlight)
    "heat_sink_flow_rate": {
        "name": "Durchfluss Wärmesenke (B2)",
        "icon": "mdi:water-pump",
        "unit": "l/min",
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "heat_sink_flow_temp": {
        "name": "Vorlauftemperatur Wärmesenke (B125)",
        "icon": "mdi:thermometer",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "heat_sink_return_temp": {
        "name": "Rücklauftemperatur Wärmesenke (B124)",
        "icon": "mdi:thermometer-chevron-down",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "heat_sink_charging_pump_signal": {
        "name": "Steuersignal Ladepumpe Wärmesenke (M73)",
        "icon": "mdi:pump",
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "enabled_by_default": False,
    },
    # Booster
    "booster_fault": {
        "name": "Booster Störung",
        "icon": "mdi:alert",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "booster_a_compressor": {
        "name": "Booster A Verdichter",
        "icon": "mdi:engine",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "enabled_by_default": False,
    },
    "booster_b_compressor": {
        "name": "Booster B Verdichter",
        "icon": "mdi:engine",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "enabled_by_default": False,
    },
}


NUMBER_METADATA: dict[str, dict[str, Any]] = {
    "power_limit_hp": {
        "name": "Leistungsbegrenzung Wärmepumpe",
        "icon": "mdi:flash-alert",
        "entity_category": EntityCategory.CONFIG,
        "enabled_by_default": False,
        "min": -1,
        "max": 50,
        "step": 0.1,
        "unit": UnitOfPower.KILO_WATT,
        "device_class": NumberDeviceClass.POWER,
    },
    "power_limit_cascade": {
        "name": "Leistungsbegrenzung Kaskade",
        "icon": "mdi:flash-alert",
        "entity_category": EntityCategory.CONFIG,
        "enabled_by_default": False,
        "min": -1,
        "max": 200,
        "step": 0.1,
        "unit": UnitOfPower.KILO_WATT,
        "device_class": NumberDeviceClass.POWER,
    },
}


_EXPERT_DISABLED_PREFIXES: tuple[str, ...] = (
    "booster_",
    "cascade_",
)
_EXPERT_DISABLED_FRAGMENTS: tuple[str, ...] = (
    "charging_pump_signal",
    "pump_signal",
    "_pump_",
    "_valve",
    "valve_",
    "_relay",
    "_raw",
    "raw_",
    "_stage",
    "stage_",
    "service",
)


def entity_enabled_by_default(register_name: str, *, default: bool = True) -> bool:
    """Return the safe default entity-registry state for generated descriptions.

    Explicit metadata in the tables above still wins for user-facing core
    measurements. This helper only provides a conservative profile for generated
    entities where we otherwise would expose every optional technical value by
    default.
    """
    if not default:
        return False

    normalized = register_name.casefold()
    if normalized.startswith(_EXPERT_DISABLED_PREFIXES):
        return False
    return not any(fragment in normalized for fragment in _EXPERT_DISABLED_FRAGMENTS)


def _metadata_category(meta: dict[str, Any] | None) -> str | None:
    if not meta:
        return None
    category = meta.get("entity_category")
    if category is None:
        return None
    value = getattr(category, "value", category)
    return str(value).casefold()


def entity_profile(register_name: str, meta: dict[str, Any] | None = None, *, default: bool = True) -> EntityProfile:
    """Return the presentation profile for an explicit or generated entity."""
    if meta:
        if meta.get("enabled_by_default") is False:
            return EntityProfile.DIAGNOSTIC_EXPERT
        category = _metadata_category(meta)
        if category in {"diagnostic", "config"}:
            return EntityProfile.ADVANCED
        return EntityProfile.BASIC

    if not entity_enabled_by_default(register_name, default=default):
        return EntityProfile.DIAGNOSTIC_EXPERT
    return EntityProfile.BASIC
