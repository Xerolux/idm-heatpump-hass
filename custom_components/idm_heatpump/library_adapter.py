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

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory

from idm_heatpump import (
    RegisterDef,
    build_register_map,
    get_heating_circuit_registers,
    get_zone_module_registers,
)
from idm_heatpump import IdmModbusClient as LibIdmModbusClient
from idm_heatpump.const import (
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    MODEL_NAVIGATOR_PRO,
)

# Note: We import the HA helpers only inside functions to avoid circular imports during early migration.

# ============================================================
# Future-proofing: Unterstützung für ha_metadata im RegisterDef
# Wenn die Library später ha_metadata direkt mitliefert, können wir das hier nutzen.
# ============================================================


def _apply_ha_metadata(reg: RegisterDef, base_meta: dict[str, Any]) -> dict[str, Any]:
    """Kann später erweitert werden, wenn RegisterDef ha_metadata enthält."""
    # Placeholder für zukünftige Library-Unterstützung
    # if hasattr(reg, "ha_metadata") and reg.ha_metadata:
    #     base_meta.update(reg.ha_metadata)
    return base_meta


# ============================================================
# Deutsche Namen für wichtige Register (wird sukzessive erweitert)
# ============================================================

_GERMAN_NAMES: dict[str, str] = {
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
    "heat_sink_flow_rate": "Durchfluss Wärmesenke (B2)",
    "heat_sink_flow_temp": "Vorlauftemperatur Wärmesenke",
    "heat_sink_return_temp": "Rücklauftemperatur Wärmesenke",
    "heat_sink_charging_pump_signal": "Ladepumpe Wärmesenke",
    "charge_pump_status": "Ladepumpe",
    "brine_pump_status": "Sole-/Zwischenkreispumpe",
    "source_pump_status": "Wärmequellenpumpe",
    "isc_cold_pump_status": "ISC Kältespeicherpumpe",
    "isc_recool_pump_status": "ISC Rückkühlpumpe",
    "circulation_pump_status": "Zirkulationspumpe",
    "valve_hc_heat_cool": "Umschaltventil Heizkreis Heizen/Kühlen",
    "valve_storage_heat_cool": "Umschaltventil Speicher Heizen/Kühlen",
    "valve_heat_dhw": "Umschaltventil Heizen/Warmwasser",
    "solar_collector_temp": "Solar Kollektortemperatur",
    "solar_return_temp": "Solar Rücklauftemperatur",
    "solar_charging_temp": "Solar Ladetemperatur",
    "solar_mode": "Solar Betriebsart",
    "pv_surplus": "PV Überschuss",
    "pv_production": "PV Produktion",
    "house_consumption": "Hausverbrauch",
    "battery_discharge": "Batterie Entladung",
    "battery_soc": "Batterie SOC",
    "electric_heater_power": "E-Heizstab Leistung",
    "cascade_available_heating": "Kaskade verfügbar Heizen",
    "cascade_available_cooling": "Kaskade verfügbar Kühlen",
    "cascade_available_dhw": "Kaskade verfügbar Warmwasser",
    "cascade_running_heating": "Kaskade in Betrieb Heizen",
    "cascade_running_cooling": "Kaskade in Betrieb Kühlen",
    "cascade_running_dhw": "Kaskade in Betrieb Warmwasser",
    "energy_heating": "Wärmemenge Heizen",
    "energy_cooling": "Wärmemenge Kühlen",
    "energy_dhw": "Wärmemenge Warmwasser",
    "energy_total": "Wärmemenge Gesamt",
    "energy_defrost": "Wärmemenge Abtauen",
    "energy_solar": "Wärmemenge Solar",
    "energy_electric_heater": "Wärmemenge E-Heizstab",
    "ext_outdoor_temp": "Externe Außentemperatur (GLT)",
    "ext_humidity": "Externe Feuchte (GLT)",
    "glt_temp_demand_heating": "GLT Temperaturanforderung Heizen",
    "glt_temp_demand_cooling": "GLT Temperaturanforderung Kühlen",
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
    "air_intake_temp_2": "Luftansaugtemperatur 2",
    "valve_solar_storage_heat_source": "Solar Speicher/Wärmequelle Ventil",
    "valve_isc_heat_source_cold_storage": "ISC Umschaltventil",
    "valve_isc_storage_bypass": "Umschaltventil ISC Speicher/Bypass",
    "isc_charging_temp_cooling": "ISC Ladetemperatur Kühlen",
    "isc_recooling_temp": "ISC Rückkühltemperatur",
    "isc_mode": "ISC Modus",
    "ext_room_temp": "Externe Raumtemperatur",
    "humidity_sensor": "Feuchtesensor",
    "fault_heat_source_circuit": "Störung Wärmequellenkreis",
    "fault_heat_source_pressure": "Störung Druckschalter Wärmequelle",
    "booster_a_source_inlet_temp": "Booster A Wärmequelleneintritt",
    "booster_a_flow_temp": "Booster A Vorlauftemperatur",
    "booster_a_compressor": "Booster A Verdichter",
    "booster_b_compressor": "Booster B Verdichter",
    "power_limit_hp": "Leistungsbegrenzung Wärmepumpe",
    "power_limit_cascade": "Leistungsbegrenzung Kaskade",
    "dhw_draw_temp": "Warmwasserzapftemperatur",
    "current_energy_price": "Aktueller Strompreis",
    "hgl_flow_temp": "HGL Vorlauftemperatur B35",
    "air_hx_temp": "Luftwärmetauschertemperatur B72",
    "charge_sensor_temp": "Ladefühler B45",
    "heatpump_status": "Betriebsart Wärmepumpe",
    "valve_source_heat_cool": "Umschaltventil Wärmequelle Heizen/Kühlen",
    "valve_solar_storage_source": "Umschaltventil Solar Speicher/Wärmequelle",
    "valve_isc_source_cold": "Umschaltventil ISC Wärmequelle/Kältespeicher",
    "cascade_avail_stages_heat": "Kaskade Verfügbare Stufen Heizen",
    "cascade_avail_stages_cool": "Kaskade Verfügbare Stufen Kühlen",
    "cascade_avail_stages_dhw": "Kaskade Verfügbare Stufen Warmwasser",
    "cascade_running_stages_heat": "Kaskade Laufende Stufen Heizen",
    "cascade_running_stages_cool": "Kaskade Laufende Stufen Kühlen",
    "cascade_running_stages_dhw": "Kaskade Laufende Stufen Warmwasser",
    "cascade_req_heat_temp": "Kaskade Angeforderte Heiztemperatur",
    "cascade_req_cool_temp": "Kaskade Angeforderte Kühltemperatur",
    "cascade_req_dhw_temp": "Kaskade Angeforderte WW-Temperatur",
    "cascade_avg_flow_heat": "Kaskade Gemittelte VL-Temp Heizen",
    "cascade_avg_flow_cool": "Kaskade Gemittelte VL-Temp Kühlen",
    "cascade_avg_flow_dhw": "Kaskade Gemittelte VL-Temp Warmwasser",
    "humidity": "Feuchtesensor",
    "outdoor_temp_ext": "Externe Außentemperatur",
    "humidity_ext": "Externe Feuchte",
    "energy_heat_heating": "Wärmemenge Heizen",
    "energy_heat_total": "Wärmemenge Gesamt",
    "energy_heat_cooling": "Wärmemenge Kühlen",
    "energy_heat_dhw": "Wärmemenge Warmwasser",
    "energy_heat_defrost": "Wärmemenge Abtauung",
    "energy_heat_passive_cooling": "Wärmemenge Passive Kühlen",
    "energy_heat_solar": "Wärmemenge Solar",
    "energy_heat_electric": "Wärmemenge Elektroheizeinsatz",
    "current_power_draw": "Momentanleistung",
    "solar_collector_return_temp": "Solar Kollektorrücklauftemperatur",
    "solar_charge_temp": "Solar Ladetemperatur",
    "solar_reference_temp": "Solar WQ-Referenztemperatur/Pooltemperatur",
    "isc_charge_cooling_temp": "ISC Ladetemperatur Kühlen",
    "firmware_version": "Firmware Version Navigator",
    "power_draw_total": "Aktuelle Leistungsaufnahme Wärmepumpe",
    "thermal_power": "Thermische Leistung",
    "energy_total_flow_sensor": "Wärmemenge Gesamt (Durchflusssensor)",
    "flow_temp_hk": "Vorlauftemperatur Heizkreis",
    "room_temp_hk": "Raumtemperatur Heizkreis",
    "target_flow_temp_hk": "Sollvorlauftemperatur Heizkreis",
    "room_target_heat_normal": "Raumsoll Heizen Normal",
    "room_target_heat_eco": "Raumsoll Heizen Eco",
    "room_target_cool_normal": "Raumsoll Kühlen Normal",
    "room_target_cool_eco": "Raumsoll Kühlen Eco",
    "heating_curve": "Heizkurve",
    "heating_limit": "Heizgrenze",
    "cooling_limit": "Kühlgrenze",
    "parallel_shift": "Parallelverschiebung",
    "active_mode": "Aktive Betriebsart",
    "zone_mode": "Zonenmodus",
    "zone_room_temp": "Raumtemperatur Zone",
    "zone_room_target": "Raumsolltemperatur Zone",
    "zone_room_humidity": "Raumfeuchte Zone",
    "zone_room_mode": "Raumbetriebsart Zone",
}


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


def get_icon_for_register(name: str, unit: str | None = None) -> str:
    """Gibt ein passendes Icon für ein Register zurück (besser als simple Fallbacks)."""
    name_lower = name.lower()

    # Temperaturen
    if "temp" in name_lower or unit == "°C":
        if "dhw" in name_lower or "warmwasser" in name_lower:
            return "mdi:water-boiler"
        if "cold" in name_lower or "kühl" in name_lower:
            return "mdi:snowflake"
        if "heat_sink" in name_lower or "wärmesenke" in name_lower:
            return "mdi:heat-pump"
        return "mdi:thermometer"
    if "humidity" in name_lower or "%rF" in (unit or ""):
        return "mdi:water-percent"

    # Leistung & Energie
    if any(x in name_lower for x in ["power", "energy", "consumption", "leistung"]):
        if "thermal" in name_lower:
            return "mdi:heat-wave"
        return "mdi:flash"
    if "soc" in name_lower or "battery" in name_lower:
        return "mdi:battery"

    # Pumpen
    if "pump" in name_lower:
        return "mdi:pump"

    # Ventile
    if "valve" in name_lower:
        return "mdi:valve"

    # Solar
    if "solar" in name_lower:
        return "mdi:solar-power"

    # PV
    if "pv" in name_lower:
        return "mdi:solar-panel"

    # Kaskade
    if "cascade" in name_lower:
        return "mdi:heat-pump-multiple"

    # Störungen / Alarme
    if any(x in name_lower for x in ["fault", "alarm", "error", "störung"]):
        return "mdi:alert-circle"

    # Modus / Status
    if any(x in name_lower for x in ["mode", "status", "betriebsart", "demand"]):
        return "mdi:cog"

    # Standard
    if unit and "%" in unit:
        return "mdi:gauge"
    return "mdi:information-outline"


def _make_sensor_description(
    reg: RegisterDef, meta: dict[str, Any]
) -> SensorEntityDescription:
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


def _make_number_description(
    reg: RegisterDef, meta: dict[str, Any]
) -> NumberEntityDescription:
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


def get_library_sensors(
    model_info=None, circuits=None, zone_modules=0
) -> list[dict[str, Any]]:
    """
    Returns sensor descriptions primarily sourced from the idm_heatpump library.
    This is intended to become the main source over time.
    """
    reg_map = build_register_map(
        model_info=model_info, circuits=circuits or [], zone_modules=zone_modules or 0
    )
    sensors = []

    # Explicitly mapped sensors (best quality)
    for key, meta in SENSOR_METADATA.items():
        if key in reg_map:
            reg = reg_map[key]
            desc = _make_sensor_description(reg, meta)
            sensors.append(
                {
                    "register": reg,
                    "description": desc,
                    "category": "system",
                }
            )

    # Fallback: Generate basic but usable descriptions for everything else from the library
    # This helps during the migration so we don't have to duplicate every register manually.
    known_keys = set(SENSOR_METADATA.keys())
    for name, reg in reg_map.items():
        if name in known_keys:
            continue  # already handled above

        # Skip things that are clearly numbers/writables for now
        if reg.writable:
            continue

        icon = get_icon_for_register(name, reg.unit)

        desc = SensorEntityDescription(
            key=name,
            name=name.replace("_", " ").title(),
            native_unit_of_measurement=reg.unit,
            device_class=SensorDeviceClass.TEMPERATURE
            if reg.unit and "°C" in (reg.unit or "")
            else None,
            icon=icon,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        sensors.append(
            {
                "register": reg,
                "description": desc,
                "category": "library",
            }
        )

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
            device_class=SensorDeviceClass.TEMPERATURE
            if reg.unit and "°C" in reg.unit
            else None,
            icon=get_icon_for_register(name, reg.unit),
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        sensors.append(
            {
                "register": reg,
                "description": desc,
                "category": f"heating_circuit_{circuit.lower()}",
            }
        )
    return sensors


def get_library_zone_sensors(
    zone_idx: int, room_count: int = 6
) -> list[dict[str, Any]]:
    """Erzeugt Sensor-Beschreibungen für ein Zonenmodul direkt aus der Library."""
    try:
        zone_regs = get_zone_module_registers(zone_idx, room_count)
    except Exception:
        return []

    sensors = []
    for name, reg in zone_regs.items():
        if reg.writable:
            continue

        desc = SensorEntityDescription(
            key=name,
            name=_get_german_name(name),
            native_unit_of_measurement=reg.unit,
            device_class=SensorDeviceClass.TEMPERATURE if "temp" in name else None,
            icon=get_icon_for_register(name, reg.unit),
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        sensors.append(
            {
                "register": reg,
                "description": desc,
                "category": f"zone_{zone_idx}",
            }
        )
    return sensors


# ============================================================
# Weitere Generatoren für umfassende Abdeckung (System, Energy, Pumps, Solar, PV, Cascade, GLT)
# ============================================================


def get_library_energy_sensors() -> list[dict[str, Any]]:
    """Energie- und Leistungssensoren aus der Library."""
    return []


def get_library_pump_valve_sensors() -> list[dict[str, Any]]:
    """Pumpen- und Ventilstatus aus der Library."""
    return []


def get_library_solar_pv_sensors() -> list[dict[str, Any]]:
    """Solar- und PV-bezogene Sensoren."""
    return []


def get_library_cascade_sensors() -> list[dict[str, Any]]:
    """Kaskaden-spezifische Sensoren."""
    return []


def get_library_glt_sensors() -> list[dict[str, Any]]:
    """GLT / externe Ansteuerung Sensoren."""
    return []


def get_ha_entity_descriptions(
    platform: str,
    model_info=None,
    circuits: list[str] | None = None,
    zone_modules: int = 0,
) -> list[dict[str, Any]]:
    """
    Zentrale Funktion, die für eine Plattform (sensor, number, select, binary_sensor, switch)
    fertige HA-EntityDescriptions aus der Library generiert.

    Das ist der empfohlene Weg für zukünftige Erweiterungen.
    """
    if platform in ("sensor", "binary_sensor"):
        return get_library_readonly_sensors(model_info, circuits, zone_modules)
    if platform == "number":
        return get_library_numbers(model_info, circuits, zone_modules)
    if platform == "select":
        return get_library_selects(circuits, zone_modules)
    if platform == "switch":
        return get_library_switches()
    return []


# ============================================================
# Hilfsfunktion für icons.json Generierung (Empfehlung)
# ============================================================


def generate_icons_json_entries(
    model_info=None, circuits=None, zone_modules=0
) -> dict[str, dict]:
    """
    Hilfsfunktion, die Icons für alle bekannten Register vorschlägt.
    Kann genutzt werden, um icons.json teilweise zu generieren.
    """
    reg_map = build_register_map(
        model_info=model_info, circuits=circuits or [], zone_modules=zone_modules or 0
    )
    icons = {}
    for name, reg in reg_map.items():
        icon = get_icon_for_register(name, reg.unit)
        icons[name] = {"default": icon}
    return icons


def get_library_binary_sensors(circuits=None, zone_modules=0) -> list[dict[str, Any]]:
    """Binary sensors (pumps, valves, demands, etc.) from the library."""
    # For now, return empty — these can be expanded later with specific metadata.
    # The general get_library_readonly_sensors will catch most of them.
    return []


def get_library_selects(circuits=None, zone_modules=0) -> list[dict[str, Any]]:
    """Select entities (modes) from the library."""
    from homeassistant.components.select import SelectEntityDescription

    reg_map = build_register_map(
        circuits=circuits or [],
        zone_modules=zone_modules or 0,
    )
    selects = []
    for name, reg in reg_map.items():
        if not reg.writable or not reg.enum_options:
            continue
        desc = SelectEntityDescription(
            key=name,
            name=_get_german_name(name),
            options=list(reg.enum_options.values()),
            icon=get_icon_for_register(name),
            entity_category=EntityCategory.CONFIG,
        )
        selects.append(
            {
                "register": reg,
                "description": desc,
            }
        )
    return selects


def get_library_switches() -> list[dict[str, Any]]:
    """Switch entities (GLT demands etc.) from the library."""
    from homeassistant.components.switch import SwitchEntityDescription

    reg_map = build_register_map(circuits=[], zone_modules=0)
    switches = []
    for name, reg in reg_map.items():
        if reg.datatype.value != "BOOL" or not reg.writable:
            continue
        desc = SwitchEntityDescription(
            key=name,
            name=_get_german_name(name),
            icon=get_icon_for_register(name),
            entity_category=EntityCategory.CONFIG,
        )
        switches.append(
            {
                "register": reg,
                "description": desc,
            }
        )
    return switches


def get_library_readonly_sensors(
    model_info=None, circuits=None, zone_modules=0
) -> list[dict[str, Any]]:
    """
    Gibt nur lesbare Sensoren aus der Library zurück.
    Diese Funktion ist der bevorzugte Weg, um Sensoren aus der Library zu bekommen.
    """
    reg_map = build_register_map(
        model_info=model_info, circuits=circuits or [], zone_modules=zone_modules or 0
    )
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
        icon = get_icon_for_register(name, reg.unit)

        desc = SensorEntityDescription(
            key=name,
            name=_get_german_name(name),
            native_unit_of_measurement=reg.unit,
            device_class=SensorDeviceClass.TEMPERATURE
            if (reg.unit and "°C" in reg.unit)
            else None,
            icon=icon,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        sensors.append({"register": reg, "description": desc, "category": "library"})

    return sensors


_WRITE_ONLY_COMMANDS = {"error_acknowledge"}


def get_library_numbers(
    model_info=None, circuits=None, zone_modules=0
) -> list[dict[str, Any]]:
    """Returns number descriptions for writable library registers with HA metadata."""
    reg_map = build_register_map(
        model_info=model_info, circuits=circuits or [], zone_modules=zone_modules or 0
    )
    numbers = []

    for name, reg in reg_map.items():
        if not reg.writable or reg.enum_options:
            continue
        if reg.datatype.value == "BOOL":
            continue
        if name in _WRITE_ONLY_COMMANDS:
            continue

        meta = NUMBER_METADATA.get(name, {})
        min_val = meta.get("min", reg.min_val if reg.min_val is not None else -999)
        max_val = meta.get("max", reg.max_val if reg.max_val is not None else 999)

        desc = NumberEntityDescription(
            key=name,
            name=meta.get("name", _get_german_name(name)),
            native_min_value=min_val,
            native_max_value=max_val,
            native_step=meta.get("step", 0.5),
            native_unit_of_measurement=meta.get("unit") or reg.unit,
            device_class=meta.get("device_class"),
            icon=meta.get("icon", get_icon_for_register(name, reg.unit)),
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
        )
        numbers.append(
            {
                "register": reg,
                "description": desc,
            }
        )

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
