"""Tests for IdmHeatpumpConfigFlow and IdmHeatpumpOptionsFlow."""

from unittest.mock import AsyncMock, MagicMock, patch


from custom_components.idm_heatpump.config_flow import (
    IdmHeatpumpConfigFlow,
    IdmHeatpumpOptionsFlow,
    _build_options_schema,
    _build_zones_schema,
    _has_duplicate_host,
)
from custom_components.idm_heatpump.const import (
    CONF_DETECTED_NAVIGATOR_VERSION,
    CONF_DETECTED_SOFTWARE_VERSION,
    CONF_HEATING_CIRCUITS,
    CONF_HIDE_UNUSED,
    CONF_MODBUS_MAX_RETRIES,
    CONF_MODBUS_PROXY,
    CONF_MODBUS_TIMEOUT,
    CONF_ROOM_TEMP_FORWARDING,
    CONF_ROOM_TEMP_FORWARDING_ENTITIES,
    CONF_ROOM_TEMP_FORWARDING_INTERVAL,
    CONF_ROOM_TEMP_FORWARDING_TOLERANCE,
    CONF_SCAN_INTERVAL,
    CONF_ZONE_COUNT,
    CONF_ZONE_ROOMS,
    CONF_TECHNICIAN_CODES,
    CONF_WEB_ENABLED,
    CONF_WEB_HOST,
    CONF_WEB_ONLY,
    CONF_WEB_PIN,
    CONF_WEB_SCAN_INTERVAL,
    DEFAULT_MODBUS_MAX_RETRIES,
    DEFAULT_MODBUS_TIMEOUT,
    DEFAULT_WEB_ENABLED,
)
from custom_components.idm_heatpump.web_data import IdmWebAuthenticationFailed


def _make_flow():
    flow = IdmHeatpumpConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config_entries.async_entries = MagicMock(return_value=[])
    return flow


def _make_entry(entry_id: str, host: str, port: int = 502, slave_id: int = 1):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {"host": host, "port": port, "slave_id": slave_id}
    entry.title = "IDM"
    return entry


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

    def test_web_supplement_enabled_by_default(self):
        schema = _build_options_schema({})
        defaults = {key.key: key.default for key in schema._schema}

        assert DEFAULT_WEB_ENABLED is True
        assert defaults[CONF_WEB_ENABLED] is True


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
        assert IdmHeatpumpConfigFlow.MINOR_VERSION == 2

    def test_duplicate_host_detection_ignores_port_and_slave_id(self):
        hass = MagicMock()
        hass.config_entries.async_entries = MagicMock(
            return_value=[_make_entry("entry-1", "192.168.1.100", port=502, slave_id=1)]
        )

        assert _has_duplicate_host(hass, " 192.168.1.100 ", current_entry_id=None)
        assert _has_duplicate_host(hass, "192.168.1.100", current_entry_id="other-entry")
        assert not _has_duplicate_host(hass, "192.168.1.100", current_entry_id="entry-1")
        hass.config_entries.async_entries.assert_called_with("idm_heatpump")


class TestAsyncStepUser:
    async def test_shows_form_without_input(self):
        flow = _make_flow()
        result = await flow.async_step_user(None)
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    async def test_empty_name_shows_error(self):
        flow = _make_flow()
        result = await flow.async_step_user(
            {
                "name": "",
                "host": "192.168.1.100",
                "port": 502,
            }
        )
        assert result["type"] == "form"
        assert "name" in result["errors"]

    async def test_empty_host_shows_error(self):
        flow = _make_flow()
        result = await flow.async_step_user(
            {
                "name": "IDM",
                "host": "",
                "port": 502,
            }
        )
        assert result["type"] == "form"
        assert "host" in result["errors"]

    async def test_connection_failure_shows_error(self):
        flow = _make_flow()
        with patch.object(flow, "_test_connection", return_value=False):
            result = await flow.async_step_user(
                {
                    "name": "IDM",
                    "host": "192.168.1.100",
                    "port": 502,
                    "slave_id": 1,
                }
            )
        assert result["type"] == "form"
        assert result["errors"].get("base") == "cannot_connect"

    async def test_duplicate_host_blocks_second_entry_even_with_different_port_or_slave(self):
        flow = _make_flow()
        flow.hass.config_entries.async_entries.return_value = [
            _make_entry("entry-1", "192.168.1.100", port=502, slave_id=1)
        ]

        with patch.object(flow, "_test_connection", return_value=True) as test_connection:
            result = await flow.async_step_user(
                {
                    "name": "IDM Duplicate",
                    "host": "192.168.1.100",
                    "port": 1502,
                    "slave_id": 2,
                }
            )

        assert result["type"] == "form"
        assert result["errors"]["host"] == "already_configured"
        test_connection.assert_not_awaited()

    async def test_successful_connection_goes_to_options(self):
        flow = _make_flow()
        flow._async_abort_entries_match = MagicMock()
        with patch.object(flow, "_test_connection", return_value=True):
            with patch.object(
                flow, "async_step_options", return_value={"type": "form", "step_id": "options", "errors": {}}
            ):
                result = await flow.async_step_user(
                    {
                        "name": "IDM Test",
                        "host": "192.168.1.100",
                        "port": 502,
                        "slave_id": 1,
                    }
                )
        assert result["step_id"] == "options"
        flow._async_abort_entries_match.assert_called_once_with({"host": "192.168.1.100", "port": 502, "slave_id": 1})

    async def test_successful_connection_stores_detected_web_metadata(self):
        flow = _make_flow()
        detected = {
            CONF_DETECTED_NAVIGATOR_VERSION: "Navigator 10",
            CONF_DETECTED_SOFTWARE_VERSION: "NAV10_20.23",
        }
        with patch.object(flow, "_test_connection", return_value=True):
            with patch.object(flow, "_async_detect_web_supplement", return_value=detected):
                with patch.object(
                    flow,
                    "async_step_options",
                    return_value={"type": "form", "step_id": "options", "errors": {}},
                ):
                    result = await flow.async_step_user(
                        {
                            "name": "IDM Test",
                            "host": "192.168.1.100",
                            "port": 502,
                            "slave_id": 1,
                            CONF_WEB_PIN: " 1234 ",
                        }
                    )

        assert result["step_id"] == "options"
        assert flow._data[CONF_WEB_PIN] == "1234"
        assert flow._data[CONF_DETECTED_NAVIGATOR_VERSION] == "Navigator 10"
        assert flow._data[CONF_DETECTED_SOFTWARE_VERSION] == "NAV10_20.23"

    async def test_successful_connection_uses_separate_web_host_for_detection(self):
        flow = _make_flow()
        flow._async_abort_entries_match = MagicMock()

        with (
            patch.object(flow, "_test_connection", return_value=True),
            patch.object(flow, "_async_detect_web_supplement", return_value={}) as detect_web,
            patch.object(
                flow,
                "async_step_options",
                return_value={"type": "form", "step_id": "options", "errors": {}},
            ),
        ):
            result = await flow.async_step_user(
                {
                    "name": "IDM Test",
                    "host": "192.168.178.196",
                    "port": 502,
                    "slave_id": 1,
                    CONF_WEB_PIN: "2634",
                    CONF_MODBUS_PROXY: True,
                    CONF_WEB_HOST: "192.168.178.103",
                }
            )

        assert result["step_id"] == "options"
        detect_web.assert_awaited_once_with("192.168.178.103", "2634", model_hint=None)
        assert flow._data[CONF_MODBUS_PROXY] is True
        assert flow._data[CONF_WEB_HOST] == "192.168.178.103"

    async def test_successful_connection_ignores_web_host_without_proxy_checkbox(self):
        flow = _make_flow()
        flow._async_abort_entries_match = MagicMock()

        with (
            patch.object(flow, "_test_connection", return_value=True),
            patch.object(flow, "_async_detect_web_supplement", return_value={}) as detect_web,
            patch.object(
                flow,
                "async_step_options",
                return_value={"type": "form", "step_id": "options", "errors": {}},
            ),
        ):
            await flow.async_step_user(
                {
                    "name": "IDM Test",
                    "host": "192.168.178.196",
                    "port": 502,
                    "slave_id": 1,
                    CONF_WEB_PIN: "2634",
                    CONF_MODBUS_PROXY: False,
                    CONF_WEB_HOST: "192.168.178.103",
                }
            )

        detect_web.assert_awaited_once_with("192.168.178.196", "2634")
        assert flow._data[CONF_MODBUS_PROXY] is False
        assert flow._data[CONF_WEB_HOST] == ""

    async def test_proxy_checkbox_requires_web_host_when_pin_is_set(self):
        flow = _make_flow()
        flow._async_abort_entries_match = MagicMock()

        with patch.object(flow, "_test_connection", return_value=True):
            result = await flow.async_step_user(
                {
                    "name": "IDM Test",
                    "host": "192.168.178.196",
                    "port": 502,
                    "slave_id": 1,
                    CONF_WEB_PIN: "2634",
                    CONF_MODBUS_PROXY: True,
                    CONF_WEB_HOST: "",
                }
            )

        assert result["type"] == "form"
        assert result["errors"][CONF_WEB_HOST] == "web_host_required"

    async def test_invalid_web_pin_shows_field_error(self):
        flow = _make_flow()
        with patch.object(flow, "_test_connection", return_value=True):
            with patch.object(
                flow,
                "_async_detect_web_supplement",
                side_effect=IdmWebAuthenticationFailed("bad pin"),
            ):
                result = await flow.async_step_user(
                    {
                        "name": "IDM Test",
                        "host": "192.168.1.100",
                        "port": 502,
                        "slave_id": 1,
                        CONF_WEB_PIN: "0000",
                    }
                )

        assert result["type"] == "form"
        assert result["errors"][CONF_WEB_PIN] == "invalid_web_pin"


class TestAsyncStepOptions:
    async def test_shows_form_without_input(self):
        flow = _make_flow()
        flow._data = {"name": "IDM"}
        result = await flow.async_step_options(None)
        assert result["type"] == "form"
        assert result["step_id"] == "options"

    def test_options_schema_exposes_modbus_timeout_and_retries(self):
        """Timeout/retries must be user-tunable in the options step."""
        schema = _build_options_schema({})
        schema_dict = dict(schema._schema)
        assert CONF_MODBUS_TIMEOUT in schema_dict
        assert CONF_MODBUS_MAX_RETRIES in schema_dict

    def test_options_schema_applies_defaults_for_timeout_and_retries(self):
        schema = _build_options_schema({})
        # The dict keys are _Required markers; extract their defaults by key name.
        markers = {marker.key: marker for marker in schema._schema.keys()}
        assert markers[CONF_MODBUS_TIMEOUT].default == DEFAULT_MODBUS_TIMEOUT
        assert markers[CONF_MODBUS_MAX_RETRIES].default == DEFAULT_MODBUS_MAX_RETRIES

    async def test_no_zones_creates_entry(self):
        flow = _make_flow()
        flow._data = {"name": "IDM Test", "host": "192.168.1.100"}
        result = await flow.async_step_options(
            {
                CONF_SCAN_INTERVAL: 10,
                CONF_HIDE_UNUSED: True,
                CONF_HEATING_CIRCUITS: ["a"],
                CONF_ZONE_COUNT: 0,
                CONF_TECHNICIAN_CODES: False,
            }
        )
        assert result["type"] == "create_entry"
        assert result["title"] == "IDM Test"
        assert result["options"][CONF_ROOM_TEMP_FORWARDING_ENTITIES] == {}

    async def test_room_temp_forwarding_goes_to_sensor_mapping_step(self):
        flow = _make_flow()
        flow._data = {"name": "IDM Test", "host": "192.168.1.100"}
        result = await flow.async_step_options(
            {
                CONF_SCAN_INTERVAL: 10,
                CONF_HIDE_UNUSED: True,
                CONF_HEATING_CIRCUITS: ["a", "b"],
                CONF_ZONE_COUNT: 0,
                CONF_TECHNICIAN_CODES: False,
                CONF_WEB_ENABLED: True,
                CONF_WEB_SCAN_INTERVAL: 30,
                CONF_ROOM_TEMP_FORWARDING: True,
                CONF_ROOM_TEMP_FORWARDING_INTERVAL: 300,
                CONF_ROOM_TEMP_FORWARDING_TOLERANCE: 0.2,
            }
        )
        assert result["type"] == "form"
        assert result["step_id"] == "room_temp_forwarding"

        result = await flow.async_step_room_temp_forwarding(
            {
                "room_temp_forwarding_a": "sensor.living_room_temperature",
                "room_temp_forwarding_b": "",
            }
        )
        assert result["type"] == "create_entry"
        assert result["options"][CONF_ROOM_TEMP_FORWARDING_ENTITIES] == {
            "a": "sensor.living_room_temperature",
        }

    async def test_with_zones_goes_to_zones_step(self):
        flow = _make_flow()
        flow._data = {"name": "IDM Test", "host": "192.168.1.100"}
        with patch.object(flow, "async_step_zones", return_value={"type": "form", "step_id": "zones", "errors": {}}):
            result = await flow.async_step_options(
                {
                    CONF_SCAN_INTERVAL: 10,
                    CONF_HIDE_UNUSED: True,
                    CONF_HEATING_CIRCUITS: ["a"],
                    CONF_ZONE_COUNT: 2,
                    CONF_TECHNICIAN_CODES: False,
                }
            )
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
        result = await flow.async_step_zones(
            {
                "zone_0_rooms": 3,
                "zone_1_rooms": 4,
            }
        )
        assert result["type"] == "create_entry"
        assert result["options"][CONF_ZONE_ROOMS] == {0: 3, 1: 4}

    async def test_zones_then_room_temp_forwarding_step(self):
        flow = _make_flow()
        flow._data = {"name": "IDM Test", "host": "192.168.1.100"}
        flow._options = {
            CONF_SCAN_INTERVAL: 10,
            CONF_HEATING_CIRCUITS: ["a"],
            CONF_ZONE_COUNT: 1,
            CONF_ROOM_TEMP_FORWARDING: True,
        }
        result = await flow.async_step_zones({"zone_0_rooms": 3})
        assert result["type"] == "form"
        assert result["step_id"] == "room_temp_forwarding"
        assert flow._options[CONF_ZONE_ROOMS] == {0: 3}


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
            result = await flow.async_step_reconfigure(
                {
                    "host": "",
                    "port": 502,
                }
            )
        assert result["type"] == "form"
        assert "host" in result["errors"]

    async def test_duplicate_host_blocks_reconfigure_to_other_entry_host(self):
        flow = _make_flow()
        entry = _make_entry("entry-1", "192.168.1.100")
        flow.hass.config_entries.async_entries.return_value = [
            entry,
            _make_entry("entry-2", "192.168.1.101"),
        ]

        with (
            patch.object(flow, "_get_reconfigure_entry", return_value=entry),
            patch.object(flow, "_test_connection", return_value=True) as test_connection,
        ):
            result = await flow.async_step_reconfigure(
                {
                    "host": "192.168.1.101",
                    "port": 1502,
                    "slave_id": 2,
                }
            )

        assert result["type"] == "form"
        assert result["errors"]["host"] == "already_configured"
        test_connection.assert_not_awaited()

    async def test_connection_failure_shows_error(self):
        flow = _make_flow()
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 1}
        entry.title = "IDM"
        with patch.object(flow, "_get_reconfigure_entry", return_value=entry):
            with patch.object(flow, "_test_connection", return_value=False):
                result = await flow.async_step_reconfigure(
                    {
                        "host": "10.0.0.1",
                        "port": 502,
                    }
                )
        assert result["errors"].get("base") == "cannot_connect"

    async def test_reconfigure_modbus_failure_with_web_pin_offers_web_only_without_duplicate_entry(self):
        flow = _make_flow()
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 1}
        entry.title = "IDM"
        update_and_abort = MagicMock(return_value={"type": "abort", "reason": "reconfigure_successful"})

        with (
            patch.object(flow, "_get_reconfigure_entry", return_value=entry),
            patch.object(flow, "_test_connection", return_value=False),
            patch.object(flow, "_async_detect_web_supplement", return_value={}),
            patch.object(flow, "async_update_and_abort", update_and_abort),
        ):
            result = await flow.async_step_reconfigure(
                {
                    "host": "10.0.0.1",
                    "port": 502,
                    "slave_id": 1,
                    CONF_WEB_PIN: "1234",
                }
            )
            assert result["type"] == "form"
            assert result["step_id"] == "modbus_failed"

            result = await flow.async_step_modbus_failed({"action": "web_only"})
            assert result["type"] == "form"
            assert result["step_id"] == "web_only_options"

            result = await flow.async_step_web_only_options({CONF_WEB_SCAN_INTERVAL: 60})

        assert result == {"type": "abort", "reason": "reconfigure_successful"}
        update_and_abort.assert_called_once()
        assert update_and_abort.call_args.args[0] is entry
        assert update_and_abort.call_args.kwargs["data_updates"][CONF_WEB_ONLY] is True

    async def test_successful_reconfigure(self):
        flow = _make_flow()
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 1}
        entry.title = "IDM"
        with patch.object(flow, "_get_reconfigure_entry", return_value=entry):
            with patch.object(flow, "_test_connection", return_value=True):
                result = await flow.async_step_reconfigure(
                    {
                        "host": "10.0.0.1",
                        "port": 502,
                        "slave_id": 1,
                    }
                )
        assert result["type"] in ("abort", "create_entry")

    async def test_successful_reconfigure_updates_network_fields(self):
        flow = _make_flow()
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 1}
        entry.title = "IDM"
        update_and_abort = MagicMock(return_value={"type": "abort", "reason": "reconfigure_successful"})

        with (
            patch.object(flow, "_get_reconfigure_entry", return_value=entry),
            patch.object(flow, "_test_connection", return_value=True) as test_connection,
            patch.object(flow, "async_update_and_abort", update_and_abort),
        ):
            result = await flow.async_step_reconfigure(
                {
                    "host": "idm.local",
                    "port": 5020,
                    "slave_id": 2,
                }
            )

        assert result == {"type": "abort", "reason": "reconfigure_successful"}
        test_connection.assert_awaited_once_with(
            {
                "host": "idm.local",
                "port": 5020,
                "slave_id": 2,
            }
        )
        update_and_abort.assert_called_once_with(
            entry,
            data_updates={
                "host": "idm.local",
                "port": 5020,
                "slave_id": 2,
                "web_pin": "",
                "modbus_proxy": False,
                "web_host": "",
            },
        )

    async def test_reconfigure_defaults_missing_slave_id(self):
        flow = _make_flow()
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 7}
        entry.title = "IDM"
        update_and_abort = MagicMock(return_value={"type": "abort", "reason": "reconfigure_successful"})

        with (
            patch.object(flow, "_get_reconfigure_entry", return_value=entry),
            patch.object(flow, "_test_connection", return_value=True),
            patch.object(flow, "async_update_and_abort", update_and_abort),
        ):
            await flow.async_step_reconfigure(
                {
                    "host": "idm.local",
                    "port": 5020,
                }
            )

        update_and_abort.assert_called_once_with(
            entry,
            data_updates={
                "host": "idm.local",
                "port": 5020,
                "slave_id": 1,
                "web_pin": "",
                "modbus_proxy": False,
                "web_host": "",
            },
        )

    async def test_reconfigure_updates_separate_web_host(self):
        flow = _make_flow()
        entry = MagicMock()
        entry.data = {"host": "192.168.178.196", "port": 502, "slave_id": 1, "web_pin": "2634"}
        entry.title = "IDM"
        update_and_abort = MagicMock(return_value={"type": "abort", "reason": "reconfigure_successful"})

        with (
            patch.object(flow, "_get_reconfigure_entry", return_value=entry),
            patch.object(flow, "_test_connection", return_value=True),
            patch.object(flow, "_async_detect_web_supplement", return_value={}) as detect_web,
            patch.object(flow, "async_update_and_abort", update_and_abort),
        ):
            await flow.async_step_reconfigure(
                {
                    "host": "192.168.178.196",
                    "port": 502,
                    "slave_id": 1,
                    CONF_WEB_PIN: "2634",
                    CONF_MODBUS_PROXY: True,
                    CONF_WEB_HOST: "192.168.178.103",
                }
            )

        detect_web.assert_awaited_once_with("192.168.178.103", "2634")
        update_and_abort.assert_called_once_with(
            entry,
            data_updates={
                "host": "192.168.178.196",
                "port": 502,
                "slave_id": 1,
                "web_pin": "2634",
                "modbus_proxy": True,
                "web_host": "192.168.178.103",
            },
        )

    async def test_reconfigure_invalid_web_pin_shows_field_error(self):
        flow = _make_flow()
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 1}
        entry.title = "IDM"

        with (
            patch.object(flow, "_get_reconfigure_entry", return_value=entry),
            patch.object(flow, "_test_connection", return_value=True),
            patch.object(
                flow,
                "_async_detect_web_supplement",
                side_effect=IdmWebAuthenticationFailed("bad pin"),
            ),
        ):
            result = await flow.async_step_reconfigure(
                {
                    "host": "idm.local",
                    "port": 502,
                    "slave_id": 1,
                    CONF_WEB_PIN: "0000",
                }
            )

        assert result["type"] == "form"
        assert result["errors"][CONF_WEB_PIN] == "invalid_web_pin"


class TestTestConnection:
    async def test_returns_true_on_success(self):
        flow = _make_flow()
        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_client.probe_register = AsyncMock(return_value=[0, 0])
        with patch(
            "idm_heatpump.IdmModbusClient",
            return_value=mock_client,
        ):
            result = await flow._test_connection(
                {
                    "host": "192.168.1.100",
                    "port": 502,
                    "slave_id": 1,
                }
            )
        assert result is True

    async def test_returns_false_on_exception(self):
        flow = _make_flow()
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=Exception("connection refused"))
        with patch(
            "idm_heatpump.IdmModbusClient",
            return_value=mock_client,
        ):
            result = await flow._test_connection(
                {
                    "host": "192.168.1.100",
                    "port": 502,
                    "slave_id": 1,
                }
            )
        assert result is False

    async def test_returns_false_on_test_failure(self):
        flow = _make_flow()
        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_client.probe_register = AsyncMock(return_value=None)
        with patch(
            "idm_heatpump.IdmModbusClient",
            return_value=mock_client,
        ):
            result = await flow._test_connection(
                {
                    "host": "192.168.1.100",
                    "port": 502,
                    "slave_id": 1,
                }
            )
        assert result is False

    async def test_disconnects_after_success(self):
        flow = _make_flow()
        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_client.probe_register = AsyncMock(return_value=[0, 0])
        with patch(
            "idm_heatpump.IdmModbusClient",
            return_value=mock_client,
        ):
            await flow._test_connection(
                {
                    "host": "192.168.1.100",
                    "port": 502,
                    "slave_id": 1,
                }
            )
        mock_client.disconnect.assert_awaited_once()

    async def test_disconnects_after_exception(self):
        flow = _make_flow()
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=Exception("connection refused"))
        with patch(
            "idm_heatpump.IdmModbusClient",
            return_value=mock_client,
        ):
            await flow._test_connection(
                {
                    "host": "192.168.1.100",
                    "port": 502,
                    "slave_id": 1,
                }
            )
        mock_client.disconnect.assert_awaited_once()


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
        result = await flow.async_step_options(
            {
                CONF_SCAN_INTERVAL: 15,
                CONF_HIDE_UNUSED: True,
                CONF_HEATING_CIRCUITS: ["a"],
                CONF_ZONE_COUNT: 0,
                CONF_TECHNICIAN_CODES: False,
            }
        )
        assert result["type"] == "create_entry"

    async def test_step_options_with_zones_goes_to_zones(self):
        flow = IdmHeatpumpOptionsFlow()
        flow.config_entry = MagicMock()
        flow.config_entry.options = {}
        flow._options = {}
        with patch.object(flow, "async_step_zones", return_value={"type": "form", "step_id": "zones", "errors": {}}):
            result = await flow.async_step_options(
                {
                    CONF_SCAN_INTERVAL: 15,
                    CONF_HIDE_UNUSED: True,
                    CONF_HEATING_CIRCUITS: ["a"],
                    CONF_ZONE_COUNT: 1,
                    CONF_TECHNICIAN_CODES: False,
                }
            )
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


class TestConfigFlowZoneBoundaries:
    async def test_max_zones_accepted(self):
        """zone_count=10 with 10 rooms each should not error."""
        flow = _make_flow()
        flow._data = {"name": "IDM Test", "host": "192.168.1.100"}
        flow._options = {
            CONF_SCAN_INTERVAL: 10,
            CONF_HEATING_CIRCUITS: ["a"],
            CONF_ZONE_COUNT: 10,
        }
        zone_input = {f"zone_{i}_rooms": 8 for i in range(10)}
        result = await flow.async_step_zones(zone_input)
        assert result["type"] == "create_entry"
        zone_rooms = result["options"][CONF_ZONE_ROOMS]
        assert zone_rooms == {i: 8 for i in range(10)}

    async def test_zone_count_zero_skips_zones_step(self):
        """zone_count=0 creates entry directly from options step."""
        flow = _make_flow()
        flow._data = {"name": "IDM", "host": "10.0.0.1"}
        result = await flow.async_step_options(
            {
                CONF_SCAN_INTERVAL: 10,
                CONF_HIDE_UNUSED: True,
                CONF_HEATING_CIRCUITS: ["a"],
                CONF_ZONE_COUNT: 0,
                CONF_TECHNICIAN_CODES: False,
            }
        )
        assert result["type"] == "create_entry"

    async def test_all_seven_heating_circuits(self):
        """Selecting all 7 circuits proceeds to entry creation."""
        flow = _make_flow()
        flow._data = {"name": "IDM", "host": "10.0.0.1"}
        result = await flow.async_step_options(
            {
                CONF_SCAN_INTERVAL: 10,
                CONF_HIDE_UNUSED: True,
                CONF_HEATING_CIRCUITS: ["a", "b", "c", "d", "e", "f", "g"],
                CONF_ZONE_COUNT: 0,
                CONF_TECHNICIAN_CODES: False,
            }
        )
        assert result["type"] == "create_entry"
        assert result["options"][CONF_HEATING_CIRCUITS] == ["a", "b", "c", "d", "e", "f", "g"]

    async def test_zone_rooms_stored_correctly(self):
        flow = _make_flow()
        flow._data = {"name": "IDM", "host": "10.0.0.1"}
        flow._options = {
            CONF_SCAN_INTERVAL: 10,
            CONF_HEATING_CIRCUITS: ["a"],
            CONF_ZONE_COUNT: 3,
        }
        result = await flow.async_step_zones(
            {
                "zone_0_rooms": 1,
                "zone_1_rooms": 4,
                "zone_2_rooms": 8,
            }
        )
        assert result["type"] == "create_entry"
        assert result["options"][CONF_ZONE_ROOMS] == {0: 1, 1: 4, 2: 8}


class TestConfigFlowFullFlow:
    async def test_user_to_options_to_create_entry(self):
        """Full happy path: user step → options step → create_entry."""
        flow = _make_flow()
        # Step 1: user
        with patch.object(flow, "_test_connection", return_value=True):
            step1 = await flow.async_step_user(
                {
                    "name": "IDM Heat",
                    "host": "192.168.1.100",
                    "port": 502,
                    "slave_id": 1,
                }
            )
        assert step1["type"] == "form"
        assert step1["step_id"] == "options"

        # Step 2: options (no zones)
        step2 = await flow.async_step_options(
            {
                CONF_SCAN_INTERVAL: 10,
                CONF_HIDE_UNUSED: True,
                CONF_HEATING_CIRCUITS: ["a"],
                CONF_ZONE_COUNT: 0,
                CONF_TECHNICIAN_CODES: False,
            }
        )
        assert step2["type"] == "create_entry"
        assert step2["title"] == "IDM Heat"

    async def test_user_to_options_to_zones_to_create_entry(self):
        """Full happy path with zones: user → options → zones → create_entry."""
        flow = _make_flow()
        with patch.object(flow, "_test_connection", return_value=True):
            await flow.async_step_user(
                {
                    "name": "IDM Zone",
                    "host": "192.168.1.200",
                    "port": 502,
                    "slave_id": 1,
                }
            )

        step2 = await flow.async_step_options(
            {
                CONF_SCAN_INTERVAL: 10,
                CONF_HIDE_UNUSED: False,
                CONF_HEATING_CIRCUITS: ["a"],
                CONF_ZONE_COUNT: 2,
                CONF_TECHNICIAN_CODES: False,
            }
        )
        assert step2["type"] == "form"
        assert step2["step_id"] == "zones"

        step3 = await flow.async_step_zones(
            {
                "zone_0_rooms": 3,
                "zone_1_rooms": 5,
            }
        )
        assert step3["type"] == "create_entry"
        assert step3["options"][CONF_ZONE_ROOMS] == {0: 3, 1: 5}
        assert step3["options"][CONF_ZONE_COUNT] == 2


class TestOptionsFlowFull:
    async def test_options_change_scan_interval(self):
        flow = IdmHeatpumpOptionsFlow()
        flow.config_entry = MagicMock()
        flow.config_entry.options = {
            CONF_SCAN_INTERVAL: 10,
            CONF_HEATING_CIRCUITS: ["a"],
            CONF_ZONE_COUNT: 0,
        }
        result = await flow.async_step_options(
            {
                CONF_SCAN_INTERVAL: 30,
                CONF_HIDE_UNUSED: False,
                CONF_HEATING_CIRCUITS: ["a"],
                CONF_ZONE_COUNT: 0,
                CONF_TECHNICIAN_CODES: True,
            }
        )
        assert result["type"] == "create_entry"
        assert result["data"][CONF_SCAN_INTERVAL] == 30
        assert result["data"][CONF_TECHNICIAN_CODES] is True
        assert result["data"][CONF_ROOM_TEMP_FORWARDING_ENTITIES] == {}

    async def test_options_defaults_loaded_from_entry(self):
        """async_step_init loads existing options as defaults."""
        flow = IdmHeatpumpOptionsFlow()
        flow.config_entry = MagicMock()
        flow.config_entry.options = {
            CONF_SCAN_INTERVAL: 25,
            CONF_HEATING_CIRCUITS: ["a", "b"],
            CONF_ZONE_COUNT: 1,
            CONF_HIDE_UNUSED: False,
        }
        result = await flow.async_step_init(None)
        # Should re-display form with existing options pre-filled
        assert result["type"] == "form"
        assert result["step_id"] == "options"
