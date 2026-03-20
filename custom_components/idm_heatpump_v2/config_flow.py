"""Config flow for IDM Navigator Heatpump integration."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_HEATING_CIRCUITS,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    CONF_ZONE_COUNT,
    CONF_ZONE_ROOMS,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DOMAIN,
    HEATING_CIRCUITS,
    MAX_ROOM_COUNT,
    MAX_ZONE_COUNT,
)

_LOGGER = logging.getLogger(__name__)

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


def _build_options_schema(options: dict[str, Any]) -> vol.Schema:
    circuits_default = options.get(CONF_HEATING_CIRCUITS, ["A"])
    if "A" not in circuits_default:
        circuits_default = ["A"] + [c for c in circuits_default if c != "A"]
    
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5, max=300, step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            vol.Required(
                CONF_HEATING_CIRCUITS,
                default=circuits_default,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=HEATING_CIRCUITS,
                    multiple=True,
                )
            ),
            vol.Required(
                CONF_ZONE_COUNT,
                default=options.get(CONF_ZONE_COUNT, 0),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=MAX_ZONE_COUNT, mode=NumberSelectorMode.BOX)
            ),
        }
    )


def _build_zones_schema(options: dict[str, Any], zone_count: int) -> vol.Schema:
    schema_dict: dict = {}
    for z in range(zone_count):
        schema_dict[
            vol.Required(
                f"zone_{z}_rooms",
                default=options.get(CONF_ZONE_ROOMS, {}).get(z, 1),
            )
        ] = NumberSelector(
            NumberSelectorConfig(min=1, max=MAX_ROOM_COUNT, mode=NumberSelectorMode.BOX)
        )
    return vol.Schema(schema_dict)


class IdmHeatpumpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data = user_input.copy()
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            if not await self._test_connection(user_input):
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_options()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_options(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        schema = _build_options_schema(self._options)

        if user_input is not None:
            self._options.update(user_input)
            if user_input.get(CONF_ZONE_COUNT, 0) > 0:
                return await self.async_step_zones()
            return self.async_create_entry(
                title=self._data[CONF_NAME],
                data=self._data,
                options=self._options,
            )

        return self.async_show_form(
            step_id="options",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_zones(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        zone_count = self._options.get(CONF_ZONE_COUNT, 0)
        schema = _build_zones_schema(self._options, zone_count)

        if user_input is not None:
            zone_rooms: dict[int, int] = {}
            for z in range(zone_count):
                zone_rooms[z] = user_input.get(f"zone_{z}_rooms", 1)
            self._options[CONF_ZONE_ROOMS] = zone_rooms
            return self.async_create_entry(
                title=self._data[CONF_NAME],
                data=self._data,
                options=self._options,
            )

        return self.async_show_form(
            step_id="zones",
            data_schema=schema,
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
            host=data[CONF_HOST],
            port=data.get(CONF_PORT, DEFAULT_PORT),
            slave_id=data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
        )
        try:
            return await client.test_connection()
        except Exception as err:
            _LOGGER.debug("Connection test failed: %s", err)
            return False


class IdmHeatpumpOptionsFlow(config_entries.OptionsFlow):
    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        self._options = dict(self.config_entry.options)
        return await self.async_step_options()

    async def async_step_options(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        schema = _build_options_schema(self._options)

        if user_input is not None:
            self._options.update(user_input)
            if user_input.get(CONF_ZONE_COUNT, 0) > 0:
                return await self.async_step_zones()
            self._options[CONF_ZONE_ROOMS] = {}
            return self.async_create_entry(data=self._options)

        return self.async_show_form(
            step_id="options",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_zones(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        zone_count = self._options.get(CONF_ZONE_COUNT, 0)
        schema = _build_zones_schema(self._options, zone_count)

        if user_input is not None:
            zone_rooms: dict[int, int] = {}
            for z in range(zone_count):
                zone_rooms[z] = user_input.get(f"zone_{z}_rooms", 1)
            self._options[CONF_ZONE_ROOMS] = zone_rooms
            return self.async_create_entry(data=self._options)

        return self.async_show_form(
            step_id="zones",
            data_schema=schema,
            errors=errors,
        )
