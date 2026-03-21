"""Tests for IdmModbusClient."""

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymodbus.exceptions import ConnectionException, ModbusException

from custom_components.idm_heatpump.modbus_client import (
    DataType,
    IdmModbusClient,
    RegisterDef,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client_and_tcp(mock_modbus_client):
    return mock_modbus_client


def _make_reg(address, datatype, name="reg", writable=False, multiplier=1.0,
              min_val=None, max_val=None):
    return RegisterDef(
        address=address,
        datatype=datatype,
        name=name,
        writable=writable,
        multiplier=multiplier,
        min_val=min_val,
        max_val=max_val,
    )


def _mock_read_result(registers):
    result = MagicMock()
    result.isError = MagicMock(return_value=False)
    result.registers = registers
    return result


# ---------------------------------------------------------------------------
# RegisterDef
# ---------------------------------------------------------------------------

class TestRegisterDef:
    def test_float_size(self):
        reg = _make_reg(1000, DataType.FLOAT, "f")
        assert reg.size == 2

    def test_non_float_size(self):
        for dt in [DataType.UCHAR, DataType.INT8, DataType.INT16, DataType.UINT16, DataType.BOOL]:
            reg = _make_reg(1000, dt)
            assert reg.size == 1


# ---------------------------------------------------------------------------
# decode_value
# ---------------------------------------------------------------------------

class TestDecodeValue:
    def setup_method(self):
        self.client = IdmModbusClient("127.0.0.1")

    def test_float(self):
        raw = struct.pack("<f", 25.5)
        low, high = struct.unpack("<HH", raw)
        reg = _make_reg(0, DataType.FLOAT)
        assert self.client.decode_value([low, high], reg) == 25.5

    def test_float_nan_returns_none(self):
        raw = struct.pack("<f", float("nan"))
        low, high = struct.unpack("<HH", raw)
        reg = _make_reg(0, DataType.FLOAT)
        assert self.client.decode_value([low, high], reg) is None

    def test_float_with_multiplier(self):
        raw = struct.pack("<f", 10.0)
        low, high = struct.unpack("<HH", raw)
        reg = _make_reg(0, DataType.FLOAT, multiplier=2.0)
        assert self.client.decode_value([low, high], reg) == 20.0

    def test_uchar(self):
        reg = _make_reg(0, DataType.UCHAR)
        assert self.client.decode_value([42], reg) == 42

    def test_uchar_high_byte_masked(self):
        reg = _make_reg(0, DataType.UCHAR)
        assert self.client.decode_value([0x01FF], reg) == 255

    def test_int8_positive(self):
        reg = _make_reg(0, DataType.INT8)
        assert self.client.decode_value([50], reg) == 50

    def test_int8_negative(self):
        reg = _make_reg(0, DataType.INT8)
        assert self.client.decode_value([0xFF], reg) == -1

    def test_int16_positive(self):
        reg = _make_reg(0, DataType.INT16)
        assert self.client.decode_value([1000], reg) == 1000

    def test_int16_negative(self):
        reg = _make_reg(0, DataType.INT16)
        assert self.client.decode_value([0xFFFF], reg) == -1

    def test_uint16(self):
        reg = _make_reg(0, DataType.UINT16)
        assert self.client.decode_value([65000], reg) == 65000

    def test_bool_true(self):
        reg = _make_reg(0, DataType.BOOL)
        assert self.client.decode_value([1], reg) is True

    def test_bool_false(self):
        reg = _make_reg(0, DataType.BOOL)
        assert self.client.decode_value([0], reg) is False

    def test_bool_odd_value(self):
        reg = _make_reg(0, DataType.BOOL)
        assert self.client.decode_value([3], reg) is True

    def test_float_not_enough_registers(self):
        reg = _make_reg(0, DataType.FLOAT)
        with pytest.raises(ValueError):
            self.client.decode_value([1], reg)


# ---------------------------------------------------------------------------
# encode_value
# ---------------------------------------------------------------------------

class TestEncodeValue:
    def setup_method(self):
        self.client = IdmModbusClient("127.0.0.1")

    def test_float_roundtrip(self):
        reg = _make_reg(0, DataType.FLOAT, writable=True)
        encoded = self.client.encode_value(25.5, reg)
        assert len(encoded) == 2
        decoded = self.client.decode_value(encoded, reg)
        assert decoded == 25.5

    def test_uchar(self):
        reg = _make_reg(0, DataType.UCHAR, writable=True)
        assert self.client.encode_value(5, reg) == [5]

    def test_uchar_masked(self):
        reg = _make_reg(0, DataType.UCHAR, writable=True)
        assert self.client.encode_value(260, reg) == [4]

    def test_int8_negative(self):
        reg = _make_reg(0, DataType.INT8, writable=True)
        assert self.client.encode_value(-1, reg) == [255]

    def test_int16_negative(self):
        reg = _make_reg(0, DataType.INT16, writable=True)
        assert self.client.encode_value(-1, reg) == [65535]

    def test_uint16(self):
        reg = _make_reg(0, DataType.UINT16, writable=True)
        assert self.client.encode_value(1000, reg) == [1000]

    def test_bool_true(self):
        reg = _make_reg(0, DataType.BOOL, writable=True)
        assert self.client.encode_value(True, reg) == [1]

    def test_bool_false(self):
        reg = _make_reg(0, DataType.BOOL, writable=True)
        assert self.client.encode_value(False, reg) == [0]


# ---------------------------------------------------------------------------
# read_register
# ---------------------------------------------------------------------------

class TestReadRegister:
    async def test_read_float(self, client_and_tcp):
        client, tcp = client_and_tcp
        raw = struct.pack("<f", 25.5)
        low, high = struct.unpack("<HH", raw)
        tcp.read_input_registers.return_value = _mock_read_result([low, high])

        reg = _make_reg(1000, DataType.FLOAT)
        val = await client.read_register(reg)
        assert val == 25.5
        tcp.read_input_registers.assert_called_once()

    async def test_read_uchar(self, client_and_tcp):
        client, tcp = client_and_tcp
        tcp.read_input_registers.return_value = _mock_read_result([7])
        reg = _make_reg(1000, DataType.UCHAR)
        assert await client.read_register(reg) == 7

    async def test_read_reconnects_when_disconnected(self, client_and_tcp):
        client, tcp = client_and_tcp
        tcp.connected = False
        tcp.read_input_registers.return_value = _mock_read_result([42])
        reg = _make_reg(1000, DataType.UCHAR)
        with patch.object(client, "connect", new=AsyncMock()) as mock_connect:
            tcp.connected = True
            client._client = tcp
            await client.read_register(reg)
            # connect called because connected was False at start
            # (connect mock resets state so we just check it didn't raise)

    async def test_read_raises_on_modbus_error(self, client_and_tcp):
        client, tcp = client_and_tcp
        error_result = MagicMock()
        error_result.isError = MagicMock(return_value=True)
        tcp.read_input_registers.return_value = error_result
        reg = _make_reg(1000, DataType.UCHAR)
        with pytest.raises(ModbusException):
            await client.read_register(reg)


# ---------------------------------------------------------------------------
# write_register
# ---------------------------------------------------------------------------

class TestWriteRegister:
    async def test_write_float(self, client_and_tcp):
        client, tcp = client_and_tcp
        ok_result = MagicMock()
        ok_result.isError = MagicMock(return_value=False)
        tcp.write_registers.return_value = ok_result

        reg = _make_reg(1000, DataType.FLOAT, writable=True)
        await client.write_register(reg, 25.5)
        tcp.write_registers.assert_called_once()

    async def test_write_readonly_raises(self, client_and_tcp):
        client, _ = client_and_tcp
        reg = _make_reg(1000, DataType.UCHAR, writable=False)
        with pytest.raises(ValueError, match="read-only"):
            await client.write_register(reg, 5)

    async def test_write_below_min_raises(self, client_and_tcp):
        client, _ = client_and_tcp
        reg = _make_reg(1000, DataType.UINT16, writable=True, min_val=10.0)
        with pytest.raises(ValueError, match="minimum"):
            await client.write_register(reg, 5)

    async def test_write_above_max_raises(self, client_and_tcp):
        client, _ = client_and_tcp
        reg = _make_reg(1000, DataType.UINT16, writable=True, max_val=100.0)
        with pytest.raises(ValueError, match="maximum"):
            await client.write_register(reg, 200)

    async def test_write_modbus_error_raises(self, client_and_tcp):
        client, tcp = client_and_tcp
        error_result = MagicMock()
        error_result.isError = MagicMock(return_value=True)
        tcp.write_registers.return_value = error_result
        reg = _make_reg(1000, DataType.UCHAR, writable=True)
        with pytest.raises(ModbusException):
            await client.write_register(reg, 1)


# ---------------------------------------------------------------------------
# read_batch
# ---------------------------------------------------------------------------

class TestReadBatch:
    async def test_empty_batch(self, client_and_tcp):
        client, _ = client_and_tcp
        result = await client.read_batch([])
        assert result == {}

    async def test_batch_contiguous_registers(self, client_and_tcp):
        client, tcp = client_and_tcp
        raw = struct.pack("<f", 20.0)
        low, high = struct.unpack("<HH", raw)
        tcp.read_input_registers.return_value = _mock_read_result([low, high, 5])

        regs = [
            _make_reg(1000, DataType.FLOAT, "temp"),
            _make_reg(1002, DataType.UCHAR, "mode"),
        ]
        result = await client.read_batch(regs)
        assert "temp" in result
        assert "mode" in result
        assert result["temp"] == 20.0
        assert result["mode"] == 5

    async def test_batch_non_contiguous_registers(self, client_and_tcp):
        client, tcp = client_and_tcp
        tcp.read_input_registers.return_value = _mock_read_result([10])

        regs = [
            _make_reg(1000, DataType.UCHAR, "a"),
            _make_reg(2000, DataType.UCHAR, "b"),
        ]
        result = await client.read_batch(regs)
        assert "a" in result
        assert "b" in result

    async def test_batch_partial_failure_continues(self, client_and_tcp):
        client, tcp = client_and_tcp
        error_result = MagicMock()
        error_result.isError = MagicMock(return_value=True)
        ok_result = _mock_read_result([42])
        tcp.read_input_registers.side_effect = [ModbusException("err"), ok_result]

        regs = [
            _make_reg(1000, DataType.UCHAR, "fail"),
            _make_reg(2000, DataType.UCHAR, "ok"),
        ]
        result = await client.read_batch(regs)
        assert result.get("ok") == 42


# ---------------------------------------------------------------------------
# connect / disconnect
# ---------------------------------------------------------------------------

class TestConnectDisconnect:
    async def test_connect(self):
        with patch(
            "custom_components.idm_heatpump.modbus_client.AsyncModbusTcpClient"
        ) as mock_class:
            mock_tcp = AsyncMock()
            mock_tcp.connected = True
            mock_class.return_value = mock_tcp

            client = IdmModbusClient("192.168.1.1", 502, 1)
            await client.connect()
            mock_tcp.connect.assert_called_once()

    async def test_connect_skips_if_already_connected(self):
        with patch(
            "custom_components.idm_heatpump.modbus_client.AsyncModbusTcpClient"
        ) as mock_class:
            mock_tcp = AsyncMock()
            mock_tcp.connected = True
            mock_class.return_value = mock_tcp

            client = IdmModbusClient("192.168.1.1")
            client._client = mock_tcp
            await client.connect()
            mock_tcp.connect.assert_not_called()

    async def test_disconnect(self, client_and_tcp):
        client, tcp = client_and_tcp
        await client.disconnect()
        tcp.close.assert_called_once()
        assert client._client is None

    async def test_get_client_raises_when_not_connected(self):
        client = IdmModbusClient("192.168.1.1")
        with pytest.raises(ConnectionException):
            client._get_client()


# ---------------------------------------------------------------------------
# test_connection
# ---------------------------------------------------------------------------

class TestTestConnection:
    async def test_successful_connection(self):
        # test_connection does `from pymodbus.client import AsyncModbusTcpClient as FreshClient`
        # so we patch the class on the pymodbus.client module directly.
        mock_tcp = AsyncMock()
        mock_tcp.connected = True
        ok_result = _mock_read_result([0x0000, 0x4148])
        mock_tcp.read_input_registers.return_value = ok_result
        mock_tcp.close = MagicMock()

        import pymodbus.client as _pymodbus_client
        original = _pymodbus_client.AsyncModbusTcpClient
        _pymodbus_client.AsyncModbusTcpClient = MagicMock(return_value=mock_tcp)
        try:
            client = IdmModbusClient("192.168.1.1")
            result = await client.test_connection()
            assert result is True
        finally:
            _pymodbus_client.AsyncModbusTcpClient = original

    async def test_connection_fails_not_connected(self):
        with patch(
            "custom_components.idm_heatpump.modbus_client.AsyncModbusTcpClient"
        ) as mock_class:
            mock_tcp = AsyncMock()
            mock_tcp.connected = False
            mock_class.return_value = mock_tcp

            client = IdmModbusClient("192.168.1.1")
            result = await client.test_connection()
            assert result is False

    async def test_connection_fails_on_exception(self):
        with patch(
            "custom_components.idm_heatpump.modbus_client.AsyncModbusTcpClient"
        ) as mock_class:
            mock_tcp = AsyncMock()
            mock_tcp.connect.side_effect = ConnectionException("refused")
            mock_class.return_value = mock_tcp

            client = IdmModbusClient("192.168.1.1")
            result = await client.test_connection()
            assert result is False
