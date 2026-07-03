"""Data update coordinator for IDM Navigator heat pump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from idm_heatpump import IdmModbusClient, IdmModelInfo, RegisterDef
from pymodbus.exceptions import ConnectionException, ModbusException

from .const import DOMAIN, MODEL, NEGATIVE_ONE_VALID_REGISTERS, UNUSED_VALUE
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


def _is_illegal_address_error(err: ModbusException) -> bool:
    """Return whether a Modbus exception reports an unsupported address."""
    message = str(err).casefold()
    return any(marker in message for marker in _ILLEGAL_ADDRESS_MARKERS)


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
        self._last_web_error: str | None = None
        self._unused_registers: set[str] = set()
        self._unsupported_registers: set[str] = set()
        self._alias_map: dict[int, list[str]] = {}

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
    def web_enabled(self) -> bool:
        return bool(self._web_pin)

    @property
    def web_host(self) -> str:
        return self._web_host

    @property
    def last_web_error(self) -> str | None:
        return self._last_web_error

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
            if isinstance(value, float) and (value != value or abs(value) == float("inf")):
                return True
        return False

    async def _async_read_registers_resilient(self, registers: list[RegisterDef]) -> dict[str, Any]:
        """Read registers while isolating addresses unsupported by this device.

        Some Navigator firmware variants reject optional register blocks with
        Modbus exception code 2. Bisecting only on that specific response keeps
        all supported entities available without hiding real connection errors.
        """
        if not registers:
            return await self._client.read_batch(registers)

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
                    "Register %s (address %d) is not supported by this heat pump; skipping it",
                    reg.name,
                    reg.address,
                )
                return {}

            midpoint = len(readable) // 2
            data = await self._async_read_registers_resilient(readable[:midpoint])
            data.update(await self._async_read_registers_resilient(readable[midpoint:]))
            return data

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
            raise UpdateFailed(f"Error communicating with heat pump: {err}") from err

        for issue_id in _CONNECTIVITY_REPAIR_ISSUES:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

        if not data:
            raise UpdateFailed("No data received from heat pump")

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
            web_supplement = await async_read_web_supplement(self._web_host, self._web_pin)
        except Exception as err:
            error = f"{err.__class__.__name__}: {err}"
            if error != self._last_web_error:
                _LOGGER.warning("Optional IDM web supplement refresh failed for %s: %s", self._web_host, error)
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
        if web_supplement.model_name:
            self._model_name = web_supplement.model_name
        if web_supplement.software_version:
            self._firmware_version = web_supplement.software_version

        if self.data is not None:
            if web_supplement.navigator_version:
                self.data["web_navigator_version"] = web_supplement.navigator_version
            if web_supplement.software_version:
                self.data["web_software_version"] = web_supplement.software_version
            if web_supplement.heatpump_model:
                self.data["web_heatpump_model"] = web_supplement.heatpump_model
        self.async_update_listeners()

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
        # Delayed refresh: wait for device to confirm write before re-polling.
        # Without delay, read-back may return stale value before device processes write,
        # causing optimistic update to be overwritten.
        asyncio.create_task(self._delayed_refresh())
