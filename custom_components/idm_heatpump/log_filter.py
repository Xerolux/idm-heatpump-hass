"""Logging filters for noisy third-party dependencies.

Two sources of log spam are suppressed here:

1. **pymodbus** (used via idm-heatpump-api) logs routine connection drops at
   ERROR level and, when DEBUG logging is disabled, appends up to 20 buffered
   raw frame dumps to each record (``pymodbus/logging.py`` -> ``Log.error``).
   This floods the Home Assistant log with byte-for-byte Modbus frames after
   every transient disconnect. The integration's coordinator already converts
   communication failures into a single ``UpdateFailed`` warning, so these
   pymodbus records are redundant.

2. **idm-heatpump-api** logs a WARNING "Modbus read at address X failed after N
   attempts: ..." whenever a register read exhausts its retries. For registers
   the device does not implement (Modbus ``Illegal Data Address`` / exception
   code 2) this is a permanent condition that is retried on every poll,
   producing thousands of identical warnings over hours (e.g. 6000+ entries for
   a handful of optional registers on a Navigator 2.0). The coordinator and the
   library already isolate these addresses and stop reading them, so the
   repeated warnings carry no actionable information. They are suppressed
   entirely.

All other logging from both libraries (genuine ERRORs, DEBUG frame dumps,
decoding warnings) is left untouched, and DEBUG-level detail remains available
when the user explicitly enables debug logging.
"""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

PYMODBUS_LOGGER_NAME = "pymodbus.logging"
LIBRARY_LOGGER_NAME = "idm_heatpump.client"

_NOISY_ERROR_PREFIXES: tuple[str, ...] = (
    # pymodbus transport.py: Log.error("Cancel send, because not connected!")
    "Cancel send, because not connected!",
    # pymodbus transaction.py: Log.error("No response received after N retries, ...")
    "No response received after ",
)

# idm-heatpump-api retry-exhaustion warnings for individual registers. These are
# emitted from IdmModbusClient._retry_command on every poll for addresses the
# device rejects, flooding the log. Suppressed outright: the coordinator's
# UpdateFailed path and the library's own permanently-failed tracking already
# surface persistent problems.
_ILLEGAL_ADDRESS_LIBRARY_MARKERS: tuple[str, ...] = (
    "failed after",
    "has failed",
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


class _LibraryIllegalAddressFilter(logging.Filter):
    """Drop idm-heatpump-api register-failure warnings that repeat every poll.

    Matches the WARNING records the library emits when a register read exhausts
    its retries ("Modbus read at address X failed after N attempts") or when a
    register crosses the permanent-failure threshold ("Register X has failed N
    times"). For ``Illegal Data Address`` registers these fire on every poll and
    carry no new information once the address has been isolated. They are
    suppressed here; the coordinator's repair issues and DEBUG-level logs remain
    the source of truth for unsupported registers.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < logging.WARNING:
            return True
        message = record.getMessage()
        for marker in _ILLEGAL_ADDRESS_LIBRARY_MARKERS:
            if marker in message:
                return False
        return True


_INSTALLED = False


def install_pymodbus_log_filter() -> None:
    """Install the log filters once on the third-party loggers.

    Safe to call multiple times: each filter is added only once even if the
    integration is reloaded. This keeps the global loggers clean across HA
    restarts without stacking duplicate filters.

    Installs two filters:
      * ``pymodbus.logging``: suppresses routine connection-drop ERROR records.
      * ``idm_heatpump.client``: suppresses repeated register-failure WARNINGs
        for ``Illegal Data Address`` registers so they do not flood the log.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    logging.getLogger(PYMODBUS_LOGGER_NAME).addFilter(_PymodbusNoiseFilter())
    logging.getLogger(LIBRARY_LOGGER_NAME).addFilter(_LibraryIllegalAddressFilter())
    _INSTALLED = True
    _LOGGER.debug(
        "Installed noise filters on pymodbus and idm-heatpump-api loggers "
        "(suppressing routine connection-drop ERRORs and repeated register-failure WARNINGs)",
    )
