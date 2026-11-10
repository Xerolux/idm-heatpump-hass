"""Localized titles for advisor recommendations.

The recommendation ``title`` remains a documented English data field — events,
diagnostics and stored records stay machine-readable and stable across
languages.  Every producer additionally names a stable ``title_key`` plus
pre-formatted placeholder values; this module renders the user-facing variant
in German or English, following the bilingual-table discipline of
:func:`~.advisor_evidence.explain_recommendation` (spec section 13: producers
ship translations for their categories).

Values are formatted at the producing site (which knows the precision: whole
percent, one-decimal kelvin, two-decimal curve values) using period decimal
separators; the German renderer swaps them to commas, mirroring
``assist_agent._format``.  Unknown keys answer ``None`` so callers fall back
to the stored English title instead of showing a raw key.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

#: title key -> (German template, English template). Placeholders are named
#: and filled with the pre-formatted strings the engine passes.
TITLE_TEXTS: Final[dict[str, tuple[str, str]]] = {
    "anomaly_flow_rate_low": (
        "Der Heizkreis-Volumenstrom liegt {percent} % unter der {days}-Tage-Baseline",
        "Heat-circle flow is {percent}% below its {days}-day baseline",
    ),
    "anomaly_flow_rate_low_heating": (
        "Der Heizkreis-Volumenstrom liegt {percent} % unter der {days}-Tage-Baseline beim Heizen",
        "Heat-circle flow is {percent}% below its {days}-day heating baseline",
    ),
    "anomaly_flow_rate_low_dhw": (
        "Der Heizkreis-Volumenstrom liegt {percent} % unter der {days}-Tage-Baseline beim Warmwasser",
        "Heat-circle flow is {percent}% below its {days}-day hot-water baseline",
    ),
    "anomaly_spread_high": (
        "Die Spreizung liegt über ihrer Baseline",
        "Flow/return spread is above its baseline",
    ),
    "anomaly_spread_high_k": (
        "Die Spreizung liegt {delta} K über ihrer Baseline",
        "Flow/return spread is {delta} K above its baseline",
    ),
    "anomaly_compressor_starts": (
        "Die Kompressorstarts liegen {percent} % über der {days}-Tage-Baseline",
        "Compressor starts are {percent}% above the {days}-day baseline",
    ),
    "anomaly_dhw_charge_long": (
        "Die Warmwasserladung dauert {percent} % länger als üblich",
        "Hot-water charging takes {percent}% longer than usual",
    ),
    "advisor_heating_curve_review": (
        "Heizkurve HK {circuit} prüfen: {curve} → {recommended}",
        "Review heating curve HC {circuit}: {curve} -> {recommended}",
    ),
    "advisor_dhw_window_pv": (
        "Warmwasser um {window} erwägen: PV-Prognose {pv_kwh} kWh; Überschuss unbestätigt",
        "Consider hot water {window}: forecast PV generation {pv_kwh} kWh; surplus unconfirmed",
    ),
    "advisor_dhw_window_price": (
        "Warmwasser um {window} erwägen: niedrigste geschätzte Wärmekosten {heat_cost} €/kWh",
        "Consider hot water {window}: lowest estimated heat cost {heat_cost} €/kWh",
    ),
    "advisor_dhw_window_conflict": (
        "Das empfohlene Warmwasser-Fenster überschneidet sich mit den teuersten Stunden",
        "Recommended hot-water window overlaps the most expensive hours",
    ),
}


def render_title(key: str, values: Mapping[str, str] | None, language: str = "en") -> str | None:
    """Render one localized title, or ``None`` for an unknown key.

    German output swaps the placeholder decimal points to commas — only the
    substituted values carry decimals, so the surrounding text stays untouched.
    """
    templates = TITLE_TEXTS.get(key)
    if templates is None:
        return None
    german = language.startswith("de")
    template = templates[0] if german else templates[1]
    if not values:
        return template
    substituted = {name: (str(value).replace(".", ",") if german else str(value)) for name, value in values.items()}
    return template.format(**substituted)


def localized_title(key: str, values: Mapping[str, str] | None, fallback: str, language: str = "en") -> str:
    """Return the rendered title, falling back to the stored English title."""
    rendered = render_title(key, values, language)
    return rendered if rendered is not None else fallback


__all__ = ["TITLE_TEXTS", "localized_title", "render_title"]
