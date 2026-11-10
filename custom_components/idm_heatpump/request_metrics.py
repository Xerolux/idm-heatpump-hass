"""Passive request-level metrics for the Modbus transport boundary.

The whole-poll aggregates in :class:`~.coordinator.PollStatistics` answer "how
long did one coordinator cycle take".  They cannot answer "how long does one
physical request take" — which request dominates a poll, how durations
distribute, or how many requests the resilient bisect path and the write path
add.  Those numbers are the evidence the open field validations need (shared
links under several holders, maximum-plant response times, Navigator 2.0/Pro
capture review), so this module measures them without changing any I/O.

:class:`RequestMetricsRecorder` keeps a bounded window of per-request records
(function code, register count, duration, outcome class).  Everything stays in
memory, per config entry, and is redaction-safe by construction: records hold
counts and durations, never hosts, addresses or payloads.

:class:`RequestMetricsTransport` wraps either production transport (the private
tmodbus socket or the shared Home Assistant claim) and times every request
method passively — the wrapped transport still performs the I/O, this class
only observes the call.  It is a deliberate decorator, not a second transport
path.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from idm_heatpump import (
    IdmConnectionError,
    IdmDeviceError,
    IdmTransportError,
    IllegalAddressError,
)

from .modbus_shared_transport import HaModbusTransport
from .modbus_transport import ModbusTcpEndpoint, ModbusTransportCapabilities

#: Requests kept per config entry.  One window covers the recent past without
#: growing with uptime; 100 requests is roughly one to two poll cycles of a
#: fully equipped plant plus retries.
REQUEST_METRICS_WINDOW_SIZE = 100

#: Function-code labels used as diagnostics keys (kept short for dashboards).
FUNCTION_CODE_LABELS: dict[str, str] = {
    "fc01": "read coils (FC01)",
    "fc03": "read holding registers (FC03)",
    "fc04": "read input registers (FC04)",
    "fc05": "write single coil (FC05)",
    "fc16": "write registers (FC16)",
}

_OUTCOME_SUCCESS = "success"
_OUTCOME_TIMEOUT = "timeout"
_OUTCOME_CONNECTION = "connection_error"
_OUTCOME_TRANSPORT = "transport_error"
_OUTCOME_ILLEGAL_ADDRESS = "illegal_address"
_OUTCOME_DEVICE = "device_error"
_OUTCOME_OTHER = "other_error"

_DURATION_KEYS = ("min", "median", "average", "p95", "max")


@dataclass(frozen=True, slots=True)
class RequestRecord:
    """One observed transport request; durations only, no addresses or hosts."""

    function_code: str
    register_count: int
    duration_seconds: float
    outcome: str
    at: datetime


def _classify_error(error: Exception) -> str:
    """Map an API exception to a stable, diagnostics-safe outcome class.

    The classes mirror the transport's exception translation
    (:mod:`.modbus_transport`) so a reported outcome matches what the API retry
    loop did with the same error.  Order matters:
    :class:`~idm_heatpump.IllegalAddressError` is a subclass of
    :class:`~idm_heatpump.IdmDeviceError` and must be classified first.
    """
    if isinstance(error, IllegalAddressError):
        return _OUTCOME_ILLEGAL_ADDRESS
    if isinstance(error, TimeoutError):
        return _OUTCOME_TIMEOUT
    if isinstance(error, IdmConnectionError):
        return _OUTCOME_CONNECTION
    if isinstance(error, IdmTransportError):
        return _OUTCOME_TRANSPORT
    if isinstance(error, IdmDeviceError):
        return _OUTCOME_DEVICE
    return _OUTCOME_OTHER


def _percentile(sorted_values: list[float], fraction: float) -> float:
    """Return the nearest-rank percentile of pre-sorted values."""
    if not sorted_values:
        return 0.0
    rank = max(1, math.ceil(fraction * len(sorted_values)))
    return sorted_values[rank - 1]


def _duration_summary(durations: list[float]) -> dict[str, float] | None:
    """Return min/median/average/p95/max, rounded for stable diagnostics."""
    if not durations:
        return None
    ordered = sorted(durations)
    return {
        "min": round(ordered[0], 4),
        "median": round(_percentile(ordered, 0.5), 4),
        "average": round(sum(ordered) / len(ordered), 4),
        "p95": round(_percentile(ordered, 0.95), 4),
        "max": round(ordered[-1], 4),
    }


class RequestMetricsRecorder:
    """Bounded in-memory window of request records for one config entry."""

    def __init__(self, window_size: int = REQUEST_METRICS_WINDOW_SIZE) -> None:
        """Prepare an empty window; ``window_size`` must be positive."""
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        self._records: deque[RequestRecord] = deque(maxlen=window_size)

    def record(
        self,
        function_code: str,
        register_count: int,
        duration_seconds: float,
        outcome: str = _OUTCOME_SUCCESS,
    ) -> None:
        """Append one observation; the oldest record drops out when full."""
        self._records.append(
            RequestRecord(
                function_code=function_code,
                register_count=register_count,
                duration_seconds=duration_seconds,
                outcome=outcome,
                at=datetime.now(UTC),
            )
        )

    def __len__(self) -> int:
        """Return how many requests the window currently holds."""
        return len(self._records)

    def median_duration_seconds(self) -> float | None:
        """Return the median request duration, or ``None`` without samples."""
        if not self._records:
            return None
        ordered = sorted(record.duration_seconds for record in self._records)
        return round(_percentile(ordered, 0.5), 4)

    def snapshot(self) -> dict[str, Any]:
        """Return the aggregate diagnostics view (plain, redaction-safe data)."""
        records = list(self._records)
        if not records:
            return {
                "window_size": self._records.maxlen,
                "requests_recorded": 0,
            }
        outcomes: dict[str, int] = {}
        by_function: dict[str, dict[str, Any]] = {}
        for record in records:
            outcomes[record.outcome] = outcomes.get(record.outcome, 0) + 1
            entry = by_function.setdefault(
                record.function_code,
                {"requests": 0, "registers": 0, "errors": 0, "durations_seconds": []},
            )
            entry["requests"] += 1
            entry["registers"] += record.register_count
            if record.outcome != _OUTCOME_SUCCESS:
                entry["errors"] += 1
            entry["durations_seconds"].append(record.duration_seconds)
        span = (records[-1].at - records[0].at).total_seconds()
        return {
            "window_size": self._records.maxlen,
            "requests_recorded": len(records),
            "window_seconds": round(span, 1),
            "outcomes": dict(sorted(outcomes.items())),
            "duration_seconds": _duration_summary([r.duration_seconds for r in records]),
            "by_function_code": {
                code: {
                    "label": FUNCTION_CODE_LABELS.get(code, code),
                    "requests": entry["requests"],
                    "registers": entry["registers"],
                    "errors": entry["errors"],
                    "duration_seconds": _duration_summary(entry["durations_seconds"]),
                }
                for code, entry in sorted(by_function.items())
            },
            "function_codes": sorted(by_function),
        }


class RequestMetricsTransport:
    """Transport decorator timing every request of the wrapped transport.

    Implements the API ``IdmModbusTransport`` surface by delegation: the
    wrapped transport (private socket or shared claim) still performs all I/O;
    this class observes each call, records duration and outcome, and re-raises
    every exception unchanged.  Cancels
    (``asyncio.CancelledError``) are not requests and are not recorded.
    """

    def __init__(
        self,
        transport: HaModbusTransport,
        recorder: RequestMetricsRecorder | None = None,
    ) -> None:
        self._transport = transport
        self._recorder = recorder if recorder is not None else RequestMetricsRecorder()
        # Preserve the idm-heatpump-api 2.15.0 lazy-connect declaration of the
        # wrapped transport so the API retry loop keeps its semantics.
        self.connects_lazily = bool(getattr(transport, "connects_lazily", False))

    @property
    def endpoint(self) -> ModbusTcpEndpoint:
        """Return the immutable endpoint definition of the wrapped transport."""
        return self._transport.endpoint

    @property
    def connected(self) -> bool:
        """Return the wrapped transport's connection state."""
        return self._transport.connected

    @property
    def capabilities(self) -> ModbusTransportCapabilities:
        """Return the wrapped transport's static capabilities."""
        return self._transport.capabilities

    @property
    def request_metrics(self) -> RequestMetricsRecorder:
        """Return the recorder, mainly for tests and diagnostics wiring."""
        return self._recorder

    def request_metrics_snapshot(self) -> dict[str, Any]:
        """Return the aggregate request-metrics view."""
        return self._recorder.snapshot()

    async def connect(self) -> None:
        """Delegate to the wrapped transport without recording (no request)."""
        await self._transport.connect()

    async def close(self) -> None:
        """Delegate to the wrapped transport without recording (no request)."""
        await self._transport.close()

    async def _timed(
        self,
        function_code: str,
        register_count: int,
        coroutine: Any,
    ) -> Any:
        """Await one request, recording duration and outcome either way."""
        started = time.monotonic()
        try:
            result = await coroutine
        except Exception as error:
            self._recorder.record(
                function_code,
                register_count,
                time.monotonic() - started,
                _classify_error(error),
            )
            raise
        self._recorder.record(
            function_code,
            register_count,
            time.monotonic() - started,
            _OUTCOME_SUCCESS,
        )
        return result

    async def read_holding_registers(self, *, address: int, count: int) -> list[int]:
        """Read raw holding-register words (FC03) through the wrapped transport."""
        return list(
            await self._timed(
                "fc03",
                count,
                self._transport.read_holding_registers(address=address, count=count),
            )
        )

    async def read_input_registers(self, *, address: int, count: int) -> list[int]:
        """Read raw input-register words (FC04) through the wrapped transport."""
        return list(
            await self._timed(
                "fc04",
                count,
                self._transport.read_input_registers(address=address, count=count),
            )
        )

    async def write_registers(self, *, address: int, values: list[int]) -> None:
        """Write raw holding-register words (FC16) through the wrapped transport."""
        await self._timed(
            "fc16",
            len(values),
            self._transport.write_registers(address=address, values=values),
        )

    async def read_coils(self, *, address: int, count: int) -> list[bool]:
        """Read discrete coils (FC01) through the wrapped transport."""
        return list(
            await self._timed(
                "fc01",
                count,
                self._transport.read_coils(address=address, count=count),
            )
        )

    async def write_coil(self, *, address: int, value: bool) -> None:
        """Write a single coil (FC05) through the wrapped transport."""
        await self._timed(
            "fc05",
            1,
            self._transport.write_coil(address=address, value=value),
        )

    def as_redacted_diagnostics(self) -> dict[str, object]:
        """Merge the wrapped transport's diagnostics with the metrics snapshot."""
        diagnostics = dict(self._transport.as_redacted_diagnostics())
        diagnostics["request_metrics"] = self._recorder.snapshot()
        return diagnostics


__all__ = [
    "FUNCTION_CODE_LABELS",
    "REQUEST_METRICS_WINDOW_SIZE",
    "RequestMetricsRecorder",
    "RequestMetricsTransport",
    "RequestRecord",
]
