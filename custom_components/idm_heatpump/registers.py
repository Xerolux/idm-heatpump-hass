from __future__ import annotations
"""Register definitions for IDM Navigator 2.0 heat pumps.

All Modbus register addresses, data types, units, and read/write capabilities
are defined here. Registers are organized by functional group and provide
entity descriptions for Home Assistant platforms.
"""

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntityDescription,
)
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.helpers.entity import EntityCategory

from .const import (
    CIRCUIT_MODE_OPTIONS,
    HP_STATUS_OPTIONS,
    ISC_MODE_OPTIONS,
    ROOM_MODE_OPTIONS,
    SOLAR_MODE_OPTIONS,
    SYSTEM_MODE_OPTIONS,
)
from .modbus_client import DataType, RegisterDef

HK_OFFSET = {"a": 0, "b": 2, "c": 4, "d": 6, "e": 8, "f": 10, "g": 12}
HK_MODE_ADDR = {"a": 1498, "b": 1499, "c": 1500, "d": 1501, "e": 1502, "f": 1503, "g": 1504}
HK_CONST_ADDR = {"a": 1449, "b": 1450, "c": 1451, "d": 1452, "e": 1453, "f": 1454, "g": 1455}

# ============================================================
# READ-ONLY SENSORS
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


SYSTEM_SENSORS = [
    _sensor(1000, "Aussentemperatur", "outdoor_temp", unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS),
    _sensor(1002, "Gemittelte Aussentemperatur", "outdoor_temp_avg",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1004, "Interne Meldung", "internal_message", datatype=DataType.UCHAR,
            icon="mdi:message-alert", entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1006, "Smart Grid Status", "smart_grid_status", datatype=DataType.UCHAR,
            icon="mdi:transmission-tower", entity_category=EntityCategory.DIAGNOSTIC),
    _sensor(1008, "Waermespeichertemperatur", "storage_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1010, "Kaeltetespeichertemperatur", "cold_storage_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1012, "Trinkwassererwaermer unten", "dhw_temp_bottom",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1014, "Trinkwassererwaermer oben", "dhw_temp_top",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1030, "Warmwasserzapftemperatur", "dhw_draw_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1048, "Aktueller Strompreis", "current_energy_price",
            unit="€", device_class="monetary", multiplier=0.001),
    # --- Waermepumpen-Temperaturen B33–B46 (FLOAT, je 2 Register) ---
    _sensor(1050, "WP Vorlauftemperatur B33", "hp_flow_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1052, "WP Ruecklauftemperatur B34", "hp_return_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1054, "HGL Vorlauftemperatur B35", "hgl_flow_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1056, "Waermequelleneintrittstemperatur B43", "heat_source_inlet_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1058, "Waermequellenaustrittstemperatur B36", "heat_source_outlet_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1060, "Luftansaugtemperatur B37", "air_intake_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1062, "Luftwaermetauschertemperatur B72", "air_hx_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1064, "Luftansaugtemperatur 2 B46", "air_intake_temp_2",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1066, "Ladefuehler B45", "charge_sensor_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    # --- Betriebsstatus ---
    _sensor(1090, "Betriebsart Waermepumpe", "heatpump_status", datatype=DataType.BITFLAG,
            icon="mdi:heat-pump", enum_options=HP_STATUS_OPTIONS),
    _sensor(1098, "EVU-Sperrkontakt", "evu_lock", datatype=DataType.UCHAR,
            icon="mdi:lock", entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    # --- Pumpenstatus ---
    _sensor(1104, "Status Ladepumpe M73", "charge_pump_status", datatype=DataType.INT16,
            unit=PERCENTAGE, icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1105, "Status Sole-/Zwischenkreispumpe M16", "brine_pump_status",
            datatype=DataType.INT16, unit=PERCENTAGE, icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1106, "Status Waermequellen-/Grundwasserpumpe M15", "source_pump_status",
            datatype=DataType.INT16, unit=PERCENTAGE, icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1108, "Status ISC Kaeltespeicherpumpe M84", "isc_cold_pump_status",
            datatype=DataType.INT16, unit=PERCENTAGE, icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1109, "Status ISC Rueckkuehlpumpe M17", "isc_recool_pump_status",
            datatype=DataType.INT16, unit=PERCENTAGE, icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1118, "Zirkulationspumpe M64", "circulation_pump_status",
            datatype=DataType.INT16, icon="mdi:pump",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    # --- Umschaltventile (korrekte Bezeichnungen lt. IDM-Dokumentation) ---
    _sensor(1110, "Umschaltventil Heizkreis Heizen/Kuehlen M61", "valve_hc_heat_cool",
            datatype=DataType.INT16, icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True,
            enum_options={0: "Heizen", 1: "Kuehlen"}),
    _sensor(1111, "Umschaltventil Speicher Heizen/Kuehlen M62", "valve_storage_heat_cool",
            datatype=DataType.INT16, icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True,
            enum_options={0: "Heizen", 1: "Kuehlen"}),
    _sensor(1112, "Umschaltventil Heizen/Warmwasser M63", "valve_heat_dhw",
            datatype=DataType.INT16, icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True,
            enum_options={0: "Heizen", 1: "Warmwasser"}),
    _sensor(1113, "Umschaltventil Waermequelle Heizen/Kuehlen M74", "valve_source_heat_cool",
            datatype=DataType.INT16, icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True,
            enum_options={0: "Heizen", 1: "Kuehlen"}),
    _sensor(1114, "Umschaltventil Solar Heizen/Warmwasser M78", "valve_solar_heat_dhw",
            datatype=DataType.INT16, icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True,
            enum_options={0: "Heizen", 1: "Warmwasser"}),
    _sensor(1115, "Umschaltventil Solar Speicher/Waermequelle M79", "valve_solar_storage_source",
            datatype=DataType.INT16, icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True,
            enum_options={0: "Speicher", 1: "Waermequelle"}),
    _sensor(1116, "Umschaltventil ISC Waermequelle/Kaeltespeicher M89", "valve_isc_source_cold",
            datatype=DataType.INT16, icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True,
            enum_options={0: "Waermequelle", 1: "Kaeltespeicher"}),
    _sensor(1117, "Umschaltventil ISC Speicher/Bypass M99", "valve_isc_storage_bypass",
            datatype=DataType.INT16, icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True,
            enum_options={0: "Speicher", 1: "Bypass"}),
    # --- Bivalenz ---
    _sensor(1124, "Bivalenz Betriebszustand", "bivalency_state", datatype=DataType.UCHAR,
            icon="mdi:heat-pump", entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    # --- Kaskade: verfuegbare Stufen (neu) ---
    _sensor(1147, "Kaskade Verfuegbare Stufen Heizen", "cascade_avail_stages_heat",
            datatype=DataType.UCHAR, entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1148, "Kaskade Verfuegbare Stufen Kuehlen", "cascade_avail_stages_cool",
            datatype=DataType.UCHAR, entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1149, "Kaskade Verfuegbare Stufen Warmwasser", "cascade_avail_stages_dhw",
            datatype=DataType.UCHAR, entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    # --- Kaskade: laufende Stufen ---
    _sensor(1150, "Kaskade Laufende Stufen Heizen", "cascade_running_stages_heat",
            datatype=DataType.UCHAR, icon="mdi:engine",
            entity_category=EntityCategory.DIAGNOSTIC),
    _sensor(1151, "Kaskade Laufende Stufen Kuehlen", "cascade_running_stages_cool",
            datatype=DataType.UCHAR,
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1152, "Kaskade Laufende Stufen Warmwasser", "cascade_running_stages_dhw",
            datatype=DataType.UCHAR,
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    # --- Kaskade: Temperaturen (read-only, Mehrkesselanlagen) ---
    _sensor(1200, "Kaskade Angeforderte Heiztemperatur", "cascade_req_heat_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1202, "Kaskade Angeforderte Kuehltemperatur", "cascade_req_cool_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1204, "Kaskade Angeforderte WW-Temperatur", "cascade_req_dhw_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1206, "Kaskade Gemittelte VL-Temp Heizen", "cascade_avg_flow_heat",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1208, "Kaskade Gemittelte VL-Temp Kuehlen", "cascade_avg_flow_cool",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1210, "Kaskade Gemittelte VL-Temp Warmwasser", "cascade_avg_flow_dhw",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(1392, "Feuchtesensor", "humidity",
            unit=PERCENTAGE, device_class="humidity"),
    _sensor(1690, "Externe Aussentemperatur", "outdoor_temp_ext",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1692, "Externe Feuchte", "humidity_ext",
            unit=PERCENTAGE, device_class="humidity"),
    # --- Waermemengen (lt. offiziellem IDM-YAML: 1750 = Gesamt!) ---
    _sensor(1748, "Waermemenge Heizen", "energy_heat_heating",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1750, "Waermemenge Gesamt", "energy_heat_total",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1752, "Waermemenge Kuehlen", "energy_heat_cooling",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1754, "Waermemenge Warmwasser", "energy_heat_dhw",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1756, "Waermemenge Abtauung", "energy_heat_defrost",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1758, "Waermemenge Passive Kuehlung", "energy_heat_passive_cooling",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1760, "Waermemenge Solar", "energy_heat_solar",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1762, "Waermemenge Elektroheizeinsatz", "energy_heat_electric",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    # --- Momentanleistung (war faelschlicherweise als "Maximale Leistung" deklariert) ---
    _sensor(1790, "Momentanleistung", "current_power_draw",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(1850, "Solar Kollektortemperatur", "solar_collector_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1852, "Solar Kollektorruecklauftemperatur", "solar_collector_return_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1854, "Solar Ladetemperatur", "solar_charge_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1857, "Solar WQ-Referenztemperatur/Pooltemperatur", "solar_reference_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1870, "ISC Ladetemperatur Kuehlen", "isc_charge_cooling_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1872, "ISC Rueckkuehltemperatur", "isc_recooling_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(4120, "Firmware Version Navigator", "firmware_version",
            datatype=DataType.UCHAR, icon="mdi:information",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _sensor(4122, "Aktuelle Leistungsaufnahme Waermepumpe", "power_draw_total",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(4126, "Thermische Leistung", "thermal_power",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(4128, "Waermemenge Gesamt (Durchflusssensor)", "energy_total_flow_sensor",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR,
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
]


def _hk_sensors(circuit: str) -> list[dict[str, Any]]:
    """Generate read-only sensors for a specific heating circuit (A–G).

    Address layout (n = circuit index 0–6, off = n*2 for 2-register FLOAT values):
      1350+off: Vorlauftemperatur (FLOAT)       1378+off: Sollvorlauftemperatur (FLOAT)
      1364+off: Raumtemperatur (FLOAT)           1393+n:   Betriebsart (UCHAR, via selects)
      1401+off: Raumsoll Heizen Normal (FLOAT)   1415+off: Raumsoll Heizen Eco (FLOAT)
      1429+off: Heizkurve (FLOAT)                1442+n:   Heizgrenze (UCHAR)
      1449+n:   Sollvorlauf Konstant (UCHAR)     1457+off: Raumsoll Kuehlen Normal (FLOAT)
      1471+off: Raumsoll Kuehlen Eco (FLOAT)     1484+n:   Kuehlgrenze (UCHAR)
      1491+n:   Sollvorlauf Kuehlen (UCHAR)      1498+n:   Aktive Betriebsart (UCHAR)
      1505+n:   Parallelverschiebung (UCHAR/INT8) 1650+off: Externe Raumtemperatur (FLOAT)
    """
    c = circuit.lower()
    C = circuit.upper()
    off = HK_OFFSET[c]
    idx = ord(c) - ord("a")

    return [
        # Live-Betriebstemperaturen (read-only)
        _sensor(1350 + off, f"Vorlauftemperatur HK {C}", f"flow_temp_hk_{c}",
                unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
                category="hk"),
        _sensor(1364 + off, f"Raumtemperatur HK {C}", f"room_temp_hk_{c}",
                unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
                category="hk"),
        _sensor(1378 + off, f"Sollvorlauftemperatur HK {C}", f"target_flow_temp_hk_{c}",
                unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
                category="hk"),
        # Sollwerte Heizen (auch beschreibbar via _hk_numbers)
        _sensor(1401 + off, f"Raumsoll Heizen Normal HK {C}", f"room_target_heat_normal_{c}",
                unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
                category="hk"),
        _sensor(1415 + off, f"Raumsoll Heizen Eco HK {C}", f"room_target_heat_eco_{c}",
                unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
                category="hk"),
        _sensor(1429 + off, f"Heizkurve HK {C}", f"heating_curve_{c}",
                icon="mdi:chart-line", category="hk"),
        # Sollwerte Kuehlen
        _sensor(1457 + off, f"Raumsoll Kuehlen Normal HK {C}", f"room_target_cool_normal_{c}",
                unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
                category="hk"),
        _sensor(1471 + off, f"Raumsoll Kuehlen Eco HK {C}", f"room_target_cool_eco_{c}",
                unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
                category="hk"),
        # Einzelregister-Sollwerte (1 Register)
        _sensor(1449 + idx, f"Vorlauftemperatur Soll Konstant HK {C}", f"const_flow_temp_{c}",
                datatype=DataType.UCHAR,
                unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
                category="hk"),
        _sensor(1505 + idx, f"Parallelverschiebung HK {C}", f"parallel_shift_{c}",
                datatype=DataType.INT8, unit="K", icon="mdi:arrow-expand-horizontal",
                category="hk"),
        _sensor(1498 + idx, f"Aktive Betriebsart HK {C}", f"active_mode_hk_{c}",
                datatype=DataType.UCHAR, icon="mdi:thermostat", category="hk",
                enum_options=CIRCUIT_MODE_OPTIONS),
        _sensor(1650 + off, f"Externe Raumtemperatur HK {C}", f"room_temp_ext_hk_{c}",
                unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS,
                category="hk"),
    ]

PV_SENSORS = [
    _sensor(74, "PV-Ueberschuss", "pv_surplus",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(76, "Leistung E-Heizstab", "electric_heater_power",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(78, "PV Produktion", "pv_production",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(82, "Hausverbrauch", "home_consumption",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(84, "Batterieentladung", "battery_discharge",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(86, "Batteriefuellstand", "battery_level",
            datatype=DataType.INT16, unit=PERCENTAGE,
            device_class=SensorDeviceClass.BATTERY),
    _sensor(1792, "Momentanleistung Solar", "current_power_solar",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
]

# ============================================================
# BINARY SENSORS (read-only on/off)
# ============================================================


def _binary_sensor(
    address: int,
    name: str,
    key: str,
    datatype: DataType = DataType.UCHAR,
    icon: str = "mdi:toggle-switch",
    device_class: str | None = None,
    entity_category: EntityCategory | None = None,
    disabled: bool = False,
) -> dict[str, Any]:
    return {
        "register": RegisterDef(
            address=address,
            datatype=datatype,
            name=key,
        ),
        "description": BinarySensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
            device_class=device_class,
            entity_category=entity_category,
            entity_registry_enabled_default=not disabled,
        ),
    }


BINARY_SENSORS = [
    # --- Stoerung ---
    _binary_sensor(1099, "Summenstoerung Waermepumpe", "total_fault",
            icon="mdi:alert-circle", device_class="problem"),
    # --- Verdichterstatus (laufend / nicht laufend) ---
    _binary_sensor(1100, "Status Verdichter 1", "state_compressor1", icon="mdi:engine",
            device_class="running",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _binary_sensor(1101, "Status Verdichter 2", "state_compressor2", icon="mdi:engine",
            device_class="running",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _binary_sensor(1102, "Status Verdichter 3", "state_compressor3", icon="mdi:engine",
            device_class="running",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    _binary_sensor(1103, "Status Verdichter 4", "state_compressor4", icon="mdi:engine",
            device_class="running",
            entity_category=EntityCategory.DIAGNOSTIC, disabled=True),
    # --- Anforderungsstatus (vom WP-Regler gemeldet, read-only) ---
    _binary_sensor(1091, "Heizanforderung aktiv", "heating_request_active",
            icon="mdi:fire"),
    _binary_sensor(1092, "Kuehlanforderung aktiv", "cooling_request_active",
            icon="mdi:snowflake"),
    _binary_sensor(1093, "Warmwasseranforderung aktiv", "dhw_request_active",
            icon="mdi:water-boiler"),
]

# ============================================================
# WRITABLE NUMBER VALUES (temperatures, setpoints, etc.)
# ============================================================


_NUMBER_DC_MAP = {
    UnitOfTemperature.CELSIUS: NumberDeviceClass.TEMPERATURE,
}


def _number(
    address: int,
    name: str,
    key: str,
    min_val: float,
    max_val: float,
    datatype: DataType = DataType.FLOAT,
    unit: str | None = None,
    step: float = 0.5,
    device_class: str | None = None,
    icon: str | None = None,
    mode: NumberMode = NumberMode.BOX,
) -> dict[str, Any]:
    resolved_dc = _NUMBER_DC_MAP.get(device_class, device_class)
    return {
        "register": RegisterDef(
            address=address,
            datatype=datatype,
            name=key,
            unit=unit,
            writable=True,
            min_val=min_val,
            max_val=max_val,
        ),
        "description": NumberEntityDescription(
            key=key,
            name=name,
            native_min_value=min_val,
            native_max_value=max_val,
            native_step=step,
            native_unit_of_measurement=unit,
            device_class=resolved_dc,
            icon=icon,
            mode=mode,
            entity_category=EntityCategory.CONFIG,
        ),
    }


DHW_NUMBERS = [
    _number(1032, "Warmwasser Solltemperatur", "dhw_target_set",
            35, 95, DataType.UCHAR, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1033, "Warmwasser Ein", "dhw_on_temp",
            30, 50, DataType.UCHAR, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1034, "Warmwasser Aus", "dhw_off_temp",
            46, 53, DataType.UCHAR, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
]

BIVALENCY_NUMBERS = [
    _number(1120, "2. WE Bivalenzpunkt 1", "bivalency_2we_1",
            -20, 40, DataType.INT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1121, "2. WE Bivalenzpunkt 2", "bivalency_2we_2",
            -20, 40, DataType.INT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1122, "3. WE Bivalenzpunkt 1", "bivalency_3we_1",
            -20, 40, DataType.INT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1123, "3. WE Bivalenzpunkt 2", "bivalency_3we_2",
            -20, 40, DataType.INT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
]

CASCADE_NUMBERS = [
    _number(1220, "Kaskade Min Heizen", "cascade_min_heat",
            0, 100, DataType.UCHAR, PERCENTAGE, 1),
    _number(1221, "Kaskade Max Heizen", "cascade_max_heat",
            0, 100, DataType.UCHAR, PERCENTAGE, 1),
    _number(1222, "Kaskade Min Kuehlen", "cascade_min_cool",
            0, 100, DataType.UCHAR, PERCENTAGE, 1),
    _number(1223, "Kaskade Max Kuehlen", "cascade_max_cool",
            0, 100, DataType.UCHAR, PERCENTAGE, 1),
    _number(1224, "Kaskade Min Warmwasser", "cascade_min_dhw",
            0, 100, DataType.UCHAR, PERCENTAGE, 1),
    _number(1225, "Kaskade Max Warmwasser", "cascade_max_dhw",
            0, 100, DataType.UCHAR, PERCENTAGE, 1),
    _number(1226, "Kaskade BV Heiz Parallel", "cascade_bv_heat_par",
            -20, 40, DataType.INT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1227, "Kaskade BV Heiz Alternativ", "cascade_bv_heat_alt",
            -20, 40, DataType.INT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1228, "Kaskade BV Kuehl Parallel", "cascade_bv_cool_par",
            -20, 40, DataType.INT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1229, "Kaskade BV Kuehl Alternativ", "cascade_bv_cool_alt",
            -20, 40, DataType.INT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1230, "Kaskade BV WW Parallel", "cascade_bv_dhw_par",
            -20, 40, DataType.INT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1231, "Kaskade BV WW Alternativ", "cascade_bv_dhw_alt",
            -20, 40, DataType.INT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
]

EXTERNAL_NUMBERS = [
    _number(1694, "Externe Anforderung Heizung", "ext_request_heat",
            20, 65, DataType.UCHAR, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1695, "Externe Anforderung Kuehlung", "ext_request_cool",
            10, 25, DataType.UCHAR, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
]


def _hk_numbers(circuit: str) -> list[dict[str, Any]]:
    idx = ord(circuit) - ord("a")
    base_heat_normal = 1401 + idx * 2
    base_heat_eco = 1415 + idx * 2
    base_curve = 1429 + idx * 2
    base_limit = 1442 + idx
    base_const_flow = 1449 + idx
    base_cool_normal = 1457 + idx * 2
    base_cool_eco = 1471 + idx * 2
    base_cool_limit = 1484 + idx
    base_cool_flow = 1491 + idx
    base_parallel = 1505 + idx
    prefix = f"hk_{circuit.lower()}"

    return [
        _number(
            base_heat_normal,
            f"Raumsoll Heizung Normal HK {circuit}",
            f"{prefix}_heat_normal",
            15, 30, DataType.FLOAT, UnitOfTemperature.CELSIUS, 0.5,
            device_class=UnitOfTemperature.CELSIUS,
        ),
        _number(
            base_heat_eco,
            f"Raumsoll Heizung Eco HK {circuit}",
            f"{prefix}_heat_eco",
            10, 25, DataType.FLOAT, UnitOfTemperature.CELSIUS, 0.5,
            device_class=UnitOfTemperature.CELSIUS,
        ),
        _number(
            base_curve,
            f"Heizkurve HK {circuit}",
            f"{prefix}_heating_curve",
            0.1, 3.5, DataType.FLOAT, step=0.1,
            icon="mdi:chart-line",
        ),
        _number(
            base_limit,
            f"Heizgrenze HK {circuit}",
            f"{prefix}_heat_limit",
            0, 50, DataType.UCHAR, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS,
        ),
        _number(
            base_const_flow,
            f"Sollvorlauf Konstant HK {circuit}",
            f"{prefix}_const_flow",
            20, 90, DataType.UCHAR, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS,
        ),
        _number(
            base_cool_normal,
            f"Raumsoll Kuehlung Normal HK {circuit}",
            f"{prefix}_cool_normal",
            15, 30, DataType.FLOAT, UnitOfTemperature.CELSIUS, 0.5,
            device_class=UnitOfTemperature.CELSIUS,
        ),
        _number(
            base_cool_eco,
            f"Raumsoll Kuehlung Eco HK {circuit}",
            f"{prefix}_cool_eco",
            15, 30, DataType.FLOAT, UnitOfTemperature.CELSIUS, 0.5,
            device_class=UnitOfTemperature.CELSIUS,
        ),
        _number(
            base_cool_limit,
            f"Kuehlgrenze HK {circuit}",
            f"{prefix}_cool_limit",
            0, 36, DataType.UCHAR, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS,
        ),
        _number(
            base_cool_flow,
            f"Sollvorlauf Kuehlung HK {circuit}",
            f"{prefix}_cool_flow",
            8, 30, DataType.UCHAR, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS,
        ),
        _number(
            base_parallel,
            f"Parallelverschiebung HK {circuit}",
            f"{prefix}_parallel_shift",
            -10, 30, DataType.INT8, "K", 1,
            icon="mdi:arrow-expand-horizontal",
        ),
    ]


# ============================================================
# WRITABLE SELECT VALUES (enums / modes)
# ============================================================


def _select(
    address: int,
    name: str,
    key: str,
    options: dict[int, str],
    datatype: DataType = DataType.UCHAR,
    icon: str | None = None,
) -> dict[str, Any]:
    return {
        "register": RegisterDef(
            address=address,
            datatype=datatype,
            name=key,
            writable=True,
            enum_options=options,
        ),
        "description": SelectEntityDescription(
            key=key,
            name=name,
            options=list(options.values()),
            icon=icon,
            entity_category=EntityCategory.CONFIG,
        ),
    }


SYSTEM_SELECTS = [
    _select(1005, "Betriebsart System", "system_mode", SYSTEM_MODE_OPTIONS,
            icon="mdi:power-settings"),
]

SOLAR_SELECTS = [
    _select(1856, "Solar Betriebsart", "solar_mode", SOLAR_MODE_OPTIONS,
            icon="mdi:solar-power"),
    _select(1874, "ISC Modus", "isc_mode", ISC_MODE_OPTIONS,
            icon="mdi:sync"),
]


def _hk_selects(circuit: str) -> list[dict[str, Any]]:
    idx = ord(circuit) - ord("a")
    base = 1393 + idx
    prefix = f"hk_{circuit.lower()}"
    return [
        _select(
            base,
            f"Betriebsart HK {circuit}",
            f"{prefix}_mode",
            CIRCUIT_MODE_OPTIONS,
            icon="mdi:thermostat",
        ),
    ]


# ============================================================
# WRITABLE SWITCH VALUES (on/off booleans)
# ============================================================


def _switch(
    address: int,
    name: str,
    key: str,
    datatype: DataType = DataType.BOOL,
    icon: str = "mdi:toggle-switch",
) -> dict[str, Any]:
    return {
        "register": RegisterDef(
            address=address,
            datatype=datatype,
            name=key,
            writable=True,
        ),
        "description": SwitchEntityDescription(
            key=key,
            name=name,
            icon=icon,
        ),
    }


GLT_SWITCHES = [
    _switch(1710, "Anforderung Heizen", "glt_request_heating",
            icon="mdi:fire"),
    _switch(1711, "Anforderung Kuehlen", "glt_request_cooling",
            icon="mdi:snowflake"),
    _switch(1712, "Anforderung Warmwasserladung", "glt_request_dhw",
            icon="mdi:water-boiler"),
    _switch(1713, "Einmalige WW-Ladung", "glt_single_dhw",
            icon="mdi:water-plus"),
]

# ============================================================
# ZONE MODULE SENSORS
# ============================================================

# Zonenmodul-Adressen lt. offiziellem IDM-YAML:
#   Zone n (1-basiert) beginnt bei 2000 + 65*(n-1)
#   Offset innerhalb der Zone:
#     +0: Modus Heizen/Kühlen (UCHAR, RO)
#     +1: Entfeuchtungsausgang (UCHAR, RO)
#     +2 + r*7: Raumtemperatur Raum r (FLOAT, 2 Reg)
#     +4 + r*7: Raumsolltemperatur Raum r (FLOAT, 2 Reg, RW)
#     +6 + r*7: Raumfeuchte Raum r (UCHAR)
#     +7 + r*7: Betriebsart Raum r (UCHAR, RW)
#     +8 + r*7: Status Relais Raum r (UCHAR, RO)
#     +64: Status Relais Raum 9 (optional)
ZONE_BASE_ADDRESSES = [2000 + 65 * i for i in range(10)]


def _zone_sensors(zone_idx: int, room_count: int) -> list[dict[str, Any]]:
    if zone_idx >= len(ZONE_BASE_ADDRESSES):
        return []

    base = ZONE_BASE_ADDRESSES[zone_idx]
    # Zone mode is read-only per IDM YAML (base+0)
    sensors = [
        _sensor(
            base,
            f"Zone {zone_idx + 1} Betriebsart",
            f"zone{zone_idx + 1}_mode",
            datatype=DataType.UCHAR,
            icon="mdi:thermostat",
            category="zone",
            enum_options={0: "Kuehlung", 1: "Heizung"},
        )
    ]
    for room in range(room_count):
        sensors.append(_sensor(
            base + 2 + room * 7,
            f"Zone {zone_idx + 1} Raum {room + 1} Temperatur",
            f"zone{zone_idx + 1}_room{room + 1}_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            category="zone",
        ))
        sensors.append(_sensor(
            base + 4 + room * 7,
            f"Zone {zone_idx + 1} Raum {room + 1} Solltemperatur",
            f"zone{zone_idx + 1}_room{room + 1}_target",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            category="zone",
        ))
        sensors.append(_sensor(
            base + 6 + room * 7,
            f"Zone {zone_idx + 1} Raum {room + 1} Feuchte",
            f"zone{zone_idx + 1}_room{room + 1}_humidity",
            datatype=DataType.UCHAR,
            unit=PERCENTAGE,
            icon="mdi:water-percent",
            category="zone",
        ))

    return sensors


def _zone_binary_sensors(zone_idx: int, room_count: int) -> list[dict[str, Any]]:
    if zone_idx >= len(ZONE_BASE_ADDRESSES):
        return []

    base = ZONE_BASE_ADDRESSES[zone_idx]
    sensors = [
        # Entfeuchtungsausgang (zone_base+1, lt. IDM-YAML)
        _binary_sensor(
            base + 1,
            f"Zone {zone_idx + 1} Entfeuchtungsausgang",
            f"zone{zone_idx + 1}_dehumidifier",
            icon="mdi:water-off",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ]
    for room in range(room_count):
        sensors.append(_binary_sensor(
            base + 8 + room * 7,
            f"Zone {zone_idx + 1} Raum {room + 1} Relais",
            f"zone{zone_idx + 1}_room{room + 1}_relay",
            icon="mdi:electric-switch",
        ))
    return sensors


def _zone_numbers(zone_idx: int, room_count: int) -> list[dict[str, Any]]:
    if zone_idx >= len(ZONE_BASE_ADDRESSES):
        return []

    base = ZONE_BASE_ADDRESSES[zone_idx]
    numbers = []
    for room in range(room_count):
        numbers.append(_number(
            base + 4 + room * 7,
            f"Zone {zone_idx + 1} Raum {room + 1} Solltemperatur",
            f"zone{zone_idx + 1}_room{room + 1}_target_set",
            5, 35, DataType.FLOAT, UnitOfTemperature.CELSIUS, 0.5,
            device_class=UnitOfTemperature.CELSIUS,
        ))
    return numbers


def _zone_selects(zone_idx: int, room_count: int) -> list[dict[str, Any]]:
    if zone_idx >= len(ZONE_BASE_ADDRESSES):
        return []

    base = ZONE_BASE_ADDRESSES[zone_idx]
    selects = []
    # Raum-Betriebsarten (RW)
    for room in range(room_count):
        selects.append(_select(
            base + 7 + room * 7,
            f"Zone {zone_idx + 1} Raum {room + 1} Betriebsart",
            f"zone{zone_idx + 1}_room{room + 1}_mode",
            ROOM_MODE_OPTIONS,
            icon="mdi:thermostat",
        ))

    return selects


# ============================================================
# PUBLIC FUNCTIONS - Collect all register descriptions
# ============================================================


def get_all_sensor_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    descriptions = list(SYSTEM_SENSORS) + list(PV_SENSORS)
    for circuit in circuits:
        descriptions.extend(_hk_sensors(circuit))
    for z in range(zone_count):
        rooms = zone_rooms.get(z, 1)
        descriptions.extend(_zone_sensors(z, rooms))
    return descriptions


def get_all_binary_sensor_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    descriptions = list(BINARY_SENSORS)
    for z in range(zone_count):
        rooms = zone_rooms.get(z, 1)
        descriptions.extend(_zone_binary_sensors(z, rooms))
    return descriptions


def get_all_number_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    descriptions = list(DHW_NUMBERS) + list(BIVALENCY_NUMBERS)
    if enable_cascade:
        descriptions.extend(CASCADE_NUMBERS)
    descriptions.extend(EXTERNAL_NUMBERS)
    for circuit in circuits:
        descriptions.extend(_hk_numbers(circuit))
    for z in range(zone_count):
        rooms = zone_rooms.get(z, 1)
        descriptions.extend(_zone_numbers(z, rooms))
    return descriptions


def get_all_select_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    descriptions = list(SYSTEM_SELECTS) + list(SOLAR_SELECTS)
    for circuit in circuits:
        descriptions.extend(_hk_selects(circuit))
    for z in range(zone_count):
        rooms = zone_rooms.get(z, 1)
        descriptions.extend(_zone_selects(z, rooms))
    return descriptions


def get_all_switch_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    return list(GLT_SWITCHES)


def collect_all_registers(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[RegisterDef]:
    """Collect all unique registers for batch reading."""
    all_descriptions = (
        get_all_sensor_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
        + get_all_binary_sensor_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
        + get_all_number_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
        + get_all_select_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
        + get_all_switch_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
    )

    seen: dict[int, RegisterDef] = {}
    for desc in all_descriptions:
        reg: RegisterDef = desc["register"]
        if reg.address not in seen:
            seen[reg.address] = reg

    return list(seen.values())
