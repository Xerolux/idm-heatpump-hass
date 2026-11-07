"""Entry lifecycle against a genuine Home Assistant (audit package E1).

Everything the stubbed suite cannot see lives here: the real config-entry
machinery, entity and device registries, stores and the background-task
bookkeeping. One walk through setup, reload and unload catches the lifecycle
bugs the audit was written for.
"""

from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er


async def test_differential_circuit_reload_preserves_temperature_ids(
    smoke_hass, patched_client, smoke_entry, fake_client
) -> None:
    """Real frozen descriptions and registry migration for issue #429."""

    def read(registers):
        values = {"hc_d_flow_temp": 41.83, "hc_d_room_temp": 22.63, "hc_d_active_mode": 255}
        return {register.name: values.get(register.name, 20.0) for register in registers}

    fake_client.read_batch.side_effect = read
    fake_client.detect_model.return_value.active_heating_circuits = ["a", "d"]
    await smoke_hass.config_entries.async_add(smoke_entry)
    await smoke_hass.async_block_till_done()
    assert smoke_entry.state is ConfigEntryState.LOADED
    smoke_hass.config_entries.async_update_entry(smoke_entry, options={"heating_circuits": ["a", "d"]})
    await smoke_hass.config_entries.async_reload(smoke_entry.entry_id)
    await smoke_hass.async_block_till_done()
    registry = er.async_get(smoke_hass)
    prefix = smoke_entry.entry_id + "_"

    def entries():
        return {
            e.unique_id.removeprefix(prefix): e
            for e in er.async_entries_for_config_entry(registry, smoke_entry.entry_id)
        }

    original = entries()
    temperature_ids = {key: original[key].entity_id for key in ("hc_d_flow_temp", "hc_d_room_temp")}
    smoke_hass.config_entries.async_update_entry(
        smoke_entry, options={"heating_circuits": ["a", "d"], "differential_circuits": ["d"]}
    )
    await smoke_hass.config_entries.async_reload(smoke_entry.entry_id)
    await smoke_hass.async_block_till_done()
    assert smoke_entry.state is ConfigEntryState.LOADED
    differential = entries()
    assert {key: differential[key].entity_id for key in temperature_ids} == temperature_ids
    assert "hc_d_heating_curve" not in differential
    assert "climate_hc_d" not in differential
    assert "hc_d_temperature_difference" in differential
    status = smoke_hass.states.get(differential["hc_d_active_mode"].entity_id)
    assert status is not None and status.state == "standby"
    delta = smoke_hass.states.get(differential["hc_d_temperature_difference"].entity_id)
    assert delta is not None and float(delta.state) == -19.2
    smoke_hass.config_entries.async_update_entry(smoke_entry, options={"heating_circuits": ["a", "d"]})
    await smoke_hass.config_entries.async_reload(smoke_entry.entry_id)
    await smoke_hass.async_block_till_done()
    assert "hc_d_heating_curve" in entries()
    assert "hc_d_temperature_difference" not in entries()
    assert await smoke_hass.config_entries.async_unload(smoke_entry.entry_id)
    await smoke_hass.async_block_till_done()


async def test_setup_reload_and_unload_leave_no_tasks_behind(smoke_hass, patched_client, smoke_entry) -> None:
    # async_add sets the entry up right away in current Home Assistant.
    await smoke_hass.config_entries.async_add(smoke_entry)
    await smoke_hass.async_block_till_done()
    assert smoke_entry.state is ConfigEntryState.LOADED

    registry = er.async_get(smoke_hass)
    entities = er.async_entries_for_config_entry(registry, smoke_entry.entry_id)
    # A Navigator 10 with heating circuit A carries hundreds of register
    # entities; a number this small means the platforms never attached.
    assert len(entities) > 50, f"only {len(entities)} entities were created"
    assert len({entity.unique_id for entity in entities}) == len(entities)
    live_states = [smoke_hass.states.get(entity.entity_id) for entity in entities]
    assert any(state is not None and state.state != "unavailable" for state in live_states)

    # Reload through the public path: unload plus setup again.
    await smoke_hass.config_entries.async_reload(smoke_entry.entry_id)
    await smoke_hass.async_block_till_done()
    assert smoke_entry.state is ConfigEntryState.LOADED
    reloaded = er.async_entries_for_config_entry(registry, smoke_entry.entry_id)
    assert {entity.unique_id for entity in reloaded} == {entity.unique_id for entity in entities}

    assert await smoke_hass.config_entries.async_unload(smoke_entry.entry_id)
    await smoke_hass.async_block_till_done()
    assert smoke_entry.state is ConfigEntryState.NOT_LOADED

    # The audit's core concern: nothing the integration started may outlive
    # the entry. Only the test's own task may remain on the loop.
    pending = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    assert not pending, f"leaked tasks after unload: {[task.get_coro() for task in pending]}"


async def test_shared_advisor_readback_review_survives_real_ha_reload(
    smoke_hass, patched_client, smoke_entry, fake_client
) -> None:
    """Exercise the actual Store, new entity registration and listener teardown."""
    from custom_components.idm_heatpump.advisor_evidence import AnalysisHistory

    values = {
        "hc_a_heating_curve": 1.0,
        "hp_operating_mode": 1,
        "power_consumption_hp": 2.0,
        "thermal_power_flow_sensor": 6.0,
        "outdoor_temp": 5.0,
        "hc_a_room_temp": 21.0,
        "hc_a_room_setpoint_heat_normal": 21.0,
    }
    fake_client.read_batch.side_effect = lambda registers: {
        register.name: values.get(register.name, 20.0) for register in registers
    }
    await smoke_hass.config_entries.async_add(smoke_entry)
    await smoke_hass.async_block_till_done()
    assert smoke_entry.state is ConfigEntryState.LOADED
    coordinator = smoke_entry.runtime_data.coordinator
    history = coordinator.analysis_history
    assert isinstance(history, AnalysisHistory)
    registry = er.async_get(smoke_hass)
    entities = {entry.unique_id: entry for entry in er.async_entries_for_config_entry(registry, smoke_entry.entry_id)}
    review_id = entities[f"{smoke_entry.entry_id}_advisor_optimization_review"].entity_id
    assert smoke_hass.states.get(review_id).state == "no_change_recorded"
    assert f"{smoke_entry.entry_id}_advisor_changes" in entities

    values["hc_a_heating_curve"] = 0.98
    await coordinator.async_request_refresh()
    await smoke_hass.async_block_till_done()
    assert len(history.changes) == 1
    assert history.changes[0]["after"] == 0.98
    await smoke_hass.config_entries.async_reload(smoke_entry.entry_id)
    await smoke_hass.async_block_till_done()
    reloaded = smoke_entry.runtime_data.coordinator.analysis_history
    assert isinstance(reloaded, AnalysisHistory) and reloaded is not history
    assert len(reloaded.changes) == 1 and reloaded.changes[0]["after"] == 0.98
    assert smoke_hass.states.get(review_id).state == "collecting_after"
    assert await smoke_hass.config_entries.async_unload(smoke_entry.entry_id)
    await smoke_hass.async_block_till_done()
    assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]


async def test_existing_ai_measurements_survive_shared_history_upgrade(smoke_hass, patched_client, smoke_entry) -> None:
    """Use actual HA storage and platform setup to exercise upgrade backfill."""
    import time

    from homeassistant.helpers.storage import Store

    from custom_components.idm_heatpump.const import CONF_AI_ADVISOR, DOMAIN

    now = time.time()
    records = [
        {
            "at": now - offset * 300,
            "connected": True,
            "mode": 1,
            "outdoor_temp": 5,
            "total_electrical_kwh": 1000 - offset,
            "total_thermal_kwh": 3000 - 3 * offset,
        }
        for offset in reversed(range(577))
    ]
    store = Store(smoke_hass, 1, f"{DOMAIN}.ai_advisor.{smoke_entry.entry_id}")
    await store.async_save({"records": records})
    await smoke_hass.config_entries.async_add(smoke_entry)
    await smoke_hass.async_block_till_done()
    smoke_hass.config_entries.async_update_entry(smoke_entry, options={CONF_AI_ADVISOR: True})
    await smoke_hass.async_block_till_done()
    assert smoke_entry.state is ConfigEntryState.LOADED
    advisor = smoke_entry.runtime_data.ai_advisor
    facts = advisor.build_facts("daily", now)
    assert facts["period"]["energy_counter_coverage_percent"] > 99
    assert facts["previous_period"]["cop_observed"] == 3
    await smoke_hass.config_entries.async_reload(smoke_entry.entry_id)
    await smoke_hass.async_block_till_done()
    facts = smoke_entry.runtime_data.ai_advisor.build_facts("daily", now)
    assert facts["period"]["energy_counter_coverage_percent"] > 99
    assert await smoke_hass.config_entries.async_unload(smoke_entry.entry_id)
    await smoke_hass.async_block_till_done()
    assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]


async def test_connection_entities_register_as_diagnostics(smoke_hass, patched_client, smoke_entry) -> None:
    """The connection entities must land in the device page's Diagnose section.

    Found in the wild: an installation carried none of the connection
    entities in its diagnostics card. The entity registry is what the device
    page groups by, so the smoke leg pins presence, diagnostic category and
    enabled state against a genuine Home Assistant. (web_last_success needs a
    configured web PIN and is not part of the web-less smoke entry.)
    """
    await smoke_hass.config_entries.async_add(smoke_entry)
    await smoke_hass.async_block_till_done()
    assert smoke_entry.state is ConfigEntryState.LOADED

    registry = er.async_get(smoke_hass)
    by_unique_id = {
        entity.unique_id: entity for entity in er.async_entries_for_config_entry(registry, smoke_entry.entry_id)
    }

    for suffix in ("connection_mode", "connection_reload"):
        unique_id = f"{smoke_entry.entry_id}_{suffix}"
        entry = by_unique_id.get(unique_id)
        assert entry is not None, f"{unique_id} was not registered"
        assert entry.entity_category is er.EntityCategory.DIAGNOSTIC, unique_id
        assert entry.disabled_by is None, unique_id

    assert await smoke_hass.config_entries.async_unload(smoke_entry.entry_id)
    await smoke_hass.async_block_till_done()


async def test_whats_new_notice_lands_in_repairs(smoke_hass, patched_client, smoke_entry) -> None:
    """The one-time what's-new notice must reach the Repairs roll-up card.

    The settings page's "N Reparaturen" card lists every active, non-dismissed
    issue of the issue registry. This pins the real-registry behaviour: the
    notice is there after setup, and once the user dismisses it, a reload (or
    restart) must not bring it back — Home Assistant preserves the dismissal
    because the issue is persistent.
    """
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers import issue_registry as ir

    from custom_components.idm_heatpump.const import DOMAIN
    from custom_components.idm_heatpump.whats_new import LAST_RUN_VERSION_DATA_KEY, WHATS_NEW_ISSUE_ID

    # Simulate the update case: this entry last ran an older release. A
    # fresh install (no stamp) must never produce the notice.
    updated_entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="IDM Update",
        data={
            "host": "192.0.2.1",
            "port": 502,
            "slave_id": 1,
            "name": "IDM Update",
            LAST_RUN_VERSION_DATA_KEY: "0.19.0",
        },
        options={},
        unique_id="idm-heatpump-update-smoke",
        source="user",
        state=ConfigEntryState.NOT_LOADED,
        discovery_keys={},
        subentries_data={},
    )
    await smoke_hass.config_entries.async_add(updated_entry)
    await smoke_hass.async_block_till_done()
    assert updated_entry.state is ConfigEntryState.LOADED

    registry = ir.async_get(smoke_hass)
    issue = registry.async_get_issue(DOMAIN, WHATS_NEW_ISSUE_ID)
    assert issue is not None, "the what's-new notice never reached the issue registry"
    assert issue.is_persistent is True
    assert issue.is_fixable is False
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == WHATS_NEW_ISSUE_ID
    assert issue.dismissed_version is None  # visible in the Repairs card

    # The user dismisses the notice once …
    registry.async_ignore(DOMAIN, WHATS_NEW_ISSUE_ID, True)
    dismissed = registry.async_get_issue(DOMAIN, WHATS_NEW_ISSUE_ID)
    assert dismissed is not None and dismissed.dismissed_version is not None

    # … and neither a reload nor a fresh setup may resurrect it: the entry
    # now carries the current version stamp, so the notice code never even
    # runs again for this release.
    assert updated_entry.data[LAST_RUN_VERSION_DATA_KEY] != "0.19.0"
    await smoke_hass.config_entries.async_reload(updated_entry.entry_id)
    await smoke_hass.async_block_till_done()
    after_reload = registry.async_get_issue(DOMAIN, WHATS_NEW_ISSUE_ID)
    assert after_reload is not None and after_reload.dismissed_version is not None

    assert await smoke_hass.config_entries.async_unload(updated_entry.entry_id)
    await smoke_hass.async_block_till_done()

    # A second, fresh entry on the same installation gets no notice at all.
    fresh = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="IDM Fresh",
        data={"host": "192.0.2.2", "port": 502, "slave_id": 1, "name": "IDM Fresh"},
        options={},
        unique_id="idm-heatpump-fresh-smoke",
        source="user",
        state=ConfigEntryState.NOT_LOADED,
        discovery_keys={},
        subentries_data={},
    )
    await smoke_hass.config_entries.async_add(fresh)
    await smoke_hass.async_block_till_done()
    fresh_issue = registry.async_get_issue(DOMAIN, "whats_new_0_21_0")
    assert fresh_issue is None or fresh_issue.dismissed_version is not None
    await smoke_hass.config_entries.async_unload(fresh.entry_id)
    await smoke_hass.async_block_till_done()


async def test_external_power_source_can_be_cleared_with_real_ha_selectors() -> None:
    """A cleared suggested entity must stay absent after actual HA validation."""
    from custom_components.idm_heatpump.config_flow import (
        _build_external_power_forwarding_schema,
        _store_external_power_forwarding_entities,
    )
    from custom_components.idm_heatpump.const import CONF_EXTERNAL_POWER_FORWARDING_ENTITIES

    options = {CONF_EXTERNAL_POWER_FORWARDING_ENTITIES: {"battery_soc": "sensor.battery_soc"}}
    schema = _build_external_power_forwarding_schema(options)
    submitted = schema({"external_power_forwarding_pv_production": "sensor.pv"})
    assert "external_power_forwarding_battery_soc" not in submitted
    _store_external_power_forwarding_entities(options, submitted)
    assert options[CONF_EXTERNAL_POWER_FORWARDING_ENTITIES] == {"pv_production": "sensor.pv"}


async def test_telemetry_reload_preserves_aggregates_and_refusal_erases_them(
    smoke_hass, patched_client, smoke_entry
) -> None:
    """Exercise real HA Store and lifecycle; never contact an external endpoint."""
    from datetime import UTC, datetime
    from pathlib import Path
    from unittest.mock import patch

    from custom_components.idm_heatpump.telemetry import TELEMETRY_POLICY

    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession") as session:
        await smoke_hass.config_entries.async_add(smoke_entry)
        await smoke_hass.async_block_till_done()
        assert smoke_entry.runtime_data.telemetry is None
        smoke_hass.config_entries.async_update_entry(
            smoke_entry,
            options={
                "telemetry": True,
                "telemetry_myidm_id": "TEST-Smoke-123",
                "telemetry_consent_at": datetime.now(UTC).isoformat(),
                "telemetry_policy": TELEMETRY_POLICY,
                "firmware_check": True,
                "firmware_policy": "idm-firmware-v1",
                "firmware_consent_at": datetime.now(UTC).isoformat(),
            },
        )
        await smoke_hass.config_entries.async_reload(smoke_entry.entry_id)
        await smoke_hass.async_block_till_done()
        telemetry = smoke_entry.runtime_data.telemetry
        assert telemetry is not None
        firmware_entities = [
            e
            for e in er.async_entries_for_config_entry(er.async_get(smoke_hass), smoke_entry.entry_id)
            if e.unique_id.endswith("_telemetry_latest_firmware")
        ]
        assert len(firmware_entities) == 1
        firmware_entity_id = firmware_entities[0].entity_id
        smoke_entry.runtime_data.firmware.firmware_result = {
            "status": "no_matching_observations",
            "latest_firmware": None,
        }
        for listener in tuple(smoke_entry.runtime_data.firmware._firmware_listeners):
            listener()
        await smoke_hass.async_block_till_done()
        firmware_state = smoke_hass.states.get(firmware_entity_id)
        assert firmware_state is not None and firmware_state.state == "unknown"
        assert firmware_state.attributes["status"] == "no_matching_observations"
        telemetry._pending["modbus_polls"] = 7
        await smoke_hass.config_entries.async_reload(smoke_entry.entry_id)
        await smoke_hass.async_block_till_done()
        restored = smoke_entry.runtime_data.telemetry
        assert restored is not None and restored is not telemetry
        assert restored.payload()["counters"]["modbus_polls"] >= 7
        path = Path(smoke_hass.config.path(".storage", "idm_heatpump.telemetry." + smoke_entry.entry_id))
        assert path.exists()
        smoke_hass.config_entries.async_update_entry(smoke_entry, options={"telemetry": False})
        await smoke_hass.config_entries.async_reload(smoke_entry.entry_id)
        await smoke_hass.async_block_till_done()
        assert smoke_entry.runtime_data.telemetry is None
        assert er.async_get(smoke_hass).async_get(firmware_entity_id) is None
        assert smoke_hass.states.get(firmware_entity_id) is None
        assert not path.exists()
        session.assert_not_called()  # Even opted-in startup queries are spread over time.
        assert await smoke_hass.config_entries.async_unload(smoke_entry.entry_id)
        await smoke_hass.async_block_till_done()
    pending = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    assert not pending


async def test_firmware_only_works_without_identity_or_telemetry_store(smoke_hass, patched_client, smoke_entry) -> None:
    """Exercise both independent consent boundaries in a genuine HA lifecycle."""
    from datetime import UTC, datetime
    from pathlib import Path
    from unittest.mock import patch

    options = {
        "firmware_check": True,
        "firmware_policy": "idm-firmware-v1",
        "firmware_consent_at": datetime.now(UTC).isoformat(),
        "telemetry": False,
    }
    with (
        patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession") as firmware_session,
        patch("custom_components.idm_heatpump.telemetry.async_get_clientsession") as analytics_session,
    ):
        await smoke_hass.config_entries.async_add(smoke_entry)
        await smoke_hass.async_block_till_done()
        smoke_hass.config_entries.async_update_entry(smoke_entry, options=options)
        await smoke_hass.config_entries.async_reload(smoke_entry.entry_id)
        await smoke_hass.async_block_till_done()
        assert smoke_entry.runtime_data.telemetry is None
        assert smoke_entry.runtime_data.firmware is not None
        firmware_session.assert_not_called()
        await smoke_entry.runtime_data.firmware.async_refresh_firmware()
        assert set(firmware_session.return_value.post.call_args.kwargs["json"]) == {
            "navigator",
            "navigator_model",
            "heatpump_model",
            "firmware",
        }
        analytics_session.assert_not_called()
        store = Path(smoke_hass.config.path(".storage", "idm_heatpump.telemetry." + smoke_entry.entry_id))
        assert not store.exists()
        entities = [
            e
            for e in er.async_entries_for_config_entry(er.async_get(smoke_hass), smoke_entry.entry_id)
            if e.unique_id.endswith("_telemetry_latest_firmware")
        ]
        assert len(entities) == 1
        entity_id = entities[0].entity_id
        options.update(
            {
                "firmware_check": False,
                "telemetry": True,
                "telemetry_myidm_id": "TEST-INDEPENDENT",
                "telemetry_policy": "idm-telemetry-v3",
                "telemetry_consent_at": datetime.now(UTC).isoformat(),
            }
        )
        count = firmware_session.call_count
        smoke_hass.config_entries.async_update_entry(smoke_entry, options=dict(options))
        await smoke_hass.config_entries.async_reload(smoke_entry.entry_id)
        await smoke_hass.async_block_till_done()
        assert smoke_entry.runtime_data.firmware is None
        assert smoke_entry.runtime_data.telemetry is not None
        assert er.async_get(smoke_hass).async_get(entity_id) is None
        assert smoke_hass.states.get(entity_id) is None
        assert firmware_session.call_count == count
        assert store.exists()
        analytics_session.assert_not_called()
        assert await smoke_hass.config_entries.async_unload(smoke_entry.entry_id)
        await smoke_hass.async_block_till_done()


async def test_retired_technician_registry_cleanup_once(smoke_hass, patched_client, smoke_entry) -> None:
    """Remove historical unique IDs in a real registry, including renamed sensors."""
    from types import SimpleNamespace

    from custom_components.idm_heatpump.device_hierarchy import cleanup_removed_technician_entities

    await smoke_hass.config_entries.async_add(smoke_entry)
    await smoke_hass.async_block_till_done()
    smoke_hass.config_entries.async_update_entry(smoke_entry, data={k: v for k, v in smoke_entry.data.items() if k != "technician_entities_removed_0263"})
    registry = er.async_get(smoke_hass)
    old = registry.async_get_or_create(
        "sensor",
        "idm_heatpump",
        f"{smoke_entry.entry_id}_technician_level_1",
        config_entry=smoke_entry,
        suggested_object_id="renamed_old_installer",
    )
    keep = registry.async_get_or_create(
        "sensor", "idm_heatpump", f"{smoke_entry.entry_id}_controller_clock", config_entry=smoke_entry
    )
    coordinator = SimpleNamespace(config_entry=smoke_entry)
    cleanup_removed_technician_entities(smoke_hass, coordinator)
    assert registry.async_get(old.entity_id) is None
    assert registry.async_get(keep.entity_id) is not None
    assert smoke_entry.data["technician_entities_removed_0263"] is True
    cleanup_removed_technician_entities(smoke_hass, coordinator)
    assert registry.async_get(keep.entity_id) is not None

