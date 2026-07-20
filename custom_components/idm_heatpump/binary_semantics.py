"""Binary sensor semantics shared by the IDM integration.

The IDM register map contains simple 0/1 states today, but some firmware and
future library metadata may use active-low values, bit masks, explicit on/off
sets, or negative values for an inactive state.  Keeping the conversion in one
place prevents platform code from accidentally treating every non-zero value
as active (for example ``bool(-1) is True``).
"""

from __future__ import annotations

import math
from collections.abc import Collection
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass


def infer_binary_device_class(name: str) -> BinarySensorDeviceClass | None:
    """Infer the most useful Home Assistant binary device class from a key."""
    normalized = name.casefold()

    if any(token in normalized for token in ("fault", "failure", "alarm", "error", "störung")):
        return BinarySensorDeviceClass.PROBLEM
    if any(token in normalized for token in ("connected", "connectivity", "online", "reachable")):
        return BinarySensorDeviceClass.CONNECTIVITY
    if any(token in normalized for token in ("lock", "locked", "sperre", "sperr")):
        return BinarySensorDeviceClass.LOCK
    if any(token in normalized for token in ("cooling", "cool", "defrost", "kühl", "abtau")):
        return BinarySensorDeviceClass.COLD
    if any(token in normalized for token in ("heating", "heat", "dhw", "hotwater", "warmwasser")):
        return BinarySensorDeviceClass.HEAT
    if any(token in normalized for token in ("compressor", "pump", "relay", "fan", "demand", "running")):
        return BinarySensorDeviceClass.RUNNING
    return None


def _as_value_set(value: Any) -> set[Any]:
    """Normalize optional scalar or collection metadata to a set."""
    if value is None:
        return set()
    if isinstance(value, Collection) and not isinstance(value, (str, bytes, bytearray)):
        return set(value)
    return {value}


def _metadata_values(register: Any, plural: str, singular: str) -> set[Any]:
    """Read future-proof plural or singular register metadata."""
    values = _as_value_set(getattr(register, plural, None))
    values.update(_as_value_set(getattr(register, singular, None)))
    return values


def binary_value_is_on(register: Any, value: Any) -> bool:
    """Convert a decoded IDM register value to a safe binary state.

    Supported optional metadata fields on ``RegisterDef`` are intentionally
    accessed with ``getattr`` so this integration remains compatible with the
    currently pinned API while being ready for richer register metadata:

    - ``binary_on_values`` / ``binary_on_value``
    - ``binary_off_values`` / ``binary_off_value``
    - ``binary_bitmask``
    - ``binary_inverted`` / ``binary_active_low``
    """
    if value is None:
        return False

    sentinel_values = _as_value_set(getattr(register, "sentinel_values", None))
    try:
        if value in sentinel_values:
            return False
    except TypeError:
        return False

    on_values = _metadata_values(register, "binary_on_values", "binary_on_value")
    off_values = _metadata_values(register, "binary_off_values", "binary_off_value")
    inverted = bool(
        getattr(register, "binary_inverted", False)
        or getattr(register, "binary_active_low", False)
    )

    if value in on_values:
        result = True
    elif value in off_values:
        result = False
    elif (bitmask := getattr(register, "binary_bitmask", None)) is not None:
        try:
            result = bool(int(value) & int(bitmask))
        except (TypeError, ValueError):
            result = False
    elif isinstance(value, bool):
        result = value
    elif isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "on", "true", "yes", "active", "running", "ein", "aktiv"}:
            result = True
        elif normalized in {"0", "off", "false", "no", "inactive", "stopped", "aus", "inaktiv"}:
            result = False
        else:
            result = False
    elif isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            result = False
        else:
            # Negative controller values conventionally indicate off, invalid,
            # or unavailable.  They must never become active through bool(-1).
            result = value > 0
    else:
        result = bool(value)

    return not result if inverted else result
