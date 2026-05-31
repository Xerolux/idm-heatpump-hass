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

    async def test_connection(self) -> bool:
        """
        Safe read-only connection test.

        Tries to read the outdoor temperature register (1000) as a basic
        connectivity and register access check. Does NOT perform any writes.
        """
        try:
            await self.connect()
            if not self.is_connected:
                return False

            # Safe read-only probe: outdoor temperature (very common register)
            value = await self.probe_register(1000, 2)
            if value is not None:
                _LOGGER.debug("Connection test successful (read outdoor temp register)")
                return True

            _LOGGER.warning("Connection test: could not read test register")
            return False

        except Exception as err:
            _LOGGER.debug("Connection test failed: %s", err)
            return False
        finally:
            # We leave the connection open — the normal lifecycle will handle disconnect
            pass


# Convenience re-exports used in some places in the integration
__all__ = ["IdmModbusClient", "DataType", "RegisterDef"]