"""GLT measurement classification helpers."""

from __future__ import annotations

import re

_GLT_MEASUREMENT_NAMES: frozenset[str] = frozenset(
    {
        "pv_surplus",
        "pv_production",
        "house_consumption",
        "battery_discharge",
        "battery_soc",
        "electric_heater_power",
    }
)

_ZONE_ROOM_MEASUREMENT_RE = re.compile(r"zm\d+_room\d+_(temp|humidity)$")


def is_glt_measurement(name: str) -> bool:
    """Return true when a writable register represents a GLT measurement input."""
    return name in _GLT_MEASUREMENT_NAMES or _ZONE_ROOM_MEASUREMENT_RE.match(name) is not None


def is_zone_room_measurement(name: str) -> bool:
    """Return true for zone room temperature and humidity GLT measurement inputs."""
    return _ZONE_ROOM_MEASUREMENT_RE.match(name) is not None
