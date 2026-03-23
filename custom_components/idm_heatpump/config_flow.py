# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT
"""Config flow for IDM Heatpump integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
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
    CONF_HEATING_CIRCUITS,
    CONF_HIDE_UNUSED,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    CONF_TECHNICIAN_CODES,
    CONF_ZONE_COUNT,
    CONF_ZONE_ROOMS,
    DEFAULT_ENABLE_CASCADE,
    DEFAULT_HIDE_UNUSED,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DOMAIN,
    HEATING_CIRCUITS,
    MAX_ROOM_COUNT,
    MAX_ZONE_COUNT,
)

_LOGGER = logging.getLogger(__name__)

# Schema for initial setup – no defaults so add_suggested_values_to_schema fills them
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): NumberSelector(
            NumberSelectorConfig(min=1, max=247, mode=NumberSelectorMode.BOX)
        ),
    }
)

# Schema for reconfigure – values are injected via add_suggested_values_to_schema
STEP_RECONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): NumberSelector(
            NumberSelectorConfig(min=1, max=247, mode=NumberSelectorMode.BOX)
        ),
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
        }
    )


def _build_zones_schema(options: dict[str, Any], zone_count: int) -> vol.Schema:
    existing_rooms: dict = options.get(CONF_ZONE_ROOMS, {})
    schema_dict: dict = {}
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
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get(CONF_NAME, "").strip()
            host = user_input.get(CONF_HOST, "").strip()

            if not name:
                errors[CONF_NAME] = "name_required"
            elif not host:
                errors[CONF_HOST] = "host_required"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()

                if not await self._test_connection(user_input):
                    errors["base"] = "cannot_connect"
                else:
                    self._data = {**user_input, CONF_HOST: host, CONF_NAME: name}
                    return await self.async_step_options()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or {}
            ),
            description_placeholders={
                "wiki_url": "https://github.com/Xerolux/idm-heatpump-hass/wiki"
            },
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
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
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: host,
                        CONF_PORT: int(user_input.get(CONF_PORT, DEFAULT_PORT)),
                        CONF_SLAVE_ID: int(
                            user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
                        ),
                    },
                )

        suggested = {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_PORT: entry.data.get(CONF_PORT, DEFAULT_PORT),
            CONF_SLAVE_ID: entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
        }

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_SCHEMA, suggested
            ),
            description_placeholders={
                "name": entry.title,
                "host": entry.data[CONF_HOST],
                "wiki_url": "https://github.com/Xerolux/idm-heatpump-hass/wiki"
            },
            errors=errors,
        )

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
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

    async def async_step_zones(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        errors: dict[str, str] = {}
        zone_count = int(self._options.get(CONF_ZONE_COUNT, 0))
        schema = _build_zones_schema(self._options, zone_count)

        if user_input is not None:
            zone_rooms: dict[int, int] = {
                z: int(user_input.get(f"zone_{z}_rooms", 1))
                for z in range(zone_count)
            }
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
        from .modbus_client import IdmModbusClient

        client = IdmModbusClient(
            host=str(data[CONF_HOST]).strip(),
            port=int(data.get(CONF_PORT, DEFAULT_PORT)),
            slave_id=int(data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)),
        )
        try:
            return await client.test_connection()
        except Exception as err:
            _LOGGER.debug("Connection test failed: %s", err)
            return False


class IdmHeatpumpOptionsFlow(config_entries.OptionsFlow):
    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        self._options = dict(self.config_entry.options)
        return await self.async_step_options()

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
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

    async def async_step_zones(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        errors: dict[str, str] = {}
        zone_count = int(self._options.get(CONF_ZONE_COUNT, 0))
        schema = _build_zones_schema(self._options, zone_count)

        if user_input is not None:
            zone_rooms: dict[int, int] = {
                z: int(user_input.get(f"zone_{z}_rooms", 1))
                for z in range(zone_count)
            }
            self._options[CONF_ZONE_ROOMS] = zone_rooms
            return self.async_create_entry(data=self._options)

        return self.async_show_form(
            step_id="zones",
            data_schema=schema,
            description_placeholders={"zone_count": str(zone_count)},
            errors=errors,
        )
