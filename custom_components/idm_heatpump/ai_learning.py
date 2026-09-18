"""Bounded statistical baselines; no model training or device actions."""

from __future__ import annotations

import math
from typing import Any

MAX_BUCKETS = 4096
RETENTION_DAYS = 365


def finite(value: Any) -> bool:
    """Reject booleans, non-numbers and non-finite values."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class LearningHistory:
    """Keep daily energy totals per mode and five-degree outdoor bin."""

    def __init__(self) -> None:
        self.buckets: dict[str, list[float]] = {}

    def load(self, value: Any, now: float) -> None:
        """Load only the bounded numerical schema, dropping expired entries."""
        if isinstance(value, dict):
            for key, row in list(value.items())[-MAX_BUCKETS:]:
                parts = str(key).split(":")
                if (
                    len(parts) == 3
                    and all(p.lstrip("-").isdigit() for p in parts)
                    and int(parts[1]) in (1, 2, 4)
                    and -12 <= int(parts[2]) <= 22
                    and isinstance(row, list)
                    and len(row) == 4
                    and all(finite(v) and 0 <= v <= 1e9 for v in row)
                ):
                    self.buckets[str(key)] = [float(v) for v in row]
        self.prune(now)

    def prune(self, now: float) -> None:
        day = int(now // 86400)
        self.buckets = dict(
            sorted(
                ((k, v) for k, v in self.buckets.items() if day - RETENTION_DAYS < int(k.split(":")[0]) <= day),
                key=lambda item: int(item[0].split(":")[0]),
            )[-MAX_BUCKETS:]
        )

    def observe(self, before: dict[str, Any], after: dict[str, Any]) -> None:
        """Reject gaps, mode changes, resets, standby and implausible intervals."""
        values = [
            r.get(k)
            for r in (before, after)
            for k in ("at", "outdoor_temp", "total_electrical_kwh", "total_thermal_kwh")
        ]
        mode = after.get("mode")
        if not all(finite(v) for v in values) or mode not in (1, 2, 4) or before.get("mode") != mode:
            return
        gap = after["at"] - before["at"]
        electric = after["total_electrical_kwh"] - before["total_electrical_kwh"]
        thermal = after["total_thermal_kwh"] - before["total_thermal_kwh"]
        if (
            not before.get("connected")
            or not after.get("connected")
            or not 0 < gap <= 900
            or electric <= 0
            or thermal < 0
            or thermal / electric > 15
            or electric * 3600 / gap > 1000
            or abs(after["outdoor_temp"] - before["outdoor_temp"]) > 5
        ):
            return
        key = f"{int(after['at'] // 86400)}:{int(mode)}:{math.floor(after['outdoor_temp'] / 5)}"
        row = self.buckets.setdefault(key, [0.0, 0.0, 0.0, 0.0])
        for i, value in enumerate((electric, thermal, gap, 1)):
            row[i] += value
        self.prune(after["at"])

    def comparison(self, sample: dict[str, Any]) -> dict[str, Any]:
        """Compare today's matched bin with prior days, never with itself."""
        result: dict[str, Any] = {
            "status": "collecting",
            "days": 0,
            "hours": 0.0,
            "baseline_cop": None,
            "current_cop": None,
            "deviation_percent": None,
        }
        if not finite(sample.get("outdoor_temp")) or sample.get("mode") not in (1, 2, 4):
            return result
        day = int(sample["at"] // 86400)
        suffix = f":{int(sample['mode'])}:{math.floor(sample['outdoor_temp'] / 5)}"
        rows = [v for k, v in self.buckets.items() if k.endswith(suffix) and int(k.split(":")[0]) < day]
        hours = sum(r[2] for r in rows) / 3600
        result.update(
            days=len(rows),
            hours=round(hours, 2),
            mode=int(sample["mode"]),
            outdoor_bin_c=math.floor(sample["outdoor_temp"] / 5) * 5,
        )
        electric = sum(r[0] for r in rows)
        if len(rows) < 3 or hours < 6 or electric <= 0:
            return result
        baseline = sum(r[1] for r in rows) / electric
        result.update(status="ready", baseline_cop=round(baseline, 2))
        current = self.buckets.get(f"{day}{suffix}")
        if current and current[2] >= 3600 and current[0] > 0 and baseline > 0:
            cop = current[1] / current[0]
            result.update(current_cop=round(cop, 2), deviation_percent=round(100 * (cop / baseline - 1), 1))
        return result
