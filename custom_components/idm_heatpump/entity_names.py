"""Translation keys, placeholders and English names for register-backed entities.

Home Assistant's ``entity-translations`` quality rule wants the visible entity
name to come from the translation files, not from a hardcoded ``name`` on the
entity description. The register space is generated (heating circuits A-G, up to
ten zone modules with eight rooms each), so the mapping is expressed as a rule
instead of one translation key per register:

``hc_c_flow_temp``      -> key ``hc_flow_temp``      + ``{"circuit": "C"}``
``zm7_room3_temp``      -> key ``zone_room_temp``    + ``{"zone": "7", "room": "3"}``
``zm7_dehumidification``-> key ``zone_dehumidification`` + ``{"zone": "7"}``
``outdoor_temp``        -> key ``outdoor_temp``      + ``{}``

The English names below are the canonical strings; ``strings.json`` and the
``en``/``de`` translation files are generated from them together with the German
names in :mod:`.adapter_names` (see ``scripts/generate_entity_translations.py``).
A register that is not covered here keeps the German fallback name of the entity
description, so a register added by a newer ``idm-heatpump-api`` release still
gets a readable name instead of falling back to the bare device name.

The module deliberately imports nothing from Home Assistant so the generator and
the documentation tooling can use it without a full HA runtime.
"""

from __future__ import annotations

import re
from typing import Final

_HEATING_CIRCUIT_RE: Final = re.compile(r"^hc_(?P<circuit>[a-g])_(?P<rest>.+)$")
_ZONE_ROOM_RE: Final = re.compile(r"^zm(?P<zone>\d+)_room(?P<room>\d+)_(?P<rest>.+)$")
_ZONE_RE: Final = re.compile(r"^zm(?P<zone>\d+)_(?P<rest>.+)$")

# Registers that are exposed twice: as a sensor (the measured value) and as a
# number (the external building-management setpoint). The number needs its own
# name so both entities stay distinguishable.
BMS_SETPOINT_SUFFIX_EN: Final = " (external setpoint)"
BMS_SETPOINT_SUFFIX_DE: Final = " (Vorgabe)"


def translation_for_register(name: str) -> tuple[str, dict[str, str]]:
    """Return the translation key and placeholders for a register name."""
    match = _HEATING_CIRCUIT_RE.match(name)
    if match is not None:
        return f"hc_{match['rest']}", {"circuit": match["circuit"].upper()}
    match = _ZONE_ROOM_RE.match(name)
    if match is not None:
        return f"zone_room_{match['rest']}", {"zone": match["zone"], "room": match["room"]}
    match = _ZONE_RE.match(name)
    if match is not None:
        return f"zone_{match['rest']}", {"zone": match["zone"]}
    return name, {}


def translation_key_for_register(name: str) -> str:
    """Return only the translation key for a register name."""
    return translation_for_register(name)[0]


def has_translated_name(name: str) -> bool:
    """Whether this register's entity name is shipped in the translation files."""
    return translation_key_for_register(name) in ENGLISH_NAMES


# Value keys of the local Navigator web supplement that exist once per heating
# circuit. They share one translation key with the circuit as a placeholder.
_WEB_CIRCUIT_PREFIXES: Final[dict[str, str]] = {
    "mixer_heating_circuit": "web_mixer_heating_circuit",
    "pump_heating_circuit": "web_pump_heating_circuit",
    "flow_temp_HK_": "web_flow_temp_hc",
    "room_temperature_HK_": "web_room_temperature_hc",
}


def web_translation_for_value(value_key: str) -> tuple[str, dict[str, str]]:
    """Return the translation key and placeholders of a web supplement value."""
    for prefix, key in _WEB_CIRCUIT_PREFIXES.items():
        if not value_key.startswith(prefix):
            continue
        circuit = value_key[len(prefix) :]
        if len(circuit) == 1 and circuit.isalpha():
            return key, {"circuit": circuit.upper()}
    return f"web_{value_key.lower()}", {}


ENGLISH_NAMES: Final[dict[str, str]] = {
    # === System / outdoor ===
    "outdoor_temp": "Outdoor temperature",
    "outdoor_temp_avg": "Average outdoor temperature",
    "storage_temp": "Heat storage temperature",
    "cold_storage_temp": "Cold storage temperature",
    "charging_sensor_temp": "Charging sensor temperature",
    "system_mode": "System mode",
    "hp_operating_mode": "Heat pump operating mode",
    "internal_message": "Internal message",
    "firmware_version": "Navigator firmware version",
    "smart_grid_status": "Smart grid status",
    "variable_input": "Variable input",
    "humidity_sensor": "Humidity sensor",
    "current_electricity_price": "Current electricity price",
    # === Heat pump circuit ===
    "hp_flow_temp": "Heat pump flow temperature",
    "hp_return_temp": "Heat pump return temperature",
    "heat_source_inlet_temp": "Heat source inlet",
    "heat_source_outlet_temp": "Heat source outlet",
    "heat_sink_flow_temp": "Heat sink flow temperature (B125)",
    "heat_sink_return_temp": "Heat sink return temperature (B124)",
    "heat_sink_flow_rate": "Heat sink flow rate (B2)",
    "heat_sink_charging_pump_signal": "Heat sink charging pump control signal (M73)",
    "air_intake_temp": "Air intake temperature",
    "air_intake_temp_2": "Air intake temperature 2",
    "air_heat_exchanger_temp": "Air heat exchanger temperature",
    "hgl_flow_temp": "HGL flow temperature (B35)",
    "groundwater_inlet_temp_1": "Groundwater inlet temperature 1",
    "groundwater_inlet_temp_2": "Groundwater inlet temperature 2",
    "current_power": "Current thermal power",
    "thermal_power_flow_sensor": "Thermal power (flow sensor)",
    "power_consumption_hp": "Heat pump power consumption",
    "power_consumption_hp_smartfox": "Smartfox power consumption",
    "electric_heater_power": "Electric heater power",
    "power_limit_hp": "Heat pump power limit",
    "power_limit_cascade": "Cascade power limit",
    "evu_lock": "Utility lock",
    # === Pumps, valves and compressors ===
    "charging_pump_status": "Charging pump M73",
    "brine_pump_status": "Brine/intermediate circuit pump",
    "heat_source_pump_status": "Heat source pump M15",
    "circulation_pump": "Circulation pump M64",
    "isc_cold_storage_pump_status": "ISC cold storage pump M84",
    "isc_recooling_pump_status": "ISC recooling pump M17",
    "compressor_status_1": "Compressor 1",
    "compressor_status_2": "Compressor 2",
    "compressor_status_3": "Compressor 3",
    "compressor_status_4": "Compressor 4",
    "valve_hc_heat_cool": "Heating circuit changeover valve heating/cooling",
    "valve_storage_heat_cool": "Storage changeover valve heating/cooling",
    "valve_heat_dhw": "Changeover valve heating/hot water",
    "valve_heat_source_heat_cool": "Heat source changeover valve",
    "valve_isc_heat_source_cold_storage": "ISC changeover valve",
    "valve_isc_storage_bypass": "ISC changeover valve storage/bypass",
    "valve_solar_heat_dhw": "Solar changeover valve heating/hot water",
    "valve_solar_storage_heat_source": "Solar storage/heat source valve",
    # === Demands and faults ===
    "heating_demand": "Heating demand",
    "cooling_demand": "Cooling demand",
    "dhw_demand": "Hot water demand",
    "demand_heating": "External heating demand",
    "demand_cooling": "External cooling demand",
    "demand_dhw_charging": "External hot water charging demand",
    "demand_onetime_dhw": "One-time hot water demand",
    "hp_sum_alarm": "Collective fault",
    "booster_fault": "Booster fault",
    "booster_interlock": "Booster interlock",
    "fault_heat_source_circuit": "Heat source circuit fault",
    "fault_heat_source_pressure_switch": "Heat source pressure switch fault",
    "fault_charging_pump_1_intermediate": "Charging pump 1 intermediate circuit fault",
    "fault_charging_pump_2_intermediate": "Charging pump 2 intermediate circuit fault",
    # === Domestic hot water ===
    "dhw_temp_bottom": "Hot water tank bottom",
    "dhw_temp_top": "Hot water tank top",
    "dhw_tapping_temp": "Hot water tapping temperature",
    "dhw_setpoint": "Hot water setpoint",
    "dhw_charge_on_temp": "Hot water charge start temperature",
    "dhw_charge_off_temp": "Hot water charge stop temperature",
    # === Energy counters ===
    "energy_total": "Total energy",
    "energy_heating": "Heating energy",
    "energy_cooling": "Cooling energy",
    "energy_dhw": "Hot water energy",
    "energy_defrost": "Defrost energy",
    "energy_solar": "Solar energy",
    "energy_electric_heater": "Electric heater energy",
    "energy_passive_cooling": "Passive cooling energy",
    "total_heat_energy": "Total heat energy (Vortex)",
    # === Bivalence ===
    "bivalence_state": "Bivalence operating state",
    "bivalence_point_1_2nd_gen": "Bivalence point 1 (2nd heat generator)",
    "bivalence_point_2_2nd_gen": "Bivalence point 2 (2nd heat generator)",
    "bivalence_point_1_3rd_gen": "Bivalence point 1 (3rd heat generator)",
    "bivalence_point_2_3rd_gen": "Bivalence point 2 (3rd heat generator)",
    # === Heating circuits ===
    "hc_flow_temp": "Heating circuit {circuit} flow temperature",
    "hc_setpoint_flow_temp": "Heating circuit {circuit} flow temperature setpoint",
    "hc_room_temp": "Heating circuit {circuit} room temperature",
    "hc_ext_room_temp": "Heating circuit {circuit} external room temperature",
    "hc_mode": "Heating circuit {circuit} mode",
    "hc_active_mode": "Heating circuit {circuit} active mode",
    "hc_heating_curve": "Heating circuit {circuit} heating curve",
    "hc_heating_limit": "Heating circuit {circuit} heating limit",
    "hc_cooling_limit": "Heating circuit {circuit} cooling limit",
    "hc_parallel_shift": "Heating circuit {circuit} parallel shift",
    "hc_setpoint_flow_constant": "Heating circuit {circuit} constant flow setpoint",
    "hc_setpoint_flow_cooling": "Heating circuit {circuit} cooling flow setpoint",
    "hc_room_setpoint_heat_normal": "Heating circuit {circuit} room setpoint heating normal",
    "hc_room_setpoint_heat_eco": "Heating circuit {circuit} room setpoint heating eco",
    "hc_room_setpoint_cool_normal": "Heating circuit {circuit} room setpoint cooling normal",
    "hc_room_setpoint_cool_eco": "Heating circuit {circuit} room setpoint cooling eco",
    # === Zone modules ===
    "zone_dehumidification": "Zone {zone} dehumidification",
    "zone_mode_heat_cool": "Zone {zone} heating/cooling changeover",
    "zone_room_temp": "Zone {zone} room {room} temperature",
    "zone_room_setpoint": "Zone {zone} room {room} setpoint",
    "zone_room_humidity": "Zone {zone} room {room} humidity",
    "zone_room_mode": "Zone {zone} room {room} mode",
    "zone_room_relay": "Zone {zone} room {room} relay",
    # === Solar and ISC ===
    "solar_mode": "Solar mode",
    "solar_collector_temp": "Solar collector temperature",
    "solar_charging_temp": "Solar charging temperature",
    "solar_return_temp": "Solar return temperature",
    "solar_wq_pool_temp": "Solar heat source reference/pool temperature",
    "current_power_solar": "Current solar power",
    "isc_mode": "ISC mode",
    "isc_charging_temp_cooling": "ISC charging temperature cooling",
    "isc_recooling_temp": "ISC recooling temperature",
    # === Photovoltaics and battery ===
    "pv_production": "PV production",
    "pv_surplus": "PV surplus",
    "pv_target_value": "PV target value",
    "house_consumption": "House consumption",
    "battery_soc": "Battery state of charge",
    "battery_discharge": "Battery discharge",
    # === External / building management (GLT) values ===
    "ext_outdoor_temp": "External outdoor temperature (BMS)",
    "ext_humidity": "External humidity (BMS)",
    "ext_demand_temp_heating": "External demand temperature heating",
    "ext_demand_temp_cooling": "External demand temperature cooling",
    "ext_demand_groundwater_pump_m15": "External demand groundwater pump M15",
    "ext_demand_groundwater_pump_m15_sw_max": "External demand groundwater pump M15 (SW max)",
    "glt_heat_storage_temp": "BMS heat storage temperature",
    "glt_cold_storage_temp": "BMS cold storage temperature",
    "glt_dhw_temp_top": "BMS hot water tank top",
    "glt_dhw_temp_bottom": "BMS hot water tank bottom",
    "glt_temp_demand_heating": "BMS temperature demand heating",
    "glt_temp_demand_cooling": "BMS temperature demand cooling",
    # === Booster ===
    "booster_a_compressor": "Booster A compressor",
    "booster_a_charging_pump": "Booster A charging pump",
    "booster_a_source_pump": "Booster A heat source pump",
    "booster_a_flow_temp": "Booster A flow temperature",
    "booster_a_return_temp": "Booster A return temperature",
    "booster_a_storage_temp": "Booster A storage temperature",
    "booster_a_source_inlet_temp": "Booster A heat source inlet",
    "booster_a_source_outlet_temp": "Booster A heat source outlet",
    "booster_b_compressor": "Booster B compressor",
    "booster_b_charging_pump": "Booster B charging pump",
    "booster_b_source_pump": "Booster B heat source pump",
    "booster_b_flow_temp": "Booster B flow temperature",
    "booster_b_return_temp": "Booster B return temperature",
    "booster_b_storage_temp": "Booster B storage temperature",
    "booster_b_source_inlet_temp": "Booster B heat source inlet",
    "booster_b_source_outlet_temp": "Booster B heat source outlet",
    # === Cascade ===
    "cascade_available_heating": "Cascade available for heating",
    "cascade_available_cooling": "Cascade available for cooling",
    "cascade_available_dhw": "Cascade available for hot water",
    "cascade_running_heating": "Cascade running in heating",
    "cascade_running_cooling": "Cascade running in cooling",
    "cascade_running_dhw": "Cascade running for hot water",
    "cascade_req_heating_temp": "Cascade requested heating temperature",
    "cascade_req_cooling_temp": "Cascade requested cooling temperature",
    "cascade_req_dhw_temp": "Cascade requested hot water temperature",
    "cascade_avg_flow_heating": "Cascade average flow temperature heating",
    "cascade_avg_flow_cooling": "Cascade average flow temperature cooling",
    "cascade_avg_flow_dhw": "Cascade average flow temperature hot water",
    "cascade_min_power_heating": "Cascade minimum power heating",
    "cascade_min_power_cooling": "Cascade minimum power cooling",
    "cascade_min_power_dhw": "Cascade minimum power hot water",
    "cascade_max_power_heating": "Cascade maximum power heating",
    "cascade_max_power_cooling": "Cascade maximum power cooling",
    "cascade_max_power_dhw": "Cascade maximum power hot water",
    "cascade_bivalence_heating_parallel": "Cascade bivalence heating parallel",
    "cascade_bivalence_heating_alternative": "Cascade bivalence heating alternative",
    "cascade_bivalence_cooling_parallel": "Cascade bivalence cooling parallel",
    "cascade_bivalence_cooling_alternative": "Cascade bivalence cooling alternative",
    "cascade_bivalence_dhw_parallel": "Cascade bivalence hot water parallel",
    "cascade_bivalence_dhw_alternative": "Cascade bivalence hot water alternative",
}


# Entities the integration derives itself instead of reading from a register:
# calculated sensors, the operating analysis and the technician access codes.
# They carry their own translation keys, so their names are kept here as
# ``(English, German)`` pairs and written to the translation files by
# ``scripts/generate_entity_translations.py``.
DERIVED_NAMES: Final[dict[str, dict[str, tuple[str, str]]]] = {
    "sensor": {
        # === Calculated ===
        "calculated_hp_temperature_delta": (
            "Heat pump temperature spread",
            "Wärmepumpen-Spreizung",
        ),
        "calculated_heat_source_temperature_delta": (
            "Heat source temperature spread",
            "Wärmequellen-Spreizung",
        ),
        "calculated_dhw_setpoint_deviation": (
            "Hot water deviation from setpoint",
            "Warmwasser-Abweichung Ist zu Soll",
        ),
        "calculated_cop": (
            "Coefficient of performance (current)",
            "Jahresarbeitszahl (COP, momentan)",
        ),
        "calculated_hc_flow_deviation": (
            "Heating circuit {circuit} flow deviation",
            "Heizkreis {circuit} Vorlauf-Abweichung",
        ),
        # === Operating analysis ===
        "analysis_heat_pump_cycles_recorded": ("Heat pump cycles recorded", "Wärmepumpentakte erfasst"),
        "analysis_heat_pump_cycles_today": ("Heat pump cycles today", "Wärmepumpentakte heute"),
        "analysis_heat_pump_cycles_2h": ("Heat pump cycles last 2 hours", "Wärmepumpentakte letzte 2 Stunden"),
        "analysis_heat_pump_cycles_4h": ("Heat pump cycles last 4 hours", "Wärmepumpentakte letzte 4 Stunden"),
        "analysis_current_cycle_duration": ("Current cycle runtime", "Aktuelle Taktlaufzeit"),
        "analysis_average_cycle_duration": ("Average cycle runtime", "Durchschnittliche Taktlaufzeit"),
        "analysis_last_compressor_start": ("Last compressor start", "Letzter Verdichterstart"),
        "analysis_last_cycle_duration": ("Last cycle runtime", "Letzte Taktlaufzeit"),
        "analysis_defrost_starts_recorded": ("Defrost cycles recorded", "Abtauvorgänge erfasst"),
        "analysis_defrost_starts_today": ("Defrost cycles today", "Abtauvorgänge heute"),
        "analysis_last_defrost_start": ("Last defrost start", "Letzter Abtaustart"),
        "analysis_time_since_last_defrost": ("Time since last defrost start", "Zeit seit letztem Abtaustart"),
        "analysis_operating_share_heating": ("Operating share heating", "Betriebsanteil Heizen"),
        "analysis_operating_share_dhw": ("Operating share hot water", "Betriebsanteil Warmwasser"),
        "analysis_operating_share_cooling": ("Operating share cooling", "Betriebsanteil Kühlen"),
        "analysis_operating_share_defrost": ("Operating share defrost", "Betriebsanteil Abtauen"),
        # === Technician access codes ===
        "technician_level_1": ("Technician level 1 code", "00 Fachmann Ebene 1"),
        "technician_level_2": ("Technician level 2 code", "00 Fachmann Ebene 2"),
        # === Local Navigator web supplement ===
        "web_4way_valve_circuit1": ("4-way valve circuit 1 (Web)", "4-Wege-Ventil Kreis 1 (Web)"),
        "web_airsource_temperature": ("Air source temperature (Web)", "Luftquellen Temperatur (Web)"),
        "web_battery_voltage_central_unit": (
            "Central unit battery voltage (Web)",
            "Batteriespannung Zentraleinheit (Web)",
        ),
        "web_board_temperature": ("Board temperature (Web)", "Platinentemperatur (Web)"),
        "web_cold_water_temperature": ("Cold water temperature (Web)", "Kaltwasser Temperatur (Web)"),
        "web_condenser_pressure": ("Condenser pressure (Web)", "Kondensator Druck (Web)"),
        "web_condenser_temperature": ("Condenser temperature (Web)", "Kondensator Temperatur (Web)"),
        "web_controller_online_hours": ("Controller online time (Web)", "Regler Online (Web)"),
        "web_current_electrical_power": ("Current electrical power (Web)", "Aktuelle elektrische Leistung (Web)"),
        "web_current_expected_power_cooling": (
            "Current/projected cooling power (Web)",
            "Momentane/prognostizierte Leistung Kühlen (Web)",
        ),
        "web_current_expected_power_heating": (
            "Current/projected heating power (Web)",
            "Momentane/prognostizierte Leistung Heizen (Web)",
        ),
        "web_current_expected_power_hotwater": (
            "Current/projected hot water power (Web)",
            "Momentane/prognostizierte Leistung Warmwasser (Web)",
        ),
        "web_evaporation_temperature": ("Evaporation temperature (Web)", "Verdampfungstemperatur (Web)"),
        "web_evaporator_outlet_temperature": (
            "Evaporator outlet temperature (Web)",
            "Verdampfer Austrittstemperatur (Web)",
        ),
        "web_ext_switch_heating_cooling": (
            "External heating/cooling changeover (Web)",
            "Externe Umschaltung Heizen/Kühlen (Web)",
        ),
        "web_flow_pump_output": ("Flow pump output (Web)", "Durchflusspumpe Ausgang (Web)"),
        "web_flow_pump_percentage": ("Flow pump signal (Web)", "Durchflusspumpe Signal (Web)"),
        "web_flow_temp_hc": (
            "Heating circuit {circuit} flow temperature (Web)",
            "Vorlauftemperatur HK {circuit} (Web)",
        ),
        "web_flow_temperature": ("Flow temperature (Web)", "Vorlauftemperatur (Web)"),
        "web_flowmeter": ("Flow meter (Web)", "Durchflussmesser (Web)"),
        "web_heat_sink_intermediate_circuit_pump_signal": (
            "Heat sink intermediate circuit pump signal (Web)",
            "Wärmesenke Zwischenkreispumpe Signal (Web)",
        ),
        "web_heating_water_outlet_temperature": (
            "Heating water outlet temperature (Web)",
            "Heizwasser Austrittstemperatur (Web)",
        ),
        "web_heatpump_model": ("Heat pump model (Web)", "Wärmepumpenmodell (Web)"),
        "web_heatstore_temperature": ("Heat storage temperature (Web)", "Wärmespeichertemperatur (Web)"),
        "web_hotgas_temperature": ("Hot gas temperature (Web)", "Heißgastemperatur (Web)"),
        "web_hotwater_circulation_heat_quantity": ("Circulation heat quantity (Web)", "Wärmemenge Zirkulation (Web)"),
        "web_hotwater_station_flowmeter": ("Hot water station flow (Web)", "Warmwasserstation Durchfluss (Web)"),
        "web_hotwater_station_pump_percentage": ("Hot water station pump (Web)", "Warmwasserstation Pumpe (Web)"),
        "web_hotwater_tapping_heat_quantity": ("Tapping heat quantity (Web)", "Wärmemenge Zapfung (Web)"),
        "web_hotwater_temperature": ("Hot water temperature (Web)", "Warmwassertemperatur (Web)"),
        "web_infosystem_notification_count": (
            "Info system notification count (Web)",
            "Infosystem Meldungen Anzahl (Web)",
        ),
        "web_infosystem_notifications": ("Info system notifications (Web)", "Infosystem Meldungen (Web)"),
        "web_liquid_line_temperature": ("Liquid line temperature (Web)", "Flüssigkeitsleitung Temperatur (Web)"),
        "web_loading_temperature": ("Charging temperature (Web)", "Ladetemperatur (Web)"),
        "web_mixer_heating_circuit": ("Heating circuit {circuit} mixer (Web)", "Mischer Heizkreis {circuit} (Web)"),
        "web_myidm_id": ("myIDM ID (Web)", "myIDM ID (Web)"),
        "web_navigator_version": ("Navigator version (Web)", "Navigator Version (Web)"),
        "web_outside_air_temperature": ("Outside air temperature (Web)", "Außenlufttemperatur (Web)"),
        "web_return_temperature": ("Return temperature (Web)", "Rücklauftemperatur (Web)"),
        "web_room_temperature_hc": (
            "Heating circuit {circuit} room temperature (Web)",
            "Raumtemperatur HK {circuit} (Web)",
        ),
        "web_runtime_cooling_hours": ("Cooling runtime (Web)", "Laufzeit Kühlen (Web)"),
        "web_runtime_defrosting_hours": ("Defrost runtime (Web)", "Laufzeit Abtauen (Web)"),
        "web_runtime_heating_hours": ("Heating runtime (Web)", "Laufzeit Heizen (Web)"),
        "web_runtime_hotwater_hours": ("Hot water runtime (Web)", "Laufzeit Warmwasser (Web)"),
        "web_runtime_second_heat_generator_hours": (
            "Second heat generator runtime (Web)",
            "Laufzeit 2. Wärmeerzeuger (Web)",
        ),
        "web_runtime_stage_1_hours": ("Stage 1 runtime (Web)", "Laufzeit Stufe 1 (Web)"),
        "web_software_version": ("Software version (Web)", "Software Version (Web)"),
        "web_switch_cycles_second_heat_generator": (
            "Second heat generator switch cycles (Web)",
            "Schaltzyklen 2. Wärmeerzeuger (Web)",
        ),
        "web_switch_cycles_stage_1": ("Stage 1 switch cycles (Web)", "Schaltzyklen Stufe 1 (Web)"),
        "web_valve_heating_hotwater": ("Heating/hot water valve (Web)", "Ventil Heizung/Warmwasser (Web)"),
        "web_ventilator_direction_1": ("Fan direction 1 (Web)", "Ventilator Richtung 1 (Web)"),
        "web_ventilator_voltage": ("Fan voltage (Web)", "Ventilator Spannung (Web)"),
        "web_verdamper_pressure": ("Evaporator pressure (Web)", "Verdampfer Druck (Web)"),
        "web_water_temp_bottom": ("Tank temperature bottom (Web)", "Speichertemperatur unten (Web)"),
        "web_water_temp_top": ("Tank temperature top (Web)", "Speichertemperatur oben (Web)"),
    },
    "binary_sensor": {
        "analysis_last_cycle_short": ("Last compressor cycle too short", "Letzter Verdichtertakt zu kurz"),
        # === Local Navigator web supplement ===
        "web_compressor_1": ("Compressor 1 (Web)", "Verdichter 1 (Web)"),
        "web_compressor_heating": ("Compressor heater (Web)", "Verdichterheizung (Web)"),
        "web_dewpoint_humidity_alarm": ("Dew point humidity alarm (Web)", "Taupunkt-Feuchtealarm (Web)"),
        "web_ew_evu_lock_contact": ("Utility lock contact (Web)", "EVU-Sperrkontakt (Web)"),
        "web_ext_hotwater_signal": ("External hot water request (Web)", "Externe Warmwasseranforderung (Web)"),
        "web_external_request": ("External request (Web)", "Externe Anforderung (Web)"),
        "web_failure_eheating": ("Electric heater fault (Web)", "Störung E-Heizung (Web)"),
        "web_flow_pump_on": ("Flow pump (Web)", "Durchflusspumpe (Web)"),
        "web_heat_generator_2nd": ("Second heat generator (Web)", "Zweiter Wärmeerzeuger (Web)"),
        "web_heat_generator_2nd_3rd": (
            "Second or third heat generator (Web)",
            "Zweiter oder dritter Wärmeerzeuger (Web)",
        ),
        "web_high_pressure_error": ("High-pressure fault (Web)", "Hochdruckstörung (Web)"),
        "web_hotwater_circulation_pump": ("Hot water circulation pump (Web)", "Warmwasser-Zirkulationspumpe (Web)"),
        "web_hotwater_station_flow_switch": (
            "Hot water station flow switch (Web)",
            "Warmwasserstation Strömungsschalter (Web)",
        ),
        "web_siphon_heating": ("Siphon heater (Web)", "Siphonheizung (Web)"),
        "web_pump_heating_circuit": ("Heating circuit {circuit} pump (Web)", "Pumpe Heizkreis {circuit} (Web)"),
    },
}

__all__ = [
    "BMS_SETPOINT_SUFFIX_DE",
    "BMS_SETPOINT_SUFFIX_EN",
    "DERIVED_NAMES",
    "ENGLISH_NAMES",
    "has_translated_name",
    "translation_for_register",
    "translation_key_for_register",
    "web_translation_for_value",
]
