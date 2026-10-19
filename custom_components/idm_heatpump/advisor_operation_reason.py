"""Compose the "why is the heat pump running" explanation (spec section 12).

Pure functions over one coordinator snapshot — no persistence, no writes.
The label is English data; the explanation sentence is composed from the
same numbers it shows, so it can never drift from them.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from .calculated_sensors import evaluate_pv_surplus_state
from .web_demand_reason import REASON_LABELS

_MODE_LABELS: Final[dict[int, str]] = {1: "Heating", 2: "Cooling", 4: "Hot water", 8: "Defrosting"}
_IDLE_DEMAND_REASONS: Final[frozenset[str]] = frozenset(
    {
        REASON_LABELS["no_info"],
        REASON_LABELS["off"],
        REASON_LABELS["system_off"],
    }
)
# The controller's web supplement reports demand reasons in its German UI
# wording. Passing those through verbatim made the sensor alternate between
# the composer's English labels ("Heating circuit A") and the German web
# label ("Heizkreis A") for the same physical cause (#538); known labels
# are mapped onto the composer's English vocabulary, unknown ones stay
# verbatim so a new controller wording remains recognizable.
_WEB_DEMAND_LABELS_EN: Final[dict[str, str]] = {
    **{REASON_LABELS[f"hc_{letter}"]: f"Heating circuit {letter.upper()}" for letter in "abcdefg"},
    REASON_LABELS["pv"]: "PV surplus",
    REASON_LABELS["more_demands"]: "Multiple demands",
    REASON_LABELS["external_input"]: "External input",
    REASON_LABELS["external_bus"]: "External bus",
    REASON_LABELS["frost_protection"]: "Frost protection",
    REASON_LABELS["ion"]: "ION",
    REASON_LABELS["single_loading"]: "DHW single charge",
    REASON_LABELS["single_loading_boost"]: "DHW single charge boost",
    REASON_LABELS["schedule"]: "Schedule",
    REASON_LABELS["schedule_boost"]: "Schedule boost",
    REASON_LABELS["dhw_comfort"]: "DHW comfort",
    REASON_LABELS["cascade"]: "Cascade",
    REASON_LABELS["dhw_booster"]: "DHW booster",
}


def _normalize_web_demand_label(label: str) -> str:
    """Map a controller web label onto the composer's English vocabulary."""
    return _WEB_DEMAND_LABELS_EN.get(label, label)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


@dataclass(frozen=True)
class OperationReason:
    """Why the heat pump runs right now, with the numbers behind it."""

    label: str
    mode_label: str
    explanation: str
    details: dict[str, Any]


def compose_operation_reason(
    data: Mapping[str, Any],
    *,
    demand_reason: str | None,
    circuits: tuple[str, ...] = ("a",),
) -> OperationReason | None:
    """Explain the current operation from one snapshot.

    Priority: off → PV surplus → hot water → defrosting → requesting heating
    circuit → active controller demand reason → the operating mode itself.
    Returns None when neither the operating mode nor the power draw is readable.
    """
    mode = data.get("hp_operating_mode")
    mode = mode if isinstance(mode, int) and not isinstance(mode, bool) else None
    power = _number(data.get("power_consumption_hp"))
    if mode is None and power is None:
        return None

    # The ``is not None`` guard is a type guard: the labels are keyed by int,
    # and ``mode`` legitimately reaches here as None (power-only snapshots).
    mode_label = _MODE_LABELS.get(mode, "Unknown") if mode is not None else "Unknown"
    outdoor = _number(data.get("outdoor_temp"))
    flow = _number(data.get("hp_flow_temp"))
    dhw_temp = _number(data.get("dhw_temp_top"))
    dhw_setpoint = _number(data.get("dhw_setpoint"))

    if mode == 0 or (power is not None and power < 0.05 and mode is None):
        return OperationReason(
            label="Off",
            mode_label=mode_label,
            explanation="The heat pump is not running.",
            details={"operating_mode": mode, "power_consumption_kw": power},
        )

    pv = evaluate_pv_surplus_state(data)
    if pv.is_on:
        return OperationReason(
            label="PV surplus",
            mode_label=mode_label,
            explanation="A photovoltaic surplus is signalled while the heat pump draws power.",
            details={
                "operating_mode": mode,
                "power_consumption_kw": power,
                "pv_surplus_kw": pv.pv_surplus_kw,
            },
        )

    if mode == 8:
        return OperationReason(
            label="Defrosting",
            mode_label=mode_label,
            explanation="The heat pump runs in mode 'Defrosting'.",
            details={"operating_mode": mode, "outdoor_temp": outdoor, "power_consumption_kw": power},
        )

    if mode == 4 or (mode != 2 and dhw_temp is not None and dhw_setpoint is not None and dhw_temp < dhw_setpoint - 3.0):
        short = dhw_setpoint - dhw_temp if dhw_temp is not None and dhw_setpoint is not None else None
        return OperationReason(
            label="Hot water",
            mode_label=mode_label,
            explanation=(
                "The hot-water tank is below its setpoint"
                + (f" by {short:.1f} K" if short is not None and short > 0 else "")
                + "."
            ),
            details={
                "operating_mode": mode,
                "dhw_temp_top": dhw_temp,
                "dhw_setpoint": dhw_setpoint,
            },
        )

    for circuit in circuits:
        room = _number(data.get(f"hc_{circuit}_room_temp"))
        room_setpoint = _number(data.get(f"hc_{circuit}_room_setpoint_heat_normal"))
        circuit_flow = _number(data.get(f"hc_{circuit}_flow_temp"))
        circuit_setpoint = _number(data.get(f"hc_{circuit}_setpoint_flow_temp"))
        if (
            circuit_setpoint is not None
            and circuit_setpoint > 0
            and (circuit_flow is None or circuit_flow < circuit_setpoint - 0.3)
        ):
            short_room = room_setpoint - room if room is not None and room_setpoint is not None else None
            return OperationReason(
                label=f"Heating circuit {circuit.upper()}",
                mode_label=mode_label,
                explanation=(
                    f"Heating circuit {circuit.upper()} requests flow: the flow temperature is below its setpoint"
                    + (
                        f" and the room is {short_room:.1f} K under target"
                        if short_room is not None and short_room > 0
                        else ""
                    )
                    + "."
                ),
                details={
                    "operating_mode": mode,
                    "circuit": circuit,
                    "flow_temp": circuit_flow if circuit_flow is not None else flow,
                    "flow_setpoint": circuit_setpoint,
                    "room_temp": room,
                    "room_setpoint": room_setpoint,
                    "outdoor_temp": outdoor,
                },
            )

    if demand_reason and demand_reason not in _IDLE_DEMAND_REASONS:
        normalized_reason = _normalize_web_demand_label(demand_reason)
        return OperationReason(
            label=normalized_reason,
            mode_label=mode_label,
            explanation=f"The controller reports '{normalized_reason}' as the demand reason.",
            details={"operating_mode": mode, "demand_reason": normalized_reason, "demand_reason_raw": demand_reason},
        )

    return OperationReason(
        label=mode_label,
        mode_label=mode_label,
        explanation=f"The heat pump runs in mode '{mode_label}'.",
        details={"operating_mode": mode, "outdoor_temp": outdoor, "power_consumption_kw": power},
    )
