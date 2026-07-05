"""Constants for IDM Heatpump integration."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import enum

try:
    import idm_heatpump as idm_api
except ImportError:
    RECOMMENDED_WEB_SCAN_INTERVAL = 30.0
else:
    RECOMMENDED_WEB_SCAN_INTERVAL = float(getattr(idm_api, "RECOMMENDED_WEB_SCAN_INTERVAL", 30.0))

DOMAIN: str = "idm_heatpump"
NAME: str = "IDM Heatpump"
MANUFACTURER: str = "iDM Energiesysteme"
MODEL: str = "Navigator 2.0 / 10"
MODEL_ZONE: str = "Navigator Pro Einzelraumregelung"

CONF_HOST: str = "host"
CONF_PORT: str = "port"
CONF_SLAVE_ID: str = "slave_id"
CONF_NAME: str = "name"
CONF_SCAN_INTERVAL: str = "scan_interval"
CONF_HEATING_CIRCUITS: str = "heating_circuits"
CONF_ZONE_COUNT: str = "zone_count"
CONF_ZONE_ROOMS: str = "zone_rooms"
CONF_HIDE_UNUSED: str = "hide_unused_registers"
CONF_TECHNICIAN_CODES: str = "technician_codes"
CONF_ENABLE_CASCADE: str = "enable_cascade"
CONF_MODBUS_PROXY: str = "modbus_proxy"
CONF_WEB_PIN: str = "web_pin"
CONF_WEB_HOST: str = "web_host"
CONF_WEB_ENABLED: str = "web_extra_data"
CONF_WEB_SCAN_INTERVAL: str = "web_scan_interval"
CONF_DETECTED_NAVIGATOR_VERSION: str = "detected_navigator_version"
CONF_DETECTED_SOFTWARE_VERSION: str = "detected_software_version"
CONF_ROOM_TEMP_FORWARDING: str = "room_temp_forwarding"
CONF_ROOM_TEMP_FORWARDING_INTERVAL: str = "room_temp_forwarding_interval"
CONF_ROOM_TEMP_FORWARDING_TOLERANCE: str = "room_temp_forwarding_tolerance"
CONF_ROOM_TEMP_FORWARDING_ENTITIES: str = "room_temp_forwarding_entities"
CONF_WEB_ONLY: str = "web_only_mode"
CONF_MODBUS_TIMEOUT: str = "modbus_timeout"
CONF_MODBUS_MAX_RETRIES: str = "modbus_retries"

DEFAULT_HOST: str = ""
DEFAULT_WEB_ONLY: bool = False
DEFAULT_PORT: int = 502
DEFAULT_SLAVE_ID: int = 1
DEFAULT_SCAN_INTERVAL: int = 10
DEFAULT_HIDE_UNUSED: bool = True
DEFAULT_ENABLE_CASCADE: bool = False
DEFAULT_WEB_ENABLED: bool = True
DEFAULT_WEB_SCAN_INTERVAL: int = int(RECOMMENDED_WEB_SCAN_INTERVAL)
DEFAULT_ROOM_TEMP_FORWARDING: bool = False
DEFAULT_ROOM_TEMP_FORWARDING_INTERVAL: int = 300
DEFAULT_ROOM_TEMP_FORWARDING_TOLERANCE: float = 0.2
DEFAULT_MODBUS_TIMEOUT: float = 10.0
DEFAULT_MODBUS_MAX_RETRIES: int = 3
MIN_MODBUS_TIMEOUT: float = 3.0
MAX_MODBUS_TIMEOUT: float = 30.0
MIN_MODBUS_MAX_RETRIES: int = 1
MAX_MODBUS_MAX_RETRIES: int = 5

# Service-spezifische Register-Adressen (werden in services.py verwendet)
REGISTER_ADDRESS_SYSTEM_MODE: int = 1005
REGISTER_ADDRESS_ERROR_ACKNOWLEDGE: int = 1999

UNUSED_VALUE: float = -1.0

# Pumpen-Statusregister (INT16, %), bei denen -1 laut iDM-Doku "Aus" bedeutet.
# Für diese Register ist -1 ein gültiger Wert und NICHT der Unused-Sentinel.
NEGATIVE_ONE_VALID_REGISTERS: frozenset[str] = frozenset(
    {
        "heat_sink_charging_pump_signal",
        "charging_pump_status",
        "brine_pump_status",
        "heat_source_pump_status",
        "isc_cold_storage_pump_status",
        "isc_recooling_pump_status",
        "booster_a_source_pump",
        "booster_a_charging_pump",
        "booster_b_source_pump",
        "booster_b_charging_pump",
    }
)

MAX_ZONE_COUNT: int = 10
MAX_ROOM_COUNT: int = 8
HEATING_CIRCUITS: list[str] = ["a", "b", "c", "d", "e", "f", "g"]
HEATING_CIRCUITS_OPTIONAL: list[str] = ["b", "c", "d", "e", "f", "g"]
ZONE_OPTIONS: list[str] = [str(i) for i in range(1, 11)]


class SystemMode(enum.IntEnum):
    STANDBY = 0
    AUTOMATIC = 1
    AWAY = 2
    HOLIDAY = 3
    HOT_WATER_ONLY = 4
    HEATING_COOLING_ONLY = 5


SYSTEM_MODE_OPTIONS: dict[int, str] = {
    0: "Standby",
    1: "Automatik",
    2: "Abwesend",
    3: "Urlaub",
    4: "Nur Warmwasser",
    5: "Nur Heizung/Kuehlung",
}


class CircuitMode(enum.IntEnum):
    OFF = 0
    TIMED = 1
    NORMAL = 2
    ECO = 3
    MANUAL_HEAT = 4
    MANUAL_COOL = 5


CIRCUIT_MODE_OPTIONS: dict[int, str] = {
    0: "Aus",
    1: "Zeitprogramm",
    2: "Normal",
    3: "Eco",
    4: "Manuell Heizen",
    5: "Manuell Kuehlen",
    255: "Nicht konfiguriert / Nicht verfügbar",
}


class RoomMode(enum.IntEnum):
    OFF = 0
    AUTOMATIC = 1
    ECO = 2
    NORMAL = 3
    COMFORT = 4


ROOM_MODE_OPTIONS: dict[int, str] = {
    0: "Aus",
    1: "Automatik",
    2: "Eco",
    3: "Normal",
    4: "Komfort",
}


class SolarMode(enum.IntEnum):
    AUTO = 0
    WATER = 1
    HEATING = 2
    WATER_HEATING = 3
    SOURCE_POOL = 4


SOLAR_MODE_OPTIONS: dict[int, str] = {
    0: "Automatik",
    1: "Warmwasser",
    2: "Heizung",
    3: "Warmwasser + Heizung",
    4: "Waermequelle/Pool",
}


ISC_MODE_OPTIONS: dict[int, str] = {
    0: "Aus",
    1: "Heizung",
    4: "Warmwasser",
    8: "Quelle",
    255: "Nicht konfiguriert / Nicht verfügbar",
}


class SmartGridStatus(enum.IntEnum):
    GRID_BLOCKED_SOLAR_OFF = 0
    GRID_ALLOWED_SOLAR_OFF = 1
    GRID_UNUSED_SOLAR_ON = 2
    GRID_BLOCKED_SOLAR_ON = 4


class HeatPumpStatus(enum.IntFlag):
    OFF = 0
    HEATING = 1
    COOLING = 2
    WATER = 4
    DEFROSTING = 8


HP_STATUS_OPTIONS: dict[int, str] = {
    0: "Aus",
    1: "Heizen",
    2: "Kuehlen",
    4: "Warmwasser",
    8: "Abtauen",
}
