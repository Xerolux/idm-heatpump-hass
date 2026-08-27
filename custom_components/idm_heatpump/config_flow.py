"""Config flow for IDM Heatpump integration."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT
import asyncio
import logging
import socket
from collections.abc import Awaitable, Callable, Mapping
from enum import StrEnum
from time import monotonic
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
    BooleanSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_COMMUNICATION_DIAGNOSTICS,
    CONF_DETECTED_NAVIGATOR_VERSION,
    CONF_DETECTED_SOFTWARE_VERSION,
    CONF_DETECTED_WEB_VARIANT,
    CONF_DEVICE_HIERARCHY,
    CONF_EEPROM_WRITE_INTERVAL,
    CONF_ENABLE_CASCADE,
    CONF_HEATING_CIRCUITS,
    CONF_HIDE_UNUSED,
    CONF_HUMIDITY_FORWARDING,
    CONF_HUMIDITY_FORWARDING_ENTITY,
    CONF_HUMIDITY_FORWARDING_INTERVAL,
    CONF_HUMIDITY_FORWARDING_TOLERANCE,
    CONF_KNX_BASE_ADDRESS,
    CONF_KNX_BRIDGE,
    CONF_KNX_GROUPS,
    CONF_KNX_OVERRIDES,
    CONF_KNX_RECEIVE,
    CONF_KNX_RESEND_INTERVAL,
    CONF_KNX_RESPOND_TO_READ,
    CONF_KNX_SEND,
    CONF_KNX_TOLERANCE,
    CONF_MODBUS_CONNECT_DELAY,
    CONF_MODBUS_MAX_RETRIES,
    CONF_MODBUS_MESSAGE_SPACING,
    CONF_MODBUS_PROXY,
    CONF_MODBUS_TIMEOUT,
    CONF_MODEL_OVERRIDE,
    CONF_POLLING_JITTER,
    CONF_ROOM_TEMP_FORWARDING,
    CONF_ROOM_TEMP_FORWARDING_ENTITIES,
    CONF_ROOM_TEMP_FORWARDING_INTERVAL,
    CONF_ROOM_TEMP_FORWARDING_TOLERANCE,
    CONF_SCAN_INTERVAL,
    CONF_SHORT_CYCLE_MINUTES,
    CONF_SLAVE_ID,
    CONF_STORAGE_TEMP_FORWARDING,
    CONF_STORAGE_TEMP_FORWARDING_ENTITIES,
    CONF_STORAGE_TEMP_FORWARDING_INTERVAL,
    CONF_STORAGE_TEMP_FORWARDING_TOLERANCE,
    CONF_TECHNICIAN_CODES,
    CONF_WEB_ENABLED,
    CONF_WEB_HOST,
    CONF_WEB_ONLY,
    CONF_WEB_PIN,
    CONF_WEB_SCAN_INTERVAL,
    CONF_WRITE_COOLDOWN,
    CONF_ZONE_COUNT,
    CONF_ZONE_ROOMS,
    CONFIG_FLOW_TCP_TIMEOUT,
    DEFAULT_COMMUNICATION_DIAGNOSTICS,
    DEFAULT_DEVICE_HIERARCHY,
    DEFAULT_EEPROM_WRITE_INTERVAL,
    DEFAULT_ENABLE_CASCADE,
    DEFAULT_HIDE_UNUSED,
    DEFAULT_HUMIDITY_FORWARDING,
    DEFAULT_HUMIDITY_FORWARDING_INTERVAL,
    DEFAULT_HUMIDITY_FORWARDING_TOLERANCE,
    DEFAULT_KNX_BASE_ADDRESS,
    DEFAULT_KNX_BRIDGE,
    DEFAULT_KNX_RECEIVE,
    DEFAULT_KNX_RESEND_INTERVAL,
    DEFAULT_KNX_RESPOND_TO_READ,
    DEFAULT_KNX_SEND,
    DEFAULT_KNX_TOLERANCE,
    DEFAULT_MODBUS_CONNECT_DELAY,
    DEFAULT_MODBUS_MAX_RETRIES,
    DEFAULT_MODBUS_MESSAGE_SPACING,
    DEFAULT_MODBUS_TIMEOUT,
    DEFAULT_MODEL_OVERRIDE,
    DEFAULT_POLLING_JITTER,
    DEFAULT_PORT,
    DEFAULT_ROOM_TEMP_FORWARDING,
    DEFAULT_ROOM_TEMP_FORWARDING_INTERVAL,
    DEFAULT_ROOM_TEMP_FORWARDING_TOLERANCE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SHORT_CYCLE_MINUTES,
    DEFAULT_SLAVE_ID,
    DEFAULT_STORAGE_TEMP_FORWARDING,
    DEFAULT_STORAGE_TEMP_FORWARDING_INTERVAL,
    DEFAULT_STORAGE_TEMP_FORWARDING_TOLERANCE,
    DEFAULT_WEB_ENABLED,
    DEFAULT_WEB_SCAN_INTERVAL,
    DEFAULT_WRITE_COOLDOWN,
    DOMAIN,
    HEATING_CIRCUITS,
    MAX_EEPROM_WRITE_INTERVAL,
    MAX_KNX_RESEND_INTERVAL,
    MAX_KNX_TOLERANCE,
    MAX_MODBUS_CONNECT_DELAY,
    MAX_MODBUS_MAX_RETRIES,
    MAX_MODBUS_MESSAGE_SPACING,
    MAX_MODBUS_TIMEOUT,
    MAX_POLLING_JITTER,
    MAX_ROOM_COUNT,
    MAX_WRITE_COOLDOWN,
    MAX_ZONE_COUNT,
    MIN_EEPROM_WRITE_INTERVAL,
    MIN_KNX_RESEND_INTERVAL,
    MIN_KNX_TOLERANCE,
    MIN_MODBUS_CONNECT_DELAY,
    MIN_MODBUS_MAX_RETRIES,
    MIN_MODBUS_MESSAGE_SPACING,
    MIN_MODBUS_TIMEOUT,
    MIN_POLLING_JITTER,
    MIN_WRITE_COOLDOWN,
    MODEL_OVERRIDE_OPTIONS,
    REGISTER_ADDRESS_CONNECTION_PROBE,
    REGISTER_COUNT_CONNECTION_PROBE,
)
from .knx_catalog import (
    KNX_OBJECTS,
    OBJECT_GROUPS,
    InvalidGroupAddressError,
    validate_base_address,
    validate_overrides,
)
from .library_adapter import get_idm_client
from .log_filter import install_library_log_filter
from .registers import normalize_zone_rooms
from .web_data import IdmWebAuthenticationFailed, async_read_web_supplement, web_pin_configured

_LOGGER = logging.getLogger(__name__)


class _ModbusConnectionStatus(StrEnum):
    """Result of the setup-time Modbus connection check."""

    SUCCESS = "success"
    HOST_NOT_FOUND = "host_not_found"
    CONNECTION_REFUSED = "modbus_connection_refused"
    TIMEOUT = "modbus_timeout"
    UNREACHABLE = "modbus_unreachable"
    NO_RESPONSE = "modbus_no_response"
    FAILED = "cannot_connect"


_MODBUS_SETUP_URL = (
    "https://xerolux.github.io/idm-heatpump-hass/docs/#/installation-and-setup/enable-modbus-tcp-on-the-idm-heat-pump"
)


class _WebSupplementConnectionFailed(Exception):
    """Raised when web-only setup cannot read the local Navigator web UI."""


def _connection_error_key(result: _ModbusConnectionStatus | bool) -> str | None:
    """Translate a connection result to a config-flow error key."""
    if result is True or result is _ModbusConnectionStatus.SUCCESS:
        return None
    if isinstance(result, _ModbusConnectionStatus):
        return result.value
    return _ModbusConnectionStatus.FAILED.value


# Optional manual Navigator model override. Initial setup asks for it only after
# automatic detection so users can make an informed choice. Reconfigure keeps it
# available as an advanced field for repairing an existing entry.
_MODEL_OVERRIDE_SELECTOR: SelectSelector = SelectSelector(
    SelectSelectorConfig(
        options=list(MODEL_OVERRIDE_OPTIONS),
        mode=SelectSelectorMode.DROPDOWN,
        translation_key="model_override",
    )
)


_SETUP_WEB_ACCESS = "setup_web_access"


# Initial setup defaults to full local Modbus + Navigator web access. Users who
# deliberately want Modbus only must switch the web-access field off.
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Required(CONF_HOST): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(
            CONF_SLAVE_ID,
            default=DEFAULT_SLAVE_ID,
            description={"advanced": True},
        ): NumberSelector(NumberSelectorConfig(min=1, max=247, mode=NumberSelectorMode.BOX)),
        vol.Required(_SETUP_WEB_ACCESS, default=True): BooleanSelector(BooleanSelectorConfig()),
        vol.Optional(CONF_WEB_PIN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        vol.Optional(CONF_MODBUS_PROXY, default=False): BooleanSelector(BooleanSelectorConfig()),
        vol.Optional(CONF_WEB_HOST): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
    }
)

# Schema for reconfigure – values are injected via add_suggested_values_to_schema
STEP_RECONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(
            CONF_SLAVE_ID,
            default=DEFAULT_SLAVE_ID,
            description={"advanced": True},
        ): NumberSelector(NumberSelectorConfig(min=1, max=247, mode=NumberSelectorMode.BOX)),
        vol.Required(_SETUP_WEB_ACCESS, default=True): BooleanSelector(BooleanSelectorConfig()),
        vol.Optional(CONF_WEB_PIN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        vol.Optional(CONF_MODBUS_PROXY, default=False): BooleanSelector(BooleanSelectorConfig()),
        vol.Optional(CONF_WEB_HOST): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Optional(
            CONF_MODEL_OVERRIDE,
            default=DEFAULT_MODEL_OVERRIDE,
            description={"advanced": True},
        ): _MODEL_OVERRIDE_SELECTOR,
    }
)

_CIRCUIT_SELECTOR: SelectSelector = SelectSelector(
    SelectSelectorConfig(
        options=HEATING_CIRCUITS,
        multiple=True,
        mode=SelectSelectorMode.LIST,
        translation_key="heating_circuit",
    )
)

# Optional manual Navigator model override. Marked ``advanced`` so it is hidden
# behind the "show advanced" toggle in the config flow UI; automatic detection
# is correct for the vast majority of installations and a wrong manual choice
# can degrade the register map. The data_description (strings.json) repeats the
# "only change if detection fails" warning next to the field.
_ROOM_TEMPERATURE_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        domain="sensor",
        device_class="temperature",
    )
)

# Single global GLT humidity register (ext_humidity), so unlike
# _ROOM_TEMPERATURE_SELECTOR this is used once, not once per heating circuit.
_HUMIDITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        domain="sensor",
        device_class="humidity",
    )
)

# Four fixed GLT storage-temperature registers (heat/cold/DHW top/bottom
# storage), so like _ROOM_TEMPERATURE_SELECTOR this is used once per key, but
# the keys are fixed instead of the configured heating circuits.
_STORAGE_TEMPERATURE_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        domain="sensor",
        device_class="temperature",
    )
)


def _build_modbus_failed_schema(data: dict[str, Any]) -> vol.Schema:
    """Build the recovery form shown after a failed Modbus check."""
    schema: dict[Any, Any] = {
        vol.Required("action", default="retry"): SelectSelector(
            SelectSelectorConfig(
                options=["retry", "web_only"],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="modbus_failed_action",
            )
        ),
        vol.Required(CONF_WEB_PIN, default=_clean_pin(data.get(CONF_WEB_PIN))): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
    if _uses_modbus_proxy(data):
        schema[vol.Required(CONF_WEB_HOST, default=str(data.get(CONF_WEB_HOST, "")))] = TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        )
    return vol.Schema(schema)


_OPTIONS_FEATURES_SECTION = "features"
_OPTIONS_ROOM_SECTION = "room_temperature_forwarding"
_OPTIONS_HUMIDITY_SECTION = "humidity_forwarding_section"
_OPTIONS_STORAGE_SECTION = "storage_temp_forwarding_section"
_OPTIONS_KNX_SECTION = "knx_bridge_section"
_OPTIONS_MODBUS_SECTION = "advanced_modbus"
_OPTIONS_SECTION_KEYS = (
    _OPTIONS_FEATURES_SECTION,
    _OPTIONS_ROOM_SECTION,
    _OPTIONS_HUMIDITY_SECTION,
    _OPTIONS_STORAGE_SECTION,
    _OPTIONS_KNX_SECTION,
    _OPTIONS_MODBUS_SECTION,
)

_SETUP_PROFILE = "profile"
_SETUP_PROFILE_RECOMMENDED = "recommended"
_SETUP_PROFILE_RELIABLE = "reliable_network"
_SETUP_PROFILE_MULTI_CLIENT = "multiple_clients"
_SETUP_PROFILE_CUSTOM = "custom"


def _default_options() -> dict[str, Any]:
    """Return a complete, independent set of recommended options."""
    return {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_HIDE_UNUSED: DEFAULT_HIDE_UNUSED,
        CONF_HEATING_CIRCUITS: ["a"],
        CONF_ZONE_COUNT: 0,
        CONF_ZONE_ROOMS: {},
        CONF_DEVICE_HIERARCHY: DEFAULT_DEVICE_HIERARCHY,
        CONF_SHORT_CYCLE_MINUTES: DEFAULT_SHORT_CYCLE_MINUTES,
        CONF_TECHNICIAN_CODES: False,
        CONF_ENABLE_CASCADE: DEFAULT_ENABLE_CASCADE,
        CONF_WEB_ENABLED: DEFAULT_WEB_ENABLED,
        CONF_WEB_SCAN_INTERVAL: DEFAULT_WEB_SCAN_INTERVAL,
        CONF_ROOM_TEMP_FORWARDING: DEFAULT_ROOM_TEMP_FORWARDING,
        CONF_ROOM_TEMP_FORWARDING_ENTITIES: {},
        CONF_ROOM_TEMP_FORWARDING_INTERVAL: DEFAULT_ROOM_TEMP_FORWARDING_INTERVAL,
        CONF_ROOM_TEMP_FORWARDING_TOLERANCE: DEFAULT_ROOM_TEMP_FORWARDING_TOLERANCE,
        CONF_HUMIDITY_FORWARDING: DEFAULT_HUMIDITY_FORWARDING,
        CONF_HUMIDITY_FORWARDING_ENTITY: "",
        CONF_HUMIDITY_FORWARDING_INTERVAL: DEFAULT_HUMIDITY_FORWARDING_INTERVAL,
        CONF_HUMIDITY_FORWARDING_TOLERANCE: DEFAULT_HUMIDITY_FORWARDING_TOLERANCE,
        CONF_STORAGE_TEMP_FORWARDING: DEFAULT_STORAGE_TEMP_FORWARDING,
        CONF_STORAGE_TEMP_FORWARDING_ENTITIES: {},
        CONF_STORAGE_TEMP_FORWARDING_INTERVAL: DEFAULT_STORAGE_TEMP_FORWARDING_INTERVAL,
        CONF_STORAGE_TEMP_FORWARDING_TOLERANCE: DEFAULT_STORAGE_TEMP_FORWARDING_TOLERANCE,
        CONF_KNX_BRIDGE: DEFAULT_KNX_BRIDGE,
        CONF_KNX_BASE_ADDRESS: DEFAULT_KNX_BASE_ADDRESS,
        CONF_KNX_SEND: DEFAULT_KNX_SEND,
        CONF_KNX_RECEIVE: DEFAULT_KNX_RECEIVE,
        CONF_KNX_RESPOND_TO_READ: DEFAULT_KNX_RESPOND_TO_READ,
        CONF_KNX_GROUPS: list(OBJECT_GROUPS),
        CONF_KNX_RESEND_INTERVAL: DEFAULT_KNX_RESEND_INTERVAL,
        CONF_KNX_TOLERANCE: DEFAULT_KNX_TOLERANCE,
        CONF_KNX_OVERRIDES: {},
        CONF_MODBUS_TIMEOUT: DEFAULT_MODBUS_TIMEOUT,
        CONF_MODBUS_MAX_RETRIES: DEFAULT_MODBUS_MAX_RETRIES,
        CONF_MODBUS_MESSAGE_SPACING: DEFAULT_MODBUS_MESSAGE_SPACING,
        CONF_MODBUS_CONNECT_DELAY: DEFAULT_MODBUS_CONNECT_DELAY,
        CONF_POLLING_JITTER: DEFAULT_POLLING_JITTER,
        CONF_COMMUNICATION_DIAGNOSTICS: DEFAULT_COMMUNICATION_DIAGNOSTICS,
        CONF_WRITE_COOLDOWN: DEFAULT_WRITE_COOLDOWN,
        CONF_EEPROM_WRITE_INTERVAL: DEFAULT_EEPROM_WRITE_INTERVAL,
    }


def _options_for_profile(profile: str) -> dict[str, Any]:
    """Return recommended options adjusted for a guided setup profile."""
    options = _default_options()
    if profile == _SETUP_PROFILE_RELIABLE:
        # A slow endpoint gets air between requests as well as more patience per
        # request: 50 ms costs a fraction of a second over a full poll, but keeps
        # a busy controller from answering "device busy" to the next batch.
        options.update(
            {
                CONF_SCAN_INTERVAL: 30,
                CONF_MODBUS_TIMEOUT: 20.0,
                CONF_MODBUS_MAX_RETRIES: 5,
                CONF_MODBUS_MESSAGE_SPACING: 0.05,
            }
        )
    elif profile == _SETUP_PROFILE_MULTI_CLIENT:
        # A gateway shared with other Modbus clients benefits most from pacing:
        # jitter spreads the polls, spacing keeps this integration from filling
        # the link back-to-back while another client waits for its turn.
        options.update(
            {
                CONF_SCAN_INTERVAL: 30,
                CONF_POLLING_JITTER: 20,
                CONF_MODBUS_MESSAGE_SPACING: 0.1,
            }
        )
    return options


def _build_setup_review_schema(data: dict[str, Any]) -> vol.Schema:
    """Build the post-detection setup profile selector."""
    return vol.Schema(
        {
            vol.Required(
                CONF_MODEL_OVERRIDE,
                default=data.get(CONF_MODEL_OVERRIDE, DEFAULT_MODEL_OVERRIDE),
            ): _MODEL_OVERRIDE_SELECTOR,
            vol.Required(_SETUP_PROFILE, default=_SETUP_PROFILE_RECOMMENDED): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        _SETUP_PROFILE_RECOMMENDED,
                        _SETUP_PROFILE_RELIABLE,
                        _SETUP_PROFILE_MULTI_CLIENT,
                        _SETUP_PROFILE_CUSTOM,
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="setup_profile",
                )
            ),
        }
    )


def _flatten_options_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Flatten Home Assistant's sectioned options form for storage."""
    options = dict(user_input)
    for section_key in _OPTIONS_SECTION_KEYS:
        section_data = options.pop(section_key, {})
        if isinstance(section_data, dict):
            options.update(section_data)
    return options


def _build_options_schema(options: dict[str, Any]) -> vol.Schema:
    circuits_default = options.get(CONF_HEATING_CIRCUITS, ["a"])
    if "a" not in circuits_default:
        circuits_default = ["a"] + [c for c in circuits_default if c != "a"]

    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    max=300,
                    step=1,
                    mode=NumberSelectorMode.SLIDER,
                    unit_of_measurement="s",
                )
            ),
            vol.Required(
                CONF_HIDE_UNUSED,
                default=options.get(CONF_HIDE_UNUSED, DEFAULT_HIDE_UNUSED),
            ): BooleanSelector(BooleanSelectorConfig()),
            vol.Required(
                CONF_HEATING_CIRCUITS,
                default=circuits_default,
            ): _CIRCUIT_SELECTOR,
            vol.Required(
                CONF_ZONE_COUNT,
                default=int(options.get(CONF_ZONE_COUNT, 0)),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=MAX_ZONE_COUNT,
                    step=1,
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(_OPTIONS_FEATURES_SECTION): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_DEVICE_HIERARCHY,
                            default=options.get(CONF_DEVICE_HIERARCHY, DEFAULT_DEVICE_HIERARCHY),
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_SHORT_CYCLE_MINUTES,
                            default=int(
                                options.get(
                                    CONF_SHORT_CYCLE_MINUTES,
                                    DEFAULT_SHORT_CYCLE_MINUTES,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=5,
                                max=60,
                                step=1,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="min",
                            )
                        ),
                        vol.Required(
                            CONF_TECHNICIAN_CODES,
                            default=options.get(CONF_TECHNICIAN_CODES, False),
                            description={"advanced": True},
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_ENABLE_CASCADE,
                            default=options.get(CONF_ENABLE_CASCADE, DEFAULT_ENABLE_CASCADE),
                            description={"advanced": True},
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_WEB_ENABLED,
                            default=options.get(CONF_WEB_ENABLED, DEFAULT_WEB_ENABLED),
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_WEB_SCAN_INTERVAL,
                            default=int(options.get(CONF_WEB_SCAN_INTERVAL, DEFAULT_WEB_SCAN_INTERVAL)),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=30,
                                max=1800,
                                step=10,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="s",
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required(_OPTIONS_ROOM_SECTION): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_ROOM_TEMP_FORWARDING,
                            default=options.get(CONF_ROOM_TEMP_FORWARDING, DEFAULT_ROOM_TEMP_FORWARDING),
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_ROOM_TEMP_FORWARDING_INTERVAL,
                            default=int(
                                options.get(
                                    CONF_ROOM_TEMP_FORWARDING_INTERVAL,
                                    DEFAULT_ROOM_TEMP_FORWARDING_INTERVAL,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=30,
                                max=3600,
                                step=30,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="s",
                            )
                        ),
                        vol.Required(
                            CONF_ROOM_TEMP_FORWARDING_TOLERANCE,
                            default=float(
                                options.get(
                                    CONF_ROOM_TEMP_FORWARDING_TOLERANCE,
                                    DEFAULT_ROOM_TEMP_FORWARDING_TOLERANCE,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=0.1,
                                max=2.0,
                                step=0.1,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="°C",
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required(_OPTIONS_HUMIDITY_SECTION): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_HUMIDITY_FORWARDING,
                            default=options.get(CONF_HUMIDITY_FORWARDING, DEFAULT_HUMIDITY_FORWARDING),
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_HUMIDITY_FORWARDING_INTERVAL,
                            default=int(
                                options.get(
                                    CONF_HUMIDITY_FORWARDING_INTERVAL,
                                    DEFAULT_HUMIDITY_FORWARDING_INTERVAL,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=30,
                                max=3600,
                                step=30,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="s",
                            )
                        ),
                        vol.Required(
                            CONF_HUMIDITY_FORWARDING_TOLERANCE,
                            default=float(
                                options.get(
                                    CONF_HUMIDITY_FORWARDING_TOLERANCE,
                                    DEFAULT_HUMIDITY_FORWARDING_TOLERANCE,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=0.5,
                                max=10.0,
                                step=0.5,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="%",
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required(_OPTIONS_STORAGE_SECTION): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_STORAGE_TEMP_FORWARDING,
                            default=options.get(CONF_STORAGE_TEMP_FORWARDING, DEFAULT_STORAGE_TEMP_FORWARDING),
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_STORAGE_TEMP_FORWARDING_INTERVAL,
                            default=int(
                                options.get(
                                    CONF_STORAGE_TEMP_FORWARDING_INTERVAL,
                                    DEFAULT_STORAGE_TEMP_FORWARDING_INTERVAL,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=30,
                                max=3600,
                                step=30,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="s",
                            )
                        ),
                        vol.Required(
                            CONF_STORAGE_TEMP_FORWARDING_TOLERANCE,
                            default=float(
                                options.get(
                                    CONF_STORAGE_TEMP_FORWARDING_TOLERANCE,
                                    DEFAULT_STORAGE_TEMP_FORWARDING_TOLERANCE,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=0.1,
                                max=2.0,
                                step=0.1,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="°C",
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required(_OPTIONS_KNX_SECTION): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_KNX_BRIDGE,
                            default=options.get(CONF_KNX_BRIDGE, DEFAULT_KNX_BRIDGE),
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_KNX_SEND,
                            default=options.get(CONF_KNX_SEND, DEFAULT_KNX_SEND),
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_KNX_RECEIVE,
                            default=options.get(CONF_KNX_RECEIVE, DEFAULT_KNX_RECEIVE),
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_KNX_RESPOND_TO_READ,
                            default=options.get(CONF_KNX_RESPOND_TO_READ, DEFAULT_KNX_RESPOND_TO_READ),
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_KNX_RESEND_INTERVAL,
                            default=int(options.get(CONF_KNX_RESEND_INTERVAL, DEFAULT_KNX_RESEND_INTERVAL)),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_KNX_RESEND_INTERVAL,
                                max=MAX_KNX_RESEND_INTERVAL,
                                step=60,
                                mode=NumberSelectorMode.BOX,
                                unit_of_measurement="s",
                            )
                        ),
                        vol.Required(
                            CONF_KNX_TOLERANCE,
                            default=float(options.get(CONF_KNX_TOLERANCE, DEFAULT_KNX_TOLERANCE)),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_KNX_TOLERANCE,
                                max=MAX_KNX_TOLERANCE,
                                step=0.1,
                                mode=NumberSelectorMode.SLIDER,
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required(_OPTIONS_MODBUS_SECTION): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_MODBUS_TIMEOUT,
                            default=float(options.get(CONF_MODBUS_TIMEOUT, DEFAULT_MODBUS_TIMEOUT)),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_MODBUS_TIMEOUT,
                                max=MAX_MODBUS_TIMEOUT,
                                step=1.0,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="s",
                            )
                        ),
                        vol.Required(
                            CONF_MODBUS_MAX_RETRIES,
                            default=int(options.get(CONF_MODBUS_MAX_RETRIES, DEFAULT_MODBUS_MAX_RETRIES)),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_MODBUS_MAX_RETRIES,
                                max=MAX_MODBUS_MAX_RETRIES,
                                step=1,
                                mode=NumberSelectorMode.SLIDER,
                            )
                        ),
                        vol.Required(
                            CONF_MODBUS_MESSAGE_SPACING,
                            default=float(options.get(CONF_MODBUS_MESSAGE_SPACING, DEFAULT_MODBUS_MESSAGE_SPACING)),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_MODBUS_MESSAGE_SPACING,
                                max=MAX_MODBUS_MESSAGE_SPACING,
                                step=0.01,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="s",
                            )
                        ),
                        vol.Required(
                            CONF_MODBUS_CONNECT_DELAY,
                            default=float(options.get(CONF_MODBUS_CONNECT_DELAY, DEFAULT_MODBUS_CONNECT_DELAY)),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_MODBUS_CONNECT_DELAY,
                                max=MAX_MODBUS_CONNECT_DELAY,
                                step=0.1,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="s",
                            )
                        ),
                        vol.Required(
                            CONF_POLLING_JITTER,
                            default=int(options.get(CONF_POLLING_JITTER, DEFAULT_POLLING_JITTER)),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_POLLING_JITTER,
                                max=MAX_POLLING_JITTER,
                                step=1,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="%",
                            )
                        ),
                        vol.Required(
                            CONF_COMMUNICATION_DIAGNOSTICS,
                            default=options.get(
                                CONF_COMMUNICATION_DIAGNOSTICS,
                                DEFAULT_COMMUNICATION_DIAGNOSTICS,
                            ),
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_WRITE_COOLDOWN,
                            default=float(options.get(CONF_WRITE_COOLDOWN, DEFAULT_WRITE_COOLDOWN)),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_WRITE_COOLDOWN,
                                max=MAX_WRITE_COOLDOWN,
                                step=1.0,
                                mode=NumberSelectorMode.BOX,
                                unit_of_measurement="s",
                            )
                        ),
                        vol.Required(
                            CONF_EEPROM_WRITE_INTERVAL,
                            default=float(options.get(CONF_EEPROM_WRITE_INTERVAL, DEFAULT_EEPROM_WRITE_INTERVAL)),
                            description={"advanced": True},
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_EEPROM_WRITE_INTERVAL,
                                max=MAX_EEPROM_WRITE_INTERVAL,
                                step=5.0,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement="s",
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


def _clean_pin(value: Any) -> str:
    """Normalize an optional local web PIN from flow input."""
    return str(value or "").strip()


def _web_access_requested(data: dict[str, Any]) -> bool:
    """Return whether setup should require and verify local Navigator web access."""
    if _SETUP_WEB_ACCESS in data:
        return bool(data[_SETUP_WEB_ACCESS])
    # Config-flow schemas always submit the required toggle. The fallback keeps
    # older imported/reconfigure data compatible and treats a stored PIN as the
    # user's existing web-access choice.
    return web_pin_configured(_clean_pin(data.get(CONF_WEB_PIN)))


def _without_setup_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Remove transient form controls before persisting config-entry data."""
    return {key: value for key, value in data.items() if key not in {_SETUP_WEB_ACCESS, CONF_MODEL_OVERRIDE}}


def _uses_modbus_proxy(data: dict[str, Any]) -> bool:
    """Return whether local web access should use a host separate from Modbus."""
    return bool(data.get(CONF_MODBUS_PROXY))


def _web_host_for_input(user_input: dict[str, Any], host: str) -> str:
    if not _uses_modbus_proxy(user_input):
        return host
    return str(user_input.get(CONF_WEB_HOST, "")).strip()


def _stored_web_host(web_host: str, host: str) -> str:
    return "" if web_host == host else web_host


def _normalize_model_override(user_input: dict[str, Any]) -> str:
    """Return a valid model override value, defaulting to ``auto``.

    The field is marked advanced and optional; missing/empty/invalid values
    always fall back to automatic detection so a misconfigured entry never
    forces a wrong Navigator family.
    """
    raw = str(user_input.get(CONF_MODEL_OVERRIDE, DEFAULT_MODEL_OVERRIDE) or "").strip()
    return raw if raw in MODEL_OVERRIDE_OPTIONS else DEFAULT_MODEL_OVERRIDE


def _host_key(host: str) -> str:
    """Return a stable key for duplicate host checks."""
    return host.strip().casefold()


def _entry_host(entry: Any) -> str:
    data = getattr(entry, "data", {})
    if not isinstance(data, dict):
        return ""
    return str(data.get(CONF_HOST, "")).strip()


def _has_duplicate_host(hass: Any, host: str, current_entry_id: str | None = None) -> bool:
    """Return whether another IDM entry already uses this Modbus host."""
    target = _host_key(host)
    if not target:
        return False

    entries = hass.config_entries.async_entries(DOMAIN)
    for entry in entries:
        if current_entry_id is not None and getattr(entry, "entry_id", None) == current_entry_id:
            continue
        if _host_key(_entry_host(entry)) == target:
            return True
    return False


def _build_zones_schema(options: dict[str, Any], zone_count: int) -> vol.Schema:
    existing_rooms = normalize_zone_rooms(options.get(CONF_ZONE_ROOMS, {}))
    schema_dict: dict[Any, Any] = {}
    for z in range(zone_count):
        schema_dict[
            vol.Required(
                f"zone_{z}_rooms",
                default=int(existing_rooms.get(z, 1)),
            )
        ] = NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=MAX_ROOM_COUNT,
                step=1,
                mode=NumberSelectorMode.SLIDER,
            )
        )
    return vol.Schema(schema_dict)


def _room_temp_forwarding_enabled(options: dict[str, Any]) -> bool:
    return bool(options.get(CONF_ROOM_TEMP_FORWARDING, DEFAULT_ROOM_TEMP_FORWARDING))


def _build_room_temp_forwarding_schema(options: dict[str, Any]) -> vol.Schema:
    configured_entities = options.get(CONF_ROOM_TEMP_FORWARDING_ENTITIES, {})
    circuits = options.get(CONF_HEATING_CIRCUITS, ["a"])
    schema_dict: dict[Any, Any] = {}
    for circuit in circuits:
        schema_dict[
            vol.Optional(
                f"room_temp_forwarding_{circuit}",
                default=str(configured_entities.get(circuit, "")),
            )
        ] = _ROOM_TEMPERATURE_SELECTOR
    return vol.Schema(schema_dict)


def _store_room_temp_forwarding_entities(options: dict[str, Any], user_input: dict[str, Any]) -> None:
    circuits = options.get(CONF_HEATING_CIRCUITS, ["a"])
    options[CONF_ROOM_TEMP_FORWARDING_ENTITIES] = {
        circuit: str(user_input.get(f"room_temp_forwarding_{circuit}", "")).strip()
        for circuit in circuits
        if str(user_input.get(f"room_temp_forwarding_{circuit}", "")).strip()
    }


def _humidity_forwarding_enabled(options: dict[str, Any]) -> bool:
    return bool(options.get(CONF_HUMIDITY_FORWARDING, DEFAULT_HUMIDITY_FORWARDING))


def _build_humidity_forwarding_schema(options: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_HUMIDITY_FORWARDING_ENTITY,
                default=str(options.get(CONF_HUMIDITY_FORWARDING_ENTITY, "")),
            ): _HUMIDITY_SELECTOR,
        }
    )


def _store_humidity_forwarding_entity(options: dict[str, Any], user_input: dict[str, Any]) -> None:
    options[CONF_HUMIDITY_FORWARDING_ENTITY] = str(user_input.get(CONF_HUMIDITY_FORWARDING_ENTITY, "")).strip()


# Fixed keys for the GLT storage-temperature registers, matching
# room_temp_forwarding.STORAGE_TEMP_REGISTER_NAMES.
_STORAGE_TEMP_KEYS: tuple[str, ...] = ("heat_storage", "cold_storage", "dhw_bottom", "dhw_top")


def _storage_temp_forwarding_enabled(options: dict[str, Any]) -> bool:
    return bool(options.get(CONF_STORAGE_TEMP_FORWARDING, DEFAULT_STORAGE_TEMP_FORWARDING))


def _build_storage_temp_forwarding_schema(options: dict[str, Any]) -> vol.Schema:
    configured_entities = options.get(CONF_STORAGE_TEMP_FORWARDING_ENTITIES, {})
    schema_dict: dict[Any, Any] = {}
    for key in _STORAGE_TEMP_KEYS:
        schema_dict[
            vol.Optional(
                f"storage_temp_forwarding_{key}",
                default=str(configured_entities.get(key, "")),
            )
        ] = _STORAGE_TEMPERATURE_SELECTOR
    return vol.Schema(schema_dict)


def _store_storage_temp_forwarding_entities(options: dict[str, Any], user_input: dict[str, Any]) -> None:
    options[CONF_STORAGE_TEMP_FORWARDING_ENTITIES] = {
        key: str(user_input.get(f"storage_temp_forwarding_{key}", "")).strip()
        for key in _STORAGE_TEMP_KEYS
        if str(user_input.get(f"storage_temp_forwarding_{key}", "")).strip()
    }


def _knx_bridge_enabled(options: dict[str, Any]) -> bool:
    return bool(options.get(CONF_KNX_BRIDGE, DEFAULT_KNX_BRIDGE))


_KNX_GROUP_SELECTOR: SelectSelector = SelectSelector(
    SelectSelectorConfig(
        options=list(OBJECT_GROUPS),
        multiple=True,
        mode=SelectSelectorMode.LIST,
        translation_key="knx_object_group",
    )
)

_KNX_OVERRIDES_SELECTOR: TextSelector = TextSelector(TextSelectorConfig(multiline=True))


def _format_knx_overrides(overrides: Mapping[str, str]) -> str:
    """Render the override map as one ``register = address`` line each."""
    return "\n".join(f"{register} = {address}" for register, address in sorted(overrides.items()))


def _parse_knx_overrides(text: str) -> dict[str, str]:
    """Parse the override text area into a validated override map.

    Blank lines and ``#`` comments are ignored so a user can annotate the
    list. Raises InvalidGroupAddressError for anything else that does not
    resolve to a known object and a usable group address.
    """
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        entry = line.split("#", 1)[0].strip()
        if not entry:
            continue
        separator = "=" if "=" in entry else ":"
        register, _, address = entry.partition(separator)
        register = register.strip()
        address = address.strip()
        if not register or not address:
            raise InvalidGroupAddressError(f"not a 'register = address' line: {line!r}")
        parsed[register] = address
    return validate_overrides(parsed)


def _build_knx_bridge_schema(options: dict[str, Any]) -> vol.Schema:
    overrides = options.get(CONF_KNX_OVERRIDES) or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_KNX_BASE_ADDRESS,
                default=str(options.get(CONF_KNX_BASE_ADDRESS, DEFAULT_KNX_BASE_ADDRESS)),
            ): str,
            vol.Required(
                CONF_KNX_GROUPS,
                default=list(options.get(CONF_KNX_GROUPS) or OBJECT_GROUPS),
            ): _KNX_GROUP_SELECTOR,
            vol.Optional(
                CONF_KNX_OVERRIDES,
                default=_format_knx_overrides(overrides if isinstance(overrides, Mapping) else {}),
            ): _KNX_OVERRIDES_SELECTOR,
        }
    )


# Optional follow-up steps shown after the base options/zones steps, tried in
# this order. Each entry's predicate decides whether its step is shown at
# all. Adding a future GLT forwarding channel (or any other optional step)
# means adding one entry here and one async_step_<step_id> method below -
# no other step needs to know it exists, since _async_continue_optional_steps
# looks steps up by name instead of each step hardcoding what comes next.
_OPTIONAL_FLOW_STEPS: tuple[tuple[str, Callable[[dict[str, Any]], bool]], ...] = (
    ("room_temp_forwarding", _room_temp_forwarding_enabled),
    ("humidity_forwarding", _humidity_forwarding_enabled),
    ("storage_temp_forwarding", _storage_temp_forwarding_enabled),
    ("knx_bridge", _knx_bridge_enabled),
)


class _IdmOptionsStepsMixin(config_entries.ConfigEntryBaseFlow):
    """Shared option/zone/forwarding step handlers for config and options flows.

    Both IdmHeatpumpConfigFlow and IdmHeatpumpOptionsFlow walk the same
    options -> zones -> (optional steps from _OPTIONAL_FLOW_STEPS) sequence.
    Centralizing the step bodies here keeps them in lockstep instead of
    drifting (the two copies had already diverged subtly in
    description_placeholders).
    """

    # Shared mutable state provided by the concrete flow.
    _options: dict[str, Any]

    def _flow_name_placeholder(self) -> str:
        raise NotImplementedError

    def _create_flow_entry(self) -> ConfigFlowResult:
        raise NotImplementedError

    async def _async_continue_optional_steps(self, after_step_id: str | None = None) -> ConfigFlowResult:
        """Show the next enabled optional step after ``after_step_id``, or finish.

        ``after_step_id=None`` starts from the beginning of
        _OPTIONAL_FLOW_STEPS (called once, right after options/zones). Each
        optional step then calls this again with its own step_id once
        submitted, so the steps stay chained in table order without any of
        them naming the next one directly.
        """
        start = 0
        if after_step_id is not None:
            for index, (step_id, _) in enumerate(_OPTIONAL_FLOW_STEPS):
                if step_id == after_step_id:
                    start = index + 1
                    break
            else:
                raise ValueError(f"Unknown optional flow step: {after_step_id!r}")

        for step_id, is_enabled in _OPTIONAL_FLOW_STEPS[start:]:
            if is_enabled(self._options):
                handler: Callable[[], Awaitable[ConfigFlowResult]] = getattr(self, f"async_step_{step_id}")
                return await handler()
        return self._create_flow_entry()

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            submitted_options = _flatten_options_input(user_input)
            self._options.update(submitted_options)
            if int(submitted_options.get(CONF_ZONE_COUNT, 0)) > 0:
                return await self.async_step_zones()
            self._options[CONF_ZONE_ROOMS] = {}
            return await self._async_continue_optional_steps()

        return self.async_show_form(
            step_id="options",
            data_schema=_build_options_schema(self._options),
            description_placeholders={"name": self._flow_name_placeholder()},
            errors={},
        )

    async def async_step_zones(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        zone_count = int(self._options.get(CONF_ZONE_COUNT, 0))
        if user_input is not None:
            zone_rooms: dict[int, int] = {z: int(user_input.get(f"zone_{z}_rooms", 1)) for z in range(zone_count)}
            self._options[CONF_ZONE_ROOMS] = zone_rooms
            return await self._async_continue_optional_steps()

        return self.async_show_form(
            step_id="zones",
            data_schema=_build_zones_schema(self._options, zone_count),
            description_placeholders={"zone_count": str(zone_count)},
            errors={},
        )

    async def async_step_room_temp_forwarding(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            _store_room_temp_forwarding_entities(self._options, user_input)
            return await self._async_continue_optional_steps("room_temp_forwarding")

        return self.async_show_form(
            step_id="room_temp_forwarding",
            data_schema=_build_room_temp_forwarding_schema(self._options),
            description_placeholders={"name": self._flow_name_placeholder()},
            errors={},
        )

    async def async_step_humidity_forwarding(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            _store_humidity_forwarding_entity(self._options, user_input)
            return await self._async_continue_optional_steps("humidity_forwarding")

        return self.async_show_form(
            step_id="humidity_forwarding",
            data_schema=_build_humidity_forwarding_schema(self._options),
            description_placeholders={"name": self._flow_name_placeholder()},
            errors={},
        )

    async def async_step_storage_temp_forwarding(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            _store_storage_temp_forwarding_entities(self._options, user_input)
            return await self._async_continue_optional_steps("storage_temp_forwarding")

        return self.async_show_form(
            step_id="storage_temp_forwarding",
            data_schema=_build_storage_temp_forwarding_schema(self._options),
            description_placeholders={"name": self._flow_name_placeholder()},
            errors={},
        )

    async def async_step_knx_bridge(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            base_address = str(user_input.get(CONF_KNX_BASE_ADDRESS, "")).strip()
            try:
                validate_base_address(base_address)
            except InvalidGroupAddressError:
                errors[CONF_KNX_BASE_ADDRESS] = "invalid_knx_base_address"
            try:
                overrides = _parse_knx_overrides(str(user_input.get(CONF_KNX_OVERRIDES, "")))
            except InvalidGroupAddressError:
                errors[CONF_KNX_OVERRIDES] = "invalid_knx_overrides"
                overrides = {}
            groups = [group for group in user_input.get(CONF_KNX_GROUPS) or [] if group in OBJECT_GROUPS]
            if not groups:
                errors[CONF_KNX_GROUPS] = "no_knx_groups"
            if not errors:
                self._options[CONF_KNX_BASE_ADDRESS] = base_address
                self._options[CONF_KNX_GROUPS] = groups
                self._options[CONF_KNX_OVERRIDES] = overrides
                return await self._async_continue_optional_steps("knx_bridge")
            self._options[CONF_KNX_BASE_ADDRESS] = base_address
            self._options[CONF_KNX_GROUPS] = groups or list(OBJECT_GROUPS)

        return self.async_show_form(
            step_id="knx_bridge",
            data_schema=_build_knx_bridge_schema(self._options),
            description_placeholders={
                "name": self._flow_name_placeholder(),
                "object_count": str(len(KNX_OBJECTS)),
            },
            errors=errors,
        )


class IdmHeatpumpConfigFlow(_IdmOptionsStepsMixin, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 3

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}
        self._modbus_error = _ModbusConnectionStatus.FAILED.value
        self._reconfigure_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get(CONF_NAME, "").strip()
            host = user_input.get(CONF_HOST, "").strip()

            if not name:
                errors[CONF_NAME] = "name_required"
            elif not host:
                errors[CONF_HOST] = "host_required"
            elif _web_access_requested(user_input) and not web_pin_configured(_clean_pin(user_input.get(CONF_WEB_PIN))):
                errors[CONF_WEB_PIN] = "web_pin_required_or_disable"
            elif (
                _web_access_requested(user_input)
                and _uses_modbus_proxy(user_input)
                and not _web_host_for_input(user_input, host)
            ):
                errors[CONF_WEB_HOST] = "web_host_required"
            elif _has_duplicate_host(self.hass, host):
                errors[CONF_HOST] = "already_configured"
            else:
                port = int(user_input.get(CONF_PORT, DEFAULT_PORT))
                slave_id = int(user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID))
                self._async_abort_entries_match(
                    {
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_SLAVE_ID: slave_id,
                    }
                )

                connection_error = _connection_error_key(await self._test_connection(user_input))
                if connection_error is not None:
                    self._modbus_error = connection_error
                    web_pin = _clean_pin(user_input.get(CONF_WEB_PIN)) if _web_access_requested(user_input) else ""
                    if web_pin_configured(web_pin):
                        _LOGGER.info(
                            "IDM Modbus connection to %s failed, but web PIN is configured; offering web-only fallback",
                            host,
                        )
                        # A proxy setup without a web host was already rejected
                        # by the validation above, so the host is usable here.
                        web_host = _web_host_for_input(user_input, host)
                        self._data = {
                            **_without_setup_fields(user_input),
                            CONF_HOST: host,
                            CONF_NAME: name,
                            CONF_WEB_PIN: web_pin,
                            CONF_MODBUS_PROXY: _uses_modbus_proxy(user_input),
                            CONF_WEB_HOST: _stored_web_host(web_host, host),
                        }
                        return await self.async_step_modbus_failed()
                    _LOGGER.warning(
                        "IDM Modbus connection to %s failed and no web PIN configured; cannot set up integration",
                        host,
                    )
                    errors["base"] = connection_error
                else:
                    web_requested = _web_access_requested(user_input)
                    web_pin = _clean_pin(user_input.get(CONF_WEB_PIN)) if web_requested else ""
                    web_host = _web_host_for_input(user_input, host) if web_requested else host
                    try:
                        detected = await self._async_detect_web_supplement(
                            web_host,
                            web_pin,
                            model_hint=self._data.get(CONF_DETECTED_NAVIGATOR_VERSION),
                            required=web_requested,
                        )
                    except IdmWebAuthenticationFailed:
                        _LOGGER.warning("IDM Navigator web PIN was rejected during setup for host %s", web_host)
                        errors[CONF_WEB_PIN] = "invalid_web_pin"
                    except _WebSupplementConnectionFailed:
                        _LOGGER.warning(
                            "IDM Navigator web interface at %s could not be read during setup; "
                            "check the web host or clear the PIN for Modbus-only operation",
                            web_host,
                        )
                        errors["base"] = "web_cannot_connect"
                    else:
                        self._data = {
                            **_without_setup_fields(user_input),
                            CONF_HOST: host,
                            CONF_NAME: name,
                            CONF_WEB_PIN: web_pin,
                            CONF_MODBUS_PROXY: _uses_modbus_proxy(user_input) if web_requested else False,
                            CONF_WEB_HOST: _stored_web_host(web_host, host),
                            **detected,
                        }
                        return await self.async_step_setup_review()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input or {}),
            description_placeholders={"wiki_url": _MODBUS_SETUP_URL},
            errors=errors,
        )

    async def async_step_setup_review(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show detected endpoints and offer a guided configuration profile."""
        if user_input is not None:
            profile = str(user_input.get(_SETUP_PROFILE, _SETUP_PROFILE_RECOMMENDED))
            self._data[CONF_MODEL_OVERRIDE] = _normalize_model_override(user_input)
            if profile == _SETUP_PROFILE_CUSTOM:
                self._options = _default_options()
                return await self.async_step_options()
            self._options = _options_for_profile(profile)
            return self._create_flow_entry()

        web_enabled = web_pin_configured(_clean_pin(self._data.get(CONF_WEB_PIN)))
        return self.async_show_form(
            step_id="setup_review",
            data_schema=_build_setup_review_schema(self._data),
            description_placeholders={
                "host": str(self._data.get(CONF_HOST, "")),
                "port": str(self._data.get(CONF_PORT, DEFAULT_PORT)),
                "slave_id": str(self._data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)),
                "navigator": str(self._data.get(CONF_DETECTED_NAVIGATOR_VERSION, "not detected")),
                "software": str(self._data.get(CONF_DETECTED_SOFTWARE_VERSION, "not detected")),
                "web": "connected" if web_enabled else "not configured",
            },
            errors={},
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show connection editing and non-destructive diagnostics choices."""
        if user_input is not None:
            return await self.async_step_connection(user_input)
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=["connection", "diagnostics"],
        )

    async def async_step_connection(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Validate and update connection settings."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        self._reconfigure_entry = entry

        if user_input is not None:
            host = user_input.get(CONF_HOST, "").strip()
            if not host:
                errors[CONF_HOST] = "host_required"
            elif _web_access_requested(user_input) and not web_pin_configured(_clean_pin(user_input.get(CONF_WEB_PIN))):
                errors[CONF_WEB_PIN] = "web_pin_required_or_disable"
            elif (
                _web_access_requested(user_input)
                and _uses_modbus_proxy(user_input)
                and not _web_host_for_input(user_input, host)
            ):
                errors[CONF_WEB_HOST] = "web_host_required"
            elif _has_duplicate_host(self.hass, host, entry.entry_id):
                errors[CONF_HOST] = "already_configured"
            else:
                connection_error = _connection_error_key(await self._test_connection(user_input))
                if connection_error is not None:
                    self._modbus_error = connection_error
                    web_pin = _clean_pin(user_input.get(CONF_WEB_PIN)) if _web_access_requested(user_input) else ""
                    if web_pin_configured(web_pin):
                        _LOGGER.info(
                            "IDM Modbus connection to %s failed during reconfigure, but web PIN is configured; offering web-only fallback",
                            host,
                        )
                        # A proxy setup without a web host was already rejected
                        # by the validation above, so the host is usable here.
                        web_host = _web_host_for_input(user_input, host)
                        self._data = {
                            **_without_setup_fields(user_input),
                            CONF_HOST: host,
                            CONF_NAME: entry.title,
                            CONF_WEB_PIN: web_pin,
                            CONF_MODBUS_PROXY: _uses_modbus_proxy(user_input),
                            CONF_WEB_HOST: _stored_web_host(web_host, host),
                        }
                        return await self.async_step_modbus_failed()
                    else:
                        errors["base"] = connection_error
                else:
                    web_requested = _web_access_requested(user_input)
                    web_pin = _clean_pin(user_input.get(CONF_WEB_PIN)) if web_requested else ""
                    web_host = _web_host_for_input(user_input, host) if web_requested else host
                    try:
                        detected = await self._async_detect_web_supplement(
                            web_host,
                            web_pin,
                            model_hint=entry.data.get(CONF_DETECTED_NAVIGATOR_VERSION),
                            required=web_requested,
                        )
                    except IdmWebAuthenticationFailed:
                        _LOGGER.warning(
                            "IDM Navigator web PIN was rejected during reconfiguration for host %s", web_host
                        )
                        errors[CONF_WEB_PIN] = "invalid_web_pin"
                    except _WebSupplementConnectionFailed:
                        _LOGGER.warning(
                            "IDM Navigator web interface at %s could not be read during reconfiguration; "
                            "check the web host or clear the PIN for Modbus-only operation",
                            web_host,
                        )
                        errors["base"] = "web_cannot_connect"
                    else:
                        _LOGGER.info(
                            "IDM reconfiguration validated for host=%s port=%d slave_id=%d; "
                            "web supplement=%s; web-only mode will be disabled",
                            host,
                            int(user_input.get(CONF_PORT, DEFAULT_PORT)),
                            int(user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)),
                            "enabled" if web_pin else "disabled",
                        )
                        return self.async_update_and_abort(
                            entry,
                            data_updates={
                                CONF_HOST: host,
                                CONF_PORT: int(user_input.get(CONF_PORT, DEFAULT_PORT)),
                                CONF_SLAVE_ID: int(user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)),
                                CONF_WEB_PIN: web_pin,
                                CONF_MODBUS_PROXY: _uses_modbus_proxy(user_input) if web_requested else False,
                                CONF_WEB_HOST: _stored_web_host(web_host, host),
                                CONF_MODEL_OVERRIDE: _normalize_model_override(user_input),
                                CONF_WEB_ONLY: False,
                                **detected,
                            },
                        )

        # Re-show the user's just-typed values on a validation/detection
        # failure, not the stale stored entry data — self._data is only
        # populated on success paths above, so falling back to it here would
        # silently discard whatever the user just corrected and re-submitted.
        current_data = user_input or self._data or entry.data
        suggested = {
            CONF_HOST: current_data[CONF_HOST],
            CONF_PORT: current_data.get(CONF_PORT, DEFAULT_PORT),
            CONF_SLAVE_ID: current_data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
            _SETUP_WEB_ACCESS: web_pin_configured(_clean_pin(current_data.get(CONF_WEB_PIN))),
            CONF_WEB_PIN: current_data.get(CONF_WEB_PIN, ""),
            CONF_MODBUS_PROXY: bool(current_data.get(CONF_MODBUS_PROXY) or current_data.get(CONF_WEB_HOST)),
            CONF_WEB_HOST: current_data.get(CONF_WEB_HOST, ""),
            CONF_MODEL_OVERRIDE: current_data.get(CONF_MODEL_OVERRIDE, DEFAULT_MODEL_OVERRIDE),
        }

        return self.async_show_form(
            step_id="connection",
            data_schema=self.add_suggested_values_to_schema(STEP_RECONFIGURE_SCHEMA, suggested),
            description_placeholders={
                "name": entry.title,
                "host": entry.data[CONF_HOST],
                "wiki_url": _MODBUS_SETUP_URL,
            },
            errors=errors,
        )

    async def async_step_diagnostics(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Test configured endpoints without changing the config entry."""
        started = monotonic()
        entry = self._get_reconfigure_entry()
        self._reconfigure_entry = entry
        connection_data = dict(entry.data)
        self._data = connection_data
        host = str(connection_data.get(CONF_HOST, "")).strip()
        port = int(connection_data.get(CONF_PORT, DEFAULT_PORT))
        slave_id = int(connection_data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID))

        connection_error = _connection_error_key(await self._test_connection(connection_data))
        if connection_error is not None:
            _LOGGER.warning(
                "IDM diagnostics test failed for host=%s port=%d slave_id=%d: %s",
                host,
                port,
                slave_id,
                connection_error,
            )
            return self._show_diagnostics_result(
                "diagnostics_failed",
                host,
                port,
                slave_id,
                errors={"base": connection_error},
                duration=monotonic() - started,
                modbus_status="failed",
                web_status="not tested",
            )

        web_pin = _clean_pin(connection_data.get(CONF_WEB_PIN))
        if not web_pin_configured(web_pin):
            _LOGGER.info(
                "IDM diagnostics test succeeded for host=%s port=%d slave_id=%d; web test skipped (no PIN)",
                host,
                port,
                slave_id,
            )
            return self._show_diagnostics_result(
                "diagnostics_modbus_success",
                host,
                port,
                slave_id,
                duration=monotonic() - started,
                modbus_status="connected",
                web_status="not configured",
            )

        web_host = str(connection_data.get(CONF_WEB_HOST) or host).strip()
        try:
            await self._async_detect_web_supplement(
                web_host,
                web_pin,
                model_hint=connection_data.get(CONF_DETECTED_NAVIGATOR_VERSION),
                required=True,
            )
        except IdmWebAuthenticationFailed:
            _LOGGER.warning("IDM diagnostics test: Navigator web PIN rejected by %s", web_host)
            return self._show_diagnostics_result(
                "diagnostics_failed",
                host,
                port,
                slave_id,
                errors={"base": "invalid_web_pin"},
                duration=monotonic() - started,
                modbus_status="connected",
                web_status="authentication failed",
            )
        except _WebSupplementConnectionFailed:
            _LOGGER.warning("IDM diagnostics test: Navigator web interface %s is unavailable", web_host)
            return self._show_diagnostics_result(
                "diagnostics_failed",
                host,
                port,
                slave_id,
                errors={"base": "web_cannot_connect"},
                duration=monotonic() - started,
                modbus_status="connected",
                web_status="unreachable",
            )

        _LOGGER.info(
            "IDM diagnostics test succeeded for Modbus %s:%d (slave %d) and web host %s",
            host,
            port,
            slave_id,
            web_host,
        )
        return self._show_diagnostics_result(
            "diagnostics_success",
            host,
            port,
            slave_id,
            duration=monotonic() - started,
            modbus_status="connected",
            web_status="connected",
        )

    def _show_diagnostics_result(
        self,
        step_id: str,
        host: str,
        port: int,
        slave_id: int,
        *,
        errors: dict[str, str] | None = None,
        duration: float = 0.0,
        modbus_status: str = "unknown",
        web_status: str = "unknown",
    ) -> ConfigFlowResult:
        """Render a translated, repeatable diagnostics result."""
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema({}),
            description_placeholders={
                "host": host,
                "port": str(port),
                "slave_id": str(slave_id),
                "duration": f"{duration:.2f}",
                "modbus_status": modbus_status,
                "web_status": web_status,
                "navigator": str(self._data.get(CONF_DETECTED_NAVIGATOR_VERSION, "not detected")),
                "software": str(self._data.get(CONF_DETECTED_SOFTWARE_VERSION, "not detected")),
            },
            errors=errors or {},
        )

    async def async_step_diagnostics_success(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Repeat a successful full diagnostics test."""
        return await self.async_step_diagnostics()

    async def async_step_diagnostics_modbus_success(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Repeat a successful Modbus-only diagnostics test."""
        return await self.async_step_diagnostics()

    async def async_step_diagnostics_failed(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Repeat a failed diagnostics test."""
        return await self.async_step_diagnostics()

    def _flow_name_placeholder(self) -> str:
        return str(self._data.get(CONF_NAME, ""))

    def _create_flow_entry(self) -> ConfigFlowResult:
        if not _room_temp_forwarding_enabled(self._options):
            self._options[CONF_ROOM_TEMP_FORWARDING_ENTITIES] = {}
        if not _storage_temp_forwarding_enabled(self._options):
            self._options[CONF_STORAGE_TEMP_FORWARDING_ENTITIES] = {}
        if self._reconfigure_entry is not None:
            _LOGGER.info(
                "Updating existing IDM entry %s for web-only operation while preserving its Modbus options",
                self._reconfigure_entry.entry_id,
            )
            return self.async_update_and_abort(
                self._reconfigure_entry,
                data_updates=self._data,
                options=self._options,
            )
        return self.async_create_entry(
            title=self._data[CONF_NAME],
            data=self._data,
            options=self._options,
        )

    async def async_step_modbus_failed(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {"base": self._modbus_error}
        host = str(self._data.get(CONF_HOST, ""))

        if user_input is not None:
            web_pin = _clean_pin(user_input.get(CONF_WEB_PIN, self._data.get(CONF_WEB_PIN)))
            self._data[CONF_WEB_PIN] = web_pin
            if _uses_modbus_proxy(self._data):
                self._data[CONF_WEB_HOST] = str(
                    user_input.get(CONF_WEB_HOST, self._data.get(CONF_WEB_HOST, ""))
                ).strip()

            action = user_input.get("action")
            if action == "retry":
                if self._reconfigure_entry is not None:
                    return await self.async_step_connection()
                return self.async_show_form(
                    step_id="user",
                    data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, self._data),
                    description_placeholders={"wiki_url": _MODBUS_SETUP_URL},
                )
            if action == "web_only":
                if not web_pin_configured(web_pin):
                    errors = {CONF_WEB_PIN: "web_pin_required"}
                    return self.async_show_form(
                        step_id="modbus_failed",
                        data_schema=_build_modbus_failed_schema(self._data),
                        description_placeholders={"host": host},
                        errors=errors,
                    )
                web_host = str(self._data.get(CONF_WEB_HOST) or host).strip()
                _LOGGER.info(
                    "Attempting IDM web-only setup for %s via %s; auto-detecting Navigator web variant",
                    host,
                    web_host,
                )
                try:
                    detected = await self._async_detect_web_supplement(
                        web_host,
                        web_pin,
                        model_hint=self._data.get(CONF_DETECTED_NAVIGATOR_VERSION),
                        required=True,
                    )
                except IdmWebAuthenticationFailed:
                    _LOGGER.warning(
                        "IDM Navigator web interface at %s rejected the PIN during web-only setup",
                        web_host,
                    )
                    errors = {CONF_WEB_PIN: "invalid_web_pin"}
                    return self.async_show_form(
                        step_id="modbus_failed",
                        data_schema=_build_modbus_failed_schema(self._data),
                        description_placeholders={"host": host},
                        errors=errors,
                    )
                except _WebSupplementConnectionFailed:
                    _LOGGER.warning(
                        "IDM Navigator web interface at %s is unavailable during web-only setup",
                        web_host,
                    )
                    errors = {"base": "web_cannot_connect"}
                    return self.async_show_form(
                        step_id="modbus_failed",
                        data_schema=_build_modbus_failed_schema(self._data),
                        description_placeholders={"host": host},
                        errors=errors,
                    )
                _LOGGER.info(
                    "IDM web-only setup for %s succeeded; detected=%s",
                    host,
                    sorted(detected.keys()) if detected else "none",
                )
                self._data[CONF_WEB_ONLY] = True
                if detected:
                    self._data.update(detected)
                return await self.async_step_web_only_options()

        return self.async_show_form(
            step_id="modbus_failed",
            data_schema=_build_modbus_failed_schema(self._data),
            description_placeholders={"host": host},
            errors=errors,
        )

    async def async_step_web_only_options(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            if self._reconfigure_entry is not None:
                # Keep the user's Modbus feature choices while web-only mode is
                # active so they are restored when Modbus is enabled later.
                self._options = dict(self._reconfigure_entry.options)
            else:
                self._options = _default_options()
            self._options.update(
                {
                    CONF_WEB_ENABLED: True,
                    CONF_WEB_SCAN_INTERVAL: int(user_input.get(CONF_WEB_SCAN_INTERVAL, DEFAULT_WEB_SCAN_INTERVAL)),
                }
            )
            return self._create_flow_entry()

        default_interval = DEFAULT_WEB_SCAN_INTERVAL
        if self._reconfigure_entry is not None:
            default_interval = int(
                self._reconfigure_entry.options.get(CONF_WEB_SCAN_INTERVAL, DEFAULT_WEB_SCAN_INTERVAL)
            )
        return self.async_show_form(
            step_id="web_only_options",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_WEB_SCAN_INTERVAL,
                        default=default_interval,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=30,
                            max=1800,
                            step=10,
                            mode=NumberSelectorMode.SLIDER,
                            unit_of_measurement="s",
                        )
                    ),
                }
            ),
            description_placeholders={"name": self._data.get(CONF_NAME, "")},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return IdmHeatpumpOptionsFlow()

    async def _test_tcp_endpoint(self, host: str, port: int) -> _ModbusConnectionStatus:
        """Check DNS and TCP separately so setup can show an actionable cause."""
        writer: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(CONFIG_FLOW_TCP_TIMEOUT):
                _, writer = await asyncio.open_connection(host, port)
        except socket.gaierror as err:
            _LOGGER.warning(
                "IDM setup could not resolve host %s: %s. Check the hostname or use the heat pump IP address",
                host,
                err,
            )
            return _ModbusConnectionStatus.HOST_NOT_FOUND
        except ConnectionRefusedError as err:
            _LOGGER.warning(
                "IDM Modbus TCP connection to %s:%d was refused: %s. "
                "Modbus TCP may be disabled on the heat pump or the configured port may be wrong",
                host,
                port,
                err,
            )
            return _ModbusConnectionStatus.CONNECTION_REFUSED
        except TimeoutError:
            _LOGGER.warning(
                "IDM Modbus TCP connection to %s:%d timed out after %.1f seconds. "
                "Check the IP address, device power, routing and firewall",
                host,
                port,
                CONFIG_FLOW_TCP_TIMEOUT,
            )
            return _ModbusConnectionStatus.TIMEOUT
        except OSError as err:
            _LOGGER.warning(
                "IDM Modbus TCP endpoint %s:%d is unreachable: %s: %s",
                host,
                port,
                err.__class__.__name__,
                err,
            )
            return _ModbusConnectionStatus.UNREACHABLE
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    _LOGGER.debug("TCP preflight connection to %s:%d closed with an error", host, port)

        _LOGGER.debug("IDM Modbus TCP endpoint %s:%d accepted a connection", host, port)
        return _ModbusConnectionStatus.SUCCESS

    async def _test_connection(self, data: dict[str, Any]) -> _ModbusConnectionStatus:
        install_library_log_filter()
        host = str(data[CONF_HOST]).strip()
        port = int(data.get(CONF_PORT, DEFAULT_PORT))
        slave_id = int(data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID))
        client = get_idm_client(
            host=host,
            port=port,
            slave_id=slave_id,
        )
        try:
            await client.connect()
            if not client.is_connected:
                tcp_status = await self._test_tcp_endpoint(host, port)
                if tcp_status is not _ModbusConnectionStatus.SUCCESS:
                    return tcp_status
                _LOGGER.warning(
                    "IDM Modbus connection test to %s:%d (slave %s) failed: TCP is reachable but "
                    "the Modbus client is not connected; check Modbus activation and the slave ID",
                    host,
                    port,
                    slave_id,
                )
                return _ModbusConnectionStatus.NO_RESPONSE
            value = await client.probe_register(
                REGISTER_ADDRESS_CONNECTION_PROBE,
                REGISTER_COUNT_CONNECTION_PROBE,
            )
            if value is not None:
                _LOGGER.info(
                    "IDM Modbus connection test to %s:%d (slave %s) succeeded",
                    host,
                    port,
                    slave_id,
                )
                return _ModbusConnectionStatus.SUCCESS
            _LOGGER.warning(
                "IDM Modbus connection test to %s:%d (slave %s) failed: probe register returned no data",
                host,
                port,
                slave_id,
            )
            return _ModbusConnectionStatus.NO_RESPONSE
        except socket.gaierror as err:
            _LOGGER.warning("IDM Modbus host %s could not be resolved during protocol check: %s", host, err)
            return _ModbusConnectionStatus.HOST_NOT_FOUND
        except ConnectionRefusedError as err:
            _LOGGER.warning(
                "IDM Modbus connection to %s:%d was refused during protocol check: %s",
                host,
                port,
                err,
            )
            return _ModbusConnectionStatus.CONNECTION_REFUSED
        except TimeoutError as err:
            _LOGGER.warning(
                "IDM Modbus connection test to %s:%d (slave %s) timed out: %s",
                host,
                port,
                slave_id,
                err,
            )
            return _ModbusConnectionStatus.TIMEOUT
        except (ConnectionError, OSError) as err:
            _LOGGER.warning(
                "IDM Modbus endpoint %s:%d (slave %s) is unreachable: %s",
                host,
                port,
                slave_id,
                err,
            )
            return _ModbusConnectionStatus.UNREACHABLE
        except Exception as err:  # noqa: BLE001
            tcp_status = await self._test_tcp_endpoint(host, port)
            if tcp_status is not _ModbusConnectionStatus.SUCCESS:
                return tcp_status
            _LOGGER.warning(
                "IDM Modbus connection test to %s:%d (slave %s) failed although TCP is reachable: %s: %s",
                host,
                port,
                slave_id,
                err.__class__.__name__,
                err,
            )
            return _ModbusConnectionStatus.FAILED
        finally:
            try:
                await client.disconnect()
            except Exception:
                _LOGGER.debug("Error closing connection test client", exc_info=True)

    async def _async_detect_web_supplement(
        self,
        host: str,
        pin: str,
        model_hint: str | None = None,
        *,
        required: bool = False,
    ) -> dict[str, str]:
        """Detect optional web metadata during setup/reconfigure."""
        if not web_pin_configured(pin):
            return {}

        try:
            web_supplement = await async_read_web_supplement(host, pin, model_hint=model_hint, hass=self.hass)
        except IdmWebAuthenticationFailed:
            _LOGGER.error("IDM Navigator web PIN was rejected for %s; please re-enter the PIN", host)
            raise
        except Exception as err:
            _LOGGER.debug("Optional web supplement detection failed during config flow", exc_info=True)
            if required:
                raise _WebSupplementConnectionFailed from err
            return {}

        if web_supplement is None:
            if required:
                raise _WebSupplementConnectionFailed
            return {}

        detected: dict[str, str] = {}
        if web_supplement.navigator_version:
            detected[CONF_DETECTED_NAVIGATOR_VERSION] = web_supplement.navigator_version
        if web_supplement.software_version:
            detected[CONF_DETECTED_SOFTWARE_VERSION] = web_supplement.software_version
        web_variant = getattr(web_supplement, "web_variant", None)
        if web_variant:
            detected[CONF_DETECTED_WEB_VARIANT] = web_variant
        return detected


class IdmHeatpumpOptionsFlow(_IdmOptionsStepsMixin, config_entries.OptionsFlow):
    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    def _flow_name_placeholder(self) -> str:
        return str(self.config_entry.title)

    def _create_flow_entry(self) -> ConfigFlowResult:
        if not _room_temp_forwarding_enabled(self._options):
            self._options[CONF_ROOM_TEMP_FORWARDING_ENTITIES] = {}
        if not _storage_temp_forwarding_enabled(self._options):
            self._options[CONF_STORAGE_TEMP_FORWARDING_ENTITIES] = {}
        return self.async_create_entry(data=self._options)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        self._options = dict(self.config_entry.options)
        return await self.async_step_options()
