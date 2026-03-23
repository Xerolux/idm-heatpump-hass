"""Tests for IdmCoordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.idm_heatpump.coordinator import IdmCoordinator
from custom_components.idm_heatpump.modbus_client import DataType, RegisterDef
from custom_components.idm_heatpump.const import UNUSED_VALUE


def _make_coordinator(mock_hass, mock_config_entry, client=None, **kwargs):
    if client is None:
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={})
        client.write_register = AsyncMock()
    coord = IdmCoordinator(
        hass=mock_hass,
        config_entry=mock_config_entry,
        client=client,
        scan_interval=timedelta(seconds=10),
        sensor_descriptions=kwargs.get("sensor_descriptions", []),
        binary_sensor_descriptions=kwargs.get("binary_sensor_descriptions", []),
        number_descriptions=kwargs.get("number_descriptions", []),
        select_descriptions=kwargs.get("select_descriptions", []),
        switch_descriptions=kwargs.get("switch_descriptions", []),
        hide_unused=kwargs.get("hide_unused", True),
    )
    return coord, client


class TestCoordinatorInit:
    def test_properties_match_init(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(
            mock_hass, mock_config_entry,
            sensor_descriptions=[{"key": "s1"}],
            binary_sensor_descriptions=[{"key": "b1"}],
            number_descriptions=[{"key": "n1"}, {"key": "n2"}],
            select_descriptions=[],
            switch_descriptions=[{"key": "sw1"}],
            hide_unused=False,
        )
        assert len(coord.sensor_descriptions) == 1
        assert len(coord.binary_sensor_descriptions) == 1
        assert len(coord.number_descriptions) == 2
        assert len(coord.select_descriptions) == 0
        assert len(coord.switch_descriptions) == 1
        assert coord.hide_unused is False

    def test_update_interval(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.update_interval == timedelta(seconds=10)

    def test_client_stored(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        assert coord.client is client

    def test_config_entry_stored(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.config_entry is mock_config_entry


class TestSetupRegisters:
    def test_registers_count(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        with patch(
            "custom_components.idm_heatpump.coordinator.collect_all_registers",
            return_value=[MagicMock(), MagicMock(), MagicMock()],
        ):
            coord.setup_registers(["a"], 0, {})
        assert coord.registers_count == 3

    def test_empty_registers(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        with patch(
            "custom_components.idm_heatpump.coordinator.collect_all_registers",
            return_value=[],
        ):
            coord.setup_registers(["a"], 0, {})
        assert coord.registers_count == 0


class TestIsRegisterUnused:
    def test_unused_value_is_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", UNUSED_VALUE) is True

    def test_none_is_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", None) is True

    def test_normal_value_is_not_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", 20.0) is False

    def test_hide_unused_false_never_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=False)
        assert coord.is_register_unused("x", UNUSED_VALUE) is False
        assert coord.is_register_unused("x", None) is False

    def test_zero_is_not_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.is_register_unused("x", 0.0) is False

    def test_negative_one_is_unused(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        # UNUSED_VALUE is -1.0
        assert coord.is_register_unused("x", -1.0) is True


class TestAsyncUpdateData:
    async def test_successful_update(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 22.5, "mode": 1})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            data = await coord._async_update_data()

        assert data["temp"] == 22.5
        assert data["mode"] == 1
        mock_ir.async_delete_issue.assert_called_once()

    async def test_empty_data_raises_update_failed(self, mock_hass, mock_config_entry):
        from homeassistant.helpers.update_coordinator import UpdateFailed

        client = MagicMock()
        client.read_batch = AsyncMock(return_value={})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()

    async def test_exception_raises_update_failed(self, mock_hass, mock_config_entry):
        from homeassistant.helpers.update_coordinator import UpdateFailed

        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=Exception("connection lost"))
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()
        mock_ir.async_create_issue.assert_called_once()

    async def test_unused_registers_tracked(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"dead": UNUSED_VALUE, "alive": 5.0})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, hide_unused=True)

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
        assert "dead" in coord.unused_registers
        assert "alive" not in coord.unused_registers

    async def test_issue_deleted_on_success(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"temp": 20.0})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            await coord._async_update_data()
        mock_ir.async_delete_issue.assert_called_once_with(
            mock_hass, "idm_heatpump", "cannot_connect"
        )

    async def test_issue_created_on_failure(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=Exception("timeout"))
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)

        with patch("custom_components.idm_heatpump.coordinator.ir") as mock_ir:
            with pytest.raises(Exception):
                await coord._async_update_data()
        mock_ir.async_create_issue.assert_called_once()
        call_kwargs = mock_ir.async_create_issue.call_args
        assert call_kwargs is not None


class TestAsyncWriteRegister:
    async def test_write_updates_data_optimistically(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {"temp_set": 20.0}

        reg = RegisterDef(address=1000, datatype=DataType.FLOAT, name="temp_set", writable=True)
        await coord.async_write_register(reg, 22.0)

        assert coord.data["temp_set"] == 22.0
        client.write_register.assert_called_once_with(reg, 22.0)

    async def test_write_triggers_refresh(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {}
        coord.async_request_refresh = AsyncMock()

        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="mode", writable=True)
        await coord.async_write_register(reg, 1)

        coord.async_request_refresh.assert_called_once()

    async def test_write_no_data_initializes(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = None
        coord.async_request_refresh = AsyncMock()

        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="mode", writable=True)
        # Should not crash even if data is None
        await coord.async_write_register(reg, 1)
        coord.async_request_refresh.assert_called_once()

    async def test_write_calls_async_update_listeners(self, mock_hass, mock_config_entry):
        """async_update_listeners() is called on every write for optimistic updates."""
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {"val": 0}
        coord.async_request_refresh = AsyncMock()
        coord.async_update_listeners = MagicMock()

        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="val", writable=True)
        await coord.async_write_register(reg, 5)
        coord.async_update_listeners.assert_called_once()

    async def test_multiple_writes_update_data_and_listeners(self, mock_hass, mock_config_entry):
        """Multiple consecutive writes each update data and notify listeners."""
        client = MagicMock()
        client.write_register = AsyncMock()
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {"a": 0, "b": 0}
        coord.async_request_refresh = AsyncMock()
        coord.async_update_listeners = MagicMock()

        reg_a = RegisterDef(address=1000, datatype=DataType.UCHAR, name="a", writable=True)
        reg_b = RegisterDef(address=1001, datatype=DataType.UCHAR, name="b", writable=True)
        await coord.async_write_register(reg_a, 3)
        await coord.async_write_register(reg_b, 7)

        assert coord.data["a"] == 3
        assert coord.data["b"] == 7
        assert coord.async_update_listeners.call_count == 2

    async def test_write_failure_propagates(self, mock_hass, mock_config_entry):
        """If client.write_register raises, async_write_register propagates the exception."""
        client = MagicMock()
        client.write_register = AsyncMock(side_effect=Exception("write error"))
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        coord.data = {"x": 0}
        coord.async_request_refresh = AsyncMock()

        reg = RegisterDef(address=1000, datatype=DataType.UCHAR, name="x", writable=True)
        with pytest.raises(Exception, match="write error"):
            await coord.async_write_register(reg, 1)


class TestCoordinatorProperties:
    def test_client_property(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client)
        assert coord.client is client

    def test_hide_unused_property(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=True)
        assert coord.hide_unused is True
        coord2, _ = _make_coordinator(mock_hass, mock_config_entry, hide_unused=False)
        assert coord2.hide_unused is False

    def test_registers_count_initial_zero(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.registers_count == 0

    def test_unused_registers_initially_empty(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        assert coord.unused_registers == set()


class TestSetupRegistersWithCascade:
    def test_cascade_registers_included(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        with patch(
            "custom_components.idm_heatpump.coordinator.collect_all_registers",
            return_value=[MagicMock()],
        ) as mock_collect:
            coord.setup_registers(["a"], 0, {}, enable_cascade=True)
        mock_collect.assert_called_once_with(["a"], 0, {}, True)

    def test_cascade_false_by_default(self, mock_hass, mock_config_entry):
        coord, _ = _make_coordinator(mock_hass, mock_config_entry)
        with patch(
            "custom_components.idm_heatpump.coordinator.collect_all_registers",
            return_value=[],
        ) as mock_collect:
            coord.setup_registers(["a"], 0, {})
        # Default enable_cascade=False
        mock_collect.assert_called_once_with(["a"], 0, {}, False)


class TestUnusedRegistersAccumulation:
    async def test_unused_registers_accumulate_across_updates(self, mock_hass, mock_config_entry):
        """Unused registers from different updates accumulate in the set."""
        client = MagicMock()
        client.read_batch = AsyncMock(side_effect=[
            {"x": UNUSED_VALUE, "y": 5.0},
            {"x": UNUSED_VALUE, "z": UNUSED_VALUE},
        ])
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, hide_unused=True)

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
        assert "x" in coord.unused_registers
        assert "y" not in coord.unused_registers

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
        assert "z" in coord.unused_registers
        assert "x" in coord.unused_registers  # still there from first update

    async def test_unused_registers_not_tracked_when_hide_unused_false(self, mock_hass, mock_config_entry):
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={"x": UNUSED_VALUE, "y": 5.0})
        coord, _ = _make_coordinator(mock_hass, mock_config_entry, client=client, hide_unused=False)

        with patch("custom_components.idm_heatpump.coordinator.ir"):
            await coord._async_update_data()
        assert "x" not in coord.unused_registers
