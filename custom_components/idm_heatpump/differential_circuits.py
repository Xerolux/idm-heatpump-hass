"""Opt-in semantics for differential-temperature controlled heating circuits."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from .const import CONF_DIFFERENTIAL_CIRCUITS, CONF_HEATING_CIRCUITS, HEATING_CIRCUITS

_REGISTER = re.compile(r"^hc_([a-g])_(.+)$")
_MEASUREMENTS = {
    "flow_temp": "hc_storage_temp",
    "room_temp": "hc_reference_temp",
    "active_mode": "hc_differential_status",
}


def differential_circuits(options: Mapping[str, Any]) -> frozenset[str]:
    """Return selected, installed circuits; ignore malformed stored options."""
    selected = options.get(CONF_DIFFERENTIAL_CIRCUITS, ())
    installed = options.get(CONF_HEATING_CIRCUITS, ["a"])
    if not isinstance(selected, (list, tuple)) or not isinstance(installed, (list, tuple)):
        return frozenset()
    return (
        frozenset(str(c).lower() for c in selected)
        & frozenset(str(c).lower() for c in installed)
        & frozenset(HEATING_CIRCUITS)
    )


#: Regulation type of a differential-temperature controlled circuit in the
#: Navigator 10 ``system/overview`` frame. The numbering follows the
#: Heizsystem chooselist order (Keines / Ungeregelt / Geregelt / Konstant /
#: Differenztemperaturgeregelt); ``2`` (Geregelt) is live-confirmed, the
#: differential value rests on that order and awaits field confirmation.
NAVIGATOR10_CIRCUIT_TYPE_DIFFERENTIAL = 4


def web_detected_differential_circuits(system_overview: Any) -> frozenset[str]:
    """Detect differential circuits from the web system/overview frame.

    Works on the raw ``IdmWebSystemOverview`` (or anything shaped like it) and
    never raises: a missing or differently-shaped frame detects nothing.
    """
    circuits = getattr(system_overview, "heating_circuits", None)
    if not isinstance(circuits, (list, tuple)):
        return frozenset()
    detected: set[str] = set()
    for circuit in circuits:
        circuit_id = getattr(circuit, "circuit_id", None)
        circuit_type = getattr(circuit, "type", None)
        if (
            isinstance(circuit_id, str)
            and circuit_id.lower() in HEATING_CIRCUITS
            and circuit_type == NAVIGATOR10_CIRCUIT_TYPE_DIFFERENTIAL
        ):
            detected.add(circuit_id.lower())
    return frozenset(detected)


def configured_differential_circuits(coordinator: Any) -> frozenset[str]:
    """Options plus web detection, without transport or hierarchy coupling."""
    options = getattr(getattr(coordinator, "config_entry", None), "options", {})
    selected = differential_circuits(options) if isinstance(options, Mapping) else frozenset()
    detected: frozenset[str] = getattr(coordinator, "web_differential_circuits", frozenset())
    if not isinstance(detected, frozenset):
        return selected
    return selected | detected


def differential_register_translation(name: str, circuits: frozenset[str]) -> str | None:
    """Return the context-specific translation for a retained measurement."""
    match = _REGISTER.match(name)
    if match and match[1] in circuits:
        return _MEASUREMENTS.get(match[2])
    return None


def register_allowed(name: str, circuits: frozenset[str]) -> bool:
    """Keep only confirmed read-only measurements for selected circuits."""
    if not circuits:
        return True
    match = _REGISTER.match(name)
    return not match or match[1] not in circuits or match[2] in _MEASUREMENTS


def filter_descriptions(
    descriptions: list[dict[str, Any]], circuits: frozenset[str], *, sensors: bool = False
) -> list[dict[str, Any]]:
    """Filter controls and rename measurements without changing register IDs."""
    if not circuits:
        return descriptions
    result = []
    for item in descriptions:
        name = item["register"].name
        translation = differential_register_translation(name, circuits)
        if not register_allowed(name, circuits) or (translation and not sensors):
            continue
        if translation:
            description = item["description"]
            changes: dict[str, Any] = {"translation_key": translation}
            if translation == "hc_differential_status":
                changes["options"] = ["off", "heating", "cooling", "standby"]
            item = {**item, "description": replace(description, **changes)}
        result.append(item)
    return result


def web_value_allowed(key: str, circuits: frozenset[str]) -> bool:
    """Suppress normal circuit temperatures and mixer values; keep the pump."""
    return not any(
        key in {f"mixer_heating_circuit{c.upper()}", f"flow_temp_HK_{c.upper()}", f"room_temperature_HK_{c.upper()}"}
        for c in circuits
    )
