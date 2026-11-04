"""Normalize read-only advisor inputs consistently across models and quality."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from homeassistant.const import UnitOfTemperature
from homeassistant.util.unit_conversion import TemperatureConverter


def room_temperature_celsius(state: Any) -> float | None:
    """Read a mapped HA temperature; absent units retain Celsius compatibility.

    Unavailable or mismatched sources never fall back to an unrelated register.
    NaN represents present but unusable data for the advisor quality classifier.
    """
    raw = getattr(state, "state", None)
    if raw is None or raw in ("unknown", "unavailable", "none"):
        return None
    if isinstance(raw, bool):
        return math.nan
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return math.nan
    attributes = getattr(state, "attributes", {})
    unit = attributes.get("unit_of_measurement") if isinstance(attributes, Mapping) else None
    if unit in (None, "", UnitOfTemperature.CELSIUS):
        return value
    if unit not in (UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.KELVIN):
        return math.nan
    return float(TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS))
