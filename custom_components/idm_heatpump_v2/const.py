"""Constants for IDM Navigator Heatpump integration."""

import enum

DOMAIN = "idm_heatpump_v2"
NAME = "IDM Navigator Heatpump"
MANUFACTURER = "iDM Energiesysteme"
MODEL = "Navigator 2.0"
MODEL_ZONE = "Navigator Pro Einzelraumregelung"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SLAVE_ID = "slave_id"
CONF_NAME = "name"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_HEATING_CIRCUITS = "heating_circuits"
CONF_ZONE_COUNT = "zone_count"
CONF_ZONE_ROOMS = "zone_rooms"
CONF_HIDE_UNUSED = "hide_unused_registers"

DEFAULT_HOST = ""
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 1
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_HIDE_UNUSED = True

UNUSED_VALUE = -1.0

MAX_ZONE_COUNT = 10
MAX_ROOM_COUNT = 8
HEATING_CIRCUITS = ["A", "B", "C", "D", "E", "F", "G"]
HEATING_CIRCUITS_OPTIONAL = ["B", "C", "D", "E", "F", "G"]
ZONE_OPTIONS = [str(i) for i in range(1, 11)]


class SystemMode(enum.IntEnum):
    STANDBY = 0
    AUTOMATIC = 1
    AWAY = 2
    HOLIDAY = 3
    HOT_WATER_ONLY = 4
    HEATING_COOLING_ONLY = 5


SYSTEM_MODE_OPTIONS = {
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


CIRCUIT_MODE_OPTIONS = {
    0: "Aus",
    1: "Zeitprogramm",
    2: "Normal",
    3: "Eco",
    4: "Manuell Heizen",
    5: "Manuell Kuehlen",
}


class RoomMode(enum.IntEnum):
    OFF = 0
    AUTOMATIC = 1
    ECO = 2
    NORMAL = 3
    COMFORT = 4


ROOM_MODE_OPTIONS = {
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


SOLAR_MODE_OPTIONS = {
    0: "Automatik",
    1: "Warmwasser",
    2: "Heizung",
    3: "Warmwasser + Heizung",
    4: "Waermequelle/Pool",
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
