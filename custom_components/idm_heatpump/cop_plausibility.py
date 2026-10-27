"""Shared COP-sample plausibility guard for the two learning systems (#610).

The advisor's COP map and the AI learner's statistical baselines both derive a
coefficient of performance from electrical and thermal energy, but they guarded
those samples independently — the advisor did not guard the COP ratio at all,
so a spurious counter spike that ``ai_learning`` rejected could still bias the
advisor's map. This single predicate is the one source of truth for whether an
electrical/thermal interval can represent a real heat-pump COP.
"""

from __future__ import annotations

#: A COP above this is a counter artefact, not a heat pump (ai_learning's
#: historical bound, now shared with the advisor).
MAX_COP: float = 15.0
#: Sanity cap on the implied electrical power; anything above is a corrupted
#: counter or a doubled value, never a residential heat pump.
MAX_POWER_KW: float = 1000.0


def cop_interval_is_plausible(
    thermal: float,
    electric: float,
    *,
    electric_kw: float | None = None,
) -> bool:
    """Whether one thermal/electric interval can represent a real COP.

    ``thermal`` and ``electric`` are energy in matching units (both kWh or
    both Wh); their ratio is therefore unit-independent. ``electric_kw``
    optionally bounds the implied electrical power. Positive thermal output
    is required: an interval that consumed power without producing heat is
    not a usable COP sample.
    """
    if electric <= 0 or thermal <= 0:
        return False
    if thermal / electric > MAX_COP:
        return False
    return electric_kw is None or electric_kw <= MAX_POWER_KW
