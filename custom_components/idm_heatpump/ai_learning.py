"""Bounded statistical baselines; no model training or device actions."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

MAX_BUCKETS = 4096
RETENTION_DAYS = 365
BASELINE_MIN_DAYS = 3
BASELINE_MIN_HOURS = 6.0
CURRENT_MIN_HOURS = 3600.0  # seconds of matched-bin observation on the current day
_MODE_NAMES = {1: "heating", 2: "cooling", 4: "dhw"}


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
                    len(str(key)) <= 64
                    and len(parts) == 3
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
        if (
            not all(finite(v) for v in values)
            or not finite(mode)
            or mode not in (1, 2, 4)
            or before.get("mode") != mode
        ):
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

    def best_bucket(self, now: float) -> dict[str, Any]:
        """Report the best-covered bucket, independent of the current mode.

        While the plant idles, ``comparison`` has no current operating point
        and reads as if nothing had been learned at all. This answers "is
        learning actually progressing anywhere" with the (mode, outdoor bin)
        combination that is closest to the baseline threshold. Buckets are
        keyed per day, so counting keys per combination counts days.
        """
        day = int(now // 86400)
        grouped: dict[tuple[int, int], dict[str, float]] = {}
        for key, row in self.buckets.items():
            parts = str(key).split(":")
            if len(parts) != 3 or int(parts[0]) >= day:
                continue
            entry = grouped.setdefault((int(parts[1]), int(parts[2])), {"days": 0.0, "hours": 0.0})
            entry["days"] += 1
            entry["hours"] += row[2]
        if not grouped:
            return {"mode": None, "outdoor_bin_c": None, "days": 0, "hours": 0.0}
        (mode, bin_index), entry = max(grouped.items(), key=lambda item: (item[1]["days"], item[1]["hours"]))
        return {
            "mode": _MODE_NAMES.get(mode, mode),
            "outdoor_bin_c": bin_index * 5,
            "days": int(entry["days"]),
            "hours": round(entry["hours"] / 3600, 2),
        }

    def comparison(self, sample: dict[str, Any]) -> dict[str, Any]:
        """Compare today's matched bin with prior days, never with itself."""
        result: dict[str, Any] = {
            "status": "collecting",
            "days": 0,
            "hours": 0.0,
            "baseline_cop": None,
            "current_cop": None,
            "deviation_percent": None,
            "status_reason": None,
            "best_bucket": self.best_bucket(float(sample.get("at") or 0.0)),
        }
        if not finite(sample.get("outdoor_temp")) or sample.get("mode") not in (1, 2, 4):
            result["status_reason"] = "idle"
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
        if len(rows) < BASELINE_MIN_DAYS or hours < BASELINE_MIN_HOURS or electric <= 0:
            result["status_reason"] = "sparse_data"
            return result
        baseline = sum(r[1] for r in rows) / electric
        result.update(status="ready", baseline_cop=round(baseline, 2))
        current = self.buckets.get(f"{day}{suffix}")
        if current and current[2] >= CURRENT_MIN_HOURS and current[0] > 0 and baseline > 0:
            cop = current[1] / current[0]
            result.update(current_cop=round(cop, 2), deviation_percent=round(100 * (cop / baseline - 1), 1))
        return result

    def summary(self, now: float) -> dict[str, Any]:
        """Learned coverage across every bin, independent of the current mode.

        ``comparison`` answers for the current operating point only; while the
        plant idles it has no answer at all. This totals what was learned.
        """
        day = int(now // 86400)
        older: list[tuple[int, int, list[float]]] = []
        for key, row in self.buckets.items():
            parts = str(key).split(":")
            if len(parts) == 3 and int(parts[0]) < day:
                older.append((int(parts[0]), int(parts[1]), row))
        oldest = min((bucket_day for bucket_day, _, _ in older), default=None)
        return {
            "total_days": len({bucket_day for bucket_day, _, _ in older}),
            "buckets": len(older),
            "total_hours": round(sum(row[2] for _, _, row in older) / 3600, 2),
            "modes": sorted({_MODE_NAMES.get(mode, str(mode)) for _, mode, _ in older}),
            "oldest_learning_day_utc": (
                datetime.fromtimestamp(oldest * 86400, UTC).date().isoformat() if oldest is not None else None
            ),
        }
