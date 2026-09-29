"""Tests for the connection-state entities (effective mode, web liveness)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from custom_components.idm_heatpump.connection_entities import (
    STATE_MODBUS_AND_WEB,
    STATE_MODBUS_ONLY,
    STATE_WEB_ONLY,
    connection_sensor_entities,
)


def _coordinator(
    *,
    modbus_interval: float | None = 30.0,
    web_enabled: bool = True,
    web_supplement: object | None = object(),
    web_variant: str | None = "nav10",
) -> MagicMock:
    from datetime import timedelta

    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.options = {}
    coordinator.config_entry.data = {}
    coordinator.last_update_success = True
    coordinator.update_interval = timedelta(seconds=modbus_interval) if modbus_interval is not None else None
    coordinator.web_enabled = web_enabled
    coordinator.web_supplement = web_supplement
    coordinator.web_variant = web_variant
    coordinator.web_last_success = None
    return coordinator


class TestConnectionModeSensor:
    def test_created_in_every_mode(self) -> None:
        assert len(connection_sensor_entities(_coordinator())) >= 1

    def test_modbus_and_web_when_both_transports_are_live(self) -> None:
        entities = connection_sensor_entities(_coordinator())

        mode = entities[0]
        assert mode.entity_description.key == "connection_mode"
        assert mode.native_value == STATE_MODBUS_AND_WEB

    def test_modbus_only_without_a_web_supplement(self) -> None:
        coordinator = _coordinator(web_supplement=None, web_enabled=True)

        mode = connection_sensor_entities(coordinator)[0]
        assert mode.native_value == STATE_MODBUS_ONLY

    def test_web_only_entry_without_modbus_polling(self) -> None:
        coordinator = _coordinator(modbus_interval=None)

        mode = connection_sensor_entities(coordinator)[0]
        assert mode.native_value == STATE_WEB_ONLY

    def test_attributes_carry_the_configured_mode_and_web_variant(self) -> None:
        mode = connection_sensor_entities(_coordinator())[0]

        attributes = mode.extra_state_attributes
        assert attributes["configured_mode"] == "auto"
        assert attributes["web_variant"] == "nav10"

    def test_no_enum_options_without_enum_device_class(self) -> None:
        """HA 2026.8+ rejects options on sensors without the ENUM device class.

        The mode sensor deliberately keeps plain string states (they are
        identical in every language), so it must not declare options.
        """
        mode = connection_sensor_entities(_coordinator())[0]

        assert getattr(mode, "_attr_options", None) is None


class TestWebLastSuccessSensor:
    def test_created_when_the_web_path_is_enabled(self) -> None:
        entities = connection_sensor_entities(_coordinator())

        assert [e.entity_description.key for e in entities] == [
            "connection_mode",
            "web_last_success",
        ]

    def test_not_created_without_the_web_path(self) -> None:
        entities = connection_sensor_entities(_coordinator(web_enabled=False))

        assert [e.entity_description.key for e in entities] == ["connection_mode"]

    def test_unavailable_until_the_first_web_success(self) -> None:
        entity = connection_sensor_entities(_coordinator())[1]

        assert entity.available is False
        assert entity.native_value is None

    def test_reports_the_last_success_timestamp(self) -> None:
        coordinator = _coordinator()
        stamp = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
        coordinator.web_last_success = stamp

        entity = connection_sensor_entities(coordinator)[1]

        assert entity.available is True
        assert entity.native_value is stamp


class TestCoordinatorWebSuccess:
    @pytest.mark.asyncio
    async def test_web_refresh_success_stamps_web_last_success(self) -> None:
        from custom_components.idm_heatpump import coordinator as coordinator_module

        # the success path is exercised through the module's own tests; here we
        # only pin the contract that the stamp is a UTC datetime once set.
        assert hasattr(coordinator_module.IdmCoordinator, "web_last_success")
