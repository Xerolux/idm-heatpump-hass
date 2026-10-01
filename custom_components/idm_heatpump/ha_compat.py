"""Version-tolerant imports across the supported Home Assistant range.

The integration supports Home Assistant 2026.8 through 2026.10, and the
2026.10 line moved public surface in ways a single import line cannot
satisfy under strict mypy on both generations at once:

- the schema library: Home Assistant replaced voluptuous with probatio
  (2026.9+). At runtime ``import voluptuous`` keeps resolving through Home
  Assistant's ``sys.modules`` alias, so nothing changes for users — but the
  Home Assistant annotations now name ``probatio`` types.
- flow-result types became generic (``FlowResult[FlowContext, str]``), and
  the canonical repairs-step annotation is ``RepairsFlowResult``.
- component enums (``BinarySensorDeviceClass``,
  ``WaterHeaterEntityFeature``) moved into per-component ``const`` modules
  that the package re-exports only implicitly, which strict mypy rejects.

This module resolves the right implementation at runtime and deliberately
types every re-export as ``Any``: the runtime objects behave identically on
each supported version, and ``Any`` is the only static type both
generations' signatures accept. Import ``vol`` and the version-moved
symbols from here instead of their canonical locations.
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
        # on 2026.8 (and in the stubbed unit suite) it is the real library.
        import voluptuous as vol  # re-export
    except ImportError:  # pragma: no cover - only if the alias is ever dropped
        import probatio as vol  # noqa: F401  # re-export

    from homeassistant.components.repairs import RepairsFlowResult  # noqa: F401  # re-export

    try:  # Home Assistant 2026.10+: the enum lives in the const module
        from homeassistant.components.binary_sensor.const import (  # type: ignore[attr-defined]
            BinarySensorDeviceClass,
        )
    except ImportError:  # Home Assistant 2026.8/2026.9
        from homeassistant.components.binary_sensor import BinarySensorDeviceClass  # noqa: F401

    try:  # Home Assistant 2026.10+: the enum lives in the const module
        from homeassistant.components.water_heater.const import (  # type: ignore[attr-defined]
            WaterHeaterEntityFeature,
        )
    except ImportError:  # Home Assistant 2026.8/2026.9
        from homeassistant.components.water_heater import (  # noqa: F401
            WaterHeaterEntityFeature,
        )
