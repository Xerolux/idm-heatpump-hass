"""IDM Navigator Heatpump integration for Home Assistant."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.loader import async_get_integration

from .const import (
    CONF_HEATING_CIRCUITS,
    CONF_HIDE_UNUSED,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    CONF_ZONE_COUNT,
    CONF_ZONE_ROOMS,
    DEFAULT_HIDE_UNUSED,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DOMAIN,
    NAME,
)
from .coordinator import IdmCoordinator
from .modbus_client import IdmModbusClient
from .registers import (
    get_all_binary_sensor_descriptions,
    get_all_number_descriptions,
    get_all_select_descriptions,
    get_all_sensor_descriptions,
    get_all_switch_descriptions,
)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    integration = await async_get_integration(hass, DOMAIN)
    _LOGGER.info(
        "Setting up %s v%s", NAME, integration.manifest.get("version", "unknown")
    )

    host = str(entry.data[CONF_HOST])
    port = int(entry.data.get(CONF_PORT, 502))
    slave_id = int(entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID))
    scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    circuits = entry.options.get(CONF_HEATING_CIRCUITS, ["A"])
    zone_count = int(entry.options.get(CONF_ZONE_COUNT, 0))
    zone_rooms = entry.options.get(CONF_ZONE_ROOMS, {})
    hide_unused = entry.options.get(CONF_HIDE_UNUSED, DEFAULT_HIDE_UNUSED)

    client = IdmModbusClient(host=host, port=port, slave_id=slave_id)

    try:
        await client.connect()
    except Exception as err:
        _LOGGER.error("Failed to connect to %s:%d - %s", host, port, err)
        raise ConfigEntryNotReady(f"Cannot connect to {host}:{port}") from err

    sensor_descs = get_all_sensor_descriptions(circuits, zone_count, zone_rooms)
    binary_descs = get_all_binary_sensor_descriptions(circuits, zone_count, zone_rooms)
    number_descs = get_all_number_descriptions(circuits, zone_count, zone_rooms)
    select_descs = get_all_select_descriptions(circuits, zone_count, zone_rooms)
    switch_descs = get_all_switch_descriptions(circuits, zone_count, zone_rooms)

    coordinator = IdmCoordinator(
        hass=hass,
        config_entry=entry,
        client=client,
        scan_interval=timedelta(seconds=scan_interval),
        sensor_descriptions=sensor_descs,
        binary_sensor_descriptions=binary_descs,
        number_descriptions=number_descs,
        select_descriptions=select_descs,
        switch_descriptions=switch_descs,
        hide_unused=hide_unused,
    )
    coordinator.setup_registers(circuits, zone_count, zone_rooms)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    from .services import async_setup_services
    await async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        client: IdmModbusClient = data["client"]
        await client.disconnect()
        from .services import async_unload_services
        await async_unload_services(hass)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
