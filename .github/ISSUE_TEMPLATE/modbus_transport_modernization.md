---
name: Modbus transport modernization
about: Track the future Home Assistant shared Modbus connection adapter without changing runtime behavior yet
title: "[Modbus transport]: "
labels: modbus, architecture, blocked-upstream
assignees: ''
---

## Upstream status

- Home Assistant developer documentation link:
- Date checked:
- Is the HA shared Modbus connection contract final? yes / no / unclear
- Are custom integrations allowed to depend on it? yes / no / unclear

## Current integration boundary

- [ ] Current `idm-heatpump-api` / `IdmModbusClient` path remains the production path.
- [ ] No new manifest requirement is introduced in this issue.
- [ ] No Optionsflow switch for experimental transports is added yet.
- [ ] No direct import of a non-final Home Assistant Modbus API is added.
- [ ] No additional write path is added.

## Proposed mapping to the prepared contract

Prepared contract: `custom_components/idm_heatpump/modbus_transport.py`

- HA connection object:
- Adapter class name:
- How `ModbusTcpEndpoint` is populated:
- How `ModbusTransportCapabilities.source` is reported:
- How `owns_socket` is set:
- How `supports_shared_connection` is set:

## Open decisions

- Timeout owner: Home Assistant / API / integration / undecided
- Retry owner: Home Assistant / API / integration / undecided
- Batch planning owner: API / transport / undecided
- Error classification owner: API / integration / undecided
- Fallback when shared connection is unavailable:
- Handling multiple IDM config entries for the same host/port/slave:

## Diagnostics requirements

- [ ] Diagnostics include transport source.
- [ ] Diagnostics include socket ownership.
- [ ] Diagnostics include shared-connection capability.
- [ ] Diagnostics remain redacted for host/IP/private identifiers.
- [ ] Repair issues keep user-friendly communication error messages.

## Migration requirements

- [ ] Existing config entries keep working without user action.
- [ ] Existing entities keep the same Unique IDs.
- [ ] Existing user-enabled/user-disabled entity registry choices are preserved.
- [ ] Fallback to the current Pymodbus path is documented if the HA shared connection is unavailable.

## Acceptance criteria for a future implementation PR

- [ ] The current Pymodbus path still passes tests.
- [ ] The shared-connection adapter is optional or guarded until upstream is stable.
- [ ] All platforms still route writes through `IdmCoordinator.async_write_register`.
- [ ] Fake transports cover both private-socket and shared-connection behavior.
- [ ] No real heat pump write tests are required for CI.
- [ ] Release notes explain the migration and fallback behavior.
