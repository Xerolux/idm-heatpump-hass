"""Tests for entity-aware Modbus polling plans."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump import polling_plan
from custom_components.idm_heatpump.polling_plan import (
    EntityAwarePollingManager,
    ensure_entity_aware_polling,
)


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


def test_pv_surplus_operation_keeps_or_sources_polled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Issue #353: every candidate source of the OR-shaped entity stays polled."""
    known = {
        "outdoor_temp",
        "pv_surplus",
        "smart_grid_status",
        "power_consumption_hp",
        "hp_operating_mode",
        "unrelated_service_value",
    }
    required = _build(
        monkeypatch,
        [_RegistryEntry("entry_calculated_pv_surplus_operation")],
        known,
    )

    assert required is not None
    assert {"pv_surplus", "smart_grid_status", "power_consumption_hp", "hp_operating_mode"} <= required
    assert "unrelated_service_value" not in required


def test_calculated_cop_keeps_both_thermal_power_sources_polled(monkeypatch: pytest.MonkeyPatch) -> None:
    known = {
        "outdoor_temp",
        "power_consumption_hp",
        "thermal_power_flow_sensor",
        "current_power",
        "unrelated_service_value",
    }
    required = _build(
        monkeypatch,
        [_RegistryEntry("entry_calculated_cop")],
        known,
    )

    assert required is not None
    assert {"power_consumption_hp", "thermal_power_flow_sensor", "current_power"} <= required
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


def test_water_heater_dependencies_cover_the_navigator_17_sensor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 1.x map has dhw_temp instead of dhw_temp_top (0.19.0-b16)."""
    known = {
        "outdoor_temp",
        "internal_message",
        "hp_operating_mode",
        "hp_sum_alarm",
        "dhw_temp",
        "dhw_setpoint",
    }
    required = _build(
        monkeypatch,
        [_RegistryEntry("entry_water_heater")],
        known,
    )

    assert required is not None
    assert "dhw_temp" in required
    assert "dhw_setpoint" in required
    # Absent from the 1.x map, so neither the always-required set nor the
    # entity dependency may resurrect it.
    assert "dhw_temp_top" not in required


# ---------------------------------------------------------------------------
# EntityAwarePollingManager: replan scheduling and early-out branches
# ---------------------------------------------------------------------------


class _PlanCoordinator:
    """Stands in for IdmCoordinator with the surface the plan manager uses."""

    def __init__(self, registers: list[RegisterDef]) -> None:
        self._registers = list(registers)
        self.alias_map: dict[int, list[str]] = {}
        self.externally_required_registers: frozenset[str] = frozenset()
        self.async_request_refresh = AsyncMock()
        self.applied: list[frozenset[str]] = []

    @property
    def active_registers(self) -> tuple[RegisterDef, ...]:
        return tuple(self._registers)

    def set_active_registers(self, registers: list[RegisterDef], *, total: int) -> None:
        self._registers = list(registers)
        self.applied.append(frozenset(register.name for register in registers))


def _patch_entity_registry(monkeypatch: pytest.MonkeyPatch, entries: list[_RegistryEntry]) -> None:
    monkeypatch.setattr(polling_plan.er, "async_get", lambda hass: object())
    monkeypatch.setattr(
        polling_plan.er,
        "async_entries_for_config_entry",
        lambda registry, entry_id: entries,
    )


def _plan_manager(
    monkeypatch: pytest.MonkeyPatch,
    entries: list[_RegistryEntry],
    registers: list[RegisterDef],
    *,
    debounce_seconds: float = 0.0,
) -> tuple[EntityAwarePollingManager, _PlanCoordinator]:
    _patch_entity_registry(monkeypatch, entries)
    hass = MagicMock()
    hass.async_create_task.side_effect = asyncio.ensure_future
    coordinator = _PlanCoordinator(registers)
    manager = EntityAwarePollingManager(
        hass,
        MagicMock(entry_id="entry"),
        coordinator,
        debounce_seconds=debounce_seconds,
    )
    return manager, coordinator


async def test_registry_event_without_a_string_entity_id_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _coordinator = _plan_manager(monkeypatch, [], [])

    manager._handle_registry_event(MagicMock(data={"entity_id": 123}))

    assert manager._refresh_task is None
    manager._hass.async_create_task.assert_not_called()


async def test_schedule_replan_cancels_a_pending_debounce_and_rearms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = [_RegistryEntry("entry_hp_flow_temp")]
    registers = [
        RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp"),
        RegisterDef(address=1050, datatype=DataType.FLOAT, name="hp_flow_temp"),
        RegisterDef(address=1052, datatype=DataType.FLOAT, name="hp_return_temp"),
    ]
    manager, coordinator = _plan_manager(
        monkeypatch,
        entries,
        registers,
        debounce_seconds=0.05,
    )

    manager.schedule_replan()
    first = manager._refresh_task
    assert first is not None

    manager.schedule_replan()  # cancels the queued debounce and re-arms it
    second = manager._refresh_task
    assert second is not None
    assert second is not first

    await asyncio.gather(first, second, return_exceptions=True)

    assert first.cancelled()
    # Only the surviving debounce applied a plan and asked for a refresh.
    assert coordinator.applied == [{"outdoor_temp", "hp_flow_temp"}]
    coordinator.async_request_refresh.assert_awaited_once()


async def test_apply_plan_keeps_the_plan_when_nothing_is_selectable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = [_RegistryEntry("entry_hp_flow_temp")]
    registers = [RegisterDef(address=1670, datatype=DataType.FLOAT, name="variable_input")]
    manager, coordinator = _plan_manager(monkeypatch, entries, registers)

    await manager._async_apply_plan(request_refresh=True)

    # No always-required register is known and no entity demands one, so the
    # plan stays untouched rather than polling an empty register set.
    assert coordinator.applied == []
    coordinator.async_request_refresh.assert_not_awaited()


async def test_apply_plan_skips_the_update_when_the_selection_did_not_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = [_RegistryEntry("entry_hp_flow_temp")]
    registers = [
        RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp"),
        RegisterDef(address=1050, datatype=DataType.FLOAT, name="hp_flow_temp"),
        RegisterDef(address=1052, datatype=DataType.FLOAT, name="hp_return_temp"),
    ]
    manager, coordinator = _plan_manager(monkeypatch, entries, registers)

    await manager._async_apply_plan(request_refresh=True)
    await manager._async_apply_plan(request_refresh=True)

    # The second pass found the plan already in place and changed nothing.
    assert coordinator.applied == [{"outdoor_temp", "hp_flow_temp"}]
    coordinator.async_request_refresh.assert_awaited_once()


# ---------------------------------------------------------------------------
# ensure_entity_aware_polling: only a genuine coordinator gets a manager
# ---------------------------------------------------------------------------


def _real_coordinator(
    mock_hass: MagicMock,
    mock_config_entry: MagicMock,
    registers: list[RegisterDef] | None = None,
):
    from custom_components.idm_heatpump.coordinator import IdmCoordinator

    client = MagicMock()
    client.read_batch = AsyncMock(return_value={})
    client.write_register = AsyncMock()
    coordinator = IdmCoordinator(
        hass=mock_hass,
        config_entry=mock_config_entry,
        client=client,
        scan_interval=timedelta(seconds=10),
        sensor_descriptions=[],
        binary_sensor_descriptions=[],
        number_descriptions=[],
        select_descriptions=[],
        switch_descriptions=[],
    )
    if registers is not None:
        coordinator._registers = list(registers)
        coordinator._register_by_name = {register.name: register for register in registers}
    return coordinator


async def test_ensure_returns_none_without_a_config_entry(
    mock_hass: MagicMock,
    mock_config_entry: MagicMock,
) -> None:
    coordinator = _real_coordinator(mock_hass, mock_config_entry)
    coordinator.config_entry = None

    assert ensure_entity_aware_polling(coordinator) is None
    assert coordinator.entity_aware_polling_manager is None


async def test_ensure_returns_none_without_active_registers(
    mock_hass: MagicMock,
    mock_config_entry: MagicMock,
) -> None:
    coordinator = _real_coordinator(mock_hass, mock_config_entry)

    assert ensure_entity_aware_polling(coordinator) is None
    assert coordinator.entity_aware_polling_manager is None


async def test_ensure_creates_exactly_one_manager_for_a_real_coordinator(
    mock_hass: MagicMock,
    mock_config_entry: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_entity_registry(monkeypatch, [])
    mock_hass.async_create_task.side_effect = asyncio.ensure_future
    coordinator = _real_coordinator(
        mock_hass,
        mock_config_entry,
        [RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp")],
    )

    manager = ensure_entity_aware_polling(coordinator)
    assert manager is not None
    assert coordinator.entity_aware_polling_manager is manager

    # The attached manager is reused rather than replaced.
    assert ensure_entity_aware_polling(coordinator) is manager

    await manager.async_shutdown()
