"""Presentation layer for the Navigator 10 web demand reason.

The connection and the decode tables live in ``idm-heatpump-api`` (2.3.0+):
``IdmNavigator10WebClient.read_home_detail()`` returns an ``IdmWebHomeDetail``
with the decoded demand-reason widgets (``reason`` slugs like ``"pv"``) and the
energy-flow power values. This module only adds the German presentation labels
and the aggregate wording used by the Home Assistant entities.

Navigator 10 only: the Navigator 2.0 PHP interface has no home controller.
"""

from __future__ import annotations

import logging
from typing import Final

from idm_heatpump import IdmWebHomeDetail

_LOGGER = logging.getLogger(__name__)

REASON_LABELS: Final[dict[str, str]] = {
    # The idle widget (operationMode 0) is what the controller's display and
    # web interface render as "keine Anforderung" — the sensor mirrors that
    # wording instead of translating the API's "no_info" slug literally.
    "no_info": "Keine Anforderung",
    "off": "Aus",
    "more_demands": "Mehrere Anforderungen",
    "external_input": "Externer Eingang",
    "external_bus": "Externer Bus",
    "isc": "ISC",
    "pv": "PV",
    "frost_protection": "Frostschutz",
    "hc_a": "Heizkreis A",
    "hc_b": "Heizkreis B",
    "hc_c": "Heizkreis C",
    "hc_d": "Heizkreis D",
    "hc_e": "Heizkreis E",
    "hc_f": "Heizkreis F",
    "hc_g": "Heizkreis G",
    "system_off": "System aus",
    "ion": "ION",
    "single_loading": "Einzeladung",
    "single_loading_boost": "Einzeladung-Boost",
    "schedule": "Zeitprogramm",
    "schedule_boost": "Zeitprogramm-Boost",
    "dhw_comfort": "Komfort",
    "cascade": "Kaskade",
    "dhw_booster": "WW-Booster",
}


def demand_reason_label(detail: IdmWebHomeDetail) -> str | None:
    """Return the German aggregate label for one home/detail snapshot."""
    active = [node.reason for node in detail.demand_reasons if node.reason not in (None, "no_info", "off")]
    if not active:
        for node in detail.demand_reasons:
            if node.reason in ("no_info", "off"):
                return REASON_LABELS[node.reason]
        return None
    if len(set(active)) > 1:
        return REASON_LABELS["more_demands"]
    return REASON_LABELS[active[0]]


async def async_read_home_detail(client: object) -> IdmWebHomeDetail | None:
    """Fetch the home screen detail through a Navigator 10 web client.

    Uses the public API method (``idm-heatpump-api`` 2.3.0+). Any failure is
    non-fatal: the supplement simply keeps its previous demand reason.
    """
    read_home_detail = getattr(client, "read_home_detail", None)
    if not callable(read_home_detail):
        return None
    try:
        detail = await read_home_detail()
    except Exception:  # optional extra, never break the web supplement poll
        _LOGGER.debug("Navigator 10 home/detail demand reason unavailable", exc_info=True)
        return None
    return detail if isinstance(detail, IdmWebHomeDetail) else None


__all__ = [
    "REASON_LABELS",
    "async_read_home_detail",
    "demand_reason_label",
]
