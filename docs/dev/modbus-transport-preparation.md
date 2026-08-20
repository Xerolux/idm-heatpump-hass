# Modbus Transport Preparation

Last updated: 2026-08-04

This document describes the local Modbus transport, which is implemented by now,
and the two steps deliberately left open: read-only hardware verification and a
possible later Home Assistant connection with cross-entry sharing.

## Current status

- The direct Modbus TCP runtime path uses `modbus-connection==4.0.0a3` and the
  separately, exactly pinned backend level `tmodbus==0.5.0`.
- `IdmModbusConnectionClient` is the integration's production client. It uses
  the device model of `idm-heatpump-api[web]==0.9.1`, but replaces its raw I/O
  hooks with `ModbusConnectionTransport`.
- `pymodbus>=3.12.1,<4.0` stays installed for the time being, because
  `idm-heatpump-api` 0.9.1 still imports pymodbus and uses its established error
  contract. Pymodbus no longer owns the direct socket.
- Every config entry owns its own tmodbus connection. Home Assistant's central
  cross-entry Modbus connection is currently not available to custom
  integrations as a stable contract, which is why the adapter explicitly reports
  `supports_shared_connection=False`.
- There is no transport selection in the options flow and no parallel pymodbus
  fallback path.
- The first integration version to ship this is `0.11.0-beta.1`. `4.0.0a3` is
  the version of the transport library, not an IDM release.

## Implemented layer separation

1. **Home Assistant integration**
   - config flow, coordinator, entities, services, diagnostics and repairs.
   - `library_adapter.create_library_client()` always creates the new
     `IdmModbusConnectionClient`.
2. **idm-heatpump-api 0.9.1**
   - register model and register type,
   - batch planning,
   - encoding/decoding,
   - model and firmware detection,
   - write safety rules,
   - retry/backoff contract.
3. **Local Modbus transport**
   - `ModbusConnectionTransport` reserves and closes the socket,
   - tmodbus performs raw FC03/FC04/FC16 operations,
   - `modbus_client.py` translates transport errors into the existing
     API/coordinator error contract,
   - static capabilities document the source, socket ownership and the missing
     central sharing.

The runtime path is therefore:

```text
IdmCoordinator
  -> IdmModbusConnectionClient
     -> idm-heatpump-api 0.9.1 (device logic)
     -> ModbusConnectionTransport
        -> modbus-connection 4.0.0a3
           -> tmodbus 0.5.0
              -> IDM Navigator (TCP 502)
```

## Transport contract

The contract uses raw register addresses and raw 16-bit words. That keeps device
knowledge in the API instead of in the transport class.

```python
transport.endpoint
transport.capabilities
await transport.async_connect()
await transport.async_close()
input_words = await transport.async_read_input_registers(address, count)
holding_words = await transport.async_read_holding_registers(address, count)
await transport.async_write_registers(address, values)
```

Input registers (function code 04) and holding registers (function code 03)
remain separate read operations. Writing uses function code 16. In each case the
adapter takes the register type the API prescribes and verifies that the answer
contains the expected number of words.

`ModbusTcpEndpoint` validates the host, the TCP port, slave IDs 1–247, a
positive timeout and non-negative retries. `connection_key` returns a normalized
`(host, port, slave_id)` identifier for conflict checks.

## Connection and error behavior

- Setup and reconfigure connect immediately on purpose, so that an invalid
  target definition surfaces before the entry is created or updated.
- Normal operations are serialized. After a dropped connection,
  `modbus-connection` reconnects on the next operation.
- The API retry configuration and its exponential backoff are preserved.
- Illegal address (Modbus exception code 2), timeout, connection and protocol
  errors are translated into the existing API exceptions, so that resilient
  polling, repairs and user-friendly config flow errors keep working.
- An entry closes only its own socket. The adapter claims neither pooling nor
  cross-entry reuse.

## Diagnostics and privacy

`ModbusTcpEndpoint.as_redacted_diagnostics()` replaces host/IP with a fixed
redaction value. Port, slave ID, timeout and retries stay visible for
troubleshooting.

The transport block reports:

```yaml
source: modbus_connection.tmodbus
owns_socket: true
supports_shared_connection: false
connected: true_or_false
```

The diagnostics export, the startup log and the existing API version sensor
additionally contain the installed versions of the integration,
`idm-heatpump-api`, `modbus-connection`, `tmodbus` and the temporary pymodbus
compatibility dependency.

## Verification

Automated tests cover endpoint validation, FC03/FC04 separation, FC16 writes,
retry and error translation, reconnect, close behavior, factory wiring, version
diagnostics and redacted capabilities.

Still open is the **read-only hardware verification of the new tmodbus path** on
real Navigator systems. Earlier hardware measurements prove registers and device
logic, but they were taken before this transport change and therefore do not
automatically confirm the new socket path. Write tests on real systems remain
excluded without an explicit authorization.

## Remaining work

1. Verify setup, FC03, FC04, connection loss and reconnect read-only against
   real Navigator hardware, and document firmware and model.
2. Evolve `idm-heatpump-api` towards a public, transport-neutral I/O contract.
   Only then can the temporary pymodbus dependency be dropped, after a
   compatibility check.
3. Watch Home Assistant's final central shared-connection contract. If it
   becomes stably available for custom integrations, implement a separate
   provider; only that provider may report `supports_shared_connection=True` and
   `owns_socket=False`.
4. Plan any migration without new unique IDs, without a new write path and
   without forcing options changes. Until then the private tmodbus socket
   remains the only production Modbus path.

## Issue template

`.github/ISSUE_TEMPLATE/modbus_transport_modernization.md` tracks the hardware
verification as well as the later central sharing provider. The template no
longer treats the already implemented tmodbus adapter as future work.
