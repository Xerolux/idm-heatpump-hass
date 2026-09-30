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
