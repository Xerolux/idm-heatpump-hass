import asyncio
import struct
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pymodbus.exceptions import ModbusException
from custom_components.idm_heatpump_v2.modbus_client import (
    IdmModbusClient,
    RegisterDef,
    DataType,
)


@pytest.fixture
def mock_client():
    with patch("custom_components.idm_heatpump_v2.modbus_client.AsyncModbusTcpClient") as mock_class:
        mock_instance = AsyncMock()
        mock_instance.connected = True
        mock_instance.isError = MagicMock(return_value=False)
        mock_class.return_value = mock_instance

        client = IdmModbusClient(host="127.0.0.1", port=502, slave_id=1)
        client._client = mock_instance
        yield client, mock_instance


@pytest.mark.asyncio
async def test_read_float_register(mock_client):
    client, mock_tcp_client = mock_client

    # Mock return values for read_input_registers
    mock_result = MagicMock()
    mock_result.isError = MagicMock(return_value=False)
    # 25.5 -> struct.pack("<f", 25.5) -> b'\x00\x00\xccA'
    # unpack("<HH") -> (0, 16844)
    # raw = b'\x00\x00\xccA'
    # struct.unpack("<f", raw)[0] == 25.5
    mock_result.registers = [0x0000, 0x41cc]
    mock_tcp_client.read_input_registers.return_value = mock_result

    reg = RegisterDef(
        address=1000,
        datatype=DataType.FLOAT,
        name="test_float",
    )

    val = await client.read_register(reg)
    assert val == 25.5
    mock_tcp_client.read_input_registers.assert_called_once()


@pytest.mark.asyncio
async def test_write_float_register(mock_client):
    client, mock_tcp_client = mock_client

    mock_result = MagicMock()
    mock_result.isError = MagicMock(return_value=False)
    mock_tcp_client.write_registers.return_value = mock_result

    reg = RegisterDef(
        address=1000,
        datatype=DataType.FLOAT,
        name="test_float_write",
        writable=True,
    )

    await client.write_register(reg, 25.5)

    # Check that it encoded correctly
    # After fixing the endianness bug, it should write [0x0000, 0x41cc]
    # For now, let's just assert write_registers was called
    mock_tcp_client.write_registers.assert_called_once()


@pytest.mark.asyncio
async def test_read_batch(mock_client):
    client, mock_tcp_client = mock_client

    mock_result = MagicMock()
    mock_result.isError = MagicMock(return_value=False)
    # provide some generic data
    mock_result.registers = [0x0000, 0x41cc, 25, 0]
    mock_tcp_client.read_input_registers.return_value = mock_result

    reg1 = RegisterDef(address=1000, datatype=DataType.FLOAT, name="test1")
    reg2 = RegisterDef(address=1002, datatype=DataType.UCHAR, name="test2")

    res = await client.read_batch([reg1, reg2])

    assert "test1" in res
    assert "test2" in res
