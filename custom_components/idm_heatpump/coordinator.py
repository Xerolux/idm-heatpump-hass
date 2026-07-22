"""Data update coordinator for IDM Navigator heat pump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import asyncio
import logging
import math
import time
from datetime import timedelta
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from idm_heatpump import IdmModbusClient, IdmModelInfo, RegisterDef
from pymodbus.exceptions import ConnectionException, ModbusException

from .const import (
    CONF_DETECTED_NAVIGATOR_VERSION,
    CONF_DETECTED_SOFTWARE_VERSION,
    CONF_DETECTED_WEB_VARIANT,
    DOMAIN,
    MODEL,
    NEGATIVE_ONE_VALID_REGISTERS,
    UNUSED_VALUE,
)
from .error_messages import (
    classify_communication_error as _repair_issue_for_error,
    classify_web_error,
    friendly_communication_error as _friendly_communication_error,
    friendly_web_error,
)
from .registers import (
    collect_all_registers,
    collect_alias_map,
    collect_registers_from_descriptions,
    collect_aliases_from_descriptions,
)

if TYPE_CHECKING:
    from .operation_analysis import OperationAnalysis

from .web_data import (
    IdmWebAuthenticationFailed,
    IdmWebClientPool,
    IdmWebSupplement,
    async_read_web_supplement,
)

_LOGGER = logging.getLogger(__name__)
_ILLEGAL_ADDRESS_MARKERS = ("exception_code=2", "illegal data address")
_CONNECTIVITY_REPAIR_ISSUES = (
    "cannot_connect",
    "host_not_found",
    "modbus_connection_refused",
    "modbus_timeout",
    "wrong_slave_id",
    "incompatible_firmware",
    "no_data_received",
)
_WEB_SUPPLEMENT_FAILED_ISSUE = "web_supplement_failed"
_WEB_AUTH_FAILED_ISSUE = "web_authentication_failed"
_WEB_REPAIR_ISSUES = (
    _WEB_SUPPLEMENT_FAILED_ISSUE,
    _WEB_AUTH_FAILED_ISSUE,
    "web_host_not_found",
    "web_connection_refused",
    "web_timeout",
    "web_invalid_response",
)
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


def navigator_family(model_name: str | None) -> str | None:
    """Return a coarse Navigator generation identifier for conflict checks."""
    if not isinstance(model_name, str):
        return None
    normalized = model_name.casefold().replace("-", "_").replace(" ", "_")
    # Collapse repeated underscores from mixed human/slug names.
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    if normalized in {MODEL.casefold().replace(" ", "_"), "navigator_2.0_/_10", "navigator_2_0_/_10"}:
        return None
    # Accept human labels ("Navigator 2.0") and slug constants ("navigator_20").
    has_navigator_20 = (
        "navigator_20" in normalized
        or "navigator_2.0" in normalized
        or "navigator_2_0" in normalized
        or normalized.endswith("navigator_2")
    )
    has_navigator_10 = "navigator_10" in normalized
    has_navigator_pro = "navigator_pro" in normalized
    if has_navigator_20 and has_navigator_10:
        return None
    if has_navigator_20:
        return "navigator_20"
    if has_navigator_10:
        return "navigator_10"
    if has_navigator_pro:
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
    if supplement.web_variant in ("nav10", "nav20"):
        return supplement.web_variant
    family = navigator_family(supplement.navigator_version) or navigator_family(supplement.heatpump_model)
    return _web_variant_from_family(family)


class IdmCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage data fetching from IDM heat pump."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: IdmModbusClient,
        scan_interval: timedelta | None,
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
        web_variant: str | None = None,
        device_hierarchy_enabled: bool = False,
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
        self._web_variant = web_variant if web_variant in ("nav10", "nav20") else None
        self._device_hierarchy_enabled = device_hierarchy_enabled
        if web_supplement is not None:
            self._web_variant = _web_variant_from_supplement(web_supplement) or self._web_variant
        self._last_web_error: str | None = None
        self._unused_registers: set[str] = set()
        self._unsupported_registers: set[str] = set()
        self._alias_map: dict[int, list[str]] = {}
        self._register_by_name: dict[str, RegisterDef] = {}
        self._alias_primary_map: dict[int, str] | None = None
        self._room_mode_registers: list[RegisterDef] = []
        self._device_info_cache: tuple[tuple[Any, ...], Any] | None = None
        self._operation_analysis: OperationAnalysis | None = None
        self._delayed_refresh_task: asyncio.Task[None] | None = None
        self._write_timestamps: dict[int, float] = {}
        self._write_cooldown_seconds: float = 5.0
        # Room-mode individual validation is expensive (one Modbus read per
        # register). Run it on the first poll, then only every Nth poll.
        self._room_mode_validation_counter = 0
        self._room_mode_validation_interval = 6
        # Persistent web client pool: keeps the Navigator web client across
        # polls so the TCP+auth overhead is paid once per session instead of
        # every 30s. Invalidated on failure and closed in async_shutdown.
        self._web_client_pool = IdmWebClientPool()

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
        descriptions: list[dict[str, Any]] | None = None,
    ) -> None:
        if descriptions is not None:
            self._registers = collect_registers_from_descriptions(descriptions)
            self._alias_map = collect_aliases_from_descriptions(descriptions)
        elif model_info is None:
            self._registers = collect_all_registers(circuits, zone_count, zone_rooms, enable_cascade)
            self._alias_map = collect_alias_map(circuits, zone_count, zone_rooms, enable_cascade)
        else:
            self._registers = collect_all_registers(
                circuits, zone_count, zone_rooms, enable_cascade, model_info=model_info
            )
            self._alias_map = collect_alias_map(circuits, zone_count, zone_rooms, enable_cascade, model_info=model_info)
        self._register_by_name = {reg.name: reg for reg in self._registers}
        self._alias_primary_map = None
        # Room-mode registers only depend on the register set (fixed at setup
        # time), so precompute them once instead of re-scanning all registers
        # on every poll.
        self._room_mode_registers = [reg for reg in self._registers if _is_zone_room_mode_register(reg)]
        self._invalidate_device_info_cache()

    def attach_operation_analysis(self, analysis: OperationAnalysis) -> None:
        """Attach the restart-safe operating analysis before first refresh."""
        self._operation_analysis = analysis

    @property
    def operation_analysis(self) -> OperationAnalysis | None:
        return self._operation_analysis

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
    def device_hierarchy_enabled(self) -> bool:
        """Return whether entities should be organized into subdevices."""
        return self._device_hierarchy_enabled

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

    def _web_metadata_data(self) -> dict[str, str]:
        """Return web metadata stored alongside the Modbus data snapshot."""
        supplement = self._web_supplement
        if supplement is None:
            return {}
        values = {
            "web_navigator_version": supplement.navigator_version,
            "web_software_version": supplement.software_version,
            "web_heatpump_model": supplement.heatpump_model,
            "web_myidm_id": supplement.myidm_id,
        }
        return {key: value for key, value in values.items() if value}

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

    def get_register(self, register_name: str) -> RegisterDef | None:
        """Return a register by name via the cached name index (O(1))."""
        return self._register_by_name.get(register_name)

    def is_register_unused(self, register_name: str, value: Any) -> bool:
        """Check if a register value indicates an unused/invalid register."""
        if not self._hide_unused:
            return False
        if value is None:
            return True
        register = self._register_by_name.get(register_name)
        if register is None and self._registers:
            # Fallback for code paths that mutate _registers directly (e.g. tests)
            register = next((reg for reg in self._registers if reg.name == register_name), None)
        sentinel_values = getattr(register, "sentinel_values", ())
        if value in sentinel_values:
            return True
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
                    f"register_not_supported_{reg.name}",
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

    def _merge_unsupported_registers(self) -> None:
        """Mirror the library's unsupported-register set into the coordinator.

        idm-heatpump-api marks registers that respond with Modbus ``Illegal Data
        Address`` (exception code 2) as permanently failed and skips them on
        subsequent ``read_batch`` calls. The coordinator keeps its own
        ``_unsupported_registers`` skip-list (used for the zone-room mode path
        and surfaced via the ``unsupported_registers`` property), so the two
        sets must stay in sync. Merging after every poll ensures registers
        isolated by the library are reflected here too, without relying on the
        coordinator's bisection path (which never runs for these addresses
        because the library swallows the exception inside ``read_batch``).

        Uses ``getattr`` so this is a no-op against older library versions that
        do not expose ``get_unsupported_registers()``.
        """
        get_unsupported = getattr(self._client, "get_unsupported_registers", None)
        if get_unsupported is None:
            return
        library_unsupported = get_unsupported()
        if not library_unsupported:
            return
        new_unsupported = [name for name in library_unsupported if name not in self._unsupported_registers]
        if not new_unsupported:
            return
        self._unsupported_registers.update(new_unsupported)
        _LOGGER.debug(
            "Library reported %d unsupported register(s); merged into coordinator skip-list: %s",
            len(new_unsupported),
            new_unsupported,
        )

    async def _async_refresh_zone_room_modes(self, data: dict[str, Any]) -> None:
        """Refresh room mode registers individually to avoid faulty batch values.

        Room mode registers are read one-by-one because Navigator 2.0 firmware
        has been observed to return corrupt UCHAR values when they are part of
        larger batch reads. Reads stay sequential because the API serializes
        Modbus I/O on one connection; creating many waiting tasks would add no
        wire-level concurrency and would delay cancellation after a failure.
        """
        # The API already reads quarantined registers individually. Avoid a
        # second direct read on every poll once a room-mode register has been
        # proven batch-unsafe and handed over to that API path.
        get_batch_unsafe = getattr(self._client, "get_batch_unsafe_registers", None)
        batch_unsafe = set(get_batch_unsafe()) if callable(get_batch_unsafe) else set()

        # Reuse the cached register subset (built once in setup_registers) and
        # only filter out registers discovered unsupported at runtime.
        room_mode_registers = [
            reg
            for reg in self._room_mode_registers
            if reg.name not in self._unsupported_registers and reg.name not in batch_unsafe
        ]
        if not room_mode_registers:
            return

        # Skip most polls once batch-unsafe quarantine is established for a
        # register set; still re-check periodically for newly added rooms.
        self._room_mode_validation_counter += 1
        if (
            self._room_mode_validation_counter > 1
            and (self._room_mode_validation_counter - 1) % self._room_mode_validation_interval != 0
        ):
            return

        for reg in room_mode_registers:
            try:
                result = await self._client.read_register(reg)
            except asyncio.CancelledError:
                raise
            except ModbusException as err:
                if _is_illegal_address_error(err):
                    self._unsupported_registers.add(reg.name)
                    data.pop(reg.name, None)
                    _LOGGER.debug(
                        "Zone room mode register %s at address %d is unsupported; skipping it",
                        reg.name,
                        reg.address,
                    )
                    continue
                raise
            except (OSError, TimeoutError):
                raise
            except Exception as err:
                data.pop(reg.name, None)
                _LOGGER.warning(
                    "Individual validation of zone room mode register %s at address %d failed; "
                    "omitting its batch value from this update: %s",
                    reg.name,
                    reg.address,
                    err,
                )
                continue

            batch_value = data.get(reg.name)
            if batch_value != result:
                mark_batch_unsafe = getattr(self._client, "mark_batch_unsafe", None)
                if callable(mark_batch_unsafe):
                    mark_batch_unsafe(reg)
                _LOGGER.debug(
                    "Zone room mode register %s differed between batch (%r) and individual (%r) read; "
                    "quarantining it from future grouped reads",
                    reg.name,
                    batch_value,
                    result,
                )
            data[reg.name] = result

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self._async_read_registers_resilient(self._registers)

            # Keep the API and coordinator skip-lists synchronized before the
            # room-mode validation, then perform that validation in the same
            # communication error boundary as the main batch read.
            self._merge_unsupported_registers()
            await self._async_refresh_zone_room_modes(data)
        except Exception as err:
            issue_id = _repair_issue_for_error(err)
            friendly_error = _friendly_communication_error(
                issue_id,
                self._client.host,
                getattr(self._client, "port", None),
                err,
            )
            for stale_issue_id in _CONNECTIVITY_REPAIR_ISSUES:
                if stale_issue_id != issue_id:
                    ir.async_delete_issue(self.hass, DOMAIN, stale_issue_id)
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
                "%s; created repair issue %s",
                friendly_error,
                issue_id,
            )
            raise UpdateFailed(friendly_error) from err

        if not data:
            issue_id = "no_data_received"
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=issue_id,
                translation_placeholders={"host": self._client.host},
            )
            raise UpdateFailed(
                "The IDM connection succeeded, but the heat pump returned no usable register data. "
                "Check the slave ID (normally 1), Modbus proxy target and Navigator model settings"
            )

        for issue_id in _CONNECTIVITY_REPAIR_ISSUES:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

        # Apply aliases: when multiple register names share an address,
        # ensure all names appear in the data dict.
        if self._alias_map:
            if self._alias_primary_map is None:
                self._alias_primary_map = {reg.address: reg.name for reg in self._registers}
            for addr, names in self._alias_map.items():
                primary = self._alias_primary_map.get(addr)
                if primary and primary in data:
                    val = data[primary]
                    for alias in names:
                        if alias != primary and alias not in data:
                            data[alias] = val

        # Preserve independently refreshed web metadata when the base
        # coordinator replaces self.data with this new Modbus snapshot.
        data.update(self._web_metadata_data())

        new_unused_registers: set[str] = set()
        for reg_name, value in data.items():
            if self.is_register_unused(reg_name, value):
                new_unused_registers.add(reg_name)
        self._unused_registers = new_unused_registers

        if self._operation_analysis is not None:
            try:
                self._operation_analysis.process_snapshot(data, self._unused_registers)
            except Exception:
                _LOGGER.warning(
                    "Could not update IDM operation analysis; normal polling continues",
                    exc_info=True,
                )

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
                client_pool=self._web_client_pool,
                allow_variant_fallback=self._web_variant is None,
            )
        except IdmWebAuthenticationFailed as err:
            error = f"{err.__class__.__name__}: {err}"
            if error != self._last_web_error:
                _LOGGER.warning(
                    "IDM Navigator web authentication failed for %s. Re-enter the local web PIN in reconfigure",
                    self._web_host,
                )
            self._last_web_error = error
            for issue_id in _WEB_REPAIR_ISSUES:
                if issue_id != _WEB_AUTH_FAILED_ISSUE:
                    ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                _WEB_AUTH_FAILED_ISSUE,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=_WEB_AUTH_FAILED_ISSUE,
                data={"entry_id": self.config_entry.entry_id} if self.config_entry is not None else None,
                translation_placeholders={"host": self._web_host},
            )
            return
        except Exception as err:
            error = f"{err.__class__.__name__}: {err}"
            issue_id = classify_web_error(err)
            friendly_error = friendly_web_error(issue_id, self._web_host)
            if error != self._last_web_error:
                _LOGGER.warning(
                    "%s; Modbus polling continues",
                    friendly_error,
                )
                _LOGGER.debug("Technical Navigator web error", exc_info=True)
            self._last_web_error = error
            for stale_issue_id in _WEB_REPAIR_ISSUES:
                if stale_issue_id != issue_id:
                    ir.async_delete_issue(self.hass, DOMAIN, stale_issue_id)
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=issue_id,
                translation_placeholders={"host": self._web_host},
            )
            return

        if web_supplement is None:
            self._last_web_error = "No web supplement data returned"
            return

        self._last_web_error = None
        for issue_id in _WEB_REPAIR_ISSUES:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
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
                # Prefer a replaced model_info object over mutating a library
                # dataclass field in place (may be shared / frozen in future).
                try:
                    from dataclasses import replace

                    self._model_info = replace(self._model_info, model_name=web_model_name)
                except (TypeError, ValueError):
                    self._model_info.model_name = web_model_name
        elif web_model_name:
            _LOGGER.warning(
                "Ignoring conflicting IDM web Navigator model %s because Modbus detected %s",
                web_model_name,
                getattr(self._model_info, "model_name", None) or self._model_name,
            )
        if web_supplement.software_version and not model_conflicts:
            self._firmware_version = web_supplement.software_version

        # Model metadata changed; invalidate cached device info so the next
        # entity state update publishes the new model/firmware/serial number.
        self._invalidate_device_info_cache()

        # Persist retroactively detected model/firmware so it survives reloads.
        # Detection keys alone must not trigger a config-entry reload (see
        # async_reload_entry fingerprinting in __init__.py).
        self._persist_web_detection(web_supplement, model_conflicts)

        # Re-read live coordinator data after the await above. A concurrent
        # Modbus poll may have replaced self.data while the web call was in
        # flight; merging into a stale snapshot would drop those register values.
        live_data = cast(dict[str, Any] | None, getattr(self, "data", None))
        if live_data is not None:
            self.data = {**live_data, **self._web_metadata_data()}
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
        web_variant = _web_variant_from_supplement(supplement)
        if web_variant and data.get(CONF_DETECTED_WEB_VARIANT) != web_variant:
            updates[CONF_DETECTED_WEB_VARIANT] = web_variant

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
        try:
            await asyncio.sleep(delay)
            await self.async_request_refresh()
        except asyncio.CancelledError:
            pass

    def simulate_write(
        self,
        reg: RegisterDef,
        value: Any,
        *,
        dry_run: bool = True,
        allow_custom_register: bool = False,
    ) -> Any:
        """Validate a write using idm-heatpump-api write-safety hooks when available."""
        simulator = getattr(self._client, "simulate_write", None)
        if callable(simulator):
            if allow_custom_register:
                return simulator(
                    reg,
                    value,
                    dry_run=dry_run,
                    allow_custom_register=True,
                )
            return simulator(reg, value, dry_run=dry_run)
        # idm-heatpump-api < 0.6 has no dry-run safety result; keep compatibility
        # by falling back to encoding, which still validates datatype/range locally.
        encoder = getattr(self._client, "encode_value", None)
        if callable(encoder):
            return {"encoded_registers": encoder(value, reg)}
        return None

    def client_diagnostics(self) -> Mapping[str, Any]:
        """Return redaction-safe diagnostics exposed by newer idm-heatpump-api versions."""
        getter = getattr(self._client, "get_diagnostics", None)
        if not callable(getter):
            return {}
        diagnostics = getter()
        if hasattr(diagnostics, "to_dict"):
            diagnostics = diagnostics.to_dict()
        if isinstance(diagnostics, Mapping):
            return diagnostics
        if hasattr(diagnostics, "__dict__"):
            return dict(vars(diagnostics))
        return {}

    async def async_write_register(
        self,
        reg: RegisterDef,
        value: Any,
        *,
        allow_custom_register: bool = False,
    ) -> None:
        now = time.monotonic()
        last = self._write_timestamps.get(reg.address)
        if last is not None and (now - last) < self._write_cooldown_seconds:
            _LOGGER.warning(
                "Write to register %s (addr %d) within %0.1fs cooldown (last write was %0.1fs ago)",
                reg.name,
                reg.address,
                self._write_cooldown_seconds,
                now - last,
            )
        self._write_timestamps[reg.address] = now
        try:
            self.simulate_write(reg, value, allow_custom_register=allow_custom_register)
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
        # Optimistic update so entities reflect the new value immediately.
        # Replace the snapshot dict (do not mutate in place) so concurrent web
        # merges that re-read self.data cannot race mid-mutation.
        if self.data is not None:
            updated = dict(self.data)
            alias_names = self._alias_map.get(reg.address)
            if alias_names:
                for name in alias_names:
                    updated[name] = value
            else:
                updated[reg.name] = value
            self.data = updated
        self.async_update_listeners()
        old_task = self._delayed_refresh_task
        if old_task is not None and not old_task.done():
            old_task.cancel()
        # Short-lived confirmation refresh; use asyncio.create_task so unit
        # tests can await the real Task (hass.async_create_task is often a MagicMock).
        self._delayed_refresh_task = asyncio.create_task(self._delayed_refresh())

    def _invalidate_device_info_cache(self) -> None:
        """Clear cached DeviceInfo so the next access reflects fresh metadata."""
        self._device_info_cache = None

    async def async_shutdown(self) -> None:
        """Cancel pending background tasks and release resources.

        Called during config entry unload to prevent delayed refresh tasks
        from running after the coordinator is no longer active.
        """
        task = self._delayed_refresh_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        # Release any held web client so the persistent connection is closed.
        await self._web_client_pool.close()
