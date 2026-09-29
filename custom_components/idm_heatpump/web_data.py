"""Optional local web supplement support for IDM Navigator controllers."""

from __future__ import annotations

import asyncio
import inspect
import ipaddress
import logging
import re
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Protocol

from homeassistant.helpers.aiohttp_client import async_create_clientsession, async_get_clientsession

from .const import MODEL, WEB_READ_TIMEOUT
from .web_demand_reason import async_read_home_detail

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class _ClosableSession(Protocol):
    async def close(self) -> None:
        """Close the HTTP session."""


#: Releases one aiohttp session. ``None`` where the session is not ours to release.
type _SessionRelease = Callable[[], Coroutine[Any, Any, None]]


class _IdmWebClient(Protocol):
    async def read_data(self) -> Any:
        """Read one web data snapshot."""

    async def close(self) -> None:
        """Close the web client."""


class IdmWebAuthenticationFailed(Exception):
    """Raised when the local Navigator web interface rejects the configured PIN."""


@dataclass(frozen=True)
class IdmWebSensorValue:
    """One normalized web supplement value for Home Assistant sensors."""

    value: str
    native_value: str | float
    unit: str | None = None


@dataclass(frozen=True)
class IdmWebSupplement:
    """Normalized subset of optional local web data."""

    navigator_version: str | None = None
    software_version: str | None = None
    heatpump_model: str | None = None
    web_variant: str | None = None
    myidm_id: str | None = None
    values: dict[str, str] = field(default_factory=dict)
    sensor_values: dict[str, IdmWebSensorValue] = field(default_factory=dict)
    demand_reason: Any | None = None
    # Navigator 10 status/overview snapshot (jsonVersion, userlevel,
    # controller clock); None on other variants or when the frame failed.
    status: Any | None = None
    # Navigator 10 system.freshwater/overview snapshot (circulation state,
    # status info, DHW system mode); None on other variants or on failure.
    freshwater: Any | None = None
    # Navigator 10 home/overview snapshot (operating-mode state with the
    # controller's own selectable values); None on other variants or failure.
    home_overview: Any | None = None
    # Navigator 10 hot-water setpoint parameter (the device's own declared
    # range with the current value); None on other variants or failure.
    dhw_setpoint: Any | None = None
    # Heating circuits of a Navigator 10 (system.heatingcircuit/detail per
    # configured circuit); empty on other variants or failure.
    heating_circuits: tuple[Any, ...] = ()
    # Navigator 10 system.heatpump.performance snapshot (live power figures:
    # consumption, environment/source side, heating rod, modes); None on
    # other variants or when the frame failed.
    performance: Any | None = None
    # Navigator 10 weather/detail snapshot (the controller's own forecast via
    # the myiDM service: today plus up to six forecast days); None on other
    # variants or when the frame failed.
    weather: Any | None = None
    # Navigator 10 ion/overview snapshot (iON cloud energy-optimization
    # status); None on other variants or when the frame failed.
    ion: Any | None = None
    # Navigator 10 energyflow/overview snapshot (grid/PV power of the
    # energy-flow widget); None on other variants or when the frame failed.
    energyflow: Any | None = None

    @property
    def model_name(self) -> str | None:
        """Return the best Home Assistant device model from the web snapshot."""
        if self.navigator_version:
            return self.navigator_version
        return self.heatpump_model


def _read_str_attr(source: Any, attr: str) -> str | None:
    value = getattr(source, attr, None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _local_part(value: Any) -> str | None:
    """Return the compact ID part before @ for myIDM account values."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if "@" in text:
        text = text.split("@", 1)[0].strip()
    return text or None


def _read_myidm_id(data: Any, values: dict[Any, Any]) -> str | None:
    """Read the myIDM ID from common API fields and normalize mail-style IDs."""
    for attr in ("myidm_id", "myIDMId", "myidmId", "myidm_email", "myidmEmail"):
        value = _local_part(getattr(data, attr, None))
        if value is not None:
            return value

    for key, raw_value in values.items():
        key_text = str(key).casefold()
        value = _local_part(raw_value)
        if value is None:
            continue
        if key_text in {"myidm_id", "myidmid"} or "myidm" in key_text:
            return value
        if key_text in {"email", "user_email", "username"} and value.casefold().startswith("m"):
            return value
    return None


_UNIT_SUFFIX_RE = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)\s*([A-Za-z°/%]+(?:/[A-Za-z]+)?)?\s*$")


def _normalize_sensor_value(value: Any) -> IdmWebSensorValue:
    raw_value = getattr(value, "value", value)
    text_value = str(raw_value).strip()
    numeric_value = getattr(value, "numeric_value", None)
    unit = getattr(value, "unit", None)
    if isinstance(numeric_value, (int, float)):
        return IdmWebSensorValue(value=text_value, native_value=float(numeric_value), unit=unit)

    match = _UNIT_SUFFIX_RE.match(text_value)
    if match is not None:
        try:
            parsed = float(match.group(1).replace(",", "."))
        except ValueError:
            parsed = None
        if parsed is not None:
            return IdmWebSensorValue(value=text_value, native_value=parsed, unit=unit or match.group(2))

    return IdmWebSensorValue(value=text_value, native_value=text_value, unit=unit)


def _normalize_web_data(data: Any, web_variant: str | None = None) -> IdmWebSupplement:
    simple_values = getattr(data, "simple_values", None)
    values = dict(simple_values) if isinstance(simple_values, dict) else {}
    raw_values = getattr(data, "values", None)
    sensor_values = (
        {str(name): _normalize_sensor_value(value) for name, value in raw_values.items()}
        if isinstance(raw_values, dict)
        else {str(name): _normalize_sensor_value(value) for name, value in values.items()}
    )
    metadata_values = {
        "navigator_version": _read_str_attr(data, "navigator_version"),
        "software_version": _read_str_attr(data, "software_version"),
        "heatpump_model": _read_str_attr(data, "heatpump_model"),
    }
    myidm_id = _read_myidm_id(data, values)
    if myidm_id is not None:
        metadata_values["myidm_id"] = myidm_id
    for name, value in metadata_values.items():
        if value is None:
            continue
        values[name] = value
        sensor_values[name] = IdmWebSensorValue(value=value, native_value=value)

    return IdmWebSupplement(
        navigator_version=_read_str_attr(data, "navigator_version"),
        software_version=_read_str_attr(data, "software_version"),
        heatpump_model=_read_str_attr(data, "heatpump_model"),
        web_variant=web_variant,
        myidm_id=myidm_id,
        values={str(key): str(value) for key, value in values.items()},
        sensor_values=sensor_values,
    )


def _add_web_notifications(
    supplement: IdmWebSupplement,
    notifications: Any,
) -> IdmWebSupplement:
    """Return a supplement enriched with Navigator 10 infosystem notifications."""
    count = getattr(notifications, "count", None)
    summary = getattr(notifications, "summary", None)
    if not isinstance(count, int) or not isinstance(summary, str):
        return supplement

    values = dict(supplement.values)
    sensor_values = dict(supplement.sensor_values)
    values["infosystem_notification_count"] = str(count)
    values["infosystem_notifications"] = summary
    sensor_values["infosystem_notification_count"] = IdmWebSensorValue(
        value=str(count),
        native_value=float(count),
    )
    sensor_values["infosystem_notifications"] = IdmWebSensorValue(
        value=summary,
        native_value=summary,
    )
    return IdmWebSupplement(
        navigator_version=supplement.navigator_version,
        software_version=supplement.software_version,
        heatpump_model=supplement.heatpump_model,
        web_variant=supplement.web_variant,
        myidm_id=supplement.myidm_id,
        values=values,
        sensor_values=sensor_values,
    )


async def _read_optional_notifications(
    client: _IdmWebClient,
    supplement: IdmWebSupplement,
) -> IdmWebSupplement:
    read_notifications = getattr(client, "read_notifications", None)
    if read_notifications is None:
        return supplement
    try:
        notifications = await read_notifications()
    except Exception:
        _LOGGER.debug("IDM web notifications read failed", exc_info=True)
        return supplement
    return _add_web_notifications(supplement, notifications)


async def _read_optional_demand_reason(
    client: _IdmWebClient,
    supplement: IdmWebSupplement,
) -> IdmWebSupplement:
    """Augment a Navigator 10 snapshot with the home-screen demand reason.

    Uses the public API method (``read_home_detail``, idm-heatpump-api 2.3.0+)
    under the same hard time limit as the rest of the snapshot. Strictly
    optional: any failure keeps the supplement unchanged, and the Navigator
    2.0 PHP client has no home controller at all.
    """
    if supplement.web_variant != "nav10":
        return supplement
    try:
        async with asyncio.timeout(WEB_READ_TIMEOUT):
            detail = await async_read_home_detail(client)
    except Exception:
        _LOGGER.debug("IDM web home/detail read failed", exc_info=True)
        return supplement
    if detail is None:
        return supplement
    return replace(supplement, demand_reason=detail)


def _with_sensor_values(
    supplement: IdmWebSupplement,
    extra: dict[str, IdmWebSensorValue],
    **field_updates: Any,
) -> IdmWebSupplement:
    """Return a supplement with merged sensor values and updated fields."""
    if not extra and not field_updates:
        return supplement
    sensor_values = dict(supplement.sensor_values)
    sensor_values.update(extra)
    values = dict(supplement.values)
    values.update({name: item.value for name, item in extra.items()})
    return replace(supplement, values=values, sensor_values=sensor_values, **field_updates)


def _statistic_sensor_value(value: Any) -> IdmWebSensorValue:
    """Convert one API statistic value into a kWh sensor value."""
    text = str(getattr(value, "value", value))
    try:
        numeric = float(text)
    except ValueError:
        numeric = None
    return IdmWebSensorValue(value=text, native_value=numeric if numeric is not None else text, unit="kWh")


async def _read_optional_statistics(
    client: _IdmWebClient,
    supplement: IdmWebSupplement,
) -> IdmWebSupplement:
    """Augment a Navigator 10 snapshot with the device-side heat quantities.

    Reads ``statistic/detail`` for the heat-quantity block (statisticType 6,
    verified against a live controller; the selector constants live in
    idm-heatpump-api) with both the lifetime total and the today aggregation.
    The controller's own heat totals are an independent cross-check for the
    self-integrated energy statistics. Strictly optional: any failure keeps
    the supplement unchanged.
    """
    if supplement.web_variant != "nav10":
        return supplement
    from idm_heatpump import (
        NAVIGATOR10_STATISTIC_HEAT_QUANTITIES,
        NAVIGATOR10_STATISTIC_PERIOD_TODAY,
        NAVIGATOR10_STATISTIC_PERIOD_TOTAL,
    )

    read_statistics = getattr(client, "read_statistics", None)
    if not callable(read_statistics):
        return supplement
    extra: dict[str, IdmWebSensorValue] = {}
    name_map = {
        "heating": "heat_quantity_heating",
        "priority": "heat_quantity_hotwater",
    }
    try:
        async with asyncio.timeout(WEB_READ_TIMEOUT):
            totals = await read_statistics(
                NAVIGATOR10_STATISTIC_HEAT_QUANTITIES,
                NAVIGATOR10_STATISTIC_PERIOD_TOTAL,
                "hq",
            )
            todays = await read_statistics(
                NAVIGATOR10_STATISTIC_HEAT_QUANTITIES,
                NAVIGATOR10_STATISTIC_PERIOD_TODAY,
                "hq",
            )
    except Exception:
        _LOGGER.debug("IDM web statistic/detail read failed", exc_info=True)
        return supplement
    for parsed in (totals, todays):
        for name, value in (getattr(parsed, "values", None) or {}).items():
            for raw_key, target in name_map.items():
                if name.endswith(f"_{raw_key}"):
                    suffix = "today" if "_today_" in name else "total"
                    extra[f"{target}_{suffix}"] = _statistic_sensor_value(value)
    return _with_sensor_values(supplement, extra)


async def _read_optional_freshwater(
    client: _IdmWebClient,
    supplement: IdmWebSupplement,
) -> IdmWebSupplement:
    """Augment a Navigator 10 snapshot with the domestic-hot-water detail.

    ``system.freshwater/overview`` carries the circulation-pump state and the
    numeric status info — two values the Modbus map does not expose. The tank
    temperatures are deliberately not republished: the Modbus registers and
    the web setting pages already provide them. Strictly optional.
    """
    if supplement.web_variant != "nav10":
        return supplement
    read_freshwater = getattr(client, "read_freshwater_overview", None)
    if not callable(read_freshwater):
        return supplement
    try:
        async with asyncio.timeout(WEB_READ_TIMEOUT):
            freshwater = await read_freshwater()
    except Exception:
        _LOGGER.debug("IDM web system.freshwater/overview read failed", exc_info=True)
        return supplement
    extra: dict[str, IdmWebSensorValue] = {}
    circulation = getattr(freshwater, "circulation_active", None)
    if circulation is not None:
        extra["dhw_circulation_active"] = IdmWebSensorValue(
            value="on" if circulation else "off",
            native_value=1.0 if circulation else 0.0,
        )
    status = getattr(freshwater, "status", None)
    if status is not None:
        extra["dhw_status_info"] = IdmWebSensorValue(value=str(status), native_value=float(status))
    return _with_sensor_values(supplement, extra, freshwater=freshwater)


async def _read_optional_home_overview(
    client: _IdmWebClient,
    supplement: IdmWebSupplement,
) -> IdmWebSupplement:
    """Augment a Navigator 10 snapshot with the home/overview mode tile.

    The frame carries the operating-mode widget — the current value and the
    controller's own selectable values, numbered like the Modbus
    ``system_mode`` register. It is the state source for the web-only
    operating-mode control. Strictly optional.
    """
    if supplement.web_variant != "nav10":
        return supplement
    read_home_overview = getattr(client, "read_home_overview", None)
    if not callable(read_home_overview):
        return supplement
    try:
        async with asyncio.timeout(WEB_READ_TIMEOUT):
            overview = await read_home_overview()
    except Exception:
        _LOGGER.debug("IDM web home/overview read failed", exc_info=True)
        return supplement
    return replace(supplement, home_overview=overview)


async def _read_optional_status(
    client: _IdmWebClient,
    supplement: IdmWebSupplement,
) -> IdmWebSupplement:
    """Augment a Navigator 10 snapshot with the status/overview frame.

    The frame carries connection-level facts (jsonVersion, active userlevel,
    controller clock, frost-protection flag). The dedicated controller-clock
    entity publishes them; nothing enters ``sensor_values`` here. Strictly
    optional.
    """
    if supplement.web_variant != "nav10":
        return supplement
    read_status = getattr(client, "read_status_overview", None)
    if not callable(read_status):
        return supplement
    try:
        async with asyncio.timeout(WEB_READ_TIMEOUT):
            status = await read_status()
    except Exception:
        _LOGGER.debug("IDM web status/overview read failed", exc_info=True)
        return supplement
    return replace(supplement, status=status)


async def _read_optional_dhw_setpoint(
    client: _IdmWebClient,
    supplement: IdmWebSupplement,
) -> IdmWebSupplement:
    """Augment a Navigator 10 snapshot with the hot-water setpoint.

    Reads the settings-tree parameter (13256 / FW030 on the confirmed
    firmware) with the device's own declared range and the current value —
    the state and bounds of the web-only setpoint control. Strictly
    optional: any failure keeps the supplement unchanged.
    """
    if supplement.web_variant != "nav10":
        return supplement
    read_setting_parameter = getattr(client, "read_setting_parameter", None)
    if not callable(read_setting_parameter):
        return supplement
    try:
        from idm_heatpump import NAVIGATOR10_DHW_SETPOINT_SETTING_ID

        async with asyncio.timeout(WEB_READ_TIMEOUT):
            parameter = await read_setting_parameter(NAVIGATOR10_DHW_SETPOINT_SETTING_ID)
    except Exception:
        _LOGGER.debug("IDM web hot-water setpoint read failed", exc_info=True)
        return supplement
    if getattr(parameter, "param", None) != "FW030":
        return supplement
    return replace(supplement, dhw_setpoint=parameter)


async def _read_optional_nav20_statistics(
    client: _IdmWebClient,
    supplement: IdmWebSupplement,
) -> IdmWebSupplement:
    """Augment a Navigator 2.0 snapshot with the statistics pages.

    The three statistics.php types (runtime, generated heat, electrical
    energy) arrive as JSON with the page's own unit scale; the API
    normalizes them to hours/kWh. Strictly optional: any failure keeps the
    supplement unchanged. Navigator 2.0 only - the Navigator 10 statistics
    arrive through the WebSocket in :func:`_read_optional_statistics`.
    """
    if supplement.web_variant != "nav20":
        return supplement
    read_statistics = getattr(client, "read_statistics", None)
    if not callable(read_statistics):
        return supplement
    try:
        async with asyncio.timeout(WEB_READ_TIMEOUT):
            statistics = await read_statistics()
    except Exception:
        _LOGGER.debug("IDM web statistics pages read failed", exc_info=True)
        return supplement
    extra = {
        name: _normalize_sensor_value(value) for name, value in (getattr(statistics, "values", None) or {}).items()
    }
    return _with_sensor_values(supplement, extra)


async def _read_optional_heatingcircuits(
    client: _IdmWebClient,
    supplement: IdmWebSupplement,
) -> IdmWebSupplement:
    """Augment a Navigator 10 snapshot with the heating-circuit states.

    One ``system.heatingcircuit/detail`` frame per circuit carries the
    operating mode (with the device's own chooselist), the normal and eco
    room setpoints with their declared ranges, the room temperature and the
    pump state — the state and bounds of the web-only heating controls. The
    first answer also lists every configured circuit, so the reader walks
    the plant's own circuit list. Strictly optional.
    """
    if supplement.web_variant != "nav10":
        return supplement
    read_heatingcircuit = getattr(client, "read_heatingcircuit", None)
    if not callable(read_heatingcircuit):
        return supplement
    circuits: list[Any] = []
    try:
        async with asyncio.timeout(WEB_READ_TIMEOUT):
            first = await read_heatingcircuit("A")
            circuits.append(first)
            wanted = [ref.hc_id for ref in first.available_circuits if ref.hc_id != first.hc_id]
            for hc_id in wanted:
                circuits.append(await read_heatingcircuit(hc_id))
    except Exception:
        _LOGGER.debug("IDM web heating-circuit read failed", exc_info=True)
        return supplement
    return replace(supplement, heating_circuits=tuple(circuits))


async def _read_optional_system_frames(
    client: _IdmWebClient,
    supplement: IdmWebSupplement,
) -> IdmWebSupplement:
    """Augment a Navigator 10 snapshot with the system-level read frames.

    Four controllers the shipped frontend uses for its performance page,
    weather tile, iON status and energy-flow widget: performance (live power
    figures), weather (the controller's own forecast), ion (cloud
    optimization status) and energyflow (grid/PV power). Each read is
    individually optional and failure-tolerant — a firmware without one
    controller keeps the rest of the snapshot intact.
    """
    if supplement.web_variant != "nav10":
        return supplement
    for attr, reader_name in (
        ("performance", "read_performance"),
        ("weather", "read_weather"),
        ("ion", "read_ion"),
        ("energyflow", "read_energyflow"),
    ):
        reader = getattr(client, reader_name, None)
        if not callable(reader) or getattr(supplement, attr, None) is not None:
            continue
        try:
            async with asyncio.timeout(WEB_READ_TIMEOUT):
                frame = await reader()
        except Exception:
            _LOGGER.debug("IDM web %s read failed", reader_name, exc_info=True)
            continue
        supplement = replace(supplement, **{attr: frame})
    return supplement


async def _augment_web_supplement(
    client: _IdmWebClient,
    supplement: IdmWebSupplement,
) -> IdmWebSupplement:
    """Run every optional Navigator 10 enrichment in one place.

    Each reader is individually optional and failure-tolerant, so a firmware
    without one controller keeps the rest of the snapshot intact.
    """
    supplement = await _read_optional_notifications(client, supplement)
    supplement = await _read_optional_demand_reason(client, supplement)
    supplement = await _read_optional_statistics(client, supplement)
    supplement = await _read_optional_nav20_statistics(client, supplement)
    supplement = await _read_optional_freshwater(client, supplement)
    supplement = await _read_optional_status(client, supplement)
    supplement = await _read_optional_home_overview(client, supplement)
    supplement = await _read_optional_dhw_setpoint(client, supplement)
    supplement = await _read_optional_heatingcircuits(client, supplement)
    supplement = await _read_optional_system_frames(client, supplement)
    return supplement


def _is_authentication_error(err: Exception) -> bool:
    """Return whether an API exception indicates an invalid local web PIN."""
    auth_error_type: type[Exception] | None
    try:
        from idm_heatpump import IdmWebAuthenticationError
    except ImportError:
        auth_error_type = None
    else:
        auth_error_type = IdmWebAuthenticationError

    if auth_error_type is not None and isinstance(err, auth_error_type):
        return True
    return err.__class__.__name__ == "IdmWebAuthenticationError"


#: Web value name -> Modbus register name, for values the register map and
#: the web interface both deliver under different names (verified against the
#: Navigator 10 register map). The web-only mode bridges these into the
#: coordinator snapshot so register-keyed consumers (calculated sensors, the
#: KNX bridge) keep working without a Modbus connection.
WEB_TO_REGISTER_ALIASES: dict[str, str] = {
    "flow_temperature": "hp_flow_temp",
    "return_temperature": "hp_return_temp",
    "outside_air_temperature": "outdoor_temp",
    "water_temp_top": "dhw_temp_top",
    "water_temp_bottom": "dhw_temp_bottom",
    "compressor_1": "compressor_status_1",
}


def web_to_register_value(name: str) -> str | None:
    """Return the register name a web value can bridge to, if any."""
    direct = WEB_TO_REGISTER_ALIASES.get(name)
    if direct is not None:
        return direct
    if name.startswith("flow_temp_HK_") and len(name) == len("flow_temp_HK_X"):
        return f"hc_{name[-1].lower()}_flow_temp"
    if name.startswith("room_temperature_HK_") and len(name) == len("room_temperature_HK_X"):
        return f"hc_{name[-1].lower()}_room_temp"
    return None


def web_pin_configured(pin: str | None) -> bool:
    """Return whether optional local web access can be attempted."""
    if not pin:
        return False
    clean_pin = pin.strip()
    # Navigator controllers use an empty local-network code or 0 to disable
    # their local web interface. Treat both as "not configured" so setup does
    # not report a misleading rejected-PIN error for a disabled endpoint.
    if not clean_pin or clean_pin == "0":
        return False
    try:
        from idm_heatpump import web_pin_configured as api_web_pin_configured
    except ImportError:
        return True
    return bool(api_web_pin_configured(clean_pin))


def _is_ip_literal(host: str) -> bool:
    """Return whether *host* is an IPv4 or IPv6 address literal."""
    candidate = host.strip()
    if not candidate:
        return False
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif ":" in candidate and candidate.count(":") == 1:
        candidate = candidate.rsplit(":", 1)[0]
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return False
    return True


def _session_factory_supports_session(factory: Callable[..., Any]) -> bool:
    """Return whether an API web-client factory accepts a session argument."""
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return False
    return any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD or name == "session"
        for name, parameter in signature.parameters.items()
    )


def _create_ip_cookie_session(host: str) -> _ClosableSession | None:
    """Create an aiohttp session that accepts Navigator cookies from IP hosts.

    Only used where no Home Assistant instance is available (direct library
    use and unit tests). Everything running inside Home Assistant goes through
    :func:`_web_session`, which uses Home Assistant's own session helpers.
    """
    if not _is_ip_literal(host):
        return None
    try:
        import aiohttp
    except ImportError:
        return None
    return aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))


def _unsafe_cookie_jar() -> Any | None:
    """Return a cookie jar that keeps cookies a bare IP address sets."""
    try:
        import aiohttp
    except ImportError:  # pragma: no cover - aiohttp ships with Home Assistant
        return None
    return aiohttp.CookieJar(unsafe=True)


def _detach_home_assistant_session(session: Any) -> _SessionRelease:
    """Return the release for a session Home Assistant created for us.

    Never ``close()``. Home Assistant wraps ``close()`` on every session its
    helpers hand out and logs the custom integration that calls it, because the
    connector underneath belongs to Home Assistant and is shared with everyone
    else. ``detach()`` is what Home Assistant's own shutdown handler calls, so
    it is what releases ours.
    """

    async def _release() -> None:
        session.detach()

    return _release


def _web_session(hass: HomeAssistant | None, host: str) -> tuple[Any, _SessionRelease | None]:
    """Return the aiohttp session for a web client and how to release it.

    Home Assistant owns the session (quality scale rule ``inject-websession``):
    a hostname uses the shared client session, which is never ours to release,
    while an IP address needs its own session because the Navigator sets cookies
    for a bare IP, which the shared (safe) cookie jar drops.

    That per-IP session is still created through Home Assistant, but with
    ``auto_cleanup=False``. The coordinator rebuilds the web client after every
    failed poll, and Home Assistant's automatic cleanup would pin each rebuilt
    session in an ``EVENT_HOMEASSISTANT_CLOSE`` listener until it stops, because
    a poll runs outside the config-entry setup context that would otherwise
    scope the cleanup to an unload. Releasing each session with its own client
    is both prompt and complete: the pool closes its client on invalidation and
    on ``async_shutdown``.
    """
    if hass is None:
        session = _create_ip_cookie_session(host)
        return session, (session.close if session is not None else None)
    cookie_jar = _unsafe_cookie_jar() if _is_ip_literal(host) else None
    if cookie_jar is None:
        return async_get_clientsession(hass), None
    session = async_create_clientsession(hass, cookie_jar=cookie_jar, auto_cleanup=False)
    return session, _detach_home_assistant_session(session)


class _SessionReleasingWebClient:
    """Release an integration-owned aiohttp session with its web client."""

    def __init__(self, client: _IdmWebClient, release: _SessionRelease | None) -> None:
        self._client = client
        self._release = release

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    async def read_data(self) -> Any:
        return await self._client.read_data()

    async def close(self) -> None:
        close_error: Exception | None = None
        try:
            await self._client.close()
        except Exception as err:  # noqa: BLE001
            close_error = err
        if self._release is not None:
            await self._release()
        if close_error is not None:
            raise close_error


def _release_session_later(release: _SessionRelease) -> None:
    """Schedule a session release from synchronous client-factory error paths."""
    asyncio.create_task(release())


def _create_web_client_with_optional_ip_session(
    factory: Callable[..., _IdmWebClient | None],
    host: str,
    pin: str,
    hass: HomeAssistant | None = None,
) -> _IdmWebClient | None:
    """Create a web client with the Home Assistant session the API supports."""
    session, release = _web_session(hass, host) if _session_factory_supports_session(factory) else (None, None)
    try:
        client = factory(host, pin, session=session) if session is not None else factory(host, pin)
    except Exception:
        if release is not None:
            # Client construction failed before ownership was transferred.
            _release_session_later(release)
        raise
    if client is None:
        if release is not None:
            _release_session_later(release)
        return None
    if release is None:
        return client
    return _SessionReleasingWebClient(client, release)


def _create_nav10_client(host: str, pin: str, hass: HomeAssistant | None = None) -> _IdmWebClient | None:
    try:
        from idm_heatpump import create_optional_navigator10_web_client
    except ImportError:
        return None
    return _create_web_client_with_optional_ip_session(create_optional_navigator10_web_client, host, pin, hass)


def _create_nav20_client(host: str, pin: str, hass: HomeAssistant | None = None) -> _IdmWebClient | None:
    try:
        from idm_heatpump import create_optional_navigator20_web_client
    except ImportError:
        return None
    return _create_web_client_with_optional_ip_session(create_optional_navigator20_web_client, host, pin, hass)


# Type alias for a web client factory function.
_WebClientFactory = Callable[..., "_IdmWebClient | None"]

_NAV10_VARIANTS = {"nav10", "navigator_10", "navigator_pro"}
_NAV20_VARIANTS = {"nav20", "navigator_20"}


def _is_wrong_variant_error(err: Exception) -> bool:
    """Return whether an API exception likely means we picked the wrong variant.

    Navigator 10 speaks WebSocket on port 61220; Navigator 2.0 speaks plain
    HTTP with a CSRF token. Connecting the wrong client to a controller
    typically yields response-format errors (e.g. missing CSRF token, unknown
    authorization frame) or transport errors (wrong port, connection refused,
    timeout). Authentication errors are handled separately.
    """
    wrong_variant_types: tuple[type[Exception], ...]
    try:
        from idm_heatpump import IdmWebResponseError
    except ImportError:
        wrong_variant_types = ()
    else:
        wrong_variant_types = (IdmWebResponseError,)

    if wrong_variant_types and isinstance(err, wrong_variant_types):
        return True
    if isinstance(err, (OSError, TimeoutError)):
        return True
    return err.__class__.__name__ in {
        "IdmWebResponseError",
        "ClientError",
        "ClientConnectorError",
        "ServerDisconnectedError",
        "asyncio.exceptions.TimeoutError",
    }


def _nav10_authenticated(client: _IdmWebClient) -> bool:
    """Use API diagnostics to recognize a completed WebSocket authorization.

    The API records its first success when authorized:true arrives, before
    reading settings. This remains available after a failed read/reconnect.
    """
    diagnostics = getattr(client, "diagnostics", None)
    if not callable(diagnostics):
        return False
    snapshot = diagnostics()
    return (
        getattr(snapshot, "navigator_type", None) == "nav10"
        and getattr(snapshot, "last_success_monotonic", None) is not None
    )


def _preferred_web_variant(model_hint: str | None) -> str | None:
    """Return 'nav10' or 'nav20' when the hint identifies a definite Navigator family.

    Navigator 10 uses a local WebSocket login (port 61220, auth_code query
    parameter). Navigator 2.0 uses an HTTP POST login with a CSRF token.
    Trying the wrong variant wastes up to the full connect timeout on every
    poll, so we use the Modbus-detected model to pick the right one first.
    """
    if not isinstance(model_hint, str) or not model_hint.strip():
        return None
    normalized = model_hint.casefold()
    if normalized == MODEL.casefold():
        return None
    has_nav20 = "navigator 2" in normalized
    has_nav10 = "navigator 10" in normalized
    if has_nav20 and has_nav10:
        return None
    if has_nav10:
        return "nav10"
    if has_nav20:
        return "nav20"
    if "navigator pro" in normalized:
        return "nav10"
    return None


def _ordered_web_factories(
    model_hint: str | None,
    preferred_variant: str | None = None,
    *,
    allow_variant_fallback: bool = True,
) -> tuple[tuple[str, _WebClientFactory], ...]:
    """Return web client factories ordered so the most likely variant is first.

    Priority:
      1. ``preferred_variant`` — cached from a previous successful read.
      2. ``model_hint`` — Modbus-detected model name.
      3. Default: Navigator 10 WebSocket first (current generation).

    Each entry is a (variant_name, factory) tuple so callers can log which
    Navigator web client is being attempted.
    """
    nav10: tuple[str, _WebClientFactory] = ("nav10", _create_nav10_client)
    nav20: tuple[str, _WebClientFactory] = ("nav20", _create_nav20_client)

    variant = preferred_variant or _preferred_web_variant(model_hint)
    ordered = (nav20, nav10) if variant in _NAV20_VARIANTS else (nav10, nav20)
    if allow_variant_fallback:
        return ordered
    return ordered[:1]


async def _read_data_bounded(client: _IdmWebClient, timeout: float) -> Any:
    """Read one snapshot under a hard time limit.

    The web client brings its own connect timeout, but nothing bounded the read
    itself, so a Navigator that accepted the connection and then went quiet
    could stall the poll loop — or, at setup, entity creation — indefinitely.
    A timeout is reported as a transport failure, which is what it is.
    """
    async with asyncio.timeout(timeout):
        return await client.read_data()


async def async_read_web_supplement(
    host: str,
    pin: str | None,
    model_hint: str | None = None,
    preferred_variant: str | None = None,
    client_pool: IdmWebClientPool | None = None,
    *,
    allow_variant_fallback: bool = True,
    hass: HomeAssistant | None = None,
    read_timeout: float = WEB_READ_TIMEOUT,
) -> IdmWebSupplement | None:
    """Read one optional local web supplement snapshot.

    Navigator 10 and Navigator 2.0 use fundamentally different login
    mechanisms (WebSocket auth_code vs. HTTP CSRF token). The
    ``model_hint`` (Modbus-detected model) and ``preferred_variant``
    (cached from a previous successful read) determine which client is
    tried first to avoid wasting the connect timeout on the wrong
    variant every poll cycle. Callers should treat every exception as
    non-fatal to Modbus operation.

    During setup, ``allow_variant_fallback`` keeps automatic detection enabled:
    if the first client fails, the other Navigator protocol is attempted. Once
    a variant has succeeded, runtime callers disable that fallback and reconnect
    only the known protocol on later transport, session or authentication
    failures.

    When *client_pool* is supplied, a previously successful web client is
    reused across polls instead of reconnecting (TCP+auth) every cycle.
    On any failure the cached client is closed and dropped so the next poll
    rebuilds it from scratch.
    """
    if not web_pin_configured(pin):
        return None

    clean_pin = pin.strip() if pin is not None else ""
    last_error: Exception | None = None
    last_auth_error: Exception | None = None

    # Fast path: reuse the cached client from a previous successful poll.
    if client_pool is not None:
        cached = client_pool.get()
        if cached is not None:
            cached_client, cached_variant = cached
            # A previous successful snapshot already established the protocol.
            preferred_variant = cached_variant
            allow_variant_fallback = False
            try:
                supplement = _normalize_web_data(await _read_data_bounded(cached_client, read_timeout), cached_variant)
                return await _augment_web_supplement(cached_client, supplement)
            except Exception as err:
                _LOGGER.debug(
                    "IDM web %s cached client failed at %s; rebuilding the same variant",
                    cached_variant,
                    host,
                    exc_info=True,
                )
                await client_pool.invalidate()
                if _is_authentication_error(err):
                    last_auth_error = err
                else:
                    last_error = err

    tried_variants: list[str] = []
    factories = _ordered_web_factories(
        model_hint,
        preferred_variant,
        allow_variant_fallback=allow_variant_fallback,
    )
    for variant_name, factory in factories:
        tried_variants.append(variant_name)
        client = factory(host, clean_pin, hass)
        if client is None:
            continue
        try:
            supplement = _normalize_web_data(await _read_data_bounded(client, read_timeout), variant_name)
            _LOGGER.debug(
                "IDM web supplement succeeded with %s variant at %s",
                variant_name,
                host,
            )
            result = await _augment_web_supplement(client, supplement)
            # Cache the successful client for reuse on subsequent polls.
            if client_pool is not None:
                client_pool.set(client, variant_name)
            else:
                # No pool: keep the historical close-after-read behaviour.
                await _safe_close(client)
            return result
        except Exception as err:
            if variant_name == "nav10" and _nav10_authenticated(client):
                # Authentication identified the controller, even if an optional
                # setting or a later transport operation failed. A NAV2 probe
                # would only obscure the actual error (issue #325).
                await _safe_close(client)
                if _is_authentication_error(err):
                    raise IdmWebAuthenticationFailed("IDM Navigator web PIN was rejected") from err
                raise
            if _is_authentication_error(err):
                last_auth_error = err
                _LOGGER.debug(
                    "IDM web %s variant rejected PIN at %s",
                    variant_name,
                    host,
                )
                await _safe_close(client)
                continue
            if _is_wrong_variant_error(err):
                _LOGGER.debug(
                    "IDM web %s variant appears to be the wrong variant at %s: %s",
                    variant_name,
                    host,
                    err,
                )
            else:
                _LOGGER.debug(
                    "IDM web %s variant failed at %s",
                    variant_name,
                    host,
                    exc_info=True,
                )
            last_error = err
            await _safe_close(client)

    # If any attempted variant explicitly rejected the PIN, report it. During
    # initial detection the other protocol has already been tried; for a locked
    # runtime variant the same protocol has already been rebuilt once.
    if last_auth_error is not None:
        raise IdmWebAuthenticationFailed("IDM Navigator web PIN was rejected") from last_auth_error
    if last_error is not None:
        raise last_error
    _LOGGER.debug(
        "IDM web supplement unavailable at %s (tried %s); idm-heatpump-api has no web API",
        host,
        ", ".join(tried_variants),
    )
    return None


async def _safe_close(client: _IdmWebClient) -> None:
    """Close a web client, logging but never raising close failures."""
    try:
        await client.close()
    except Exception:
        _LOGGER.debug("Error closing IDM web supplement client", exc_info=True)


class IdmWebClientPool:
    """Holds a web client across polls so TCP+auth overhead is paid once.

    The optional web supplement polls every 30s. Rebuilding the client each
    time repeats the TCP handshake, WebSocket/HTTP upgrade and PIN login.
    This pool keeps the most recently successful client and variant so the
    coordinator can reuse it. On any failure the caller calls invalidate()
    and the next poll rebuilds from scratch.
    """

    __slots__ = ("_client", "_variant")

    def __init__(self) -> None:
        self._client: _IdmWebClient | None = None
        self._variant: str | None = None

    def get(self) -> tuple[_IdmWebClient, str] | None:
        """Return the cached (client, variant) or None when empty."""
        if self._client is None:
            return None
        return self._client, self._variant  # type: ignore[return-value]

    def set(self, client: _IdmWebClient, variant: str) -> None:
        """Store a successful client for reuse."""
        self._client = client
        self._variant = variant

    async def invalidate(self) -> None:
        """Drop the cached client, closing it best-effort."""
        client = self._client
        self._client = None
        self._variant = None
        if client is not None:
            await _safe_close(client)

    async def close(self) -> None:
        """Close the pool, releasing any held client."""
        await self.invalidate()


def _firmware_indicates_nav10(software_version: str | None) -> bool:
    """Return True when the firmware string definitively indicates Navigator 10.

    Navigator 10 firmwares carry a ``NAV10_`` prefix (e.g.
    ``NAV10_20.24-880-g265e09c4a``). This signal is available from the local
    web supplement and is more reliable than a single Modbus probe that may be
    rejected by certain firmware builds.
    """
    if not isinstance(software_version, str):
        return False
    return software_version.strip().upper().startswith("NAV10")


def merge_model_info(
    modbus_model_name: str,
    modbus_firmware_version: str | None,
    web_supplement: IdmWebSupplement | None,
) -> tuple[str, str | None]:
    """Merge Modbus detection with optional web model/software data."""
    if web_supplement is None:
        return modbus_model_name, modbus_firmware_version

    model_name = web_supplement.model_name or modbus_model_name
    if model_name == MODEL:
        model_name = modbus_model_name
    firmware_version = web_supplement.software_version or modbus_firmware_version
    return model_name, firmware_version
