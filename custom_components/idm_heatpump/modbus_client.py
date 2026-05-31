"""Async Modbus TCP client for IDM Navigator heat pumps.

This module is now a thin compatibility wrapper around the official
`idm_heatpump` library (Option B migration).

All real functionality (connection handling, batching, retries,
decoding, model detection, etc.) lives in the library.
"""

from __future__ import annotations

import logging

from pymodbus.exceptions import ConnectionException

from idm_heatpump import IdmModbusClient as _LibIdmModbusClient
from idm_heatpump.client import DataType as LibDataType, RegisterDef as LibRegisterDef

_LOGGER = logging.getLogger(__name__)

# Re-export for backward compatibility with the rest of the integration
DataType = LibDataType
RegisterDef = LibRegisterDef


class IdmModbusClient(_LibIdmModbusClient):
    """
    HA compatibility wrapper around the official idm_heatpump library client.

    Everything important (connect, read/write batch, decode/encode,
    detect_model, etc.) is inherited from the library.
    """

    def __init__(self, host: str, port: int = 502, slave_id: int = 1) -> None:
        super().__init__(host=host, port=port, slave_id=slave_id)
        _LOGGER.debug("IdmModbusClient (HA wrapper) using idm_heatpump library")


# Convenience re-exports used in some places in the integration
__all__ = ["IdmModbusClient", "DataType", "RegisterDef"]