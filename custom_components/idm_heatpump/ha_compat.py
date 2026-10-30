"""Version-tolerant imports for the supported Home Assistant range.

Home Assistant replaced voluptuous with probatio as its schema validation
engine (2026.9+). At runtime ``import voluptuous`` keeps resolving through
Home Assistant's ``sys.modules`` alias, so nothing changes for users — but
the Home Assistant annotations now name ``probatio`` types, and flow-result
types became generic (``FlowResult[FlowContext, str]``) with the canonical
repairs-step annotation named ``RepairsFlowResult``. Component enums such as
``BinarySensorDeviceClass`` and ``WaterHeaterEntityFeature`` live in
per-component ``const`` modules that the package re-exports only implicitly.

This module resolves the right implementation at runtime and deliberately
types every re-export as ``Any``: the runtime objects behave identically on
each supported version, and ``Any`` is the only static type both the real
library and probatio's signatures accept under strict mypy. Import ``vol``
and the moved symbols from here instead of their canonical locations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Static surface, deliberately Any (see the module docstring).
    vol: Any
    BinarySensorDeviceClass: Any
    WaterHeaterEntityFeature: Any
    RepairsFlowResult: Any
else:
    try:
        # On Home Assistant >= 2026.9 this import resolves to probatio
        # through the sys.modules alias Home Assistant installs at startup;
        # in the stubbed unit suite it is the real library.
        import voluptuous as vol  # re-export
    except ImportError:  # pragma: no cover - only if the alias is ever dropped
        import probatio as vol  # noqa: F401  # re-export

    from homeassistant.components.binary_sensor.const import (  # noqa: F401
        BinarySensorDeviceClass,
    )
    from homeassistant.components.repairs import RepairsFlowResult  # noqa: F401
    from homeassistant.components.water_heater.const import (  # noqa: F401
        WaterHeaterEntityFeature,
    )


MIN_HA_MAJOR_MINOR: tuple[int, int] = (2026, 11)
#: Human-readable form of the minimum for error messages: the beta the
#: integration validates against, and the stable that supersedes it.
MIN_HA_VERSION_LABEL: str = "2026.11.0b0"


def ha_running_version() -> str:
    """Return the running Home Assistant version, or '' when unavailable."""
    try:
        from homeassistant.const import __version__
    except ImportError:  # stubbed unit-test builds carry no __version__
        return ""
    return __version__


def ha_version_supported(version: str | None = None) -> bool:
    """Return whether the running Home Assistant meets the 2026.11 minimum.

    The 2026.11 adoption replaced the last cross-version compatibility
    layer, so older builds must not set the integration up: their climate
    and water-heater platforms crash with ``AttributeError`` half-way
    through (idm-heatpump-hass#632). The manifest ``homeassistant`` key
    cannot express a beta minimum (hassfest rejects prereleases, and a
    stable key would also lock out the 2026.11 beta the release targets),
    so the gate runs here at component setup.

    Only major.minor is compared, so the ``2026.11.0b0`` beta and the
    ``2026.11.0`` stable both pass while every 2026.10.x build fails.
    Unparseable or missing versions fail open: the gate exists to reject
    the known-unsupported 2026.8-2026.10 line, not to guess about unknown
    future formats.
    """
    if version is None:
        version = ha_running_version()
    try:
        major, minor = (int(part) for part in version.split("-")[0].split(".")[:2])
    except (ValueError, IndexError, AttributeError):
        return True
    return (major, minor) >= MIN_HA_MAJOR_MINOR
