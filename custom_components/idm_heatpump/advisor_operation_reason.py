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

_MODE_LABELS: Final[dict[int, str]] = {1: "Heating", 2: "Cooling", 4: "Hot water", 8: "Defrosting"}


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

    Priority: off → PV surplus → hot water → requesting heating circuit →
    the operating mode itself. Returns None when neither the operating mode
    nor the power draw is readable.
    """
    mode = data.get("hp_operating_mode")
    mode = mode if isinstance(mode, int) and not isinstance(mode, bool) else None
    power = _number(data.get("power_consumption_hp"))
    if mode is None and power is None:
        return None

    mode_label = _MODE_LABELS.get(mode, "Unknown") if mode is not None else "Unknown"
    outdoor = _number(data.get("outdoor_temp"))
    flow = _number(data.get("hp_flow_temp"))
    dhw_temp = _number(data.get("dhw_temp_top"))
    dhw_setpoint = _number(data.get("dhw_setpoint"))

    if mode == 0 or (power is not None and power < 0.05 and (mode is None or mode == 0)):
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

    if mode == 4 or (dhw_temp is not None and dhw_setpoint is not None and dhw_temp < dhw_setpoint - 3.0):
        short = dhw_setpoint - dhw_temp if dhw_temp is not None and dhw_setpoint is not None else None
        return OperationReason(
            label="Hot water",
            mode_label=mode_label,
            explanation=(
                "The hot-water tank is below its setpoint" + (f" by {short:.1f} K" if short is not None else "") + "."
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

    if demand_reason:
        return OperationReason(
            label=demand_reason,
            mode_label=mode_label,
            explanation=f"The controller reports '{demand_reason}' as the demand reason.",
            details={"operating_mode": mode, "demand_reason": demand_reason},
        )

    return OperationReason(
        label=mode_label,
        mode_label=mode_label,
        explanation=f"The heat pump runs in mode '{mode_label}'.",
        details={"operating_mode": mode, "outdoor_temp": outdoor, "power_consumption_kw": power},
    )
