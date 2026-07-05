"""Logging filters for noisy third-party dependencies.

pymodbus (used via idm-heatpump-api) logs routine connection drops at
ERROR level and, when DEBUG logging is disabled, appends up to 20
buffered raw frame dumps to each record (``pymodbus/logging.py`` ->
``Log.error``). This floods the Home Assistant log with byte-for-byte
Modbus frames after every transient disconnect.

The integration's coordinator already converts communication failures
into a single ``UpdateFailed`` warning, so the pymodbus records are
redundant. ``_install_pymodbus_log_filter`` installs a small filter on
the ``pymodbus.logging`` logger that drops the two known-noisy
transport/transaction ERROR records. All other pymodbus logging
(including genuine ERROR records with different messages) is left
untouched, and DEBUG-level frame dumps remain available when the user
explicitly enables debug logging for pymodbus.
"""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

PYMODBUS_LOGGER_NAME = "pymodbus.logging"

_NOISY_ERROR_PREFIXES: tuple[str, ...] = (
    # pymodbus transport.py: Log.error("Cancel send, because not connected!")
    "Cancel send, because not connected!",
    # pymodbus transaction.py: Log.error("No response received after N retries, ...")
    "No response received after ",
)


class _PymodbusNoiseFilter(logging.Filter):
    """Drop pymodbus ERROR records that are routine connection noise.

    Only matches the two specific ERROR-level messages that pymodbus
    emits during transient disconnects. Each match returns False so the
    record is suppressed before reaching Home Assistant's log. Every
    other record (DEBUG frame dumps, real ERRORs, warnings) flows
    through unchanged.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < logging.ERROR:
            return True
        message = record.getMessage()
        for prefix in _NOISY_ERROR_PREFIXES:
            if message.startswith(prefix):
                return False
        return True


_INSTALLED = False


def install_pymodbus_log_filter() -> None:
    """Install the pymodbus noise filter once on the pymodbus logger.

    Safe to call multiple times: the filter is added only once even if
    the integration is reloaded. This keeps the global pymodbus logger
    clean across HA restarts without stacking duplicate filters.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    logger = logging.getLogger(PYMODBUS_LOGGER_NAME)
    logger.addFilter(_PymodbusNoiseFilter())
    _INSTALLED = True
    _LOGGER.debug(
        "Installed pymodbus noise filter on logger %s (suppressing routine "
        "connection-drop ERROR records)",
        PYMODBUS_LOGGER_NAME,
    )
