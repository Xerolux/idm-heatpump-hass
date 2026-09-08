"""IDM Heatpump integration for Home Assistant."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — unofficial community integration for IDM Navigator 2.0 / 10 heat pumps
# Created by Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# SPDX-License-Identifier: MIT
import asyncio
import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, TypeAlias, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration

from idm_heatpump import (
    MODEL_UNKNOWN,
    IdmModbusClient,
    IdmModelInfo,
)

from .const import (
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
    CONF_MODBUS_TIMEOUT,
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
    CONF_WEB_ENABLED,
    CONF_WEB_HOST,
    CONF_WEB_ONLY,
    CONF_WEB_PIN,
    CONF_WEB_SCAN_INTERVAL,
    CONF_WRITE_COOLDOWN,
    CONF_ZONE_COUNT,
    CONF_ZONE_ROOMS,
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
    DEFAULT_POLLING_JITTER,
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
    DEFAULT_WEB_ONLY,
    DEFAULT_WEB_SCAN_INTERVAL,
    DEFAULT_WRITE_COOLDOWN,
    DOMAIN,
    MAX_WEB_BACKOFF_FACTOR,
    MODEL,
    NAME,
    WEB_SETUP_READ_TIMEOUT,
)
from .coordinator import IdmCoordinator
from .device_hierarchy import (
    cleanup_deconfigured_heating_circuit_entities,
    cleanup_stale_hierarchy_devices,
    cleanup_stale_web_sensor_entities,
    precreate_main_device,
)
from .error_messages import (
    classify_communication_error,
    classify_web_error,
    friendly_communication_error,
    friendly_web_error,
    scoped_issue_id,
)
from .knx_bridge import KnxBridge, KnxBridgeConfig
from .knx_catalog import OBJECT_GROUPS, InvalidGroupAddressError
from .library_adapter import get_idm_client
from .model_resolution import (
    DetectionResult,
    StoredDetection,
    plan_web_read,
    plant_shape,
    resolve_model,
    resolved_model_override,
)
from .operation_analysis import OperationAnalysis
from .polling_plan import ensure_entity_aware_polling
from .registers import (
    get_all_binary_sensor_descriptions,
    get_all_number_descriptions,
    get_all_select_descriptions,
    get_all_sensor_descriptions,
    get_all_switch_descriptions,
    normalize_zone_rooms,
)
from .room_temp_forwarding import (
    HumidityForwarder,
    HumidityForwardingConfig,
    RoomTempForwarder,
    RoomTempForwardingConfig,
    register_for_storage_temp_key,
)
from .versions import async_runtime_versions
from .web_data import (
    IdmWebAuthenticationFailed,
    async_read_web_supplement,
    web_pin_configured,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.CLIMATE,
    Platform.WATER_HEATER,
    Platform.BUTTON,
]

_LOGGER = logging.getLogger(__name__)
_LEGACY_ENTITY_UNIQUE_ID = re.compile(r"^.+:\d+_(?P<entity_key>.+)$")


# Config-entry data keys that only store retroactive detection metadata.
# Changing them must not force a full integration reload.
_DETECTION_ONLY_DATA_KEYS = frozenset(
    {
        CONF_DETECTED_NAVIGATOR_VERSION,
        CONF_DETECTED_SOFTWARE_VERSION,
        CONF_DETECTED_WEB_VARIANT,
    }
)


@dataclass
class IdmHeatpumpData:
    """Runtime data stored in ConfigEntry.runtime_data."""

    coordinator: IdmCoordinator
    client: IdmModbusClient
    web_task: asyncio.Task[None] | None = None
    room_temp_forwarding_task: asyncio.Task[None] | None = None
    humidity_forwarding_task: asyncio.Task[None] | None = None
    storage_temp_forwarding_task: asyncio.Task[None] | None = None
    knx_bridge: KnxBridge | None = None
    operation_analysis: OperationAnalysis | None = None
    reload_fingerprint: str | None = None
    loaded_platforms: tuple[Platform, ...] = ()


IdmConfigEntry: TypeAlias = ConfigEntry[IdmHeatpumpData]


def _entry_reload_fingerprint(entry: ConfigEntry) -> str:
    """Return a stable fingerprint of settings that require a reload.

    Detection-only keys (navigator version, software version, web variant)
    are excluded so ``IdmCoordinator._persist_web_detection`` can update
    ``entry.data`` without tearing down Modbus, web polls, or active writes.
    """
    data = {key: value for key, value in dict(entry.data).items() if key not in _DETECTION_ONLY_DATA_KEYS}
    options = dict(entry.options)
    return json.dumps({"data": data, "options": options}, sort_keys=True, default=str)


def _create_entry_background_task(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coro: Any,
    *,
    name: str,
) -> asyncio.Task[None]:
    """Create a background task tracked by the config entry when supported.

    Looks up ``async_create_background_task`` on the entry **class** so unit
    tests that pass a MagicMock entry still fall back to ``asyncio.create_task``
    instead of swallowing the coroutine into another MagicMock.
    """
    create_bg = getattr(type(entry), "async_create_background_task", None)
    if callable(create_bg):
        return cast("asyncio.Task[None]", create_bg(entry, hass, coro, name))
    create_task = getattr(hass, "async_create_task", None)
    if callable(create_task):
        return cast("asyncio.Task[None]", create_task(coro))
    return asyncio.create_task(coro)


def _register_update_listener(entry: IdmConfigEntry) -> None:
    """Store the reload fingerprint and attach the update listener."""
    entry.runtime_data.reload_fingerprint = _entry_reload_fingerprint(entry)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))


async def _detect_model_info(client: IdmModbusClient) -> tuple[str, str | None, IdmModelInfo | None]:
    """Probe the heat pump for its model and firmware version.

    Returns (model_name, firmware_version, model_info). detect_model() reads
    only the model-probe registers to distinguish Navigator 2.0, Navigator 10
    and Navigator Pro. It intentionally skips the optional firmware register
    probe because register 4120 is unreliable on some Navigator 10 firmwares.
    model_name falls back to the generic MODEL constant if detection fails
    (e.g. older firmware, transient Modbus error) or is inconclusive, so setup
    never fails because of this.

    firmware_version is read via getattr defensively so a test double or a
    future IdmModelInfo shape that omits the field never raises here.
    """
    try:
        model_info = await client.detect_model(read_firmware=False)
    except Exception:
        _LOGGER.warning(
            "IDM Modbus model detection failed; using generic model %s and isolating unsupported registers during polling",
            MODEL,
            exc_info=True,
        )
        return MODEL, None, None

    model_name = getattr(model_info, "model_name", None)
    if not (isinstance(model_name, str) and model_name and model_name != MODEL_UNKNOWN):
        fallback_model_name = getattr(client, "model_name", None)
        if isinstance(fallback_model_name, str) and fallback_model_name and fallback_model_name != MODEL_UNKNOWN:
            model_name = fallback_model_name
        else:
            model_name = MODEL

    firmware_value = getattr(model_info, "firmware_version", None)
    firmware_version = str(firmware_value) if firmware_value is not None else None
    if not firmware_version:
        firmware_version = None

    detected_model_info = model_info if isinstance(model_info, IdmModelInfo) else None
    return model_name, firmware_version, detected_model_info


async def _web_poll_loop(coordinator: IdmCoordinator, interval: int) -> None:
    """Poll optional web supplement data independently from Modbus.

    Backs off on repeated failures. A Navigator that is switched off, or a web
    host that is simply wrong, used to be retried at the full rate forever, and
    every attempt paid the connect timeout of both protocol variants. The loop
    also stops entirely once the controller has rejected the PIN: Navigator
    firmware locks the local login after repeated failures, so continuing to
    retry is how the integration would cause the lockout it then reports. The
    repair issue asks the user for a new PIN, and applying one reloads the entry
    and restarts this loop.
    """
    await asyncio.sleep(0.3)
    failures = 0
    while True:
        try:
            await coordinator.async_refresh_web_supplement()
        except Exception:
            _LOGGER.exception("Unhandled error in IDM web poll loop; retrying next cycle")
            failures += 1
        else:
            failures = 0 if coordinator.last_web_error is None else failures + 1

        if coordinator.web_auth_blocked:
            _LOGGER.warning(
                "IDM Navigator web polling stopped: the local web PIN was rejected. "
                "Enter a valid PIN through the repair issue or reconfigure to resume"
            )
            return

        delay = interval * min(2**failures, MAX_WEB_BACKOFF_FACTOR)
        await asyncio.sleep(delay)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the IDM Heatpump component.

    Services are registered here (action-setup rule) so they are available
    as soon as the domain loads, independently of config entries.
    """
    from .log_filter import install_library_log_filter
    from .services import async_setup_services

    install_library_log_filter()

    await async_setup_services(hass)
    return True


async def _async_setup_web_only_entry(
    hass: HomeAssistant,
    entry: IdmConfigEntry,
    host: str,
    port: int,
    slave_id: int,
    scan_interval: int,
    web_pin: str | None,
    web_host: str,
    web_scan_interval: int,
    device_hierarchy_enabled: bool,
) -> bool:
    """Set up a web-only integration entry (no Modbus)."""
    _LOGGER.info(
        "Setting up IDM heat pump %s in web-only mode via %s (Modbus will not be used)",
        entry.title,
        web_host,
    )
    ir.async_delete_issue(hass, DOMAIN, scoped_issue_id(entry.entry_id, "web_pin_missing"))

    if bool(entry.options.get(CONF_KNX_BRIDGE, DEFAULT_KNX_BRIDGE)):
        # The bridge serves Modbus register values; a web-only entry has none,
        # so it would come up with nothing to publish. Say so instead of
        # leaving an enabled option looking active.
        _LOGGER.warning(
            "KNX bridge for %s is enabled but stays off in web-only mode: it serves Modbus "
            "register values, which a web-only entry does not read",
            entry.title,
        )

    web_supplement = None
    model_name: str = MODEL
    firmware_version: str | None = None
    stored_web_variant = entry.data.get(CONF_DETECTED_WEB_VARIANT)
    if stored_web_variant not in ("nav10", "nav20"):
        stored_web_variant = None

    try:
        web_supplement = await async_read_web_supplement(
            web_host,
            web_pin,
            model_hint=entry.data.get(CONF_DETECTED_NAVIGATOR_VERSION),
            preferred_variant=stored_web_variant,
            allow_variant_fallback=stored_web_variant is None,
            hass=hass,
            read_timeout=WEB_SETUP_READ_TIMEOUT,
        )
    except Exception as err:
        issue_id = classify_web_error(err)
        _LOGGER.warning(
            "%s. Continuing with a generic model; the web polling loop will retry automatically",
            friendly_web_error(issue_id, web_host),
        )
        _LOGGER.debug("Technical Navigator web-only setup error", exc_info=True)

    if web_supplement is not None:
        model_name = web_supplement.model_name or MODEL
        firmware_version = web_supplement.software_version
        _LOGGER.info(
            "IDM web-only setup for %s detected model=%s firmware=%s",
            web_host,
            model_name,
            firmware_version or "unknown",
        )
    else:
        _LOGGER.warning(
            "IDM web-only setup for %s could not detect the heat pump model; using generic %s",
            web_host,
            MODEL,
        )

    # A user-configured override is authoritative even in web-only mode (it
    # only affects the device model label here, since web-only has no Modbus
    # register map). The web-supplement firmware version is still kept.
    override_model_name = resolved_model_override(entry.data)
    if override_model_name is not None:
        _LOGGER.warning(
            "IDM Navigator model override active in web-only mode: using %s",
            override_model_name,
        )
        model_name = override_model_name

    client = get_idm_client(host=host, port=port, slave_id=slave_id)

    empty_descriptions: list[dict[str, Any]] = []
    coordinator = IdmCoordinator(
        hass=hass,
        config_entry=entry,
        client=client,
        # Web-only entries are refreshed by _web_poll_loop. Disabling the
        # DataUpdateCoordinator scheduler prevents empty Modbus polls from
        # marking all web entities unavailable.
        scan_interval=None,
        sensor_descriptions=empty_descriptions,
        binary_sensor_descriptions=empty_descriptions,
        number_descriptions=empty_descriptions,
        select_descriptions=empty_descriptions,
        switch_descriptions=empty_descriptions,
        hide_unused=False,
        model_name=model_name,
        firmware_version=firmware_version,
        model_info=None,
        web_pin=web_pin,
        web_host=web_host,
        web_supplement=web_supplement,
        web_variant=stored_web_variant,
        device_hierarchy_enabled=device_hierarchy_enabled,
    )
    # A web-only entry reads no Modbus registers at all.
    coordinator.setup_registers([], 0, {}, descriptions=[])
    coordinator.data = {}

    entry.runtime_data = IdmHeatpumpData(
        coordinator=coordinator,
        client=client,
        loaded_platforms=(Platform.SENSOR,),
    )

    precreate_main_device(hass, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    cleanup_stale_hierarchy_devices(hass, coordinator)
    cleanup_deconfigured_heating_circuit_entities(hass, coordinator)
    cleanup_stale_web_sensor_entities(hass, coordinator)

    entry.runtime_data.web_task = _create_entry_background_task(
        hass,
        entry,
        _web_poll_loop(coordinator, web_scan_interval),
        name=f"{DOMAIN}_web_poll_{entry.entry_id}",
    )

    _register_update_listener(entry)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: IdmConfigEntry) -> bool:
    """Migrate entity IDs and preserve existing device placement safely."""
    if entry.version != 1:
        return True
    if entry.minor_version >= 3:
        return True

    if entry.minor_version < 2:
        entity_registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            match = _LEGACY_ENTITY_UNIQUE_ID.fullmatch(entity.unique_id)
            if match is None:
                continue
            new_unique_id = f"{entry.entry_id}_{match.group('entity_key')}"
            entity_registry.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)

    options = dict(entry.options)
    if entry.minor_version < 3 and CONF_DEVICE_HIERARCHY not in options:
        # Existing users keep the previous single-device layout until they
        # explicitly opt in. New entries default to the hierarchy in the flow.
        options[CONF_DEVICE_HIERARCHY] = False

    hass.config_entries.async_update_entry(
        entry,
        unique_id=None,
        options=options,
        version=1,
        minor_version=3,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: IdmConfigEntry) -> bool:
    integration = await async_get_integration(hass, DOMAIN)
    versions = await async_runtime_versions(integration.manifest.get("version"))
    _LOGGER.info(
        "Setting up %s v%s (idm-heatpump-api v%s, modbus-connection v%s, tmodbus v%s)",
        NAME,
        versions.integration,
        versions.api,
        versions.modbus_connection,
        versions.tmodbus,
    )

    host = str(entry.data[CONF_HOST])
    port = int(entry.data.get(CONF_PORT, 502))
    slave_id = int(entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID))
    scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    circuits = entry.options.get(CONF_HEATING_CIRCUITS, ["a"])
    zone_count = int(entry.options.get(CONF_ZONE_COUNT, 0))
    zone_rooms = normalize_zone_rooms(entry.options.get(CONF_ZONE_ROOMS, {}))
    hide_unused = entry.options.get(CONF_HIDE_UNUSED, DEFAULT_HIDE_UNUSED)
    short_cycle_minutes = int(entry.options.get(CONF_SHORT_CYCLE_MINUTES, DEFAULT_SHORT_CYCLE_MINUTES))
    device_hierarchy_enabled = bool(entry.options.get(CONF_DEVICE_HIERARCHY, DEFAULT_DEVICE_HIERARCHY))
    enable_cascade = entry.options.get(CONF_ENABLE_CASCADE, DEFAULT_ENABLE_CASCADE)
    web_pin = str(entry.data.get(CONF_WEB_PIN, "")).strip() or None
    web_host = str(entry.data.get(CONF_WEB_HOST, "")).strip() or host
    web_enabled = bool(entry.options.get(CONF_WEB_ENABLED, DEFAULT_WEB_ENABLED))
    web_scan_interval = int(entry.options.get(CONF_WEB_SCAN_INTERVAL, DEFAULT_WEB_SCAN_INTERVAL))
    stored_web_variant = entry.data.get(CONF_DETECTED_WEB_VARIANT)
    if stored_web_variant not in ("nav10", "nav20"):
        stored_web_variant = None
    room_temp_forwarding_enabled = bool(entry.options.get(CONF_ROOM_TEMP_FORWARDING, DEFAULT_ROOM_TEMP_FORWARDING))
    room_temp_forwarding_entities = entry.options.get(CONF_ROOM_TEMP_FORWARDING_ENTITIES, {})
    room_temp_forwarding_interval = int(
        entry.options.get(CONF_ROOM_TEMP_FORWARDING_INTERVAL, DEFAULT_ROOM_TEMP_FORWARDING_INTERVAL)
    )
    room_temp_forwarding_tolerance = float(
        entry.options.get(CONF_ROOM_TEMP_FORWARDING_TOLERANCE, DEFAULT_ROOM_TEMP_FORWARDING_TOLERANCE)
    )
    humidity_forwarding_enabled = bool(entry.options.get(CONF_HUMIDITY_FORWARDING, DEFAULT_HUMIDITY_FORWARDING))
    humidity_forwarding_entity = str(entry.options.get(CONF_HUMIDITY_FORWARDING_ENTITY, "")).strip()
    humidity_forwarding_interval = int(
        entry.options.get(CONF_HUMIDITY_FORWARDING_INTERVAL, DEFAULT_HUMIDITY_FORWARDING_INTERVAL)
    )
    humidity_forwarding_tolerance = float(
        entry.options.get(CONF_HUMIDITY_FORWARDING_TOLERANCE, DEFAULT_HUMIDITY_FORWARDING_TOLERANCE)
    )
    storage_temp_forwarding_enabled = bool(
        entry.options.get(CONF_STORAGE_TEMP_FORWARDING, DEFAULT_STORAGE_TEMP_FORWARDING)
    )
    storage_temp_forwarding_entities = entry.options.get(CONF_STORAGE_TEMP_FORWARDING_ENTITIES, {})
    storage_temp_forwarding_interval = int(
        entry.options.get(CONF_STORAGE_TEMP_FORWARDING_INTERVAL, DEFAULT_STORAGE_TEMP_FORWARDING_INTERVAL)
    )
    storage_temp_forwarding_tolerance = float(
        entry.options.get(CONF_STORAGE_TEMP_FORWARDING_TOLERANCE, DEFAULT_STORAGE_TEMP_FORWARDING_TOLERANCE)
    )
    knx_bridge_enabled = bool(entry.options.get(CONF_KNX_BRIDGE, DEFAULT_KNX_BRIDGE))
    knx_base_address = str(entry.options.get(CONF_KNX_BASE_ADDRESS, DEFAULT_KNX_BASE_ADDRESS)).strip()
    knx_send = bool(entry.options.get(CONF_KNX_SEND, DEFAULT_KNX_SEND))
    knx_receive = bool(entry.options.get(CONF_KNX_RECEIVE, DEFAULT_KNX_RECEIVE))
    knx_respond_to_read = bool(entry.options.get(CONF_KNX_RESPOND_TO_READ, DEFAULT_KNX_RESPOND_TO_READ))
    knx_groups = tuple(str(group) for group in (entry.options.get(CONF_KNX_GROUPS) or OBJECT_GROUPS))
    knx_overrides = entry.options.get(CONF_KNX_OVERRIDES) or {}
    knx_resend_interval = int(entry.options.get(CONF_KNX_RESEND_INTERVAL, DEFAULT_KNX_RESEND_INTERVAL))
    knx_tolerance = float(entry.options.get(CONF_KNX_TOLERANCE, DEFAULT_KNX_TOLERANCE))
    modbus_timeout = float(entry.options.get(CONF_MODBUS_TIMEOUT, DEFAULT_MODBUS_TIMEOUT))
    modbus_max_retries = int(entry.options.get(CONF_MODBUS_MAX_RETRIES, DEFAULT_MODBUS_MAX_RETRIES))
    modbus_message_spacing = float(entry.options.get(CONF_MODBUS_MESSAGE_SPACING, DEFAULT_MODBUS_MESSAGE_SPACING))
    modbus_connect_delay = float(entry.options.get(CONF_MODBUS_CONNECT_DELAY, DEFAULT_MODBUS_CONNECT_DELAY))
    polling_jitter = int(entry.options.get(CONF_POLLING_JITTER, DEFAULT_POLLING_JITTER))
    write_cooldown = float(entry.options.get(CONF_WRITE_COOLDOWN, DEFAULT_WRITE_COOLDOWN))
    eeprom_write_interval = float(entry.options.get(CONF_EEPROM_WRITE_INTERVAL, DEFAULT_EEPROM_WRITE_INTERVAL))

    if web_pin_configured(web_pin):
        ir.async_delete_issue(hass, DOMAIN, scoped_issue_id(entry.entry_id, "web_pin_missing"))
    elif web_enabled:
        ir.async_create_issue(
            hass,
            DOMAIN,
            scoped_issue_id(entry.entry_id, "web_pin_missing"),
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="web_pin_missing",
            data={"entry_id": entry.entry_id},
            translation_placeholders={"name": entry.title},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, scoped_issue_id(entry.entry_id, "web_pin_missing"))

    web_only = bool(entry.data.get(CONF_WEB_ONLY, DEFAULT_WEB_ONLY))

    if web_only:
        return await _async_setup_web_only_entry(
            hass,
            entry,
            host,
            port,
            slave_id,
            scan_interval,
            web_pin,
            web_host,
            web_scan_interval,
            device_hierarchy_enabled,
        )

    # Use the library via the adapter (migration Option B)
    client = get_idm_client(
        host=host,
        port=port,
        slave_id=slave_id,
        timeout=modbus_timeout,
        max_retries=modbus_max_retries,
        message_spacing=modbus_message_spacing,
        connect_delay=modbus_connect_delay,
    )
    # Apply the per-entry EEPROM write interval (power-user override; default
    # stays 60s to protect the EEPROM's limited write cycles).
    try:
        client.eeprom_write_interval = eeprom_write_interval
    except (AttributeError, ValueError) as err:  # older API without the setter
        _LOGGER.debug("Could not apply eeprom_write_interval=%.1f: %s", eeprom_write_interval, err)

    try:
        await client.connect()
    except Exception as err:
        issue_id = classify_communication_error(err)
        friendly_error = friendly_communication_error(issue_id, host, port, err)
        try:
            await client.disconnect()
        except Exception:
            _LOGGER.warning("Failed to clean up client for %s:%d", host, port, exc_info=True)
        _LOGGER.error("%s", friendly_error)
        _LOGGER.debug("Technical IDM Modbus setup error", exc_info=True)
        raise ConfigEntryNotReady(friendly_error) from err

    try:
        model_name, firmware_version, detected_model_info = await _detect_model_info(client)
        _LOGGER.info(
            "IDM Modbus model detection result: model=%s firmware=%s model_info=%s",
            model_name,
            firmware_version or "unknown",
            "available" if detected_model_info is not None else "unavailable",
        )

        client_model_info = getattr(client, "model_info", None)
        detection = DetectionResult(
            model_name=model_name,
            firmware_version=firmware_version,
            model_info=detected_model_info,
            client_model_info=client_model_info if isinstance(client_model_info, IdmModelInfo) else None,
        )
        stored_detection = StoredDetection.from_entry_data(entry.data)
        override_model_name = resolved_model_override(entry.data)
        plant = plant_shape(circuits, zone_count, enable_cascade)

        # The web read is the only I/O in the middle of the decision, so the
        # plan for it is computed first and its answer handed back below.
        web_plan = plan_web_read(detection, stored_detection, override_model_name)
        web_supplement = None
        if web_enabled and web_pin_configured(web_pin):
            try:
                web_supplement = await async_read_web_supplement(
                    web_host,
                    web_pin,
                    model_hint=web_plan.model_hint,
                    preferred_variant=web_plan.preferred_variant,
                    allow_variant_fallback=web_plan.allow_variant_fallback,
                    hass=hass,
                    # Setup must not wait on the optional supplement; the poll
                    # loop finishes detection later.
                    read_timeout=WEB_SETUP_READ_TIMEOUT,
                )
            except IdmWebAuthenticationFailed:
                _LOGGER.warning(
                    "IDM Navigator web PIN was rejected by %s during setup. "
                    "Modbus setup continues; update or clear the PIN in reconfigure",
                    web_host,
                )
            except Exception as err:
                issue_id = classify_web_error(err)
                _LOGGER.warning(
                    "%s; Modbus setup continues",
                    friendly_web_error(issue_id, web_host),
                )
                _LOGGER.debug("Technical initial Navigator web error", exc_info=True)

        resolution = resolve_model(
            detection,
            stored_detection,
            web_supplement,
            override_model_name,
            plant,
        )
        for level, message, args in resolution.log_lines:
            _LOGGER.log(level, message, *args)
        model_name = resolution.model_name
        firmware_version = resolution.firmware_version
        detected_model_info = resolution.model_info
        runtime_web_variant = web_plan.preferred_variant

        if resolution.data_updates or resolution.data_removals:
            updated_data = {**entry.data, **resolution.data_updates}
            for key in resolution.data_removals:
                updated_data.pop(key, None)
            hass.config_entries.async_update_entry(entry, data=updated_data)

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
            web_host=web_host,
            web_supplement=web_supplement,
            web_variant=runtime_web_variant,
            device_hierarchy_enabled=device_hierarchy_enabled,
            polling_jitter_percent=polling_jitter,
            write_cooldown_seconds=write_cooldown,
        )
        coordinator.setup_registers(
            circuits,
            zone_count,
            zone_rooms,
            enable_cascade,
            model_info=detected_model_info,
            descriptions=sensor_descs + binary_descs + number_descs + select_descs + switch_descs,
        )

        operation_analysis = OperationAnalysis(
            hass,
            entry.entry_id,
            coordinator.get_register,
            short_cycle_minutes=short_cycle_minutes,
            expected_poll_interval=float(scan_interval),
        )
        await operation_analysis.async_load()
        coordinator.attach_operation_analysis(operation_analysis)

        entry.runtime_data = IdmHeatpumpData(
            coordinator=coordinator,
            client=client,
            operation_analysis=operation_analysis,
            loaded_platforms=tuple(PLATFORMS),
        )

        await coordinator.async_config_entry_first_refresh()
        precreate_main_device(hass, coordinator)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        cleanup_stale_hierarchy_devices(hass, coordinator)
        cleanup_deconfigured_heating_circuit_entities(hass, coordinator)
        cleanup_stale_web_sensor_entities(hass, coordinator)

        # Activate entity-aware polling after platforms have created registry
        # entries. Idempotent — subsequent calls from operation_entities.py are no-ops.
        ensure_entity_aware_polling(coordinator)

        if web_enabled and web_pin_configured(web_pin):
            entry.runtime_data.web_task = _create_entry_background_task(
                hass,
                entry,
                _web_poll_loop(coordinator, web_scan_interval),
                name=f"{DOMAIN}_web_poll_{entry.entry_id}",
            )

        if room_temp_forwarding_enabled and isinstance(room_temp_forwarding_entities, dict):
            forwarding_entities = {
                str(circuit): str(entity_id)
                for circuit, entity_id in room_temp_forwarding_entities.items()
                if str(entity_id).strip()
            }
            if forwarding_entities:
                forwarder = RoomTempForwarder(
                    hass,
                    coordinator,
                    RoomTempForwardingConfig(
                        entities=forwarding_entities,
                        interval=room_temp_forwarding_interval,
                        tolerance=room_temp_forwarding_tolerance,
                    ),
                )
                entry.runtime_data.room_temp_forwarding_task = _create_entry_background_task(
                    hass,
                    entry,
                    forwarder.async_run(),
                    name=f"{DOMAIN}_room_temp_{entry.entry_id}",
                )

        if humidity_forwarding_enabled and humidity_forwarding_entity:
            humidity_forwarder = HumidityForwarder(
                hass,
                coordinator,
                HumidityForwardingConfig(
                    entity_id=humidity_forwarding_entity,
                    interval=humidity_forwarding_interval,
                    tolerance=humidity_forwarding_tolerance,
                ),
            )
            entry.runtime_data.humidity_forwarding_task = _create_entry_background_task(
                hass,
                entry,
                humidity_forwarder.async_run(),
                name=f"{DOMAIN}_humidity_{entry.entry_id}",
            )

        if storage_temp_forwarding_enabled and isinstance(storage_temp_forwarding_entities, dict):
            storage_forwarding_entities = {
                str(key): str(entity_id)
                for key, entity_id in storage_temp_forwarding_entities.items()
                if str(entity_id).strip()
            }
            if storage_forwarding_entities:
                storage_forwarder = RoomTempForwarder(
                    hass,
                    coordinator,
                    RoomTempForwardingConfig(
                        entities=storage_forwarding_entities,
                        interval=storage_temp_forwarding_interval,
                        tolerance=storage_temp_forwarding_tolerance,
                    ),
                    register_for_key=register_for_storage_temp_key,
                    key_label="storage key",
                    value_label="storage temperature",
                )
                entry.runtime_data.storage_temp_forwarding_task = _create_entry_background_task(
                    hass,
                    entry,
                    storage_forwarder.async_run(),
                    name=f"{DOMAIN}_storage_temp_{entry.entry_id}",
                )
        if knx_bridge_enabled and (knx_send or knx_receive):
            bridge = KnxBridge(
                hass,
                coordinator,
                KnxBridgeConfig(
                    base_address=knx_base_address,
                    send_enabled=knx_send,
                    receive_enabled=knx_receive,
                    respond_to_read=knx_respond_to_read,
                    groups=knx_groups,
                    overrides=dict(knx_overrides) if isinstance(knx_overrides, Mapping) else {},
                    resend_interval=knx_resend_interval,
                    tolerance=knx_tolerance,
                    write_cooldown=write_cooldown,
                    eeprom_write_interval=eeprom_write_interval,
                ),
                entry_id=entry.entry_id,
            )
            # Store it before starting: async_start registers register demand
            # and event listeners as it goes, so a bridge that fails halfway
            # still has to be reachable for the teardown below to stop it.
            entry.runtime_data.knx_bridge = bridge
            try:
                await bridge.async_start()
            except InvalidGroupAddressError as err:
                entry.runtime_data.knx_bridge = None
                await bridge.async_stop()
                _LOGGER.error(
                    "KNX bridge for %s not started: %s",
                    entry.title,
                    err,
                )

    except Exception:
        # Everything after async_forward_entry_setups can still fail — the KNX
        # bridge raising something other than InvalidGroupAddressError, a
        # malformed option reaching int()/float(). Home Assistant then marks the
        # entry failed, but the platforms stay registered against a coordinator
        # whose client this handler is about to close, leaving the user a wall
        # of unavailable entities and a connection error on every poll. Take the
        # platforms and the background tasks down before re-raising.
        await _async_teardown_partial_setup(hass, entry)
        try:
            await client.disconnect()
        except Exception:
            _LOGGER.warning("Failed to clean up client for %s:%d", host, port, exc_info=True)
        raise

    _register_update_listener(entry)

    return True


async def _async_teardown_partial_setup(hass: HomeAssistant, entry: IdmConfigEntry) -> None:
    """Undo whatever a failed ``async_setup_entry`` had already brought up.

    Best-effort throughout: this runs while an exception is propagating, so a
    secondary failure here must not replace the original one.
    """
    runtime = getattr(entry, "runtime_data", None)
    if runtime is None:
        return

    bridge = getattr(runtime, "knx_bridge", None)
    if bridge is not None:
        try:
            await bridge.async_stop()
        except Exception:
            _LOGGER.debug("Error stopping the KNX bridge while unwinding setup", exc_info=True)

    await _async_cancel_entry_tasks(runtime)

    coordinator = getattr(runtime, "coordinator", None)
    shutdown = getattr(coordinator, "async_shutdown", None)
    if callable(shutdown):
        try:
            await shutdown()
        except TypeError:
            pass
        except Exception:
            _LOGGER.debug("Error shutting the coordinator down while unwinding setup", exc_info=True)

    platforms = getattr(runtime, "loaded_platforms", None)
    if platforms:
        try:
            await hass.config_entries.async_unload_platforms(entry, list(platforms))
        except Exception:
            _LOGGER.warning("Failed to unload platforms while unwinding a failed setup", exc_info=True)


async def _async_cancel_entry_tasks(runtime: Any) -> None:
    """Cancel and await every background task an entry owns."""
    for attribute in (
        "web_task",
        "room_temp_forwarding_task",
        "humidity_forwarding_task",
        "storage_temp_forwarding_task",
    ):
        task = getattr(runtime, attribute, None)
        if isinstance(task, asyncio.Task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def async_unload_entry(hass: HomeAssistant, entry: IdmConfigEntry) -> bool:
    platforms = getattr(entry.runtime_data, "loaded_platforms", None) or tuple(PLATFORMS)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, list(platforms))
    if unload_ok:
        operation_analysis = getattr(entry.runtime_data, "operation_analysis", None)
        if operation_analysis is not None:
            try:
                await operation_analysis.async_save()
            except Exception:
                _LOGGER.warning("Failed to persist IDM operation analysis during unload", exc_info=True)
        coordinator = getattr(entry.runtime_data, "coordinator", None)
        shutdown = getattr(coordinator, "async_shutdown", None)
        if callable(shutdown):
            try:
                await shutdown()
            except TypeError:
                # Non-awaitable mock or sync cleanup callback; not fatal on unload.
                pass
        await _async_cancel_entry_tasks(entry.runtime_data)
        knx_bridge = getattr(entry.runtime_data, "knx_bridge", None)
        if knx_bridge is not None:
            try:
                await knx_bridge.async_stop()
            except Exception:
                _LOGGER.debug("Error stopping the KNX bridge for %s", entry.title, exc_info=True)
        try:
            await entry.runtime_data.client.disconnect()
        except Exception:
            _LOGGER.debug("Error disconnecting client for %s", entry.title, exc_info=True)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: IdmConfigEntry) -> None:
    """Reload the config entry when structural settings change.

    Retroactive web detection only updates detection metadata in ``entry.data``.
    Those keys are excluded from the fingerprint so a successful web poll does
    not unload platforms, cancel DHW boost / room-temp tasks, or reconnect.
    """
    new_fingerprint = _entry_reload_fingerprint(entry)
    runtime = getattr(entry, "runtime_data", None)
    previous = getattr(runtime, "reload_fingerprint", None) if runtime is not None else None
    if previous is not None and previous == new_fingerprint:
        _LOGGER.debug(
            "Skipping IDM config entry reload for %s; only detection metadata changed",
            entry.entry_id,
        )
        return
    await hass.config_entries.async_reload(entry.entry_id)
