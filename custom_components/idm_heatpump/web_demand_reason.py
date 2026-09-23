"""Demand-reason decoding from the Navigator 10 WebSocket home screen.

The Navigator controllers expose no internal PV-mode state register over
Modbus, but the local Navigator 10 web interface renders the display's
"Anforderungsgrund" (demand reason) — including **PV** — from a bitmask in
the ``home/detail`` WebSocket frame. The SPA decode table (verified against
``main-*.js`` of firmware jsonVersion 11, September 2026) is reproduced here
bit for bit:

* every widget that shows a demand reason carries ``operationMode`` and,
  while a demand is active, an ``info`` bitmask;
* ``operationMode`` 1 selects the heating reason table, 4 the domestic hot
  water table, 0 means "no information" and 8 "off";
* bit 32 means **PV** in both tables;
* more than one set bit (ignoring bit 0) is displayed as
  "mehrere Anforderungen".

This module is deliberately Navigator 10 only: Navigator 2.0 has a different
PHP-based web interface and is not covered.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

_LOGGER = logging.getLogger(__name__)

# SPA priority order: the first matching bit wins.
_HEATING_REASON_BITS: Final[tuple[tuple[int, str], ...]] = (
    (2, "no_info"),
    (4, "external_input"),
    (8, "external_bus"),
    (16, "isc"),
    (32, "pv"),
    (64, "frost_protection"),
    (128, "hc_a"),
    (256, "hc_b"),
    (512, "hc_c"),
    (1024, "hc_d"),
    (2048, "hc_e"),
    (4096, "hc_f"),
    (8192, "hc_g"),
    (16384, "system_off"),
    (32768, "ion"),
)
_DHW_REASON_BITS: Final[tuple[tuple[int, str], ...]] = (
    (2, "single_loading"),
    (4, "single_loading_boost"),
    (8, "external_input"),
    (16, "external_bus"),
    (32, "pv"),
    (64, "isc"),
    (128, "schedule"),
    (256, "schedule_boost"),
    (512, "system_off"),
    (1024, "dhw_comfort"),
    (2048, "ion"),
    (4096, "cascade"),
    (8192, "dhw_booster"),
)

REASON_LABELS: Final[dict[str, str]] = {
    "no_info": "Keine Information",
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

_OPERATION_MODE_HEATING: Final = 1
_OPERATION_MODE_DHW: Final = 4
_PV_BIT: Final = 32


def decode_demand_reason(operation_mode: int, info: int | None) -> str | None:
    """Decode one widget's demand reason exactly like the web UI.

    Returns ``None`` for an undocumented ``operationMode`` or an ``info``
    bitmask whose set bits are all unknown to the firmware tables.
    """
    if operation_mode == 0:
        return "no_info"
    if operation_mode == 8:
        return "off"
    if info is None:
        return None
    # The SPA checks "more than one bit set" (ignoring bit 0) before
    # consulting the reason tables.
    masked = info & -2
    if masked & (masked - 1):
        return "more_demands"
    if operation_mode == _OPERATION_MODE_HEATING:
        table = _HEATING_REASON_BITS
    elif operation_mode == _OPERATION_MODE_DHW:
        table = _DHW_REASON_BITS
    else:
        return None
    for bit, reason in table:
        if info & bit:
            return reason
    return None


@dataclass(frozen=True)
class DemandReasonNode:
    """One decoded demand-reason widget of the home screen."""

    path: str
    operation_mode: int
    info: int | None
    reason: str | None


@dataclass(frozen=True)
class WebDemandReasonState:
    """Aggregated demand reason of one ``home/detail`` snapshot."""

    nodes: tuple[DemandReasonNode, ...] = field(default_factory=tuple)

    @property
    def pv_active(self) -> bool:
        """Return whether any widget reports PV as its demand reason."""
        return any(node.reason == "pv" for node in self.nodes)

    @property
    def label(self) -> str | None:
        """Return the human-readable aggregate, or None while undecidable."""
        active = [node.reason for node in self.nodes if node.reason not in (None, "no_info", "off")]
        if not active:
            for node in self.nodes:
                if node.reason in ("no_info", "off"):
                    return REASON_LABELS[node.reason]
            return None
        if len(set(active)) > 1:
            return REASON_LABELS["more_demands"]
        return REASON_LABELS[active[0]]


def collect_demand_reason_nodes(payload: Mapping[str, Any]) -> list[DemandReasonNode]:
    """Collect every node carrying ``operationMode``/``info`` from a frame."""
    nodes: list[DemandReasonNode] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if "operationMode" in node or "info" in node:
                mode = node.get("operationMode")
                info = node.get("info")
                mode_int = mode if isinstance(mode, int) and not isinstance(mode, bool) else None
                info_int = info if isinstance(info, int) and not isinstance(info, bool) else None
                if mode_int is not None:
                    nodes.append(
                        DemandReasonNode(
                            path=path,
                            operation_mode=mode_int,
                            info=info_int,
                            reason=decode_demand_reason(mode_int, info_int),
                        )
                    )
            for key, value in node.items():
                walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(payload, "home")
    return nodes


def evaluate_demand_reason(payload: Mapping[str, Any]) -> WebDemandReasonState:
    """Evaluate the demand reason of one ``home/detail`` payload."""
    return WebDemandReasonState(nodes=tuple(collect_demand_reason_nodes(payload)))


async def async_read_home_detail_demand_reason(
    client: Any,
    timeout: float,
) -> WebDemandReasonState | None:
    """Fetch and evaluate ``home/detail`` through a Navigator 10 web client.

    Uses the pinned API client's WebSocket frame seam. Any failure is
    non-fatal: the supplement simply keeps its previous demand reason.
    """
    send_frame = getattr(client, "_send_json_and_receive_text", None)
    if not callable(send_frame):
        return None
    try:
        async with asyncio.timeout(timeout):
            raw = await send_frame({"controller": "home", "command": "detail"})
        payload = json.loads(raw)
    except Exception:
        _LOGGER.debug("Navigator 10 home/detail demand reason unavailable", exc_info=True)
        return None
    if not isinstance(payload, dict):
        return None
    return evaluate_demand_reason(payload)
