"""Classify low-level errors into actionable user-facing messages."""

from __future__ import annotations

import socket

from pymodbus.exceptions import ConnectionException, ModbusIOException


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


def classify_write_error(err: Exception) -> str:
    """Return a translated Home Assistant exception key for a write failure."""
    message = _error_chain_text(err)
    if any(marker in message for marker in ("read only", "readonly", "not writable", "write protected")):
        return "write_read_only"
    if any(marker in message for marker in ("out of range", "outside", "minimum", "maximum", "min_val", "max_val")):
        return "write_out_of_range"
    if any(marker in message for marker in ("illegal data address", "exception_code=2", "unsupported register")):
        return "write_not_supported"
    if any(marker in message for marker in ("invalid value", "invalid type", "cannot encode", "conversion")):
        return "write_invalid_value"
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
    }
    return messages.get(translation_key, f"register {register_name} rejected the value")


def write_error_placeholders(register_name: str) -> dict[str, str]:
    """Return safe placeholders without exposing a raw library exception."""
    return {"register": register_name}
