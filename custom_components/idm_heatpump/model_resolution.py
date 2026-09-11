"""Decide which Navigator model — and therefore which register map — to use.

Four sources can disagree about the controller in front of us:

1. the fresh Modbus probe (``client.detect_model()``),
2. the model persisted from an earlier setup (``entry.data``),
3. the optional local web supplement,
4. an explicit model override the user picked in the options.

The rules that settle it decide which registers get polled, so they matter for
every entity. They used to live inline in ``async_setup_entry`` as roughly 250
lines of interleaved branching and I/O, testable only through the whole setup
path with heavy mocks. Here they are pure functions over dataclasses: the same
decisions, reachable one case at a time.

Nothing in this module performs I/O or touches Home Assistant state. A caller
reads the sources, asks :func:`resolve_model` what to do, and applies the
result — including the ``entry.data`` writes it asks for and the log lines it
wants emitted.
"""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — unofficial community integration for IDM Navigator 2.0 / 10 heat pumps
# Created by Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# SPDX-License-Identifier: MIT
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from idm_heatpump import (
    FEATURE_CASCADE,
    FEATURE_HEATING_CIRCUITS,
    FEATURE_ISC,
    FEATURE_PV,
    FEATURE_SOLAR,
    FEATURE_ZONE_MODULES,
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    MODEL_NAVIGATOR_PRO,
    IdmModelInfo,
)

from .const import (
    CONF_DETECTED_NAVIGATOR_VERSION,
    CONF_DETECTED_SOFTWARE_VERSION,
    CONF_DETECTED_WEB_VARIANT,
    CONF_MODEL_OVERRIDE,
    MODEL,
    MODEL_OVERRIDE_AUTO,
    MODEL_OVERRIDE_NAVIGATOR_10,
    MODEL_OVERRIDE_NAVIGATOR_20,
    MODEL_OVERRIDE_NAVIGATOR_PRO,
)
from .coordinator import navigator_family
from .web_data import IdmWebSupplement, _firmware_indicates_nav10, merge_model_info

#: One deferred log call: level, message, arguments. Collected rather than
#: emitted so the decision logic stays free of side effects; the caller replays
#: them through its own logger, keeping the messages where users expect them.
LogLine = tuple[int, str, tuple[Any, ...]]


@dataclass(frozen=True, slots=True)
class DetectionResult:
    """What the Modbus probe reported about the controller."""

    model_name: str
    firmware_version: str | None = None
    model_info: IdmModelInfo | None = None
    #: ``client.model_info`` after the probe. Richer than ``model_info`` when
    #: the two agree on the family, so it is preferred then.
    client_model_info: IdmModelInfo | None = None


@dataclass(frozen=True, slots=True)
class StoredDetection:
    """What an earlier setup persisted in ``entry.data``."""

    navigator_version: str | None = None
    software_version: str | None = None
    web_variant: str | None = None

    @classmethod
    def from_entry_data(cls, data: Mapping[str, Any]) -> StoredDetection:
        """Read the detection keys out of a config entry's data."""
        variant = data.get(CONF_DETECTED_WEB_VARIANT)
        return cls(
            navigator_version=_clean(data.get(CONF_DETECTED_NAVIGATOR_VERSION)),
            software_version=_clean(data.get(CONF_DETECTED_SOFTWARE_VERSION)),
            web_variant=variant if variant in ("nav10", "nav20") else None,
        )


@dataclass(frozen=True, slots=True)
class PlantShape:
    """The configured installation, used to build fallback model info."""

    circuits: tuple[str, ...] = ()
    zone_count: int = 0
    enable_cascade: bool = False


@dataclass(frozen=True, slots=True)
class WebReadPlan:
    """How to address the optional web supplement for this controller."""

    model_hint: str
    preferred_variant: str | None

    @property
    def allow_variant_fallback(self) -> bool:
        """Try the other protocol only while no variant is known to work."""
        return self.preferred_variant is None


@dataclass(frozen=True, slots=True)
class ModelResolution:
    """The decision, and everything the caller has to apply for it."""

    model_name: str
    firmware_version: str | None
    model_info: IdmModelInfo
    #: Detection keys to write back to ``entry.data``.
    data_updates: Mapping[str, Any] = field(default_factory=dict)
    #: Detection keys to drop from ``entry.data`` because they are now stale.
    data_removals: frozenset[str] = frozenset()
    log_lines: tuple[LogLine, ...] = ()


def _clean(value: Any) -> str | None:
    """Return a non-empty stripped string, or None."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def model_name_for_override(override_value: str) -> str | None:
    """Map a config-flow override value to a library model name.

    Returns ``None`` for ``auto``/unknown so callers keep using automatic
    detection.
    """
    mapping = {
        MODEL_OVERRIDE_NAVIGATOR_10: MODEL_NAVIGATOR_10,
        MODEL_OVERRIDE_NAVIGATOR_20: MODEL_NAVIGATOR_20,
        MODEL_OVERRIDE_NAVIGATOR_PRO: MODEL_NAVIGATOR_PRO,
    }
    return mapping.get(override_value)


def resolved_model_override(entry_data: Mapping[str, Any]) -> str | None:
    """Return the configured override model name, or ``None`` for automatic."""
    raw = _clean(entry_data.get(CONF_MODEL_OVERRIDE))
    if raw is None or raw == MODEL_OVERRIDE_AUTO:
        return None
    return model_name_for_override(raw)


def model_info_from_name(model_name: str, plant: PlantShape) -> IdmModelInfo:
    """Build model info from a trusted model name and the configured plant.

    When the name is generic ("Navigator 2.0 / 10"), inconclusive, or unknown,
    default to Navigator 2.0. That is the safer baseline: Navigator-10-only
    registers such as 4108 / 4001 cause "Illegal Data Address" errors on older
    controllers, whereas a Navigator 10 controller simply won't expose a few
    Navigator-2.0-specific registers.
    """
    normalized = model_name.casefold()
    has_navigator_20 = "navigator 2" in normalized
    has_navigator_10 = "navigator 10" in normalized
    has_navigator_pro = "navigator pro" in normalized

    if has_navigator_10 and not has_navigator_20:
        detected_model = MODEL_NAVIGATOR_10
    elif has_navigator_pro and not has_navigator_20 and not has_navigator_10:
        detected_model = MODEL_NAVIGATOR_PRO
    else:
        detected_model = MODEL_NAVIGATOR_20

    features: set[str] = set()
    if plant.circuits:
        features.add(FEATURE_HEATING_CIRCUITS)
    if plant.zone_count > 0:
        features.add(FEATURE_ZONE_MODULES)
    features.add(FEATURE_SOLAR)
    features.add(FEATURE_ISC)
    features.add(FEATURE_PV)
    if plant.enable_cascade:
        features.add(FEATURE_CASCADE)

    return IdmModelInfo(
        model_name=detected_model,
        active_heating_circuits=[circuit.upper() for circuit in plant.circuits],
        zone_modules=plant.zone_count,
        has_solar=True,
        has_isc=True,
        has_pv=True,
        has_cascade=plant.enable_cascade,
        features=features,
    )


@dataclass(frozen=True, slots=True)
class _StoredReconciliation:
    """The state after weighing the stored detection against the fresh probe."""

    model_name: str
    firmware_version: str | None
    #: The Modbus-side name, after any override. Everything downstream compares
    #: against this rather than against the possibly stored ``model_name``.
    modbus_model_name: str
    override_active: bool
    stored_conflict: bool
    stale_navigator_version: str | None
    log_lines: tuple[LogLine, ...]


def _reconcile_stored(
    fresh: DetectionResult,
    stored: StoredDetection,
    override_model_name: str | None,
) -> _StoredReconciliation:
    """Weigh an override and the stored detection against the fresh probe."""
    logs: list[LogLine] = []
    model_name = fresh.model_name
    firmware_version = fresh.firmware_version
    modbus_model_name = fresh.model_name
    override_active = override_model_name is not None

    if override_model_name is not None:
        logs.append(
            (
                logging.WARNING,
                (
                    "IDM Navigator model override active: using %s (automatic detection was %s); "
                    "change the override back to 'Automatic' in the integration settings if it was "
                    "set by mistake"
                ),
                (override_model_name, modbus_model_name),
            )
        )
        model_name = override_model_name
        modbus_model_name = override_model_name

    stored_conflict = False
    stale_navigator_version: str | None = None
    # An override is the user's explicit choice, so the stored value is not a
    # detection result that could go stale — skip the reconciliation entirely
    # rather than silently rewriting what the user picked.
    if not override_active and stored.navigator_version is not None:
        agrees = fresh.model_info is None or navigator_family(stored.navigator_version) == navigator_family(
            modbus_model_name
        )
        if agrees:
            model_name = stored.navigator_version
            logs.append(
                (
                    logging.INFO,
                    "Using stored IDM Navigator model %s because it matches fresh Modbus detection",
                    (model_name,),
                )
            )
        else:
            stored_conflict = True
            stale_navigator_version = stored.navigator_version
            logs.append(
                (
                    logging.INFO,
                    "Stored IDM Navigator model %s conflicts with fresh Modbus detection %s; correcting stored data",
                    (stored.navigator_version, modbus_model_name),
                )
            )

    if stored.software_version is not None and not stored_conflict:
        firmware_version = stored.software_version

    return _StoredReconciliation(
        model_name=model_name,
        firmware_version=firmware_version,
        modbus_model_name=modbus_model_name,
        override_active=override_active,
        stored_conflict=stored_conflict,
        stale_navigator_version=stale_navigator_version,
        log_lines=tuple(logs),
    )


def plan_web_read(
    fresh: DetectionResult,
    stored: StoredDetection,
    override_model_name: str | None = None,
) -> WebReadPlan:
    """Decide how to address the web supplement before reading it.

    Separate from :func:`resolve_model` only because the read itself is I/O:
    the caller needs the hint and the variant first, then hands the answer back
    to ``resolve_model``.
    """
    reconciled = _reconcile_stored(fresh, stored, override_model_name)
    return WebReadPlan(
        model_hint=reconciled.modbus_model_name,
        # A stored variant belongs to a stored model the fresh probe just
        # contradicted, so it cannot be trusted to pick the protocol.
        preferred_variant=None if reconciled.stored_conflict else stored.web_variant,
    )


def resolve_model(
    fresh: DetectionResult,
    stored: StoredDetection,
    web: IdmWebSupplement | None,
    override_model_name: str | None,
    plant: PlantShape,
) -> ModelResolution:
    """Settle on one model, firmware string and register map.

    ``web`` is whatever :func:`plan_web_read` led the caller to read, or None
    when the supplement is disabled, unreachable or rejected the PIN.
    """
    reconciled = _reconcile_stored(fresh, stored, override_model_name)
    logs: list[LogLine] = list(reconciled.log_lines)

    model_name = reconciled.model_name
    firmware_version = reconciled.firmware_version
    model_info = fresh.model_info
    # Carries the value a later write should replace; the key alone is what
    # matters, so any non-None value marks "the stored model needs correcting".
    stale_navigator_version = reconciled.stale_navigator_version
    web_correction_updates: dict[str, Any] = {}

    if web is not None:
        web_model_name = web.model_name
        web_disagrees = (
            web_model_name is not None
            and web_model_name != ""
            and not reconciled.override_active
            and fresh.model_info is not None
            and navigator_family(web_model_name) != navigator_family(reconciled.modbus_model_name)
        )
        if web_model_name and web_disagrees:
            # The web variant that connected is definitive: a nav10 client only
            # speaks to a Navigator 10. With a NAV10 firmware string on top,
            # the web evidence beats a Modbus probe that may simply have been
            # refused register 4108, as some Navigator 10 firmwares do.
            if _firmware_indicates_nav10(web.software_version):
                logs.append(
                    (
                        logging.INFO,
                        "Correcting Modbus-detected model %s to %s based on web firmware string %s",
                        (reconciled.modbus_model_name, web_model_name, web.software_version),
                    )
                )
                model_name = web_model_name
                firmware_version = web.software_version or firmware_version
                # The library's own model_info still holds the stale detection,
                # so build the corrected one from the name the web proved.
                model_info = model_info_from_name(model_name, plant)
                web_correction_updates[CONF_DETECTED_NAVIGATOR_VERSION] = model_name
                if firmware_version:
                    web_correction_updates[CONF_DETECTED_SOFTWARE_VERSION] = firmware_version
                if web.web_variant:
                    web_correction_updates[CONF_DETECTED_WEB_VARIANT] = web.web_variant
            else:
                stale_navigator_version = web_model_name
                logs.append(
                    (
                        logging.WARNING,
                        "Ignoring conflicting stored/web Navigator model %s because Modbus detected %s",
                        (web_model_name, reconciled.modbus_model_name),
                    )
                )
        elif reconciled.override_active:
            # The override owns the model; the supplement may still contribute
            # a software version.
            _, firmware_version = merge_model_info(model_name, firmware_version, web)
        else:
            model_name, firmware_version = merge_model_info(model_name, firmware_version, web)

    data_updates: dict[str, Any] = dict(web_correction_updates)
    data_removals: set[str] = set()
    # Persist the resolved model: confirmed web evidence may have corrected
    # the fresh probe as well as the stale stored detection.
    if stale_navigator_version is not None and fresh.model_info is not None:
        data_updates[CONF_DETECTED_NAVIGATOR_VERSION] = model_name
        if web is not None and web.web_variant:
            data_updates[CONF_DETECTED_WEB_VARIANT] = web.web_variant
        if firmware_version:
            data_updates[CONF_DETECTED_SOFTWARE_VERSION] = firmware_version
        if reconciled.stored_conflict and CONF_DETECTED_SOFTWARE_VERSION not in data_updates:
            data_removals.add(CONF_DETECTED_SOFTWARE_VERSION)
            logs.append(
                (
                    logging.INFO,
                    "Removed stale stored IDM software version because the stored Navigator model was corrected",
                    (),
                )
            )
        if reconciled.stored_conflict and CONF_DETECTED_WEB_VARIANT not in data_updates:
            data_removals.add(CONF_DETECTED_WEB_VARIANT)
            logs.append(
                (
                    logging.INFO,
                    "Removed stale stored IDM web variant because the stored Navigator model was corrected",
                    (),
                )
            )
        logs.append(
            (logging.INFO, "Persisting corrected IDM detection data: %s", (sorted(data_updates),)),
        )

    resolved_info = _resolve_model_info(fresh, model_info, model_name, reconciled.override_active, plant)

    return ModelResolution(
        model_name=model_name,
        firmware_version=firmware_version,
        model_info=resolved_info,
        data_updates=data_updates,
        data_removals=frozenset(data_removals),
        log_lines=tuple(logs),
    )


def _resolve_model_info(
    fresh: DetectionResult,
    model_info: IdmModelInfo | None,
    model_name: str,
    override_active: bool,
    plant: PlantShape,
) -> IdmModelInfo:
    """Pick the richest model info consistent with the decided model name."""
    client_info = fresh.client_model_info
    if not override_active and isinstance(client_info, IdmModelInfo):
        if isinstance(model_info, IdmModelInfo) and navigator_family(client_info.model_name) == navigator_family(
            model_info.model_name
        ):
            # Same family: the library's info carries features and capabilities
            # the locally built one does not.
            model_info = client_info
        elif model_info is None and navigator_family(client_info.model_name) == navigator_family(model_name):
            model_info = client_info
    if override_active or model_info is None:
        # An override is authoritative for the register map, so rebuild from
        # the name the user chose rather than from whatever was probed.
        model_info = model_info_from_name(model_name, plant)
    return model_info


def plant_shape(circuits: Sequence[str], zone_count: int, enable_cascade: bool) -> PlantShape:
    """Build a :class:`PlantShape` from the config entry's options."""
    return PlantShape(
        circuits=tuple(circuits),
        zone_count=zone_count,
        enable_cascade=enable_cascade,
    )


__all__ = [
    "MODEL",
    "DetectionResult",
    "LogLine",
    "ModelResolution",
    "PlantShape",
    "StoredDetection",
    "WebReadPlan",
    "model_info_from_name",
    "model_name_for_override",
    "plan_web_read",
    "plant_shape",
    "resolve_model",
    "resolved_model_override",
]
