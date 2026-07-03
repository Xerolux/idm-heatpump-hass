"""IDM Heatpump integration for Home Assistant."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration

from .const import (
    CONF_ENABLE_CASCADE,
    CONF_DETECTED_NAVIGATOR_VERSION,
    CONF_DETECTED_SOFTWARE_VERSION,
    CONF_HEATING_CIRCUITS,
    CONF_HIDE_UNUSED,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    CONF_WEB_ENABLED,
    CONF_WEB_PIN,
    CONF_WEB_SCAN_INTERVAL,
    CONF_ZONE_COUNT,
    CONF_ZONE_ROOMS,
    DEFAULT_ENABLE_CASCADE,
    DEFAULT_HIDE_UNUSED,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DEFAULT_WEB_ENABLED,
    DEFAULT_WEB_SCAN_INTERVAL,
    DOMAIN,
    MODEL,
    NAME,
)
from .web_data import async_read_web_supplement, merge_model_info, web_pin_configured
from .coordinator import IdmCoordinator
from idm_heatpump import IdmModbusClient, IdmModelInfo
from idm_heatpump.const import MODEL_UNKNOWN

from .library_adapter import get_idm_client
from .registers import (
    get_all_binary_sensor_descriptions,
    get_all_number_descriptions,
    get_all_select_descriptions,
    get_all_sensor_descriptions,
    get_all_switch_descriptions,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)
_LEGACY_ENTITY_UNIQUE_ID = re.compile(r"^.+:\d+_(?P<entity_key>.+)$")


@dataclass
class IdmHeatpumpData:
    """Runtime data stored in ConfigEntry.runtime_data."""

    coordinator: IdmCoordinator
    client: IdmModbusClient
    web_task: asyncio.Task[None] | None = None


IdmConfigEntry: TypeAlias = ConfigEntry[IdmHeatpumpData]


async def _detect_model_info(client: IdmModbusClient) -> tuple[str, str | None]:
    """Probe the heat pump for its model and firmware version.

    Returns (model_name, firmware_version). detect_model() reads a handful of
    registers to distinguish Navigator 2.0, Navigator 10 and Navigator Pro;
    model_name falls back to the generic MODEL constant if detection fails
    (e.g. older firmware, transient Modbus error) or is inconclusive, so
    setup never fails because of this.

    firmware_version is read via getattr defensively: idm-heatpump-api 0.3.4
    does not expose it on IdmModelInfo yet, but a future release is expected
    to add it. This picks it up automatically once available, without a
    version bump here or raising on the current release.
    """
    try:
        model_info = await client.detect_model()
    except Exception:
        _LOGGER.debug("Heat pump model auto-detection failed", exc_info=True)
        return MODEL, None

    model_name = getattr(model_info, "model_name", None)
    if not (isinstance(model_name, str) and model_name and model_name != MODEL_UNKNOWN):
        model_name = MODEL

    firmware_value = getattr(model_info, "firmware_version", None)
    firmware_version = str(firmware_value) if firmware_value is not None else None
    if not firmware_version:
        firmware_version = None

    return model_name, firmware_version


async def _web_poll_loop(coordinator: IdmCoordinator, interval: int) -> None:
    """Poll optional web supplement data independently from Modbus."""
    await asyncio.sleep(0.3)
    while True:
        await coordinator.async_refresh_web_supplement()
        await asyncio.sleep(interval)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the IDM Heatpump component.

    Services are registered here (action-setup rule) so they are available
    as soon as the domain loads, independently of config entries.
    """
    from .services import async_setup_services

    await async_setup_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: IdmConfigEntry) -> bool:
    """Migrate connection-based IDs to stable config-entry-based IDs."""
    if entry.version != 1 or entry.minor_version >= 2:
        return True

    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        match = _LEGACY_ENTITY_UNIQUE_ID.fullmatch(entity.unique_id)
        if match is None:
            continue
        new_unique_id = f"{entry.entry_id}_{match.group('entity_key')}"
        entity_registry.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)

    hass.config_entries.async_update_entry(
        entry,
        unique_id=None,
        version=1,
        minor_version=2,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: IdmConfigEntry) -> bool:
    integration = await async_get_integration(hass, DOMAIN)
    _LOGGER.info("Setting up %s v%s", NAME, integration.manifest.get("version", "unknown"))

    host = str(entry.data[CONF_HOST])
    port = int(entry.data.get(CONF_PORT, 502))
    slave_id = int(entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID))
    scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    circuits = entry.options.get(CONF_HEATING_CIRCUITS, ["a"])
    zone_count = int(entry.options.get(CONF_ZONE_COUNT, 0))
    zone_rooms = entry.options.get(CONF_ZONE_ROOMS, {})
    hide_unused = entry.options.get(CONF_HIDE_UNUSED, DEFAULT_HIDE_UNUSED)
    enable_cascade = entry.options.get(CONF_ENABLE_CASCADE, DEFAULT_ENABLE_CASCADE)
    web_pin = str(entry.data.get(CONF_WEB_PIN, "")).strip() or None
    web_enabled = bool(entry.options.get(CONF_WEB_ENABLED, DEFAULT_WEB_ENABLED))
    web_scan_interval = int(entry.options.get(CONF_WEB_SCAN_INTERVAL, DEFAULT_WEB_SCAN_INTERVAL))

    if web_pin_configured(web_pin):
        ir.async_delete_issue(hass, DOMAIN, "web_pin_missing")
    else:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "web_pin_missing",
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="web_pin_missing",
            translation_placeholders={"name": entry.title},
        )

    # Use the library via the adapter (migration Option B)
    client = get_idm_client(host=host, port=port, slave_id=slave_id)

    try:
        await client.connect()
    except Exception as err:
        try:
            await client.disconnect()
        except Exception:
            _LOGGER.warning("Failed to clean up client for %s:%d", host, port, exc_info=True)
        _LOGGER.error("Failed to connect to %s:%d - %s", host, port, err)
        raise ConfigEntryNotReady(f"Cannot connect to {host}:{port}") from err

    try:
        model_name, firmware_version = await _detect_model_info(client)
        detected_model_name = entry.data.get(CONF_DETECTED_NAVIGATOR_VERSION)
        if isinstance(detected_model_name, str) and detected_model_name.strip():
            model_name = detected_model_name.strip()
        detected_firmware_version = entry.data.get(CONF_DETECTED_SOFTWARE_VERSION)
        if isinstance(detected_firmware_version, str) and detected_firmware_version.strip():
            firmware_version = detected_firmware_version.strip()

        web_supplement = None
        if web_enabled and web_pin_configured(web_pin):
            try:
                web_supplement = await async_read_web_supplement(host, web_pin)
            except Exception:
                _LOGGER.debug("Initial IDM web supplement detection failed", exc_info=True)
            model_name, firmware_version = merge_model_info(
                model_name,
                firmware_version,
                web_supplement,
            )

        detected_model_info = client.model_info
        if not isinstance(detected_model_info, IdmModelInfo):
            detected_model_info = None

        sensor_descs = get_all_sensor_descriptions(
            circuits, zone_count, zone_rooms, enable_cascade, detected_model_info
        )
        binary_descs = get_all_binary_sensor_descriptions(
            circuits, zone_count, zone_rooms, enable_cascade, detected_model_info
        )
        number_descs = get_all_number_descriptions(
            circuits, zone_count, zone_rooms, enable_cascade, detected_model_info
        )
        select_descs = get_all_select_descriptions(
            circuits, zone_count, zone_rooms, enable_cascade, detected_model_info
        )
        switch_descs = get_all_switch_descriptions(
            circuits, zone_count, zone_rooms, enable_cascade, detected_model_info
        )

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
            model_name=model_name,
            firmware_version=firmware_version,
            model_info=detected_model_info,
            web_pin=web_pin if web_enabled else None,
            web_supplement=web_supplement,
        )
        coordinator.setup_registers(
            circuits,
            zone_count,
            zone_rooms,
            enable_cascade,
            model_info=detected_model_info,
        )

        web_task = None
        if web_enabled and web_pin_configured(web_pin):
            web_task = asyncio.create_task(_web_poll_loop(coordinator, web_scan_interval))

        entry.runtime_data = IdmHeatpumpData(
            coordinator=coordinator,
            client=client,
            web_task=web_task,
        )

        await coordinator.async_config_entry_first_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        try:
            await client.disconnect()
        except Exception:
            _LOGGER.warning("Failed to clean up client for %s:%d", host, port, exc_info=True)
        raise

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IdmConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        web_task = getattr(entry.runtime_data, "web_task", None)
        if isinstance(web_task, asyncio.Future):
            web_task.cancel()
            try:
                await web_task
            except asyncio.CancelledError:
                pass
        await entry.runtime_data.client.disconnect()
        from .services import async_unload_services

        await async_unload_services(hass)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: IdmConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
