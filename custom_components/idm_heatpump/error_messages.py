"""Classify low-level errors into actionable user-facing messages."""

from __future__ import annotations

import re
import socket

from pymodbus.exceptions import ConnectionException, ModbusIOException

# Modbus exception codes as rendered by ``modbus_transport._translate_backend_error``
# ("... (exception_code=<N>)"). Naming the code in the user-facing message and in
# the log is the difference between "the write failed" and a report a maintainer
# can act on, so the code is parsed back out of the message chain.
_EXCEPTION_CODE_PATTERN = re.compile(r"exception_code=(\d+)")

MODBUS_EXCEPTION_NAMES: dict[int, str] = {
    1: "Illegal Function",
    2: "Illegal Data Address",
    3: "Illegal Data Value",
    4: "Server Device Failure",
    5: "Acknowledge",
    6: "Server Device Busy",
    8: "Memory Parity Error",
    10: "Gateway Path Unavailable",
    11: "Gateway Target Device Failed To Respond",
}

# Upper bound for the technical detail shown in a Home Assistant message. Long
# library messages must not push the actionable part of the text off screen.
_MAX_DETAIL_LENGTH = 200


def _error_chain_text(err: BaseException) -> str:
    """Return normalized text from an exception and its direct causes."""
    messages: list[str] = []
    current: BaseException | None = err
    while current is not None and len(messages) < 4:
        messages.append(str(current).casefold())
        current = current.__cause__ or current.__context__
    return " ".join(messages)


def classify_communication_error(err: Exception) -> str:
    """Map communication errors to Home Assistant repair issue IDs."""
    message = _error_chain_text(err)
    if isinstance(err, socket.gaierror) or any(
        marker in message
        for marker in (
            "name or service not known",
            "nodename nor servname",
            "temporary failure in name resolution",
            "getaddrinfo failed",
            "dns",
        )
    ):
        return "host_not_found"
    if isinstance(err, ConnectionRefusedError) or any(
        marker in message
        for marker in (
            "connection refused",
            "connect call failed",
            "actively refused",
            "errno 111",
            "winerror 10061",
        )
    ):
        return "modbus_connection_refused"
    if isinstance(err, TimeoutError) or any(
        marker in message for marker in ("timed out", "timeout", "errno 110", "winerror 10060")
    ):
        return "modbus_timeout"
    if isinstance(err, ModbusIOException):
        return "modbus_timeout"
    if isinstance(err, ConnectionException):
        return "cannot_connect"
    if any(marker in message for marker in ("slave", "unit id", "device id", "no response", "no reply")):
        return "wrong_slave_id"
    if any(
        marker in message for marker in ("exception_code=1", "illegal function", "unsupported function", "firmware")
    ):
        return "incompatible_firmware"
    return "cannot_connect"


def friendly_communication_error(issue_id: str, host: str, port: int | None, err: Exception) -> str:
    """Return an actionable communication error for the Home Assistant log."""
    endpoint = f"{host}:{port}" if port is not None else host
    technical_message = _error_chain_text(err)
    messages = {
        "host_not_found": (
            f"The configured IDM address {host} could not be found. "
            "Check the IP address or hostname in the integration settings"
        ),
        "modbus_connection_refused": (
            f"The IDM device at {endpoint} refused the Modbus TCP connection. "
            "Check that Building management system -> Modbus TCP is enabled on the Navigator "
            "and that the configured IP address and port are correct"
        ),
        "modbus_timeout": (
            f"The IDM device at {endpoint} did not respond in time. "
            "Check that the controller is online and that no firewall or network rule blocks the connection"
        ),
        "wrong_slave_id": (
            f"A Modbus endpoint was reached at {endpoint}, but the IDM controller did not answer as expected. "
            "Check the slave ID (normally 1) and the Modbus proxy target"
        ),
        "incompatible_firmware": (
            f"The IDM device at {endpoint} does not support the requested Modbus function. "
            "Check the Navigator firmware and integration compatibility"
        ),
    }
    if issue_id in messages:
        return messages[issue_id]
    if any(
        marker in technical_message
        for marker in ("network is unreachable", "no route to host", "host is unreachable", "errno 101", "errno 113")
    ):
        return (
            f"There is no working network route from Home Assistant to the IDM device at {endpoint}. "
            "Check the device address, network connection, VLAN and router settings"
        )
    if any(
        marker in technical_message
        for marker in ("connection lost", "connection reset", "reset by peer", "broken pipe", "disconnected")
    ):
        return (
            f"The Modbus TCP connection to the IDM device at {endpoint} was interrupted. "
            "Check the network cable or Wi-Fi connection, the controller and any Modbus proxy"
        )
    if any(marker in technical_message for marker in ("crc", "invalid response", "malformed", "decode")):
        return (
            f"The IDM device at {endpoint} sent a Modbus response that could not be read. "
            "Check the network connection, Modbus proxy and whether another Modbus client is interfering"
        )
    return (
        f"The integration could not connect to the IDM device at {endpoint}. "
        "Check the network connection and the Modbus TCP settings on the Navigator"
    )


def classify_web_error(err: Exception) -> str:
    """Map local Navigator web errors to repair issue IDs."""
    message = _error_chain_text(err)
    if isinstance(err, socket.gaierror) or any(
        marker in message for marker in ("name or service not known", "getaddrinfo failed", "name resolution", "dns")
    ):
        return "web_host_not_found"
    if isinstance(err, ConnectionRefusedError) or any(
        marker in message for marker in ("connection refused", "connect call failed", "errno 111", "winerror 10061")
    ):
        return "web_connection_refused"
    if isinstance(err, TimeoutError) or any(marker in message for marker in ("timed out", "timeout")):
        return "web_timeout"
    if any(
        marker in message
        for marker in ("invalid response", "invalid json", "jsondecode", "malformed", "decode", "unexpected content")
    ):
        return "web_invalid_response"
    return "web_supplement_failed"


def friendly_web_error(issue_id: str, host: str) -> str:
    """Return a concise and actionable local web error."""
    messages = {
        "web_host_not_found": (
            f"The configured Navigator web address {host} could not be found. "
            "Check the web host or use the heat pump IP address"
        ),
        "web_connection_refused": (
            f"The Navigator web interface at {host} refused the connection. "
            "Check the web host and whether the local Navigator web interface is available"
        ),
        "web_timeout": (
            f"The Navigator web interface at {host} did not respond in time. "
            "Check the controller and network connection"
        ),
        "web_invalid_response": (
            f"The Navigator web interface at {host} returned data that could not be read. "
            "Check the Navigator model, firmware and integration compatibility"
        ),
    }
    return messages.get(
        issue_id,
        f"The optional Navigator web data at {host} could not be read. "
        "Modbus data continues to work; check the web host and local network access",
    )


def modbus_exception_code(err: BaseException) -> int | None:
    """Return the Modbus exception code carried by an error chain, if any.

    The transport preserves the ``exception_code=<N>`` marker verbatim (see
    :mod:`.modbus_transport`), so the code the controller actually answered
    with survives all the way up to the user-facing message.
    """
    match = _EXCEPTION_CODE_PATTERN.search(_error_chain_text(err))
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:  # pragma: no cover - the pattern only matches digits
        return None


def write_error_detail(err: BaseException) -> str:
    """Return a compact technical summary of a write failure.

    Without this, the only trace of *why* a write failed was a debug-level
    ``exc_info`` line, so a bug report filed at default log level contained
    nothing a maintainer could act on (#237). The summary is short enough to
    carry in a Home Assistant message and in downloaded diagnostics.
    """
    detail = f"{type(err).__name__}: {err}".strip()
    code = modbus_exception_code(err)
    if code is not None:
        name = MODBUS_EXCEPTION_NAMES.get(code)
        rendered = f"Modbus exception code {code}" + (f" ({name})" if name else "")
        if rendered.casefold() not in detail.casefold():
            detail = f"{detail} [{rendered}]"
    if len(detail) > _MAX_DETAIL_LENGTH:
        detail = f"{detail[: _MAX_DETAIL_LENGTH - 1]}\u2026"
    return detail


def classify_write_error(err: Exception) -> str:
    """Return a translated Home Assistant exception key for a write failure."""
    message = _error_chain_text(err)
    # Local guards first: these never reach the wire, so reporting them as a
    # controller rejection sends the user looking in the wrong place.
    if "eeprom" in message and any(marker in message for marker in ("too recently", "write cycle")):
        return "write_eeprom_blocked"
    if any(marker in message for marker in ("read only", "readonly", "not writable", "write protected")):
        return "write_read_only"
    if any(marker in message for marker in ("out of range", "outside", "minimum", "maximum", "min_val", "max_val")):
        return "write_out_of_range"
    if any(
        marker in message
        for marker in (
            "illegal data address",
            "exception_code=2",
            "unsupported register",
            "not available for detected model",
        )
    ):
        return "write_not_supported"
    if any(marker in message for marker in ("invalid value", "invalid type", "cannot encode", "conversion")):
        return "write_invalid_value"
    # Any other Modbus exception code means the controller answered and
    # refused the write; that is a different problem from "no connection".
    if modbus_exception_code(err) is not None:
        return "write_rejected_by_device"
    communication_issue = classify_communication_error(err)
    if (
        communication_issue != "cannot_connect"
        or isinstance(err, (ConnectionException, ConnectionError, OSError))
        or any(
            marker in message
            for marker in ("connection lost", "connection reset", "broken pipe", "not connected", "disconnected")
        )
    ):
        return "write_connection_failed"
    return "write_failed"


def friendly_write_error(translation_key: str, register_name: str) -> str:
    """Return a concise reason for background write logs."""
    messages = {
        "write_connection_failed": "the Modbus connection to the heat pump failed",
        "write_read_only": "the target register is read-only or currently locked",
        "write_out_of_range": "the temperature is outside the permitted register range",
        "write_not_supported": "the target register is not supported by this heat pump",
        "write_invalid_value": "the value has an invalid format or data type",
        "write_eeprom_blocked": "the EEPROM write protection is still blocking this register",
        "write_rejected_by_device": "the heat pump answered the write with a Modbus exception",
    }
    return messages.get(translation_key, f"register {register_name} rejected the value")


def write_error_placeholders(register_name: str, err: BaseException | None = None) -> dict[str, str]:
    """Return safe placeholders for a write-failure message.

    ``detail`` carries the technical summary for the message templates that ask
    for it; templates that do not reference it simply ignore the extra key.
    """
    return {
        "register": register_name,
        "detail": write_error_detail(err) if err is not None else "no technical detail available",
    }


def scoped_issue_id(entry_id: str | None, issue_id: str) -> str:
    """Scope a repair-issue id to one config entry.

    Home Assistant's issue registry is keyed by (domain, issue_id) with no
    implicit per-entry scoping. Every repair issue this integration creates
    must therefore embed the entry id itself, or two heat pumps hitting the
    same condition (e.g. both missing a web PIN) silently overwrite each
    other's registry entry - the second entry's problem becomes invisible
    and clearing it also clears the first entry's issue.
    """
    return f"{issue_id}_{entry_id}" if entry_id else issue_id
