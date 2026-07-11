"""Tests for actionable error classification and messages."""

from __future__ import annotations

import socket

import pytest

from custom_components.idm_heatpump.error_messages import (
    classify_communication_error,
    classify_web_error,
    classify_write_error,
    friendly_write_error,
    friendly_web_error,
)
from pymodbus.exceptions import ConnectionException, ModbusException


@pytest.mark.parametrize(
    ("error", "issue_id"),
    [
        (socket.gaierror("getaddrinfo failed"), "host_not_found"),
        (ConnectionException("WinError 10061 actively refused"), "modbus_connection_refused"),
        (ConnectionException("WinError 10060 timeout"), "modbus_timeout"),
        (ModbusException("no response from slave 1"), "wrong_slave_id"),
        (ModbusException("unsupported function"), "incompatible_firmware"),
    ],
)
def test_classifies_common_communication_variants(error: Exception, issue_id: str) -> None:
    assert classify_communication_error(error) == issue_id


@pytest.mark.parametrize(
    ("error", "issue_id"),
    [
        (socket.gaierror("name resolution failed"), "web_host_not_found"),
        (ConnectionRefusedError("connection refused"), "web_connection_refused"),
        (TimeoutError("request timed out"), "web_timeout"),
        (ValueError("invalid JSON response"), "web_invalid_response"),
        (RuntimeError("unexpected web failure"), "web_supplement_failed"),
    ],
)
def test_classifies_web_errors(error: Exception, issue_id: str) -> None:
    assert classify_web_error(error) == issue_id
    assert "Navigator" in friendly_web_error(issue_id, "192.0.2.103")


@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        (ConnectionException("connection lost"), "write_connection_failed"),
        (ValueError("value out of range"), "write_out_of_range"),
        (PermissionError("register is read only"), "write_read_only"),
        (ModbusException("Illegal Data Address exception_code=2"), "write_not_supported"),
        (ValueError("cannot encode invalid value"), "write_invalid_value"),
        (RuntimeError("unknown failure"), "write_failed"),
    ],
)
def test_classifies_write_errors(error: Exception, translation_key: str) -> None:
    assert classify_write_error(error) == translation_key
    assert friendly_write_error(translation_key, "test_register")
