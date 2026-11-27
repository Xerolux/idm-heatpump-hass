"""Tests for restart-safe compressor and operating-mode analysis."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
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
        self._delayed: Callable[[], dict[str, Any]] | None = None
        self.scheduled = 0

    @property
    def delayed(self) -> dict[str, Any] | None:
        return self._delayed() if self._delayed is not None else None

    async def async_load(self) -> dict[str, Any] | None:
        return self.loaded

    async def async_save(self, data: dict[str, Any]) -> None:
        self.saved = data

    def async_delay_save(self, data_func, delay: float) -> None:
        assert delay > 0
        self.scheduled += 1
        self._delayed = data_func


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
    registers["hp_sum_alarm"] = RegisterDef(
        address=1091,
        datatype=DataType.UCHAR,
        name="hp_sum_alarm",
        binary=True,
    )
    registers["dhw_demand"] = RegisterDef(
        address=1093,
        datatype=DataType.UCHAR,
        name="dhw_demand",
        binary=True,
    )
    registers["dhw_temp_top"] = RegisterDef(
        address=1014,
        datatype=DataType.FLOAT,
        name="dhw_temp_top",
    )
    registers["dhw_charge_off_temp"] = RegisterDef(
        address=1034,
        datatype=DataType.UCHAR,
        name="dhw_charge_off_temp",
    )
    return registers


def _analysis(
    monkeypatch,
    *,
    loaded: dict[str, Any] | None = None,
    expected_poll_interval: float = 10,
) -> tuple[OperationAnalysis, FakeStore]:
    fake_store = FakeStore(loaded)
    monkeypatch.setattr(module, "Store", lambda *args, **kwargs: fake_store)
    registers = _registers()
    analysis = OperationAnalysis(
        object(),
        "entry",
        registers.get,
        short_cycle_minutes=15,
        expected_poll_interval=expected_poll_interval,
    )
    return analysis, fake_store


def _dhw_analysis(
    monkeypatch,
    *,
    loaded: dict[str, Any] | None = None,
) -> tuple[OperationAnalysis, FakeStore]:
    """Analysis with a ten-minute poll cadence, as a DHW charge cycle sees it (#713)."""
    return _analysis(monkeypatch, loaded=loaded, expected_poll_interval=600)


def _snapshot(*, compressor: int = 0, mode: int = 0) -> dict[str, int]:
    return {
        "compressor_status_1": compressor,
        "compressor_status_2": 0,
        "compressor_status_3": 0,
        "compressor_status_4": 0,
        "hp_operating_mode": mode,
    }


def _dhw_snapshot(*, demand: int, top: float = 48.0, charge_off: float = 50.0) -> dict[str, Any]:
    """One snapshot of a Navigator-10 style plant with charge hysteresis (#713)."""
    return {
        **_snapshot(mode=4 if demand else 0),
        "dhw_demand": demand,
        "dhw_temp_top": top,
        "dhw_charge_off_temp": charge_off,
    }


@pytest.mark.asyncio
async def test_alarm_edges_persist_and_restart_reconciles_without_false_event(monkeypatch) -> None:
    analysis, store = _analysis(monkeypatch)
    assert analysis.supports_alarm is True
    now = datetime(2026, 9, 17, 8, tzinfo=UTC)
    analysis.process_snapshot({**_snapshot(), "hp_sum_alarm": 0}, set(), now=now)
    for minute, value in enumerate((1, 1, 0, 1, 0, 1), start=1):
        analysis.process_snapshot({**_snapshot(), "hp_sum_alarm": value}, set(), now=now + timedelta(minutes=minute))
    assert analysis.total_alarm_starts == 3
    assert analysis.alarm_starts_last_days(7, now + timedelta(minutes=6)) == 3
    assert store.delayed is not None

    restarted, _ = _analysis(monkeypatch, loaded=store.delayed)
    await restarted.async_load()
    restarted.process_snapshot({**_snapshot(), "hp_sum_alarm": 1}, set(), now=now + timedelta(minutes=7))
    assert restarted.total_alarm_starts == 3
    restarted.process_snapshot({**_snapshot(), "hp_sum_alarm": 0}, set(), now=now + timedelta(minutes=8))
    restarted.process_snapshot({**_snapshot(), "hp_sum_alarm": 1}, set(), now=now + timedelta(minutes=9))
    assert restarted.total_alarm_starts == 4


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
async def test_defrost_run_is_not_a_compressor_cycle(monkeypatch) -> None:
    """Replay a Navigator 10 defrost as recorded in the field (#757).

    The compressor status drops when the defrost starts, runs for about five
    minutes in defrost and drops again before heating resumes. Only the two
    heating runs are cycles; the defrost run belongs to the defrost counters.
    """
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    start = datetime(2026, 11, 27, 15, 37, tzinfo=UTC)
    defrost = start + timedelta(minutes=96)
    analysis.process_snapshot(_snapshot(mode=1), set(), now=start)
    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=start + timedelta(minutes=1))

    # The defrost starts: the heating cycle ends, the compressor restarts in defrost.
    analysis.process_snapshot(_snapshot(mode=8), set(), now=defrost)
    analysis.process_snapshot(_snapshot(compressor=1, mode=8), set(), now=defrost + timedelta(seconds=63))
    assert analysis.total_compressor_starts == 1
    assert analysis.current_cycle_minutes(defrost + timedelta(minutes=2, seconds=63)) == 0.0

    # The defrost ends and heating resumes.
    analysis.process_snapshot(_snapshot(mode=1), set(), now=defrost + timedelta(minutes=6, seconds=7))
    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=defrost + timedelta(minutes=9, seconds=21))

    assert analysis.total_compressor_starts == 2
    assert analysis.total_defrost_starts == 1
    assert analysis.completed_cycle_durations == [95 * 60]
    assert analysis.last_cycle_duration == 95 * 60
    assert analysis.last_cycle_was_short is False
    assert analysis.current_cycle_minutes(defrost + timedelta(minutes=19, seconds=21)) == 10.0


@pytest.mark.asyncio
async def test_restart_during_a_defrost_run_does_not_invent_a_cycle(monkeypatch) -> None:
    """A defrost run in progress at startup is still no cycle when it ends."""
    loaded = {
        "compressor_on": True,
        "defrost_on": True,
        "compressor_start_events": [],
        "defrost_start_events": [],
        "cycle_accounting": 2,
    }
    analysis, _store = _analysis(monkeypatch, loaded=loaded)
    await analysis.async_load()
    now = datetime(2026, 11, 27, 15, 40, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(compressor=1, mode=8), set(), now=now)
    analysis.process_snapshot(_snapshot(mode=1), set(), now=now + timedelta(minutes=3))

    assert analysis.total_compressor_starts == 0
    assert analysis.completed_cycle_durations == []
    assert analysis.last_cycle_duration is None
    assert analysis.last_cycle_was_short is None


@pytest.mark.asyncio
async def test_run_continuing_from_defrost_becomes_a_cycle_without_a_start(monkeypatch) -> None:
    """A unit that keeps the compressor running from the defrost into heating."""
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    start = datetime(2026, 11, 27, 15, 37, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(mode=1), set(), now=start)
    analysis.process_snapshot(_snapshot(compressor=1, mode=8), set(), now=start + timedelta(seconds=60))

    heating = start + timedelta(minutes=6)
    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=heating)
    assert analysis.current_cycle_minutes(heating) == 0.0
    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=heating + timedelta(minutes=1))
    assert analysis.current_cycle_minutes(heating + timedelta(minutes=1)) == 1.0
    analysis.process_snapshot(_snapshot(mode=1), set(), now=heating + timedelta(minutes=40))

    assert analysis.total_compressor_starts == 0
    assert analysis.last_compressor_start is None
    assert analysis.completed_cycle_durations == [40 * 60]
    assert analysis.last_cycle_was_short is False


@pytest.mark.asyncio
async def test_stop_right_after_the_defrost_leaves_no_cycle(monkeypatch) -> None:
    """The mode can leave Defrost one sample before the controller stops the compressor."""
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    start = datetime(2026, 11, 27, 15, 37, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(mode=1), set(), now=start)
    analysis.process_snapshot(_snapshot(compressor=1, mode=8), set(), now=start + timedelta(seconds=60))
    left = start + timedelta(minutes=6)
    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=left)
    analysis.process_snapshot(_snapshot(mode=1), set(), now=left + timedelta(seconds=6))

    assert analysis.completed_cycle_durations == []
    assert analysis.last_cycle_duration is None


@pytest.mark.asyncio
async def test_mode_flicker_back_into_defrost_does_not_start_a_cycle(monkeypatch) -> None:
    """A mode reading that dips out of Defrost and back must not open the delay window."""
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    start = datetime(2026, 11, 27, 15, 37, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(mode=1), set(), now=start)
    analysis.process_snapshot(_snapshot(compressor=1, mode=8), set(), now=start + timedelta(seconds=10))

    flicker = start + timedelta(minutes=6, seconds=10)
    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=flicker)
    analysis.process_snapshot(_snapshot(compressor=1, mode=8), set(), now=flicker + timedelta(seconds=10))
    left = flicker + timedelta(minutes=1, seconds=20)
    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=left)
    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=left + timedelta(seconds=30))
    assert analysis.current_cycle_minutes(left + timedelta(seconds=30)) == 0.0
    analysis.process_snapshot(_snapshot(mode=1), set(), now=left + timedelta(seconds=50))

    assert analysis.completed_cycle_durations == []
    assert analysis.last_cycle_duration is None


@pytest.mark.asyncio
async def test_cycle_running_into_a_restart_during_defrost_keeps_its_start(monkeypatch) -> None:
    """A tracked heating cycle survives a restart that lands inside a defrost."""
    started = datetime(2026, 11, 27, 15, 38, tzinfo=UTC)
    loaded = {
        "compressor_on": True,
        "defrost_on": False,
        "current_cycle_started": started.isoformat(),
        "compressor_start_events": [],
        "defrost_start_events": [],
        "cycle_accounting": 2,
    }
    analysis, _store = _analysis(monkeypatch, loaded=loaded)
    await analysis.async_load()
    defrost = datetime(2026, 11, 27, 15, 50, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(compressor=1, mode=8), set(), now=defrost)
    analysis.process_snapshot(_snapshot(mode=1), set(), now=defrost + timedelta(minutes=5))

    assert analysis.total_compressor_starts == 0
    assert analysis.completed_cycle_durations == [17 * 60]


@pytest.mark.asyncio
async def test_legacy_cycle_history_is_discarded_once(monkeypatch) -> None:
    """Durations recorded before #757 include defrost runs and cannot be told apart."""
    loaded = {
        "total_compressor_starts": 871,
        "compressor_on": False,
        "compressor_start_events": [],
        "defrost_start_events": [],
        "completed_cycle_durations": [300.0, 5400.0],
        "last_cycle_duration": 306.0,
        "last_cycle_ended": "2026-11-27T16:29:52+00:00",
    }
    analysis, store = _analysis(monkeypatch, loaded=loaded)
    await analysis.async_load()

    assert analysis.total_compressor_starts == 871
    assert analysis.completed_cycle_durations == []
    assert analysis.last_cycle_duration is None
    assert analysis.last_cycle_ended is None
    assert analysis.last_cycle_was_short is None

    await analysis.async_save()
    assert store.saved is not None
    assert store.saved["cycle_accounting"] == 2


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


@pytest.mark.asyncio
async def test_malformed_persisted_counts_are_reset_safely(monkeypatch) -> None:
    analysis, _store = _analysis(
        monkeypatch,
        loaded={
            "total_compressor_starts": "broken",
            "total_defrost_starts": None,
        },
    )

    await analysis.async_load()

    assert analysis.total_compressor_starts == 0
    assert analysis.total_defrost_starts == 0


@pytest.mark.asyncio
async def test_current_cycle_duration_is_zero_while_reconciled_off(monkeypatch) -> None:
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    now = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)

    analysis.process_snapshot(_snapshot(), set(), now=now)

    assert analysis.current_cycle_minutes(now) == 0.0


def test_short_cycle_threshold_is_clamped(monkeypatch) -> None:
    fake_store = FakeStore()
    monkeypatch.setattr(module, "Store", lambda *args, **kwargs: fake_store)
    analysis = OperationAnalysis(
        object(),
        "entry",
        _registers().get,
        short_cycle_minutes=999,
        expected_poll_interval=10,
    )

    assert analysis.short_cycle_minutes == 60


@pytest.mark.asyncio
async def test_persisted_values_are_validated(monkeypatch) -> None:
    """Restored state is untrusted: broken values must not corrupt the counters."""
    loaded = {
        "total_compressor_starts": True,  # a bool is not a counter
        "cycle_accounting": 2,
        "completed_cycle_durations": [120.0, "nonsense", -5, float("inf"), 240.0],
        "mode_durations": {"heating": 600.0, "cooling": "nope", "unknown_mode": 10.0},
        "last_compressor_start": "not-a-timestamp",
        "last_defrost_start": "2026-07-20T08:00:00",
    }
    analysis, _store = _analysis(monkeypatch, loaded=loaded)

    await analysis.async_load()

    assert analysis.total_compressor_starts == 0
    assert analysis.completed_cycle_durations == [120.0, 240.0]
    assert analysis.mode_durations["heating"] == 600.0
    assert analysis.mode_durations["cooling"] == 0.0
    assert "unknown_mode" not in analysis.mode_durations
    assert analysis.last_compressor_start is None
    assert analysis.last_defrost_start == datetime(2026, 7, 20, 8, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_an_unreadable_store_keeps_the_analysis_empty(monkeypatch) -> None:
    class _BrokenStore(FakeStore):
        async def async_load(self):
            raise RuntimeError("store is corrupt")

    monkeypatch.setattr(module, "Store", lambda *args, **kwargs: _BrokenStore())
    registers = _registers()
    analysis = OperationAnalysis(object(), "entry", registers.get, short_cycle_minutes=15, expected_poll_interval=10)

    await analysis.async_load()

    assert analysis.total_compressor_starts == 0


@pytest.mark.asyncio
async def test_non_dict_state_is_ignored(monkeypatch) -> None:
    analysis, _store = _analysis(monkeypatch, loaded=["not", "a", "dict"])  # type: ignore[arg-type]

    await analysis.async_load()

    assert analysis.total_compressor_starts == 0


def test_source_capabilities_follow_the_register_map(monkeypatch) -> None:
    registers = _registers()
    with_sources = OperationAnalysis(
        object(), "entry", registers.get, short_cycle_minutes=15, expected_poll_interval=10
    )
    without_sources = OperationAnalysis(
        object(), "entry", lambda name: None, short_cycle_minutes=15, expected_poll_interval=10
    )

    assert with_sources.supports_compressor is True
    assert with_sources.supports_operating_mode is True
    assert without_sources.supports_compressor is False
    assert without_sources.supports_operating_mode is False


@pytest.mark.asyncio
async def test_unusable_samples_pause_the_accounting(monkeypatch) -> None:
    analysis, _store = _analysis(monkeypatch)
    await analysis.async_load()
    start = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(compressor=1, mode=1), set(), now=start)

    # A snapshot whose compressor and mode values are missing keeps the previous
    # state instead of inventing an off edge or a mode interval.
    analysis.process_snapshot(
        {"compressor_status_1": None, "hp_operating_mode": None},
        set(),
        now=start + timedelta(seconds=10),
    )

    assert analysis.total_compressor_starts == 0
    assert analysis._last_mode is None


def test_derived_values_are_none_without_data(monkeypatch) -> None:
    registers = _registers()
    analysis = OperationAnalysis(object(), "entry", registers.get, short_cycle_minutes=15, expected_poll_interval=10)

    assert analysis.current_cycle_minutes() is None
    assert analysis.average_cycle_minutes() is None
    assert analysis.minutes_since_last_defrost() is None
    assert analysis.operating_share("nonexistent_mode") is None
    assert analysis.operating_share("heating") is None
    assert analysis.last_cycle_was_short is None


def test_defrost_age_and_operating_share_are_rounded(monkeypatch) -> None:
    registers = _registers()
    analysis = OperationAnalysis(object(), "entry", registers.get, short_cycle_minutes=15, expected_poll_interval=10)
    now = datetime(2026, 7, 20, 9, 0, tzinfo=UTC)
    analysis.last_defrost_start = now - timedelta(minutes=42, seconds=30)
    analysis.mode_durations["heating"] = 300.0
    analysis.mode_durations["cooling"] = 100.0

    assert analysis.minutes_since_last_defrost(now) == 42.5
    assert analysis.operating_share("heating") == 75.0


def test_value_helpers_reject_unusable_input() -> None:
    assert module._parse_datetime("not-a-timestamp") is None
    naive = module._parse_datetime("2026-07-20T08:00:00")
    assert naive is not None and naive.tzinfo is UTC
    assert module._finite_non_negative(-1) is None
    assert module._finite_non_negative(float("nan")) is None
    assert module._finite_non_negative(float("inf")) is None
    assert module._finite_non_negative(3.5) == 3.5
    assert module._non_negative_int(True) == 0


def test_current_defrost_minutes_reports_the_observed_cycle(monkeypatch) -> None:
    analysis, _store = _analysis(monkeypatch)

    # Before the first mode snapshot the defrost state is undecidable, not zero.
    assert analysis.current_defrost_minutes() is None

    now = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    # First mode snapshot only reconciles: defrost is off afterwards.
    analysis.process_snapshot(_snapshot(mode=1), set(), now=now)
    assert analysis.current_defrost_minutes(now=now) == 0.0

    # The observed off -> defrost edge starts the clock.
    analysis.process_snapshot(_snapshot(mode=8), set(), now=now + timedelta(minutes=10))
    assert analysis.last_defrost_start == now + timedelta(minutes=10)
    assert analysis.current_defrost_minutes(now=now + timedelta(minutes=40)) == 30.0
    # Never negative, even when queried with an earlier timestamp.
    assert analysis.current_defrost_minutes(now=now) == 0.0

    # Leaving defrost reconciles again: the cycle is over, so zero, not None.
    analysis.process_snapshot(_snapshot(mode=1), set(), now=now + timedelta(minutes=45))
    assert analysis.current_defrost_minutes(now=now + timedelta(minutes=50)) == 0.0


@pytest.mark.asyncio
async def test_dhw_charge_outcome_follows_the_switch_off_temperature(monkeypatch) -> None:
    """A completed charge is judged against dhw_charge_off_temp, not dhw_setpoint (#713)."""
    analysis, store = _dhw_analysis(monkeypatch)
    await analysis.async_load()
    now = datetime(2026, 11, 16, 5, 0, tzinfo=UTC)

    # First observation reconciles: a running charge starts at the first sample.
    analysis.process_snapshot(_dhw_snapshot(demand=0, top=49.9), set(), now=now)
    analysis.process_snapshot(_dhw_snapshot(demand=1, top=46.2), set(), now=now + timedelta(minutes=10))
    assert analysis.dhw_charge_minutes(now + timedelta(minutes=10)) == 0.0
    analysis.process_snapshot(_dhw_snapshot(demand=1, top=49.4), set(), now=now + timedelta(minutes=40))
    assert analysis.dhw_charge_minutes(now + timedelta(minutes=40)) == 30.0
    # Demand clears with the tank above the switch-off temperature: success.
    analysis.process_snapshot(_dhw_snapshot(demand=0, top=50.1), set(), now=now + timedelta(minutes=45))

    assert analysis.last_dhw_charge_reached_target is True
    assert analysis.last_dhw_charge_ended == now + timedelta(minutes=45)
    assert analysis.dhw_consecutive_charge_failures == 0
    assert analysis.dhw_charge_minutes(now + timedelta(minutes=45)) == 0.0
    assert store.delayed is not None


@pytest.mark.asyncio
async def test_dhw_charge_failures_accumulate_and_reset(monkeypatch) -> None:
    analysis, _store = _dhw_analysis(monkeypatch)
    await analysis.async_load()
    now = datetime(2026, 11, 16, 5, 0, tzinfo=UTC)

    analysis.process_snapshot(_dhw_snapshot(demand=0, top=47.9), set(), now=now)
    # First failed charge: peak 47.9 never reaches 50 - 1.0.
    analysis.process_snapshot(_dhw_snapshot(demand=1, top=46.4), set(), now=now + timedelta(minutes=5))
    analysis.process_snapshot(_dhw_snapshot(demand=0, top=47.1), set(), now=now + timedelta(minutes=35))
    assert analysis.last_dhw_charge_reached_target is False
    assert analysis.dhw_consecutive_charge_failures == 1
    # Second failed charge: two in a row.
    analysis.process_snapshot(_dhw_snapshot(demand=1, top=45.8), set(), now=now + timedelta(minutes=40))
    analysis.process_snapshot(_dhw_snapshot(demand=0, top=46.9), set(), now=now + timedelta(minutes=70))
    assert analysis.dhw_consecutive_charge_failures == 2
    # A successful charge clears the streak.
    analysis.process_snapshot(_dhw_snapshot(demand=1, top=46.1), set(), now=now + timedelta(minutes=75))
    analysis.process_snapshot(_dhw_snapshot(demand=0, top=50.3), set(), now=now + timedelta(minutes=105))
    assert analysis.dhw_consecutive_charge_failures == 0
    assert analysis.last_dhw_charge_reached_target is True


@pytest.mark.asyncio
async def test_dhw_charge_outcome_survives_restart_without_false_edges(monkeypatch) -> None:
    analysis, store = _dhw_analysis(monkeypatch)
    await analysis.async_load()
    now = datetime(2026, 11, 16, 5, 0, tzinfo=UTC)

    analysis.process_snapshot(_dhw_snapshot(demand=0, top=47.5), set(), now=now)
    analysis.process_snapshot(_dhw_snapshot(demand=1, top=46.0), set(), now=now + timedelta(minutes=5))
    analysis.process_snapshot(_dhw_snapshot(demand=0, top=47.2), set(), now=now + timedelta(minutes=30))
    assert analysis.dhw_consecutive_charge_failures == 1

    restarted, _store = _dhw_analysis(monkeypatch, loaded=store.delayed)
    await restarted.async_load()
    assert restarted.dhw_consecutive_charge_failures == 1
    assert restarted.last_dhw_charge_reached_target is False
    # The first snapshot after the restart only reconciles: a running charge
    # re-anchors at the observation and no completion is invented.
    restarted.process_snapshot(_dhw_snapshot(demand=1, top=46.0), set(), now=now + timedelta(minutes=35))
    assert restarted.dhw_consecutive_charge_failures == 1
    assert restarted.last_dhw_charge_reached_target is False
    assert restarted.dhw_charge_minutes(now + timedelta(minutes=35)) == 0.0


@pytest.mark.asyncio
async def test_dhw_charge_gap_never_implies_a_stuck_charge(monkeypatch) -> None:
    analysis, _store = _dhw_analysis(monkeypatch)
    await analysis.async_load()
    now = datetime(2026, 11, 16, 5, 0, tzinfo=UTC)

    analysis.process_snapshot(_dhw_snapshot(demand=0, top=49.5), set(), now=now)
    analysis.process_snapshot(_dhw_snapshot(demand=1, top=46.0), set(), now=now + timedelta(minutes=1))
    # A communication gap of hours must not be charged to the running charge.
    analysis.process_snapshot(_dhw_snapshot(demand=1, top=46.4), set(), now=now + timedelta(hours=3))
    assert analysis.dhw_charge_minutes(now + timedelta(hours=3, minutes=1)) == 1.0


@pytest.mark.asyncio
async def test_dhw_charge_paused_when_demand_register_unavailable(monkeypatch) -> None:
    analysis, _store = _dhw_analysis(monkeypatch)
    await analysis.async_load()
    now = datetime(2026, 11, 16, 5, 0, tzinfo=UTC)

    analysis.process_snapshot(_dhw_snapshot(demand=0, top=49.5), set(), now=now)
    analysis.process_snapshot(_dhw_snapshot(demand=1, top=46.0), set(), now=now + timedelta(minutes=1))
    # A snapshot without the demand bit neither completes nor anchors a charge.
    analysis.process_snapshot(_snapshot(mode=4), set(), now=now + timedelta(minutes=10))
    assert analysis.dhw_charge_minutes(now + timedelta(minutes=10)) == 9.0
    assert analysis.last_dhw_charge_reached_target is None
    # Unused registers are treated like missing data: no invented outcome.
    analysis.process_snapshot(_dhw_snapshot(demand=0, top=50.2), {"dhw_demand"}, now=now + timedelta(minutes=11))
    assert analysis.last_dhw_charge_reached_target is None


@pytest.mark.asyncio
async def test_dhw_charge_without_peak_or_target_stays_unknown(monkeypatch) -> None:
    analysis, _store = _dhw_analysis(monkeypatch)
    await analysis.async_load()
    now = datetime(2026, 11, 16, 5, 0, tzinfo=UTC)

    analysis.process_snapshot(_dhw_snapshot(demand=0, top=49.5), set(), now=now)
    # No usable tank temperature during the whole charge: no invented outcome.
    analysis.process_snapshot(_dhw_snapshot(demand=1, top=-327.2), set(), now=now + timedelta(minutes=1))
    analysis.process_snapshot(_dhw_snapshot(demand=0, top=-327.2), set(), now=now + timedelta(minutes=30))
    assert analysis.last_dhw_charge_reached_target is None
    assert analysis.dhw_consecutive_charge_failures == 0


def test_continuous_polling_does_not_postpone_storage(monkeypatch) -> None:
    analysis, store = _analysis(monkeypatch, expected_poll_interval=5)
    now = datetime(2026, 11, 16, tzinfo=UTC)
    for seconds in range(0, 31, 5):
        analysis.process_snapshot(_snapshot(mode=1), set(), now=now + timedelta(seconds=seconds))
        assert store.scheduled == 1
    checkpoint = store.delayed
    assert checkpoint is not None
    assert checkpoint["mode_durations"]["heating"] == 30

    analysis.process_snapshot(_snapshot(mode=1), set(), now=now + timedelta(seconds=35))
    assert store.scheduled == 2
    checkpoint = store.delayed
    assert checkpoint is not None
    assert checkpoint["mode_durations"]["heating"] == 35


@pytest.mark.parametrize("demand_after_gap", [0, 1])
def test_dhw_gap_discards_the_interrupted_outcome(monkeypatch, demand_after_gap: int) -> None:
    analysis, _ = _analysis(monkeypatch)
    now = datetime(2026, 11, 16, 5, tzinfo=UTC)
    analysis.process_snapshot(_dhw_snapshot(demand=0), set(), now=now)
    analysis.process_snapshot(_dhw_snapshot(demand=1, top=46), set(), now=now + timedelta(seconds=10))
    resumed = now + timedelta(hours=3)
    analysis.process_snapshot(_dhw_snapshot(demand=demand_after_gap, top=46), set(), now=resumed)
    analysis.process_snapshot(_dhw_snapshot(demand=0, top=47), set(), now=resumed + timedelta(seconds=10))
    assert analysis.last_dhw_charge_reached_target is None
    assert analysis.dhw_consecutive_charge_failures == 0
    analysis.process_snapshot(_dhw_snapshot(demand=1, top=46), set(), now=resumed + timedelta(seconds=20))
    analysis.process_snapshot(_dhw_snapshot(demand=0, top=47), set(), now=resumed + timedelta(seconds=30))
    assert analysis.dhw_consecutive_charge_failures == 1


def test_dhw_runtime_is_split_at_local_midnight(monkeypatch) -> None:
    local_zone = timezone(timedelta(hours=1))
    monkeypatch.setattr(module.dt_util, "as_local", lambda value: value.astimezone(local_zone))
    analysis, store = _analysis(monkeypatch)
    before_midnight = datetime(2026, 11, 16, 22, 59, 55, tzinfo=UTC)
    analysis.process_snapshot(_snapshot(mode=4), set(), now=before_midnight)
    analysis.process_snapshot(_snapshot(mode=4), set(), now=before_midnight + timedelta(seconds=10))
    assert store.delayed is not None
    assert store.delayed["daily_dhw"] == {"2026-11-16": 5.0, "2026-11-17": 5.0}
