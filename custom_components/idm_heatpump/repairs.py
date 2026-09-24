"""Repair flows for IDM Heatpump."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypeAlias

import voluptuous as vol
from homeassistant.components import repairs
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_DETECTED_NAVIGATOR_VERSION,
    CONF_DETECTED_SOFTWARE_VERSION,
    CONF_DETECTED_WEB_VARIANT,
    CONF_SOLAR_THERMAL,
    CONF_WEB_ENABLED,
    CONF_WEB_HOST,
    CONF_WEB_PIN,
    DOMAIN,
)
from .error_messages import scoped_issue_id
from .web_data import IdmWebAuthenticationFailed, async_read_web_supplement, web_pin_configured

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult
else:
    FlowResult: TypeAlias = dict[str, Any]

_ISSUE_WEB_PIN_MISSING = "web_pin_missing"
_ISSUE_WEB_AUTH_FAILED = "web_authentication_failed"
_ISSUE_SOLAR_MODULE_UNUSED = "solar_module_unused"
_ACTION_SET_PIN = "set_pin"
_ACTION_DISABLE_WEB = "disable_web"
_ACTION_DISABLE_SOLAR = "disable"
_ACTION_KEEP_SOLAR = "keep"
_LOGGER = logging.getLogger(__name__)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> repairs.RepairsFlow:
    """Create a repair flow for a fixable issue."""
    if issue_id.startswith(_ISSUE_SOLAR_MODULE_UNUSED):
        return IdmSolarUnusedRepairFlow(hass, data or {})
    return IdmWebPinMissingRepairFlow(hass, data or {})


class IdmWebPinMissingRepairFlow(repairs.RepairsFlow):
    """Resolve a missing local web PIN by setting it or disabling web data."""

    def __init__(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        self.hass = hass
        self._issue_data = data
        self._entry: ConfigEntry | None = None

    def _get_entry(self) -> ConfigEntry | None:
        if self._entry is not None:
            return self._entry

        entry_id = self._issue_data.get("entry_id")
        entries = list(self.hass.config_entries.async_entries(DOMAIN))
        if entry_id:
            self._entry = next((entry for entry in entries if entry.entry_id == entry_id), None)
        elif len(entries) == 1:
            self._entry = entries[0]
        return self._entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Choose how to resolve the missing PIN."""
        if self._get_entry() is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            action = user_input.get("action")
            if action == _ACTION_SET_PIN:
                return await self.async_step_set_pin()
            if action == _ACTION_DISABLE_WEB:
                return await self.async_step_disable_web()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): SelectSelector(
                        SelectSelectorConfig(
                            options=[_ACTION_SET_PIN, _ACTION_DISABLE_WEB],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="web_pin_missing_action",
                        )
                    )
                }
            ),
        )

    async def async_step_set_pin(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Store a valid local Navigator web PIN."""
        entry = self._get_entry()
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        errors: dict[str, str] = {}
        if user_input is not None:
            web_pin = str(user_input.get(CONF_WEB_PIN, "")).strip()
            if not web_pin_configured(web_pin):
                errors[CONF_WEB_PIN] = "web_pin_required"
            else:
                try:
                    web_supplement = await async_read_web_supplement(
                        str(entry.data.get(CONF_WEB_HOST) or entry.data[CONF_HOST]),
                        web_pin,
                        hass=self.hass,
                    )
                except IdmWebAuthenticationFailed:
                    _LOGGER.warning(
                        "IDM Navigator web PIN was rejected while repairing entry %s",
                        entry.entry_id,
                    )
                    errors[CONF_WEB_PIN] = "invalid_web_pin"
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning(
                        "IDM Navigator web access test failed while repairing entry %s: %s: %s",
                        entry.entry_id,
                        err.__class__.__name__,
                        err,
                    )
                    errors["base"] = "web_cannot_connect"
                else:
                    if web_supplement is None:
                        errors["base"] = "web_cannot_connect"
                        return self.async_show_form(
                            step_id="set_pin",
                            data_schema=vol.Schema(
                                {
                                    vol.Required(CONF_WEB_PIN): TextSelector(
                                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                                    )
                                }
                            ),
                            errors=errors,
                        )
                    data = dict(entry.data)
                    data[CONF_WEB_PIN] = web_pin
                    if web_supplement is not None:
                        if web_supplement.navigator_version:
                            data[CONF_DETECTED_NAVIGATOR_VERSION] = web_supplement.navigator_version
                        if web_supplement.software_version:
                            data[CONF_DETECTED_SOFTWARE_VERSION] = web_supplement.software_version
                        web_variant = getattr(web_supplement, "web_variant", None)
                        if web_variant:
                            data[CONF_DETECTED_WEB_VARIANT] = web_variant

                    options = {**entry.options, CONF_WEB_ENABLED: True}
                    self.hass.config_entries.async_update_entry(entry, data=data, options=options)
                    ir.async_delete_issue(self.hass, DOMAIN, scoped_issue_id(entry.entry_id, _ISSUE_WEB_PIN_MISSING))
                    ir.async_delete_issue(self.hass, DOMAIN, scoped_issue_id(entry.entry_id, _ISSUE_WEB_AUTH_FAILED))
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="set_pin",
            data_schema=vol.Schema(
                {vol.Required(CONF_WEB_PIN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
            ),
            errors=errors,
        )

    async def async_step_disable_web(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Disable optional web supplement data and clear the repair issue."""
        entry = self._get_entry()
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            data = {**entry.data, CONF_WEB_PIN: ""}
            options = {**entry.options, CONF_WEB_ENABLED: False}
            self.hass.config_entries.async_update_entry(entry, data=data, options=options)
            ir.async_delete_issue(self.hass, DOMAIN, scoped_issue_id(entry.entry_id, _ISSUE_WEB_PIN_MISSING))
            ir.async_delete_issue(self.hass, DOMAIN, scoped_issue_id(entry.entry_id, _ISSUE_WEB_AUTH_FAILED))
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="disable_web", data_schema=vol.Schema({}))


class IdmSolarUnusedRepairFlow(repairs.RepairsFlow):
    """Resolve the unused-solar-module suggestion.

    The issue is a suggestion, not a fault: a plant whose solar registers
    never report anything most likely has no collectors, and the fix either
    switches the module off (removing the empty *Solaranlage* group after a
    reload) or keeps it and dismisses this round of the suggestion.
    """

    def __init__(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        self.hass = hass
        self._issue_data = data

    def _get_entry(self) -> ConfigEntry | None:
        entry_id = self._issue_data.get("entry_id")
        entries = list(self.hass.config_entries.async_entries(DOMAIN))
        if entry_id:
            return next((entry for entry in entries if entry.entry_id == entry_id), None)
        if len(entries) == 1:
            return entries[0]
        return None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Choose whether to switch the solar module off or keep it."""
        if user_input is not None:
            action = user_input.get("action")
            if action == _ACTION_DISABLE_SOLAR:
                return await self.async_step_disable()
            if action == _ACTION_KEEP_SOLAR:
                return await self.async_step_keep()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): SelectSelector(
                        SelectSelectorConfig(
                            options=[_ACTION_DISABLE_SOLAR, _ACTION_KEEP_SOLAR],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="solar_unused_action",
                        )
                    )
                }
            ),
        )

    async def async_step_disable(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Turn the solar thermal module off and reload the entry."""
        entry = self._get_entry()
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        self.hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_SOLAR_THERMAL: False},
        )
        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            f"{_ISSUE_SOLAR_MODULE_UNUSED}_{entry.entry_id}",
        )
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_create_entry(title="", data={})

    async def async_step_keep(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Keep the module and dismiss this round of the suggestion."""
        entry = self._get_entry()
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        coordinator = getattr(getattr(entry, "runtime_data", None), "coordinator", None)
        dismiss = getattr(coordinator, "dismiss_solar_suggestion", None)
        if callable(dismiss):
            dismiss()
        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            f"{_ISSUE_SOLAR_MODULE_UNUSED}_{entry.entry_id}",
        )
        return self.async_create_entry(title="", data={})
