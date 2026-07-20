"""Config flow for IDM Heatpump integration."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import asyncio
import logging
import socket
from enum import StrEnum
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import section

try:
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:
    from typing import Any

    ConfigFlowResult = dict[str, Any]  # type: ignore[assignment]
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant.core import callback
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
    CONF_ENABLE_CASCADE,
    CONF_DETECTED_NAVIGATOR_VERSION,
    CONF_DETECTED_SOFTWARE_VERSION,
    CONF_DETECTED_WEB_VARIANT,
    CONF_DEVICE_HIERARCHY,
    CONF_HEATING_CIRCUITS,
    CONF_HIDE_UNUSED,
    CONF_MODBUS_MAX_RETRIES,
    CONF_MODBUS_PROXY,
    CONF_MODBUS_TIMEOUT,
    CONF_ROOM_TEMP_FORWARDING,
    CONF_ROOM_TEMP_FORWARDING_ENTITIES,
    CONF_ROOM_TEMP_FORWARDING_INTERVAL,
    CONF_ROOM_TEMP_FORWARDING_TOLERANCE,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    CONF_TECHNICIAN_CODES,
    CONF_WEB_ENABLED,
    CONF_WEB_HOST,
    CONF_WEB_ONLY,
    CONF_WEB_PIN,
    CONF_WEB_SCAN_INTERVAL,
    CONF_ZONE_COUNT,
    CONF_ZONE_ROOMS,
    CONFIG_FLOW_TCP_TIMEOUT,
    DEFAULT_DEVICE_HIERARCHY,
    DEFAULT_ENABLE_CASCADE,
    DEFAULT_HIDE_UNUSED,
    DEFAULT_MODBUS_MAX_RETRIES,
    DEFAULT_MODBUS_TIMEOUT,
    DEFAULT_PORT,
    DEFAULT_ROOM_TEMP_FORWARDING,
    DEFAULT_ROOM_TEMP_FORWARDING_INTERVAL,
    DEFAULT_ROOM_TEMP_FORWARDING_TOLERANCE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DEFAULT_WEB_ENABLED,
    DEFAULT_WEB_SCAN_INTERVAL,
    DOMAIN,
    HEATING_CIRCUITS,
    MAX_MODBUS_MAX_RETRIES,
    MAX_MODBUS_TIMEOUT,
    MAX_ROOM_COUNT,
    MAX_ZONE_COUNT,
    MIN_MODBUS_MAX_RETRIES,
    MIN_MODBUS_TIMEOUT,
    REGISTER_ADDRESS_CONNECTION_PROBE,
    REGISTER_COUNT_CONNECTION_PROBE,
)
from .log_filter import install_pymodbus_log_filter
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


# Schema for initial setup – no defaults so add_suggested_values_to_schema fills them
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Required(CONF_HOST): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): NumberSelector(
            NumberSelectorConfig(min=1, max=247, mode=NumberSelectorMode.BOX)
        ),
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
        vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): NumberSelector(
            NumberSelectorConfig(min=1, max=247, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_WEB_PIN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        vol.Optional(CONF_MODBUS_PROXY, default=False): BooleanSelector(BooleanSelectorConfig()),
        vol.Optional(CONF_WEB_HOST): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
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

_ROOM_TEMPERATURE_SELECTOR = EntitySelector(
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
_OPTIONS_MODBUS_SECTION = "advanced_modbus"
_OPTIONS_SECTION_KEYS = (
    _OPTIONS_FEATURES_SECTION,
    _OPTIONS_ROOM_SECTION,
    _OPTIONS_MODBUS_SECTION,
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
                            CONF_TECHNICIAN_CODES,
                            default=options.get(CONF_TECHNICIAN_CODES, False),
                        ): BooleanSelector(BooleanSelectorConfig()),
                        vol.Required(
                            CONF_ENABLE_CASCADE,
                            default=options.get(CONF_ENABLE_CASCADE, DEFAULT_ENABLE_CASCADE),
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
                {"collapsed": False},
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
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


def _clean_pin(value: Any) -> str:
    """Normalize an optional local web PIN from flow input."""
    return str(value or "").strip()


def _uses_modbus_proxy(data: dict[str, Any]) -> bool:
    """Return whether local web access should use a host separate from Modbus."""
    return bool(data.get(CONF_MODBUS_PROXY))


def _web_host_for_input(user_input: dict[str, Any], host: str) -> str:
    if not _uses_modbus_proxy(user_input):
        return host
    return str(user_input.get(CONF_WEB_HOST, "")).strip()


def _stored_web_host(web_host: str, host: str) -> str:
    return "" if web_host == host else web_host


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


class _IdmOptionsStepsMixin:
    """Shared option/zone/room-temp step handlers for config and options flows.

    Both IdmHeatpumpConfigFlow and IdmHeatpumpOptionsFlow walk the same
    options -> zones -> room_temp_forwarding sequence. Centralizing the step
    bodies here keeps them in lockstep instead of drifting (the two copies had
    already diverged subtly in description_placeholders).
    """

    # Shared mutable state provided by the concrete flow.
    _options: dict[str, Any]

    def _flow_name_placeholder(self) -> str:
        raise NotImplementedError

    def _create_flow_entry(self) -> ConfigFlowResult:
        raise NotImplementedError

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            submitted_options = _flatten_options_input(user_input)
            self._options.update(submitted_options)
            if int(submitted_options.get(CONF_ZONE_COUNT, 0)) > 0:
                return await self.async_step_zones()  # type: ignore[attr-defined]
            self._options[CONF_ZONE_ROOMS] = {}
            if _room_temp_forwarding_enabled(self._options):
                return await self.async_step_room_temp_forwarding()  # type: ignore[attr-defined]
            return self._create_flow_entry()

        return self.async_show_form(  # type: ignore[attr-defined]
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
            if _room_temp_forwarding_enabled(self._options):
                return await self.async_step_room_temp_forwarding()  # type: ignore[attr-defined]
            return self._create_flow_entry()

        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="zones",
            data_schema=_build_zones_schema(self._options, zone_count),
            description_placeholders={"zone_count": str(zone_count)},
            errors={},
        )

    async def async_step_room_temp_forwarding(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            _store_room_temp_forwarding_entities(self._options, user_input)
            return self._create_flow_entry()

        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="room_temp_forwarding",
            data_schema=_build_room_temp_forwarding_schema(self._options),
            description_placeholders={"name": self._flow_name_placeholder()},
            errors={},
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
                    web_pin = _clean_pin(user_input.get(CONF_WEB_PIN))
                    if web_pin_configured(web_pin):
                        _LOGGER.info(
                            "IDM Modbus connection to %s failed, but web PIN is configured; offering web-only fallback",
                            host,
                        )
                        web_host = _web_host_for_input(user_input, host)
                        if _uses_modbus_proxy(user_input) and not web_host:
                            errors[CONF_WEB_HOST] = "web_host_required"
                            return self.async_show_form(
                                step_id="user",
                                data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input),
                                description_placeholders={"wiki_url": _MODBUS_SETUP_URL},
                                errors=errors,
                            )
                        self._data = {
                            **user_input,
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
                    web_pin = _clean_pin(user_input.get(CONF_WEB_PIN))
                    web_host = _web_host_for_input(user_input, host)
                    if web_pin and _uses_modbus_proxy(user_input) and not web_host:
                        errors[CONF_WEB_HOST] = "web_host_required"
                        return self.async_show_form(
                            step_id="user",
                            data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input),
                            description_placeholders={"wiki_url": _MODBUS_SETUP_URL},
                            errors=errors,
                        )
                    try:
                        detected = await self._async_detect_web_supplement(
                            web_host,
                            web_pin,
                            model_hint=self._data.get(CONF_DETECTED_NAVIGATOR_VERSION),
                            required=bool(web_pin),
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
                            **user_input,
                            CONF_HOST: host,
                            CONF_NAME: name,
                            CONF_WEB_PIN: web_pin,
                            CONF_MODBUS_PROXY: _uses_modbus_proxy(user_input),
                            CONF_WEB_HOST: _stored_web_host(web_host, host),
                            **detected,
                        }
                        return await self.async_step_options()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input or {}),
            description_placeholders={"wiki_url": _MODBUS_SETUP_URL},
            errors=errors,
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
            elif _has_duplicate_host(self.hass, host, entry.entry_id):
                errors[CONF_HOST] = "already_configured"
            else:
                connection_error = _connection_error_key(await self._test_connection(user_input))
                if connection_error is not None:
                    self._modbus_error = connection_error
                    web_pin = _clean_pin(user_input.get(CONF_WEB_PIN))
                    if web_pin_configured(web_pin):
                        _LOGGER.info(
                            "IDM Modbus connection to %s failed during reconfigure, but web PIN is configured; offering web-only fallback",
                            host,
                        )
                        web_host = _web_host_for_input(user_input, host)
                        if _uses_modbus_proxy(user_input) and not web_host:
                            errors[CONF_WEB_HOST] = "web_host_required"
                        else:
                            self._data = {
                                **user_input,
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
                    web_pin = _clean_pin(user_input.get(CONF_WEB_PIN))
                    web_host = _web_host_for_input(user_input, host)
                    if web_pin and _uses_modbus_proxy(user_input) and not web_host:
                        errors[CONF_WEB_HOST] = "web_host_required"
                        return self.async_show_form(
                            step_id="connection",
                            data_schema=self.add_suggested_values_to_schema(STEP_RECONFIGURE_SCHEMA, user_input),
                            description_placeholders={
                                "name": entry.title,
                                "host": entry.data[CONF_HOST],
                                "wiki_url": _MODBUS_SETUP_URL,
                            },
                            errors=errors,
                        )
                    try:
                        detected = await self._async_detect_web_supplement(
                            web_host,
                            web_pin,
                            model_hint=entry.data.get(CONF_DETECTED_NAVIGATOR_VERSION),
                            required=bool(web_pin),
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
                                CONF_MODBUS_PROXY: _uses_modbus_proxy(user_input),
                                CONF_WEB_HOST: _stored_web_host(web_host, host),
                                CONF_WEB_ONLY: False,
                                **detected,
                            },
                        )

        current_data = self._data or entry.data
        suggested = {
            CONF_HOST: current_data[CONF_HOST],
            CONF_PORT: current_data.get(CONF_PORT, DEFAULT_PORT),
            CONF_SLAVE_ID: current_data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
            CONF_WEB_PIN: current_data.get(CONF_WEB_PIN, ""),
            CONF_MODBUS_PROXY: bool(current_data.get(CONF_MODBUS_PROXY) or current_data.get(CONF_WEB_HOST)),
            CONF_WEB_HOST: current_data.get(CONF_WEB_HOST, ""),
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
        entry = self._get_reconfigure_entry()
        self._reconfigure_entry = entry
        connection_data = dict(entry.data)
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
            )

        web_pin = _clean_pin(connection_data.get(CONF_WEB_PIN))
        if not web_pin_configured(web_pin):
            _LOGGER.info(
                "IDM diagnostics test succeeded for host=%s port=%d slave_id=%d; web test skipped (no PIN)",
                host,
                port,
                slave_id,
            )
            return self._show_diagnostics_result("diagnostics_modbus_success", host, port, slave_id)

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
            )
        except _WebSupplementConnectionFailed:
            _LOGGER.warning("IDM diagnostics test: Navigator web interface %s is unavailable", web_host)
            return self._show_diagnostics_result(
                "diagnostics_failed",
                host,
                port,
                slave_id,
                errors={"base": "web_cannot_connect"},
            )

        _LOGGER.info(
            "IDM diagnostics test succeeded for Modbus %s:%d (slave %d) and web host %s",
            host,
            port,
            slave_id,
            web_host,
        )
        return self._show_diagnostics_result("diagnostics_success", host, port, slave_id)

    def _show_diagnostics_result(
        self,
        step_id: str,
        host: str,
        port: int,
        slave_id: int,
        *,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Render a translated, repeatable diagnostics result."""
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema({}),
            description_placeholders={
                "host": host,
                "port": str(port),
                "slave_id": str(slave_id),
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
                self._options = {
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    CONF_HIDE_UNUSED: DEFAULT_HIDE_UNUSED,
                    CONF_HEATING_CIRCUITS: ["a"],
                    CONF_ZONE_COUNT: 0,
                    CONF_ZONE_ROOMS: {},
                    CONF_TECHNICIAN_CODES: False,
                    CONF_ENABLE_CASCADE: False,
                    CONF_ROOM_TEMP_FORWARDING: False,
                    CONF_ROOM_TEMP_FORWARDING_ENTITIES: {},
                    CONF_ROOM_TEMP_FORWARDING_INTERVAL: DEFAULT_ROOM_TEMP_FORWARDING_INTERVAL,
                    CONF_ROOM_TEMP_FORWARDING_TOLERANCE: DEFAULT_ROOM_TEMP_FORWARDING_TOLERANCE,
                    CONF_MODBUS_TIMEOUT: DEFAULT_MODBUS_TIMEOUT,
                    CONF_MODBUS_MAX_RETRIES: DEFAULT_MODBUS_MAX_RETRIES,
                }
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
        from idm_heatpump import IdmModbusClient

        install_pymodbus_log_filter()
        host = str(data[CONF_HOST]).strip()
        port = int(data.get(CONF_PORT, DEFAULT_PORT))
        slave_id = int(data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID))
        client = IdmModbusClient(
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
        except Exception as err:
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
            web_supplement = await async_read_web_supplement(host, pin, model_hint=model_hint)
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
        return self.async_create_entry(data=self._options)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        self._options = dict(self.config_entry.options)
        return await self.async_step_options()
