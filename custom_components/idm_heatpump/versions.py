"""Runtime dependency version helpers for diagnostics and entities."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import cache
from importlib.metadata import PackageNotFoundError, version


@dataclass(frozen=True)
class RuntimeVersions:
    """Versions relevant when diagnosing the integration runtime."""

    integration: str
    api: str
    pymodbus: str


@cache
def distribution_version(distribution: str) -> str:
    """Return an installed distribution version without failing setup."""
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "unknown"


def runtime_versions(integration_version: object) -> RuntimeVersions:
    """Build a stable version snapshot for logs, sensors, and diagnostics."""
    return RuntimeVersions(
        integration=str(integration_version or "unknown"),
        api=distribution_version("idm-heatpump-api"),
        pymodbus=distribution_version("pymodbus"),
    )


async def async_runtime_versions(integration_version: object) -> RuntimeVersions:
    """Build the version snapshot without blocking the Home Assistant event loop."""
    return await asyncio.to_thread(runtime_versions, integration_version)
