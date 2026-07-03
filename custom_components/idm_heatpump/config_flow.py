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
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    CONF_TECHNICIAN_CODES,
    CONF_WEB_ENABLED,
    CONF_WEB_HOST,
    CONF_WEB_PIN,
    CONF_WEB_SCAN_INTERVAL,
    CONF_ZONE_COUNT,
    CONF_ZONE_ROOMS,
    DEFAULT_ENABLE_CASCADE,
    DEFAULT_HIDE_UNUSED,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DEFAULT_WEB_ENABLED,
    DEFAULT_WEB_SCAN_INTERVAL,
    DOMAIN,
    HEATING_CIRCUITS,
    MAX_ROOM_COUNT,
    MAX_ZONE_COUNT,
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
        }
    )


def _clean_pin(value: Any) -> str:
    """Normalize an optional local web PIN from flow input."""
    return str(value or "").strip()


def _clean_web_host(value: Any, fallback_host: str) -> str:
    """Normalize an optional local web host from flow input."""
    return str(value or "").strip() or fallback_host


def _build_zones_schema(options: dict[str, Any], zone_count: int) -> vol.Schema:
    existing_rooms: dict[int, int] = options.get(CONF_ZONE_ROOMS, {})
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
                    errors["base"] = "cannot_connect"
                else:
                    web_pin = _clean_pin(user_input.get(CONF_WEB_PIN))
                    web_host = _clean_web_host(user_input.get(CONF_WEB_HOST), host)
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
                            CONF_WEB_HOST: "" if web_host == host else web_host,
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
            elif not await self._test_connection(user_input):
                errors["base"] = "cannot_connect"
            else:
                web_pin = _clean_pin(user_input.get(CONF_WEB_PIN))
                web_host = _clean_web_host(user_input.get(CONF_WEB_HOST), host)
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
                            CONF_WEB_HOST: "" if web_host == host else web_host,
                            **detected,
                        },
                    )

        suggested = {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_PORT: entry.data.get(CONF_PORT, DEFAULT_PORT),
            CONF_SLAVE_ID: entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
            CONF_WEB_PIN: entry.data.get(CONF_WEB_PIN, ""),
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
            return self.async_create_entry(
                title=self._data[CONF_NAME],
                data=self._data,
                options=self._options,
            )

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
            return self.async_create_entry(
                title=self._data[CONF_NAME],
                data=self._data,
                options=self._options,
            )

        return self.async_show_form(
            step_id="zones",
            data_schema=schema,
            description_placeholders={"zone_count": str(zone_count)},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return IdmHeatpumpOptionsFlow()

    async def _test_connection(self, data: dict[str, Any]) -> bool:
        from idm_heatpump import IdmModbusClient

        client = IdmModbusClient(
            host=str(data[CONF_HOST]).strip(),
            port=int(data.get(CONF_PORT, DEFAULT_PORT)),
            slave_id=int(data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)),
        )
        try:
            await client.connect()
            if not client.is_connected:
                return False
            value = await client.probe_register(1000, 2)
            if value is not None:
                return True
            _LOGGER.warning("Connection test: could not read test register")
            return False
        except Exception as err:
            _LOGGER.debug("Connection test failed: %s", err)
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
            return self.async_create_entry(data=self._options)

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
            return self.async_create_entry(data=self._options)

        return self.async_show_form(
            step_id="zones",
            data_schema=schema,
            description_placeholders={"zone_count": str(zone_count)},
            errors=errors,
        )
