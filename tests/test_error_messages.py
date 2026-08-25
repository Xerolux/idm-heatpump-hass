"""Tests for actionable error classification and messages."""

from __future__ import annotations

import socket

import pytest
from idm_heatpump import IdmConnectionError, IdmDeviceError, IdmModbusError

from custom_components.idm_heatpump.error_messages import (
    classify_communication_error,
    classify_web_error,
    classify_write_error,
    friendly_web_error,
    friendly_write_error,
    modbus_exception_code,
    scoped_issue_id,
    write_error_detail,
    write_error_placeholders,
)


@pytest.mark.parametrize(
    ("error", "issue_id"),
    [
        (socket.gaierror("getaddrinfo failed"), "host_not_found"),
        (IdmConnectionError("WinError 10061 actively refused"), "modbus_connection_refused"),
        (IdmConnectionError("WinError 10060 timeout"), "modbus_timeout"),
        (IdmDeviceError("no response from slave 1"), "wrong_slave_id"),
        (IdmDeviceError("unsupported function"), "incompatible_firmware"),
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
        (IdmConnectionError("connection lost"), "write_connection_failed"),
        (ValueError("value out of range"), "write_out_of_range"),
        (PermissionError("register is read only"), "write_read_only"),
        (IdmDeviceError("Illegal Data Address exception_code=2"), "write_not_supported"),
        (ValueError("cannot encode invalid value"), "write_invalid_value"),
        (RuntimeError("unknown failure"), "write_failed"),
        (
            ValueError("EEPROM-sensitive register 'hc_c_room_setpoint_heat_normal' was written too recently"),
            "write_eeprom_blocked",
        ),
        (
            ValueError("Register 'hc_c_room_setpoint_heat_normal' is not available for detected model Navigator 10"),
            "write_not_supported",
        ),
        (
            IdmModbusError("Modbus write at address 1405 failed: refused (exception_code=4)"),
            "write_rejected_by_device",
        ),
        (
            IdmModbusError("Modbus write at address 1405 failed: busy (exception_code=6)"),
            "write_rejected_by_device",
        ),
    ],
)
def test_classifies_write_errors(error: Exception, translation_key: str) -> None:
    assert classify_write_error(error) == translation_key
    assert friendly_write_error(translation_key, "test_register")


class TestWriteErrorDetail:
    """A write failure has to carry its reason all the way into the message.

    Before #237 the technical reason lived only behind ``logger: debug``, so a
    bug report filed at default log level said nothing beyond "write failed".
    """

    def test_reads_back_the_modbus_exception_code(self) -> None:
        error = IdmDeviceError("Modbus write at address 1405 failed: refused (exception_code=4)")
        assert modbus_exception_code(error) == 4
        detail = write_error_detail(error)
        assert "Modbus exception code 4" in detail
        assert "Server Device Failure" in detail

    def test_plain_errors_have_no_code(self) -> None:
        assert modbus_exception_code(ValueError("nope")) is None
        assert write_error_detail(ValueError("nope")) == "ValueError: nope"

    def test_detail_is_bounded(self) -> None:
        detail = write_error_detail(ValueError("x" * 500))
        assert len(detail) <= 200

    def test_placeholders_carry_the_detail(self) -> None:
        placeholders = write_error_placeholders("hc_c_room_setpoint_heat_normal", ValueError("nope"))
        assert placeholders["register"] == "hc_c_room_setpoint_heat_normal"
        assert placeholders["detail"] == "ValueError: nope"

    def test_placeholders_stay_valid_without_an_error(self) -> None:
        placeholders = write_error_placeholders("hc_c_room_setpoint_heat_normal")
        assert set(placeholders) == {"register", "detail"}


def test_scoped_issue_id_embeds_entry_id() -> None:
    assert scoped_issue_id("entry-1", "web_pin_missing") == "web_pin_missing_entry-1"


def test_scoped_issue_id_differs_across_entries() -> None:
    """Two heat pumps hitting the same condition must not collide in the issue registry."""
    first = scoped_issue_id("entry-1", "web_pin_missing")
    second = scoped_issue_id("entry-2", "web_pin_missing")
    assert first != second


def test_scoped_issue_id_falls_back_without_entry_id() -> None:
    assert scoped_issue_id(None, "web_pin_missing") == "web_pin_missing"
