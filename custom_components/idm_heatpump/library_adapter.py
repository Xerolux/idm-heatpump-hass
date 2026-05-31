"""Adapter layer between idm_heatpump library and the Home Assistant integration.

This file is the core of the migration (Option B). It allows the HA integration
to use the clean idm_heatpump library as the source of truth for:

- Modbus communication (IdmModbusClient)
- Register definitions (via build_register_map, get_*_registers, etc.)
- Model detection and capabilities

While still providing the rich HA-specific EntityDescriptions (German names,
icons, device classes, categories, etc.) that the current integration uses.

Goal: Over time, move as much logic as possible into the library and keep this
adapter relatively thin.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntityDescription, NumberMode
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory

from idm_heatpump import (
    DataType,
    RegisterDef,
    build_register_map,
    get_heating_circuit_registers,
    get_zone_module_registers,
)

# Note: We import the HA helpers only inside functions to avoid circular imports during early migration.

# Re-export the real client and models from the library
from idm_heatpump import IdmModbusClient as LibIdmModbusClient
from idm_heatpump.const import (
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    MODEL_NAVIGATOR_PRO,
)

# ============================================================
# HA Metadata Overlay
# These dictionaries add the Home Assistant specific presentation
# layer on top of the pure library RegisterDef objects.
# ============================================================


SENSOR_METADATA: dict[str, dict[str, Any]] = {
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
    # Power limitation (writable via numbers, but also useful as sensor)
    "power_limit_hp": {
        "name": "Leistungsbegrenzung Wärmepumpe",
        "icon": "mdi:flash-alert",
        "unit": UnitOfPower.KILO_WATT,
        "device_class": SensorDeviceClass.POWER,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
}


NUMBER_METADATA: dict[str, dict[str, Any]] = {
    "power_limit_hp": {
        "name": "Leistungsbegrenzung Wärmepumpe",
        "icon": "mdi:flash-alert",
        "min": -1,
        "max": 50,
        "step": 0.1,
        "unit": UnitOfPower.KILO_WATT,
        "device_class": NumberDeviceClass.POWER,
    },
    "power_limit_cascade": {
        "name": "Leistungsbegrenzung Kaskade",
        "icon": "mdi:flash-alert",
        "min": -1,
        "max": 200,
        "step": 0.1,
        "unit": UnitOfPower.KILO_WATT,
        "device_class": NumberDeviceClass.POWER,
    },
}


def _make_sensor_description(reg: RegisterDef, meta: dict[str, Any]) -> SensorEntityDescription:
    """Create a rich HA SensorEntityDescription from a library RegisterDef + metadata."""
    return SensorEntityDescription(
        key=reg.name,
        name=meta.get("name", reg.name),
        native_unit_of_measurement=meta.get("unit") or reg.unit,
        device_class=meta.get("device_class"),
        state_class=SensorStateClass.MEASUREMENT if meta.get("device_class") else None,
        icon=meta.get("icon"),
        entity_category=meta.get("entity_category"),
        entity_registry_enabled_default=meta.get("enabled_by_default", True),
    )


def _make_number_description(reg: RegisterDef, meta: dict[str, Any]) -> NumberEntityDescription:
    """Create a rich HA NumberEntityDescription from a library RegisterDef + metadata."""
    return NumberEntityDescription(
        key=reg.name,
        name=meta.get("name", reg.name),
        native_min_value=meta.get("min", reg.min_val or -999),
        native_max_value=meta.get("max", reg.max_val or 999),
        native_step=meta.get("step", 0.1),
        native_unit_of_measurement=meta.get("unit") or reg.unit,
        device_class=meta.get("device_class"),
        icon=meta.get("icon"),
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    )


def get_library_sensors(model_info=None, circuits=None, zone_modules=0) -> list[dict[str, Any]]:
    """
    Returns sensor descriptions primarily sourced from the idm_heatpump library.
    This is intended to become the main source over time.
    """
    reg_map = build_register_map(model_info=model_info, circuits=circuits or [], zone_modules=zone_modules or 0)
    sensors = []

    # Explicitly mapped sensors (best quality)
    for key, meta in SENSOR_METADATA.items():
        if key in reg_map:
            reg = reg_map[key]
            desc = _make_sensor_description(reg, meta)
            sensors.append({
                "register": reg,
                "description": desc,
                "category": "system",
            })

    # Fallback: Generate basic but usable descriptions for everything else from the library
    # This helps during the migration so we don't have to duplicate every register manually.
    known_keys = set(SENSOR_METADATA.keys())
    for name, reg in reg_map.items():
        if name in known_keys:
            continue  # already handled above

        # Skip things that are clearly numbers/writables for now
        if reg.writable:
            continue

        icon = "mdi:thermometer" if reg.unit and "°C" in reg.unit else "mdi:gauge"
        if "power" in name or "energy" in name:
            icon = "mdi:flash"

        desc = SensorEntityDescription(
            key=name,
            name=name.replace("_", " ").title(),
            native_unit_of_measurement=reg.unit,
            device_class=SensorDeviceClass.TEMPERATURE if reg.unit and "°C" in (reg.unit or "") else None,
            icon=icon,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        sensors.append({
            "register": reg,
            "description": desc,
            "category": "library",
        })

    return sensors


def get_library_numbers(model_info=None, circuits=None, zone_modules=0) -> list[dict[str, Any]]:
    """Returns number descriptions for writable library registers with HA metadata."""
    reg_map = build_register_map(model_info=model_info, circuits=circuits, zone_modules=zone_modules)
    numbers = []

    for key, meta in NUMBER_METADATA.items():
        if key in reg_map:
            reg = reg_map[key]
            desc = _make_number_description(reg, meta)
            numbers.append({
                "register": reg,
                "description": desc,
            })

    return numbers


def get_idm_client(host: str, port: int = 502, slave_id: int = 1) -> LibIdmModbusClient:
    """Factory that returns a properly typed client from the library."""
    return LibIdmModbusClient(host=host, port=port, slave_id=slave_id)


__all__ = [
    "LibIdmModbusClient",
    "MODEL_NAVIGATOR_10",
    "MODEL_NAVIGATOR_20",
    "MODEL_NAVIGATOR_PRO",
    "get_library_sensors",
    "get_library_numbers",
    "get_idm_client",
]