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

# ============================================================
# Deutsche Namen für wichtige Register (wird sukzessive erweitert)
# ============================================================

_GERMAN_NAMES: dict[str, str] = {
    # === System ===
    "outdoor_temp": "Außentemperatur",
    "outdoor_temp_avg": "Gemittelte Außentemperatur",
    "storage_temp": "Wärmespeichertemperatur",
    "cold_storage_temp": "Kältespeichertemperatur",
    "dhw_temp_bottom": "Trinkwassererwärmer unten",
    "dhw_temp_top": "Trinkwassererwärmer oben",
    "dhw_tapping_temp": "Warmwasser Zapftemperatur",
    "dhw_setpoint": "Warmwasser Sollwert",
    "hp_flow_temp": "Wärmepumpen Vorlauftemperatur",
    "hp_return_temp": "Wärmepumpen Rücklauftemperatur",
    "heat_source_inlet_temp": "Wärmequelleneintritt",
    "heat_source_outlet_temp": "Wärmequellenaustritt",
    "current_power": "Thermische Momentanleistung",
    "power_consumption_hp": "Elektrische Leistungsaufnahme Wärmepumpe",
    "evu_lock": "EVU Sperre",
    "hp_sum_alarm": "Summenstörung",
    
    # === Heat Sink / Trennwärmetauscher (Navigator 10) ===
    "heat_sink_flow_rate": "Durchfluss Wärmesenke (B2)",
    "heat_sink_flow_temp": "Vorlauftemperatur Wärmesenke",
    "heat_sink_return_temp": "Rücklauftemperatur Wärmesenke",
    "heat_sink_charging_pump_signal": "Ladepumpe Wärmesenke",
    
    # === Pumpen Status ===
    "charge_pump_status": "Ladepumpe",
    "brine_pump_status": "Sole-/Zwischenkreispumpe",
    "source_pump_status": "Wärmequellenpumpe",
    "isc_cold_pump_status": "ISC Kältespeicherpumpe",
    "isc_recool_pump_status": "ISC Rückkühlpumpe",
    "circulation_pump_status": "Zirkulationspumpe",
    
    # === Ventile ===
    "valve_hc_heat_cool": "Umschaltventil Heizkreis Heizen/Kühlen",
    "valve_storage_heat_cool": "Umschaltventil Speicher Heizen/Kühlen",
    "valve_heat_dhw": "Umschaltventil Heizen/Warmwasser",
    
    # === Solar ===
    "solar_collector_temp": "Solar Kollektortemperatur",
    "solar_return_temp": "Solar Rücklauftemperatur",
    "solar_charging_temp": "Solar Ladetemperatur",
    "solar_mode": "Solar Betriebsart",
    
    # === PV / Smartfox ===
    "pv_surplus": "PV Überschuss",
    "pv_production": "PV Produktion",
    "house_consumption": "Hausverbrauch",
    "battery_discharge": "Batterie Entladung",
    "battery_soc": "Batterie SOC",
    "electric_heater_power": "E-Heizstab Leistung",
    
    # === Cascade ===
    "cascade_available_heating": "Kaskade verfügbar Heizen",
    "cascade_available_cooling": "Kaskade verfügbar Kühlen",
    "cascade_available_dhw": "Kaskade verfügbar Warmwasser",
    "cascade_running_heating": "Kaskade in Betrieb Heizen",
    "cascade_running_cooling": "Kaskade in Betrieb Kühlen",
    "cascade_running_dhw": "Kaskade in Betrieb Warmwasser",
    
    # === Energie ===
    "energy_heating": "Wärmemenge Heizen",
    "energy_cooling": "Wärmemenge Kühlen",
    "energy_dhw": "Wärmemenge Warmwasser",
    "energy_total": "Wärmemenge Gesamt",
    "energy_defrost": "Wärmemenge Abtauen",
    "energy_solar": "Wärmemenge Solar",
    "energy_electric_heater": "Wärmemenge E-Heizstab",
    
    # === GLT / Externe Ansteuerung ===
    "ext_outdoor_temp": "Externe Außentemperatur (GLT)",
    "ext_humidity": "Externe Feuchte (GLT)",
    "glt_temp_demand_heating": "GLT Temperaturanforderung Heizen",
    "glt_temp_demand_cooling": "GLT Temperaturanforderung Kühlen",
    
    # === Sonstiges ===
    "bivalence_state": "Bivalenz Betriebszustand",
    "smart_grid_status": "Smart Grid Status",
    "internal_message": "Interne Meldung",
    "hp_operating_mode": "Wärmepumpen Betriebsart",
    "heating_demand": "Heizanforderung",
    "cooling_demand": "Kühlanforderung",
    "dhw_demand": "Warmwasseranforderung",
    "compressor_status_1": "Verdichter 1",
    "compressor_status_2": "Verdichter 2",
    "compressor_status_3": "Verdichter 3",
    "compressor_status_4": "Verdichter 4",
    "valve_solar_heat_dhw": "Solar Umschaltventil Heizen/WW",
    "valve_heat_source_heat_cool": "Wärmequelle Umschaltventil",
    "bivalence_point_1_2nd_gen": "Bivalenzpunkt 1 (2. WE)",
    "bivalence_point_2_2nd_gen": "Bivalenzpunkt 2 (2. WE)",
    "glt_heat_storage_temp": "GLT Wärmespeichertemperatur",
    "glt_cold_storage_temp": "GLT Kältespeichertemperatur",
    "glt_dhw_temp_bottom": "GLT Warmwasser unten",
    "glt_dhw_temp_top": "GLT Warmwasser oben",
    "demand_heating": "Externe Heizanforderung",
    "demand_cooling": "Externe Kühlanforderung",
    "demand_dhw_charging": "Externe WW-Ladeanforderung",
    "total_heat_energy": "Gesamte Wärmemenge (Vortex)",
    "thermal_power_flow_sensor": "Thermische Leistung (Durchflusssensor)",
    "air_intake_temp": "Luftansaugtemperatur",
    "air_heat_exchanger_temp": "Luftwärmetauscher Temperatur",
    "charging_sensor_temp": "Ladefühler Temperatur",
    "ext_demand_temp_heating": "Externe Anforderungstemperatur Heizen",
    "ext_demand_temp_cooling": "Externe Anforderungstemperatur Kühlen",
}

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


def _get_german_name(name: str) -> str:
    """Liefert einen schönen deutschen Namen, falls bekannt, sonst eine formatierte Version."""
    if name in _GERMAN_NAMES:
        return _GERMAN_NAMES[name]
    return name.replace("_", " ").title()


def _make_sensor_description(reg: RegisterDef, meta: dict[str, Any]) -> SensorEntityDescription:
    """Create a rich HA SensorEntityDescription from a library RegisterDef + metadata."""
    german_name = meta.get("name") or _get_german_name(reg.name)
    
    return SensorEntityDescription(
        key=reg.name,
        name=german_name,
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


def get_library_system_sensors() -> list[dict[str, Any]]:
    """Generiert wichtige System-Sensoren direkt aus der Library mit guten deutschen Namen."""
    # This can be expanded further. For now it relies on the general logic + German names.
    return []


# ============================================================
# Spezialisierte Generatoren für Heizkreise und Zonen (stark verbessert)
# ============================================================

def get_library_heating_circuit_sensors(circuit: str) -> list[dict[str, Any]]:
    """Erzeugt Sensor-Beschreibungen für einen Heizkreis direkt aus der Library."""
    try:
        circuit_regs = get_heating_circuit_registers(circuit)
    except Exception:
        return []

    sensors = []
    for name, reg in circuit_regs.items():
        if reg.writable:
            continue

        desc = SensorEntityDescription(
            key=name,
            name=_get_german_name(name),
            native_unit_of_measurement=reg.unit,
            device_class=SensorDeviceClass.TEMPERATURE if reg.unit and "°C" in reg.unit else None,
            icon="mdi:thermometer" if "temp" in name else "mdi:thermostat",
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        sensors.append({
            "register": reg,
            "description": desc,
            "category": f"heating_circuit_{circuit.lower()}",
        })
    return sensors


def get_library_zone_sensors(zone_idx: int, room_count: int = 6) -> list[dict[str, Any]]:
    """Erzeugt Sensor-Beschreibungen für ein Zonenmodul direkt aus der Library."""
    try:
        zone_regs = get_zone_module_registers(zone_idx, room_count)
    except Exception:
        return []

    sensors = []
    for name, reg in zone_regs.items():
        if reg.writable:
            continue

        icon = "mdi:thermometer" if "temp" in name else "mdi:water-percent"
        desc = SensorEntityDescription(
            key=name,
            name=_get_german_name(name),
            native_unit_of_measurement=reg.unit,
            device_class=SensorDeviceClass.TEMPERATURE if "temp" in name else None,
            icon=icon,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        sensors.append({
            "register": reg,
            "description": desc,
            "category": f"zone_{zone_idx}",
        })
    return sensors


def get_library_readonly_sensors(model_info=None, circuits=None, zone_modules=0) -> list[dict[str, Any]]:
    """
    Gibt nur lesbare Sensoren aus der Library zurück.
    Diese Funktion ist der bevorzugte Weg, um Sensoren aus der Library zu bekommen.
    """
    reg_map = build_register_map(model_info=model_info, circuits=circuits or [], zone_modules=zone_modules or 0)
    sensors = []

    for name, reg in reg_map.items():
        if reg.writable:
            continue

        # Bevorzuge explizite Metadaten
        if name in SENSOR_METADATA:
            meta = SENSOR_METADATA[name]
            desc = _make_sensor_description(reg, meta)
            sensors.append({"register": reg, "description": desc, "category": "system"})
            continue

        # Ansonsten generiere vernünftige Defaults
        icon = "mdi:thermometer" if (reg.unit and "°C" in reg.unit) else "mdi:gauge"
        if any(x in name for x in ["power", "energy", "consumption"]):
            icon = "mdi:flash"

        desc = SensorEntityDescription(
            key=name,
            name=_get_german_name(name),
            native_unit_of_measurement=reg.unit,
            device_class=SensorDeviceClass.TEMPERATURE if (reg.unit and "°C" in reg.unit) else None,
            icon=icon,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        sensors.append({"register": reg, "description": desc, "category": "library"})

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