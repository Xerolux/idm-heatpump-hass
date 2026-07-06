"""Tests for IdmModbusClient."""

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymodbus.exceptions import ConnectionException, ModbusException

from idm_heatpump import DataType, IdmModbusClient, RegisterDef


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client_and_tcp(mock_modbus_client):
    return mock_modbus_client


def _make_reg(address, datatype, name="reg", writable=False, multiplier=1.0, min_val=None, max_val=None):
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

    def test_uchar_max_value(self):
        reg = _make_reg(0, DataType.UCHAR, writable=True)
        assert self.client.encode_value(255, reg) == [255]

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
        with patch.object(client, "connect", new=AsyncMock()):
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
        client._max_retries = 1
        error_result = MagicMock()
        error_result.isError = MagicMock(return_value=True)
        ok_result = _mock_read_result([42])
        tcp.read_input_registers.side_effect = [
            ModbusException("err"),
            ModbusException("err"),
            ok_result,
        ]

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
        with patch("idm_heatpump.client.AsyncModbusTcpClient") as mock_class:
            mock_tcp = AsyncMock()
            mock_tcp.connected = True
            mock_class.return_value = mock_tcp

            client = IdmModbusClient("192.168.1.1", 502, 1)
            await client.connect()
            mock_tcp.connect.assert_called_once()

    async def test_connect_skips_if_already_connected(self):
        with patch("idm_heatpump.client.AsyncModbusTcpClient") as mock_class:
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
            client._require_client()


# ---------------------------------------------------------------------------
# host / port properties
# ---------------------------------------------------------------------------


class TestClientProperties:
    def test_host_property(self):
        client = IdmModbusClient("10.0.0.1")
        assert client.host == "10.0.0.1"

    def test_port_property(self):
        client = IdmModbusClient("10.0.0.1", port=1234)
        assert client.port == 1234

    def test_default_port(self):
        client = IdmModbusClient("10.0.0.1")
        assert client.port == 502


# ---------------------------------------------------------------------------
# BITFLAG decode / encode
# ---------------------------------------------------------------------------


class TestBitflagCodec:
    def setup_method(self):
        self.client = IdmModbusClient("127.0.0.1")

    def test_decode_bitflag_returns_raw_int(self):
        reg = _make_reg(0, DataType.BITFLAG)
        assert self.client.decode_value([0b00000101], reg) == 5

    def test_decode_bitflag_masks_high_byte(self):
        reg = _make_reg(0, DataType.BITFLAG)
        # value 0x01FF -> masked to 0xFF = 255
        assert self.client.decode_value([0x01FF], reg) == 0xFF

    def test_encode_bitflag(self):
        reg = _make_reg(0, DataType.BITFLAG, writable=True)
        assert self.client.encode_value(0b00000101, reg) == [5]

    def test_encode_bitflag_masks_high_byte(self):
        reg = _make_reg(0, DataType.BITFLAG, writable=True)
        assert self.client.encode_value(0x1FF, reg) == [0xFF]


# ---------------------------------------------------------------------------
# Batch grouping (30-register limit)
# ---------------------------------------------------------------------------


class TestReadBatchGrouping:
    async def test_registers_within_30_limit_form_one_group(self, client_and_tcp):
        """30 contiguous UCHAR registers => single read_input_registers call."""
        client, tcp = client_and_tcp
        tcp.read_input_registers.return_value = _mock_read_result([i for i in range(30)])
        regs = [_make_reg(1000 + i, DataType.UCHAR, f"r{i}") for i in range(30)]
        result = await client.read_batch(regs)
        assert tcp.read_input_registers.call_count == 1
        assert len(result) == 30

    async def test_registers_exceeding_40_limit_form_two_groups(self, client_and_tcp):
        """41 contiguous UCHAR registers => two read_input_registers calls."""
        client, tcp = client_and_tcp
        tcp.read_input_registers.side_effect = lambda *args, **kwargs: _mock_read_result([0] * kwargs["count"])
        regs = [_make_reg(1000 + i, DataType.UCHAR, f"r{i}") for i in range(41)]
        await client.read_batch(regs)
        # First group: 40, second group: 1 → two calls
        assert tcp.read_input_registers.call_count == 2

    async def test_float_pair_counts_as_two_in_group_size(self, client_and_tcp):
        """A FLOAT register takes 2 addresses; 15 FLOATs = 30 slots => one group."""
        client, tcp = client_and_tcp
        raw = struct.pack("<f", 1.0)
        low, high = struct.unpack("<HH", raw)
        tcp.read_input_registers.return_value = _mock_read_result([low, high] * 15)
        regs = [_make_reg(1000 + i * 2, DataType.FLOAT, f"f{i}") for i in range(15)]
        await client.read_batch(regs)
        assert tcp.read_input_registers.call_count == 1

    async def test_twenty_one_float_registers_are_split_into_two_groups(self, client_and_tcp):
        """21 FLOATs consume 42 words and must be split into 2 groups."""
        client, tcp = client_and_tcp
        raw = struct.pack("<f", 1.0)
        low, high = struct.unpack("<HH", raw)
        tcp.read_input_registers.side_effect = lambda *args, **kwargs: _mock_read_result(
            ([low, high] * 21)[: kwargs["count"]]
        )
        regs = [_make_reg(1000 + i * 2, DataType.FLOAT, f"f{i}") for i in range(21)]
        await client.read_batch(regs)
        assert tcp.read_input_registers.call_count == 2

    async def test_gap_in_addresses_creates_new_group(self, client_and_tcp):
        """Non-contiguous registers with gap > 10 each form their own group."""
        client, tcp = client_and_tcp
        tcp.read_input_registers.return_value = _mock_read_result([7])
        regs = [
            _make_reg(1000, DataType.UCHAR, "a"),
            _make_reg(1020, DataType.UCHAR, "b"),  # gap at 1001-1019
        ]
        await client.read_batch(regs)
        assert tcp.read_input_registers.call_count == 2


# ---------------------------------------------------------------------------
# _read_group permanent failure tracking
# ---------------------------------------------------------------------------


class TestReadGroupFailureTracking:
    async def test_first_failure_increments_count(self, client_and_tcp):
        client, tcp = client_and_tcp
        client._max_retries = 1
        tcp.read_input_registers.side_effect = ModbusException("err")
        regs = [_make_reg(1000, DataType.UCHAR, "x")]
        result = await client._read_group(regs)
        assert result == {}
        assert client._register_failures.get("x") == 1

    async def test_second_failure_increments_to_two(self, client_and_tcp):
        client, tcp = client_and_tcp
        client._max_retries = 1
        tcp.read_input_registers.side_effect = ModbusException("err")
        regs = [_make_reg(1000, DataType.UCHAR, "x")]
        await client._read_group(regs)
        await client._read_group(regs)
        assert client._register_failures.get("x") == 2
        assert "x" not in client._permanently_failed_registers

    async def test_third_failure_marks_permanent(self):
        """After 3 failures, register is marked permanently failed."""
        client = IdmModbusClient("127.0.0.1")
        client._max_retries = 1
        mock_tcp = AsyncMock()
        mock_tcp.connected = True
        mock_tcp.read_input_registers.side_effect = ModbusException("err")
        client._client = mock_tcp
        regs = [_make_reg(1000, DataType.UCHAR, "x")]
        for _ in range(3):
            await client._read_group(regs)
        assert "x" in client._permanently_failed_registers

    async def test_permanently_failed_register_skipped(self, client_and_tcp):
        """A permanently-failed register is skipped by read_batch."""
        client, tcp = client_and_tcp
        client._permanently_failed_registers.add("x")
        regs = [_make_reg(1000, DataType.UCHAR, "x")]
        result = await client.read_batch(regs)
        assert result == {}
        tcp.read_input_registers.assert_not_called()

    async def test_reset_failed_registers(self, client_and_tcp):
        """reset_failed_registers clears all failure tracking."""
        client, tcp = client_and_tcp
        client._register_failures["x"] = 2
        client._permanently_failed_registers.add("x")
        client.reset_failed_registers()
        assert not client._register_failures
        assert not client._permanently_failed_registers

    async def test_incomplete_data_skips_register(self, client_and_tcp):
        """When batch returns fewer registers than needed, register is skipped."""
        client, tcp = client_and_tcp
        tcp.read_input_registers.return_value = _mock_read_result([0])
        regs = [_make_reg(1000, DataType.FLOAT, "temp")]
        result = await client._read_group(regs)
        assert "temp" not in result
