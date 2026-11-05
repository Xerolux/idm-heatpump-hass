"""Telemetry consent, scope, rate limiting and cancellation regression tests."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.idm_heatpump.const import (
    CONF_TELEMETRY,
    CONF_TELEMETRY_CONSENT_AT,
    CONF_TELEMETRY_POLICY,
    CONF_TELEMETRY_SERIAL,
)
from custom_components.idm_heatpump.telemetry import Telemetry, _label, _number, _version, valid_serial


def make_telemetry(enabled=True):
    entry = MagicMock()
    entry.entry_id = "private-entry-id"
    entry.data = {"host": "private-plant-endpoint", "web_pin": "private-pin"}
    entry.options = {
        CONF_TELEMETRY_POLICY: "idm-telemetry-v1",
        CONF_TELEMETRY: enabled,
        CONF_TELEMETRY_SERIAL: "TEST-Serial-123",
        CONF_TELEMETRY_CONSENT_AT: "2026-11-05T10:00:00+00:00",
    }
    coordinator = MagicMock()
    coordinator.data = {"error_number": 42, "flow_temp": 30, "private": "never-send"}
    coordinator.unused_registers = set()
    coordinator.last_update_success = True
    coordinator.model_name = "Navigator 10"
    coordinator.firmware_version = "V1.23.4"
    coordinator.web_variant = "nav10"
    coordinator.web_alive = True
    coordinator.web_supplement = SimpleNamespace(heatpump_model="AERO ALM")
    coordinator.model_info = SimpleNamespace(has_solar=False, has_pv=True, has_cascade=False, has_isc=False)
    coordinator.poll_statistics = SimpleNamespace(total_polls=100, total_failures=2)
    coordinator.operation_analysis = SimpleNamespace(total_compressor_starts=12, mode_durations={"heating": 100})
    coordinator.energy_statistics = SimpleNamespace(total_electrical_kwh=50, total_thermal_kwh=150)
    with patch("custom_components.idm_heatpump.telemetry.Store") as store:
        store.return_value.async_load = AsyncMock(return_value=None)
        store.return_value.async_save = AsyncMock()
        store.return_value.async_remove = AsyncMock()
        telemetry = Telemetry(MagicMock(), entry, coordinator, "0.25.0-b9")
    return telemetry, entry, coordinator


async def test_no_means_no_collection_storage_timer_or_network():
    telemetry, entry, _ = make_telemetry(False)
    with (
        patch("custom_components.idm_heatpump.telemetry.async_track_time_interval") as timer,
        patch("custom_components.idm_heatpump.telemetry.async_get_clientsession") as session,
    ):
        await telemetry.async_start()
        telemetry.observe()
        await telemetry.async_tick(datetime.now(UTC))
    telemetry._store.async_load.assert_not_called()
    telemetry._store.async_save.assert_not_called()
    entry.async_on_unload.assert_not_called()
    timer.assert_not_called()
    session.assert_not_called()
    assert not telemetry._errors


@pytest.mark.parametrize("serial,consent", [("", "yes"), ("invalid@serial", "yes"), ("TEST-123", "")])
async def test_missing_serial_or_consent_never_starts(serial, consent):
    telemetry, entry, _ = make_telemetry()
    entry.options[CONF_TELEMETRY_SERIAL] = serial
    entry.options[CONF_TELEMETRY_CONSENT_AT] = consent
    await telemetry.async_start()
    telemetry._store.async_load.assert_not_called()


async def test_persisted_daily_reservation_and_unload_callbacks():
    telemetry, entry, _ = make_telemetry()
    with patch("custom_components.idm_heatpump.telemetry.async_track_time_interval") as timer:
        await telemetry.async_start()
        assert timer.call_count == 1
        assert entry.async_on_unload.call_count == 4
    assert telemetry._last_attempt <= time.time()
    with patch("custom_components.idm_heatpump.telemetry.async_get_clientsession") as session:
        await telemetry.async_tick(datetime.now(UTC))
        session.assert_not_called()
    telemetry._store.async_load.return_value = {
        "last_attempt": time.time() - 100,
        "consent_at": entry.options[CONF_TELEMETRY_CONSENT_AT],
    }
    with patch("custom_components.idm_heatpump.telemetry.async_track_time_interval"):
        await telemetry.async_start()
    assert 99 < time.time() - telemetry._last_attempt < 105


def test_complete_allowlist_keeps_serial_unchanged_and_excludes_other_ha_data():
    telemetry, _, coordinator = make_telemetry()
    telemetry.observe()
    telemetry.observe()
    coordinator.web_alive = False
    telemetry.observe()
    coordinator.poll_statistics.total_polls += 4
    coordinator.operation_analysis.total_compressor_starts += 1
    coordinator.energy_statistics.total_electrical_kwh += 2
    payload = telemetry.payload()
    assert payload["serial_number"] == "TEST-Serial-123"
    assert payload["firmware"] == "V1.23.4"
    assert payload["heatpump_model"] == "AERO ALM"
    assert payload["counters"]["modbus_polls"] == 4
    assert payload["counters"]["compressor_starts"] == 1
    assert payload["counters"]["electrical_kwh"] == 2
    assert payload["counters"]["web_outages"] == 1
    assert payload["error_transitions"] == {"42": 1}
    assert payload["capabilities"]["pv"] is True
    encoded = json.dumps(payload)
    for secret in ("private-entry-id", "private-plant-endpoint", "private-pin", "flow_temp", "never-send"):
        assert secret not in encoded
    assert set(payload) == {
        "schema",
        "policy",
        "serial_number",
        "consent_at",
        "integration_version",
        "navigator",
        "navigator_model",
        "heatpump_model",
        "firmware",
        "connection_mode",
        "web_variant",
        "capabilities",
        "register_count",
        "observed_hours",
        "counters",
        "error_transitions",
    }
    coordinator.model_info = None
    coordinator.operation_analysis = None
    coordinator.energy_statistics = None
    coordinator.web_supplement = None
    coordinator.web_variant = "unknown"
    payload = telemetry.payload()
    assert payload["heatpump_model"] is None and payload["capabilities"] == {}
    assert set(payload["counters"]) == {"modbus_polls", "modbus_failures", "web_outages"}
    assert payload["web_variant"] is None


@pytest.mark.parametrize("value", [None, True, -1, float("nan"), float("inf"), 1e15, "12"])
def test_invalid_numbers_are_absent(value):
    assert _number(value) is None


@pytest.mark.parametrize("value", ["", None, "bad@email", "ab", "\r\nserial"])
def test_invalid_serial_is_rejected(value):
    assert not valid_serial(value)


def test_metadata_validation():
    assert _version("0.25.0-b9") == "0.25.0-b9"
    assert _version("private.host") is None
    assert _label("AERO ALM") == "AERO ALM"
    assert _label("unsafe\ntext") is None
    assert _label("x" * 81) is None


def test_error_transition_quality_and_bounds():
    telemetry, entry, coordinator = make_telemetry()
    coordinator.last_update_success = False
    telemetry.observe()
    coordinator.last_update_success = True
    coordinator.unused_registers = {"error_number"}
    telemetry.observe()
    coordinator.unused_registers = set()
    for value in (None, 1.5, 65536):
        coordinator.data["error_number"] = value
        telemetry.observe()
    assert not telemetry._errors
    for value in range(1, 100):
        coordinator.data["error_number"] = value
        telemetry.observe()
    assert len(telemetry._errors) == 64
    entry.options[CONF_TELEMETRY] = False
    telemetry.observe()
    assert len(telemetry._errors) == 64


@pytest.mark.parametrize("status", [201, 400, 302])
async def test_submission_reserves_slot_before_io_and_never_follows_redirects(status):
    telemetry, entry, _ = make_telemetry()
    telemetry._last_attempt = time.time() - 90000
    response = MagicMock(status=status)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    with patch("custom_components.idm_heatpump.telemetry.async_get_clientsession", return_value=session):
        await telemetry.async_tick(datetime.now(UTC))
        await telemetry.async_tick(datetime.now(UTC))
    assert session.post.call_count == 1
    assert session.post.call_args.kwargs["allow_redirects"] is False
    assert telemetry._store.async_save.await_count == (2 if status == 201 else 1)
    assert telemetry._active_task is None
    entry.options[CONF_TELEMETRY] = False
    await telemetry.async_options_updated(None, entry)
    assert telemetry._stopped


@pytest.mark.parametrize("error", [aiohttp.ClientError(), TimeoutError(), OSError()])
async def test_failure_does_not_retry_or_log_private_error(error):
    telemetry, _, _ = make_telemetry()
    telemetry._last_attempt = time.time() - 90000
    session = MagicMock()
    session.post.side_effect = error
    with patch("custom_components.idm_heatpump.telemetry.async_get_clientsession", return_value=session):
        await telemetry.async_tick(datetime.now(UTC))
        await telemetry.async_tick(datetime.now(UTC))
    assert session.post.call_count == 1


async def test_in_flight_request_is_cancelled_on_withdrawal():
    telemetry, entry, _ = make_telemetry()
    telemetry._last_attempt = time.time() - 90000
    started = asyncio.Event()

    async def wait_forever():
        started.set()
        await asyncio.Future()

    context = MagicMock()
    context.__aenter__ = AsyncMock(side_effect=wait_forever)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    with patch("custom_components.idm_heatpump.telemetry.async_get_clientsession", return_value=session):
        task = asyncio.create_task(telemetry.async_tick(datetime.now(UTC)))
        await asyncio.wait_for(started.wait(), timeout=2)
        entry.options[CONF_TELEMETRY] = False
        await telemetry.async_options_updated(None, entry)
        with pytest.raises(asyncio.CancelledError):
            await task
    assert telemetry._active_task is None


async def test_withdrawal_during_reservation_prevents_contact():
    telemetry, entry, _ = make_telemetry()
    telemetry._last_attempt = time.time() - 90000

    async def withdraw(data):
        entry.options[CONF_TELEMETRY] = False

    telemetry._store.async_save.side_effect = withdraw
    with patch("custom_components.idm_heatpump.telemetry.async_get_clientsession") as session:
        await telemetry.async_tick(datetime.now(UTC))
        session.assert_not_called()


async def test_aggregates_and_frozen_outbox_survive_reload_without_counting_downtime():
    telemetry, _, coordinator = make_telemetry()
    telemetry.observe()
    coordinator.poll_statistics.total_polls += 25
    coordinator.energy_statistics.total_electrical_kwh += 3
    telemetry._last_attempt = time.time() - 90000
    session = MagicMock()
    session.post.side_effect = OSError()
    with patch("custom_components.idm_heatpump.telemetry.async_get_clientsession", return_value=session):
        await telemetry.async_tick(datetime.now(UTC))
    saved = telemetry._store.async_save.call_args.args[0]
    frozen = saved["outbox"]
    assert frozen["counters"]["modbus_polls"] == 25
    restored, new_entry, new_coordinator = make_telemetry()
    new_coordinator.energy_statistics.total_electrical_kwh = 53
    restored._store.async_load.return_value = saved
    with patch("custom_components.idm_heatpump.telemetry.async_track_time_interval"):
        await restored.async_start()
    assert restored._outbox == frozen
    assert restored.payload()["counters"]["modbus_polls"] == 25
    assert restored.payload()["counters"]["electrical_kwh"] == 3
    assert restored.payload()["error_transitions"] == {"42": 1}
    new_coordinator.poll_statistics.total_polls += 5
    assert restored.payload()["counters"]["modbus_polls"] == 30
    await restored.async_stop()
    assert restored._store.async_save.call_args.args[0]["counters"]["modbus_polls"] == 30
    new_entry.options[CONF_TELEMETRY] = False
    await restored.async_stop()
    restored._store.async_remove.assert_awaited_once()


async def test_new_consent_never_reuses_old_observations_or_daily_slot():
    telemetry, _, _ = make_telemetry()
    telemetry._store.async_load.return_value = {
        "consent_at": "previous-consent",
        "last_attempt": 1,
        "counters": {"modbus_polls": 10000},
    }
    with patch("custom_components.idm_heatpump.telemetry.async_track_time_interval"):
        await telemetry.async_start()
    assert time.time() - telemetry._last_attempt < 5
    assert telemetry.payload()["counters"]["modbus_polls"] == 0


async def test_frequent_observations_do_not_postpone_persistence_forever():
    telemetry, _, _ = make_telemetry()
    for _ in range(100):
        telemetry.observe()
    telemetry._store.async_delay_save.assert_called_once()
    state = telemetry._delayed_snapshot()
    assert state["error_transitions"] == {"42": 1}
    telemetry.observe()
    assert telemetry._store.async_delay_save.call_count == 2
    telemetry.stop()
    assert telemetry._delayed_snapshot() == {}
