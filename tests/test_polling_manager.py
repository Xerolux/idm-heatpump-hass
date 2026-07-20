"""Tests for dynamic entity-aware polling management."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump import polling_plan
from custom_components.idm_heatpump.polling_plan import EntityAwarePollingManager


@dataclass
class _RegistryEntry:
    unique_id: str
    disabled_by: object | None = None
    config_entry_id: str = "entry"


class _Registry:
    def __init__(self, entries: list[_RegistryEntry]) -> None:
        self.entries = entries

    def async_get(self, entity_id: str):
        return None


class _Coordinator:
    def __init__(self) -> None:
        self._registers = [
            RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp"),
            RegisterDef(address=1050, datatype=DataType.FLOAT, name="hp_flow_temp"),
            RegisterDef(address=1052, datatype=DataType.FLOAT, name="hp_return_temp"),
            RegisterDef(address=2000, datatype=DataType.UCHAR, name="zm1_room1_mode"),
            RegisterDef(address=2001, datatype=DataType.FLOAT, name="zm1_room1_temp"),
        ]
        self._room_mode_registers = [self._registers[3]]
        self._alias_map = {1050: ["hp_flow_temp", "hp_return_temp"]}
        self.async_request_refresh = AsyncMock()


@pytest.mark.asyncio
async def test_manager_reduces_and_reexpands_polling_plan(monkeypatch) -> None:
    registry = _Registry([_RegistryEntry("entry_hp_flow_temp")])
    monkeypatch.setattr(polling_plan.er, "async_get", lambda hass: registry)
    monkeypatch.setattr(
        polling_plan.er,
        "async_entries_for_config_entry",
        lambda current, entry_id: current.entries,
    )

    coordinator = _Coordinator()
    entry = MagicMock()
    entry.entry_id = "entry"
    manager = EntityAwarePollingManager(MagicMock(), entry, coordinator)

    await manager._async_apply_plan(request_refresh=False)

    # Alias names stay together and unrelated zone registers are removed.
    assert {register.name for register in coordinator._registers} == {
        "outdoor_temp",
        "hp_flow_temp",
        "hp_return_temp",
    }
    assert coordinator._room_mode_registers == []

    registry.entries.append(_RegistryEntry("entry_zm1_room1_mode"))
    await manager._async_apply_plan(request_refresh=True)

    assert "zm1_room1_mode" in {register.name for register in coordinator._registers}
    assert [register.name for register in coordinator._room_mode_registers] == [
        "zm1_room1_mode"
    ]
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_manager_keeps_full_plan_without_registry_entries(monkeypatch) -> None:
    registry = _Registry([])
    monkeypatch.setattr(polling_plan.er, "async_get", lambda hass: registry)
    monkeypatch.setattr(
        polling_plan.er,
        "async_entries_for_config_entry",
        lambda current, entry_id: current.entries,
    )

    coordinator = _Coordinator()
    entry = MagicMock(entry_id="entry")
    manager = EntityAwarePollingManager(MagicMock(), entry, coordinator)

    await manager._async_apply_plan(request_refresh=True)

    assert len(coordinator._registers) == 5
    coordinator.async_request_refresh.assert_not_awaited()
