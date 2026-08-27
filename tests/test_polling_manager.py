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


class TestPollingManagerLifecycle:
    """Setup, registry events and shutdown of the entity-aware polling manager.

    These paths run entirely in the background, so a failure here shows up as
    "some entities stopped updating" rather than as an error — they need to be
    pinned by tests.
    """

    def _manager(self, monkeypatch, registry, *, hass=None):
        monkeypatch.setattr(polling_plan.er, "async_get", lambda hass: registry)
        monkeypatch.setattr(
            polling_plan.er,
            "async_entries_for_config_entry",
            lambda current, entry_id: current.entries,
        )
        hass = hass or MagicMock()
        entry = MagicMock()
        entry.entry_id = "entry"
        coordinator = _Coordinator()
        manager = EntityAwarePollingManager(hass, entry, coordinator, debounce_seconds=0)
        return manager, coordinator, entry, hass

    @pytest.mark.asyncio
    async def test_setup_applies_the_plan_and_listens_for_registry_changes(self, monkeypatch) -> None:
        import asyncio

        registry = _Registry([_RegistryEntry("entry_hp_flow_temp")])
        hass = MagicMock()
        hass.async_create_task.side_effect = asyncio.ensure_future
        unsub = MagicMock()
        hass.bus.async_listen = MagicMock(return_value=unsub)
        manager, coordinator, entry, _hass = self._manager(monkeypatch, registry, hass=hass)

        manager.schedule_setup()
        task = manager._setup_task
        assert task is not None
        manager.schedule_setup()  # a second call must not start a second setup
        assert manager._setup_task is task
        await task

        assert manager._unsub_registry is unsub
        assert {register.name for register in coordinator._registers} == {
            "outdoor_temp",
            "hp_flow_temp",
            "hp_return_temp",
        }
        entry.async_on_unload.assert_called_once()

        await manager.async_shutdown()
        unsub.assert_called_once()
        assert manager._unsub_registry is None

    @pytest.mark.asyncio
    async def test_registry_events_for_other_entries_are_ignored(self, monkeypatch) -> None:
        registry = _Registry([_RegistryEntry("entry_hp_flow_temp")])
        registry.async_get = lambda entity_id: MagicMock(config_entry_id="other-entry")
        manager, _coordinator, _entry, hass = self._manager(monkeypatch, registry)

        manager._handle_registry_event(MagicMock(data={"entity_id": "sensor.foreign"}))

        hass.async_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_registry_events_debounce_into_one_refresh(self, monkeypatch) -> None:
        import asyncio

        registry = _Registry([_RegistryEntry("entry_hp_flow_temp")])
        registry.async_get = lambda entity_id: MagicMock(config_entry_id="entry")
        hass = MagicMock()
        hass.async_create_task.side_effect = asyncio.ensure_future
        manager, coordinator, _entry, _hass = self._manager(monkeypatch, registry, hass=hass)

        manager._handle_registry_event(MagicMock(data={"entity_id": "sensor.idm_flow"}))
        first = manager._refresh_task
        manager._handle_registry_event(MagicMock(data={"entity_id": "sensor.idm_flow"}))
        assert first is not None and first.cancelled() or first.done() or manager._refresh_task is not first

        task = manager._refresh_task
        assert task is not None
        await asyncio.gather(task, return_exceptions=True)

        assert {register.name for register in coordinator._registers} == {
            "outdoor_temp",
            "hp_flow_temp",
            "hp_return_temp",
        }

    @pytest.mark.asyncio
    async def test_shutdown_cancels_pending_work(self, monkeypatch) -> None:
        import asyncio

        registry = _Registry([_RegistryEntry("entry_hp_flow_temp")])
        hass = MagicMock()
        hass.async_create_task.side_effect = asyncio.ensure_future
        manager, _coordinator, _entry, _hass = self._manager(monkeypatch, registry, hass=hass)
        manager._debounce_seconds = 30

        manager.schedule_setup()
        manager._handle_registry_event(MagicMock(data={"entity_id": None}))
        setup_task = manager._setup_task
        refresh_task = manager._refresh_task

        await manager.async_shutdown()

        assert setup_task is not None and setup_task.cancelled()
        assert refresh_task is not None and refresh_task.cancelled()
        assert manager._setup_task is None
        assert manager._refresh_task is None

    @pytest.mark.asyncio
    async def test_unload_schedules_the_shutdown(self, monkeypatch) -> None:
        import asyncio

        registry = _Registry([])
        hass = MagicMock()
        hass.async_create_task.side_effect = asyncio.ensure_future
        manager, _coordinator, _entry, _hass = self._manager(monkeypatch, registry, hass=hass)

        manager._schedule_shutdown()

        assert hass.async_create_task.call_count == 1
        await asyncio.sleep(0)

    def test_entries_of_other_config_entries_are_skipped(self, monkeypatch) -> None:
        monkeypatch.setattr(
            polling_plan.er,
            "async_entries_for_config_entry",
            lambda registry, entry_id: [
                _RegistryEntry("other_entry_hp_flow_temp"),
                _RegistryEntry(unique_id=None),  # type: ignore[arg-type]
            ],
        )

        required = polling_plan.build_required_register_names(object(), "entry", {"hp_flow_temp"})

        assert required == set()
