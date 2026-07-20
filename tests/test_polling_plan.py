"""Tests for entity-aware Modbus polling plans."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from custom_components.idm_heatpump import polling_plan


@dataclass
class _RegistryEntry:
    unique_id: str
    disabled_by: object | None = None


def _build(
    monkeypatch: pytest.MonkeyPatch,
    entries: list[_RegistryEntry],
    known: set[str],
) -> set[str] | None:
    monkeypatch.setattr(
        polling_plan.er,
        "async_entries_for_config_entry",
        lambda registry, entry_id: entries,
    )
    return polling_plan.build_required_register_names(object(), "entry", known)


def test_no_registry_entries_keep_full_initial_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _build(monkeypatch, [], {"outdoor_temp"}) is None


def test_enabled_register_entity_is_polled(monkeypatch: pytest.MonkeyPatch) -> None:
    required = _build(
        monkeypatch,
        [_RegistryEntry("entry_hp_flow_temp")],
        {"outdoor_temp", "hp_flow_temp", "hp_return_temp"},
    )

    assert required is not None
    assert "hp_flow_temp" in required
    assert "hp_return_temp" not in required
    assert "outdoor_temp" in required


def test_disabled_entity_is_not_polled(monkeypatch: pytest.MonkeyPatch) -> None:
    required = _build(
        monkeypatch,
        [_RegistryEntry("entry_hp_flow_temp", disabled_by="user")],
        {"outdoor_temp", "hp_flow_temp"},
    )

    assert required == {"outdoor_temp"}


def test_calculated_sensor_adds_all_source_registers(monkeypatch: pytest.MonkeyPatch) -> None:
    known = {
        "outdoor_temp",
        "hp_flow_temp",
        "hp_return_temp",
        "unrelated_service_value",
    }
    required = _build(
        monkeypatch,
        [_RegistryEntry("entry_calculated_hp_temperature_delta")],
        known,
    )

    assert required is not None
    assert {"hp_flow_temp", "hp_return_temp"} <= required
    assert "unrelated_service_value" not in required


def test_heating_climate_adds_current_target_mode_and_status(monkeypatch: pytest.MonkeyPatch) -> None:
    known = {
        "outdoor_temp",
        "hp_operating_mode",
        "hc_a_mode",
        "hc_a_room_setpoint_heat_normal",
        "hc_a_room_temp",
        "hc_b_mode",
    }
    required = _build(
        monkeypatch,
        [_RegistryEntry("entry_climate_hc_a")],
        known,
    )

    assert required is not None
    assert {
        "hc_a_mode",
        "hc_a_room_setpoint_heat_normal",
        "hc_a_room_temp",
        "hp_operating_mode",
    } <= required
    assert "hc_b_mode" not in required


def test_zone_climate_adds_room_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    known = {
        "outdoor_temp",
        "hp_operating_mode",
        "zm2_room4_mode",
        "zm2_room4_setpoint",
        "zm2_room4_temp",
    }
    required = _build(
        monkeypatch,
        [_RegistryEntry("entry_climate_zm2_room4")],
        known,
    )

    assert required is not None
    assert {
        "zm2_room4_mode",
        "zm2_room4_setpoint",
        "zm2_room4_temp",
    } <= required


def test_water_heater_and_internal_safety_registers_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    known = {
        "outdoor_temp",
        "internal_message",
        "system_mode",
        "dhw_temp_top",
        "dhw_setpoint",
        "hp_operating_mode",
        "hp_sum_alarm",
        "compressor_status_1",
        "compressor_status_2",
        "compressor_status_3",
        "compressor_status_4",
        "unused_register",
    }
    required = _build(
        monkeypatch,
        [_RegistryEntry("entry_water_heater")],
        known,
    )

    assert required is not None
    assert "dhw_temp_top" in required
    assert "dhw_setpoint" in required
    assert "hp_sum_alarm" in required
    assert "compressor_status_1" in required
    assert "unused_register" not in required
