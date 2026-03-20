"""Async Modbus TCP client for IDM Navigator heat pumps."""

import asyncio
import logging
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException

_LOGGER = logging.getLogger(__name__)


class DataType(Enum):
    FLOAT = "FLOAT"
    UCHAR = "UCHAR"
    INT16 = "INT16"
    UINT16 = "UINT16"
    BOOL = "BOOL"


@dataclass
class RegisterDef:
    address: int
    datatype: DataType
    name: str
    unit: str | None = None
    writable: bool = False
    min_val: float | None = None
    max_val: float | None = None
    enum_options: dict[int, str] | None = None
    multiplier: float = 1.0
    size: int = field(init=False)

    def __post_init__(self):
        if self.datatype == DataType.FLOAT:
            self.size = 2
        else:
            self.size = 1


class IdmModbusClient:
    def __init__(self, host: str, port: int = 502, slave_id: int = 1) -> None:
        self._host = host
        self._port = port
        self._slave_id = slave_id
        self._client: AsyncModbusTcpClient | None = None
        self._lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    async def connect(self) -> None:
        if self._client is None or not self._client.connected:
            self._client = AsyncModbusTcpClient(
                host=self._host, port=self._port, timeout=10
            )
            await self._client.connect()
            _LOGGER.debug("Connected to %s:%d", self._host, self._port)

    async def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            _LOGGER.debug("Disconnected from %s:%d", self._host, self._port)

    def _get_client(self) -> AsyncModbusTcpClient:
        if self._client is None or not self._client.connected:
            raise ConnectionException(f"Not connected to {self._host}:{self._port}")
        return self._client

    async def _read_registers(self, address: int, count: int) -> list[int]:
        async with self._lock:
            client = self._get_client()
            result = await client.read_input_registers(
                address=address, count=count, device_id=self._slave_id
            )

            if result.isError():
                raise ModbusException(f"Modbus error reading address {address}")

            return list(result.registers)

    async def _write_registers(self, address: int, values: list[int]) -> None:
        async with self._lock:
            client = self._get_client()
            result = await client.write_registers(
                address=address, values=values, device_id=self._slave_id
            )

            if result.isError():
                raise ModbusException(f"Modbus error writing address {address}")

    def decode_value(self, registers: list[int], reg: RegisterDef) -> Any:
        if reg.datatype == DataType.FLOAT:
            if len(registers) < 2:
                raise ValueError("Not enough registers for FLOAT")
            low_word = registers[0]
            high_word = registers[1]
            raw = struct.pack("<HH", low_word, high_word)
            value = struct.unpack("<f", raw)[0]
            if value != value:
                return None
            return round(value * reg.multiplier, 2)

        elif reg.datatype == DataType.UCHAR:
            return registers[0] & 0xFF

        elif reg.datatype == DataType.INT16:
            val = registers[0]
            if val >= 32768:
                val -= 65536
            return val

        elif reg.datatype == DataType.UINT16:
            return registers[0]

        elif reg.datatype == DataType.BOOL:
            return bool(registers[0] & 0x01)

        raise ValueError(f"Unknown datatype: {reg.datatype}")

    def encode_value(self, value: Any, reg: RegisterDef) -> list[int]:
        if reg.datatype == DataType.FLOAT:
            float_val = float(value) / reg.multiplier
            raw = struct.pack(">f", float_val)
            low, high = struct.unpack(">HH", raw)
            return [low, high]

        elif reg.datatype == DataType.UCHAR:
            return [int(value) & 0xFF]

        elif reg.datatype == DataType.INT16:
            val = int(value)
            if val < 0:
                val += 65536
            return [val & 0xFFFF]

        elif reg.datatype == DataType.UINT16:
            return [int(value) & 0xFFFF]

        elif reg.datatype == DataType.BOOL:
            return [1 if value else 0]

        raise ValueError(f"Unknown datatype: {reg.datatype}")

    async def read_register(self, reg: RegisterDef) -> Any:
        try:
            await self.connect()
            registers = await self._read_registers(reg.address, reg.size)
            return self.decode_value(registers, reg)
        except (ConnectionException, ModbusException) as err:
            _LOGGER.warning("Failed to read register %s (%d): %s", reg.name, reg.address, err)
            raise

    async def write_register(self, reg: RegisterDef, value: Any) -> None:
        if not reg.writable:
            raise ValueError(f"Register {reg.name} is read-only")

        if reg.min_val is not None and value < reg.min_val:
            raise ValueError(f"Value {value} below minimum {reg.min_val}")
        if reg.max_val is not None and value > reg.max_val:
            raise ValueError(f"Value {value} above maximum {reg.max_val}")

        try:
            await self.connect()
            encoded = self.encode_value(value, reg)
            await self._write_registers(reg.address, encoded)
            _LOGGER.debug("Wrote %s = %s to address %d", reg.name, value, reg.address)
        except (ConnectionException, ModbusException) as err:
            _LOGGER.error("Failed to write register %s (%d): %s", reg.name, reg.address, err)
            raise

    async def read_batch(
        self, register_list: list[RegisterDef]
    ) -> dict[str, Any]:
        if not register_list:
            return {}

        await self.connect()

        sorted_regs = sorted(register_list, key=lambda r: r.address)
        groups: list[list[RegisterDef]] = []
        current_group: list[RegisterDef] = [sorted_regs[0]]

        for reg in sorted_regs[1:]:
            last = current_group[-1]
            expected_next = last.address + last.size
            if reg.address == expected_next and (len(current_group) + reg.size) <= 30:
                current_group.append(reg)
            else:
                groups.append(current_group)
                current_group = [reg]
        groups.append(current_group)

        results: dict[str, Any] = {}
        tasks = [self._read_group(group) for group in groups]
        group_results = await asyncio.gather(*tasks, return_exceptions=True)

        for group_result in group_results:
            if isinstance(group_result, dict):
                results.update(group_result)
            elif isinstance(group_result, Exception):
                _LOGGER.warning("Error reading register group: %s", group_result)

        return results

    async def _read_group(self, group: list[RegisterDef]) -> dict[str, Any]:
        start = group[0].address
        end = group[-1].address + group[-1].size
        count = end - start

        try:
            registers = await self._read_registers(start, count)
        except (ConnectionException, ModbusException) as err:
            _LOGGER.warning(
                "Failed to read group starting at %d: %s", start, err
            )
            return {}

        data: dict[str, Any] = {}
        offset = 0
        for reg in group:
            try:
                reg_slice = registers[offset : offset + reg.size]
                value = self.decode_value(reg_slice, reg)
                data[reg.name] = value
            except (ValueError, IndexError) as err:
                _LOGGER.debug(
                    "Failed to decode %s at offset %d: %s",
                    reg.name,
                    offset,
                    err,
                )
                try:
                    individual = await self.read_register(reg)
                    data[reg.name] = individual
                except Exception:
                    pass
            offset += reg.size

        return data

    async def test_connection(self) -> bool:
        try:
            await self.connect()
            test_reg = RegisterDef(
                address=1350,
                datatype=DataType.FLOAT,
                name="test",
            )
            result = await self.read_register(test_reg)
            return result is not None
        except Exception:
            return False
        finally:
            await self.disconnect()
