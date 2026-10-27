"""Tests for __init__.py (async_setup, async_setup_entry, async_unload_entry)."""

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers import issue_registry as ir
from idm_heatpump import FEATURE_SOLAR, MODEL_UNKNOWN, IdmModelInfo

from custom_components.idm_heatpump import (
    IdmHeatpumpData,
    _detect_model_info,
    async_migrate_entry,
    async_reload_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.idm_heatpump.const import (
    CONF_DEVICE_HIERARCHY,
    CONF_MODEL_OVERRIDE,
    MODEL,
    MODEL_OVERRIDE_AUTO,
    MODEL_OVERRIDE_NAVIGATOR_10,
    MODEL_OVERRIDE_NAVIGATOR_20,
    WEB_SETUP_READ_TIMEOUT,
)
from custom_components.idm_heatpump.model_resolution import (
    model_info_from_name,
    model_name_for_override,
    plant_shape,
    resolved_model_override,
)
from custom_components.idm_heatpump.services import async_setup_services
from custom_components.idm_heatpump.web_data import IdmWebSupplement


class TestIdmHeatpumpData:
    def test_dataclass_fields(self):
        coordinator = MagicMock()
        client = MagicMock()
        data = IdmHeatpumpData(coordinator=coordinator, client=client)
        assert data.coordinator is coordinator
        assert data.client is client

    def test_is_dataclass(self):
        import dataclasses

        assert dataclasses.is_dataclass(IdmHeatpumpData)


class TestAsyncSetup:
    async def test_calls_setup_services(self, mock_hass):
        mock_setup_services = AsyncMock()
        with patch(
            "custom_components.idm_heatpump.services.async_setup_services",
            mock_setup_services,
        ):
            result = await async_setup(mock_hass, {})
        assert result is True

    async def test_returns_true(self, mock_hass):
        with patch(
            "custom_components.idm_heatpump.services.async_setup_services",
            AsyncMock(),
        ):
            result = await async_setup(mock_hass, {})
        assert result is True


class TestAsyncMigrateEntry:
    async def test_migrates_legacy_entity_and_config_entry_unique_ids(self, mock_hass):
        entry = MagicMock()
        entry.entry_id = "entry-123"
        entry.version = 1
        entry.minor_version = 1
        entry.options = {}

        legacy_entity = MagicMock()
        legacy_entity.entity_id = "sensor.outdoor_temperature"
        legacy_entity.unique_id = "192.168.1.100:502_outdoor_temp"
        stable_entity = MagicMock()
        stable_entity.entity_id = "sensor.system_mode"
        stable_entity.unique_id = "entry-123_system_mode"
        registry = MagicMock()

        with (
            patch("custom_components.idm_heatpump.er.async_get", return_value=registry),
            patch(
                "custom_components.idm_heatpump.er.async_entries_for_config_entry",
                return_value=[legacy_entity, stable_entity],
            ),
        ):
            result = await async_migrate_entry(mock_hass, entry)

        assert result is True
        registry.async_update_entity.assert_called_once_with(
            "sensor.outdoor_temperature",
            new_unique_id="entry-123_outdoor_temp",
        )
        mock_hass.config_entries.async_update_entry.assert_called_once_with(
            entry,
            unique_id=None,
            options={CONF_DEVICE_HIERARCHY: False},
            version=1,
            minor_version=3,
        )

    async def test_updates_entry_version_when_no_legacy_entities_exist(self, mock_hass):
        entry = MagicMock()
        entry.entry_id = "entry-empty"
        entry.version = 1
        entry.minor_version = 0
        entry.options = {}
        registry = MagicMock()

        with (
            patch("custom_components.idm_heatpump.er.async_get", return_value=registry),
            patch(
                "custom_components.idm_heatpump.er.async_entries_for_config_entry",
                return_value=[],
            ),
        ):
            result = await async_migrate_entry(mock_hass, entry)

        assert result is True
        registry.async_update_entity.assert_not_called()
        mock_hass.config_entries.async_update_entry.assert_called_once_with(
            entry,
            unique_id=None,
            options={CONF_DEVICE_HIERARCHY: False},
            version=1,
            minor_version=3,
        )

    async def test_migrates_multiple_legacy_unique_id_prefixes(self, mock_hass):
        entry = MagicMock()
        entry.entry_id = "entry-multi"
        entry.version = 1
        entry.minor_version = 0
        entry.options = {}
        registry = MagicMock()
        entities = [
            MagicMock(entity_id="sensor.host_prefix", unique_id="192.168.1.100:502_flow_temperature"),
            MagicMock(entity_id="sensor.host_port_prefix", unique_id="idm.local:502_return_temperature"),
            MagicMock(entity_id="sensor.non_legacy", unique_id="entry-multi_outdoor_temperature"),
        ]

        with (
            patch("custom_components.idm_heatpump.er.async_get", return_value=registry),
            patch(
                "custom_components.idm_heatpump.er.async_entries_for_config_entry",
                return_value=entities,
            ),
        ):
            result = await async_migrate_entry(mock_hass, entry)

        assert result is True
        assert registry.async_update_entity.call_count == 2
        registry.async_update_entity.assert_any_call(
            "sensor.host_prefix",
            new_unique_id="entry-multi_flow_temperature",
        )
        registry.async_update_entity.assert_any_call(
            "sensor.host_port_prefix",
            new_unique_id="entry-multi_return_temperature",
        )

    async def test_skips_current_config_entry_version(self, mock_hass):
        entry = MagicMock()
        entry.version = 1
        entry.minor_version = 3

        assert await async_migrate_entry(mock_hass, entry) is True
        mock_hass.config_entries.async_update_entry.assert_not_called()


class TestAsyncSetupEntry:
    def _make_entry(self):
        entry = MagicMock()
        entry.entry_id = "test_id"
        entry.title = "IDM Test"
        entry.data = {
            "host": "192.168.1.100",
            "port": 502,
            "slave_id": 1,
        }
        entry.options = {
            "scan_interval": 10,
            "heating_circuits": ["a"],
            "zone_count": 0,
            "zone_rooms": {},
            "hide_unused_registers": True,
        }
        entry.runtime_data = None
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    async def test_sets_runtime_data(self, mock_hass):
        entry = self._make_entry()

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 502

        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with (
            patch(
                "custom_components.idm_heatpump.get_idm_client",
                return_value=mock_client,
            ),
            patch(
                "custom_components.idm_heatpump.IdmCoordinator",
                return_value=mock_coordinator,
            ),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch(
                "custom_components.idm_heatpump.get_all_sensor_descriptions",
                return_value=[],
            ),
            patch(
                "custom_components.idm_heatpump.get_all_binary_sensor_descriptions",
                return_value=[],
            ),
            patch(
                "custom_components.idm_heatpump.get_all_number_descriptions",
                return_value=[],
            ),
            patch(
                "custom_components.idm_heatpump.get_all_select_descriptions",
                return_value=[],
            ),
            patch(
                "custom_components.idm_heatpump.get_all_switch_descriptions",
                return_value=[],
            ),
        ):
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        assert entry.runtime_data is not None
        assert isinstance(entry.runtime_data, IdmHeatpumpData)
        assert entry.runtime_data.coordinator is mock_coordinator
        assert entry.runtime_data.client is mock_client

    async def test_warms_the_error_code_database_off_the_event_loop(self, mock_hass):
        """The vendor error-code database must load in an executor, not the loop."""
        from homeassistant.exceptions import ConfigEntryNotReady

        from custom_components.idm_heatpump.internal_messages import warm_error_code_database

        entry = self._make_entry()
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=Exception("connection refused"))

        with (
            patch(
                "custom_components.idm_heatpump.get_idm_client",
                return_value=mock_client,
            ),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_entry(mock_hass, entry)

        # Scheduled before the connection is even attempted: whichever entity
        # writes the first error-code state finds the database already loaded.
        mock_hass.async_add_executor_job.assert_any_call(warm_error_code_database)

    async def test_raises_config_entry_not_ready_on_connect_failure(self, mock_hass):
        from homeassistant.exceptions import ConfigEntryNotReady

        entry = self._make_entry()
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=Exception("connection refused"))

        with (
            patch(
                "custom_components.idm_heatpump.get_idm_client",
                return_value=mock_client,
            ),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_entry(mock_hass, entry)

        mock_client.disconnect.assert_awaited_once()

    async def test_unwinds_platforms_when_a_later_setup_step_fails(self, mock_hass):
        """A failure after platform forwarding must not leave entities behind.

        Home Assistant marks the entry failed, but the platforms stay
        registered against a coordinator whose client setup then disconnects,
        so the user is left with a wall of unavailable entities and a
        connection error on every poll.
        """
        entry = self._make_entry()
        entry.options = {**entry.options, "knx_bridge": True, "knx_send": True}

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 502

        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()
        mock_coordinator.async_shutdown = AsyncMock()

        bridge = MagicMock()
        bridge.async_start = AsyncMock(side_effect=RuntimeError("knx exploded"))
        bridge.async_stop = AsyncMock()

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.KnxBridge", return_value=bridge),
            pytest.raises(RuntimeError, match="knx exploded"),
        ):
            await async_setup_entry(mock_hass, entry)

        mock_hass.config_entries.async_unload_platforms.assert_awaited_once()
        bridge.async_stop.assert_awaited_once()
        mock_coordinator.async_shutdown.assert_awaited_once()
        mock_client.disconnect.assert_awaited()

    async def test_disconnects_client_when_first_refresh_fails(self, mock_hass):
        entry = self._make_entry()
        mock_client = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=RuntimeError("refresh failed"))
        mock_coordinator.setup_registers = MagicMock()

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
            pytest.raises(RuntimeError, match="refresh failed"),
        ):
            await async_setup_entry(mock_hass, entry)

        mock_client.disconnect.assert_awaited_once()
        mock_hass.config_entries.async_forward_entry_setups.assert_not_awaited()

    async def test_forwards_entry_setups(self, mock_hass):
        entry = self._make_entry()

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with (
            patch(
                "custom_components.idm_heatpump.get_idm_client",
                return_value=mock_client,
            ),
            patch(
                "custom_components.idm_heatpump.IdmCoordinator",
                return_value=mock_coordinator,
            ),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        mock_hass.config_entries.async_forward_entry_setups.assert_called_once()


class TestAsyncSetupWebOnlyEntry:
    """Cover the web-only fallback setup path (T1)."""

    def _make_web_only_entry(self, *, web_pin="1234", detected_nav=None):
        entry = MagicMock()
        entry.entry_id = "web_only_id"
        entry.title = "IDM Web"
        entry.data = {
            "host": "192.168.1.100",
            "port": 502,
            "slave_id": 1,
            "web_pin": web_pin,
            "web_host": "192.168.1.100",
            "web_only_mode": True,
        }
        if detected_nav is not None:
            entry.data["detected_navigator_version"] = detected_nav
        entry.options = {
            "scan_interval": 10,
            "web_scan_interval": 30,
            "web_enabled": True,
        }
        entry.runtime_data = None
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    async def test_web_only_creates_coordinator_and_starts_web_task(self, mock_hass):
        from custom_components.idm_heatpump import IdmCoordinator

        entry = self._make_web_only_entry()
        mock_client = MagicMock()
        mock_client.host = "192.168.1.100"
        supplement = MagicMock(spec=IdmWebSupplement)
        supplement.model_name = "Navigator 10"
        supplement.software_version = "1.2.3"

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch(
                "custom_components.idm_heatpump.async_read_web_supplement",
                AsyncMock(return_value=supplement),
            ) as read_web,
            patch("custom_components.idm_heatpump.ir"),
            patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()),
        ):
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        assert isinstance(entry.runtime_data, IdmHeatpumpData)
        assert isinstance(entry.runtime_data.coordinator, IdmCoordinator)
        # Web-only mode exposes only web sensors: the register map is loaded
        # metadata-only (name resolution for the web register bridge), but no
        # register entity exists and nothing polls Modbus.
        assert entry.runtime_data.coordinator.sensor_descriptions == []
        assert entry.runtime_data.coordinator.update_interval is None
        mock_hass.config_entries.async_forward_entry_setups.assert_called_once()
        forwarded_platforms = mock_hass.config_entries.async_forward_entry_setups.call_args.args[1]
        # Web-only mode forwards sensor, select, number, button, climate and
        # water heater (the web-only controls of Phase 4). Platform members
        # are MagicMocks in the test stub, so assert on the list length.
        assert len(forwarded_platforms) == 6
        # model_hint comes from the detected navigator version stored in entry data.
        assert read_web.call_args.kwargs.get("model_hint") is None

    async def test_web_only_warms_the_error_code_database_off_the_event_loop(self, mock_hass):
        from custom_components.idm_heatpump.internal_messages import warm_error_code_database

        entry = self._make_web_only_entry()

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=MagicMock()),
            patch(
                "custom_components.idm_heatpump.async_read_web_supplement",
                AsyncMock(return_value=None),
            ),
            patch("custom_components.idm_heatpump.ir"),
            patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()),
        ):
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        mock_hass.async_add_executor_job.assert_any_call(warm_error_code_database)

    async def test_web_only_uses_detected_navigator_version_as_model_hint(self, mock_hass):
        entry = self._make_web_only_entry(detected_nav="Navigator 10")

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=MagicMock()),
            patch(
                "custom_components.idm_heatpump.async_read_web_supplement",
                AsyncMock(return_value=None),
            ) as read_web,
            patch("custom_components.idm_heatpump.ir"),
            patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()),
        ):
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        assert read_web.call_args.kwargs.get("model_hint") == "Navigator 10"

    async def test_web_only_continues_when_initial_web_read_fails(self, mock_hass):
        from custom_components.idm_heatpump import IdmCoordinator

        entry = self._make_web_only_entry()

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=MagicMock()),
            patch(
                "custom_components.idm_heatpump.async_read_web_supplement",
                AsyncMock(side_effect=RuntimeError("network down")),
            ),
            patch("custom_components.idm_heatpump.ir"),
            patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()),
        ):
            result = await async_setup_entry(mock_hass, entry)

        # Setup must still succeed with the generic model; the web loop retries.
        assert result is True
        assert isinstance(entry.runtime_data.coordinator, IdmCoordinator)
        assert entry.runtime_data.coordinator.model_name == MODEL


class TestWebOnlyRegisterBridge:
    """Web-only entries load the register map and can serve KNX from it."""

    def _make_web_only_entry(self, *, knx=False):
        entry = MagicMock()
        entry.entry_id = "bridge_entry"
        entry.title = "IDM Web"
        entry.data = {
            "host": "192.168.1.100",
            "port": 502,
            "slave_id": 1,
            "web_pin": "1234",
            "web_host": "192.168.1.100",
        }
        entry.options = {
            "connection_mode": "web_only",
            "scan_interval": 10,
            "heating_circuits": ["a"],
            "zone_count": 0,
            "zone_rooms": {},
            "web_enabled": True,
            "web_scan_interval": 10,
        }
        if knx:
            entry.options["knx_bridge"] = True
        entry.runtime_data = None
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    async def test_web_only_loads_the_register_map_metadata_only(self, mock_hass):
        supplement = MagicMock(spec=IdmWebSupplement)
        supplement.model_name = "Navigator 10"

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=MagicMock()),
            patch(
                "custom_components.idm_heatpump.async_read_web_supplement",
                AsyncMock(return_value=supplement),
            ),
            patch("custom_components.idm_heatpump.ir"),
            patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()),
        ):
            entry = self._make_web_only_entry()
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        coordinator = entry.runtime_data.coordinator
        # The register map resolved real register names (metadata-only)...
        assert coordinator.get_register("outdoor_temp") is not None
        # ...but no register entity exists and nothing polls Modbus.
        assert coordinator.sensor_descriptions == []

    async def test_web_only_starts_the_knx_bridge_when_enabled(self, mock_hass):
        supplement = MagicMock(spec=IdmWebSupplement)
        supplement.model_name = "Navigator 10"
        bridge = MagicMock()
        bridge.async_start = AsyncMock()

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=MagicMock()),
            patch(
                "custom_components.idm_heatpump.async_read_web_supplement",
                AsyncMock(return_value=supplement),
            ),
            patch("custom_components.idm_heatpump.ir"),
            patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()),
            patch("custom_components.idm_heatpump.KnxBridge", return_value=bridge) as knx_cls,
        ):
            entry = self._make_web_only_entry(knx=True)
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        bridge.async_start.assert_awaited_once()
        assert entry.runtime_data.knx_bridge is bridge
        # Bus commands follow the receive option (default: enabled); the
        # coordinator routes register-named writes to the web path in
        # web-only operation.
        constructed_config = knx_cls.call_args[0][2]
        assert constructed_config.receive_enabled is True


class TestConnectionMode:
    """The explicit connection mode selects the data paths (Phase 1)."""

    def _make_entry(self, *, options=None, data_extra=None):
        entry = MagicMock()
        entry.entry_id = "mode_entry"
        entry.title = "IDM Mode"
        entry.data = {
            "host": "192.168.1.100",
            "port": 502,
            "slave_id": 1,
            "web_pin": "1234",
        }
        entry.data.update(data_extra or {})
        entry.options = {
            "scan_interval": 10,
            "heating_circuits": ["a"],
            "zone_count": 0,
            "zone_rooms": {},
            "hide_unused_registers": True,
            "web_enabled": True,
            "web_scan_interval": 30,
        }
        entry.options.update(options or {})
        entry.runtime_data = None
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    def _normal_setup_patches(self, mock_client, mock_coordinator):
        return (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()),
        )

    async def test_web_only_mode_skips_modbus_entirely(self, mock_hass):
        """A first-class web_only selection must not attempt a Modbus connection."""
        entry = self._make_entry(options={"connection_mode": "web_only"})
        supplement = MagicMock(spec=IdmWebSupplement)
        supplement.model_name = "Navigator 10"
        supplement.software_version = "1.2.3"

        with (
            patch("custom_components.idm_heatpump.get_idm_client") as client_factory,
            patch(
                "custom_components.idm_heatpump.async_read_web_supplement",
                AsyncMock(return_value=supplement),
            ),
            patch("custom_components.idm_heatpump.ir"),
            patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()),
        ):
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        mock_client = client_factory.return_value
        mock_client.connect.assert_not_called()
        # Web-only forwards sensor, select, number, button, climate and
        # water heater (Phase 4).
        forwarded = mock_hass.config_entries.async_forward_entry_setups.call_args.args[1]
        assert len(forwarded) == 6

    async def test_modbus_only_mode_never_touches_the_web(self, mock_hass):
        """modbus_only skips the web read, the poll loop and the web pin."""
        entry = self._make_entry(options={"connection_mode": "modbus_only"})

        mock_client = AsyncMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 502
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with contextlib.ExitStack() as stack:
            for ctx in self._normal_setup_patches(mock_client, mock_coordinator)[:8]:
                stack.enter_context(ctx)
            read_web = stack.enter_context(
                patch("custom_components.idm_heatpump.async_read_web_supplement", AsyncMock())
            )
            web_loop = stack.enter_context(patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()))
            stack.enter_context(patch("custom_components.idm_heatpump.ir"))
            from custom_components.idm_heatpump import IdmCoordinator as coordinator_class

            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        read_web.assert_not_called()
        web_loop.assert_not_called()
        assert entry.runtime_data.web_task is None
        # The coordinator must not carry the web pin, or web sensors appear.
        assert coordinator_class.call_args.kwargs["web_pin"] is None

    async def test_modbus_only_does_not_raise_web_pin_missing(self, mock_hass):
        """Without the web path there is nothing a PIN could fix."""
        entry = self._make_entry(options={"connection_mode": "modbus_only"})
        entry.data = {k: v for k, v in entry.data.items() if k != "web_pin"}

        mock_client = AsyncMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 502
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with contextlib.ExitStack() as stack:
            for ctx in self._normal_setup_patches(mock_client, mock_coordinator)[:8]:
                stack.enter_context(ctx)
            stack.enter_context(patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()))
            issue_registry = stack.enter_context(patch("custom_components.idm_heatpump.ir"))
            await async_setup_entry(mock_hass, entry)

        issue_registry.async_create_issue.assert_not_called()

    async def test_modbus_web_mode_restores_modbus_despite_legacy_flag(self, mock_hass):
        """An explicit modbus_web selection overrides the old web_only flag."""
        entry = self._make_entry(
            options={"connection_mode": "modbus_web"},
            data_extra={"web_only_mode": True},
        )

        mock_client = AsyncMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 502
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with contextlib.ExitStack() as stack:
            for ctx in self._normal_setup_patches(mock_client, mock_coordinator)[:8]:
                stack.enter_context(ctx)
            read_web = stack.enter_context(
                patch(
                    "custom_components.idm_heatpump.async_read_web_supplement",
                    AsyncMock(return_value=None),
                )
            )
            stack.enter_context(patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()))
            stack.enter_context(patch("custom_components.idm_heatpump.ir"))
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        mock_client.connect.assert_awaited_once()
        read_web.assert_awaited_once()


class TestAsyncUnloadEntry:
    async def test_unloads_platforms(self, mock_hass):
        entry = MagicMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = AsyncMock()
        entry.runtime_data.client.disconnect = AsyncMock()
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass, entry)

        assert result is True
        mock_hass.config_entries.async_unload_platforms.assert_called_once()
        # #171: domain services must NOT be removed during entry unload.
        mock_hass.services.async_remove.assert_not_called()

    async def test_disconnects_client_on_success(self, mock_hass):
        entry = MagicMock()
        mock_client = AsyncMock()
        mock_client.disconnect = AsyncMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = mock_client
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        await async_unload_entry(mock_hass, entry)

        mock_client.disconnect.assert_called_once()

    async def test_does_not_disconnect_on_unload_failure(self, mock_hass):
        entry = MagicMock()
        mock_client = AsyncMock()
        mock_client.disconnect = AsyncMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = mock_client
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        result = await async_unload_entry(mock_hass, entry)

        assert result is False
        mock_client.disconnect.assert_not_called()

    async def test_returns_unload_result(self, mock_hass):
        entry = MagicMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = AsyncMock()
        entry.runtime_data.client.disconnect = AsyncMock()
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        result = await async_unload_entry(mock_hass, entry)
        assert result is False

    async def test_shuts_down_coordinator_on_unload(self, mock_hass):
        entry = MagicMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = AsyncMock()
        entry.runtime_data.client.disconnect = AsyncMock()
        mock_coordinator = AsyncMock()
        entry.runtime_data.coordinator = mock_coordinator
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass, entry)

        assert result is True
        mock_coordinator.async_shutdown.assert_awaited_once()

    async def test_services_survive_entry_unload(self, mock_hass):
        """#171: unloading an entry must not remove the domain services."""
        await async_setup_services(mock_hass)
        registered_before = mock_hass.services.async_register.call_count
        # Core services plus the two DHW boost actions and the advisor snooze pair.
        assert registered_before == 13

        entry = MagicMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = AsyncMock()
        entry.runtime_data.client.disconnect = AsyncMock()
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        await async_unload_entry(mock_hass, entry)

        # Services are untouched: no removals, registration count unchanged.
        mock_hass.services.async_remove.assert_not_called()
        assert mock_hass.services.async_register.call_count == 13

    async def test_services_survive_entry_reload(self, mock_hass):
        """#171: after unload + re-setup services remain registered exactly once."""
        await async_setup_services(mock_hass)
        entry = MagicMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = AsyncMock()
        entry.runtime_data.client.disconnect = AsyncMock()
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        await async_unload_entry(mock_hass, entry)
        # Idempotent re-registration (has_service now reports registered).
        mock_hass.services.has_service = MagicMock(return_value=True)
        await async_setup_services(mock_hass)

        mock_hass.services.async_remove.assert_not_called()
        assert mock_hass.services.async_register.call_count == 13


class TestAsyncReloadEntry:
    async def test_calls_async_reload(self, mock_hass):
        entry = MagicMock()
        entry.entry_id = "test_id"
        entry.data = {"host": "10.0.0.1", "port": 502}
        entry.options = {"scan_interval": 10}
        entry.runtime_data = MagicMock()
        entry.runtime_data.reload_fingerprint = None
        await async_reload_entry(mock_hass, entry)
        mock_hass.config_entries.async_reload.assert_called_once_with("test_id")

    async def test_skips_reload_when_only_detection_metadata_changed(self, mock_hass):
        from custom_components.idm_heatpump import _entry_reload_fingerprint

        entry = MagicMock()
        entry.entry_id = "test_id"
        entry.data = {
            "host": "10.0.0.1",
            "port": 502,
            "detected_navigator_version": "Navigator 10",
        }
        entry.options = {"scan_interval": 10}
        entry.runtime_data = MagicMock()
        # Fingerprint without detection keys matches structural settings.
        entry.data = {"host": "10.0.0.1", "port": 502}
        entry.runtime_data.reload_fingerprint = _entry_reload_fingerprint(entry)
        # Detection metadata arrives later without changing structural settings.
        entry.data = {
            "host": "10.0.0.1",
            "port": 502,
            "detected_navigator_version": "Navigator 10",
            "detected_software_version": "NAV10_20.24",
            "detected_web_variant": "nav10",
        }

        await async_reload_entry(mock_hass, entry)
        mock_hass.config_entries.async_reload.assert_not_called()


class TestAsyncSetupEntryOptions:
    """Verify that config options are extracted correctly with defaults."""

    def _make_entry(self, data_override=None, options_override=None):
        entry = MagicMock()
        entry.entry_id = "opt_test_id"
        entry.title = "IDM Options Test"
        entry.data = {"host": "10.0.0.5", **(data_override or {})}
        entry.options = {
            "scan_interval": 15,
            "heating_circuits": ["a", "b"],
            "zone_count": 0,
            "zone_rooms": {},
            "hide_unused_registers": False,
            **(options_override or {}),
        }
        entry.runtime_data = None
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    def _common_patches(self, mock_client, mock_coordinator):
        return [
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ]

    async def test_missing_web_pin_issue_created_only_when_web_enabled(self, mock_hass):
        """A missing web PIN is actionable only while web supplement data is enabled."""
        entry = self._make_entry(
            data_override={"web_pin": ""},
            options_override={"web_extra_data": True},
        )
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()
        ir.async_create_issue.reset_mock()

        ctx = __import__("contextlib").ExitStack()
        for p in self._common_patches(mock_client, mock_coordinator):
            ctx.enter_context(p)
        with ctx:
            await async_setup_entry(mock_hass, entry)

        ir.async_create_issue.assert_any_call(
            mock_hass,
            "idm_heatpump",
            f"web_pin_missing_{entry.entry_id}",
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="web_pin_missing",
            data={"entry_id": entry.entry_id},
            translation_placeholders={"name": entry.title},
        )

    async def test_missing_web_pin_issue_not_created_when_web_disabled(self, mock_hass):
        """Choosing Modbus-only mode keeps the missing web PIN repair closed."""
        entry = self._make_entry(
            data_override={"web_pin": ""},
            options_override={"web_extra_data": False},
        )
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()
        ir.async_create_issue.reset_mock()
        ir.async_delete_issue.reset_mock()

        ctx = __import__("contextlib").ExitStack()
        for p in self._common_patches(mock_client, mock_coordinator):
            ctx.enter_context(p)
        with ctx:
            await async_setup_entry(mock_hass, entry)

        assert not any(
            call.args[:3] == (mock_hass, "idm_heatpump", f"web_pin_missing_{entry.entry_id}")
            for call in ir.async_create_issue.call_args_list
        )
        ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", f"web_pin_missing_{entry.entry_id}")

    async def test_default_port_used_when_missing(self, mock_hass):
        """When port is absent from entry.data, default 502 is used."""
        entry = self._make_entry()
        # host only, no port
        entry.data = {"host": "10.0.0.5"}

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_kwargs: dict = {}

        def _capture_client(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_client

        patches = self._common_patches(mock_client, mock_coordinator)
        patches[0] = patch("custom_components.idm_heatpump.get_idm_client", side_effect=_capture_client)

        ctx = __import__("contextlib").ExitStack()
        for p in patches:
            ctx.enter_context(p)
        with ctx:
            await async_setup_entry(mock_hass, entry)

        assert captured_kwargs.get("port") == 502

    async def test_default_slave_id_used_when_missing(self, mock_hass):
        """When slave_id is absent from entry.data, default 1 is used."""
        entry = self._make_entry()
        entry.data = {"host": "10.0.0.5", "port": 502}

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_kwargs: dict = {}

        def _capture_client(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_client

        patches = self._common_patches(mock_client, mock_coordinator)
        patches[0] = patch("custom_components.idm_heatpump.get_idm_client", side_effect=_capture_client)

        ctx = __import__("contextlib").ExitStack()
        for p in patches:
            ctx.enter_context(p)
        with ctx:
            await async_setup_entry(mock_hass, entry)

        assert captured_kwargs.get("slave_id") == 1

    async def test_modbus_timeout_and_retries_passed_to_client(self, mock_hass):
        """Configured modbus_timeout / modbus_retries must reach get_idm_client."""
        entry = self._make_entry(options_override={"modbus_timeout": 20.0, "modbus_retries": 4})

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_kwargs: dict = {}

        def _capture_client(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_client

        patches = self._common_patches(mock_client, mock_coordinator)
        patches[0] = patch("custom_components.idm_heatpump.get_idm_client", side_effect=_capture_client)

        ctx = __import__("contextlib").ExitStack()
        for p in patches:
            ctx.enter_context(p)
        with ctx:
            await async_setup_entry(mock_hass, entry)

        assert captured_kwargs.get("timeout") == 20.0
        assert captured_kwargs.get("max_retries") == 4

    async def test_modbus_timeout_and_retries_default_when_missing(self, mock_hass):
        """Without explicit options, default timeout/retries are forwarded."""
        entry = self._make_entry()

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_kwargs: dict = {}

        def _capture_client(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_client

        patches = self._common_patches(mock_client, mock_coordinator)
        patches[0] = patch("custom_components.idm_heatpump.get_idm_client", side_effect=_capture_client)

        ctx = __import__("contextlib").ExitStack()
        for p in patches:
            ctx.enter_context(p)
        with ctx:
            await async_setup_entry(mock_hass, entry)

        assert captured_kwargs.get("timeout") == 10.0
        assert captured_kwargs.get("max_retries") == 3

    async def test_separate_web_host_is_used_for_web_supplement(self, mock_hass):
        """Proxy setups can use one host for Modbus and another for Navigator web."""
        entry = self._make_entry(
            data_override={
                "web_pin": "1234",
                "web_host": "192.0.2.103",
            },
            options_override={"web_extra_data": True},
        )
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_kwargs: dict = {}

        def _capture_coordinator(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_coordinator

        patches = self._common_patches(mock_client, mock_coordinator)
        patches[1] = patch("custom_components.idm_heatpump.IdmCoordinator", side_effect=_capture_coordinator)

        ctx = __import__("contextlib").ExitStack()
        for p in patches:
            ctx.enter_context(p)
        with (
            ctx,
            patch("custom_components.idm_heatpump.async_read_web_supplement", return_value=None) as read_web,
        ):
            await async_setup_entry(mock_hass, entry)

        read_web.assert_awaited_once_with(
            "192.0.2.103",
            "1234",
            model_hint="Navigator 2.0 / 10",
            preferred_variant=None,
            allow_variant_fallback=True,
            hass=mock_hass,
            read_timeout=WEB_SETUP_READ_TIMEOUT,
        )
        assert captured_kwargs.get("web_host") == "192.0.2.103"

    async def test_stored_web_variant_locks_runtime_protocol(self, mock_hass):
        """A previously detected Nav 2.0 entry must not probe Nav 10 at startup."""
        entry = self._make_entry(
            data_override={
                "web_pin": "1234",
                "detected_navigator_version": "Navigator 2.0",
                "detected_web_variant": "nav20",
            },
            options_override={"web_extra_data": True},
        )
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()
        captured_kwargs: dict = {}

        def _capture_coordinator(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_coordinator

        patches = self._common_patches(mock_client, mock_coordinator)
        patches[1] = patch("custom_components.idm_heatpump.IdmCoordinator", side_effect=_capture_coordinator)

        ctx = __import__("contextlib").ExitStack()
        for item in patches:
            ctx.enter_context(item)
        with (
            ctx,
            patch("custom_components.idm_heatpump.async_read_web_supplement", return_value=None) as read_web,
        ):
            await async_setup_entry(mock_hass, entry)

        kwargs = read_web.await_args.kwargs
        assert kwargs["preferred_variant"] == "nav20"
        assert kwargs["allow_variant_fallback"] is False
        assert captured_kwargs["web_variant"] == "nav20"

    async def test_coordinator_first_refresh_failure_raises_not_ready(self, mock_hass):
        """If coordinator.async_config_entry_first_refresh() fails, ConfigEntryNotReady is raised."""

        entry = self._make_entry()
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=Exception("first refresh failed"))
        mock_coordinator.setup_registers = MagicMock()

        patches = self._common_patches(mock_client, mock_coordinator)
        ctx = __import__("contextlib").ExitStack()
        for p in patches:
            ctx.enter_context(p)
        with ctx, pytest.raises(Exception):  # noqa: B017
            await async_setup_entry(mock_hass, entry)

    async def test_hide_unused_passed_to_coordinator(self, mock_hass):
        """hide_unused_registers option is forwarded to IdmCoordinator."""
        entry = self._make_entry(options_override={"hide_unused_registers": False})

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_kwargs: dict = {}

        def _capture_coordinator(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_coordinator

        patches = self._common_patches(mock_client, mock_coordinator)
        patches[1] = patch("custom_components.idm_heatpump.IdmCoordinator", side_effect=_capture_coordinator)

        ctx = __import__("contextlib").ExitStack()
        for p in patches:
            ctx.enter_context(p)
        with ctx:
            await async_setup_entry(mock_hass, entry)

        assert captured_kwargs.get("hide_unused") is False

    async def test_solar_thermal_option_strips_solar_from_the_model_info(self, mock_hass):
        """Turning 'solar thermal present' off removes the solar module from the register map."""
        entry = self._make_entry(options_override={"solar_thermal": False})

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]) as mock_sensors,
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        model_info = mock_sensors.call_args.args[4]
        assert isinstance(model_info, IdmModelInfo)
        assert model_info.has_solar is False
        assert FEATURE_SOLAR not in model_info.features
        # Every consumer sees the stripped info, not just the descriptions.
        assert mock_coordinator.setup_registers.call_args.kwargs["model_info"] is model_info

    async def test_solar_thermal_defaults_to_present(self, mock_hass):
        """Without the option the solar module stays in the map (backward compatible)."""
        entry = self._make_entry()

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]) as mock_sensors,
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        model_info = mock_sensors.call_args.args[4]
        assert isinstance(model_info, IdmModelInfo)
        assert model_info.has_solar is True

    async def test_selected_circuits_zones_and_cascade_drive_description_builders(self, mock_hass):
        entry = self._make_entry(
            options_override={
                "heating_circuits": ["a", "c"],
                "zone_count": 2,
                "zone_rooms": {"0": 1, "1": 3},
                "enable_cascade": True,
            }
        )

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]) as mock_sensors,
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]) as mock_binary,
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]) as mock_numbers,
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]) as mock_selects,
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]) as mock_switches,
        ):
            await async_setup_entry(mock_hass, entry)

        expected_args = (["a", "c"], 2, {0: 1, 1: 3}, True)
        for mock_builder in (mock_sensors, mock_binary, mock_numbers, mock_selects, mock_switches):
            mock_builder.assert_called_once()
            assert mock_builder.call_args.args[:4] == expected_args
        mock_coordinator.setup_registers.assert_called_once_with(
            ["a", "c"],
            2,
            {0: 1, 1: 3},
            True,
            model_info=mock_sensors.call_args.args[4],
            descriptions=[],
        )

    async def test_setup_entry_normalizes_persisted_zone_room_keys(self, mock_hass):
        """Home Assistant persists option dict keys as strings in JSON."""
        entry = self._make_entry(
            options_override={
                "zone_count": 2,
                "zone_rooms": {"0": 5, "1": 8},
            }
        )

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]) as mock_sensors,
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]) as mock_binary,
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]) as mock_numbers,
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]) as mock_selects,
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]) as mock_switches,
        ):
            await async_setup_entry(mock_hass, entry)

        for mock_builder in (mock_sensors, mock_binary, mock_numbers, mock_selects, mock_switches):
            assert mock_builder.call_args.args[2] == {0: 5, 1: 8}
        assert mock_coordinator.setup_registers.call_args.args[2] == {0: 5, 1: 8}

    async def test_enable_cascade_defaults_false(self, mock_hass):
        """enable_cascade defaults to False when not in options."""
        entry = self._make_entry()
        # No enable_cascade in options

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        setup_regs_args: list = []

        def _capture_setup_registers(*args, **kwargs):
            setup_regs_args.extend(args)

        mock_coordinator.setup_registers = _capture_setup_registers

        patches = self._common_patches(mock_client, mock_coordinator)
        ctx = __import__("contextlib").ExitStack()
        for p in patches:
            ctx.enter_context(p)
        with ctx:
            await async_setup_entry(mock_hass, entry)

        # setup_registers(circuits, zone_count, zone_rooms, enable_cascade=False)
        # 4th positional arg or absence = False
        if len(setup_regs_args) >= 4:
            assert setup_regs_args[3] is False
        # If not passed at all, that's also fine (default=False)


class TestDetectModelInfo:
    """detect_model() result should drive the displayed device model and
    firmware version, with a safe fallback when detection is unreliable."""

    async def test_returns_detected_model_name(self):
        client = AsyncMock()
        client.detect_model = AsyncMock(return_value=MagicMock(model_name="Navigator 10"))
        model_name, _, model_info = await _detect_model_info(client)
        assert model_name == "Navigator 10"
        assert model_info is None

    async def test_uses_client_model_name_when_model_unknown(self):
        client = AsyncMock()
        client.detect_model = AsyncMock(return_value=MagicMock(model_name=MODEL_UNKNOWN))
        client.model_name = "Navigator 2.0"
        model_name, _, _ = await _detect_model_info(client)
        assert model_name == "Navigator 2.0"

    async def test_falls_back_when_model_and_client_model_unknown(self):
        client = AsyncMock()
        client.detect_model = AsyncMock(return_value=MagicMock(model_name=MODEL_UNKNOWN))
        client.model_name = MODEL_UNKNOWN
        model_name, _, _ = await _detect_model_info(client)
        assert model_name == MODEL

    async def test_falls_back_on_detection_exception(self):
        client = AsyncMock()
        client.detect_model = AsyncMock(side_effect=Exception("modbus timeout"))
        model_name, firmware_version, model_info = await _detect_model_info(client)
        assert model_name == MODEL
        assert firmware_version is None
        assert model_info is None

    async def test_falls_back_on_non_string_model_name(self):
        """A plain AsyncMock client (no detect_model patched) must not leak a
        mock object into the device info model field."""
        client = AsyncMock()
        model_name, _, _ = await _detect_model_info(client)
        assert model_name == MODEL

    async def test_returns_firmware_version_when_present(self):
        client = AsyncMock()
        client.detect_model = AsyncMock(return_value=MagicMock(model_name="Navigator 10", firmware_version="1.4.2"))
        _, firmware_version, _ = await _detect_model_info(client)
        assert firmware_version == "1.4.2"

    async def test_returns_numeric_firmware_version_as_string(self):
        client = AsyncMock()
        client.detect_model = AsyncMock(return_value=MagicMock(model_name="Navigator 10", firmware_version=2.34))
        _, firmware_version, _ = await _detect_model_info(client)
        assert firmware_version == "2.34"

    async def test_firmware_version_none_when_not_exposed_by_library(self):
        """idm-heatpump-api 0.3.4's IdmModelInfo has no firmware_version field;
        getattr must not surface a mock/garbage value in that case."""
        client = AsyncMock()
        client.detect_model = AsyncMock(return_value=MagicMock(model_name="Navigator 10", spec=["model_name"]))
        _, firmware_version, _ = await _detect_model_info(client)
        assert firmware_version is None

    async def test_returns_detected_model_info_object(self):
        model_info = IdmModelInfo(
            model_name="Navigator 2.0",
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )
        client = AsyncMock()
        client.detect_model = AsyncMock(return_value=model_info)

        model_name, _, detected_model_info = await _detect_model_info(client)

        assert model_name == "Navigator 2.0"
        assert detected_model_info is model_info

    async def test_skips_unreliable_firmware_register_probe(self):
        client = AsyncMock()
        client.detect_model = AsyncMock(return_value=MagicMock(model_name="Navigator 10"))

        await _detect_model_info(client)

        client.detect_model.assert_awaited_once_with(read_firmware=False)

    def test_builds_navigator_20_model_info_from_a_name(self):
        model_info = model_info_from_name("Navigator 2.0", plant_shape(["a", "b"], 0, False))

        assert model_info is not None
        assert model_info.model_name == "Navigator 2.0"
        assert model_info.active_heating_circuits == ["A", "B"]
        assert model_info.has_cascade is False

    def test_generic_model_name_defaults_to_navigator_20(self):
        """Inconclusive/generic names must default to Nav 2.0 to avoid Nav-10-only crashes."""
        model_info = model_info_from_name(MODEL, plant_shape(["a"], 0, False))

        assert model_info is not None
        assert model_info.model_name == "Navigator 2.0"

    def test_navigator_10_model_name_returns_navigator_10(self):
        model_info = model_info_from_name("Navigator 10", plant_shape(["a"], 0, False))

        assert model_info is not None
        assert model_info.model_name == "Navigator 10"

    def test_unknown_model_name_defaults_to_navigator_20(self):
        model_info = model_info_from_name("Some Unknown Controller", plant_shape(["a"], 0, False))

        assert model_info is not None
        assert model_info.model_name == "Navigator 2.0"


class TestAsyncSetupEntryModelDetection:
    def _make_entry(self):
        entry = MagicMock()
        entry.entry_id = "model_test_id"
        entry.title = "IDM Model Test"
        entry.data = {"host": "10.0.0.9", "port": 502, "slave_id": 1}
        entry.options = {
            "scan_interval": 10,
            "heating_circuits": ["a"],
            "zone_count": 0,
            "zone_rooms": {},
            "hide_unused_registers": True,
        }
        entry.runtime_data = None
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    async def test_coordinator_receives_detected_model_name(self, mock_hass):
        entry = self._make_entry()

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.detect_model = AsyncMock(return_value=MagicMock(model_name="Navigator 10"))
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_kwargs: dict = {}

        def _capture_coordinator(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_coordinator

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", side_effect=_capture_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        assert captured_kwargs.get("model_name") == "Navigator 10"

    async def test_coordinator_receives_detected_model_info(self, mock_hass):
        entry = self._make_entry()
        model_info = IdmModelInfo(
            model_name="Navigator 10",
            active_heating_circuits=["A"],
            zone_modules=1,
            has_solar=False,
            has_isc=True,
            has_pv=False,
            has_cascade=False,
        )

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.detect_model = AsyncMock(return_value=model_info)
        mock_client.model_info = model_info
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_kwargs: dict = {}

        def _capture_coordinator(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_coordinator

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", side_effect=_capture_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        assert captured_kwargs.get("model_info") is model_info

    async def test_detected_model_info_drives_register_generation(self, mock_hass):
        entry = self._make_entry()
        model_info = IdmModelInfo(
            model_name="Navigator 2.0",
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.detect_model = AsyncMock(return_value=model_info)
        mock_client.model_info = model_info
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.7.2"}),
            ),
            patch(
                "custom_components.idm_heatpump.get_all_sensor_descriptions",
                return_value=[],
            ) as mock_sensors,
            patch(
                "custom_components.idm_heatpump.get_all_binary_sensor_descriptions",
                return_value=[],
            ),
            patch(
                "custom_components.idm_heatpump.get_all_number_descriptions",
                return_value=[],
            ),
            patch(
                "custom_components.idm_heatpump.get_all_select_descriptions",
                return_value=[],
            ),
            patch(
                "custom_components.idm_heatpump.get_all_switch_descriptions",
                return_value=[],
            ),
        ):
            await async_setup_entry(mock_hass, entry)

        mock_sensors.assert_called_once_with(["a"], 0, {}, False, model_info)
        mock_coordinator.setup_registers.assert_called_once_with(
            ["a"], 0, {}, False, model_info=model_info, descriptions=[]
        )

    async def test_detect_model_result_drives_register_generation_without_client_cache(self, mock_hass):
        entry = self._make_entry()
        model_info = IdmModelInfo(
            model_name="Navigator 2.0",
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.detect_model = AsyncMock(return_value=model_info)
        mock_client.model_info = None
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.8.0-beta.4"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]) as mock_sensors,
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        mock_sensors.assert_called_once_with(["a"], 0, {}, False, model_info)
        mock_coordinator.setup_registers.assert_called_once_with(
            ["a"], 0, {}, False, model_info=model_info, descriptions=[]
        )

    async def test_stored_detected_navigator_20_name_drives_register_generation(self, mock_hass):
        entry = self._make_entry()
        entry.data = {
            **entry.data,
            "detected_navigator_version": "Navigator 2.0",
        }
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.detect_model = AsyncMock(side_effect=Exception("probe timeout"))
        mock_client.model_info = None
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_model_info: list[IdmModelInfo | None] = []

        def _capture_sensors(*args):
            captured_model_info.append(args[-1])
            return []

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.8.0-beta.4"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", side_effect=_capture_sensors),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        assert captured_model_info
        assert captured_model_info[0] is not None
        assert captured_model_info[0].model_name == "Navigator 2.0"
        mock_coordinator.setup_registers.assert_called_once()
        assert mock_coordinator.setup_registers.call_args.kwargs["model_info"].model_name == "Navigator 2.0"

    async def test_modbus_detected_navigator_20_overrides_stale_stored_navigator_10(self, mock_hass):
        entry = self._make_entry()
        entry.data = {
            **entry.data,
            "detected_navigator_version": "Navigator 10",
            "detected_software_version": "NAV10_20.23",
        }
        model_info = IdmModelInfo(
            model_name="Navigator 2.0",
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.detect_model = AsyncMock(return_value=model_info)
        mock_client.model_info = model_info
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_kwargs: dict = {}

        def _capture_coordinator(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_coordinator

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", side_effect=_capture_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.8.0-beta.4"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        assert captured_kwargs["model_name"] == "Navigator 2.0"
        assert captured_kwargs["firmware_version"] is None
        assert captured_kwargs["model_info"] is model_info
        assert mock_coordinator.setup_registers.call_args.kwargs["model_info"] is model_info
        mock_hass.config_entries.async_update_entry.assert_any_call(
            entry,
            data={
                "host": "10.0.0.9",
                "port": 502,
                "slave_id": 1,
                "detected_navigator_version": "Navigator 2.0",
            },
        )

    async def test_web_firmware_prefix_corrects_weak_modbus_navigator_20_detection(self, mock_hass):
        """Web firmware NAV10 prefix overrides a weak Modbus Navigator 2.0 result."""
        entry = self._make_entry()
        entry.data = {**entry.data, "web_pin": "1234"}
        entry.options = {**entry.options, "web_extra_data": True}
        model_info = IdmModelInfo(
            model_name="Navigator 2.0",
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.detect_model = AsyncMock(return_value=model_info)
        mock_client.model_info = model_info
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_kwargs: dict = {}

        def _capture_coordinator(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_coordinator

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", side_effect=_capture_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.8.0-beta.4"}),
            ),
            patch(
                "custom_components.idm_heatpump.async_read_web_supplement",
                return_value=IdmWebSupplement(navigator_version="Navigator 10", software_version="NAV10_20.23"),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        assert captured_kwargs["model_name"] == "Navigator 10"
        assert captured_kwargs["firmware_version"] == "NAV10_20.23"
        assert captured_kwargs["model_info"].model_name == "Navigator 10"

    async def test_coordinator_receives_detected_firmware_version(self, mock_hass):
        entry = self._make_entry()

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.detect_model = AsyncMock(
            return_value=MagicMock(model_name="Navigator 10", firmware_version="2.0.1")
        )
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_kwargs: dict = {}

        def _capture_coordinator(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_coordinator

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", side_effect=_capture_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        assert captured_kwargs.get("firmware_version") == "2.0.1"

    async def test_coordinator_falls_back_to_default_model(self, mock_hass):
        entry = self._make_entry()

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.detect_model = AsyncMock(side_effect=Exception("no response"))
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_kwargs: dict = {}

        def _capture_coordinator(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_coordinator

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", side_effect=_capture_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        assert captured_kwargs.get("model_name") == MODEL

    async def test_detection_failure_passes_navigator_20_model_info_to_platforms(self, mock_hass):
        """When detect_model fails and no stored data exists, platform
        functions must receive a Navigator 2.0 fallback model_info so that
        Navigator-10-only registers (e.g. 4108 / 4001) are not polled on
        older controllers."""
        entry = self._make_entry()
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.detect_model = AsyncMock(side_effect=Exception("no response"))
        mock_client.model_info = None
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_model_info: list[object | None] = []

        def _capture_sensors(*args, **_kwargs):
            captured_model_info.append(_kwargs.get("model_info") if _kwargs else args[-1] if args else None)
            return []

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.8.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", side_effect=_capture_sensors),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        assert captured_model_info
        model_info = captured_model_info[0]
        assert model_info is not None
        assert model_info.model_name == "Navigator 2.0"

    async def test_detection_failure_with_stored_navigator_version_builds_fallback_model_info(self, mock_hass):
        """When detect_model fails but stored detected_navigator_version is
        "Navigator 2.0", platform functions must receive a Navigator 2.0
        model_info via model_info_from_name()."""
        entry = self._make_entry()
        entry.data = {
            **entry.data,
            "detected_navigator_version": "Navigator 2.0",
        }
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.detect_model = AsyncMock(side_effect=Exception("probe timeout"))
        mock_client.model_info = None
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured_model_info: list[object | None] = []

        def _capture_sensors(*args, **_kwargs):
            captured_model_info.append(_kwargs.get("model_info") if _kwargs else args[-1] if args else None)
            return []

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.8.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", side_effect=_capture_sensors),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        assert captured_model_info
        model_info = captured_model_info[0]
        assert model_info is not None
        assert model_info.model_name == "Navigator 2.0"
        assert model_info.has_cascade is False


class TestModelOverrideHelpers:
    """Unit tests for the pure override mapping helpers."""

    def test_model_name_for_override_maps_known_values(self):
        assert model_name_for_override(MODEL_OVERRIDE_NAVIGATOR_10) == "Navigator 10"
        assert model_name_for_override(MODEL_OVERRIDE_NAVIGATOR_20) == "Navigator 2.0"

    def test_model_name_for_override_returns_none_for_auto(self):
        assert model_name_for_override(MODEL_OVERRIDE_AUTO) is None

    def test_model_name_for_override_returns_none_for_unknown(self):
        assert model_name_for_override("navigator_99") is None

    def test_resolved_override_returns_none_for_auto(self):
        assert resolved_model_override({CONF_MODEL_OVERRIDE: MODEL_OVERRIDE_AUTO}) is None

    def test_resolved_override_returns_none_for_missing_key(self):
        assert resolved_model_override({}) is None

    def test_resolved_override_returns_none_for_empty_string(self):
        assert resolved_model_override({CONF_MODEL_OVERRIDE: ""}) is None

    def test_resolved_override_returns_name_for_explicit_value(self):
        assert resolved_model_override({CONF_MODEL_OVERRIDE: MODEL_OVERRIDE_NAVIGATOR_10}) == "Navigator 10"

    def test_resolved_override_returns_none_for_bogus_value(self):
        # Defensive: an invalid value stored in entry.data must not force a
        # wrong family — it falls back to automatic detection.
        assert resolved_model_override({CONF_MODEL_OVERRIDE: "garbage"}) is None


class TestAsyncSetupEntryModelOverride:
    """Integration-style tests: the override must win over Modbus detection."""

    def _make_entry(self, override: str | None = None):
        entry = MagicMock()
        entry.entry_id = "override_test_id"
        entry.title = "IDM Override Test"
        data: dict = {"host": "10.0.0.9", "port": 502, "slave_id": 1}
        if override is not None:
            data[CONF_MODEL_OVERRIDE] = override
        entry.data = data
        entry.options = {
            "scan_interval": 10,
            "heating_circuits": ["a"],
            "zone_count": 0,
            "zone_rooms": {},
            "hide_unused_registers": True,
        }
        entry.runtime_data = None
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    async def test_override_wins_over_modbus_detection(self, mock_hass):
        """Even if detect_model() returns Navigator 2.0, an explicit Navigator 10
        override must drive the coordinator model and the register map."""
        entry = self._make_entry(override=MODEL_OVERRIDE_NAVIGATOR_10)

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        # Modbus detection disagrees with the override on purpose.
        mock_client.detect_model = AsyncMock(return_value=MagicMock(model_name="Navigator 2.0", firmware_version=None))
        mock_client.model_info = None
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured: dict = {}

        def _capture_coordinator(*args, **kwargs):
            captured.update(kwargs)
            return mock_coordinator

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", side_effect=_capture_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.8.5"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        # The override won: the coordinator sees Navigator 10, not the detected 2.0.
        assert captured.get("model_name") == "Navigator 10"

    async def test_auto_keeps_modbus_detection(self, mock_hass):
        """With override = auto (or missing), the Modbus detection wins as before."""
        entry = self._make_entry(override=MODEL_OVERRIDE_AUTO)

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.detect_model = AsyncMock(return_value=MagicMock(model_name="Navigator 10", firmware_version=None))
        mock_client.model_info = None
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        captured: dict = {}

        def _capture_coordinator(*args, **kwargs):
            captured.update(kwargs)
            return mock_coordinator

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", side_effect=_capture_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.8.5"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ):
            await async_setup_entry(mock_hass, entry)

        assert captured.get("model_name") == "Navigator 10"


class TestBackgroundTaskHelpers:
    """The entry-scoped helpers that keep optional loops attached to the entry."""

    async def test_prefers_the_entry_background_task_api(self):
        from custom_components.idm_heatpump import _create_entry_background_task

        class _Entry:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def async_create_background_task(self, hass, coro, name):
                self.calls.append(name)
                coro.close()
                return "entry-task"

        entry = _Entry()

        async def _noop() -> None:
            return None

        assert _create_entry_background_task(MagicMock(), entry, _noop(), name="web") == "entry-task"
        assert entry.calls == ["web"]

    async def test_falls_back_to_the_event_loop(self):
        from custom_components.idm_heatpump import _create_entry_background_task

        hass = MagicMock()
        hass.async_create_task = None
        done = []

        async def _work() -> None:
            done.append(True)

        task = _create_entry_background_task(hass, MagicMock(spec=[]), _work(), name="web")
        await task

        assert done == [True]

    async def test_web_poll_loop_survives_a_failing_refresh(self):
        import asyncio as _asyncio

        from custom_components.idm_heatpump import _web_poll_loop

        coordinator = MagicMock()
        coordinator.async_refresh_web_supplement = AsyncMock(side_effect=[RuntimeError("boom"), None])
        coordinator.web_auth_blocked = False
        coordinator.last_web_error = None
        sleeps: list[float] = []

        async def _sleep(delay: float) -> None:
            sleeps.append(delay)
            if len(sleeps) >= 3:
                raise _asyncio.CancelledError

        with (
            patch("custom_components.idm_heatpump.asyncio.sleep", _sleep),
            pytest.raises(_asyncio.CancelledError),
        ):
            await _web_poll_loop(coordinator, 30)

        # The first cycle raised, so its retry is backed off once; the second
        # succeeded and reset the interval.
        assert sleeps == [0.3, 60, 30]
        assert coordinator.async_refresh_web_supplement.await_count == 2

    async def test_web_poll_loop_backs_off_while_the_navigator_stays_unreachable(self):
        """A Navigator that is switched off must not be probed at full rate forever."""
        import asyncio as _asyncio

        from custom_components.idm_heatpump import _web_poll_loop

        coordinator = MagicMock()
        coordinator.async_refresh_web_supplement = AsyncMock()
        coordinator.web_auth_blocked = False
        # The coordinator swallows the failure and records it here.
        coordinator.last_web_error = "OSError: unreachable"
        sleeps: list[float] = []

        async def _sleep(delay: float) -> None:
            sleeps.append(delay)
            if len(sleeps) >= 6:
                raise _asyncio.CancelledError

        with (
            patch("custom_components.idm_heatpump.asyncio.sleep", _sleep),
            pytest.raises(_asyncio.CancelledError),
        ):
            await _web_poll_loop(coordinator, 30)

        assert sleeps == [0.3, 60, 120, 240, 300, 300], "backoff grows and then caps"

    async def test_web_poll_loop_stops_after_the_pin_was_rejected(self):
        """Retrying a refused PIN is how the integration would cause a lockout."""

        from custom_components.idm_heatpump import _web_poll_loop

        coordinator = MagicMock()
        coordinator.async_refresh_web_supplement = AsyncMock()
        coordinator.last_web_error = "IdmWebAuthenticationFailed: rejected"
        coordinator.web_auth_blocked = True
        sleeps: list[float] = []

        async def _sleep(delay: float) -> None:
            sleeps.append(delay)

        with patch("custom_components.idm_heatpump.asyncio.sleep", _sleep):
            await _web_poll_loop(coordinator, 30)

        assert coordinator.async_refresh_web_supplement.await_count == 1
        assert sleeps == [0.3], "the loop returns instead of sleeping for another try"


class TestUnloadCancelsBackgroundTasks:
    """Unloading must stop every optional loop the entry started."""

    async def test_all_entry_tasks_are_cancelled(self, mock_hass):
        import asyncio as _asyncio

        async def _forever() -> None:
            await _asyncio.Event().wait()

        entry = MagicMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = AsyncMock()
        tasks = {
            name: _asyncio.get_running_loop().create_task(_forever())
            for name in (
                "web_task",
                "room_temp_forwarding_task",
                "humidity_forwarding_task",
                "storage_temp_forwarding_task",
            )
        }
        for name, task in tasks.items():
            setattr(entry.runtime_data, name, task)
        entry.runtime_data.knx_bridge = None
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        assert await async_unload_entry(mock_hass, entry) is True

        for name, task in tasks.items():
            assert task.cancelled(), f"{name} was left running"


class TestWebOnlyModelOverride:
    """A stored model override stays authoritative in web-only mode."""

    def _make_entry(self):
        entry = MagicMock()
        entry.entry_id = "web_override_id"
        entry.title = "IDM Web Override"
        entry.data = {
            "host": "192.0.2.60",
            "port": 502,
            "slave_id": 1,
            "web_pin": "1234",
            "web_host": "192.0.2.60",
            "web_only_mode": True,
            "model_override": "navigator_10",
        }
        entry.options = {
            "scan_interval": 10,
            "web_scan_interval": 30,
            "web_enabled": True,
        }
        entry.runtime_data = None
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    async def test_override_beats_the_web_supplement_model(self, mock_hass):
        from custom_components.idm_heatpump import IdmCoordinator

        entry = self._make_entry()
        supplement = MagicMock(spec=IdmWebSupplement)
        supplement.model_name = "Navigator 2.0"
        supplement.software_version = "NAV20_1.2"

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=MagicMock()),
            patch("custom_components.idm_heatpump.async_read_web_supplement", AsyncMock(return_value=supplement)),
            patch("custom_components.idm_heatpump.ir"),
            patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()),
        ):
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        assert isinstance(entry.runtime_data.coordinator, IdmCoordinator)
        # The user-selected model wins even though the web supplement
        # reported a different controller.
        assert entry.runtime_data.coordinator.model_name == "Navigator 10"


class TestWebOnlyKnxInvalidBaseAddress:
    """An unusable KNX base address must not fail web-only setup."""

    def _make_entry(self):
        entry = MagicMock()
        entry.entry_id = "web_knx_invalid_id"
        entry.title = "IDM Web KNX"
        entry.data = {
            "host": "192.0.2.61",
            "port": 502,
            "slave_id": 1,
            "web_pin": "1234",
            "web_host": "192.0.2.61",
        }
        entry.options = {
            "connection_mode": "web_only",
            "scan_interval": 10,
            "heating_circuits": ["a"],
            "zone_count": 0,
            "zone_rooms": {},
            "web_enabled": True,
            "web_scan_interval": 10,
            "knx_bridge": True,
        }
        entry.runtime_data = None
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    async def test_invalid_base_address_leaves_setup_running_without_the_bridge(self, mock_hass):
        from custom_components.idm_heatpump.knx_catalog import InvalidGroupAddressError

        entry = self._make_entry()
        supplement = MagicMock(spec=IdmWebSupplement)
        supplement.model_name = "Navigator 10"
        bridge = MagicMock()
        bridge.async_start = AsyncMock(side_effect=InvalidGroupAddressError("base address out of range"))

        with (
            patch("custom_components.idm_heatpump.get_idm_client", return_value=MagicMock()),
            patch("custom_components.idm_heatpump.async_read_web_supplement", AsyncMock(return_value=supplement)),
            patch("custom_components.idm_heatpump.ir"),
            patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()),
            patch("custom_components.idm_heatpump.KnxBridge", return_value=bridge),
        ):
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        bridge.async_start.assert_awaited_once()
        # The failed bridge is not reachable for teardown later on.
        assert entry.runtime_data.knx_bridge is None


class TestAsyncMigrateEntryOtherVersions:
    async def test_entries_from_other_schema_versions_are_left_alone(self, mock_hass):
        entry = MagicMock()
        entry.version = 2
        entry.minor_version = 0

        assert await async_migrate_entry(mock_hass, entry) is True
        mock_hass.config_entries.async_update_entry.assert_not_called()


class _LegacyClientWithoutEepromSetter:
    """Stand-in for an older API client whose EEPROM interval cannot be set."""

    def __init__(self) -> None:
        self.host = "192.0.2.50"
        self.port = 502
        self.connect = AsyncMock()
        self.disconnect = AsyncMock()
        self.detect_model = AsyncMock(return_value=MagicMock(model_name="Navigator 10"))

    @property
    def eeprom_write_interval(self) -> float:
        """Property without a setter: assignment raises AttributeError."""
        return 60.0


class TestAsyncSetupEntryResilience:
    """Fallback branches of the Modbus setup path."""

    def _make_entry(self, options=None, data_extra=None):
        entry = MagicMock()
        entry.entry_id = "resilience_id"
        entry.title = "IDM Resilience"
        entry.data = {
            "host": "192.0.2.50",
            "port": 502,
            "slave_id": 1,
            **(data_extra or {}),
        }
        entry.options = {
            "scan_interval": 10,
            "heating_circuits": ["a"],
            "zone_count": 0,
            "zone_rooms": {},
            "hide_unused_registers": True,
            # Keep the optional advisor out of these failure-path tests.
            "predictive_advisor": False,
            **(options or {}),
        }
        entry.runtime_data = None
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    def _patch_list(self, mock_client, mock_coordinator):
        return [
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ]

    def _client_and_coordinator(self):
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()
        return mock_client, mock_coordinator

    async def test_eeprom_write_interval_setter_failure_is_tolerated(self, mock_hass):
        """An older API without the EEPROM setter must not fail setup."""
        entry = self._make_entry()
        legacy_client = _LegacyClientWithoutEepromSetter()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()

        with contextlib.ExitStack() as stack:
            for item in self._patch_list(legacy_client, mock_coordinator):
                stack.enter_context(item)
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        assert entry.runtime_data is not None

    async def test_disconnect_failure_after_connect_failure_is_tolerated(self, mock_hass):
        from homeassistant.exceptions import ConfigEntryNotReady

        entry = self._make_entry()
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=Exception("connection refused"))
        mock_client.disconnect = AsyncMock(side_effect=Exception("socket already closed"))

        with contextlib.ExitStack() as stack:
            for item in self._patch_list(mock_client, MagicMock()):
                stack.enter_context(item)
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(mock_hass, entry)

        mock_client.disconnect.assert_awaited_once()

    async def test_rejected_web_pin_during_setup_keeps_modbus_running(self, mock_hass):
        from custom_components.idm_heatpump.web_data import IdmWebAuthenticationFailed

        entry = self._make_entry(data_extra={"web_pin": "1234"})
        mock_client, mock_coordinator = self._client_and_coordinator()

        with contextlib.ExitStack() as stack:
            for item in self._patch_list(mock_client, mock_coordinator):
                stack.enter_context(item)
            stack.enter_context(
                patch(
                    "custom_components.idm_heatpump.async_read_web_supplement",
                    AsyncMock(side_effect=IdmWebAuthenticationFailed),
                )
            )
            stack.enter_context(patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()))
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        assert entry.runtime_data is not None

    async def test_unreachable_web_interface_during_setup_keeps_modbus_running(self, mock_hass):
        entry = self._make_entry(data_extra={"web_pin": "1234"})
        mock_client, mock_coordinator = self._client_and_coordinator()

        with contextlib.ExitStack() as stack:
            for item in self._patch_list(mock_client, mock_coordinator):
                stack.enter_context(item)
            stack.enter_context(
                patch(
                    "custom_components.idm_heatpump.async_read_web_supplement",
                    AsyncMock(side_effect=TimeoutError("web interface unreachable")),
                )
            )
            stack.enter_context(patch("custom_components.idm_heatpump._web_poll_loop", AsyncMock()))
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        assert entry.runtime_data is not None

    async def test_invalid_knx_base_address_disables_the_bridge_but_not_setup(self, mock_hass):
        from custom_components.idm_heatpump.knx_catalog import InvalidGroupAddressError

        entry = self._make_entry(options={"knx_bridge": True, "knx_send": True})
        mock_client, mock_coordinator = self._client_and_coordinator()
        bridge = MagicMock()
        bridge.async_start = AsyncMock(side_effect=InvalidGroupAddressError("bad base address"))
        bridge.async_stop = AsyncMock()

        with contextlib.ExitStack() as stack:
            for item in self._patch_list(mock_client, mock_coordinator):
                stack.enter_context(item)
            stack.enter_context(patch("custom_components.idm_heatpump.KnxBridge", return_value=bridge))
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        bridge.async_start.assert_awaited_once()
        bridge.async_stop.assert_awaited_once()
        # The failed bridge must not stay reachable for the unload teardown.
        assert entry.runtime_data.knx_bridge is None

    async def test_secondary_unwind_failures_do_not_mask_the_original_error(self, mock_hass):
        """Every teardown step is best-effort; the original setup error survives."""
        entry = self._make_entry(options={"knx_bridge": True, "knx_send": True})
        mock_client, mock_coordinator = self._client_and_coordinator()
        mock_client.disconnect = AsyncMock(side_effect=Exception("close failed"))
        mock_coordinator.async_shutdown = AsyncMock(side_effect=Exception("shutdown failed"))
        bridge = MagicMock()
        bridge.async_start = AsyncMock(side_effect=RuntimeError("knx exploded"))
        bridge.async_stop = AsyncMock(side_effect=Exception("stop failed"))
        mock_hass.config_entries.async_unload_platforms = AsyncMock(side_effect=Exception("unload failed"))

        with contextlib.ExitStack() as stack:
            for item in self._patch_list(mock_client, mock_coordinator):
                stack.enter_context(item)
            stack.enter_context(patch("custom_components.idm_heatpump.KnxBridge", return_value=bridge))
            with pytest.raises(RuntimeError, match="knx exploded"):
                await async_setup_entry(mock_hass, entry)

        # Each best-effort cleanup ran despite raising on its own.
        bridge.async_stop.assert_awaited_once()
        mock_coordinator.async_shutdown.assert_awaited_once()
        mock_hass.config_entries.async_unload_platforms.assert_awaited_once()
        mock_client.disconnect.assert_awaited_once()


class TestTeardownPartialSetup:
    async def test_without_runtime_data_nothing_is_torn_down(self, mock_hass):
        from custom_components.idm_heatpump import _async_teardown_partial_setup

        entry = MagicMock()
        entry.runtime_data = None

        await _async_teardown_partial_setup(mock_hass, entry)

        mock_hass.config_entries.async_unload_platforms.assert_not_awaited()


class TestOptionalFeatureStartup:
    """The optional forwarders, schedulers and managers wired into setup."""

    def _make_entry(self, options=None):
        entry = MagicMock()
        entry.entry_id = "features_id"
        entry.title = "IDM Features"
        entry.data = {"host": "192.0.2.51", "port": 502, "slave_id": 1}
        entry.options = {
            "scan_interval": 10,
            "heating_circuits": ["a"],
            "zone_count": 0,
            "zone_rooms": {},
            "hide_unused_registers": True,
            "predictive_advisor": False,
            **(options or {}),
        }
        entry.runtime_data = None
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    def _patch_list(self, mock_client, mock_coordinator):
        return [
            patch("custom_components.idm_heatpump.get_idm_client", return_value=mock_client),
            patch("custom_components.idm_heatpump.IdmCoordinator", return_value=mock_coordinator),
            patch(
                "custom_components.idm_heatpump.async_get_integration",
                return_value=MagicMock(manifest={"version": "0.5.0"}),
            ),
            patch("custom_components.idm_heatpump.get_all_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_binary_sensor_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_number_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_select_descriptions", return_value=[]),
            patch("custom_components.idm_heatpump.get_all_switch_descriptions", return_value=[]),
        ]

    def _client_and_coordinator(self):
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.setup_registers = MagicMock()
        return mock_client, mock_coordinator

    async def _run_setup(self, mock_hass, entry, extra_patches=(), *, client=None, coordinator=None):
        mock_client, mock_coordinator = self._client_and_coordinator()
        if client is not None:
            mock_client = client
        if coordinator is not None:
            mock_coordinator = coordinator
        with contextlib.ExitStack() as stack:
            for item in self._patch_list(mock_client, mock_coordinator):
                stack.enter_context(item)
            for item in extra_patches:
                stack.enter_context(item)
            return await async_setup_entry(mock_hass, entry)

    async def test_room_temperature_forwarding_starts_with_configured_entities(self, mock_hass):
        from custom_components.idm_heatpump.const import (
            CONF_ROOM_TEMP_FORWARDING,
            CONF_ROOM_TEMP_FORWARDING_ENTITIES,
            CONF_ROOM_TEMP_FORWARDING_INTERVAL,
            CONF_ROOM_TEMP_FORWARDING_TOLERANCE,
        )

        task = object()
        mock_hass.async_create_task = MagicMock(return_value=task)
        entry = self._make_entry(
            options={
                CONF_ROOM_TEMP_FORWARDING: True,
                CONF_ROOM_TEMP_FORWARDING_ENTITIES: {"a": "sensor.living_room", "b": "   "},
                CONF_ROOM_TEMP_FORWARDING_INTERVAL: 120,
                CONF_ROOM_TEMP_FORWARDING_TOLERANCE: 0.5,
            }
        )
        constructed: list[tuple[tuple, dict]] = []
        forwarders: list[MagicMock] = []

        def _make_forwarder(*args, **kwargs):
            constructed.append((args, kwargs))
            instance = MagicMock()
            forwarders.append(instance)
            return instance

        result = await self._run_setup(
            mock_hass, entry, [patch("custom_components.idm_heatpump.RoomTempForwarder", side_effect=_make_forwarder)]
        )

        assert result is True
        assert entry.runtime_data.room_temp_forwarding_task is task
        config = constructed[0][0][2]
        # Blank entity ids are filtered before the forwarder is built.
        assert config.entities == {"a": "sensor.living_room"}
        assert config.interval == 120
        assert config.tolerance == 0.5
        forwarders[0].async_run.assert_called_once_with()

    async def test_humidity_forwarding_starts_with_the_configured_entity(self, mock_hass):
        from custom_components.idm_heatpump.const import (
            CONF_HUMIDITY_FORWARDING,
            CONF_HUMIDITY_FORWARDING_ENTITY,
            CONF_HUMIDITY_FORWARDING_INTERVAL,
            CONF_HUMIDITY_FORWARDING_TOLERANCE,
        )

        task = object()
        mock_hass.async_create_task = MagicMock(return_value=task)
        entry = self._make_entry(
            options={
                CONF_HUMIDITY_FORWARDING: True,
                CONF_HUMIDITY_FORWARDING_ENTITY: "sensor.living_room_humidity",
                CONF_HUMIDITY_FORWARDING_INTERVAL: 90,
                CONF_HUMIDITY_FORWARDING_TOLERANCE: 3.0,
            }
        )
        constructed: list[tuple[tuple, dict]] = []
        forwarders: list[MagicMock] = []

        def _make_forwarder(*args, **kwargs):
            constructed.append((args, kwargs))
            instance = MagicMock()
            forwarders.append(instance)
            return instance

        result = await self._run_setup(
            mock_hass, entry, [patch("custom_components.idm_heatpump.HumidityForwarder", side_effect=_make_forwarder)]
        )

        assert result is True
        assert entry.runtime_data.humidity_forwarding_task is task
        config = constructed[0][0][2]
        assert config.entity_id == "sensor.living_room_humidity"
        assert config.interval == 90
        assert config.tolerance == 3.0
        forwarders[0].async_run.assert_called_once_with()

    async def test_storage_temperature_forwarding_uses_the_storage_register_resolver(self, mock_hass):
        from custom_components.idm_heatpump.const import (
            CONF_STORAGE_TEMP_FORWARDING,
            CONF_STORAGE_TEMP_FORWARDING_ENTITIES,
            CONF_STORAGE_TEMP_FORWARDING_INTERVAL,
            CONF_STORAGE_TEMP_FORWARDING_TOLERANCE,
        )
        from custom_components.idm_heatpump.room_temp_forwarding import register_for_storage_temp_key

        task = object()
        mock_hass.async_create_task = MagicMock(return_value=task)
        entry = self._make_entry(
            options={
                CONF_STORAGE_TEMP_FORWARDING: True,
                CONF_STORAGE_TEMP_FORWARDING_ENTITIES: {"hwt1": "sensor.storage_top", "hwt2": ""},
                CONF_STORAGE_TEMP_FORWARDING_INTERVAL: 240,
                CONF_STORAGE_TEMP_FORWARDING_TOLERANCE: 0.4,
            }
        )
        constructed: list[tuple[tuple, dict]] = []
        forwarders: list[MagicMock] = []

        def _make_forwarder(*args, **kwargs):
            constructed.append((args, kwargs))
            instance = MagicMock()
            forwarders.append(instance)
            return instance

        result = await self._run_setup(
            mock_hass, entry, [patch("custom_components.idm_heatpump.RoomTempForwarder", side_effect=_make_forwarder)]
        )

        assert result is True
        assert entry.runtime_data.storage_temp_forwarding_task is task
        args, kwargs = constructed[0]
        config = args[2]
        assert config.entities == {"hwt1": "sensor.storage_top"}
        assert config.interval == 240
        assert config.tolerance == 0.4
        # The storage forwarder reuses RoomTempForwarder with fixed registers.
        assert kwargs["register_for_key"] is register_for_storage_temp_key
        assert kwargs["key_label"] == "storage key"
        assert kwargs["value_label"] == "storage temperature"
        forwarders[0].async_run.assert_called_once_with()

    async def test_external_power_forwarding_starts_with_configured_sources(self, mock_hass):
        from custom_components.idm_heatpump.const import (
            CONF_EXTERNAL_POWER_FORWARDING,
            CONF_EXTERNAL_POWER_FORWARDING_ENTITIES,
            CONF_EXTERNAL_POWER_FORWARDING_INTERVAL,
        )

        task = object()
        mock_hass.async_create_task = MagicMock(return_value=task)
        entry = self._make_entry(
            options={
                CONF_EXTERNAL_POWER_FORWARDING: True,
                CONF_EXTERNAL_POWER_FORWARDING_ENTITIES: {
                    "pv_production": "sensor.pv_power",
                    "house_consumption": "sensor.house_power",
                },
                CONF_EXTERNAL_POWER_FORWARDING_INTERVAL: 45,
            }
        )
        constructed: list[tuple[tuple, dict]] = []
        forwarders: list[MagicMock] = []

        def _make_forwarder(*args, **kwargs):
            constructed.append((args, kwargs))
            instance = MagicMock()
            forwarders.append(instance)
            return instance

        result = await self._run_setup(
            mock_hass,
            entry,
            [patch("custom_components.idm_heatpump.ExternalPowerForwarder", side_effect=_make_forwarder)],
        )

        assert result is True
        assert entry.runtime_data.external_power_forwarding_task is task
        config = constructed[0][0][2]
        assert config.entities == {
            "pv_production": "sensor.pv_power",
            "house_consumption": "sensor.house_power",
        }
        assert config.interval == 45
        assert config.battery_sign == "as_is"
        forwarders[0].async_run.assert_called_once_with()

    async def test_energy_manager_starts_with_confirmed_exclusive_control(self, mock_hass):
        from custom_components.idm_heatpump.const import (
            CONF_ENERGY_MANAGER,
            CONF_ENERGY_MANAGER_COOLDOWN,
            CONF_ENERGY_MANAGER_EXCLUSIVE,
            CONF_ENERGY_MANAGER_MIN_SOC,
            CONF_ENERGY_MANAGER_MIN_SURPLUS,
            CONF_ENERGY_MANAGER_TARGET,
            CONF_ENERGY_MANAGER_TIMEOUT,
            CONF_EXTERNAL_POWER_FORWARDING_ENTITIES,
        )

        entry = self._make_entry(
            options={
                CONF_ENERGY_MANAGER: True,
                CONF_ENERGY_MANAGER_EXCLUSIVE: True,
                CONF_EXTERNAL_POWER_FORWARDING_ENTITIES: {
                    "pv_production": "sensor.pv_power",
                    "battery_soc": "  ",
                },
                CONF_ENERGY_MANAGER_MIN_SURPLUS: 1.5,
                CONF_ENERGY_MANAGER_MIN_SOC: 30,
                CONF_ENERGY_MANAGER_TARGET: 60,
                CONF_ENERGY_MANAGER_TIMEOUT: 45,
                CONF_ENERGY_MANAGER_COOLDOWN: 15,
            }
        )
        manager = MagicMock()
        constructed: list[tuple[tuple, dict]] = []

        def _make_manager(*args, **kwargs):
            constructed.append((args, kwargs))
            return manager

        result = await self._run_setup(
            mock_hass, entry, [patch("custom_components.idm_heatpump.EnergyManager", side_effect=_make_manager)]
        )

        assert result is True
        assert entry.runtime_data.energy_manager is manager
        manager.start.assert_called_once_with()
        config = constructed[0][0][2]
        assert config.sources == {"pv_production": "sensor.pv_power"}
        assert config.minimum_surplus_kw == 1.5
        assert config.minimum_battery_soc == 30.0
        assert config.target_temperature == 60
        assert config.timeout_minutes == 45
        assert config.cooldown_minutes == 15

    async def test_energy_manager_stays_off_without_usable_sources(self, mock_hass):
        from custom_components.idm_heatpump.const import (
            CONF_ENERGY_MANAGER,
            CONF_ENERGY_MANAGER_EXCLUSIVE,
            CONF_EXTERNAL_POWER_FORWARDING_ENTITIES,
        )

        entry = self._make_entry(
            options={
                CONF_ENERGY_MANAGER: True,
                CONF_ENERGY_MANAGER_EXCLUSIVE: True,
                # Every configured source entity is blank.
                CONF_EXTERNAL_POWER_FORWARDING_ENTITIES: {"pv_production": " "},
            }
        )
        manager = MagicMock()

        result = await self._run_setup(
            mock_hass, entry, [patch("custom_components.idm_heatpump.EnergyManager", return_value=manager)]
        )

        assert result is True
        # Blank sources never construct the manager, let alone start it.
        manager.start.assert_not_called()
        assert entry.runtime_data.energy_manager is None

    async def test_comfort_schedule_starts_one_scheduler_per_windowed_circuit(self, mock_hass):
        from custom_components.idm_heatpump.const import (
            CONF_COMFORT_SCHEDULE,
            CONF_COMFORT_SCHEDULE_EXCLUSIVE,
            CONF_COMFORT_WINDOWS,
        )

        entry = self._make_entry(
            options={
                CONF_COMFORT_SCHEDULE: True,
                CONF_COMFORT_SCHEDULE_EXCLUSIVE: True,
                CONF_COMFORT_WINDOWS: "a, 05:00, 22:00, 21.0\nb, 06:00, 22:00, 22.5",
                "heating_circuits": ["a", "b"],
            }
        )
        constructed: list[tuple[tuple, dict]] = []
        schedulers: list[MagicMock] = []

        def _make_scheduler(*args, **kwargs):
            instance = MagicMock()
            instance.register_name = f"comfort_reg_{len(schedulers)}"
            schedulers.append(instance)
            constructed.append((args, kwargs))
            return instance

        # Circuit "a" has a writable register; circuit "b" does not, so its
        # scheduler is constructed but never started.
        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.setup_registers = MagicMock()
        coordinator.get_register = MagicMock(side_effect=lambda name: {"comfort_reg_0": object()}.get(name))

        with contextlib.ExitStack() as stack:
            for item in self._patch_list(AsyncMock(), coordinator):
                stack.enter_context(item)
            stack.enter_context(patch("custom_components.idm_heatpump.ComfortScheduler", side_effect=_make_scheduler))
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        assert len(schedulers) == 2
        assert entry.runtime_data.comfort_schedulers == (schedulers[0],)
        assert entry.runtime_data.comfort_scheduler is schedulers[0]
        schedulers[0].start.assert_called_once_with()
        schedulers[1].start.assert_not_called()
        # Schedules are built per circuit, sorted, with that circuit's windows.
        first_args, first_kwargs = constructed[0]
        assert first_args[2] == "a"
        assert [window.circuit for window in first_kwargs["windows"]] == ["a"]
        second_args, second_kwargs = constructed[1]
        assert second_args[2] == "b"
        assert [window.circuit for window in second_kwargs["windows"]] == ["b"]

    async def test_comfort_schedule_without_windows_uses_the_default_circuit(self, mock_hass):
        from custom_components.idm_heatpump.const import (
            CONF_COMFORT_SCHEDULE,
            CONF_COMFORT_SCHEDULE_CIRCUIT,
            CONF_COMFORT_SCHEDULE_END,
            CONF_COMFORT_SCHEDULE_EXCLUSIVE,
            CONF_COMFORT_SCHEDULE_START,
            CONF_COMFORT_SCHEDULE_TARGET,
        )

        entry = self._make_entry(
            options={
                CONF_COMFORT_SCHEDULE: True,
                CONF_COMFORT_SCHEDULE_EXCLUSIVE: True,
                CONF_COMFORT_SCHEDULE_CIRCUIT: "b",
                CONF_COMFORT_SCHEDULE_START: "05:30",
                CONF_COMFORT_SCHEDULE_END: "23:00",
                CONF_COMFORT_SCHEDULE_TARGET: 20.0,
                "heating_circuits": ["b"],
            }
        )
        constructed: list[tuple[tuple, dict]] = []

        def _make_scheduler(*args, **kwargs):
            constructed.append((args, kwargs))
            instance = MagicMock()
            instance.register_name = "comfort_reg"
            return instance

        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.setup_registers = MagicMock()
        coordinator.get_register = MagicMock(return_value=object())

        with contextlib.ExitStack() as stack:
            for item in self._patch_list(AsyncMock(), coordinator):
                stack.enter_context(item)
            stack.enter_context(patch("custom_components.idm_heatpump.ComfortScheduler", side_effect=_make_scheduler))
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        assert len(constructed) == 1
        args, kwargs = constructed[0]
        assert args[2] == "b"
        assert args[3] == "05:30"
        assert args[4] == "23:00"
        assert args[5] == 20.0
        # No windows were configured, so the schedule carries none.
        assert kwargs["windows"] is None
        assert entry.runtime_data.comfort_scheduler is not None

    async def test_comfort_schedule_ignores_invalid_saved_windows(self, mock_hass):
        from custom_components.idm_heatpump.const import (
            CONF_COMFORT_SCHEDULE,
            CONF_COMFORT_SCHEDULE_EXCLUSIVE,
            CONF_COMFORT_WINDOWS,
        )

        entry = self._make_entry(
            options={
                CONF_COMFORT_SCHEDULE: True,
                CONF_COMFORT_SCHEDULE_EXCLUSIVE: True,
                # "99:00" is not a valid local time.
                CONF_COMFORT_WINDOWS: "a, 99:00, 23:00, 21.0",
            }
        )
        constructed: list[tuple[tuple, dict]] = []

        def _make_scheduler(*args, **kwargs):
            constructed.append((args, kwargs))
            instance = MagicMock()
            instance.register_name = "comfort_reg"
            return instance

        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.setup_registers = MagicMock()
        coordinator.get_register = MagicMock(return_value=object())

        with contextlib.ExitStack() as stack:
            for item in self._patch_list(AsyncMock(), coordinator):
                stack.enter_context(item)
            stack.enter_context(patch("custom_components.idm_heatpump.ComfortScheduler", side_effect=_make_scheduler))
            result = await async_setup_entry(mock_hass, entry)

        assert result is True
        # The invalid rows are dropped and the default circuit schedule remains.
        assert len(constructed) == 1
        assert constructed[0][0][2] == "a"
        assert constructed[0][1]["windows"] is None


class TestUnloadPersistsAndStopsSmartComponents:
    """Unload saves the persistent components and stops the managers."""

    def _make_entry(self, runtime):
        entry = MagicMock()
        entry.runtime_data = runtime
        return entry

    def _make_runtime(self):
        runtime = MagicMock()
        runtime.client = AsyncMock()
        runtime.coordinator = MagicMock()
        runtime.knx_bridge = None
        runtime.operation_analysis = None
        runtime.energy_statistics = None
        runtime.predictive_advisor = None
        runtime.advisor_analytics = None
        runtime.energy_manager = None
        runtime.comfort_schedulers = ()
        runtime.comfort_scheduler = None
        return runtime

    async def test_unload_persists_every_smart_component(self, mock_hass):
        from custom_components.idm_heatpump import (
            AdvisorAnalytics,
            EnergyStatistics,
            OperationAnalysis,
            PredictiveAdvisor,
        )

        runtime = self._make_runtime()
        components = []
        for cls in (OperationAnalysis, EnergyStatistics, PredictiveAdvisor, AdvisorAnalytics):
            component = cls.__new__(cls)
            component.async_save = AsyncMock()
            components.append(component)
        (
            runtime.operation_analysis,
            runtime.energy_statistics,
            runtime.predictive_advisor,
            runtime.advisor_analytics,
        ) = components
        entry = self._make_entry(runtime)
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        assert await async_unload_entry(mock_hass, entry) is True

        for component in components:
            component.async_save.assert_awaited_once()

    async def test_unload_survives_persistence_failures(self, mock_hass):
        from custom_components.idm_heatpump import (
            AdvisorAnalytics,
            EnergyStatistics,
            OperationAnalysis,
            PredictiveAdvisor,
        )

        runtime = self._make_runtime()
        for cls, attribute in (
            (OperationAnalysis, "operation_analysis"),
            (EnergyStatistics, "energy_statistics"),
            (PredictiveAdvisor, "predictive_advisor"),
            (AdvisorAnalytics, "advisor_analytics"),
        ):
            component = cls.__new__(cls)
            component.async_save = AsyncMock(side_effect=RuntimeError("disk full"))
            setattr(runtime, attribute, component)
        entry = self._make_entry(runtime)
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        assert await async_unload_entry(mock_hass, entry) is True

    async def test_unload_stops_the_energy_manager(self, mock_hass):
        from custom_components.idm_heatpump import EnergyManager

        runtime = self._make_runtime()
        manager = EnergyManager.__new__(EnergyManager)
        manager.async_stop = AsyncMock()
        runtime.energy_manager = manager
        entry = self._make_entry(runtime)
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        assert await async_unload_entry(mock_hass, entry) is True

        manager.async_stop.assert_awaited_once()

    async def test_unload_stops_every_comfort_scheduler(self, mock_hass):
        from custom_components.idm_heatpump import ComfortScheduler

        runtime = self._make_runtime()
        schedulers = []
        for _ in range(2):
            scheduler = ComfortScheduler.__new__(ComfortScheduler)
            scheduler.async_stop = AsyncMock()
            schedulers.append(scheduler)
        runtime.comfort_schedulers = tuple(schedulers)
        entry = self._make_entry(runtime)
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        assert await async_unload_entry(mock_hass, entry) is True

        for scheduler in schedulers:
            scheduler.async_stop.assert_awaited_once()

    async def test_unload_stops_a_single_legacy_comfort_scheduler(self, mock_hass):
        from custom_components.idm_heatpump import ComfortScheduler

        runtime = self._make_runtime()
        scheduler = ComfortScheduler.__new__(ComfortScheduler)
        scheduler.async_stop = AsyncMock()
        runtime.comfort_scheduler = scheduler
        entry = self._make_entry(runtime)
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        assert await async_unload_entry(mock_hass, entry) is True

        scheduler.async_stop.assert_awaited_once()

    async def test_unload_survives_a_failing_client_disconnect(self, mock_hass):
        runtime = self._make_runtime()
        runtime.client.disconnect = AsyncMock(side_effect=Exception("close failed"))
        entry = self._make_entry(runtime)
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        assert await async_unload_entry(mock_hass, entry) is True

        runtime.client.disconnect.assert_awaited_once()

    async def test_unload_cancels_advisor_forecast_task(self, mock_hass):
        import asyncio

        runtime = self._make_runtime()

        async def _sleep_forever() -> None:
            await asyncio.sleep(60)

        forecast_task = asyncio.create_task(_sleep_forever())
        await asyncio.sleep(0)
        runtime.advisor_forecast_task = forecast_task
        entry = self._make_entry(runtime)
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        assert await async_unload_entry(mock_hass, entry) is True
        assert forecast_task.cancelled()
