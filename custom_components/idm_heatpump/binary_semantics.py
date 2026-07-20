"""Binary sensor semantics shared by the IDM integration.

The IDM register map contains simple 0/1 states today, but some firmware and
future library metadata may use active-low values, bit masks, explicit on/off
sets, or negative values for an inactive state. Keeping the conversion in one
place prevents platform code from accidentally treating every non-zero value
as active (for example ``bool(-1) is True``).
"""

from __future__ import annotations

import math
from collections.abc import Collection
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

try:
    import idm_heatpump as idm_api
except ImportError:
    _GET_LIBRARY_BINARY_METADATA = None
else:
    _GET_LIBRARY_BINARY_METADATA = getattr(idm_api, "get_binary_register_metadata", None)

_DEVICE_CLASS_MAP: dict[str, BinarySensorDeviceClass] = {
    "problem": BinarySensorDeviceClass.PROBLEM,
    "connectivity": BinarySensorDeviceClass.CONNECTIVITY,
    "lock": BinarySensorDeviceClass.LOCK,
    "cold": BinarySensorDeviceClass.COLD,
    "heat": BinarySensorDeviceClass.HEAT,
    "running": BinarySensorDeviceClass.RUNNING,
    "power": BinarySensorDeviceClass.POWER,
}


def _library_metadata(name: str) -> Any | None:
    """Return optional neutral metadata from newer idm-heatpump-api releases."""
    if not callable(_GET_LIBRARY_BINARY_METADATA):
        return None
    return _GET_LIBRARY_BINARY_METADATA(name)


def infer_binary_device_class(name: str) -> BinarySensorDeviceClass | None:
    """Return an explicit or safely inferred Home Assistant device class."""
    metadata = _library_metadata(name)
    explicit = getattr(metadata, "device_class", None)
    if explicit in _DEVICE_CLASS_MAP:
        return _DEVICE_CLASS_MAP[explicit]

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


def _register_values(register: Any, plural: str, singular: str, library_attr: str) -> set[Any]:
    """Read register-local metadata, falling back to the API catalog."""
    values = _as_value_set(getattr(register, plural, None))
    values.update(_as_value_set(getattr(register, singular, None)))
    if values:
        return values
    metadata = _library_metadata(str(getattr(register, "name", "")))
    return _as_value_set(getattr(metadata, library_attr, None))


def binary_value_is_on(register: Any, value: Any) -> bool:
    """Convert a decoded IDM register value to a safe binary state.

    Register-local metadata takes priority. Newer API releases can additionally
    provide the same semantics through ``get_binary_register_metadata``. Both
    paths remain optional so the integration stays compatible with API 0.8.1.
    """
    if value is None:
        return False

    sentinel_values = _as_value_set(getattr(register, "sentinel_values", None))
    try:
        if value in sentinel_values:
            return False
    except TypeError:
        return False

    name = str(getattr(register, "name", ""))
    metadata = _library_metadata(name)
    on_values = _register_values(register, "binary_on_values", "binary_on_value", "on_values")
    off_values = _register_values(register, "binary_off_values", "binary_off_value", "off_values")
    bitmask = getattr(register, "binary_bitmask", None)
    if bitmask is None:
        bitmask = getattr(metadata, "bitmask", None)
    inverted = bool(
        getattr(register, "binary_inverted", False)
        or getattr(register, "binary_active_low", False)
        or getattr(metadata, "inverted", False)
    )

    if value in on_values:
        result = True
    elif value in off_values:
        result = False
    elif bitmask is not None:
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
            # or unavailable. They must never become active through bool(-1).
            result = value > 0
    else:
        result = bool(value)

    return not result if inverted else result
