"""Constants for IDM Heatpump integration."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — unofficial community integration for IDM Navigator 2.0 / 10 heat pumps
# Created by Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# SPDX-License-Identifier: MIT
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
CONF_DEVICE_HIERARCHY: str = "device_hierarchy"
CONF_SHORT_CYCLE_MINUTES: str = "short_cycle_minutes"
CONF_TECHNICIAN_CODES: str = "technician_codes"
CONF_ENABLE_CASCADE: str = "enable_cascade"
CONF_MODBUS_PROXY: str = "modbus_proxy"
CONF_WEB_PIN: str = "web_pin"
CONF_WEB_HOST: str = "web_host"
CONF_WEB_ENABLED: str = "web_extra_data"
CONF_WEB_SCAN_INTERVAL: str = "web_scan_interval"
CONF_DETECTED_NAVIGATOR_VERSION: str = "detected_navigator_version"
CONF_DETECTED_SOFTWARE_VERSION: str = "detected_software_version"
CONF_DETECTED_WEB_VARIANT: str = "detected_web_variant"
# Optional manual override of the detected Navigator model. Stored in
# entry.data alongside the detected_* keys. ``MODEL_OVERRIDE_AUTO`` means
# "use automatic detection"; any other value forces that model family.
CONF_MODEL_OVERRIDE: str = "model_override"
CONF_ROOM_TEMP_FORWARDING: str = "room_temp_forwarding"
CONF_ROOM_TEMP_FORWARDING_INTERVAL: str = "room_temp_forwarding_interval"
CONF_ROOM_TEMP_FORWARDING_TOLERANCE: str = "room_temp_forwarding_tolerance"
CONF_ROOM_TEMP_FORWARDING_ENTITIES: str = "room_temp_forwarding_entities"
# Single global GLT humidity register (ext_humidity), unlike room temperature
# which is one register per heating circuit.
CONF_HUMIDITY_FORWARDING: str = "humidity_forwarding"
CONF_HUMIDITY_FORWARDING_INTERVAL: str = "humidity_forwarding_interval"
CONF_HUMIDITY_FORWARDING_TOLERANCE: str = "humidity_forwarding_tolerance"
CONF_HUMIDITY_FORWARDING_ENTITY: str = "humidity_forwarding_entity"
# One register per fixed storage key (heat/cold/dhw_bottom/dhw_top), like room
# temperature forwarding, but the keys are fixed GLT storage registers instead
# of the configured heating circuits.
CONF_STORAGE_TEMP_FORWARDING: str = "storage_temp_forwarding"
CONF_STORAGE_TEMP_FORWARDING_INTERVAL: str = "storage_temp_forwarding_interval"
CONF_STORAGE_TEMP_FORWARDING_TOLERANCE: str = "storage_temp_forwarding_tolerance"
CONF_STORAGE_TEMP_FORWARDING_ENTITIES: str = "storage_temp_forwarding_entities"
# Optional automatic forwarding of selected HA energy sensors to IDM GLT/PV registers.
CONF_EXTERNAL_POWER_FORWARDING: str = "external_power_forwarding"
CONF_EXTERNAL_POWER_FORWARDING_INTERVAL: str = "external_power_forwarding_interval"
CONF_EXTERNAL_POWER_FORWARDING_ENTITIES: str = "external_power_forwarding_entities"
CONF_EXTERNAL_POWER_BATTERY_SIGN: str = "external_power_battery_sign"
# KNX bridge: mirror controller values onto a KNX bus through Home
# Assistant's own ``knx`` integration and accept commands back from it.
# The base address plus the IDM KNX object number gives every object its
# group address; the override map covers ETS projects that already use
# different ones.
CONF_KNX_BRIDGE: str = "knx_bridge"
CONF_KNX_BASE_ADDRESS: str = "knx_base_address"
CONF_KNX_SEND: str = "knx_send"
CONF_KNX_RECEIVE: str = "knx_receive"
CONF_KNX_RESPOND_TO_READ: str = "knx_respond_to_read"
CONF_KNX_GROUPS: str = "knx_groups"
CONF_KNX_RESEND_INTERVAL: str = "knx_resend_interval"
CONF_KNX_TOLERANCE: str = "knx_tolerance"
CONF_KNX_OVERRIDES: str = "knx_overrides"
CONF_WEB_ONLY: str = "web_only_mode"
CONF_MODBUS_TIMEOUT: str = "modbus_timeout"
CONF_MODBUS_MAX_RETRIES: str = "modbus_retries"
# Connection-wide pacing handed to ``modbus-connection``: the minimum pause
# between two requests on the link, and a one-off pause after every (re-)
# connect before the first request uses the link.
CONF_MODBUS_MESSAGE_SPACING: str = "modbus_message_spacing"
CONF_MODBUS_CONNECT_DELAY: str = "modbus_connect_delay"
CONF_POLLING_JITTER: str = "polling_jitter"
CONF_COMMUNICATION_DIAGNOSTICS: str = "communication_diagnostics"
CONF_WRITE_COOLDOWN: str = "write_cooldown"
# Feature profile. ``smart`` keeps the existing advanced local analytics and
# safe convenience controls enabled; ``vanilla`` exposes the core register,
# climate and water-heater entities only.
CONF_FEATURE_PROFILE: str = "feature_profile"
CONF_ENERGY_MANAGER: str = "energy_manager"
CONF_ENERGY_MANAGER_EXCLUSIVE: str = "energy_manager_exclusive_control"
CONF_ENERGY_MANAGER_MIN_SURPLUS: str = "energy_manager_min_surplus_kw"
CONF_ENERGY_MANAGER_MIN_SOC: str = "energy_manager_min_battery_soc"
CONF_ENERGY_MANAGER_TARGET: str = "energy_manager_dhw_target"
CONF_ENERGY_MANAGER_TIMEOUT: str = "energy_manager_dhw_timeout"
CONF_ENERGY_MANAGER_COOLDOWN: str = "energy_manager_cooldown"
CONF_HEALTH_MONITOR: str = "health_monitor"
CONF_ENERGY_PRICE: str = "energy_price_per_kwh"
CONF_DYNAMIC_PRICE_ENTITY: str = "dynamic_price_entity"
CONF_ENERGY_CO2_FACTOR: str = "energy_co2_g_per_kwh"
CONF_COMFORT_SCHEDULE: str = "comfort_schedule"
CONF_COMFORT_SCHEDULE_EXCLUSIVE: str = "comfort_schedule_exclusive_control"
CONF_COMFORT_SCHEDULE_CIRCUIT: str = "comfort_schedule_circuit"
CONF_COMFORT_SCHEDULE_START: str = "comfort_schedule_start"
CONF_COMFORT_SCHEDULE_END: str = "comfort_schedule_end"
CONF_COMFORT_SCHEDULE_TARGET: str = "comfort_schedule_target"
CONF_COMFORT_WINDOWS: str = "comfort_schedule_windows"
CONF_HEATING_CURVE_ASSISTANT: str = "heating_curve_assistant"
CONF_WEATHER_PREHEAT: str = "weather_preheat_advisory"
CONF_WEATHER_ENTITY: str = "weather_entity"
CONF_WEATHER_PREHEAT_THRESHOLD: str = "weather_preheat_threshold"
FEATURE_PROFILE_SMART: str = "smart"
FEATURE_PROFILE_VANILLA: str = "vanilla"
FEATURE_PROFILE_OPTIONS: tuple[str, ...] = (FEATURE_PROFILE_SMART, FEATURE_PROFILE_VANILLA)

DEFAULT_HOST: str = ""
DEFAULT_WEB_ONLY: bool = False
DEFAULT_PORT: int = 502
# Selector values for the optional model override. ``auto`` keeps the
# automatic detection; the other values force a Navigator family.
MODEL_OVERRIDE_AUTO: str = "auto"
MODEL_OVERRIDE_NAVIGATOR_10: str = "navigator_10"
MODEL_OVERRIDE_NAVIGATOR_17: str = "navigator_17"
MODEL_OVERRIDE_NAVIGATOR_20: str = "navigator_20"
MODEL_OVERRIDE_NAVIGATOR_PRO: str = "navigator_pro"
DEFAULT_MODEL_OVERRIDE: str = MODEL_OVERRIDE_AUTO
MODEL_OVERRIDE_OPTIONS: tuple[str, ...] = (
    MODEL_OVERRIDE_AUTO,
    MODEL_OVERRIDE_NAVIGATOR_10,
    MODEL_OVERRIDE_NAVIGATOR_20,
    MODEL_OVERRIDE_NAVIGATOR_PRO,
    MODEL_OVERRIDE_NAVIGATOR_17,
)
CONFIG_FLOW_TCP_TIMEOUT: float = 5.0
DEFAULT_SLAVE_ID: int = 1
DEFAULT_SCAN_INTERVAL: int = 10
DEFAULT_HIDE_UNUSED: bool = True
DEFAULT_DEVICE_HIERARCHY: bool = True
DEFAULT_SHORT_CYCLE_MINUTES: int = 15
DEFAULT_ENABLE_CASCADE: bool = False
DEFAULT_WEB_ENABLED: bool = True
DEFAULT_WEB_SCAN_INTERVAL: int = int(RECOMMENDED_WEB_SCAN_INTERVAL)
# A web supplement that keeps failing is retried ever more slowly, up to this
# multiple of the configured interval. A Navigator that is switched off should
# not be probed every 30 seconds forever, and each probe pays a connect timeout.
MAX_WEB_BACKOFF_FACTOR: int = 10
# Upper bound for one local web read, above the client's own connect timeout and
# below the default web interval, so a hung read cannot stall the poll loop.
WEB_READ_TIMEOUT: float = 15.0
# Setup must not wait on the optional supplement: the polling loop finishes
# detection later, so a slow Navigator only delays its own web values.
WEB_SETUP_READ_TIMEOUT: float = 8.0
DEFAULT_ROOM_TEMP_FORWARDING: bool = False
DEFAULT_ROOM_TEMP_FORWARDING_INTERVAL: int = 300
DEFAULT_ROOM_TEMP_FORWARDING_TOLERANCE: float = 0.2
DEFAULT_HUMIDITY_FORWARDING: bool = False
DEFAULT_HUMIDITY_FORWARDING_INTERVAL: int = 300
DEFAULT_HUMIDITY_FORWARDING_TOLERANCE: float = 2.0
DEFAULT_STORAGE_TEMP_FORWARDING: bool = False
DEFAULT_STORAGE_TEMP_FORWARDING_INTERVAL: int = 300
DEFAULT_STORAGE_TEMP_FORWARDING_TOLERANCE: float = 0.5
DEFAULT_EXTERNAL_POWER_FORWARDING: bool = False
DEFAULT_EXTERNAL_POWER_FORWARDING_INTERVAL: int = 60
DEFAULT_EXTERNAL_POWER_FORWARDING_ENTITIES: dict[str, str] = {}
DEFAULT_EXTERNAL_POWER_BATTERY_SIGN: str = "as_is"
DEFAULT_KNX_BRIDGE: bool = False
# 8/0/0 keeps the whole catalogue inside one free main group on a default
# ETS three-level project (8/0/1 .. 8/3/231).
DEFAULT_KNX_BASE_ADDRESS: str = "8/0/0"
DEFAULT_KNX_SEND: bool = True
DEFAULT_KNX_RECEIVE: bool = True
# Answering GroupValueRead is what a KNX device expects; without it a
# push-button stays blank after a restart until the next change is sent.
DEFAULT_KNX_RESPOND_TO_READ: bool = True
# 0 = send only when a value changes. A periodic full resend is what KNX
# visualisations without their own cache need after a restart.
DEFAULT_KNX_RESEND_INTERVAL: int = 0
DEFAULT_KNX_TOLERANCE: float = 0.1
MIN_KNX_RESEND_INTERVAL: int = 0
MAX_KNX_RESEND_INTERVAL: int = 86400
MIN_KNX_TOLERANCE: float = 0.0
MAX_KNX_TOLERANCE: float = 10.0
DEFAULT_MODBUS_TIMEOUT: float = 10.0
DEFAULT_MODBUS_MAX_RETRIES: int = 3
# Both pacing defaults stay at 0 so an update never slows down an
# installation that polls fine today; they are opt-in for endpoints that
# answer badly under back-to-back requests (busy Navigator controllers,
# shared gateways, serial bridges).
DEFAULT_MODBUS_MESSAGE_SPACING: float = 0.0
DEFAULT_MODBUS_CONNECT_DELAY: float = 0.0
DEFAULT_POLLING_JITTER: int = 0
DEFAULT_COMMUNICATION_DIAGNOSTICS: bool = False
DEFAULT_WRITE_COOLDOWN: float = 5.0
DEFAULT_FEATURE_PROFILE: str = FEATURE_PROFILE_SMART
DEFAULT_ENERGY_MANAGER: bool = False
DEFAULT_ENERGY_MANAGER_EXCLUSIVE: bool = False
DEFAULT_ENERGY_MANAGER_MIN_SURPLUS: float = 1.0
DEFAULT_ENERGY_MANAGER_MIN_SOC: float = 20.0
DEFAULT_ENERGY_MANAGER_TARGET: int = 55
DEFAULT_ENERGY_MANAGER_TIMEOUT: int = 90
DEFAULT_ENERGY_MANAGER_COOLDOWN: int = 60
DEFAULT_HEALTH_MONITOR: bool = False
DEFAULT_ENERGY_PRICE: float = 0.30
DEFAULT_ENERGY_CO2_FACTOR: float = 350.0
DEFAULT_COMFORT_SCHEDULE: bool = False
DEFAULT_COMFORT_SCHEDULE_EXCLUSIVE: bool = False
DEFAULT_COMFORT_SCHEDULE_CIRCUIT: str = "a"
DEFAULT_COMFORT_SCHEDULE_START: str = "06:00"
DEFAULT_COMFORT_SCHEDULE_END: str = "22:00"
DEFAULT_COMFORT_SCHEDULE_TARGET: float = 21.0
DEFAULT_HEATING_CURVE_ASSISTANT: bool = False
DEFAULT_WEATHER_PREHEAT: bool = False
DEFAULT_WEATHER_ENTITY: str = ""
DEFAULT_WEATHER_PREHEAT_THRESHOLD: float = 5.0
MIN_MODBUS_TIMEOUT: float = 3.0
MAX_MODBUS_TIMEOUT: float = 30.0
MIN_MODBUS_MAX_RETRIES: int = 1
MAX_MODBUS_MAX_RETRIES: int = 5
MIN_MODBUS_MESSAGE_SPACING: float = 0.0
# 0.5 s between requests is already slow enough to stretch a full poll far
# beyond the scan interval; anything above that is a broken endpoint, not a
# tuning value.
MAX_MODBUS_MESSAGE_SPACING: float = 0.5
MIN_MODBUS_CONNECT_DELAY: float = 0.0
MAX_MODBUS_CONNECT_DELAY: float = 5.0
MIN_POLLING_JITTER: int = 0
MAX_POLLING_JITTER: int = 20
MIN_WRITE_COOLDOWN: float = 0.0
MAX_WRITE_COOLDOWN: float = 600.0

# EEPROM write protection: the minimum number of seconds between two writes to
# the same EEPROM-backed register. The 60 s default protects the EEPROM's
# limited write cycles. Power users may lower it, explicitly at their own risk
# of accelerated EEPROM wear.
CONF_EEPROM_WRITE_INTERVAL: str = "eeprom_write_interval"
DEFAULT_EEPROM_WRITE_INTERVAL: float = 60.0
MIN_EEPROM_WRITE_INTERVAL: float = 5.0
MAX_EEPROM_WRITE_INTERVAL: float = 600.0

# Service-specific register addresses, used from services.py.
REGISTER_ADDRESS_SYSTEM_MODE: int = 1005
REGISTER_ADDRESS_ERROR_ACKNOWLEDGE: int = 1999
REGISTER_ADDRESS_CONNECTION_PROBE: int = 1000
REGISTER_COUNT_CONNECTION_PROBE: int = 2

UNUSED_VALUE: float = -1.0

# Pump status registers (INT16, %) where iDM's documentation gives -1 the
# meaning "off". For these, -1 is a valid reading and NOT the unused sentinel.
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
