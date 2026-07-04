"""Tests for __init__.py (async_setup, async_setup_entry, async_unload_entry)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers import issue_registry as ir

from custom_components.idm_heatpump import (
    IdmHeatpumpData,
    async_migrate_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
    async_reload_entry,
    _detect_model_info,
    _model_info_from_detected_name,
)
from custom_components.idm_heatpump.const import MODEL
from custom_components.idm_heatpump.web_data import IdmWebSupplement
from idm_heatpump import IdmModelInfo
from idm_heatpump.const import MODEL_UNKNOWN


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
            version=1,
            minor_version=2,
        )

    async def test_updates_entry_version_when_no_legacy_entities_exist(self, mock_hass):
        entry = MagicMock()
        entry.entry_id = "entry-empty"
        entry.version = 1
        entry.minor_version = 0
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
            version=1,
            minor_version=2,
        )

    async def test_migrates_multiple_legacy_unique_id_prefixes(self, mock_hass):
        entry = MagicMock()
        entry.entry_id = "entry-multi"
        entry.version = 1
        entry.minor_version = 0
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
        entry.minor_version = 2

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


class TestAsyncUnloadEntry:
    async def test_unloads_platforms(self, mock_hass):
        entry = MagicMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = AsyncMock()
        entry.runtime_data.client.disconnect = AsyncMock()
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        with patch(
            "custom_components.idm_heatpump.services.async_unload_services",
            AsyncMock(),
        ):
            result = await async_unload_entry(mock_hass, entry)

        assert result is True
        mock_hass.config_entries.async_unload_platforms.assert_called_once()

    async def test_disconnects_client_on_success(self, mock_hass):
        entry = MagicMock()
        mock_client = AsyncMock()
        mock_client.disconnect = AsyncMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.client = mock_client
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        with patch(
            "custom_components.idm_heatpump.services.async_unload_services",
            AsyncMock(),
        ):
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


class TestAsyncReloadEntry:
    async def test_calls_async_reload(self, mock_hass):
        entry = MagicMock()
        entry.entry_id = "test_id"
        await async_reload_entry(mock_hass, entry)
        mock_hass.config_entries.async_reload.assert_called_once_with("test_id")


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
            "web_pin_missing",
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
            call.args[:3] == (mock_hass, "idm_heatpump", "web_pin_missing")
            for call in ir.async_create_issue.call_args_list
        )
        ir.async_delete_issue.assert_any_call(mock_hass, "idm_heatpump", "web_pin_missing")

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

    async def test_separate_web_host_is_used_for_web_supplement(self, mock_hass):
        """Proxy setups can use one host for Modbus and another for Navigator web."""
        entry = self._make_entry(
            data_override={
                "web_pin": "2634",
                "web_host": "192.168.178.103",
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

        read_web.assert_awaited_once_with("192.168.178.103", "2634", model_hint="Navigator 2.0 / 10")
        assert captured_kwargs.get("web_host") == "192.168.178.103"

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
        with ctx, pytest.raises(Exception):
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

    async def test_selected_circuits_zones_and_cascade_drive_description_builders(self, mock_hass):
        entry = self._make_entry(
            options_override={
                "heating_circuits": ["a", "c"],
                "zone_count": 2,
                "zone_rooms": {0: 1, 1: 3},
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
        )

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

    def test_builds_navigator_20_model_info_from_detected_name(self):
        model_info = _model_info_from_detected_name("Navigator 2.0", ["a", "b"], 0, False)

        assert model_info is not None
        assert model_info.model_name == "Navigator 2.0"
        assert model_info.active_heating_circuits == ["A", "B"]
        assert model_info.has_cascade is False


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
        mock_coordinator.setup_registers.assert_called_once_with(["a"], 0, {}, False, model_info=model_info)

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
        mock_coordinator.setup_registers.assert_called_once_with(["a"], 0, {}, False, model_info=model_info)

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

    async def test_modbus_detected_navigator_20_overrides_conflicting_web_navigator_10(self, mock_hass):
        entry = self._make_entry()
        entry.data = {**entry.data, "web_pin": "2634"}
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

        assert captured_kwargs["model_name"] == "Navigator 2.0"
        assert captured_kwargs["firmware_version"] is None
        assert captured_kwargs["model_info"] is model_info
        mock_hass.config_entries.async_update_entry.assert_any_call(
            entry,
            data={**entry.data, "detected_navigator_version": "Navigator 2.0"},
        )

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

    async def test_detection_failure_passes_none_model_info_to_platforms(self, mock_hass):
        """When detect_model fails and no stored data exists, platform
        functions must receive model_info=None so they include all registers
        rather than incorrectly assuming Navigator 10."""
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
        assert captured_model_info[0] is None

    async def test_detection_failure_with_stored_navigator_version_builds_fallback_model_info(self, mock_hass):
        """When detect_model fails but stored detected_navigator_version is
        "Navigator 2.0", platform functions must receive a Navigator 2.0
        model_info via _model_info_from_detected_name()."""
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
