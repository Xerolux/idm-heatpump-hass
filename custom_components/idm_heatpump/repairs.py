"""Repair flows for IDM Heatpump."""

from __future__ import annotations

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
    CONF_WEB_ENABLED,
    CONF_WEB_HOST,
    CONF_WEB_PIN,
    DOMAIN,
)
from .web_data import IdmWebAuthenticationFailed, async_read_web_supplement, web_pin_configured

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult
else:
    FlowResult: TypeAlias = dict[str, Any]

_ISSUE_WEB_PIN_MISSING = "web_pin_missing"
_ACTION_SET_PIN = "set_pin"
_ACTION_DISABLE_WEB = "disable_web"


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> repairs.RepairsFlow:
    """Create a repair flow for a fixable issue."""
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
                    )
                except IdmWebAuthenticationFailed:
                    errors[CONF_WEB_PIN] = "invalid_web_pin"
                else:
                    data = dict(entry.data)
                    data[CONF_WEB_PIN] = web_pin
                    if web_supplement is not None:
                        if web_supplement.navigator_version:
                            data[CONF_DETECTED_NAVIGATOR_VERSION] = web_supplement.navigator_version
                        if web_supplement.software_version:
                            data[CONF_DETECTED_SOFTWARE_VERSION] = web_supplement.software_version

                    options = {**entry.options, CONF_WEB_ENABLED: True}
                    self.hass.config_entries.async_update_entry(entry, data=data, options=options)
                    ir.async_delete_issue(self.hass, DOMAIN, _ISSUE_WEB_PIN_MISSING)
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
            ir.async_delete_issue(self.hass, DOMAIN, _ISSUE_WEB_PIN_MISSING)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="disable_web", data_schema=vol.Schema({}))
