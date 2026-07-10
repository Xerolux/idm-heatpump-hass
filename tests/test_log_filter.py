"""Tests for the pymodbus and idm-heatpump-api logging noise filters."""

from __future__ import annotations

import logging

import pytest

from custom_components.idm_heatpump.log_filter import (
    LIBRARY_LOGGER_NAME,
    PYMODBUS_LOGGER_NAME,
    _LibraryIllegalAddressFilter,
    _PymodbusNoiseFilter,
    install_pymodbus_log_filter,
)


def _make_record(
    message: str,
    level: int = logging.ERROR,
    name: str = PYMODBUS_LOGGER_NAME,
) -> logging.LogRecord:
    return logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


class TestPymodbusNoiseFilter:
    @pytest.mark.parametrize(
        "message",
        [
            "Cancel send, because not connected!",
            "No response received after 3 retries, continue with next request",
            # pymodbus appends buffered frame dumps when DEBUG is disabled;
            # the filter still matches by prefix.
            "Cancel send, because not connected! >>>>> recv: 0xb 0x4 >>>>> send: 0xb 0x4",
            "No response received after 3 retries, continue with next request\n>>>>> recv: 0xb",
        ],
    )
    def test_drops_known_noisy_error_records(self, message: str) -> None:
        filt = _PymodbusNoiseFilter()
        assert filt.filter(_make_record(message)) is False

    @pytest.mark.parametrize(
        "message",
        [
            "ERROR: No response received of the last requests (default: retries+3), CLOSING CONNECTION.",
            "Some other modbus error",
            "Connection reset by peer",
        ],
    )
    def test_passes_through_other_error_records(self, message: str) -> None:
        filt = _PymodbusNoiseFilter()
        assert filt.filter(_make_record(message)) is True

    @pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO, logging.WARNING])
    def test_passes_through_non_error_records(self, level: int) -> None:
        filt = _PymodbusNoiseFilter()
        # Even with a noisy prefix, DEBUG/INFO/WARNING records must flow through
        # so users enabling pymodbus debug logging still see frame dumps.
        record = _make_record("No response received after 3 retries", level=level)
        assert filt.filter(record) is True


class TestInstallPymodbusLogFilter:
    def setup_method(self) -> None:
        # Reset the global installed flag and clear filters before each test
        # so we don't see state leaked from async_setup() calls in other tests.
        import custom_components.idm_heatpump.log_filter as mod

        mod._INSTALLED = False
        for logger_name in (PYMODBUS_LOGGER_NAME, LIBRARY_LOGGER_NAME):
            logging.getLogger(logger_name).filters.clear()

    def teardown_method(self) -> None:
        # Reset the global installed flag and remove any filters we added
        # so each test starts from a clean state.
        import custom_components.idm_heatpump.log_filter as mod

        mod._INSTALLED = False
        for logger_name in (PYMODBUS_LOGGER_NAME, LIBRARY_LOGGER_NAME):
            logging.getLogger(logger_name).filters.clear()

    def test_installs_filter_on_pymodbus_logger(self) -> None:
        logger = logging.getLogger(PYMODBUS_LOGGER_NAME)
        assert not any(isinstance(f, _PymodbusNoiseFilter) for f in logger.filters)
        install_pymodbus_log_filter()
        assert any(isinstance(f, _PymodbusNoiseFilter) for f in logger.filters)

    def test_installs_filter_on_library_logger(self) -> None:
        logger = logging.getLogger(LIBRARY_LOGGER_NAME)
        assert not any(isinstance(f, _LibraryIllegalAddressFilter) for f in logger.filters)
        install_pymodbus_log_filter()
        assert any(isinstance(f, _LibraryIllegalAddressFilter) for f in logger.filters)

    def test_is_idempotent(self) -> None:
        install_pymodbus_log_filter()
        install_pymodbus_log_filter()
        install_pymodbus_log_filter()
        pymodbus_logger = logging.getLogger(PYMODBUS_LOGGER_NAME)
        library_logger = logging.getLogger(LIBRARY_LOGGER_NAME)
        assert len([f for f in pymodbus_logger.filters if isinstance(f, _PymodbusNoiseFilter)]) == 1
        assert len([f for f in library_logger.filters if isinstance(f, _LibraryIllegalAddressFilter)]) == 1


class TestLibraryIllegalAddressFilter:
    @pytest.mark.parametrize(
        "message",
        [
            # idm-heatpump-api _retry_command WARNING on retry exhaustion
            "Modbus read at address 1000 failed after 3 attempts: Modbus Error: ...",
            "Modbus write at address 1200 failed after 1 attempts: ...",
            # idm-heatpump-api _read_individual_fallback permanent-failure WARNING
            "Register cascade_temp (address 1200) has failed 3 times. Marking as permanently failed.",
        ],
    )
    def test_drops_repeated_register_failure_warnings(self, message: str) -> None:
        filt = _LibraryIllegalAddressFilter()
        record = _make_record(message, level=logging.WARNING, name=LIBRARY_LOGGER_NAME)
        assert filt.filter(record) is False

    @pytest.mark.parametrize(
        "message",
        [
            # Genuine connection-loss warning must still surface
            "Connection lost while reading group at address 1000",
            "Connection lost during individual read of outdoor_temp (address 1000)",
            # Decoding failures are actionable
            "Decoding failed for register outdoor_temp (address 1000): bad value",
            # Incomplete data warnings
            "Incomplete data for register outdoor_temp (address 1000)",
            "Some unrelated library warning",
        ],
    )
    def test_passes_through_other_warnings(self, message: str) -> None:
        filt = _LibraryIllegalAddressFilter()
        record = _make_record(message, level=logging.WARNING, name=LIBRARY_LOGGER_NAME)
        assert filt.filter(record) is True

    @pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO])
    def test_passes_through_below_warning(self, level: int) -> None:
        # DEBUG/INFO records (e.g. isolation notices) must flow through so they
        # remain visible when a user enables debug logging.
        filt = _LibraryIllegalAddressFilter()
        record = _make_record(
            "Register cascade_temp failed after 1 attempts",
            level=level,
            name=LIBRARY_LOGGER_NAME,
        )
        assert filt.filter(record) is True
