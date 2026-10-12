"""Fachmann Ebene code calculation for IDM Navigator heat pumps."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — unofficial community integration for IDM Navigator 2.0 / 10 heat pumps
# Created by Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# SPDX-License-Identifier: MIT
from datetime import datetime


def technician_code_levels(model_name: str | None = None) -> tuple[str, ...]:
    """Return only the access levels supported by the resolved controller."""
    if isinstance(model_name, str):
        normalized = model_name.casefold().replace(" ", "_").replace("-", "_")
        while "__" in normalized:
            normalized = normalized.replace("__", "_")
        if "navigator_1.7" in normalized or "navigator_1_7" in normalized or normalized.endswith("navigator_17"):
            return ("level_1",)
    return ("level_1", "level_2")


def calculate_codes(now: datetime | None = None, *, model_name: str | None = None) -> dict[str, str]:
    """Calculate Fachmann Ebene Level 1 and Level 2 codes for the given time.

    Navigator 1.7: one three-digit level-1 code, day parity + padded hour.
    Navigator 2.0/10/Pro Level 1: DDMM (day + month, both zero-padded).
    Level 2: last digit of hour, first digit of hour, last digit of year,
             last digit of month, last digit of day

    Important: When ``now`` is omitted, this uses the **Home Assistant host
    local time** (``datetime.now()``), not the Navigator controller clock.
    Codes will be wrong if HA runs in UTC (common in containers) while the
    heat pump display uses local wall time. Pass an explicit ``now`` in the
    desired local timezone when needed.
    """
    if now is None:
        now = datetime.now()

    if technician_code_levels(model_name) == ("level_1",):
        # Navigator 1.7 has one three-digit installer code (issue #486).
        # Preserve the leading zero on even days and single-digit hours.
        return {"level_1": f"{now.day % 2}{now.hour:02d}"}

    d_padded = f"{now.day:02d}"
    m_padded = f"{now.month:02d}"
    code_level_1 = f"{d_padded}{m_padded}"

    hours = f"{now.hour:02d}"
    hh_first = hours[0]
    hh_last = hours[1]
    year_last = str(now.year)[-1]
    month_last = str(now.month)[-1]
    day_last = str(now.day)[-1]
    code_level_2 = f"{hh_last}{hh_first}{year_last}{month_last}{day_last}"

    return {"level_1": code_level_1, "level_2": code_level_2}
