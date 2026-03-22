from __future__ import annotations
"""Data update coordinator for IDM Navigator heat pump."""

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UNUSED_VALUE
from .modbus_client import IdmModbusClient, RegisterDef
from .registers import collect_all_registers

_LOGGER = logging.getLogger(__name__)


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
    ) -> None:
        self._client = client
        self._sensor_descs = sensor_descriptions
        self._binary_descs = binary_sensor_descriptions
        self._number_descs = number_descriptions
        self._select_descs = select_descriptions
        self._switch_descs = switch_descriptions
        self._registers: list[RegisterDef] = []
        self._hide_unused = hide_unused
        self._unused_registers: set[str] = set()

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
    ) -> None:
        self._registers = collect_all_registers(circuits, zone_count, zone_rooms)

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
    def unused_registers(self) -> set[str]:
        return self._unused_registers

    @property
    def registers_count(self) -> int:
        return len(self._registers)

    def is_register_unused(self, register_name: str, value: Any) -> bool:
        """Check if a register value indicates an unused/invalid register."""
        if not self._hide_unused:
            return False
        if value is None:
            return True
        if isinstance(value, (int, float)) and abs(value - UNUSED_VALUE) < 0.01:
            return True
        return False

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self._client.read_batch(self._registers)
        except Exception as err:
            # Only create a repair issue for actual communication failures
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "cannot_connect",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="cannot_connect",
                translation_placeholders={"host": self._client.host},
            )
            raise UpdateFailed(f"Error communicating with heat pump: {err}") from err

        # Successful read – clear any previous connectivity repair issue
        ir.async_delete_issue(self.hass, DOMAIN, "cannot_connect")

        if not data:
            raise UpdateFailed("No data received from heat pump")

        for reg_name, value in data.items():
            if self.is_register_unused(reg_name, value):
                self._unused_registers.add(reg_name)

        return data

    async def async_write_register(self, reg: RegisterDef, value: Any) -> None:
        await self._client.write_register(reg, value)
        # Optimistic update so entities reflect the new value immediately
        if self.data is not None:
            self.data[reg.name] = value
        self.async_update_listeners()
        # Schedule a full refresh so dependent registers are also updated promptly
        await self.async_request_refresh()
