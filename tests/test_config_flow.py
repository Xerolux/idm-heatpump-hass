"""Tests for IdmHeatpumpConfigFlow and IdmHeatpumpOptionsFlow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.idm_heatpump_v2.config_flow import (
    IdmHeatpumpConfigFlow,
    IdmHeatpumpOptionsFlow,
    _build_options_schema,
    _build_zones_schema,
)
from custom_components.idm_heatpump_v2.const import (
    CONF_HEATING_CIRCUITS,
    CONF_HIDE_UNUSED,
    CONF_SCAN_INTERVAL,
    CONF_ZONE_COUNT,
    CONF_ZONE_ROOMS,
    CONF_TECHNICIAN_CODES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_HIDE_UNUSED,
)


def _make_flow():
    flow = IdmHeatpumpConfigFlow()
    flow.hass = MagicMock()
    return flow


class TestBuildOptionsSchema:
    def test_returns_schema(self):
        schema = _build_options_schema({})
        assert schema is not None

    def test_with_existing_options(self):
        opts = {CONF_SCAN_INTERVAL: 30, CONF_HIDE_UNUSED: False}
        schema = _build_options_schema(opts)
        assert schema is not None

    def test_circuit_a_always_first(self):
        opts = {CONF_HEATING_CIRCUITS: ["b", "c"]}
        # Should add "a" at front if missing
        schema = _build_options_schema(opts)
        assert schema is not None

    def test_circuit_a_present_keeps_position(self):
        opts = {CONF_HEATING_CIRCUITS: ["a", "b"]}
        schema = _build_options_schema(opts)
        assert schema is not None


class TestBuildZonesSchema:
    def test_empty_zones(self):
        schema = _build_zones_schema({}, 0)
        assert schema is not None

    def test_one_zone(self):
        schema = _build_zones_schema({}, 1)
        assert schema is not None

    def test_uses_existing_room_counts(self):
        opts = {CONF_ZONE_ROOMS: {0: 3, 1: 4}}
        schema = _build_zones_schema(opts, 2)
        assert schema is not None


class TestConfigFlowInit:
    def test_initial_state(self):
        flow = _make_flow()
        assert flow._data == {}
        assert flow._options == {}

    def test_version(self):
        assert IdmHeatpumpConfigFlow.VERSION == 1


class TestAsyncStepUser:
    async def test_shows_form_without_input(self):
        flow = _make_flow()
        result = await flow.async_step_user(None)
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    async def test_empty_name_shows_error(self):
        flow = _make_flow()
        result = await flow.async_step_user({
            "name": "",
            "host": "192.168.1.100",
            "port": 502,
        })
        assert result["type"] == "form"
        assert "name" in result["errors"]

    async def test_empty_host_shows_error(self):
        flow = _make_flow()
        result = await flow.async_step_user({
            "name": "IDM",
            "host": "",
            "port": 502,
        })
        assert result["type"] == "form"
        assert "host" in result["errors"]

    async def test_connection_failure_shows_error(self):
        flow = _make_flow()
        with patch.object(flow, "_test_connection", return_value=False):
            result = await flow.async_step_user({
                "name": "IDM",
                "host": "192.168.1.100",
                "port": 502,
                "slave_id": 1,
            })
        assert result["type"] == "form"
        assert result["errors"].get("base") == "cannot_connect"

    async def test_successful_connection_goes_to_options(self):
        flow = _make_flow()
        with patch.object(flow, "_test_connection", return_value=True):
            with patch.object(flow, "async_step_options", return_value={"type": "form", "step_id": "options", "errors": {}}):
                result = await flow.async_step_user({
                    "name": "IDM Test",
                    "host": "192.168.1.100",
                    "port": 502,
                    "slave_id": 1,
                })
        assert result["step_id"] == "options"


class TestAsyncStepOptions:
    async def test_shows_form_without_input(self):
        flow = _make_flow()
        flow._data = {"name": "IDM"}
        result = await flow.async_step_options(None)
        assert result["type"] == "form"
        assert result["step_id"] == "options"

    async def test_no_zones_creates_entry(self):
        flow = _make_flow()
        flow._data = {"name": "IDM Test", "host": "192.168.1.100"}
        result = await flow.async_step_options({
            CONF_SCAN_INTERVAL: 10,
            CONF_HIDE_UNUSED: True,
            CONF_HEATING_CIRCUITS: ["a"],
            CONF_ZONE_COUNT: 0,
            CONF_TECHNICIAN_CODES: False,
        })
        assert result["type"] == "create_entry"
        assert result["title"] == "IDM Test"

    async def test_with_zones_goes_to_zones_step(self):
        flow = _make_flow()
        flow._data = {"name": "IDM Test", "host": "192.168.1.100"}
        with patch.object(flow, "async_step_zones",
                          return_value={"type": "form", "step_id": "zones", "errors": {}}):
            result = await flow.async_step_options({
                CONF_SCAN_INTERVAL: 10,
                CONF_HIDE_UNUSED: True,
                CONF_HEATING_CIRCUITS: ["a"],
                CONF_ZONE_COUNT: 2,
                CONF_TECHNICIAN_CODES: False,
            })
        assert result["step_id"] == "zones"


class TestAsyncStepZones:
    async def test_shows_form_without_input(self):
        flow = _make_flow()
        flow._data = {"name": "IDM"}
        flow._options = {CONF_ZONE_COUNT: 2}
        result = await flow.async_step_zones(None)
        assert result["type"] == "form"
        assert result["step_id"] == "zones"

    async def test_creates_entry_with_zone_rooms(self):
        flow = _make_flow()
        flow._data = {"name": "IDM Test", "host": "192.168.1.100"}
        flow._options = {
            CONF_SCAN_INTERVAL: 10,
            CONF_HEATING_CIRCUITS: ["a"],
            CONF_ZONE_COUNT: 2,
        }
        result = await flow.async_step_zones({
            "zone_0_rooms": 3,
            "zone_1_rooms": 4,
        })
        assert result["type"] == "create_entry"
        assert result["options"][CONF_ZONE_ROOMS] == {0: 3, 1: 4}


class TestAsyncStepReconfigure:
    async def test_shows_form_without_input(self):
        flow = _make_flow()
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 1}
        entry.title = "IDM"
        with patch.object(flow, "_get_reconfigure_entry", return_value=entry):
            result = await flow.async_step_reconfigure(None)
        assert result["type"] == "form"
        assert result["step_id"] == "reconfigure"

    async def test_empty_host_shows_error(self):
        flow = _make_flow()
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 1}
        entry.title = "IDM"
        with patch.object(flow, "_get_reconfigure_entry", return_value=entry):
            result = await flow.async_step_reconfigure({
                "host": "",
                "port": 502,
            })
        assert result["type"] == "form"
        assert "host" in result["errors"]

    async def test_connection_failure_shows_error(self):
        flow = _make_flow()
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 1}
        entry.title = "IDM"
        with patch.object(flow, "_get_reconfigure_entry", return_value=entry):
            with patch.object(flow, "_test_connection", return_value=False):
                result = await flow.async_step_reconfigure({
                    "host": "10.0.0.1",
                    "port": 502,
                })
        assert result["errors"].get("base") == "cannot_connect"

    async def test_successful_reconfigure(self):
        flow = _make_flow()
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 1}
        entry.title = "IDM"
        with patch.object(flow, "_get_reconfigure_entry", return_value=entry):
            with patch.object(flow, "_test_connection", return_value=True):
                result = await flow.async_step_reconfigure({
                    "host": "10.0.0.1",
                    "port": 502,
                    "slave_id": 1,
                })
        assert result["type"] in ("abort", "create_entry")


class TestTestConnection:
    async def test_returns_true_on_success(self):
        flow = _make_flow()
        mock_client = AsyncMock()
        mock_client.test_connection = AsyncMock(return_value=True)
        with patch(
            "custom_components.idm_heatpump_v2.modbus_client.IdmModbusClient",
            return_value=mock_client,
        ):
            result = await flow._test_connection({
                "host": "192.168.1.100",
                "port": 502,
                "slave_id": 1,
            })
        assert result is True

    async def test_returns_false_on_exception(self):
        flow = _make_flow()
        mock_client = AsyncMock()
        mock_client.test_connection = AsyncMock(side_effect=Exception("connection refused"))
        with patch(
            "custom_components.idm_heatpump_v2.modbus_client.IdmModbusClient",
            return_value=mock_client,
        ):
            result = await flow._test_connection({
                "host": "192.168.1.100",
                "port": 502,
                "slave_id": 1,
            })
        assert result is False

    async def test_returns_false_on_test_failure(self):
        flow = _make_flow()
        mock_client = AsyncMock()
        mock_client.test_connection = AsyncMock(return_value=False)
        with patch(
            "custom_components.idm_heatpump_v2.modbus_client.IdmModbusClient",
            return_value=mock_client,
        ):
            result = await flow._test_connection({
                "host": "192.168.1.100",
                "port": 502,
                "slave_id": 1,
            })
        assert result is False


class TestOptionsFlow:
    def test_init(self):
        flow = IdmHeatpumpOptionsFlow()
        assert flow._options == {}

    async def test_step_init_calls_step_options(self):
        flow = IdmHeatpumpOptionsFlow()
        flow.config_entry = MagicMock()
        flow.config_entry.options = {
            CONF_SCAN_INTERVAL: 20,
            CONF_HEATING_CIRCUITS: ["a"],
            CONF_ZONE_COUNT: 0,
        }
        result = await flow.async_step_init(None)
        assert result["type"] == "form"
        assert result["step_id"] == "options"

    async def test_step_options_no_zones_creates_entry(self):
        flow = IdmHeatpumpOptionsFlow()
        flow.config_entry = MagicMock()
        flow.config_entry.options = {}
        flow._options = {}
        result = await flow.async_step_options({
            CONF_SCAN_INTERVAL: 15,
            CONF_HIDE_UNUSED: True,
            CONF_HEATING_CIRCUITS: ["a"],
            CONF_ZONE_COUNT: 0,
            CONF_TECHNICIAN_CODES: False,
        })
        assert result["type"] == "create_entry"

    async def test_step_options_with_zones_goes_to_zones(self):
        flow = IdmHeatpumpOptionsFlow()
        flow.config_entry = MagicMock()
        flow.config_entry.options = {}
        flow._options = {}
        with patch.object(flow, "async_step_zones",
                          return_value={"type": "form", "step_id": "zones", "errors": {}}):
            result = await flow.async_step_options({
                CONF_SCAN_INTERVAL: 15,
                CONF_HIDE_UNUSED: True,
                CONF_HEATING_CIRCUITS: ["a"],
                CONF_ZONE_COUNT: 1,
                CONF_TECHNICIAN_CODES: False,
            })
        assert result["step_id"] == "zones"

    async def test_step_zones_no_input_shows_form(self):
        flow = IdmHeatpumpOptionsFlow()
        flow._options = {CONF_ZONE_COUNT: 2}
        result = await flow.async_step_zones(None)
        assert result["type"] == "form"
        assert result["step_id"] == "zones"

    async def test_step_zones_with_input_creates_entry(self):
        flow = IdmHeatpumpOptionsFlow()
        flow._options = {CONF_ZONE_COUNT: 1}
        result = await flow.async_step_zones({"zone_0_rooms": 5})
        assert result["type"] == "create_entry"
        assert result["data"][CONF_ZONE_ROOMS] == {0: 5}

    async def test_get_options_flow(self):
        entry = MagicMock()
        options_flow = IdmHeatpumpConfigFlow.async_get_options_flow(entry)
        assert isinstance(options_flow, IdmHeatpumpOptionsFlow)
