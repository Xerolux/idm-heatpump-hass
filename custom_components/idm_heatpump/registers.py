"""Register definitions for IDM Navigator 2.0 heat pumps.

All Modbus register addresses, data types, units, and read/write capabilities
are defined here. Registers are organized by functional group and provide
entity descriptions for Home Assistant platforms.
"""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.helpers.entity import EntityCategory

from .library_adapter import (
    get_library_binary_sensors,
    get_library_heating_circuit_sensors,
    get_library_numbers,
    get_library_selects,
    get_library_sensors,
    get_library_switches,
    get_library_zone_sensors,
)
from .modbus_client import DataType, RegisterDef

# ============================================================
# READ-ONLY SENSORS (now mostly served by library_adapter)
# ============================================================


_SENSOR_DC_MAP = {
    UnitOfTemperature.CELSIUS: SensorDeviceClass.TEMPERATURE,
    UnitOfPower.KILO_WATT: SensorDeviceClass.POWER,
    UnitOfEnergy.KILO_WATT_HOUR: SensorDeviceClass.ENERGY,
}
_SENSOR_STATE_CLASS_MAP = {
    SensorDeviceClass.TEMPERATURE: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.POWER: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.ENERGY: SensorStateClass.TOTAL_INCREASING,
    SensorDeviceClass.HUMIDITY: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.BATTERY: SensorStateClass.MEASUREMENT,
    # "humidity" string equals SensorDeviceClass.HUMIDITY, included for clarity
}


def _sensor(
    address: int,
    name: str,
    key: str,
    datatype: DataType = DataType.FLOAT,
    unit: str | None = None,
    device_class: SensorDeviceClass | str | None = None,
    icon: str | None = None,
    category: str = "system",
    entity_category: EntityCategory | None = None,
    disabled: bool = False,
    multiplier: float = 1.0,
    enum_options: dict[int, str] | None = None,
) -> dict[str, Any]:
    resolved_dc = _SENSOR_DC_MAP.get(device_class, device_class)
    state_class = _SENSOR_STATE_CLASS_MAP.get(resolved_dc)
    return {
        "register": RegisterDef(
            address=address,
            datatype=datatype,
            name=key,
            unit=unit,
            multiplier=multiplier,
            enum_options=enum_options,
        ),
        "description": SensorEntityDescription(
            key=key,
            name=name,
            native_unit_of_measurement=unit,
            device_class=resolved_dc,
            state_class=state_class,
            icon=icon,
            entity_category=entity_category,
            entity_registry_enabled_default=not disabled,
        ),
        "category": category,
    }

    # SYSTEM_SENSORS is deprecated and no longer the primary source.
    # Kept temporarily for reference during migration.
    # SYSTEM_SENSORS = [
    #     _sensor(
    #         1000,
    #         "Aussentemperatur",
    #         "outdoor_temp",
    #         unit=UnitOfTemperature.CELSIUS,
    #         device_class=UnitOfTemperature.CELSIUS,
    #     ),
    (
        _sensor(
            1002,
            "Gemittelte Aussentemperatur",
            "outdoor_temp_avg",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1004,
            "Interne Meldung",
            "internal_message",
            datatype=DataType.UCHAR,
            icon="mdi:message-alert",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1006,
            "Smart Grid Status",
            "smart_grid_status",
            datatype=DataType.UCHAR,
            icon="mdi:transmission-tower",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    )
    (
        _sensor(
            1008,
            "Waermespeichertemperatur",
            "storage_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1010,
            "Kaeltetespeichertemperatur",
            "cold_storage_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1012,
            "Trinkwassererwaermer unten",
            "dhw_temp_bottom",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1014,
            "Trinkwassererwaermer oben",
            "dhw_temp_top",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1030,
            "Warmwasserzapftemperatur",
            "dhw_draw_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1048,
            "Aktueller Strompreis",
            "current_energy_price",
            unit="€",
            device_class="monetary",
            multiplier=0.001,
        ),
    )
    # --- Waermepumpen-Temperaturen B33–B46 (FLOAT, je 2 Register) ---
    (
        _sensor(
            1050,
            "WP Vorlauftemperatur B33",
            "hp_flow_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1052,
            "WP Ruecklauftemperatur B34",
            "hp_return_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1054,
            "HGL Vorlauftemperatur B35",
            "hgl_flow_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1056,
            "Waermequelleneintrittstemperatur B43",
            "heat_source_inlet_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1058,
            "Waermequellenaustrittstemperatur B36",
            "heat_source_outlet_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1060,
            "Luftansaugtemperatur B37",
            "air_intake_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1062,
            "Luftwaermetauschertemperatur B72",
            "air_hx_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1064,
            "Luftansaugtemperatur 2 B46",
            "air_intake_temp_2",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1066,
            "Ladefuehler B45",
            "charge_sensor_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    # --- Betriebsstatus ---
    (
        _sensor(
            1090,
            "Betriebsart Waermepumpe",
            "heatpump_status",
            datatype=DataType.BITFLAG,
            icon="mdi:heat-pump",
            # enum_options moved to library_adapter during migration
        ),
    )
    (
        _sensor(
            1098,
            "EVU-Sperrkontakt",
            "evu_lock",
            datatype=DataType.UCHAR,
            icon="mdi:lock",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    # --- Pumpenstatus ---
    (
        _sensor(
            1104,
            "Status Ladepumpe M73",
            "charge_pump_status",
            datatype=DataType.INT16,
            unit=PERCENTAGE,
            icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1105,
            "Status Sole-/Zwischenkreispumpe M16",
            "brine_pump_status",
            datatype=DataType.INT16,
            unit=PERCENTAGE,
            icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1106,
            "Status Waermequellen-/Grundwasserpumpe M15",
            "source_pump_status",
            datatype=DataType.INT16,
            unit=PERCENTAGE,
            icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1108,
            "Status ISC Kaeltespeicherpumpe M84",
            "isc_cold_pump_status",
            datatype=DataType.INT16,
            unit=PERCENTAGE,
            icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1109,
            "Status ISC Rueckkuehlpumpe M17",
            "isc_recool_pump_status",
            datatype=DataType.INT16,
            unit=PERCENTAGE,
            icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1118,
            "Zirkulationspumpe M64",
            "circulation_pump_status",
            datatype=DataType.INT16,
            icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    # --- Umschaltventile (korrekte Bezeichnungen lt. IDM-Dokumentation) ---
    (
        _sensor(
            1110,
            "Umschaltventil Heizkreis Heizen/Kuehlen M61",
            "valve_hc_heat_cool",
            datatype=DataType.INT16,
            icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
            enum_options={0: "Heizen", 1: "Kuehlen"},
        ),
    )
    (
        _sensor(
            1111,
            "Umschaltventil Speicher Heizen/Kuehlen M62",
            "valve_storage_heat_cool",
            datatype=DataType.INT16,
            icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
            enum_options={0: "Heizen", 1: "Kuehlen"},
        ),
    )
    (
        _sensor(
            1112,
            "Umschaltventil Heizen/Warmwasser M63",
            "valve_heat_dhw",
            datatype=DataType.INT16,
            icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
            enum_options={0: "Heizen", 1: "Warmwasser"},
        ),
    )
    (
        _sensor(
            1113,
            "Umschaltventil Waermequelle Heizen/Kuehlen M74",
            "valve_source_heat_cool",
            datatype=DataType.INT16,
            icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
            enum_options={0: "Heizen", 1: "Kuehlen"},
        ),
    )
    (
        _sensor(
            1114,
            "Umschaltventil Solar Heizen/Warmwasser M78",
            "valve_solar_heat_dhw",
            datatype=DataType.INT16,
            icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
            enum_options={0: "Heizen", 1: "Warmwasser"},
        ),
    )
    (
        _sensor(
            1115,
            "Umschaltventil Solar Speicher/Waermequelle M79",
            "valve_solar_storage_source",
            datatype=DataType.INT16,
            icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
            enum_options={0: "Speicher", 1: "Waermequelle"},
        ),
    )
    (
        _sensor(
            1116,
            "Umschaltventil ISC Waermequelle/Kaeltespeicher M89",
            "valve_isc_source_cold",
            datatype=DataType.INT16,
            icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
            enum_options={0: "Waermequelle", 1: "Kaeltespeicher"},
        ),
    )
    (
        _sensor(
            1117,
            "Umschaltventil ISC Speicher/Bypass M99",
            "valve_isc_storage_bypass",
            datatype=DataType.INT16,
            icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
            enum_options={0: "Speicher", 1: "Bypass"},
        ),
    )
    # --- Bivalenz ---
    (
        _sensor(
            1124,
            "Bivalenz Betriebszustand",
            "bivalency_state",
            datatype=DataType.UCHAR,
            icon="mdi:heat-pump",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    # --- Kaskade: verfuegbare Stufen (neu) ---
    (
        _sensor(
            1147,
            "Kaskade Verfuegbare Stufen Heizen",
            "cascade_avail_stages_heat",
            datatype=DataType.UCHAR,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1148,
            "Kaskade Verfuegbare Stufen Kuehlen",
            "cascade_avail_stages_cool",
            datatype=DataType.UCHAR,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1149,
            "Kaskade Verfuegbare Stufen Warmwasser",
            "cascade_avail_stages_dhw",
            datatype=DataType.UCHAR,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    # --- Kaskade: laufende Stufen ---
    (
        _sensor(
            1150,
            "Kaskade Laufende Stufen Heizen",
            "cascade_running_stages_heat",
            datatype=DataType.UCHAR,
            icon="mdi:engine",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    )
    (
        _sensor(
            1151,
            "Kaskade Laufende Stufen Kuehlen",
            "cascade_running_stages_cool",
            datatype=DataType.UCHAR,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1152,
            "Kaskade Laufende Stufen Warmwasser",
            "cascade_running_stages_dhw",
            datatype=DataType.UCHAR,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    # --- Kaskade: Temperaturen (read-only, Mehrkesselanlagen) ---
    (
        _sensor(
            1200,
            "Kaskade Angeforderte Heiztemperatur",
            "cascade_req_heat_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1202,
            "Kaskade Angeforderte Kuehltemperatur",
            "cascade_req_cool_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1204,
            "Kaskade Angeforderte WW-Temperatur",
            "cascade_req_dhw_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1206,
            "Kaskade Gemittelte VL-Temp Heizen",
            "cascade_avg_flow_heat",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1208,
            "Kaskade Gemittelte VL-Temp Kuehlen",
            "cascade_avg_flow_cool",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1210,
            "Kaskade Gemittelte VL-Temp Warmwasser",
            "cascade_avg_flow_dhw",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1392,
            "Feuchtesensor",
            "humidity",
            datatype=DataType.UINT16,
            unit=PERCENTAGE,
            device_class="humidity",
        ),
    )
    (
        _sensor(
            1690,
            "Externe Aussentemperatur",
            "outdoor_temp_ext",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1692,
            "Externe Feuchte",
            "humidity_ext",
            datatype=DataType.UINT16,
            unit=PERCENTAGE,
            device_class="humidity",
        ),
    )
    # --- Waermemengen (lt. offiziellem IDM-YAML: 1750 = Gesamt!) ---
    (
        _sensor(
            1748,
            "Waermemenge Heizen",
            "energy_heat_heating",
            unit=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    )
    (
        _sensor(
            1750,
            "Waermemenge Gesamt",
            "energy_heat_total",
            unit=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    )
    (
        _sensor(
            1752,
            "Waermemenge Kuehlen",
            "energy_heat_cooling",
            unit=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    )
    (
        _sensor(
            1754,
            "Waermemenge Warmwasser",
            "energy_heat_dhw",
            unit=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    )
    (
        _sensor(
            1756,
            "Waermemenge Abtauung",
            "energy_heat_defrost",
            unit=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    )
    (
        _sensor(
            1758,
            "Waermemenge Passive Kuehlung",
            "energy_heat_passive_cooling",
            unit=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    )
    (
        _sensor(
            1760,
            "Waermemenge Solar",
            "energy_heat_solar",
            unit=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    )
    (
        _sensor(
            1762,
            "Waermemenge Elektroheizeinsatz",
            "energy_heat_electric",
            unit=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    )
    # --- Momentanleistung (war faelschlicherweise als "Maximale Leistung" deklariert) ---
    (
        _sensor(
            1790,
            "Momentanleistung",
            "current_power_draw",
            unit=UnitOfPower.KILO_WATT,
            device_class=UnitOfPower.KILO_WATT,
        ),
    )
    (
        _sensor(
            1850,
            "Solar Kollektortemperatur",
            "solar_collector_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1852,
            "Solar Kollektorruecklauftemperatur",
            "solar_collector_return_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1854,
            "Solar Ladetemperatur",
            "solar_charge_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1857,
            "Solar WQ-Referenztemperatur/Pooltemperatur",
            "solar_reference_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1870,
            "ISC Ladetemperatur Kuehlen",
            "isc_charge_cooling_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            1872,
            "ISC Rueckkuehltemperatur",
            "isc_recooling_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
        ),
    )
    (
        _sensor(
            4120,
            "Firmware Version Navigator",
            "firmware_version",
            datatype=DataType.UCHAR,
            icon="mdi:information",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            4122,
            "Aktuelle Leistungsaufnahme Waermepumpe",
            "power_draw_total",
            unit=UnitOfPower.KILO_WATT,
            device_class=UnitOfPower.KILO_WATT,
        ),
    )
    (
        _sensor(
            4126,
            "Thermische Leistung",
            "thermal_power",
            unit=UnitOfPower.KILO_WATT,
            device_class=UnitOfPower.KILO_WATT,
        ),
    )
    (
        _sensor(
            4128,
            "Waermemenge Gesamt (Durchflusssensor)",
            "energy_total_flow_sensor",
            unit=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=UnitOfEnergy.KILO_WATT_HOUR,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )

    # ============================================================
    # NAVIGATOR 10 / WÄRMESENKE (Trennwärmetauscher / Hydrauliktrennung)
    # Besonders nützlich bei ALM-Geräten mit Plattenwärmetauscher.
    # Adresse 1072 (Durchfluss) ist hervorragend zur Sieb-Überwachung geeignet.
    # ============================================================
    (
        _sensor(
            1068,
            "Rücklauftemperatur Wärmesenke (B124)",
            "heat_sink_return_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            icon="mdi:thermometer",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    )
    (
        _sensor(
            1070,
            "Vorlauftemperatur Wärmesenke (B125)",
            "heat_sink_flow_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            icon="mdi:thermometer",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    )
    (
        _sensor(
            1072,
            "Durchfluss Wärmesenke (B2)",
            "heat_sink_flow_rate",
            datatype=DataType.UCHAR,
            unit="l/min",
            icon="mdi:water-pump",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    )
    (
        _sensor(
            1074,
            "Steuersignal Ladepumpe Wärmesenke (M73)",
            "heat_sink_charging_pump_signal",
            datatype=DataType.INT16,
            unit=PERCENTAGE,
            icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )

    # Zusätzliche Störungen (Navigator 10 / erweiterte Diagnose)
    (
        _sensor(
            1680,
            "Störung Wärmequellenkreis",
            "fault_heat_source_circuit",
            datatype=DataType.UCHAR,
            icon="mdi:alert-circle",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    (
        _sensor(
            1681,
            "Störung Druckschalter Wärmequellenkreis",
            "fault_heat_source_pressure",
            datatype=DataType.UCHAR,
            icon="mdi:alert-circle",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )

    # Booster A/B (Zusatzheizung / 2. Wärmeerzeuger) - Status
    (
        _sensor(
            4001,
            "Booster Störung",
            "booster_fault",
            datatype=DataType.UCHAR,
            icon="mdi:alert",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    )
    (
        _sensor(
            4022,
            "Booster A Verdichter",
            "booster_a_compressor",
            datatype=DataType.UCHAR,
            icon="mdi:engine",
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled=True,
        ),
    )
    # _sensor(4052, "Booster B Verdichter", "booster_b_compressor", ... ),
    # ... (rest of old SYSTEM_SENSORS list removed during aggressive migration)


# ]
# Old SYSTEM_SENSORS list dismantled - now served by library_adapter


# ============================================================
# LEGACY CODE REMOVED
# The migration to the idm_heatpump library + library_adapter is 100% complete.
# PUBLIC FUNCTIONS - Collect all register descriptions
# ============================================================


def get_all_sensor_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    """
    Assembles all sensor descriptions.

    The library + adapter is now the preferred source.
    Local definitions are kept for rich German names and specific icons.
    """
    descriptions = []

    # Library + Adapter is now the primary and preferred source
    try:
        descriptions.extend(
            get_library_sensors(circuits=circuits, zone_modules=zone_count)
        )
    except Exception:
        pass

    # Spezialisierte Generatoren für Heizkreise und Zonen aus dem Adapter
    for circuit in circuits:
        descriptions.extend(get_library_heating_circuit_sensors(circuit))
    for z in range(zone_count):
        rooms = zone_rooms.get(z, 6)
        descriptions.extend(get_library_zone_sensors(z + 1, rooms))

    # Legacy old generators are fully disabled for sensors.
    # The migration to library + adapter is the goal.

    # Deduplicate
    seen_keys: set[str] = set()
    unique: list[dict[str, Any]] = []
    for desc in descriptions:
        key = desc["description"].key
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(desc)

    return unique


def get_all_binary_sensor_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    descriptions = []
    try:
        descriptions.extend(
            get_library_binary_sensors(circuits=circuits, zone_modules=zone_count)
        )
    except Exception:
        pass
    # Old local binary sensors disabled during migration
    return descriptions


def get_all_number_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    descriptions = []

    # Library numbers (preferred)
    try:
        descriptions.extend(
            get_library_numbers(circuits=circuits, zone_modules=zone_count)
        )
    except Exception:
        pass

    # Legacy numbers deaktiviert
    return descriptions


def get_all_select_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    descriptions = []
    try:
        descriptions.extend(
            get_library_selects(circuits=circuits, zone_modules=zone_count)
        )
    except Exception:
        pass
    # Old local selects disabled during migration
    return descriptions


def get_all_switch_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    descriptions = []
    try:
        descriptions.extend(get_library_switches())
    except Exception:
        pass
    # Old local switches disabled during migration
    return descriptions


def _build_alias_map(
    all_descriptions: list[dict[str, Any]],
) -> dict[int, list[str]]:
    """Build a mapping from register address to all register names sharing that address.

    Sensors and numbers often share the same Modbus address (e.g. a temperature
    sensor shows the current value, while a number entity allows setting it).
    Since ``read_batch`` returns data keyed by *register name*, we need to
    ensure that every entity can find its value under the name it expects.
    """
    addr_to_names: dict[int, list[str]] = {}
    for desc in all_descriptions:
        reg: RegisterDef = desc["register"]
        addr_to_names.setdefault(reg.address, []).append(reg.name)
    return addr_to_names


def _collect_all_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    """Collect all entity descriptions across all platforms."""
    return (
        get_all_sensor_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
        + get_all_binary_sensor_descriptions(
            circuits, zone_count, zone_rooms, enable_cascade
        )
        + get_all_number_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
        + get_all_select_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
        + get_all_switch_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
    )


def collect_all_registers(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[RegisterDef]:
    """Collect all unique registers for batch reading."""
    all_descriptions = _collect_all_descriptions(
        circuits, zone_count, zone_rooms, enable_cascade
    )

    seen: dict[int, RegisterDef] = {}
    for desc in all_descriptions:
        reg: RegisterDef = desc["register"]
        if reg.address not in seen:
            seen[reg.address] = reg

    return list(seen.values())


def collect_alias_map(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> dict[int, list[str]]:
    """Collect address -> [register_names] alias mapping.

    Multiple entity types (sensor + number) can share the same Modbus address
    but use different register names. ``read_batch`` returns data keyed by one
    name per address.  This map lets the coordinator populate the other names.
    """
    all_descriptions = _collect_all_descriptions(
        circuits, zone_count, zone_rooms, enable_cascade
    )
    return _build_alias_map(all_descriptions)
