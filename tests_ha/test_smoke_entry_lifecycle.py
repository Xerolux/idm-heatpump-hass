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
