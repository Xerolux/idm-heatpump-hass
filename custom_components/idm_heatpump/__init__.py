"""IDM Heatpump integration for Home Assistant."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from typing import Mapping
from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration

from idm_heatpump import (
    FEATURE_CASCADE,
    FEATURE_HEATING_CIRCUITS,
    FEATURE_ISC,
    FEATURE_PV,
    FEATURE_SOLAR,
    FEATURE_ZONE_MODULES,
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    MODEL_NAVIGATOR_PRO,
    MODEL_UNKNOWN,
    IdmModbusClient,
    IdmModelInfo,
)

from .const import (
    CONF_DETECTED_NAVIGATOR_VERSION,
    CONF_DETECTED_SOFTWARE_VERSION,
    CONF_DETECTED_WEB_VARIANT,
    CONF_DEVICE_HIERARCHY,
    CONF_ENABLE_CASCADE,
    CONF_HEATING_CIRCUITS,
    CONF_HIDE_UNUSED,
    CONF_MODBUS_MAX_RETRIES,
    CONF_MODBUS_TIMEOUT,
    CONF_MODEL_OVERRIDE,
    CONF_ROOM_TEMP_FORWARDING,
    CONF_SHORT_CYCLE_MINUTES,
    CONF_ROOM_TEMP_FORWARDING_ENTITIES,
    CONF_ROOM_TEMP_FORWARDING_INTERVAL,
    CONF_ROOM_TEMP_FORWARDING_TOLERANCE,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    CONF_WEB_ENABLED,
    CONF_WEB_HOST,
    CONF_WEB_ONLY,
    CONF_WEB_PIN,
    CONF_WEB_SCAN_INTERVAL,
    CONF_ZONE_COUNT,
    CONF_ZONE_ROOMS,
    DEFAULT_DEVICE_HIERARCHY,
    DEFAULT_ENABLE_CASCADE,
    DEFAULT_HIDE_UNUSED,
    DEFAULT_MODBUS_MAX_RETRIES,
    DEFAULT_MODBUS_TIMEOUT,
    DEFAULT_ROOM_TEMP_FORWARDING,
    DEFAULT_SHORT_CYCLE_MINUTES,
    DEFAULT_ROOM_TEMP_FORWARDING_INTERVAL,
    DEFAULT_ROOM_TEMP_FORWARDING_TOLERANCE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DEFAULT_WEB_ENABLED,
    DEFAULT_WEB_ONLY,
    DEFAULT_WEB_SCAN_INTERVAL,
    DOMAIN,
    MODEL,
    MODEL_OVERRIDE_AUTO,
    MODEL_OVERRIDE_NAVIGATOR_10,
    MODEL_OVERRIDE_NAVIGATOR_20,
    MODEL_OVERRIDE_NAVIGATOR_PRO,
    NAME,
)
from .coordinator import IdmCoordinator, navigator_family
from .device_hierarchy import cleanup_stale_hierarchy_devices
from .error_messages import (
    classify_communication_error,
    classify_web_error,
    friendly_communication_error,
    friendly_web_error,
)
from .library_adapter import get_idm_client
from .registers import (
    get_all_binary_sensor_descriptions,
    get_all_number_descriptions,
    get_all_select_descriptions,
    get_all_sensor_descriptions,
    get_all_switch_descriptions,
    normalize_zone_rooms,
)
from .operation_analysis import OperationAnalysis
from .polling_plan import ensure_entity_aware_polling
from .room_temp_forwarding import RoomTempForwarder, RoomTempForwardingConfig
from .web_data import (
    IdmWebAuthenticationFailed,
    _firmware_indicates_nav10,
    async_read_web_supplement,
    merge_model_info,
    web_pin_configured,
)
from .versions import async_runtime_versions

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
        return create_bg(entry, hass, coro, name)
    create_task = getattr(hass, "async_create_task", None)
    if callable(create_task):
        return create_task(coro)
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

    firmware_version is read via getattr defensively: idm-heatpump-api 0.3.4
    does not expose it on IdmModelInfo yet, but a future release is expected
    to add it. This picks it up automatically once available, without a
    version bump here or raising on the current release.
    """
    try:
        try:
            model_info = await client.detect_model(read_firmware=False)
        except TypeError:
            model_info = await client.detect_model()
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


def _model_info_from_detected_name(
    model_name: str,
    circuits: list[str],
    zone_count: int,
    enable_cascade: bool,
) -> IdmModelInfo:
    """Build fallback model info from trusted web/config metadata.

    When the name is generic ("Navigator 2.0 / 10"), inconclusive, or unknown,
    default to Navigator 2.0. That is the safer baseline: Navigator-10-only
    registers such as 4108 / 4001 cause "Illegal Data Address" errors on older
    controllers, whereas a Navigator 10 controller simply won't expose a few
    Navigator-2.0-specific registers.
    """
    normalized = model_name.casefold()
    has_navigator_20 = "navigator 2" in normalized
    has_navigator_10 = "navigator 10" in normalized
    has_navigator_pro = "navigator pro" in normalized

    if has_navigator_10 and not has_navigator_20:
        detected_model = MODEL_NAVIGATOR_10
    elif has_navigator_pro and not has_navigator_20 and not has_navigator_10:
        detected_model = MODEL_NAVIGATOR_PRO
    else:
        # Generic "Navigator 2.0 / 10", both generations mentioned, or
        # completely unknown: prefer Navigator 2.0 to avoid first-setup crashes.
        detected_model = MODEL_NAVIGATOR_20

    features: set[str] = set()
    if circuits:
        features.add(FEATURE_HEATING_CIRCUITS)
    if zone_count > 0:
        features.add(FEATURE_ZONE_MODULES)
    features.add(FEATURE_SOLAR)
    features.add(FEATURE_ISC)
    features.add(FEATURE_PV)
    if enable_cascade:
        features.add(FEATURE_CASCADE)

    return IdmModelInfo(
        model_name=detected_model,
        active_heating_circuits=[circuit.upper() for circuit in circuits],
        zone_modules=zone_count,
        has_solar=True,
        has_isc=True,
        has_pv=True,
        has_cascade=enable_cascade,
        features=features,
    )


def _model_name_for_override(override_value: str) -> str | None:
    """Map a config-flow model override value to a library model name.

    Returns ``None`` for ``auto``/unknown so callers keep using automatic
    detection. Returning the canonical library string lets the rest of setup
    (register map, family checks, device info) work unchanged.
    """
    mapping = {
        MODEL_OVERRIDE_NAVIGATOR_10: MODEL_NAVIGATOR_10,
        MODEL_OVERRIDE_NAVIGATOR_20: MODEL_NAVIGATOR_20,
        MODEL_OVERRIDE_NAVIGATOR_PRO: MODEL_NAVIGATOR_PRO,
    }
    return mapping.get(override_value)


def _resolved_model_override(entry_data: Mapping[str, Any]) -> str | None:
    """Return the configured override model name, or ``None`` for automatic.

    Empty/missing/``auto`` values resolve to ``None`` so the behavior is
    identical to the pre-override detection path.
    """
    raw = entry_data.get(CONF_MODEL_OVERRIDE)
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if raw == MODEL_OVERRIDE_AUTO or not raw:
        return None
    return _model_name_for_override(raw)


async def _web_poll_loop(coordinator: IdmCoordinator, interval: int) -> None:
    """Poll optional web supplement data independently from Modbus."""
    await asyncio.sleep(0.3)
    while True:
        try:
            await coordinator.async_refresh_web_supplement()
        except Exception:
            _LOGGER.exception("Unhandled error in IDM web poll loop; retrying next cycle")
        await asyncio.sleep(interval)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the IDM Heatpump component.

    Services are registered here (action-setup rule) so they are available
    as soon as the domain loads, independently of config entries.
    """
    from .log_filter import install_pymodbus_log_filter
    from .services import async_setup_services

    # pymodbus logs routine connection drops at ERROR level and appends up
    # to 20 buffered raw frame dumps to each record. The coordinator already
    # converts these failures into a single UpdateFailed warning, so the
    # pymodbus records are redundant and would otherwise flood the HA log.
    install_pymodbus_log_filter()

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
    ir.async_delete_issue(hass, DOMAIN, "web_pin_missing")

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
    override_model_name = _resolved_model_override(entry.data)
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
    coordinator._registers = []
    coordinator._alias_map = {}
    coordinator.data = {}

    entry.runtime_data = IdmHeatpumpData(
        coordinator=coordinator,
        client=client,
        loaded_platforms=(Platform.SENSOR,),
    )

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    cleanup_stale_hierarchy_devices(hass, coordinator)

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
        "Setting up %s v%s (idm-heatpump-api v%s, pymodbus v%s)",
        NAME,
        versions.integration,
        versions.api,
        versions.pymodbus,
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
    modbus_timeout = float(entry.options.get(CONF_MODBUS_TIMEOUT, DEFAULT_MODBUS_TIMEOUT))
    modbus_max_retries = int(entry.options.get(CONF_MODBUS_MAX_RETRIES, DEFAULT_MODBUS_MAX_RETRIES))

    if web_pin_configured(web_pin):
        ir.async_delete_issue(hass, DOMAIN, "web_pin_missing")
    elif web_enabled:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "web_pin_missing",
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="web_pin_missing",
            data={"entry_id": entry.entry_id},
            translation_placeholders={"name": entry.title},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, "web_pin_missing")

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
    )

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
        modbus_model_name = model_name
        _LOGGER.info(
            "IDM Modbus model detection result: model=%s firmware=%s model_info=%s",
            modbus_model_name,
            firmware_version or "unknown",
            "available" if detected_model_info is not None else "unavailable",
        )

        # Optional user-configured Navigator model override. An explicit
        # override wins over both the fresh Modbus detection and any stored/
        # web-supplement values, because the user explicitly chose it. It only
        # affects register selection (which registers are polled); unique IDs,
        # entity IDs and write paths stay unchanged. ``auto`` keeps detection.
        override_model_name = _resolved_model_override(entry.data)
        override_active = override_model_name is not None
        if override_active:
            assert override_model_name is not None  # for mypy
            _LOGGER.warning(
                "IDM Navigator model override active: using %s (automatic detection was %s); "
                "change the override back to 'Automatic' in the integration settings if it was set "
                "by mistake",
                override_model_name,
                modbus_model_name,
            )
            model_name = override_model_name
            modbus_model_name = override_model_name

        stale_detected_data: dict[str, Any] = {}
        stored_model_conflict = False
        detected_model_name = entry.data.get(CONF_DETECTED_NAVIGATOR_VERSION)
        # When a user override is active, the stored detected value is not a
        # detection result that could become "stale" — it is whatever the user
        # last saw. Skip the stored-vs-fresh conflict reconciliation entirely
        # so we never silently rewrite a user override.
        if (
            not override_active
            and isinstance(detected_model_name, str)
            and detected_model_name.strip()
            and (
                detected_model_info is None
                or navigator_family(detected_model_name) == navigator_family(modbus_model_name)
            )
        ):
            model_name = detected_model_name.strip()
            _LOGGER.info(
                "Using stored IDM Navigator model %s because it matches fresh Modbus detection",
                model_name,
            )
        elif not override_active and isinstance(detected_model_name, str) and detected_model_name.strip():
            stale_detected_data[CONF_DETECTED_NAVIGATOR_VERSION] = detected_model_name
            stored_model_conflict = True
            _LOGGER.info(
                "Stored IDM Navigator model %s conflicts with fresh Modbus detection %s; correcting stored data",
                detected_model_name,
                modbus_model_name,
            )
        runtime_web_variant = None if stored_model_conflict else stored_web_variant
        detected_firmware_version = entry.data.get(CONF_DETECTED_SOFTWARE_VERSION)
        if (
            isinstance(detected_firmware_version, str)
            and detected_firmware_version.strip()
            and not stored_model_conflict
        ):
            firmware_version = detected_firmware_version.strip()

        web_supplement = None
        if web_enabled and web_pin_configured(web_pin):
            try:
                web_supplement = await async_read_web_supplement(
                    web_host,
                    web_pin,
                    model_hint=modbus_model_name,
                    preferred_variant=runtime_web_variant,
                    allow_variant_fallback=runtime_web_variant is None,
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
            if (
                not override_active
                and web_supplement is not None
                and detected_model_info is not None
                and web_supplement.model_name
                and navigator_family(web_supplement.model_name) != navigator_family(modbus_model_name)
            ):
                # The web supplement disagrees with Modbus detection.
                # The web variant that succeeded is definitive: nav10 clients
                # can only connect to Navigator 10 controllers. When the
                # firmware string additionally carries a NAV10 prefix, the
                # web evidence is stronger than a potentially failed Modbus
                # probe (register 4108 is rejected by some Nav10 firmwares).
                if _firmware_indicates_nav10(web_supplement.software_version):
                    _LOGGER.info(
                        "Correcting Modbus-detected model %s to %s based on web firmware string %s",
                        modbus_model_name,
                        web_supplement.model_name,
                        web_supplement.software_version,
                    )
                    model_name = web_supplement.model_name
                    firmware_version = web_supplement.software_version or firmware_version
                    # Build corrected model_info so register map includes
                    # Navigator-10-only blocks. The library's client.model_info
                    # still holds the stale Nav2.0 detection result.
                    detected_model_info = _model_info_from_detected_name(
                        model_name,
                        circuits,
                        zone_count,
                        enable_cascade,
                    )
                    # Persist the corrected model so it survives reloads.
                    # Detection-only keys do not trigger a config-entry reload.
                    _web_correction_updates: dict[str, Any] = {
                        CONF_DETECTED_NAVIGATOR_VERSION: model_name,
                    }
                    if firmware_version:
                        _web_correction_updates[CONF_DETECTED_SOFTWARE_VERSION] = firmware_version
                    if web_supplement.web_variant:
                        _web_correction_updates[CONF_DETECTED_WEB_VARIANT] = web_supplement.web_variant
                    hass.config_entries.async_update_entry(entry, data={**entry.data, **_web_correction_updates})
                else:
                    stale_detected_data[CONF_DETECTED_NAVIGATOR_VERSION] = web_supplement.model_name
                    _LOGGER.warning(
                        "Ignoring conflicting stored/web Navigator model %s because Modbus detected %s",
                        web_supplement.model_name,
                        modbus_model_name,
                    )
            elif override_active:
                # A user override is authoritative for the model. The web
                # supplement may still contribute the software version, but it
                # must not change the model name.
                _, firmware_version = merge_model_info(
                    model_name,
                    firmware_version,
                    web_supplement,
                )
            else:
                model_name, firmware_version = merge_model_info(
                    model_name,
                    firmware_version,
                    web_supplement,
                )

        if stale_detected_data and detected_model_info is not None:
            data_updates: dict[str, Any] = {}
            if CONF_DETECTED_NAVIGATOR_VERSION in stale_detected_data:
                data_updates[CONF_DETECTED_NAVIGATOR_VERSION] = modbus_model_name
            if web_supplement is not None and web_supplement.web_variant:
                data_updates[CONF_DETECTED_WEB_VARIANT] = web_supplement.web_variant
            if firmware_version:
                data_updates[CONF_DETECTED_SOFTWARE_VERSION] = firmware_version
            updated_data = {**entry.data, **data_updates}
            if stored_model_conflict and CONF_DETECTED_SOFTWARE_VERSION not in data_updates:
                updated_data.pop(CONF_DETECTED_SOFTWARE_VERSION, None)
                _LOGGER.info(
                    "Removed stale stored IDM software version because the stored Navigator model was corrected"
                )
            if stored_model_conflict and CONF_DETECTED_WEB_VARIANT not in data_updates:
                updated_data.pop(CONF_DETECTED_WEB_VARIANT, None)
                _LOGGER.info("Removed stale stored IDM web variant because the stored Navigator model was corrected")
            _LOGGER.info("Persisting corrected IDM detection data: %s", sorted(data_updates))
            hass.config_entries.async_update_entry(entry, data=updated_data)

        client_model_info = getattr(client, "model_info", None)
        if (
            not override_active
            and isinstance(client_model_info, IdmModelInfo)
            and isinstance(detected_model_info, IdmModelInfo)
            and navigator_family(client_model_info.model_name) == navigator_family(detected_model_info.model_name)
        ):
            # When the library's detection result and the resolved model_info
            # agree on the Navigator family, prefer the library's richer info
            # (features, capabilities). Skip when families disagree (e.g. web
            # evidence corrected a weak Modbus "Navigator 2.0" detection).
            detected_model_info = client_model_info
        elif not override_active and isinstance(client_model_info, IdmModelInfo) and detected_model_info is None:
            detected_model_info = client_model_info
        if override_active or detected_model_info is None:
            # With an active override, always (re)build model info from the
            # authoritative override name so the register map reflects the
            # user's choice, not whatever the Modbus probe happened to detect.
            detected_model_info = _model_info_from_detected_name(
                model_name,
                circuits,
                zone_count,
                enable_cascade,
            )

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
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        cleanup_stale_hierarchy_devices(hass, coordinator)

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
    except Exception:
        try:
            await client.disconnect()
        except Exception:
            _LOGGER.warning("Failed to clean up client for %s:%d", host, port, exc_info=True)
        raise

    _register_update_listener(entry)

    return True


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
        web_task = getattr(entry.runtime_data, "web_task", None)
        if isinstance(web_task, asyncio.Task):
            web_task.cancel()
            try:
                await web_task
            except asyncio.CancelledError:
                pass
        room_temp_forwarding_task = getattr(entry.runtime_data, "room_temp_forwarding_task", None)
        if isinstance(room_temp_forwarding_task, asyncio.Task):
            room_temp_forwarding_task.cancel()
            try:
                await room_temp_forwarding_task
            except asyncio.CancelledError:
                pass
        try:
            await entry.runtime_data.client.disconnect()
        except Exception:
            _LOGGER.debug("Error disconnecting client for %s", entry.title, exc_info=True)
        from .services import async_unload_services

        await async_unload_services(hass)
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
