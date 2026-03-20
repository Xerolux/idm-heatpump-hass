"""Register definitions for IDM Navigator 2.0 heat pumps.

All Modbus register addresses, data types, units, and read/write capabilities
are defined here. Registers are organized by functional group and provide
entity descriptions for Home Assistant platforms.
"""

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
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
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)

from .const import (
    CIRCUIT_MODE_OPTIONS,
    ROOM_MODE_OPTIONS,
    SOLAR_MODE_OPTIONS,
    SYSTEM_MODE_OPTIONS,
)
from .modbus_client import DataType, RegisterDef

_LOGGER = logging.getLogger(__name__)

# ============================================================
# READ-ONLY SENSORS
# ============================================================


def _sensor(
    address: int,
    name: str,
    key: str,
    datatype: DataType = DataType.FLOAT,
    unit: str | None = None,
    device_class=None,
    icon: str | None = None,
    category: str = "system",
) -> dict:
    return {
        "register": RegisterDef(
            address=address,
            datatype=datatype,
            name=key,
            unit=unit,
        ),
        "description": SensorEntityDescription(
            key=key,
            name=name,
            native_unit_of_measurement=unit,
            device_class=device_class,
            icon=icon,
        ),
        "category": category,
    }


SYSTEM_SENSORS = [
    _sensor(1000, "Aussentemperatur", "outdoor_temp", unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS),
    _sensor(1002, "Gemittelte Aussentemperatur", "outdoor_temp_avg",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1004, "Interne Meldung", "internal_message", datatype=DataType.UCHAR,
            icon="mdi:message-alert"),
    _sensor(1006, "Smart Grid Status", "smart_grid_status", datatype=DataType.UCHAR,
            icon="mdi:transmission-tower"),
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
    _sensor(1036, "Warmwasser Solltemperatur", "dhw_target_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1050, "Fehlercode", "error_code", datatype=DataType.UCHAR,
            icon="mdi:alert-circle"),
    _sensor(1052, "Stoermeldungen", "fault_message", datatype=DataType.UCHAR,
            icon="mdi:alert"),
    _sensor(1090, "Waermepumpenstatus", "heatpump_status", datatype=DataType.UCHAR,
            icon="mdi:heat-pump"),
    _sensor(1104, "Status Ladepumpe", "charge_pump_status", datatype=DataType.UCHAR,
            icon="mdi:pump"),
    _sensor(1105, "Status Sole-/Zwischenkreispumpe", "brine_pump_status",
            datatype=DataType.UCHAR, icon="mdi:pump"),
    _sensor(1106, "Status Waermequellen-/Grundwasserpumpe", "source_pump_status",
            datatype=DataType.UCHAR, icon="mdi:pump"),
    _sensor(1107, "Status EVT-Sollwert Istwert", "evt_status",
            datatype=DataType.UCHAR, icon="mdi:thermostat"),
    _sensor(1108, "Statusadditional Pumpentyp", "additional_pump_status",
            datatype=DataType.UCHAR, icon="mdi:pump"),
    _sensor(1109, "Statusadditional Pumpentyp 2", "additional_pump2_status",
            datatype=DataType.UCHAR, icon="mdi:pump"),
    _sensor(1110, "Umschaltventil Heizung/Kuehlung", "valve_heating_cooling",
            datatype=DataType.UCHAR, icon="mdi:valve"),
    _sensor(1111, "Umschaltventil Heizung/Warmwasser", "valve_heating_dhw",
            datatype=DataType.UCHAR, icon="mdi:valve"),
    _sensor(1112, "Umschaltventil Speicher/Waermequelle", "valve_storage_source",
            datatype=DataType.UCHAR, icon="mdi:valve"),
    _sensor(1113, "Umschaltventil Waermequelle/Kaeltespeicher", "valve_source_cold",
            datatype=DataType.UCHAR, icon="mdi:valve"),
    _sensor(1114, "Umschaltventil Speicher/Bypass", "valve_storage_bypass",
            datatype=DataType.UCHAR, icon="mdi:valve"),
    _sensor(1115, "Umschaltventil HK1", "valve_hk1", datatype=DataType.UCHAR,
            icon="mdi:valve"),
    _sensor(1116, "Umschaltventil HK2", "valve_hk2", datatype=DataType.UCHAR,
            icon="mdi:valve"),
    _sensor(1117, "Umschaltventil HK3", "valve_hk3", datatype=DataType.UCHAR,
            icon="mdi:valve"),
    _sensor(1150, "Laufender Verdichter Stufe", "compressor_stage_running",
            datatype=DataType.UCHAR, icon="mdi:engine"),
    _sensor(1151, "Verdichter 1 Stufe", "compressor1_stage", datatype=DataType.UCHAR),
    _sensor(1152, "Verdichter 2 Stufe", "compressor2_stage", datatype=DataType.UCHAR),
    _sensor(1160, "Aktuelle Vorlauftemperatur HK A", "flow_temp_hk_a",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1162, "Aktuelle Vorlauftemperatur HK B", "flow_temp_hk_b",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1164, "Aktuelle Vorlauftemperatur HK C", "flow_temp_hk_c",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1166, "Aktuelle Vorlauftemperatur HK D", "flow_temp_hk_d",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1168, "Aktuelle Vorlauftemperatur HK E", "flow_temp_hk_e",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1170, "Aktuelle Vorlauftemperatur HK F", "flow_temp_hk_f",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1172, "Aktuelle Vorlauftemperatur HK G", "flow_temp_hk_g",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1180, "Raumtemperatur HK A", "room_temp_hk_a",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1182, "Raumtemperatur HK B", "room_temp_hk_b",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1184, "Raumtemperatur HK C", "room_temp_hk_c",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1186, "Raumtemperatur HK D", "room_temp_hk_d",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1188, "Raumtemperatur HK E", "room_temp_hk_e",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1190, "Raumtemperatur HK F", "room_temp_hk_f",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1192, "Raumtemperatur HK G", "room_temp_hk_g",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1200, "Sollvorlauftemperatur HK A", "target_flow_temp_hk_a",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1202, "Sollvorlauftemperatur HK B", "target_flow_temp_hk_b",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1204, "Sollvorlauftemperatur HK C", "target_flow_temp_hk_c",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1206, "Sollvorlauftemperatur HK D", "target_flow_temp_hk_d",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1208, "Sollvorlauftemperatur HK E", "target_flow_temp_hk_e",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1210, "Sollvorlauftemperatur HK F", "target_flow_temp_hk_f",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1212, "Sollvorlauftemperatur HK G", "target_flow_temp_hk_g",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1240, "Bivalenzpunkt 1", "bivalency_point_1",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1241, "Bivalenzpunkt 2", "bivalency_point_2",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1250, "Aktuelle Leistung Heizen", "current_power_heating",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(1252, "Aktuelle Leistung Kuehlen", "current_power_cooling",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(1254, "Aktuelle Leistung Warmwasser", "current_power_dhw",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(1260, "Minimale Leistung Heizen", "min_power_heating",
            unit=PERCENTAGE, icon="mdi:tune-variant"),
    _sensor(1261, "Maximale Leistung Heizen", "max_power_heating",
            unit=PERCENTAGE, icon="mdi:tune-variant"),
    _sensor(1262, "Minimale Leistung Kuehlen", "min_power_cooling",
            unit=PERCENTAGE, icon="mdi:tune-variant"),
    _sensor(1263, "Maximale Leistung Kuehlen", "max_power_cooling",
            unit=PERCENTAGE, icon="mdi:tune-variant"),
    _sensor(1264, "Minimale Leistung Warmwasser", "min_power_dhw",
            unit=PERCENTAGE, icon="mdi:tune-variant"),
    _sensor(1265, "Maximale Leistung Warmwasser", "max_power_dhw",
            unit=PERCENTAGE, icon="mdi:tune-variant"),
    _sensor(1350, "Raumsolltemperatur Heizung Normal HK A", "room_target_heat_normal_a",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1352, "Raumsolltemperatur Heizung Normal HK B", "room_target_heat_normal_b",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1354, "Raumsolltemperatur Heizung Normal HK C", "room_target_heat_normal_c",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1356, "Raumsolltemperatur Heizung Normal HK D", "room_target_heat_normal_d",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1358, "Raumsolltemperatur Heizung Normal HK E", "room_target_heat_normal_e",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1360, "Raumsolltemperatur Heizung Normal HK F", "room_target_heat_normal_f",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1362, "Raumsolltemperatur Heizung Normal HK G", "room_target_heat_normal_g",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1364, "Raumsolltemperatur Heizung Eco HK A", "room_target_heat_eco_a",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1366, "Raumsolltemperatur Heizung Eco HK B", "room_target_heat_eco_b",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1368, "Raumsolltemperatur Heizung Eco HK C", "room_target_heat_eco_c",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1370, "Raumsolltemperatur Heizung Eco HK D", "room_target_heat_eco_d",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1372, "Raumsolltemperatur Heizung Eco HK E", "room_target_heat_eco_e",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1374, "Raumsolltemperatur Heizung Eco HK F", "room_target_heat_eco_f",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1376, "Raumsolltemperatur Heizung Eco HK G", "room_target_heat_eco_g",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1378, "Heizkurve HK A", "heating_curve_a",
            icon="mdi:chart-line"),
    _sensor(1380, "Heizkurve HK B", "heating_curve_b",
            icon="mdi:chart-line"),
    _sensor(1382, "Heizkurve HK C", "heating_curve_c",
            icon="mdi:chart-line"),
    _sensor(1384, "Heizkurve HK D", "heating_curve_d",
            icon="mdi:chart-line"),
    _sensor(1386, "Heizkurve HK E", "heating_curve_e",
            icon="mdi:chart-line"),
    _sensor(1388, "Heizkurve HK F", "heating_curve_f",
            icon="mdi:chart-line"),
    _sensor(1390, "Heizkurve HK G", "heating_curve_g",
            icon="mdi:chart-line"),
    _sensor(1457, "Raumsolltemperatur Kuehlung Normal HK A", "room_target_cool_normal_a",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1459, "Raumsolltemperatur Kuehlung Normal HK B", "room_target_cool_normal_b",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1461, "Raumsolltemperatur Kuehlung Normal HK C", "room_target_cool_normal_c",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1463, "Raumsolltemperatur Kuehlung Normal HK D", "room_target_cool_normal_d",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1465, "Raumsolltemperatur Kuehlung Normal HK E", "room_target_cool_normal_e",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1467, "Raumsolltemperatur Kuehlung Normal HK F", "room_target_cool_normal_f",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1469, "Raumsolltemperatur Kuehlung Normal HK G", "room_target_cool_normal_g",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1471, "Raumsolltemperatur Kuehlung Eco HK A", "room_target_cool_eco_a",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1473, "Raumsolltemperatur Kuehlung Eco HK B", "room_target_cool_eco_b",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1475, "Raumsolltemperatur Kuehlung Eco HK C", "room_target_cool_eco_c",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1477, "Raumsolltemperatur Kuehlung Eco HK D", "room_target_cool_eco_d",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1479, "Raumsolltemperatur Kuehlung Eco HK E", "room_target_cool_eco_e",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1481, "Raumsolltemperatur Kuehlung Eco HK F", "room_target_cool_eco_f",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1483, "Raumsolltemperatur Kuehlung Eco HK G", "room_target_cool_eco_g",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1505, "Parallelverschiebung HK A", "parallel_shift_a",
            icon="mdi:arrow-expand-horizontal"),
    _sensor(1506, "Parallelverschiebung HK B", "parallel_shift_b",
            icon="mdi:arrow-expand-horizontal"),
    _sensor(1507, "Parallelverschiebung HK C", "parallel_shift_c",
            icon="mdi:arrow-expand-horizontal"),
    _sensor(1508, "Parallelverschiebung HK D", "parallel_shift_d",
            icon="mdi:arrow-expand-horizontal"),
    _sensor(1509, "Parallelverschiebung HK E", "parallel_shift_e",
            icon="mdi:arrow-expand-horizontal"),
    _sensor(1510, "Parallelverschiebung HK F", "parallel_shift_f",
            icon="mdi:arrow-expand-horizontal"),
    _sensor(1511, "Parallelverschiebung HK G", "parallel_shift_g",
            icon="mdi:arrow-expand-horizontal"),
    _sensor(1550, "Aktive Betriebsart HK A", "active_mode_hk_a",
            datatype=DataType.UCHAR, icon="mdi:thermostat"),
    _sensor(1551, "Aktive Betriebsart HK B", "active_mode_hk_b",
            datatype=DataType.UCHAR, icon="mdi:thermostat"),
    _sensor(1552, "Aktive Betriebsart HK C", "active_mode_hk_c",
            datatype=DataType.UCHAR, icon="mdi:thermostat"),
    _sensor(1553, "Aktive Betriebsart HK D", "active_mode_hk_d",
            datatype=DataType.UCHAR, icon="mdi:thermostat"),
    _sensor(1554, "Aktive Betriebsart HK E", "active_mode_hk_e",
            datatype=DataType.UCHAR, icon="mdi:thermostat"),
    _sensor(1555, "Aktive Betriebsart HK F", "active_mode_hk_f",
            datatype=DataType.UCHAR, icon="mdi:thermostat"),
    _sensor(1556, "Aktive Betriebsart HK G", "active_mode_hk_g",
            datatype=DataType.UCHAR, icon="mdi:thermostat"),
    _sensor(1600, "Vorlauftemperatur Soll Konstant HK A", "const_flow_temp_a",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1601, "Vorlauftemperatur Soll Konstant HK B", "const_flow_temp_b",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1602, "Vorlauftemperatur Soll Konstant HK C", "const_flow_temp_c",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1603, "Vorlauftemperatur Soll Konstant HK D", "const_flow_temp_d",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1604, "Vorlauftemperatur Soll Konstant HK E", "const_flow_temp_e",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1605, "Vorlauftemperatur Soll Konstant HK F", "const_flow_temp_f",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1606, "Vorlauftemperatur Soll Konstant HK G", "const_flow_temp_g",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1748, "Energiezaehler Heizen", "energy_heating",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1750, "Energiezaehler Kuehlen", "energy_cooling",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1752, "Energiezaehler Warmwasser", "energy_dhw",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1754, "Energiezaehler Abtauen", "energy_defrost",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1756, "Energiezaehler Solar", "energy_solar",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1758, "Energiezaehler Elektrisch", "energy_electric",
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=UnitOfEnergy.KILO_WATT_HOUR),
    _sensor(1790, "Aktuelle Leistungsaufnahme", "current_power_draw",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(1792, "Leistungsaufnahme Gesamt", "total_power_draw",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(1850, "Solar Kollektortemperatur", "solar_collector_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1852, "Solar Speichertemperatur", "solar_storage_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1854, "Solar Betriebsart", "solar_mode", datatype=DataType.UCHAR,
            icon="mdi:solar-power"),
    _sensor(1856, "Solar Isttemperatur", "solar_current_temp",
            unit=UnitOfTemperature.CELSIUS, device_class=UnitOfTemperature.CELSIUS),
    _sensor(1870, "ISC Modus", "isc_mode", datatype=DataType.UCHAR,
            icon="mdi:heat-pump-outline"),
    _sensor(1872, "ISC Status", "isc_status", datatype=DataType.UCHAR,
            icon="mdi:information"),
    _sensor(4108, "Maximale Leistung WP", "max_power_heatpump",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
    _sensor(4120, "Firmware Version Navigator", "firmware_version",
            datatype=DataType.UCHAR, icon="mdi:information"),
    _sensor(4122, "Aktuelle Leistungsaufnahme Gesamt", "power_draw_total",
            unit=UnitOfPower.KILO_WATT, device_class=UnitOfPower.KILO_WATT),
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
            datatype=DataType.UCHAR, unit=PERCENTAGE,
            icon="mdi:battery"),
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
    device_class=None,
) -> dict:
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
        ),
    }


BINARY_SENSORS = [
    _binary_sensor(1054, "Stoerung", "fault", icon="mdi:alert-circle"),
    _binary_sensor(1056, "Verdichter 1", "compressor1", icon="mdi:engine"),
    _binary_sensor(1057, "Verdichter 2", "compressor2", icon="mdi:engine"),
    _binary_sensor(1058, "Verdichter 3", "compressor3", icon="mdi:engine"),
    _binary_sensor(1059, "Verdichter 4", "compressor4", icon="mdi:engine"),
    _binary_sensor(1060, "Anforderung Heizen", "request_heating",
            icon="mdi:fire"),
    _binary_sensor(1061, "Anforderung Kuehlen", "request_cooling",
            icon="mdi:snowflake"),
    _binary_sensor(1062, "Anforderung Warmwasser", "request_dhw",
            icon="mdi:water-boiler"),
    _binary_sensor(1064, "Abtauung", "defrost", icon="mdi:snowflake-melt"),
]

# ============================================================
# WRITABLE NUMBER VALUES (temperatures, setpoints, etc.)
# ============================================================


def _number(
    address: int,
    name: str,
    key: str,
    min_val: float,
    max_val: float,
    datatype: DataType = DataType.FLOAT,
    unit: str | None = None,
    step: float = 0.5,
    device_class=None,
    icon: str | None = None,
    mode: NumberMode = NumberMode.BOX,
) -> dict:
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
            device_class=device_class,
            icon=icon,
            mode=mode,
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

BIVALency_NUMBERS = [
    _number(1120, "2. WE Bivalenzpunkt 1", "bivalency_2we_1",
            -20, 40, DataType.UINT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1121, "2. WE Bivalenzpunkt 2", "bivalency_2we_2",
            -20, 40, DataType.UINT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1122, "3. WE Bivalenzpunkt 1", "bivalency_3we_1",
            -20, 40, DataType.UINT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1123, "3. WE Bivalenzpunkt 2", "bivalency_3we_2",
            -20, 40, DataType.UINT16, UnitOfTemperature.CELSIUS, 1,
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
            -20, 40, DataType.UINT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1227, "Kaskade BV Heiz Alternativ", "cascade_bv_heat_alt",
            -20, 40, DataType.UINT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1228, "Kaskade BV Kuehl Parallel", "cascade_bv_cool_par",
            -20, 40, DataType.UINT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1229, "Kaskade BV Kuehl Alternativ", "cascade_bv_cool_alt",
            -20, 40, DataType.UINT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1230, "Kaskade BV WW Parallel", "cascade_bv_dhw_par",
            -20, 40, DataType.UINT16, UnitOfTemperature.CELSIUS, 1,
            device_class=UnitOfTemperature.CELSIUS),
    _number(1231, "Kaskade BV WW Alternativ", "cascade_bv_dhw_alt",
            -20, 40, DataType.UINT16, UnitOfTemperature.CELSIUS, 1,
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


def _hk_numbers(circuit: str) -> list[dict]:
    idx = ord(circuit) - ord("A")
    base_mode = 1393 + idx
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
            -10, 30, DataType.UCHAR, "K", 1,
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
) -> dict:
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
        ),
    }


SYSTEM_SELECTS = [
    _select(1005, "Betriebsart System", "system_mode", SYSTEM_MODE_OPTIONS,
            icon="mdi:power-settings"),
]

SOLAR_SELECTS = [
    _select(1856, "Solar Betriebsart", "solar_mode", SOLAR_MODE_OPTIONS,
            icon="mdi:solar-power"),
]


def _hk_selects(circuit: str) -> list[dict]:
    idx = ord(circuit) - ord("A")
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
) -> dict:
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

ZONE_BASE_ADDRESSES = [2000, 2067, 2130, 2193, 2256, 2319, 2382, 2445, 2508, 2571]
ZONE_MODE_ADDRESSES = [2059, 2126, 2189, 2252, 2315, 2378, 2441, 2504, 2567, 2630]


def _zone_sensors(zone_idx: int, room_count: int) -> list[dict]:
    if zone_idx >= len(ZONE_BASE_ADDRESSES):
        return []

    base = ZONE_BASE_ADDRESSES[zone_idx]
    sensors = []
    for room in range(room_count):
        offset = room * 7
        room_addr_temp = base + offset + 0
        room_addr_target = base + offset + 2
        room_addr_humidity = base + offset + 4

        sensors.append(_sensor(
            room_addr_temp,
            f"Zone {zone_idx + 1} Raum {room + 1} Temperatur",
            f"zone{zone_idx + 1}_room{room + 1}_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            category="zone",
        ))
        sensors.append(_sensor(
            room_addr_target,
            f"Zone {zone_idx + 1} Raum {room + 1} Solltemperatur",
            f"zone{zone_idx + 1}_room{room + 1}_target",
            unit=UnitOfTemperature.CELSIUS,
            device_class=UnitOfTemperature.CELSIUS,
            category="zone",
        ))
        sensors.append(_sensor(
            room_addr_humidity,
            f"Zone {zone_idx + 1} Raum {room + 1} Feuchte",
            f"zone{zone_idx + 1}_room{room + 1}_humidity",
            datatype=DataType.UCHAR,
            unit=PERCENTAGE,
            icon="mdi:water-percent",
            category="zone",
        ))

    return sensors


def _zone_binary_sensors(zone_idx: int, room_count: int) -> list[dict]:
    if zone_idx >= len(ZONE_BASE_ADDRESSES):
        return []

    base = ZONE_BASE_ADDRESSES[zone_idx]
    sensors = []
    for room in range(room_count):
        offset = room * 7
        relay_addr = base + offset + 6
        sensors.append(_binary_sensor(
            relay_addr,
            f"Zone {zone_idx + 1} Raum {room + 1} Relais",
            f"zone{zone_idx + 1}_room{room + 1}_relay",
            icon="mdi:electric-switch",
        ))
    return sensors


def _zone_numbers(zone_idx: int, room_count: int) -> list[dict]:
    if zone_idx >= len(ZONE_BASE_ADDRESSES):
        return []

    base = ZONE_BASE_ADDRESSES[zone_idx]
    numbers = []
    for room in range(room_count):
        offset = room * 7
        target_addr = base + offset + 2
        numbers.append(_number(
            target_addr,
            f"Zone {zone_idx + 1} Raum {room + 1} Solltemperatur",
            f"zone{zone_idx + 1}_room{room + 1}_target_set",
            5, 35, DataType.FLOAT, UnitOfTemperature.CELSIUS, 0.5,
            device_class=UnitOfTemperature.CELSIUS,
        ))
    return numbers


def _zone_selects(zone_idx: int, room_count: int) -> list[dict]:
    if zone_idx >= len(ZONE_MODE_ADDRESSES):
        return []

    selects = []
    mode_addr = ZONE_MODE_ADDRESSES[zone_idx]
    selects.append(_select(
        mode_addr,
        f"Zone {zone_idx + 1} Betriebsart",
        f"zone{zone_idx + 1}_mode",
        {0: "Kuehlung", 1: "Heizung"},
        icon="mdi:thermostat",
    ))

    for room in range(room_count):
        room_mode_addr = mode_addr + 1 + room
        selects.append(_select(
            room_mode_addr,
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
) -> list[dict]:
    descriptions = list(SYSTEM_SENSORS) + list(PV_SENSORS)
    for circuit in circuits:
        descriptions.extend(_hk_numbers(circuit))
        descriptions.extend(_hk_selects(circuit))
    for z in range(zone_count):
        rooms = zone_rooms.get(z, 1)
        descriptions.extend(_zone_sensors(z, rooms))
    return descriptions


def get_all_binary_sensor_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
) -> list[dict]:
    descriptions = list(BINARY_SENSORS)
    for z in range(zone_count):
        rooms = zone_rooms.get(z, 1)
        descriptions.extend(_zone_binary_sensors(z, rooms))
    return descriptions


def get_all_number_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
) -> list[dict]:
    descriptions = list(DHW_NUMBERS) + list(BIVALency_NUMBERS)
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
) -> list[dict]:
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
) -> list[dict]:
    return list(GLT_SWITCHES)


def collect_all_registers(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
) -> list[RegisterDef]:
    """Collect all unique registers for batch reading."""
    all_descriptions = (
        get_all_sensor_descriptions(circuits, zone_count, zone_rooms)
        + get_all_binary_sensor_descriptions(circuits, zone_count, zone_rooms)
        + get_all_number_descriptions(circuits, zone_count, zone_rooms)
        + get_all_select_descriptions(circuits, zone_count, zone_rooms)
        + get_all_switch_descriptions(circuits, zone_count, zone_rooms)
    )

    seen: dict[int, RegisterDef] = {}
    for desc in all_descriptions:
        reg: RegisterDef = desc["register"]
        if reg.address not in seen:
            seen[reg.address] = reg

    return list(seen.values())
