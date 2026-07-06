"""Config flow for IDM Heatpump integration."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries

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
)
from .web_data import IdmWebAuthenticationFailed, async_read_web_supplement, web_pin_configured

_LOGGER = logging.getLogger(__name__)

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
            vol.Required(
                CONF_ROOM_TEMP_FORWARDING,
                default=options.get(CONF_ROOM_TEMP_FORWARDING, DEFAULT_ROOM_TEMP_FORWARDING),
            ): BooleanSelector(BooleanSelectorConfig()),
            vol.Required(
                CONF_ROOM_TEMP_FORWARDING_INTERVAL,
                default=int(options.get(CONF_ROOM_TEMP_FORWARDING_INTERVAL, DEFAULT_ROOM_TEMP_FORWARDING_INTERVAL)),
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
                default=float(options.get(CONF_ROOM_TEMP_FORWARDING_TOLERANCE, DEFAULT_ROOM_TEMP_FORWARDING_TOLERANCE)),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.1,
                    max=2.0,
                    step=0.1,
                    mode=NumberSelectorMode.SLIDER,
                    unit_of_measurement="°C",
                )
            ),
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
    raw_existing_rooms = options.get(CONF_ZONE_ROOMS, {})
    existing_rooms: dict[int, int] = {}
    if isinstance(raw_existing_rooms, dict):
        existing_rooms = {int(zone): int(rooms) for zone, rooms in raw_existing_rooms.items()}
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


class IdmHeatpumpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}

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

                if not await self._test_connection(user_input):
                    web_pin = _clean_pin(user_input.get(CONF_WEB_PIN))
                    if web_pin_configured(web_pin):
                        _LOGGER.info(
                            "IDM Modbus connection to %s failed, but web PIN is configured; offering web-only fallback",
                            host,
                        )
                        web_host = _web_host_for_input(user_input, host)
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
                    errors["base"] = "cannot_connect"
                else:
                    web_pin = _clean_pin(user_input.get(CONF_WEB_PIN))
                    web_host = _web_host_for_input(user_input, host)
                    if web_pin and _uses_modbus_proxy(user_input) and not web_host:
                        errors[CONF_WEB_HOST] = "web_host_required"
                        return self.async_show_form(
                            step_id="user",
                            data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input),
                            description_placeholders={"wiki_url": "https://github.com/Xerolux/idm-heatpump-hass/wiki"},
                            errors=errors,
                        )
                    try:
                        detected = await self._async_detect_web_supplement(web_host, web_pin)
                    except IdmWebAuthenticationFailed:
                        _LOGGER.warning("IDM Navigator web PIN was rejected during setup for host %s", web_host)
                        errors[CONF_WEB_PIN] = "invalid_web_pin"
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
            description_placeholders={"wiki_url": "https://github.com/Xerolux/idm-heatpump-hass/wiki"},
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input.get(CONF_HOST, "").strip()
            if not host:
                errors[CONF_HOST] = "host_required"
            elif _has_duplicate_host(self.hass, host, entry.entry_id):
                errors[CONF_HOST] = "already_configured"
            elif not await self._test_connection(user_input):
                errors["base"] = "cannot_connect"
            else:
                web_pin = _clean_pin(user_input.get(CONF_WEB_PIN))
                web_host = _web_host_for_input(user_input, host)
                if web_pin and _uses_modbus_proxy(user_input) and not web_host:
                    errors[CONF_WEB_HOST] = "web_host_required"
                    return self.async_show_form(
                        step_id="reconfigure",
                        data_schema=self.add_suggested_values_to_schema(STEP_RECONFIGURE_SCHEMA, user_input),
                        description_placeholders={
                            "name": entry.title,
                            "host": entry.data[CONF_HOST],
                            "wiki_url": "https://github.com/Xerolux/idm-heatpump-hass/wiki",
                        },
                        errors=errors,
                    )
                try:
                    detected = await self._async_detect_web_supplement(web_host, web_pin)
                except IdmWebAuthenticationFailed:
                    _LOGGER.warning("IDM Navigator web PIN was rejected during reconfiguration for host %s", web_host)
                    errors[CONF_WEB_PIN] = "invalid_web_pin"
                else:
                    return self.async_update_and_abort(
                        entry,
                        data_updates={
                            CONF_HOST: host,
                            CONF_PORT: int(user_input.get(CONF_PORT, DEFAULT_PORT)),
                            CONF_SLAVE_ID: int(user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)),
                            CONF_WEB_PIN: web_pin,
                            CONF_MODBUS_PROXY: _uses_modbus_proxy(user_input),
                            CONF_WEB_HOST: _stored_web_host(web_host, host),
                            **detected,
                        },
                    )

        suggested = {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_PORT: entry.data.get(CONF_PORT, DEFAULT_PORT),
            CONF_SLAVE_ID: entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
            CONF_WEB_PIN: entry.data.get(CONF_WEB_PIN, ""),
            CONF_MODBUS_PROXY: bool(entry.data.get(CONF_MODBUS_PROXY) or entry.data.get(CONF_WEB_HOST)),
            CONF_WEB_HOST: entry.data.get(CONF_WEB_HOST, ""),
        }

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(STEP_RECONFIGURE_SCHEMA, suggested),
            description_placeholders={
                "name": entry.title,
                "host": entry.data[CONF_HOST],
                "wiki_url": "https://github.com/Xerolux/idm-heatpump-hass/wiki",
            },
            errors=errors,
        )

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        schema = _build_options_schema(self._options)

        if user_input is not None:
            self._options.update(user_input)
            if int(user_input.get(CONF_ZONE_COUNT, 0)) > 0:
                return await self.async_step_zones()
            self._options[CONF_ZONE_ROOMS] = {}
            if _room_temp_forwarding_enabled(self._options):
                return await self.async_step_room_temp_forwarding()
            return self._async_create_config_entry()

        return self.async_show_form(
            step_id="options",
            data_schema=schema,
            description_placeholders={"name": self._data.get(CONF_NAME, "")},
            errors=errors,
        )

    async def async_step_zones(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        zone_count = int(self._options.get(CONF_ZONE_COUNT, 0))
        schema = _build_zones_schema(self._options, zone_count)

        if user_input is not None:
            zone_rooms: dict[int, int] = {z: int(user_input.get(f"zone_{z}_rooms", 1)) for z in range(zone_count)}
            self._options[CONF_ZONE_ROOMS] = zone_rooms
            if _room_temp_forwarding_enabled(self._options):
                return await self.async_step_room_temp_forwarding()
            return self._async_create_config_entry()

        return self.async_show_form(
            step_id="zones",
            data_schema=schema,
            description_placeholders={"zone_count": str(zone_count)},
            errors=errors,
        )

    async def async_step_room_temp_forwarding(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        schema = _build_room_temp_forwarding_schema(self._options)

        if user_input is not None:
            _store_room_temp_forwarding_entities(self._options, user_input)
            return self._async_create_config_entry()

        return self.async_show_form(
            step_id="room_temp_forwarding",
            data_schema=schema,
            description_placeholders={"name": self._data.get(CONF_NAME, "")},
            errors=errors,
        )

    def _async_create_config_entry(self) -> ConfigFlowResult:
        if not _room_temp_forwarding_enabled(self._options):
            self._options[CONF_ROOM_TEMP_FORWARDING_ENTITIES] = {}
        return self.async_create_entry(
            title=self._data[CONF_NAME],
            data=self._data,
            options=self._options,
        )

    async def async_step_modbus_failed(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        host = str(self._data.get(CONF_HOST, ""))

        if user_input is not None:
            action = user_input.get("action")
            if action == "retry":
                return self.async_show_form(
                    step_id="user",
                    data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, self._data),
                    description_placeholders={"wiki_url": "https://github.com/Xerolux/idm-heatpump-hass/wiki"},
                )
            if action == "web_only":
                web_pin = str(self._data.get(CONF_WEB_PIN, "")).strip()
                web_host = str(self._data.get(CONF_WEB_HOST) or host).strip()
                _LOGGER.info(
                    "Attempting IDM web-only setup for %s via %s; auto-detecting Navigator web variant",
                    host,
                    web_host,
                )
                try:
                    detected = await self._async_detect_web_supplement(web_host, web_pin)
                except IdmWebAuthenticationFailed:
                    _LOGGER.warning(
                        "IDM Navigator web interface at %s rejected the PIN during web-only setup",
                        web_host,
                    )
                    errors["base"] = "invalid_web_pin_web_only"
                    return self.async_show_form(
                        step_id="modbus_failed",
                        data_schema=vol.Schema(
                            {
                                vol.Required("action"): SelectSelector(
                                    SelectSelectorConfig(
                                        options=["retry", "web_only"],
                                        mode=SelectSelectorMode.DROPDOWN,
                                        translation_key="modbus_failed_action",
                                    )
                                )
                            }
                        ),
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
            data_schema=vol.Schema(
                {
                    vol.Required("action"): SelectSelector(
                        SelectSelectorConfig(
                            options=["retry", "web_only"],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="modbus_failed_action",
                        )
                    )
                }
            ),
            description_placeholders={"host": host},
            errors=errors,
        )

    async def async_step_web_only_options(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._options = {
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                CONF_HIDE_UNUSED: DEFAULT_HIDE_UNUSED,
                CONF_HEATING_CIRCUITS: ["a"],
                CONF_ZONE_COUNT: 0,
                CONF_ZONE_ROOMS: {},
                CONF_TECHNICIAN_CODES: False,
                CONF_ENABLE_CASCADE: False,
                CONF_WEB_ENABLED: True,
                CONF_WEB_SCAN_INTERVAL: int(user_input.get(CONF_WEB_SCAN_INTERVAL, DEFAULT_WEB_SCAN_INTERVAL)),
                CONF_ROOM_TEMP_FORWARDING: False,
                CONF_ROOM_TEMP_FORWARDING_ENTITIES: {},
                CONF_ROOM_TEMP_FORWARDING_INTERVAL: DEFAULT_ROOM_TEMP_FORWARDING_INTERVAL,
                CONF_ROOM_TEMP_FORWARDING_TOLERANCE: DEFAULT_ROOM_TEMP_FORWARDING_TOLERANCE,
                CONF_MODBUS_TIMEOUT: DEFAULT_MODBUS_TIMEOUT,
                CONF_MODBUS_MAX_RETRIES: DEFAULT_MODBUS_MAX_RETRIES,
            }
            return self._async_create_config_entry()

        return self.async_show_form(
            step_id="web_only_options",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_WEB_SCAN_INTERVAL,
                        default=DEFAULT_WEB_SCAN_INTERVAL,
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

    async def _test_connection(self, data: dict[str, Any]) -> bool:
        from idm_heatpump import IdmModbusClient

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
                _LOGGER.warning(
                    "IDM Modbus connection test to %s:%d (slave %s) failed: not connected after connect()",
                    host,
                    port,
                    slave_id,
                )
                return False
            value = await client.probe_register(1000, 2)
            if value is not None:
                _LOGGER.info(
                    "IDM Modbus connection test to %s:%d (slave %s) succeeded",
                    host,
                    port,
                    slave_id,
                )
                return True
            _LOGGER.warning(
                "IDM Modbus connection test to %s:%d (slave %s) failed: probe register returned no data",
                host,
                port,
                slave_id,
            )
            return False
        except Exception as err:
            _LOGGER.warning(
                "IDM Modbus connection test to %s:%d (slave %s) failed: %s: %s",
                host,
                port,
                slave_id,
                err.__class__.__name__,
                err,
            )
            return False
        finally:
            try:
                await client.disconnect()
            except Exception:
                _LOGGER.debug("Error closing connection test client", exc_info=True)

    async def _async_detect_web_supplement(self, host: str, pin: str) -> dict[str, str]:
        """Detect optional web metadata during setup/reconfigure."""
        if not web_pin_configured(pin):
            return {}

        # Keep Modbus test and local web access slightly offset.
        await asyncio.sleep(0.3)
        try:
            web_supplement = await async_read_web_supplement(host, pin)
        except IdmWebAuthenticationFailed:
            _LOGGER.error("IDM Navigator web PIN was rejected for %s; please re-enter the PIN", host)
            raise
        except Exception:
            _LOGGER.debug("Optional web supplement detection failed during config flow", exc_info=True)
            return {}

        if web_supplement is None:
            return {}

        detected: dict[str, str] = {}
        if web_supplement.navigator_version:
            detected[CONF_DETECTED_NAVIGATOR_VERSION] = web_supplement.navigator_version
        if web_supplement.software_version:
            detected[CONF_DETECTED_SOFTWARE_VERSION] = web_supplement.software_version
        return detected


class IdmHeatpumpOptionsFlow(config_entries.OptionsFlow):
    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        self._options = dict(self.config_entry.options)
        return await self.async_step_options()

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        schema = _build_options_schema(self._options)

        if user_input is not None:
            self._options.update(user_input)
            if int(user_input.get(CONF_ZONE_COUNT, 0)) > 0:
                return await self.async_step_zones()
            self._options[CONF_ZONE_ROOMS] = {}
            if _room_temp_forwarding_enabled(self._options):
                return await self.async_step_room_temp_forwarding()
            return self._async_create_options_entry()

        return self.async_show_form(
            step_id="options",
            data_schema=schema,
            description_placeholders={"name": self.config_entry.title},
            errors=errors,
        )

    async def async_step_zones(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        zone_count = int(self._options.get(CONF_ZONE_COUNT, 0))
        schema = _build_zones_schema(self._options, zone_count)

        if user_input is not None:
            zone_rooms: dict[int, int] = {z: int(user_input.get(f"zone_{z}_rooms", 1)) for z in range(zone_count)}
            self._options[CONF_ZONE_ROOMS] = zone_rooms
            if _room_temp_forwarding_enabled(self._options):
                return await self.async_step_room_temp_forwarding()
            return self._async_create_options_entry()

        return self.async_show_form(
            step_id="zones",
            data_schema=schema,
            description_placeholders={"zone_count": str(zone_count)},
            errors=errors,
        )

    async def async_step_room_temp_forwarding(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        schema = _build_room_temp_forwarding_schema(self._options)

        if user_input is not None:
            _store_room_temp_forwarding_entities(self._options, user_input)
            return self._async_create_options_entry()

        return self.async_show_form(
            step_id="room_temp_forwarding",
            data_schema=schema,
            description_placeholders={"name": self.config_entry.title},
            errors=errors,
        )

    def _async_create_options_entry(self) -> ConfigFlowResult:
        if not _room_temp_forwarding_enabled(self._options):
            self._options[CONF_ROOM_TEMP_FORWARDING_ENTITIES] = {}
        return self.async_create_entry(data=self._options)
