"""Independent firmware consent and minimal metadata privacy boundary."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from test_telemetry import make_telemetry

from custom_components.idm_heatpump.const import (
    CONF_FIRMWARE_CHECK,
    CONF_FIRMWARE_CONSENT_AT,
    CONF_FIRMWARE_POLICY,
    CONF_PLANT_MODEL,
    CONF_TELEMETRY,
)
from custom_components.idm_heatpump.firmware_observations import (
    FIRMWARE_POLICY,
    FIRMWARE_RESULT_DATA_KEY,
    FirmwareObservations,
    _restorable_result,
)


def make_firmware(enabled=True):
    _, entry, coordinator = make_telemetry(False)
    hass = MagicMock()
    hass.config_entries.async_update_entry.side_effect = lambda target, **kwargs: setattr(
        target, "data", kwargs["data"]
    )
    entry.options.update(
        {
            CONF_FIRMWARE_CHECK: enabled,
            CONF_FIRMWARE_POLICY: FIRMWARE_POLICY,
            CONF_FIRMWARE_CONSENT_AT: "2026-11-05T10:00:00+00:00",
        }
    )
    entry.options.pop("telemetry_myidm_id", None)
    coordinator.myidm_id = None
    return FirmwareObservations(hass, entry, coordinator), entry, coordinator


STORED_ANSWER = {
    "latest_firmware": "NAV10_20.24-11",
    "installed_firmware": "NAV10_20.24-9",
    "matching_model": "AERO ALM",
    "series": "nav10_20",
    "status": "observed",
    "model_scope": "controller_and_plant_model",
    "component_status": "reported_component",
    "source": "community_telemetry",
    "newer_observed": True,
    "observations": 3,
    "last_checked": "2026-11-09T12:00:00+00:00",
}


def _session_with_answer(query, latest, newer_observed, *, series="nav10_20"):
    response = MagicMock(status=200)
    response.json = AsyncMock(
        return_value={
            "query": query,
            "source": "community_telemetry",
            "status": "observed",
            "latest_firmware": latest,
            "series": series,
            "observations": 3,
            "newer_observed": newer_observed,
            "model_scope": "controller_and_plant_model",
        }
    )
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    return session


@pytest.mark.parametrize(
    ("model", "installed", "latest", "family", "controller"),
    [
        ("Navigator 1.7", "n1.7z72", "n1.7z100", "navigator_17", "Navigator 1.7"),
        ("Navigator 1.7", "n1.0z12", "n1.0z14", "navigator_1_0", "Navigator 1.0"),
        ("Navigator 1.0", "n1.0z12", "n1.0z14", "navigator_1_0", "Navigator 1.0"),
    ],
)
async def test_legacy_firmware_payload_and_response(model, installed, latest, family, controller):
    firmware, _, coordinator = make_firmware()
    coordinator.model_name = model
    coordinator.firmware_version = "1.7"
    coordinator.web_supplement.legacy_firmware = installed
    query = {
        "navigator": family,
        "navigator_model": controller,
        "heatpump_model": "AERO ALM",
        "firmware": installed,
    }
    session = _session_with_answer(query, latest, True, series=installed[:5])
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        await firmware.async_refresh_firmware()
    assert session.post.call_args.kwargs["json"] == query
    assert firmware.firmware_result["latest_firmware"] == latest


async def test_no_firmware_query_without_consent():
    telemetry, _, _ = make_firmware(False)
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession") as session:
        await FirmwareObservations.async_refresh_firmware(telemetry)
    session.assert_not_called()


async def test_firmware_response_is_bound_to_requested_plant_metadata():
    telemetry, _, _ = make_firmware()
    telemetry._coordinator.firmware_version = "NAV10_20.24-9"
    response = MagicMock(status=200)
    query = {
        "navigator": "navigator_10",
        "navigator_model": "Navigator 10",
        "heatpump_model": "AERO ALM",
        "firmware": "NAV10_20.24-9",
    }
    response.json = AsyncMock(
        return_value={
            "query": query,
            "source": "community_telemetry",
            "status": "observed",
            "latest_firmware": "NAV10_20.24-11",
            "series": "nav10_20",
            "observations": 2,
            "newer_observed": True,
        }
    )
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    listener = MagicMock()
    remove = telemetry.async_add_firmware_listener(listener)
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        await FirmwareObservations.async_refresh_firmware(telemetry)
    assert session.post.call_args.kwargs["json"] == query
    assert telemetry._entry.options[CONF_TELEMETRY] is False
    assert telemetry.firmware_result["latest_firmware"] == "NAV10_20.24-11"
    listener.assert_called_once()
    remove()
    response.json.return_value["query"] = query | {"heatpump_model": "OTHER MODEL"}
    telemetry.firmware_result = {}
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        await FirmwareObservations.async_refresh_firmware(telemetry)
    assert telemetry.firmware_result.get("latest_firmware") is None
    assert set(telemetry.firmware_result) == {"next_check"}


async def test_withdrawal_cancels_firmware_request_as_well_as_upload():
    telemetry, entry, _ = make_firmware()
    started = asyncio.Event()

    async def wait_forever():
        started.set()
        await asyncio.Future()

    context = MagicMock()
    context.__aenter__ = AsyncMock(side_effect=wait_forever)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        task = asyncio.create_task(FirmwareObservations.async_refresh_firmware(telemetry))
        await asyncio.wait_for(started.wait(), timeout=2)
        entry.options[CONF_FIRMWARE_CHECK] = False
        await telemetry.async_options_updated(None, entry)
        with pytest.raises(asyncio.CancelledError):
            await task
    assert telemetry._firmware_task is None


def test_firmware_series_keeps_test_and_stable_channels_separate():
    from custom_components.idm_heatpump.telemetry import _firmware_series

    assert _firmware_series("T_NAV10_20.24-1580-g02a20b66f") == "t_nav10_20"
    assert _firmware_series("NAV10_20.24-1580.iup") == "nav10_20"
    assert _firmware_series("m_20.23-165") == "m_20"
    assert _firmware_series("unknown") is None
    assert _firmware_series(None) is None


@pytest.mark.parametrize(
    "options",
    [{}, {"firmware_check": True}, {"firmware_check": True, "firmware_policy": "old", "firmware_consent_at": "yes"}],
)
async def test_firmware_refusal_has_no_timer_storage_or_contact(options):
    client, entry, _ = make_firmware()
    entry.options = options
    with (
        patch("custom_components.idm_heatpump.cloud_scheduler.async_track_time_interval") as timer,
        patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession") as session,
    ):
        assert await client.async_start() is False
        await client.async_tick(datetime.now(UTC))
    timer.assert_not_called()
    session.assert_not_called()
    assert not hasattr(client, "_store")


async def test_firmware_has_independent_lifecycle_and_six_hour_timer():
    client, entry, _ = make_firmware()
    client.async_refresh_firmware = AsyncMock()
    with patch("custom_components.idm_heatpump.cloud_scheduler.async_track_time_interval") as timer:
        assert await client.async_start()
        assert timer.call_args.args[2].total_seconds() == 60
    client.async_refresh_firmware.assert_not_awaited()
    client._next_firmware_check = 0
    await client.async_tick(datetime.now(UTC))
    assert client.async_refresh_firmware.await_count == 1
    entry.options[CONF_TELEMETRY] = False
    await client.async_options_updated(None, entry)
    assert client.enabled
    entry.options[CONF_FIRMWARE_CHECK] = False
    await client.async_options_updated(None, entry)
    assert not client.enabled


async def test_unknown_firmware_consent_never_contacts_server():
    firmware, entry, _ = make_firmware()
    entry.options[CONF_FIRMWARE_POLICY] = "unsupported-policy"
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession") as session:
        await firmware.async_refresh_firmware()
    assert not firmware.enabled
    session.assert_not_called()


@pytest.mark.parametrize("scope,expected", [("controller_and_plant_model", False), ("unconfirmed_component", None)])
async def test_existing_consent_and_single_report_show_latest_without_update_notice(scope, expected):
    firmware, entry, coordinator = make_firmware()
    assert entry.options[CONF_FIRMWARE_POLICY] == "idm-firmware-v1"
    coordinator.firmware_version = "NAV10_20.24-9"
    query = {
        "navigator": "navigator_10",
        "navigator_model": "Navigator 10",
        "heatpump_model": "AERO ALM",
        "firmware": coordinator.firmware_version,
    }
    response = MagicMock(status=200)
    response.json = AsyncMock(
        return_value={
            "query": query,
            "source": "community_telemetry",
            "status": "observed",
            "latest_firmware": query["firmware"],
            "series": "nav10_20",
            "observations": 1,
            "newer_observed": scope == "unconfirmed_component",
            "model_scope": scope,
            "component_status": "reported_component",
        }
    )
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        await firmware.async_refresh_firmware()
    assert firmware.enabled
    assert firmware.firmware_result["latest_firmware"] == query["firmware"]
    assert firmware.firmware_result["newer_observed"] is expected
    assert firmware.firmware_result["component_status"] == "reported_component"


async def test_restart_restores_last_answer_without_contacting_the_server():
    """The sensor keeps its value across restarts; the load delay bridges it."""
    firmware, entry, _ = make_firmware()
    entry.data[FIRMWARE_RESULT_DATA_KEY] = dict(STORED_ANSWER)
    with (
        patch("custom_components.idm_heatpump.cloud_scheduler.async_track_time_interval"),
        patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession") as session,
    ):
        assert await firmware.async_start()
        session.assert_not_called()
    restored = firmware.firmware_result
    assert restored["latest_firmware"] == "NAV10_20.24-11"
    assert restored["newer_observed"] is True
    assert restored["last_checked"] == "2026-11-09T12:00:00+00:00"
    assert restored["status"] == "observed"
    assert "next_check" in restored
    firmware.stop()


async def test_answer_is_saved_and_kept_until_a_newer_one_replaces_it():
    firmware, entry, coordinator = make_firmware()
    coordinator.firmware_version = "NAV10_20.24-9"
    query = {
        "navigator": "navigator_10",
        "navigator_model": "Navigator 10",
        "heatpump_model": "AERO ALM",
        "firmware": "NAV10_20.24-9",
    }
    session = _session_with_answer(query, "NAV10_20.24-11", True)
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        await firmware.async_refresh_firmware()
    stored = entry.data[FIRMWARE_RESULT_DATA_KEY]
    assert stored["latest_firmware"] == "NAV10_20.24-11"
    assert stored["newer_observed"] is True

    # Restart: the same entry restores the stored answer without a request.
    restarted = FirmwareObservations(firmware._hass, entry, coordinator)
    with (
        patch("custom_components.idm_heatpump.cloud_scheduler.async_track_time_interval"),
        patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession") as session2,
    ):
        assert await restarted.async_start()
        session2.assert_not_called()
    assert restarted.firmware_result["latest_firmware"] == "NAV10_20.24-11"
    restarted.stop()

    # The next answer replaces the stored one; nothing older survives.
    session = _session_with_answer(query, "NAV10_20.24-12", True)
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        await firmware.async_refresh_firmware()
    assert entry.data[FIRMWARE_RESULT_DATA_KEY]["latest_firmware"] == "NAV10_20.24-12"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "NAV10_20.24-11",
        STORED_ANSWER | {"source": "manufacturer"},
        STORED_ANSWER | {"status": "withdrawn"},
        {key: value for key, value in STORED_ANSWER.items() if key != "status"},
        {key: value for key, value in STORED_ANSWER.items() if key != "last_checked"},
    ],
)
def test_corrupt_or_foreign_persisted_answers_are_ignored(payload):
    assert _restorable_result(payload) is None


def test_mistyped_fields_fall_back_to_none_but_keep_the_answer():
    restored = _restorable_result(STORED_ANSWER | {"latest_firmware": 11, "observations": "many"})
    assert restored is not None
    assert restored["latest_firmware"] is None
    assert restored["observations"] is None
    assert restored["newer_observed"] is True


async def test_stop_keeps_the_notice_but_withdrawal_clears_notice_and_stored_answer():
    from custom_components.idm_heatpump import _entry_reload_fingerprint

    firmware, entry, _ = make_firmware()
    entry.data[FIRMWARE_RESULT_DATA_KEY] = dict(STORED_ANSWER)
    fingerprint_before = _entry_reload_fingerprint(entry)
    with patch("custom_components.idm_heatpump.firmware_notice.ir.async_delete_issue") as delete_issue:
        firmware.stop()
        delete_issue.assert_not_called()
    assert _entry_reload_fingerprint(entry) == fingerprint_before
    firmware._stopped = False

    entry.options[CONF_FIRMWARE_CHECK] = False
    entry.options.pop(CONF_FIRMWARE_CONSENT_AT, None)
    with (
        patch("custom_components.idm_heatpump.firmware_notice.ir.async_get") as registry,
        patch("custom_components.idm_heatpump.firmware_notice.ir.async_delete_issue") as delete_issue,
    ):
        registry.return_value.issues = {("idm_heatpump", "firmware_observed_private-entry-id_ab"): None}
        await firmware.async_options_updated(None, entry)
        delete_issue.assert_called_once()
    assert FIRMWARE_RESULT_DATA_KEY not in entry.data
    assert not firmware.enabled


def test_stored_answer_key_never_triggers_an_entry_reload():
    from custom_components.idm_heatpump import _entry_reload_fingerprint

    _, entry, _ = make_firmware()
    before = _entry_reload_fingerprint(entry)
    entry.data[FIRMWARE_RESULT_DATA_KEY] = dict(STORED_ANSWER)
    assert _entry_reload_fingerprint(entry) == before


async def test_startup_check_load_spreads_within_fifteen_minutes():
    import secrets as secrets_module

    client, _, _ = make_firmware()
    with (
        patch("custom_components.idm_heatpump.cloud_scheduler.async_track_time_interval"),
        patch(
            "custom_components.idm_heatpump.firmware_observations.secrets.randbelow",
            wraps=secrets_module.randbelow,
        ) as spread,
        patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession") as session,
    ):
        assert await client.async_start()
        assert {call.args[0] for call in spread.call_args_list} == {900}
        session.assert_not_called()
    client.stop()


def _context(status):
    response = MagicMock(status=status)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    return context


async def test_a_refused_start_forgets_the_answer_of_a_consent_that_no_longer_holds():
    firmware, entry, _ = make_firmware()
    entry.data = {FIRMWARE_RESULT_DATA_KEY: dict(STORED_ANSWER), "host": "private-plant-endpoint"}
    entry.options[CONF_FIRMWARE_POLICY] = "idm-firmware-v0"
    with (
        patch("custom_components.idm_heatpump.cloud_scheduler.async_track_time_interval") as timer,
        patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession") as session,
        patch("custom_components.idm_heatpump.firmware_observations.clear_notices") as clear,
    ):
        assert await firmware.async_start() is False
    # The stored answer and its notice belong to the withdrawn notice revision.
    assert FIRMWARE_RESULT_DATA_KEY not in entry.data
    assert "host" in entry.data
    clear.assert_called_once()
    timer.assert_not_called()
    session.assert_not_called()


async def test_a_catalog_answer_is_reported_as_completed():
    firmware, _, coordinator = make_firmware()
    coordinator.firmware_version = "NAV10_20.24-9"
    query = {
        "navigator": "navigator_10",
        "navigator_model": "Navigator 10",
        "heatpump_model": "AERO ALM",
        "firmware": "NAV10_20.24-9",
    }
    session = _session_with_answer(query, "NAV10_20.24-11", True)
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        assert await firmware.async_refresh_firmware() == "completed"
    assert firmware.firmware_result["installed_firmware"] == "NAV10_20.24-9"
    status = firmware.check_status()
    assert status["last_outcome"] == "completed"
    assert status["last_check"] == firmware.firmware_result["last_checked"]


@pytest.mark.parametrize("status", [204, 302, 400, 429, 500, 503])
async def test_a_catalog_without_an_ok_answer_is_reported_and_logged_without_content(status):
    firmware, _, _ = make_firmware()
    session = MagicMock()
    session.post.return_value = _context(status)
    with (
        patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session),
        patch("custom_components.idm_heatpump.firmware_observations._LOGGER") as logger,
    ):
        assert await firmware.async_refresh_firmware() == "unavailable"
    assert firmware.firmware_result.get("status") is None
    # The status code is a lazy logging argument; no answer content is logged.
    assert logger.debug.call_args.args == (
        "IDM firmware catalog answered with HTTP %s; the last observation is kept",
        status,
    )
    assert firmware.check_status()["last_outcome"] == "unavailable"
    # A failed check keeps its regular six-hour slot instead of retrying at once.
    assert firmware._next_firmware_check > time.time() + 21500


async def test_an_answer_that_does_not_belong_to_this_plant_is_reported_as_unavailable():
    firmware, _, coordinator = make_firmware()
    coordinator.firmware_version = "NAV10_20.24-9"
    other_query = {
        "navigator": "navigator_10",
        "navigator_model": "Navigator 10",
        "heatpump_model": "AERO ALM",
        "firmware": "NAV10_20.24-99",
    }
    session = _session_with_answer(other_query, "NAV10_20.24-11", True)
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        assert await firmware.async_refresh_firmware() == "unavailable"
    assert firmware.firmware_result.get("status") is None


async def test_a_network_error_is_reported_as_unavailable_without_exception_text():
    firmware, _, _ = make_firmware()
    context = MagicMock()
    context.__aenter__ = AsyncMock(side_effect=aiohttp.ClientConnectionError("private detail"))
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    with (
        patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session),
        patch("custom_components.idm_heatpump.firmware_observations._LOGGER") as logger,
    ):
        assert await firmware.async_refresh_firmware() == "unavailable"
    assert firmware.check_status()["last_outcome"] == "unavailable"
    # Only the exception type reaches the log, never its text.
    assert logger.debug.call_args.args[1] == "ClientConnectionError"
    assert "private detail" not in logger.debug.call_args.args[0]


async def test_a_check_running_twice_reports_the_second_as_in_progress():
    firmware, _, _ = make_firmware()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def enter():
        entered.set()
        await release.wait()
        return MagicMock(status=503)

    context = MagicMock()
    context.__aenter__ = AsyncMock(side_effect=enter)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        first = asyncio.create_task(firmware.async_refresh_firmware())
        await entered.wait()
        try:
            assert await firmware.async_refresh_firmware() == "in_progress"
        finally:
            release.set()
        assert await first == "unavailable"
    assert session.post.call_count == 1


async def test_a_changed_firmware_is_checked_at_the_next_tick_instead_of_hours_later():
    firmware, _, coordinator = make_firmware()
    coordinator.firmware_version = "NAV10_20.24-9"
    session = MagicMock()
    with (
        patch("custom_components.idm_heatpump.cloud_scheduler.async_track_time_interval"),
        patch("custom_components.idm_heatpump.firmware_observations.secrets.randbelow", return_value=600),
        patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session),
    ):
        assert await firmware.async_start() is True
        coordinator.async_add_listener.assert_called_once()
        observe = coordinator.async_add_listener.call_args.args[0]
        spread_slot = firmware._next_firmware_check
        assert spread_slot > time.time() + 30

        # The firmware known at startup is not a change and keeps the spread slot.
        observe()
        assert firmware._next_firmware_check == spread_slot
        session.assert_not_called()

        coordinator.firmware_version = "NAV10_20.24-12"
        observe()
        assert firmware._next_firmware_check == 0.0
        query = {
            "navigator": "navigator_10",
            "navigator_model": "Navigator 10",
            "heatpump_model": "AERO ALM",
            "firmware": "NAV10_20.24-12",
        }
        session.post.return_value = _session_with_answer(query, "NAV10_20.24-14", True).post.return_value
        await firmware.async_tick(datetime.now(UTC))
        assert session.post.call_count == 1
        assert session.post.call_args.kwargs["json"] == query
        assert firmware.firmware_result["installed_firmware"] == "NAV10_20.24-12"
        regular_slot = firmware._next_firmware_check
        assert regular_slot > time.time() + 21500

        # The same firmware again, or a second change right after a check, waits
        # for the regular slot: the catalog must not see a retry storm.
        observe()
        assert firmware._next_firmware_check == regular_slot
        coordinator.firmware_version = "NAV10_20.24-15"
        observe()
        assert firmware._next_firmware_check == regular_slot


def test_an_unconfirmed_pro_component_answer_survives_a_restart():
    restored = _restorable_result({**STORED_ANSWER, "component_status": "unconfirmed_pro_component"})

    assert restored is not None
    assert restored["component_status"] == "unconfirmed_pro_component"


async def test_firmware_query_falls_back_to_the_entered_plant_model():
    firmware, entry, coordinator = make_firmware()
    entry.options[CONF_PLANT_MODEL] = "AERO ALM 6-15"
    coordinator.web_supplement.heatpump_model = None
    coordinator.firmware_version = "NAV10_20.24-9"
    query = {
        "navigator": "navigator_10",
        "navigator_model": "Navigator 10",
        "heatpump_model": "AERO ALM 6-15",
        "firmware": "NAV10_20.24-9",
    }
    session = _session_with_answer(query, "NAV10_20.24-11", True)
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        await firmware.async_refresh_firmware()
    assert session.post.call_args.kwargs["json"] == query
    assert set(session.post.call_args.kwargs["json"]) == {"navigator", "navigator_model", "heatpump_model", "firmware"}
