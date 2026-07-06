"""Data update coordinator for IDM Navigator heat pump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import asyncio
import logging
import math
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from idm_heatpump import IdmModbusClient, IdmModelInfo, RegisterDef
from pymodbus.exceptions import ConnectionException, ModbusException

from .const import (
    CONF_DETECTED_NAVIGATOR_VERSION,
    CONF_DETECTED_SOFTWARE_VERSION,
    DOMAIN,
    MODEL,
    NEGATIVE_ONE_VALID_REGISTERS,
    UNUSED_VALUE,
)
from .registers import collect_all_registers, collect_alias_map
from .web_data import IdmWebSupplement, async_read_web_supplement

_LOGGER = logging.getLogger(__name__)
_ILLEGAL_ADDRESS_MARKERS = ("exception_code=2", "illegal data address")
_CONNECTIVITY_REPAIR_ISSUES = (
    "cannot_connect",
    "wrong_slave_id",
    "incompatible_firmware",
)
_WEB_SUPPLEMENT_FAILED_ISSUE = "web_supplement_failed"
_WEB_CORE_VALUE_KEYS = ("navigator_version", "software_version", "heatpump_model")
_ZONE_ROOM_MODE_PREFIX = "zm"
_ZONE_ROOM_MODE_MARKER = "_room"
_ZONE_ROOM_MODE_SUFFIX = "_mode"


def _is_illegal_address_error(err: ModbusException) -> bool:
    """Return whether a Modbus exception reports an unsupported address."""
    message = str(err).casefold()
    return any(marker in message for marker in _ILLEGAL_ADDRESS_MARKERS)


def _is_zone_room_mode_register(reg: RegisterDef) -> bool:
    """Return whether a register stores a zone-room operating mode.

    Navigator 2.0 systems have been observed to return invalid decoded values
    for these UCHAR registers when they are read as part of larger batches,
    while direct single-register reads remain stable.
    """
    name = reg.name
    return (
        name.startswith(_ZONE_ROOM_MODE_PREFIX)
        and _ZONE_ROOM_MODE_MARKER in name
        and name.endswith(_ZONE_ROOM_MODE_SUFFIX)
    )


def _repair_issue_for_error(err: Exception) -> str:
    """Map communication errors to actionable repair issue translations."""
    message = str(err).casefold()
    if isinstance(err, ConnectionException):
        return "cannot_connect"
    if any(marker in message for marker in ("slave", "unit id", "device id", "no response", "no reply")):
        return "wrong_slave_id"
    if any(
        marker in message for marker in ("exception_code=1", "illegal function", "unsupported function", "firmware")
    ):
        return "incompatible_firmware"
    return "cannot_connect"


def navigator_family(model_name: str | None) -> str | None:
    """Return a coarse Navigator generation identifier for conflict checks."""
    if not isinstance(model_name, str):
        return None
    normalized = model_name.casefold()
    if normalized == MODEL.casefold():
        return None
    has_navigator_20 = "navigator 2" in normalized
    has_navigator_10 = "navigator 10" in normalized
    if has_navigator_20 and has_navigator_10:
        return None
    if has_navigator_20:
        return "navigator_20"
    if has_navigator_10:
        return "navigator_10"
    if "navigator pro" in normalized:
        return "navigator_pro"
    return None


def _web_variant_from_family(family: str | None) -> str | None:
    """Return the local web access variant for a Navigator family."""
    if family == "navigator_20":
        return "nav20"
    if family in ("navigator_10", "navigator_pro"):
        return "nav10"
    return None


def _web_variant_from_supplement(supplement: IdmWebSupplement) -> str | None:
    """Return the best web access variant detected from a web supplement."""
    family = navigator_family(supplement.navigator_version) or navigator_family(supplement.heatpump_model)
    return _web_variant_from_family(family)


class IdmCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage data fetching from IDM heat pump."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: IdmModbusClient,
        scan_interval: timedelta,
        sensor_descriptions: list[dict[str, Any]],
        binary_sensor_descriptions: list[dict[str, Any]],
        number_descriptions: list[dict[str, Any]],
        select_descriptions: list[dict[str, Any]],
        switch_descriptions: list[dict[str, Any]],
        hide_unused: bool = True,
        model_name: str = MODEL,
        firmware_version: str | None = None,
        model_info: IdmModelInfo | None = None,
        web_pin: str | None = None,
        web_host: str | None = None,
        web_supplement: IdmWebSupplement | None = None,
    ) -> None:
        self._client = client
        self._sensor_descs = sensor_descriptions
        self._binary_descs = binary_sensor_descriptions
        self._number_descs = number_descriptions
        self._select_descs = select_descriptions
        self._switch_descs = switch_descriptions
        self._registers: list[RegisterDef] = []
        self._hide_unused = hide_unused
        self._model_name = model_name
        self._firmware_version = firmware_version
        self._model_info = model_info
        self._web_pin = web_pin
        self._web_host = web_host or client.host
        self._web_supplement = web_supplement
        self._web_variant: str | None = None
        if web_supplement is not None:
            self._web_variant = _web_variant_from_supplement(web_supplement)
        self._last_web_error: str | None = None
        self._unused_registers: set[str] = set()
        self._unsupported_registers: set[str] = set()
        self._alias_map: dict[int, list[str]] = {}
        self._delayed_refresh_task: asyncio.Task[None] | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="IDM Heatpump",
            update_interval=scan_interval,
        )

    def setup_registers(
        self,
        circuits: list[str],
        zone_count: int,
        zone_rooms: dict[int, int],
        enable_cascade: bool = False,
        model_info: IdmModelInfo | None = None,
    ) -> None:
        args = (circuits, zone_count, zone_rooms, enable_cascade)
        if model_info is None:
            self._registers = collect_all_registers(*args)
            self._alias_map = collect_alias_map(*args)
        else:
            self._registers = collect_all_registers(*args, model_info=model_info)
            self._alias_map = collect_alias_map(*args, model_info=model_info)

    @property
    def sensor_descriptions(self) -> list[dict[str, Any]]:
        return self._sensor_descs

    @property
    def binary_sensor_descriptions(self) -> list[dict[str, Any]]:
        return self._binary_descs

    @property
    def number_descriptions(self) -> list[dict[str, Any]]:
        return self._number_descs

    @property
    def select_descriptions(self) -> list[dict[str, Any]]:
        return self._select_descs

    @property
    def switch_descriptions(self) -> list[dict[str, Any]]:
        return self._switch_descs

    @property
    def client(self) -> IdmModbusClient:
        return self._client

    @property
    def hide_unused(self) -> bool:
        return self._hide_unused

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def firmware_version(self) -> str | None:
        return self._firmware_version

    @property
    def model_info(self) -> IdmModelInfo | None:
        return self._model_info

    @property
    def web_supplement(self) -> IdmWebSupplement | None:
        return self._web_supplement

    @property
    def myidm_id(self) -> str | None:
        """Return the latest known compact myIDM ID."""
        if self._web_supplement is None:
            return None
        return self._web_supplement.myidm_id

    @property
    def web_enabled(self) -> bool:
        return bool(self._web_pin)

    @property
    def web_host(self) -> str:
        return self._web_host

    @property
    def web_variant(self) -> str | None:
        """Return the cached web client variant ('nav10' or 'nav20')."""
        return self._web_variant

    @property
    def last_web_error(self) -> str | None:
        return self._last_web_error

    @property
    def web_value_keys(self) -> tuple[str, ...]:
        """Return currently available optional web value keys."""
        if self._web_supplement is None:
            return ()
        return tuple(sorted(self._web_supplement.sensor_values))

    @property
    def missing_web_core_values(self) -> tuple[str, ...]:
        """Return core web metadata keys missing from the latest successful snapshot."""
        if self._web_supplement is None:
            return ()
        values = self._web_supplement.sensor_values
        return tuple(key for key in _WEB_CORE_VALUE_KEYS if key not in values)

    @property
    def unused_registers(self) -> set[str]:
        return self._unused_registers

    @property
    def unsupported_registers(self) -> set[str]:
        """Registers rejected by the device with Modbus exception code 2."""
        return self._unsupported_registers

    @property
    def registers_count(self) -> int:
        return len(self._registers)

    def is_register_unused(self, register_name: str, value: Any) -> bool:
        """Check if a register value indicates an unused/invalid register."""
        if not self._hide_unused:
            return False
        if value is None:
            return True
        register = next((reg for reg in self._registers if reg.name == register_name), None)
        enum_options = getattr(register, "enum_options", None)
        if isinstance(enum_options, dict) and value in enum_options:
            return False
        if isinstance(value, (int, float)):
            # Pumpenstatus: -1 bedeutet "Aus" — nur den Unused-Check überspringen,
            # alle übrigen Sentinel-Prüfungen bleiben aktiv.
            if register_name not in NEGATIVE_ONE_VALID_REGISTERS and abs(value - UNUSED_VALUE) < 0.01:
                return True
            if value == 65535 or value == 255:
                return True
            if value == -32768:
                return True
            if isinstance(value, float) and (math.isnan(value) or abs(value) == float("inf")):
                return True
        return False

    async def _async_read_registers_resilient(self, registers: list[RegisterDef]) -> dict[str, Any]:
        """Read registers while isolating addresses unsupported by this device.

        Some Navigator firmware variants reject optional register blocks with
        Modbus exception code 2. Bisecting only on that specific response keeps
        all supported entities available without hiding real connection errors.
        """
        if not registers:
            return {}

        readable = [reg for reg in registers if reg.name not in self._unsupported_registers]
        if not readable:
            return {}

        try:
            return await self._client.read_batch(readable)
        except ConnectionException:
            raise
        except ModbusException as err:
            if not _is_illegal_address_error(err):
                raise
            if len(readable) == 1:
                reg = readable[0]
                self._unsupported_registers.add(reg.name)
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "register_not_supported",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="register_not_supported",
                    translation_placeholders={"register": reg.name, "address": str(reg.address)},
                )
                _LOGGER.warning(
                    "IDM Modbus register %s at address %d is not supported by this heat pump "
                    "(Illegal Data Address); skipping it and continuing with supported registers",
                    reg.name,
                    reg.address,
                )
                return {}

            midpoint = len(readable) // 2
            _LOGGER.debug(
                "IDM Modbus Illegal Data Address while reading %d registers; isolating unsupported register",
                len(readable),
            )
            data = await self._async_read_registers_resilient(readable[:midpoint])
            data.update(await self._async_read_registers_resilient(readable[midpoint:]))
            return data

    async def _async_refresh_zone_room_modes(self, data: dict[str, Any]) -> None:
        """Refresh room mode registers individually to avoid faulty batch values."""
        room_mode_registers = [
            reg
            for reg in self._registers
            if reg.name not in self._unsupported_registers and _is_zone_room_mode_register(reg)
        ]
        for reg in room_mode_registers:
            data[reg.name] = await self._client.read_register(reg)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self._async_read_registers_resilient(self._registers)
        except Exception as err:
            issue_id = _repair_issue_for_error(err)
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=issue_id,
                translation_placeholders={"host": self._client.host},
            )
            _LOGGER.error(
                "IDM Modbus polling failed for %s: %s: %s; created repair issue %s",
                self._client.host,
                err.__class__.__name__,
                err,
                issue_id,
            )
            raise UpdateFailed(f"Error communicating with heat pump: {err}") from err

        for issue_id in _CONNECTIVITY_REPAIR_ISSUES:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

        if not data:
            raise UpdateFailed("No data received from heat pump")

        await self._async_refresh_zone_room_modes(data)

        # Apply aliases: when multiple register names share an address,
        # ensure all names appear in the data dict.
        if self._alias_map:
            addr_to_name: dict[int, str] = {reg.address: reg.name for reg in self._registers}
            for addr, names in self._alias_map.items():
                primary = addr_to_name.get(addr)
                if primary and primary in data:
                    val = data[primary]
                    for alias in names:
                        if alias != primary and alias not in data:
                            data[alias] = val

        new_unused_registers: set[str] = set()
        for reg_name, value in data.items():
            if self.is_register_unused(reg_name, value):
                new_unused_registers.add(reg_name)
        self._unused_registers = new_unused_registers

        return data

    async def async_refresh_web_supplement(self) -> None:
        """Refresh optional local web data without affecting Modbus updates."""
        if not self._web_pin:
            return

        try:
            web_supplement = await async_read_web_supplement(
                self._web_host,
                self._web_pin,
                model_hint=getattr(self._model_info, "model_name", None) or self._model_name,
                preferred_variant=self._web_variant,
            )
        except Exception as err:
            error = f"{err.__class__.__name__}: {err}"
            if error != self._last_web_error:
                _LOGGER.warning(
                    "Optional IDM web supplement refresh failed for %s: %s; Modbus polling continues",
                    self._web_host,
                    error,
                )
            self._last_web_error = error
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                _WEB_SUPPLEMENT_FAILED_ISSUE,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=_WEB_SUPPLEMENT_FAILED_ISSUE,
                translation_placeholders={"host": self._web_host, "error": error},
            )
            return

        if web_supplement is None:
            self._last_web_error = "No web supplement data returned"
            return

        self._last_web_error = None
        ir.async_delete_issue(self.hass, DOMAIN, _WEB_SUPPLEMENT_FAILED_ISSUE)
        self._web_supplement = web_supplement
        # Cache which web variant succeeded so the next poll skips the other
        # (WebSocket vs. HTTP have completely different login mechanisms).
        if web_variant := _web_variant_from_supplement(web_supplement):
            self._web_variant = web_variant
        web_model_name = web_supplement.model_name
        modbus_family = navigator_family(getattr(self._model_info, "model_name", None) or self._model_name)
        web_model_family = navigator_family(web_model_name)
        model_conflicts = (
            modbus_family is not None and web_model_family is not None and modbus_family != web_model_family
        )
        if web_model_name and not model_conflicts:
            self._model_name = web_model_name
            # Keep model_info consistent so future conflict checks and
            # diagnostics reflect the retroactively detected model.
            if (
                self._model_info is not None
                and web_model_family is not None
                and navigator_family(self._model_info.model_name) is None
            ):
                self._model_info.model_name = web_model_name
        elif web_model_name:
            _LOGGER.warning(
                "Ignoring conflicting IDM web Navigator model %s because Modbus detected %s",
                web_model_name,
                getattr(self._model_info, "model_name", None) or self._model_name,
            )
        if web_supplement.software_version and not model_conflicts:
            self._firmware_version = web_supplement.software_version

        # Persist retroactively detected model/firmware so it survives reloads.
        self._persist_web_detection(web_supplement, model_conflicts)

        if self.data is not None:
            if web_supplement.navigator_version:
                self.data["web_navigator_version"] = web_supplement.navigator_version
            if web_supplement.software_version:
                self.data["web_software_version"] = web_supplement.software_version
            if web_supplement.heatpump_model:
                self.data["web_heatpump_model"] = web_supplement.heatpump_model
            if web_supplement.myidm_id:
                self.data["web_myidm_id"] = web_supplement.myidm_id
        self.async_update_listeners()

    def _persist_web_detection(self, supplement: IdmWebSupplement, model_conflicts: bool) -> None:
        """Persist web-detected model/firmware so retroactive detection survives reloads.

        When the optional web supplement detects a definitive Navigator version
        that does not conflict with Modbus detection, we store it in the config
        entry data. This ensures a later HA reload can reuse the detection even
        when Modbus probing or web access is temporarily unavailable at setup.
        """
        if model_conflicts:
            return
        entry = self.config_entry
        if entry is None:
            return
        data = getattr(entry, "data", None)
        if not isinstance(data, dict):
            return

        updates: dict[str, Any] = {}
        web_nav = supplement.navigator_version
        if web_nav and data.get(CONF_DETECTED_NAVIGATOR_VERSION) != web_nav:
            updates[CONF_DETECTED_NAVIGATOR_VERSION] = web_nav
        web_sw = supplement.software_version
        if web_sw and data.get(CONF_DETECTED_SOFTWARE_VERSION) != web_sw:
            updates[CONF_DETECTED_SOFTWARE_VERSION] = web_sw

        if not updates:
            return

        try:
            self.hass.config_entries.async_update_entry(
                entry,
                data={**data, **updates},
            )
        except Exception:
            _LOGGER.debug("Failed to persist retroactive IDM web detection", exc_info=True)
        else:
            _LOGGER.info(
                "Persisted retroactive IDM Navigator detection from web supplement: %s",
                ", ".join(sorted(updates)),
            )

    async def _delayed_refresh(self, delay: float = 0.5) -> None:
        await asyncio.sleep(delay)
        await self.async_request_refresh()

    async def async_write_register(self, reg: RegisterDef, value: Any) -> None:
        try:
            await self._client.write_register(reg, value)
        except Exception:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "write_rejected",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="write_rejected",
                translation_placeholders={"register": reg.name, "address": str(reg.address)},
            )
            raise
        # Optimistic update so entities reflect the new value immediately
        if self.data is not None:
            self.data[reg.name] = value
        self.async_update_listeners()
        if self._delayed_refresh_task is not None and not self._delayed_refresh_task.done():
            self._delayed_refresh_task.cancel()
        self._delayed_refresh_task = asyncio.create_task(self._delayed_refresh())
