"""Tests for restart-safe compressor and operating-mode analysis."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump import operation_analysis as module
from custom_components.idm_heatpump.operation_analysis import OperationAnalysis


class FakeStore:
    """In-memory Home Assistant Store replacement."""

    def __init__(self, loaded: dict[str, Any] | None = None) -> None:
        self.loaded = loaded
        self.saved: dict[str, Any] | None = None
        self.delayed: dict[str, Any] | None = None

    async def async_load(self) -> dict[str, Any] | None:
        return self.loaded

    async def async_save(self, data: dict[str, Any]) -> None:
        self.saved = data

    def async_delay_save(self, data_func, delay: float) -> None:
        assert delay > 0
        self.delayed = data_func()


def _registers() -> dict[str, RegisterDef]:
    registers = {
        f"compressor_status_{index}": RegisterDef(
            address=1099 + index,
            datatype=DataType.UCHAR,
            name=f"compressor_status_{index}",
            binary=True,
        )
        for index in range(1, 5)
    }
    registers["hp_operating_mode"] = RegisterDef(
        address=1090,
        datatype=DataType.UCHAR,
        name="hp_operating_mode",
        enum_options={0: "Standby", 1: "Heating", 2: "Cooling", 4: "DHW", 8: "Defrost"},
    )
    return registers


def _analysis(monkeypatch, *, loaded: dict[str, Any] | None = None) -> tuple[OperationAnalysis, FakeStore]:
    fake_store = FakeStore(loaded)
    monkeypatch.setattr(module, "Store", lambda *args, **kwargs: fake_store)
    registers = _registers()
    analysis = OperationAnalysis(
        object(),
        "entry",
        registers.get,
        short_cycle_minutes=15,
        expected_poll_interval=10,
    )
    return analysis, fake_store


def _snapshot(*, compressor: int = 0, mode: int = 0) -> dict[str, int]:
    return {
        "compressor_status_1": compressor,
        "compressor_status_2": 0,
        "compressor_status_3": 0,
        "compressor_status_4": 0,
        "hp_operating_mode": mode,
    }


@pytest.mark.asyncio
async def test_first_snapshot_establishes_baseline_without_counting(monkeypatch) -> None:
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    now = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)

    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=now)

    assert analysis.total_compressor_starts == 0
    assert analysis.last_compressor_start is None
    assert analysis.current_cycle_started == now


@pytest.mark.asyncio
async def test_observed_off_to_on_edge_counts_one_start(monkeypatch) -> None:
    analysis, store = _analysis(monkeypatch)
    await analysis.async_load()
    start = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(), set(), now=start)

    analysis.process_snapshot(
        _snapshot(compressor=1, mode=1),
        set(),
        now=start + timedelta(seconds=10),
    )

    assert analysis.total_compressor_starts == 1
    assert analysis.compressor_starts_today(start + timedelta(seconds=10)) == 1
    assert analysis.compressor_starts_last_hours(2, start + timedelta(seconds=10)) == 1
    assert store.delayed is not None


@pytest.mark.asyncio
async def test_restart_reconciliation_does_not_invent_start(monkeypatch) -> None:
    loaded = {
        "total_compressor_starts": 7,
        "compressor_on": False,
        "defrost_on": False,
        "compressor_start_events": [],
        "defrost_start_events": [],
    }
    analysis, _store = _analysis(monkeypatch, loaded=loaded)
    await analysis.async_load()
    now = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)

    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=now)

    assert analysis.total_compressor_starts == 7
    assert analysis.last_compressor_start is None
    assert analysis.current_cycle_started == now


@pytest.mark.asyncio
async def test_continuing_cycle_survives_restart(monkeypatch) -> None:
    started = datetime(2026, 7, 20, 7, 45, tzinfo=UTC)
    loaded = {
        "compressor_on": True,
        "defrost_on": False,
        "current_cycle_started": started.isoformat(),
        "compressor_start_events": [],
        "defrost_start_events": [],
    }
    analysis, _store = _analysis(monkeypatch, loaded=loaded)
    await analysis.async_load()

    analysis.process_snapshot(
        _snapshot(compressor=1, mode=1),
        set(),
        now=started + timedelta(minutes=15),
    )

    assert analysis.current_cycle_started == started
    assert analysis.current_cycle_minutes(started + timedelta(minutes=15)) == 15.0


@pytest.mark.asyncio
async def test_completed_cycles_feed_last_and_average_duration(monkeypatch) -> None:
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    start = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(), set(), now=start)
    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=start + timedelta(minutes=1))
    analysis.process_snapshot(_snapshot(), set(), now=start + timedelta(minutes=11))
    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=start + timedelta(minutes=20))
    analysis.process_snapshot(_snapshot(), set(), now=start + timedelta(minutes=40))

    assert analysis.last_cycle_duration == 20 * 60
    assert analysis.average_cycle_minutes() == 15.0
    assert analysis.last_cycle_was_short is False


@pytest.mark.asyncio
async def test_short_cycle_warning_uses_configured_threshold(monkeypatch) -> None:
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    start = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(), set(), now=start)
    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=start + timedelta(minutes=1))
    analysis.process_snapshot(_snapshot(), set(), now=start + timedelta(minutes=10))

    assert analysis.last_cycle_duration == 9 * 60
    assert analysis.last_cycle_was_short is True


@pytest.mark.asyncio
async def test_defrost_false_to_true_edge_counts_once(monkeypatch) -> None:
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    start = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(mode=1), set(), now=start)
    analysis.process_snapshot(_snapshot(mode=8), set(), now=start + timedelta(minutes=1))
    analysis.process_snapshot(_snapshot(mode=8), set(), now=start + timedelta(minutes=2))

    assert analysis.total_defrost_starts == 1
    assert analysis.defrost_starts_today(start + timedelta(minutes=2)) == 1
    assert analysis.last_defrost_start == start + timedelta(minutes=1)


@pytest.mark.asyncio
async def test_long_communication_gap_is_not_assigned_to_previous_mode(monkeypatch) -> None:
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    start = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(mode=1), set(), now=start)
    analysis.process_snapshot(_snapshot(mode=1), set(), now=start + timedelta(seconds=10))
    analysis.process_snapshot(_snapshot(mode=4), set(), now=start + timedelta(minutes=5))
    analysis.process_snapshot(_snapshot(mode=4), set(), now=start + timedelta(minutes=5, seconds=10))

    assert analysis.mode_durations["heating"] == 10
    assert analysis.mode_durations["dhw"] == 10
    assert analysis.operating_share("heating") == 50.0
    assert analysis.operating_share("dhw") == 50.0


@pytest.mark.asyncio
async def test_unused_sources_do_not_change_state(monkeypatch) -> None:
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    now = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)

    analysis.process_snapshot(
        _snapshot(compressor=1, mode=8),
        {"compressor_status_1", "hp_operating_mode"},
        now=now,
    )

    assert analysis.total_compressor_starts == 0
    assert analysis.total_defrost_starts == 0
    assert analysis.current_cycle_started is None


@pytest.mark.asyncio
async def test_any_compressor_stage_marks_aggregate_running(monkeypatch) -> None:
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    start = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(), set(), now=start)
    data = _snapshot()
    data["compressor_status_3"] = 1

    analysis.process_snapshot(data, set(), now=start + timedelta(seconds=10))

    assert analysis.total_compressor_starts == 1


@pytest.mark.asyncio
async def test_async_save_serializes_observations(monkeypatch) -> None:
    analysis, store = _analysis(monkeypatch)
    await analysis.async_load()
    now = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(), set(), now=now)

    await analysis.async_save()

    assert store.saved is not None
    assert store.saved["total_compressor_starts"] == 0
    assert store.saved["compressor_on"] is False
