"""Tests for the Navigator 10 status/overview entities (controller clock)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from idm_heatpump import IdmWebStatus

from custom_components.idm_heatpump.web_data import IdmWebSupplement
from custom_components.idm_heatpump.web_status_entities import web_status_sensor_entities


def _coordinator(status: IdmWebStatus | None, variant: str = "nav10") -> MagicMock:
    coordinator = MagicMock()
    coordinator.web_supplement = IdmWebSupplement(web_variant=variant, status=status)
    coordinator.config_entry.options = {"heating_circuits": ["a"]}
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.title = "IDM"
    coordinator.model_name = "Navigator 10"
    coordinator.firmware_version = None
    coordinator.last_update_success = True
    return coordinator


def _live_status() -> IdmWebStatus:
    return IdmWebStatus(
        json_version=11,
        userlevel=0,
        language="de",
        notification_count=2,
        timestamp_ms=1790576788000,
        frost_protection_active=False,
        network=True,
        authentication_enabled=True,
    )


def test_entity_is_created_for_nav10_only() -> None:
    assert len(web_status_sensor_entities(_coordinator(_live_status()))) == 1
    # The variant alone creates the entity; without a frame it stays unavailable.
    assert len(web_status_sensor_entities(_coordinator(None))) == 1
    assert web_status_sensor_entities(_coordinator(None, variant="nav20")) == []


def test_native_value_is_the_controller_clock() -> None:
    entity = web_status_sensor_entities(_coordinator(_live_status()))[0]

    assert entity.native_value == datetime(2026, 9, 28, 6, 26, 28, tzinfo=UTC)


def test_entity_is_unavailable_without_a_status_frame() -> None:
    entity = web_status_sensor_entities(_coordinator(None))[0]

    assert entity.available is False
    assert entity.native_value is None
    assert entity.extra_state_attributes == {}


def test_attributes_carry_the_support_relevant_facts() -> None:
    entity = web_status_sensor_entities(_coordinator(_live_status()))[0]

    attributes = entity.extra_state_attributes
    assert attributes["json_version"] == 11
    assert attributes["userlevel"] == 0
    assert attributes["language"] == "de"
    assert attributes["notification_count"] == 2
    assert attributes["frost_protection_active"] is False
    assert attributes["network"] is True
    assert attributes["authentication_enabled"] is True


def test_a_missing_timestamp_yields_no_state() -> None:
    entity = web_status_sensor_entities(_coordinator(IdmWebStatus(json_version=11)))[0]

    assert entity.available is True
    assert entity.native_value is None
