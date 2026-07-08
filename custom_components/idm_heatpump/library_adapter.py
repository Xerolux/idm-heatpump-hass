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

import logging
import re
from dataclasses import replace
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
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.helpers.entity import EntityCategory  # type: ignore[attr-defined]

from idm_heatpump import (
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    MODEL_NAVIGATOR_PRO,
    RegisterDef,
    get_heating_circuit_registers,
    get_zone_module_registers as _library_get_zone_module_registers,
)
from idm_heatpump import IdmModbusClient as LibIdmModbusClient

from .adapter_enums import get_bitflag_de_labels, get_slug_map_and_key
from .adapter_descriptions import (
    get_icon_for_register,
    infer_binary_device_class,
    infer_sensor_classes,
    make_sensor_description,
)
from .adapter_glt import is_glt_measurement, is_zone_room_measurement
from .adapter_registers import build_filtered_register_map

_LOGGER = logging.getLogger(__name__)

# Note: We import the HA helpers only inside functions to avoid circular imports during early migration.

_SENSOR_STATE_CLASS_MAP: dict[str, SensorStateClass] = {
    SensorStateClass.MEASUREMENT: SensorStateClass.MEASUREMENT,
    SensorStateClass.TOTAL: SensorStateClass.TOTAL,
    SensorStateClass.TOTAL_INCREASING: SensorStateClass.TOTAL_INCREASING,
}

_ZONE_ROOM_REGISTER = re.compile(r"^(?P<prefix>zm(?P<zone>\d+)_room)(?P<room>\d+)(?P<suffix>_.+)$")


def _coerce_sensor_state_class(value: str | SensorStateClass | None) -> SensorStateClass | None:
    """Map neutral library state class values to Home Assistant's enum."""
    if value is None:
        return None
    return _SENSOR_STATE_CLASS_MAP.get(str(value))


def _clone_register_for_room(reg: RegisterDef, room: int, address: int) -> RegisterDef:
    """Clone a library room register for older 8-room zone modules."""
    match = _ZONE_ROOM_REGISTER.fullmatch(reg.name)
    if match is None:
        msg = f"Register {reg.name!r} is not a zone room register"
        raise ValueError(msg)
    name = f"{match.group('prefix')}{room}{match.group('suffix')}"
    try:
        return replace(reg, address=address, name=name)
    except TypeError:
        return RegisterDef(
            address,
            reg.datatype,
            name,
            unit=reg.unit,
            multiplier=reg.multiplier,
            enum_options=reg.enum_options,
            writable=reg.writable,
            binary=reg.binary,
            write_only=reg.write_only,
            exclude_from_write=reg.exclude_from_write,
            icon=reg.icon,
            min_val=reg.min_val,
            max_val=reg.max_val,
            enabled_by_default=reg.enabled_by_default,
            state_class=reg.state_class,
        )


def _get_zone_module_registers(zone_idx: int, room_count: int = 6) -> dict[str, RegisterDef]:
    """Return zone module registers, extending 6-room library maps to 8 rooms."""
    try:
        return _library_get_zone_module_registers(zone_idx, room_count)
    except ValueError:
        if room_count <= 6:
            raise

    base_regs = _library_get_zone_module_registers(zone_idx, 6)
    extended = dict(base_regs)
    for room in range(7, room_count + 1):
        previous_room = room - 1
        template_room = previous_room - 1
        for reg in list(extended.values()):
            previous_match = _ZONE_ROOM_REGISTER.fullmatch(reg.name)
            if previous_match is None or int(previous_match.group("room")) != previous_room:
                continue
            template_name = f"{previous_match.group('prefix')}{template_room}{previous_match.group('suffix')}"
            template_reg = extended.get(template_name)
            stride = reg.address - template_reg.address if template_reg is not None else 10
            cloned = _clone_register_for_room(reg, room, reg.address + stride)
            extended[cloned.name] = cloned
    return extended


def _get_zone_module_registers_compat(zone_idx: int, room_count: int = 6) -> dict[str, RegisterDef]:
    """Return zone registers, including 8-room modules with older API releases."""
    return _get_zone_module_registers(zone_idx, room_count)


# ============================================================
# Enum slug maps — stable translation keys per register
# ============================================================


# ============================================================
# GLT-Messwert-Register: beschreibbare Register, die physikalische Messwerte
# abbilden (PV-Block, Zonenraum-Temperatur/-Feuchte). Seit Library 0.3.2 sind
# diese laut iDM-Doku per GLT beschreibbar. Sie werden doppelt exponiert:
# als Sensor (Anzeige/Historie) UND als Number (externe Vorgabe).
# ============================================================

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
    "pv_target_value": "PV Zielwert",
    "variable_input": "Variabler Eingang",
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
    # === System mode ===
    "system_mode": "Systembetriebsart",
    "error_acknowledge": "Fehlerquittierung",
    # === Booster detailed ===
    "booster_a_charging_pump": "Booster A Ladepumpe",
    "booster_a_return_temp": "Booster A Rücklauftemperatur",
    "booster_a_source_outlet_temp": "Booster A Wärmequellenaustritt",
    "booster_a_source_pump": "Booster A Wärmequellenpumpe",
    "booster_a_storage_temp": "Booster A Speichertemperatur",
    "booster_b_charging_pump": "Booster B Ladepumpe",
    "booster_b_flow_temp": "Booster B Vorlauftemperatur",
    "booster_b_return_temp": "Booster B Rücklauftemperatur",
    "booster_b_source_inlet_temp": "Booster B Wärmequelleneintritt",
    "booster_b_source_outlet_temp": "Booster B Wärmequellenaustritt",
    "booster_b_source_pump": "Booster B Wärmequellenpumpe",
    "booster_b_storage_temp": "Booster B Speichertemperatur",
    "booster_interlock": "Booster Verriegelung",
    # === Pumpen ===
    "charging_pump_status": "Ladepumpe M73",
    "heat_source_pump_status": "Wärmequellenpumpe M15",
    "circulation_pump": "Zirkulationspumpe M64",
    "isc_cold_storage_pump_status": "ISC Kältespeicherpumpe M84",
    "isc_recooling_pump_status": "ISC Rückkühlpumpe M17",
    # === DHW detail ===
    "dhw_charge_on_temp": "WW Einchargetemperatur",
    "dhw_charge_off_temp": "WW Ausschalttemperatur",
    "current_electricity_price": "Aktueller Strompreis",
    "current_power_solar": "Aktuelle Solarleistung",
    "energy_passive_cooling": "Wärmemenge Passive Kühlung",
    # === Bivalenz 3. Gen ===
    "bivalence_point_1_3rd_gen": "Bivalenzpunkt 1 (3. WE)",
    "bivalence_point_2_3rd_gen": "Bivalenzpunkt 2 (3. WE)",
    # === Fehler / Diagnose ===
    "fault_heat_source_pressure_switch": "Störung Druckschalter Wärmequellenkreis",
    "fault_charging_pump_1_intermediate": "Störung Ladepumpe 1 Zwischenkreis",
    "fault_charging_pump_2_intermediate": "Störung Ladepumpe 2 Zwischenkreis",
    # === Grundwasser ===
    "groundwater_inlet_temp_1": "Grundwassereintrittstemperatur 1",
    "groundwater_inlet_temp_2": "Grundwassereintrittstemperatur 2",
    # === GLT / Extern ===
    "ext_demand_groundwater_pump_m15": "Externe Anforderung Grundwasserpumpe M15",
    "ext_demand_groundwater_pump_m15_sw_max": "Externe Anforderung Grundwasserpumpe M15 (SW max)",
    "demand_onetime_dhw": "Einmalige WW-Anforderung",
    "power_consumption_hp_smartfox": "Elektrische Leistungsaufnahme Smartfox",
    # === Heizkreis A ===
    "hc_a_flow_temp": "Vorlauftemperatur HK A",
    "hc_a_room_temp": "Raumtemperatur HK A",
    "hc_a_setpoint_flow_temp": "Sollvorlauftemperatur HK A",
    "hc_a_active_mode": "Aktive Betriebsart HK A",
    "hc_a_mode": "Betriebsart HK A",
    "hc_a_room_setpoint_heat_normal": "Raumsoll Heizen Normal HK A",
    "hc_a_room_setpoint_heat_eco": "Raumsoll Heizen Eco HK A",
    "hc_a_room_setpoint_cool_normal": "Raumsoll Kühlen Normal HK A",
    "hc_a_room_setpoint_cool_eco": "Raumsoll Kühlen Eco HK A",
    "hc_a_heating_curve": "Heizkurve HK A",
    "hc_a_heating_limit": "Heizgrenze HK A",
    "hc_a_cooling_limit": "Kühlgrenze HK A",
    "hc_a_setpoint_flow_constant": "Festwertvorlauf HK A",
    "hc_a_setpoint_flow_cooling": "Kühlvorlauf HK A",
    "hc_a_parallel_shift": "Parallelverschiebung HK A",
    "hc_a_ext_room_temp": "Externe Raumtemperatur HK A",
    # === Kaskade Detail ===
    "cascade_req_heating_temp": "Kaskade Angeforderte Heiztemperatur",
    "cascade_req_cooling_temp": "Kaskade Angeforderte Kühltemperatur",
    "cascade_avg_flow_heating": "Kaskade Gemittelte VL-Temp Heizen",
    "cascade_avg_flow_cooling": "Kaskade Gemittelte VL-Temp Kühlen",
    "cascade_min_power_heating": "Kaskade Mindestleistung Heizen",
    "cascade_min_power_cooling": "Kaskade Mindestleistung Kühlen",
    "cascade_min_power_dhw": "Kaskade Mindestleistung Warmwasser",
    "cascade_max_power_heating": "Kaskade Maximalleistung Heizen",
    "cascade_max_power_cooling": "Kaskade Maximalleistung Kühlen",
    "cascade_max_power_dhw": "Kaskade Maximalleistung Warmwasser",
    "cascade_bivalence_heating_parallel": "Kaskade Bivalenz Heizen Parallel",
    "cascade_bivalence_heating_alternative": "Kaskade Bivalenz Heizen Alternativ",
    "cascade_bivalence_cooling_parallel": "Kaskade Bivalenz Kühlen Parallel",
    "cascade_bivalence_cooling_alternative": "Kaskade Bivalenz Kühlen Alternativ",
    "cascade_bivalence_dhw_parallel": "Kaskade Bivalenz WW Parallel",
    "cascade_bivalence_dhw_alternative": "Kaskade Bivalenz WW Alternativ",
    # === Solar Detail ===
    "solar_wq_pool_temp": "Solar WQ-Referenztemperatur/Pooltemperatur",
    # === Booster (bereits teilweise vorhanden) ===
    "booster_fault": "Booster Störung",
}


# ============================================================
# HA Metadata Overlay
# These dictionaries add the Home Assistant specific presentation
# layer on top of the pure library RegisterDef objects.
# ============================================================


SENSOR_METADATA: dict[str, dict[str, Any]] = {
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


_ZONE_ROOM_NAME_RE = re.compile(r"zm(\d+)_room(\d+)_(temp|setpoint|humidity|mode|relay)$")

_ZONE_ROOM_NAME_SUFFIX: dict[str, str] = {
    "temp": "Raumtemperatur",
    "setpoint": "Raumsolltemperatur",
    "humidity": "Raumfeuchte",
    "mode": "Raumbetriebsart",
    "relay": "Relais",
}


def _get_german_name(name: str) -> str:
    """Liefert einen schönen deutschen Namen, falls bekannt, sonst eine formatierte Version."""
    if name in _GERMAN_NAMES:
        return _GERMAN_NAMES[name]
    zone_match = _ZONE_ROOM_NAME_RE.match(name)
    if zone_match:
        zone, room, kind = zone_match.groups()
        return f"Zone {zone} Raum {room} {_ZONE_ROOM_NAME_SUFFIX[kind]}"
    return name.replace("_", " ").title()


def get_library_sensors(
    model_info: Any = None,
    circuits: list[str] | None = None,
    zone_modules: int = 0,
    enable_cascade: bool = True,
) -> list[dict[str, Any]]:
    """
    Returns sensor descriptions primarily sourced from the idm_heatpump library.
    This is intended to become the main source over time.
    """
    reg_map = build_filtered_register_map(model_info, circuits, zone_modules)
    sensors = []

    # Explicitly mapped sensors (best quality)
    for key, meta in SENSOR_METADATA.items():
        if key in reg_map:
            reg = reg_map[key]
            desc = make_sensor_description(reg, meta, _get_german_name(reg.name))
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

        if reg.writable and not is_glt_measurement(name):
            continue
        if reg.write_only:
            continue
        if reg.binary:
            continue

        icon = reg.icon or get_icon_for_register(name, reg.unit)
        dc, sc = infer_sensor_classes(name, reg.unit)
        if reg.state_class:
            sc = _coerce_sensor_state_class(reg.state_class)

        # For non-BITFLAG enum sensors with a known slug map, use ENUM device class
        slug_map, t_key = get_slug_map_and_key(name)
        if reg.enum_options and reg.datatype.value != "BITFLAG" and slug_map is not None:
            desc = SensorEntityDescription(
                key=name,
                name=_get_german_name(name),
                device_class=SensorDeviceClass.ENUM,
                options=list(slug_map.values()),
                translation_key=t_key,
                icon=icon,
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=reg.enabled_by_default,
            )
        else:
            desc = SensorEntityDescription(
                key=name,
                name=_get_german_name(name),
                native_unit_of_measurement=reg.unit,
                device_class=dc,
                state_class=sc,
                icon=icon,
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=reg.enabled_by_default,
            )
        sensors.append(
            {
                "register": reg,
                "description": desc,
                "category": "library",
            }
        )

    return sensors


# ============================================================
# Spezialisierte Generatoren für Heizkreise und Zonen (stark verbessert)
# ============================================================


def get_library_heating_circuit_sensors(circuit: str) -> list[dict[str, Any]]:
    """Erzeugt Sensor-Beschreibungen für einen Heizkreis direkt aus der Library."""
    try:
        circuit_regs = get_heating_circuit_registers(circuit)
    except Exception:
        _LOGGER.debug("Failed to load heating circuit %s sensor registers", circuit, exc_info=True)
        return []

    sensors = []
    for name, reg in circuit_regs.items():
        if reg.writable:
            continue

        icon = get_icon_for_register(name, reg.unit)
        slug_map, t_key = get_slug_map_and_key(name)
        if reg.enum_options and reg.datatype.value != "BITFLAG" and slug_map is not None:
            desc = SensorEntityDescription(
                key=name,
                name=_get_german_name(name),
                device_class=SensorDeviceClass.ENUM,
                options=list(slug_map.values()),
                translation_key=t_key,
                icon=icon,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        else:
            hc_dc, hc_sc = infer_sensor_classes(name, reg.unit)
            if reg.state_class:
                hc_sc = _coerce_sensor_state_class(reg.state_class)
            desc = SensorEntityDescription(
                key=name,
                name=_get_german_name(name),
                native_unit_of_measurement=reg.unit,
                device_class=hc_dc,
                state_class=hc_sc,
                icon=icon,
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


def get_library_zone_sensors(zone_idx: int, room_count: int = 6) -> list[dict[str, Any]]:
    """Erzeugt Sensor-Beschreibungen für ein Zonenmodul direkt aus der Library."""
    try:
        zone_regs = _get_zone_module_registers_compat(zone_idx, room_count)
    except Exception:
        _LOGGER.debug("Failed to load zone %d sensor registers", zone_idx, exc_info=True)
        return []

    sensors = []
    for name, reg in zone_regs.items():
        if reg.writable and not is_glt_measurement(name):
            continue

        icon = get_icon_for_register(name, reg.unit)
        slug_map, t_key = get_slug_map_and_key(name)
        if reg.enum_options and reg.datatype.value != "BITFLAG" and slug_map is not None:
            desc = SensorEntityDescription(
                key=name,
                name=_get_german_name(name),
                device_class=SensorDeviceClass.ENUM,
                options=list(slug_map.values()),
                translation_key=t_key,
                icon=icon,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        else:
            z_dc, z_sc = infer_sensor_classes(name, reg.unit)
            if reg.state_class:
                z_sc = _coerce_sensor_state_class(reg.state_class)
            desc = SensorEntityDescription(
                key=name,
                name=_get_german_name(name),
                native_unit_of_measurement=reg.unit,
                device_class=z_dc,
                state_class=z_sc,
                icon=icon,
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


def get_library_binary_sensors(
    circuits: list[str] | None = None,
    zone_modules: int = 0,
    model_info: Any = None,
) -> list[dict[str, Any]]:
    """Binary sensors from library registers with binary=True flag."""
    from homeassistant.components.binary_sensor import BinarySensorEntityDescription

    reg_map = build_filtered_register_map(model_info, circuits, zone_modules)
    sensors = []
    for name, reg in reg_map.items():
        if not reg.binary or reg.writable:
            continue
        desc = BinarySensorEntityDescription(
            key=name,
            name=_get_german_name(name),
            device_class=infer_binary_device_class(name),
            icon=get_icon_for_register(name, reg.unit),
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        sensors.append(
            {
                "register": reg,
                "description": desc,
                "category": "binary",
            }
        )
    return sensors


def get_library_selects(
    circuits: list[str] | None = None,
    zone_modules: int = 0,
    model_info: Any = None,
) -> list[dict[str, Any]]:
    """Select entities (modes) from the library."""
    from homeassistant.components.select import SelectEntityDescription

    reg_map = build_filtered_register_map(model_info, circuits, zone_modules)
    selects = []
    for name, reg in reg_map.items():
        if not reg.writable or not reg.enum_options:
            continue
        if reg.write_only:
            continue

        slug_map, t_key = get_slug_map_and_key(name)
        excluded: set[int] = set(reg.exclude_from_write or [])

        if slug_map is not None:
            options = [v for k, v in slug_map.items() if k not in excluded]
        else:
            options = (
                [v for k, v in reg.enum_options.items() if k not in excluded]
                if excluded
                else list(reg.enum_options.values())
            )

        desc = SelectEntityDescription(
            key=name,
            name=_get_german_name(name),
            options=options,
            icon=reg.icon or get_icon_for_register(name),
            entity_category=EntityCategory.CONFIG,
            translation_key=t_key,
        )
        selects.append(
            {
                "register": reg,
                "description": desc,
            }
        )
    return selects


def get_library_zone_selects(zone_idx: int, room_count: int = 6) -> list[dict[str, Any]]:
    """Returns select descriptions for one zone module with its configured room count."""
    from homeassistant.components.select import SelectEntityDescription

    try:
        zone_regs = _get_zone_module_registers_compat(zone_idx, room_count)
    except Exception:
        _LOGGER.debug("Failed to load zone %d select registers", zone_idx, exc_info=True)
        return []

    selects = []
    for name, reg in zone_regs.items():
        if not reg.writable or not reg.enum_options:
            continue
        if reg.write_only:
            continue

        slug_map, t_key = get_slug_map_and_key(name)
        excluded: set[int] = set(reg.exclude_from_write or [])

        if slug_map is not None:
            options = [v for k, v in slug_map.items() if k not in excluded]
        else:
            options = (
                [v for k, v in reg.enum_options.items() if k not in excluded]
                if excluded
                else list(reg.enum_options.values())
            )

        desc = SelectEntityDescription(
            key=name,
            name=_get_german_name(name),
            options=options,
            icon=reg.icon or get_icon_for_register(name),
            entity_category=EntityCategory.CONFIG,
            translation_key=t_key,
        )
        selects.append({"register": reg, "description": desc})
    return selects


def get_library_switches(model_info: Any = None) -> list[dict[str, Any]]:
    """Switch entities (GLT demands etc.) from the library."""
    from homeassistant.components.switch import SwitchEntityDescription

    reg_map = build_filtered_register_map(model_info, [], 0)
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


def get_library_numbers(
    model_info: Any = None,
    circuits: list[str] | None = None,
    zone_modules: int = 0,
    enable_cascade: bool = True,
) -> list[dict[str, Any]]:
    """Returns number descriptions for writable library registers with HA metadata."""
    reg_map = build_filtered_register_map(model_info, circuits, zone_modules)
    return _numbers_from_register_map(reg_map)


def get_library_zone_numbers(zone_idx: int, room_count: int = 6) -> list[dict[str, Any]]:
    """Returns number descriptions for writable room registers in one zone module."""
    try:
        zone_regs = _get_zone_module_registers_compat(zone_idx, room_count)
    except Exception:
        _LOGGER.debug("Failed to load zone %d number registers", zone_idx, exc_info=True)
        return []
    return _numbers_from_register_map(zone_regs)


def _numbers_from_register_map(reg_map: dict[str, RegisterDef]) -> list[dict[str, Any]]:
    """Build HA number descriptions from writable non-enum library registers."""
    numbers = []

    for name, reg in reg_map.items():
        if not reg.writable or reg.enum_options:
            continue
        if reg.datatype.value == "BOOL":
            continue
        if reg.write_only:
            continue

        meta = NUMBER_METADATA.get(name, {})
        min_val = meta.get("min", reg.min_val if reg.min_val is not None else -999)
        max_val = meta.get("max", reg.max_val if reg.max_val is not None else 999)

        number_name = meta.get("name", _get_german_name(name))
        if is_glt_measurement(name):
            # Das Register existiert zusätzlich als Sensor — die Number ist die
            # externe GLT-Vorgabe und braucht einen unterscheidbaren Namen.
            number_name = f"{number_name} (Vorgabe)"

        # Raumtemperatur/-feuchte ist laut iDM-Doku (812170) nur beschreibbar,
        # wenn für den jeweiligen Raum ein externer/GLT-Raumsensor konfiguriert
        # ist; bei Verwendung der iDM-eigenen Raumsensoren ist das Register RO
        # und ein Schreibversuch wird vom Gerät ignoriert. Welcher Sensortyp je
        # Raum aktiv ist, lässt sich nicht über Modbus auslesen, daher wird die
        # Number standardmäßig deaktiviert statt sie unwirksam anzubieten.
        enabled_by_default = meta.get("enabled_by_default", not is_zone_room_measurement(name))

        desc = NumberEntityDescription(
            key=name,
            name=number_name,
            native_min_value=min_val,
            native_max_value=max_val,
            native_step=meta.get("step", 0.5),
            native_unit_of_measurement=meta.get("unit") or reg.unit,
            device_class=meta.get("device_class"),
            icon=meta.get("icon", get_icon_for_register(name, reg.unit)),
            mode=NumberMode.BOX,
            entity_category=meta.get("entity_category", EntityCategory.CONFIG),
            entity_registry_enabled_default=enabled_by_default,
        )
        numbers.append(
            {
                "register": reg,
                "description": desc,
            }
        )

    return numbers


def get_idm_client(
    host: str,
    port: int = 502,
    slave_id: int = 1,
    timeout: float | None = None,
    max_retries: int | None = None,
) -> LibIdmModbusClient:
    """Factory that returns a properly typed client from the library.

    ``timeout`` and ``max_retries`` are passed through when supplied so the
    HA integration can tune them per config entry. They default to the
    library's own defaults (10 s and 3 retries) when ``None``.
    """
    kwargs: dict[str, Any] = {}
    if timeout is not None:
        kwargs["timeout"] = float(timeout)
    if max_retries is not None:
        kwargs["max_retries"] = int(max_retries)
    return LibIdmModbusClient(host=host, port=port, slave_id=slave_id, **kwargs)


__all__ = [
    "LibIdmModbusClient",
    "MODEL_NAVIGATOR_10",
    "MODEL_NAVIGATOR_20",
    "MODEL_NAVIGATOR_PRO",
    "get_library_sensors",
    "get_library_numbers",
    "get_library_zone_numbers",
    "get_idm_client",
    "get_slug_map_and_key",
    "get_bitflag_de_labels",
    "is_glt_measurement",
]
