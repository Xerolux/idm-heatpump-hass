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
