"""Tests for the pymodbus logging noise filter."""

from __future__ import annotations

import logging

import pytest

from custom_components.idm_heatpump.log_filter import (
    PYMODBUS_LOGGER_NAME,
    _PymodbusNoiseFilter,
    install_pymodbus_log_filter,
)


def _make_record(message: str, level: int = logging.ERROR, name: str = PYMODBUS_LOGGER_NAME) -> logging.LogRecord:
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
        logger = logging.getLogger(PYMODBUS_LOGGER_NAME)
        logger.filters.clear()

    def teardown_method(self) -> None:
        # Reset the global installed flag and remove any filters we added
        # so each test starts from a clean state.
        import custom_components.idm_heatpump.log_filter as mod

        mod._INSTALLED = False
        logger = logging.getLogger(PYMODBUS_LOGGER_NAME)
        logger.filters.clear()

    def test_installs_filter_on_pymodbus_logger(self) -> None:
        logger = logging.getLogger(PYMODBUS_LOGGER_NAME)
        assert not any(isinstance(f, _PymodbusNoiseFilter) for f in logger.filters)
        install_pymodbus_log_filter()
        assert any(isinstance(f, _PymodbusNoiseFilter) for f in logger.filters)

    def test_is_idempotent(self) -> None:
        install_pymodbus_log_filter()
        install_pymodbus_log_filter()
        install_pymodbus_log_filter()
        logger = logging.getLogger(PYMODBUS_LOGGER_NAME)
        installed = [f for f in logger.filters if isinstance(f, _PymodbusNoiseFilter)]
        assert len(installed) == 1
