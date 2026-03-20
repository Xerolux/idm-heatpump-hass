"""Data update coordinator for IDM Navigator heat pump."""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UNUSED_VALUE
from .modbus_client import IdmModbusClient, RegisterDef
from .registers import collect_all_registers

_LOGGER = logging.getLogger(__name__)


class IdmCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage data fetching from IDM heat pump."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: IdmModbusClient,
        scan_interval: timedelta,
        sensor_descriptions: list[dict],
        binary_sensor_descriptions: list[dict],
        number_descriptions: list[dict],
        select_descriptions: list[dict],
        switch_descriptions: list[dict],
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
    def sensor_descriptions(self) -> list[dict]:
        return self._sensor_descs

    @property
    def binary_sensor_descriptions(self) -> list[dict]:
        return self._binary_descs

    @property
    def number_descriptions(self) -> list[dict]:
        return self._number_descs

    @property
    def select_descriptions(self) -> list[dict]:
        return self._select_descs

    @property
    def switch_descriptions(self) -> list[dict]:
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

    def is_register_unused(self, register_name: str, value: Any) -> bool:
        """Check if a register value indicates an unused/invalid register."""
        if not self._hide_unused:
            return False
        if value is None:
            return True
        if isinstance(value, float) and abs(value - UNUSED_VALUE) < 0.01:
            return True
        return False

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self._client.read_batch(self._registers)
            if not data:
                raise UpdateFailed("No data received from heat pump")
            
            for reg_name, value in data.items():
                if self.is_register_unused(reg_name, value):
                    self._unused_registers.add(reg_name)
            
            return data
        except Exception as err:
            _LOGGER.error("Error updating data: %s", err)
            raise UpdateFailed(f"Error communicating with heat pump: {err}") from err

    async def async_write_register(self, reg: RegisterDef, value: Any) -> None:
        await self._client.write_register(reg, value)
        self.data[reg.name] = value
        self.async_update_listeners()
