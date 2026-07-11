"""Optional local web supplement support for IDM Navigator controllers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
import re
from typing import Any, Callable, Protocol

from .const import MODEL

_LOGGER = logging.getLogger(__name__)


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


def _create_nav10_client(host: str, pin: str) -> _IdmWebClient | None:
    try:
        from idm_heatpump import create_optional_navigator10_web_client
    except ImportError:
        return None
    client = create_optional_navigator10_web_client(host, pin)
    return client


def _create_nav20_client(host: str, pin: str) -> _IdmWebClient | None:
    try:
        from idm_heatpump import create_optional_navigator20_web_client
    except ImportError:
        return None
    client = create_optional_navigator20_web_client(host, pin)
    return client


# Type alias for a web client factory function.
_WebClientFactory = Callable[[str, str], "_IdmWebClient | None"]

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


async def async_read_web_supplement(
    host: str,
    pin: str | None,
    model_hint: str | None = None,
    preferred_variant: str | None = None,
    client_pool: IdmWebClientPool | None = None,
    *,
    allow_variant_fallback: bool = True,
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
            try:
                supplement = _normalize_web_data(await cached_client.read_data(), cached_variant)
                return await _read_optional_notifications(cached_client, supplement)
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
        client = factory(host, clean_pin)
        if client is None:
            continue
        try:
            supplement = _normalize_web_data(await client.read_data(), variant_name)
            _LOGGER.debug(
                "IDM web supplement succeeded with %s variant at %s",
                variant_name,
                host,
            )
            result = await _read_optional_notifications(client, supplement)
            # Cache the successful client for reuse on subsequent polls.
            if client_pool is not None:
                client_pool.set(client, variant_name)
            else:
                # No pool: keep the historical close-after-read behaviour.
                await _safe_close(client)
            return result
        except Exception as err:
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
