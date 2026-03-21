from __future__ import annotations
"""Fachmann Ebene code calculation for IDM Navigator heat pumps."""

from datetime import datetime


def calculate_codes(now: datetime | None = None) -> dict[str, str]:
    """Calculate Fachmann Ebene Level 1 and Level 2 codes for the given time.

    Level 1: DDMM  (day zero-padded + month zero-padded)
    Level 2: last digit of hour, first digit of hour, last digit of year,
             last digit of month, last digit of day
    """
    if now is None:
        now = datetime.now()

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
