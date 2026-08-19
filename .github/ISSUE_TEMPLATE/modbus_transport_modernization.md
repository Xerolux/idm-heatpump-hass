---
name: Modbus transport follow-up
about: Track tmodbus hardware validation and a future Home Assistant shared-connection provider
title: "[Modbus transport]: "
labels: modbus, architecture, blocked-upstream
assignees: ''
---

## Implemented runtime boundary

- [x] `IdmModbusConnectionClient` keeps IDM device logic in
      `idm-heatpump-api[web]==1.0.0` and routes raw I/O through
      `ModbusConnectionTransport`.
- [x] The direct socket uses the exact
      `modbus-connection==4.8.1` / `tmodbus[async-serial]==0.5.1` pair.
- [x] `pymodbus>=3.12.1,<4.0` remains temporarily pinned because the pinned
      API version still imports it; pymodbus does not own the direct socket.
- [x] Each config entry owns its socket. Capabilities report
      `source=modbus_connection.tmodbus`, `owns_socket=True`, and
      `supports_shared_connection=False`.
- [x] Diagnostics redact the host and expose transport capabilities and runtime
      versions.
- [x] No Optionsflow transport selector, second socket path, or additional
      write path exists.

`4.8.1` is the version of the connection library, not the IDM integration
version. The first IDM integration beta shipping this path is
`0.11.0-beta.1`.

## Read-only hardware validation

- Navigator/controller model:
- Heat-pump model:
- Firmware:
- Home Assistant version:
- Integration commit:
- `modbus-connection` / `tmodbus` versions:
- Network path (direct / proxy; redact addresses):

Validate without writes:

- [ ] Setup-time connect and known-register probe succeed.
- [ ] FC04 input-register reads return the expected raw word count.
- [ ] FC03 holding-register reads return the expected raw word count.
- [ ] A dropped connection reconnects on the next operation.
- [ ] Unload closes only this config entry's socket.
- [ ] Timeout, refusal, wrong slave ID, and Illegal Address keep their existing
      user-facing classifications.
- [ ] Diagnostics stay redacted and report
      `supports_shared_connection: false`.

Do not perform FC16 or service writes on real hardware unless the owner
explicitly authorizes the exact register and value.

## Central Home Assistant sharing status

- Home Assistant developer documentation link:
- Date checked:
- Is a central shared Modbus connection contract stable for custom
  integrations? yes / no / unclear
- Lifecycle/ownership documentation:

The current tmodbus adapter is already implemented. This section concerns only
a future provider backed by Home Assistant's central cross-entry connection,
not the current per-entry socket.

Future-provider guardrails:

- No new manifest requirement is assumed until the central provider contract
  and its packaging are documented.
- No direct import of a non-final Home Assistant Modbus API is allowed.
- Existing entities keep the same Unique IDs.

## Open central-provider decisions

- HA connection object and acquisition API:
- Provider class implementing `IdmModbusTransport`:
- Unit/slave binding:
- Timeout and retry ownership:
- Handling multiple config entries for the same host/port/slave:
- Unload/reload ownership and reference counting:
- Error translation into the established API/coordinator contract:
- Fallback to the current private tmodbus connection when central sharing is
  unavailable:

## Acceptance criteria for a future shared provider

- [ ] The central API is documented and supported for custom integrations.
- [ ] Existing config entries and entity Unique IDs need no user migration.
- [ ] All platforms still route writes through
      `IdmCoordinator.async_write_register`.
- [ ] The provider reports `supports_shared_connection=True` only when it
      actually uses the central connection and reports socket ownership
      accurately.
- [ ] The current private tmodbus provider remains covered by tests.
- [ ] Fake transports cover private-socket and central shared-connection
      lifecycle behavior.
- [ ] No real heat-pump write test is required.
- [ ] Release notes distinguish the integration version from dependency
      versions and explain provider selection/fallback.
