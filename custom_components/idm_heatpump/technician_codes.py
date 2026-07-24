"""Fachmann Ebene code calculation for IDM Navigator heat pumps."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT
from datetime import datetime


def calculate_codes(now: datetime | None = None) -> dict[str, str]:
    """Calculate Fachmann Ebene Level 1 and Level 2 codes for the given time.

    Level 1: DDMM  (day zero-padded + month zero-padded)
    Level 2: last digit of hour, first digit of hour, last digit of year,
             last digit of month, last digit of day

    Important: When ``now`` is omitted, this uses the **Home Assistant host
    local time** (``datetime.now()``), not the Navigator controller clock.
    Codes will be wrong if HA runs in UTC (common in containers) while the
    heat pump display uses local wall time. Pass an explicit ``now`` in the
    desired local timezone when needed.
    """
    if now is None:
        now = datetime.now()  # noqa: DTZ005

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
