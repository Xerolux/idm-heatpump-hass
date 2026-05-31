"""Async Modbus TCP client for IDM Navigator heat pumps.

This module now delegates the heavy lifting to the official idm_heatpump library
while maintaining backward compatibility for the existing HA integration code
during the migration (Option B).
"""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import logging

from pymodbus.exceptions import ConnectionException

from idm_heatpump import IdmModbusClient as _LibIdmModbusClient
from idm_heatpump.client import DataType as LibDataType, RegisterDef as LibRegisterDef

_LOGGER = logging.getLogger(__name__)

# Re-export so the rest of the integration can continue importing from here
DataType = LibDataType
RegisterDef = LibRegisterDef


# pymodbus >= 3.10 uses device_id (previously called slave)
def _get_slave_param() -> str:
    try:
        params = inspect.signature(AsyncModbusTcpClient.read_input_registers).parameters
        if "device_id" in params:
            return "device_id"
        return "slave"
    except Exception:
        # Fallback if inspection fails
        parts = pymodbus.__version__.split(".")
        try:
            major = int(parts[0])
            minor = int(parts[1])
            if major > 3 or (major == 3 and minor >= 10):
                return "device_id"
        except (ValueError, IndexError):
            pass
        return "slave"


_PMODBUS_SLAVE_PARAM = _get_slave_param()


class DataType(Enum):
    FLOAT = "FLOAT"
    UCHAR = "UCHAR"
    INT8 = "INT8"
    INT16 = "INT16"
    UINT16 = "UINT16"
    BOOL = "BOOL"
    BITFLAG = "BITFLAG"  # Bitfield: each bit represents an independent flag


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

    def __post_init__(self) -> None:
        self.size = 2 if self.datatype == DataType.FLOAT else 1


_MAX_GROUP_FAILURES = 3


class IdmModbusClient(_LibIdmModbusClient):
    """
    Compatibility subclass of the official library client.

    The real implementation lives in the idm_heatpump package.
    This class exists only to keep the existing import paths in the HA
    integration working during the migration.
    """

    def __init__(self, host: str, port: int = 502, slave_id: int = 1) -> None:
        # Delegate initialization to the library client
        super().__init__(host=host, port=port, slave_id=slave_id)
        _LOGGER.debug("IdmModbusClient (HA wrapper) initialized using idm_heatpump library")

    async def _read_registers(self, address: int, count: int) -> list[int]:
        async with self._lock:
            client = self._get_client()
            addr = int(address)
            cnt = int(count)
            slave = int(self._slave_id)
            _LOGGER.debug(
                "Calling read_input_registers address=%s count=%s %s=%s",
                addr,
                cnt,
                _PMODBUS_SLAVE_PARAM,
                slave,
            )
            kwargs = {_PMODBUS_SLAVE_PARAM: slave}
            try:
                result = await client.read_input_registers(
                    address=addr,
                    count=cnt,
                    **kwargs,  # type: ignore[arg-type]
                )
            except Exception as e:
                _LOGGER.error("Exception during read_input_registers: %s", e)
                raise

            _LOGGER.debug(
                "Result type: %s, isError: %s", type(result).__name__, result.isError()
            )

            if result.isError():
                raise ModbusException(f"Modbus error reading address {address}")

            _LOGGER.debug("Registers: %s", result.registers)

            return list(result.registers)

    async def _write_registers(self, address: int, values: list[int]) -> None:
        async with self._lock:
            client = self._get_client()
            addr = int(address)
            slave = int(self._slave_id)
            vals = [int(v) for v in values]
            kwargs = {_PMODBUS_SLAVE_PARAM: slave}
            result = await client.write_registers(
                address=addr,
                values=vals,
                **kwargs,  # type: ignore[arg-type]
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
            if math.isnan(value):
                return None
            return round(value * reg.multiplier, 2)

        elif reg.datatype == DataType.UCHAR:
            return (
                round((registers[0] & 0xFF) * reg.multiplier, 2)
                if reg.multiplier != 1.0
                else (registers[0] & 0xFF)
            )

        elif reg.datatype == DataType.INT8:
            val = registers[0] & 0xFF
            if val >= 128:
                val -= 256
            return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

        elif reg.datatype == DataType.INT16:
            val = registers[0]
            if val >= 32768:
                val -= 65536
            return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

        elif reg.datatype == DataType.UINT16:
            return (
                round(registers[0] * reg.multiplier, 2)
                if reg.multiplier != 1.0
                else registers[0]
            )

        elif reg.datatype == DataType.BOOL:
            return bool(registers[0] & 0x01)

        elif reg.datatype == DataType.BITFLAG:
            # Return raw integer; sensor layer decodes flags using enum_options
            return registers[0] & 0xFF

        raise ValueError(f"Unknown datatype: {reg.datatype}")

    def encode_value(self, value: Any, reg: RegisterDef) -> list[int]:
        if reg.datatype == DataType.FLOAT:
            float_val = float(value) / reg.multiplier
            raw = struct.pack("<f", float_val)
            low, high = struct.unpack("<HH", raw)
            return [low, high]

        elif reg.datatype == DataType.UCHAR:
            val = int(round(float(value) / reg.multiplier))
            return [val & 0xFF]

        elif reg.datatype == DataType.INT8:
            val = int(round(float(value) / reg.multiplier))
            if val < 0:
                val += 256
            return [val & 0xFF]

        elif reg.datatype == DataType.INT16:
            val = int(round(float(value) / reg.multiplier))
            if val < 0:
                val += 65536
            return [val & 0xFFFF]

        elif reg.datatype == DataType.UINT16:
            val = int(round(float(value) / reg.multiplier))
            return [val & 0xFFFF]

        elif reg.datatype == DataType.BOOL:
            return [1 if value else 0]

        elif reg.datatype == DataType.BITFLAG:
            return [int(value) & 0xFF]

        raise ValueError(f"Unknown datatype: {reg.datatype}")

    async def read_register(self, reg: RegisterDef) -> Any:
        try:
            if self._client is None or not self._client.connected:
                await self.connect()
            registers = await self._read_registers(reg.address, reg.size)
            return self.decode_value(registers, reg)
        except (ConnectionException, ModbusException) as err:
            _LOGGER.warning(
                "Failed to read register %s (%d): %s", reg.name, reg.address, err
            )
            raise

    async def write_register(self, reg: RegisterDef, value: Any) -> None:
        if not reg.writable:
            raise ValueError(f"Register {reg.name} is read-only")

        if reg.min_val is not None and value < reg.min_val:
            raise ValueError(f"Value {value} below minimum {reg.min_val}")
        if reg.max_val is not None and value > reg.max_val:
            raise ValueError(f"Value {value} above maximum {reg.max_val}")

        try:
            if self._client is None or not self._client.connected:
                await self.connect()
            encoded = self.encode_value(value, reg)
            await self._write_registers(reg.address, encoded)
            _LOGGER.debug("Wrote %s = %s to address %d", reg.name, value, reg.address)
        except (ConnectionException, ModbusException) as err:
            _LOGGER.error(
                "Failed to write register %s (%d): %s", reg.name, reg.address, err
            )
            raise

    async def read_batch(self, register_list: list[RegisterDef]) -> dict[str, Any]:
        if not register_list:
            return {}

        if self._client is None or not self._client.connected:
            await self.connect()

        sorted_regs = sorted(register_list, key=lambda r: r.address)
        groups: list[list[RegisterDef]] = []
        current_group: list[RegisterDef] = [sorted_regs[0]]
        current_group_word_count = sorted_regs[0].size

        for reg in sorted_regs[1:]:
            last = current_group[-1]
            expected_next = last.address + last.size
            if (
                reg.address == expected_next
                and (current_group_word_count + reg.size) <= 30
            ):
                current_group.append(reg)
                current_group_word_count += reg.size
            else:
                groups.append(current_group)
                current_group = [reg]
                current_group_word_count = reg.size
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

        if start in self._permanently_failed_addresses:
            return {}

        try:
            registers = await self._read_registers(start, count)
            # Reset failure count on success
            self._group_failure_counts.pop(start, None)
        except (ConnectionException, ModbusException) as err:
            failures = self._group_failure_counts.get(start, 0) + 1
            self._group_failure_counts[start] = failures
            if failures >= _MAX_GROUP_FAILURES:
                self._permanently_failed_addresses.add(start)
                reg_names = [r.name for r in group]
                _LOGGER.warning(
                    "Address %d failed %d times, permanently skipping (registers: %s)",
                    start,
                    failures,
                    reg_names,
                )
            else:
                _LOGGER.warning("Failed to read group starting at %d: %s", start, err)
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
                except Exception as fallback_err:  # noqa: BLE001
                    _LOGGER.debug(
                        "Fallback read for %s also failed: %s", reg.name, fallback_err
                    )
            offset += reg.size

        return data

    async def test_connection(self) -> bool:
        from pymodbus.client import AsyncModbusTcpClient as FreshClient

        test_client = FreshClient(
            host=str(self._host), port=int(self._port), timeout=10
        )
# All legacy implementation has been removed.
# The real functionality is provided by inheriting from idm_heatpump.IdmModbusClient.
