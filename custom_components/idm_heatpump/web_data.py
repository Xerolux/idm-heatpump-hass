"""Optional local web supplement support for IDM Navigator controllers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
import re
from typing import Any, Protocol

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


def _normalize_web_data(data: Any) -> IdmWebSupplement:
    simple_values = getattr(data, "simple_values", None)
    values = dict(simple_values) if isinstance(simple_values, dict) else {}
    raw_values = getattr(data, "values", None)
    sensor_values = (
        {str(name): _normalize_sensor_value(value) for name, value in raw_values.items()}
        if isinstance(raw_values, dict)
        else {str(name): _normalize_sensor_value(value) for name, value in values.items()}
    )
    return IdmWebSupplement(
        navigator_version=_read_str_attr(data, "navigator_version"),
        software_version=_read_str_attr(data, "software_version"),
        heatpump_model=_read_str_attr(data, "heatpump_model"),
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
    try:
        from idm_heatpump import IdmWebAuthenticationError as auth_error_type
    except ImportError:
        auth_error_type = None

    if auth_error_type is not None and isinstance(err, auth_error_type):
        return True
    return err.__class__.__name__ == "IdmWebAuthenticationError"


def web_pin_configured(pin: str | None) -> bool:
    """Return whether optional local web access can be attempted."""
    if not pin:
        return False
    try:
        from idm_heatpump import web_pin_configured as api_web_pin_configured
    except ImportError:
        return bool(pin.strip())
    return bool(api_web_pin_configured(pin))


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


async def async_read_web_supplement(host: str, pin: str | None) -> IdmWebSupplement | None:
    """Read one optional local web supplement snapshot.

    Navigator 10 is tried first because it uses the dedicated local WebSocket
    port. Navigator 2.0 is tried afterwards via the HTTP web UI. Callers should
    treat every exception as non-fatal to Modbus operation.
    """
    if not web_pin_configured(pin):
        return None

    clean_pin = pin.strip() if pin is not None else ""
    last_error: Exception | None = None
    for factory in (_create_nav10_client, _create_nav20_client):
        client = factory(host, clean_pin)
        if client is None:
            continue
        try:
            supplement = _normalize_web_data(await client.read_data())
            return await _read_optional_notifications(client, supplement)
        except Exception as err:
            if _is_authentication_error(err):
                raise IdmWebAuthenticationFailed("IDM Navigator web PIN was rejected") from err
            last_error = err
            _LOGGER.debug("IDM web supplement read failed for %s", host, exc_info=True)
        finally:
            try:
                await client.close()
            except Exception:
                _LOGGER.debug("Error closing IDM web supplement client", exc_info=True)

    if last_error is not None:
        raise last_error
    _LOGGER.debug("IDM web supplement is unavailable; idm-heatpump-api has no web API")
    return None


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
