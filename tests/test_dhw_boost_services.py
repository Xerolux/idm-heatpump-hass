"""Tests for the IDM DHW boost service handlers.

Covers ``dhw_boost_services.py`` (registration, multi-entry routing,
start/cancel handlers, error translation) — these were previously
untested despite being a stable-release-critical path.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.idm_heatpump import dhw_boost_services as module
from custom_components.idm_heatpump.coordinator import IdmCoordinator
from custom_components.idm_heatpump.dhw_boost import DhwBoostError


def _make_entry(entry_id="entry-1", state=ConfigEntryState.LOADED, coordinator=None):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.state = state
    runtime = MagicMock()
    runtime.coordinator = coordinator
    entry.runtime_data = runtime
    return entry


def _make_coordinator():
    """A coordinator stub that passes the isinstance(_, IdmCoordinator) guard."""
    return MagicMock(spec=IdmCoordinator)


def _make_hass(entries):
    hass = MagicMock()
    # The service module uses the synchronous ``has_service`` helper.
    hass.services.has_service.return_value = False
    hass.services.async_register = MagicMock()
    hass.services.async_remove = MagicMock()
    hass.config_entries.async_entries.return_value = entries
    return hass


def _make_call(data=None):
    call = MagicMock()
    call.data = data or {}
    return call


class _CapturingManager:
    """Minimal stand-in for DhwBoostManager."""

    def __init__(self) -> None:
        self.default_target_temperature = 60
        self.default_timeout_minutes = 60
        self.start_calls = []
        self.cancel_calls = []
        self.start_error: DhwBoostError | None = None
        self.cancel_error: DhwBoostError | None = None

    async def async_start(self, *, target_temperature, timeout_minutes):
        self.start_calls.append((target_temperature, timeout_minutes))
        if self.start_error is not None:
            raise self.start_error

    async def async_cancel(self):
        self.cancel_calls.append(True)
        if self.cancel_error is not None:
            raise self.cancel_error


@pytest.fixture(autouse=True)
def _patch_manager_factory(monkeypatch):
    """Replace async_get_dhw_boost_manager with a controllable stub.

    Mirrors the real factory: returns the same manager instance per
    coordinator, so tests can pre-configure ``start_error``/``cancel_error``
    on a known instance before invoking the handler.
    """
    captured: dict[str, object] = {}
    managers: dict[int, _CapturingManager] = {}

    async def _fake_get_manager(coordinator):
        manager = managers.setdefault(id(coordinator), _CapturingManager())
        captured["manager"] = manager
        captured["coordinator"] = coordinator
        return manager

    monkeypatch.setattr(module, "async_get_dhw_boost_manager", _fake_get_manager)
    return captured


# ---------------------------------------------------------------------------
# Service registration / unloading lifecycle
# ---------------------------------------------------------------------------


class TestServiceRegistration:
    async def test_setup_registers_both_services_once(self):
        hass = _make_hass([])

        await module.async_setup_dhw_boost_services(hass)

        registered = [(c.args[0], c.args[1]) for c in hass.services.async_register.call_args_list]
        assert (module.DOMAIN, module._START_SERVICE) in registered
        assert (module.DOMAIN, module._CANCEL_SERVICE) in registered

    async def test_setup_skips_already_registered_services(self):
        hass = _make_hass([])
        hass.services.has_service.return_value = True

        await module.async_setup_dhw_boost_services(hass)

        hass.services.async_register.assert_not_called()

    async def test_unload_removes_services_when_last_entry_goes(self):
        unloading = _make_entry(entry_id="entry-1")
        # No other loaded entries remain.
        hass = _make_hass([unloading])
        # ``async_unload_dhw_boost_services`` only removes services that
        # ``has_service`` reports as registered.
        hass.services.has_service.return_value = True

        await module.async_unload_dhw_boost_services(hass, "entry-1")

        removed = [(c.args[0], c.args[1]) for c in hass.services.async_remove.call_args_list]
        assert (module.DOMAIN, module._START_SERVICE) in removed
        assert (module.DOMAIN, module._CANCEL_SERVICE) in removed

    async def test_unload_keeps_services_when_other_entries_remain(self):
        unloading = _make_entry(entry_id="entry-1")
        remaining = _make_entry(entry_id="entry-2")
        hass = _make_hass([unloading, remaining])

        await module.async_unload_dhw_boost_services(hass, "entry-1")

        hass.services.async_remove.assert_not_called()


# ---------------------------------------------------------------------------
# _get_manager routing
# ---------------------------------------------------------------------------


class TestGetManagerRouting:
    async def test_single_loaded_entry_resolves_coordinator(self, _patch_manager_factory):
        coord = _make_coordinator()
        entry = _make_entry(coordinator=coord)
        hass = _make_hass([entry])

        manager = await module._get_manager(hass, _make_call())

        assert manager is _patch_manager_factory["manager"]
        assert _patch_manager_factory["coordinator"] is coord

    async def test_no_loaded_entry_raises_no_device_configured(self):
        hass = _make_hass([])

        with pytest.raises(ServiceValidationError) as exc_info:
            await module._get_manager(hass, _make_call())

        assert exc_info.value.translation_key == "no_device_configured"
        assert exc_info.value.translation_domain == module.DOMAIN

    async def test_multiple_entries_without_id_raises_translated_error(self):
        hass = _make_hass([_make_entry("a"), _make_entry("b")])

        with pytest.raises(ServiceValidationError) as exc_info:
            await module._get_manager(hass, _make_call())

        assert exc_info.value.translation_key == "multiple_entries_select_entry"

    async def test_multiple_entries_with_entry_id_filters(self, _patch_manager_factory):
        coord_b = _make_coordinator()
        entries = [_make_entry("a"), _make_entry("b", coordinator=coord_b)]
        hass = _make_hass(entries)

        manager = await module._get_manager(hass, _make_call({"entry_id": "b"}))

        assert _patch_manager_factory["coordinator"] is coord_b
        assert manager is _patch_manager_factory["manager"]

    async def test_non_loaded_entry_state_is_skipped(self, _patch_manager_factory):
        loaded = _make_entry("a", coordinator=_make_coordinator())
        not_loaded = _make_entry("b", state=ConfigEntryState.SETUP_ERROR)
        hass = _make_hass([loaded, not_loaded])

        # Only one loaded entry, so no entry_id required.
        manager = await module._get_manager(hass, _make_call())
        assert manager is not None


# ---------------------------------------------------------------------------
# Start / cancel handlers
# ---------------------------------------------------------------------------


class TestStartHandler:
    async def test_start_with_defaults(self, _patch_manager_factory):
        entry = _make_entry(coordinator=_make_coordinator())
        hass = _make_hass([entry])

        await module._handle_start(hass, _make_call())

        manager: _CapturingManager = _patch_manager_factory["manager"]
        assert manager.start_calls == [(60, 60)]

    async def test_start_with_explicit_values(self, _patch_manager_factory):
        entry = _make_entry(coordinator=_make_coordinator())
        hass = _make_hass([entry])

        await module._handle_start(
            hass,
            _make_call({"target_temperature": 55, "timeout_minutes": 90}),
        )

        manager: _CapturingManager = _patch_manager_factory["manager"]
        assert manager.start_calls == [(55, 90)]

    async def test_start_translates_dhw_boost_error(self, _patch_manager_factory):
        coord = _make_coordinator()
        entry = _make_entry(coordinator=coord)
        hass = _make_hass([entry])

        # Prime the cached manager first so we can inject the error
        # before the handler runs. The factory returns the same instance
        # for the same coordinator, matching the real implementation.
        manager = await module._get_manager(hass, _make_call())
        manager.start_error = DhwBoostError(
            "intern",
            translation_key="dhw_boost_unsupported",
        )

        with pytest.raises(HomeAssistantError) as exc_info:
            await module._handle_start(hass, _make_call())

        assert exc_info.value.translation_key == "dhw_boost_unsupported"
        assert exc_info.value.translation_domain == module.DOMAIN

    async def test_start_falls_back_to_raw_string_without_translation_key(self, _patch_manager_factory):
        coord = _make_coordinator()
        entry = _make_entry(coordinator=coord)
        hass = _make_hass([entry])

        manager = await module._get_manager(hass, _make_call())
        manager.start_error = DhwBoostError("raw text")

        with pytest.raises(HomeAssistantError) as exc_info:
            await module._handle_start(hass, _make_call())

        assert str(exc_info.value) == "raw text"


class TestCancelHandler:
    async def test_cancel_delegates_to_manager(self, _patch_manager_factory):
        entry = _make_entry(coordinator=_make_coordinator())
        hass = _make_hass([entry])

        await module._handle_cancel(hass, _make_call())

        assert _patch_manager_factory["manager"].cancel_calls == [True]

    async def test_cancel_translates_dhw_boost_error(self, _patch_manager_factory):
        coord = _make_coordinator()
        entry = _make_entry(coordinator=coord)
        hass = _make_hass([entry])

        manager = await module._get_manager(hass, _make_call())
        manager.cancel_error = DhwBoostError(
            "intern",
            translation_key="dhw_boost_restore_failed",
        )

        with pytest.raises(HomeAssistantError) as exc_info:
            await module._handle_cancel(hass, _make_call())

        assert exc_info.value.translation_key == "dhw_boost_restore_failed"
