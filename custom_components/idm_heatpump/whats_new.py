"""One-time "what's new" notice in Home Assistant's Repairs area.

Many users update without reading the release notes. This places a single,
dismissible notice where they already look for problems (Settings → Repairs)
whenever a release adds user-visible features. The notice is a persistent,
non-fixable issue: Home Assistant stores the user's dismissal, and
re-creating the issue preserves it, so it truly appears only once per
version. It is a notice, not an error — the translated text says so.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

#: Bump to the next version (and move the old id into _SUPERSEDED_IDS) when
#: a future release again warrants a notice. The id encodes the version so
#: Home Assistant tracks each notice's dismissal separately.
WHATS_NEW_ISSUE_ID: str = "whats_new_0_21_0"
WHATS_NEW_LEARN_MORE_URL: str = "https://xerolux.github.io/idm-heatpump-hass/docs/predictive-advisor/"

_SUPERSEDED_IDS: tuple[str, ...] = ()


def ensure_whats_new_issue(hass: HomeAssistant) -> None:
    """Show the current release notice once; dismissed notices stay gone.

    Re-creating an already dismissed issue keeps its dismissal (Home
    Assistant's issue registry preserves ``dismissed_version``), so calling
    this on every setup is safe.
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
