"""Persistent acknowledgement of unconfirmed community firmware observations."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

ACK_KEY = "firmware_observation_acknowledgements"
LEARN_MORE = "https://xerolux.github.io/idm-heatpump-hass/docs/telemetry/#firmware-orientation"


def fingerprint(version: str) -> str:
    return hashlib.sha256(version.encode()).hexdigest()


def clear_notices(hass: HomeAssistant, entry_id: str, keep: str | None = None) -> None:
    prefix = f"firmware_observed_{entry_id}_"
    for domain, issue_id in list(ir.async_get(hass).issues):
        if domain == DOMAIN and issue_id.startswith(prefix) and issue_id != keep:
            ir.async_delete_issue(hass, DOMAIN, issue_id)


def ensure_notice(hass: HomeAssistant, entry: Any, result: dict[str, Any]) -> None:
    """Notify only a validated newer observation; never offer installation."""
    latest = result.get("latest_firmware")
    data = entry.data if isinstance(entry.data, Mapping) else {}
    acknowledged = data.get(ACK_KEY, [])
    if result.get("newer_observed") is not True or not isinstance(latest, str) or not latest:
        clear_notices(hass, entry.entry_id)
        return
    digest = fingerprint(latest)
    if isinstance(acknowledged, list) and digest in acknowledged:
        clear_notices(hass, entry.entry_id)
        return
    issue_id = f"firmware_observed_{entry.entry_id}_{digest[:16]}"
    clear_notices(hass, entry.entry_id, keep=issue_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="firmware_observed",
        translation_placeholders={"installed": str(result.get("installed_firmware") or "unknown"), "observed": latest},
        learn_more_url=LEARN_MORE,
        data={"entry_id": entry.entry_id, "firmware": latest, "fingerprint": digest},
    )
