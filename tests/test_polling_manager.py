"""Tests for dynamic entity-aware polling management."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump import polling_plan
from custom_components.idm_heatpump.coordinator import IdmCoordinator
from custom_components.idm_heatpump.polling_plan import (
    EntityAwarePollingManager,
    ensure_entity_aware_polling,
)


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

    assert {register.name for register in coordinator._registers} == {
        "outdoor_temp",
        "hp_flow_temp",
        "hp_return_temp",
    }
    assert coordinator._room_mode_registers == []

    registry.entries.append(_RegistryEntry("entry_zm1_room1_mode"))
    await manager._async_apply_plan(request_refresh=True)

    assert "zm1_room1_mode" in {register.name for register in coordinator._registers}
    assert [register.name for register in coordinator._room_mode_registers] == ["zm1_room1_mode"]
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


def test_ensure_rejects_magicmock_with_coordinator_spec() -> None:
    coordinator = MagicMock(spec=IdmCoordinator)
    coordinator._registers = [RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp")]

    assert isinstance(coordinator, IdmCoordinator)
    assert ensure_entity_aware_polling(coordinator) is None


class TestCalculatedSensorDependencies:
    """Derived sensors must keep their source registers inside the poll plan.

    Entity-aware polling drops every register no enabled entity asks for. A
    calculated sensor is not itself a register, so its sources are only polled
    because they are declared as its dependencies — a missing declaration
    leaves the sensor permanently unavailable as soon as the user disables the
    source entities.
    """

    def test_every_calculated_sensor_declares_its_sources(self) -> None:
        from custom_components.idm_heatpump.calculated_sensors import (
            CALCULATED_SENSOR_DEFINITIONS,
            FLOW_DEVIATION_DEFINITIONS,
        )

        for definition in (*CALCULATED_SENSOR_DEFINITIONS, *FLOW_DEVIATION_DEFINITIONS):
            declared = polling_plan._entity_dependencies(definition.key)
            assert declared == set(definition.sources), f"{definition.key} would lose its source registers"

    @staticmethod
    def _registry(unique_id: str) -> MagicMock:
        """Registry double shaped like the entity-registry stub in conftest."""
        registry = MagicMock()
        registry.entities = {unique_id: _RegistryEntry(unique_id)}
        return registry

    def test_cop_sources_are_required_without_their_own_entities(self) -> None:
        """The COP sensor alone must keep both power registers in the plan."""
        registry = self._registry("entry_calculated_cop")

        required = polling_plan.build_required_register_names(
            registry,
            "entry",
            {"power_consumption_hp", "thermal_power_flow_sensor", "outdoor_temp"},
        )

        assert {"power_consumption_hp", "thermal_power_flow_sensor"} <= required

    def test_flow_deviation_keeps_the_circuit_setpoint_register(self) -> None:
        registry = self._registry("entry_calculated_hc_a_flow_deviation")

        required = polling_plan.build_required_register_names(
            registry,
            "entry",
            {"hc_a_flow_temp", "hc_a_setpoint_flow_temp", "hc_b_flow_temp"},
        )

        assert {"hc_a_flow_temp", "hc_a_setpoint_flow_temp"} <= required
        assert "hc_b_flow_temp" not in required
