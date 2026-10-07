"""One-time "what's new" notice in Home Assistant's Repairs area.

Many users update without reading the release notes. This places a single,
dismissible notice where they already look for problems (Settings → Repairs)
when a release adds user-visible features.

The notice fires **exactly once per installed update** — never on a fresh
install, never again on restarts or reloads: each setup compares the entry's
``last_run_version`` stamp with the running integration version (manifest).
They differ only right after an update was installed, and that is the only
moment the issue is created; the stamp is then written back. The stamp lives
in ``entry.data`` and is fingerprint-exempt (see ``__init__``), so writing it
never reloads the entry. On top, the issue is persistent: Home Assistant
stores the user's dismissal and re-creating the issue preserves it. It is a
notice, not an error — the translated text says so.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

#: Bump to the next version (and move the old id into _SUPERSEDED_IDS) when
#: a future release again warrants a notice. The id encodes the version so
#: Home Assistant tracks each notice's dismissal separately.
WHATS_NEW_ISSUE_ID: str = "whats_new_0_21_0"
WHATS_NEW_LEARN_MORE_URL: str = "https://xerolux.github.io/idm-heatpump-hass/docs/predictive-advisor/"

#: entry.data key holding the integration version this entry last ran with.
#: Must stay listed in ``_DETECTION_ONLY_DATA_KEYS`` so stamping it never
#: triggers the reload fingerprint.
LAST_RUN_VERSION_DATA_KEY: str = "last_run_version"

_SUPERSEDED_IDS: tuple[str, ...] = ()


def ensure_whats_new_issue(hass: HomeAssistant) -> None:
    """Show the current release notice; dismissed notices stay dismissed.

    Re-creating an already dismissed issue keeps its dismissal (Home
    Assistant's issue registry preserves ``dismissed_version``).
    """
    for old_id in _SUPERSEDED_IDS:
        ir.async_delete_issue(hass, DOMAIN, old_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        WHATS_NEW_ISSUE_ID,
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=WHATS_NEW_ISSUE_ID,
        learn_more_url=WHATS_NEW_LEARN_MORE_URL,
    )
    _LOGGER.debug("IDM what's-new notice ensured (%s)", WHATS_NEW_ISSUE_ID)


async def async_note_release(hass: HomeAssistant, entry: ConfigEntry, current_version: str | None) -> None:
    """Fire the notice exactly on the update transition, once.

    ``current_version`` is the running integration version (manifest). The
    stored stamp equals it on every normal setup (restart, reload) — then
    nothing happens at all. A fresh install has no stamp: it is written
    without a notice, because a new user did not update anything. Only a
    stored *different* version means an update was just installed.
    """
    if not current_version:
        return
    data = dict(entry.data) if isinstance(entry.data, Mapping) else {}
    stored = data.get(LAST_RUN_VERSION_DATA_KEY)
    if stored == current_version:
        return
    if isinstance(stored, str) and stored:
        # An older version ran before: an update was just installed.
        ensure_whats_new_issue(hass)
    data[LAST_RUN_VERSION_DATA_KEY] = current_version
    update = getattr(hass.config_entries, "async_update_entry", None)
    if update is None:
        return
    result: Any = update(entry, data=data)
    if inspect.isawaitable(result):
        await result
