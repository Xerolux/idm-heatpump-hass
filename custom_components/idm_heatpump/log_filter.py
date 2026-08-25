"""Logging filter for repeated register-failure warnings.

``idm-heatpump-api`` logs a WARNING "Modbus read at address X failed after N
   attempts: ..." whenever a register read exhausts its retries. For registers
   the device does not implement (Modbus ``Illegal Data Address`` / exception
   code 2) this is a permanent condition that is retried on every poll,
   producing thousands of identical warnings over hours (e.g. 6000+ entries for
   a handful of optional registers on a Navigator 2.0). The coordinator and the
   library already isolate these addresses and stop reading them, so the
repeated warnings carry no actionable information. They are suppressed entirely.

All other logging from the library (genuine ERRORs, DEBUG frame dumps, decoding
warnings) is left untouched, and DEBUG-level detail remains available when the
user explicitly enables debug logging.

The pymodbus filter that used to live here went away with the dependency:
``idm-heatpump-api`` 2.0.0 no longer imports pymodbus, so there is no
``pymodbus.logging`` logger to quieten.
"""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

LIBRARY_LOGGER_NAME = "idm_heatpump.client"

# idm-heatpump-api retry-exhaustion warnings for individual registers. These are
# emitted from IdmModbusClient._retry_command on every poll for addresses the
# device rejects, flooding the log. Suppressed outright: the coordinator's
# UpdateFailed path and the library's own permanently-failed tracking already
# surface persistent problems.
_ILLEGAL_ADDRESS_LIBRARY_MARKERS: tuple[str, ...] = (
    "failed after",
    "has failed",
)


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


def install_library_log_filter() -> None:
    """Install the log filter once on the ``idm-heatpump-api`` logger.

    Safe to call multiple times: the filter is added only once even if the
    integration is reloaded. This keeps the global logger clean across HA
    restarts without stacking duplicate filters.

    Suppresses repeated register-failure WARNINGs for ``Illegal Data Address``
    registers so they do not flood the log.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    logging.getLogger(LIBRARY_LOGGER_NAME).addFilter(_LibraryIllegalAddressFilter())
    _INSTALLED = True
    _LOGGER.debug(
        "Installed the idm-heatpump-api noise filter (suppressing repeated register-failure WARNINGs)",
    )
