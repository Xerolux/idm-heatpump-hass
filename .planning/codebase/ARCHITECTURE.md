<!-- refreshed: 2026-07-25 -->
# Architecture

**Analysis Date:** 2026-07-25

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Home Assistant config entries, services, entities, repairs          │
├──────────────────────┬──────────────────────┬────────────────────────┤
│ Setup and lifecycle  │ Entity platforms     │ Service/action paths   │
│ `custom_components/  │ `sensor.py`,         │ `services.py`,         │
│ idm_heatpump/         │ `climate.py`, etc.  │ `dhw_boost_services.py`│
│ __init__.py`          │                      │                        │
└──────────┬───────────┴───────────┬──────────┴────────────┬───────────┘
           │                       │                       │
           ▼                       ▼                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Shared runtime and state boundary: `IdmCoordinator`                  │
│ `custom_components/idm_heatpump/coordinator.py`                      │
├──────────────────────┬──────────────────────┬────────────────────────┤
│ Register catalog     │ Derived state        │ Optional web data      │
│ `registers.py` and   │ `operation_          │ `web_data.py` and      │
│ `library_adapter.py` │ analysis.py`         │ web sensor modules     │
└──────────┬───────────┴───────────┬──────────┴────────────┬───────────┘
           │                       │                       │
           ▼                       ▼                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Local device interfaces                                              │
│ `idm-heatpump-api` Modbus client + Navigator local web interface     │
└──────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Config-entry lifecycle | Connect clients, resolve model, construct descriptions/registers, create runtime data, load/unload platforms | `custom_components/idm_heatpump/__init__.py` |
| Configuration UI | Validate connection settings and gather options, zones, fallback mode, reconfiguration, and room forwarding | `custom_components/idm_heatpump/config_flow.py` |
| Coordinator | Poll registers, isolate unsupported addresses, merge web data, expose shared state, and serialize writes | `custom_components/idm_heatpump/coordinator.py` |
| Register adapter | Convert `idm-heatpump-api` register definitions to Home Assistant entity descriptions | `custom_components/idm_heatpump/library_adapter.py` |
| Register catalog | Assemble and sort model-, circuit-, zone-, and platform-specific descriptions and aliases | `custom_components/idm_heatpump/registers.py` |
| Entity base | Provide stable unique IDs, device info, availability, and unused-register behavior | `custom_components/idm_heatpump/entity.py` |
| Platforms | Translate coordinator state into Home Assistant entities and route user writes back through the coordinator | `custom_components/idm_heatpump/sensor.py`, `custom_components/idm_heatpump/climate.py`, `custom_components/idm_heatpump/number.py` |
| Optional web transport | Authenticate against local Navigator web variants, normalize responses, and pool clients | `custom_components/idm_heatpump/web_data.py` |
| Action orchestration | Implement guarded DHW boost lifecycle and service-facing actions | `custom_components/idm_heatpump/dhw_boost.py`, `custom_components/idm_heatpump/dhw_boost_services.py` |
| Derived operation state | Analyze raw values into cycle/runtime diagnostics and expose derived entities | `custom_components/idm_heatpump/operation_analysis.py`, `custom_components/idm_heatpump/operation_entities.py` |

## Pattern Overview

**Overall:** Home Assistant config-entry integration using an adapter layer and a central `DataUpdateCoordinator`.

**Key Characteristics:**
- Treat `IdmCoordinator` in `custom_components/idm_heatpump/coordinator.py` as the single runtime state and device-I/O boundary.
- Source register semantics from `idm-heatpump-api`; enrich them in `custom_components/idm_heatpump/library_adapter.py` rather than duplicating addresses in platform modules.
- Keep platform modules thin: select applicable descriptions, instantiate entities, read coordinator data, and delegate writes.
- Store per-entry resources in `IdmHeatpumpData` at `custom_components/idm_heatpump/__init__.py:149`, never in process-global mutable state.
- Keep all communication local: Modbus TCP and the optional Navigator web interface are the only device transports.

## Layers

**Home Assistant lifecycle layer:**
- Purpose: Own setup, migrations, runtime resource ownership, platform forwarding, reload, and unload.
- Location: `custom_components/idm_heatpump/__init__.py`
- Contains: `async_setup_entry`, `async_unload_entry`, web-only setup, model detection, background-task wiring.
- Depends on: config entry data/options, adapter/catalog modules, coordinator, Home Assistant helpers.
- Used by: Home Assistant integration loader.

**Configuration layer:**
- Purpose: Convert user input into stable config-entry data and options.
- Location: `custom_components/idm_heatpump/config_flow.py`
- Contains: user, options, zones, Modbus-failure fallback, reconfigure, and room-temperature forwarding steps.
- Depends on: `custom_components/idm_heatpump/const.py`, local connection probes, Home Assistant config-flow APIs.
- Used by: lifecycle setup in `custom_components/idm_heatpump/__init__.py`.

**Metadata and adaptation layer:**
- Purpose: Select supported library registers and convert them to Home Assistant descriptions.
- Location: `custom_components/idm_heatpump/registers.py`, `custom_components/idm_heatpump/library_adapter.py`, `custom_components/idm_heatpump/adapter_*.py`
- Contains: description factories, enum mappings, names, metadata, GLT classification, model filtering, alias maps.
- Depends on: `idm-heatpump-api` register definitions and model information.
- Used by: setup and every register-backed platform.

**Coordination and transport layer:**
- Purpose: Perform asynchronous reads/writes and publish a coherent state snapshot.
- Location: `custom_components/idm_heatpump/coordinator.py`, `custom_components/idm_heatpump/modbus_transport.py`, `custom_components/idm_heatpump/polling_plan.py`
- Contains: resilient polling, unsupported-register isolation, optimistic writes, transport capability adaptation, polling-plan state.
- Depends on: the adapted Modbus client and register catalog.
- Used by: entities, services, room forwarding, diagnostics, and operation analysis.

**Presentation and action layer:**
- Purpose: Present state through Home Assistant entities and invoke domain operations.
- Location: `custom_components/idm_heatpump/sensor.py`, `custom_components/idm_heatpump/binary_sensor.py`, `custom_components/idm_heatpump/number.py`, `custom_components/idm_heatpump/select.py`, `custom_components/idm_heatpump/switch.py`, `custom_components/idm_heatpump/climate.py`, `custom_components/idm_heatpump/water_heater.py`, `custom_components/idm_heatpump/button.py`, `custom_components/idm_heatpump/services.py`
- Contains: platform setup functions, entity subclasses, service handlers, validation.
- Depends on: coordinator state and shared helpers such as `custom_components/idm_heatpump/entity.py`.
- Used by: Home Assistant users and automations.

## Data Flow

### Primary Setup and Poll Path

1. Home Assistant invokes `async_setup_entry` and connection/options are read (`custom_components/idm_heatpump/__init__.py:513`).
2. Setup creates the adapted Modbus client, detects the Navigator family, and builds platform descriptions via `custom_components/idm_heatpump/registers.py`.
3. Setup constructs `IdmCoordinator`, stores it in `entry.runtime_data`, and requests the first refresh (`custom_components/idm_heatpump/__init__.py:861`, `custom_components/idm_heatpump/__init__.py:868`).
4. `_async_update_data` reads the catalog through resilient batching (`custom_components/idm_heatpump/coordinator.py:571`).
5. `_async_read_registers_resilient` bisects illegal-address failures so optional unsupported registers do not fail the whole update (`custom_components/idm_heatpump/coordinator.py:412`).
6. The coordinator publishes a dictionary snapshot and `CoordinatorEntity` listeners refresh their Home Assistant states.
7. Setup forwards the entry to all declared platforms (`custom_components/idm_heatpump/__init__.py:869`).

### Entity Write Path

1. A writable entity or service validates the requested Home Assistant value in its platform module, for example `custom_components/idm_heatpump/climate.py`.
2. The caller resolves a catalog `RegisterDef`; do not create a raw address in the platform.
3. The caller invokes `IdmCoordinator.async_write_register` (`custom_components/idm_heatpump/coordinator.py:900`).
4. The coordinator encodes and writes through the library/transport and applies the optimistic state update.
5. Coordinator listeners immediately update entity state; a later poll reconciles it with the device.

### Optional Web Supplement Path

1. Setup or the background web loop calls `async_read_web_supplement` in `custom_components/idm_heatpump/web_data.py:436`.
2. Web client factories try the appropriate local Navigator protocol, normalize metadata/sensors, and report authentication/transport failures.
3. `IdmCoordinator.async_refresh_web_supplement` merges the result independently of Modbus polling and raises repair issues without making Modbus entities fail.
4. `custom_components/idm_heatpump/sensor.py` and `custom_components/idm_heatpump/web_binary_sensors.py` expose normalized web values.
5. In web-only fallback, setup loads only the sensor platform (`custom_components/idm_heatpump/__init__.py:467`).

### Room Temperature Forwarding

1. `RoomTempForwarder` in `custom_components/idm_heatpump/room_temp_forwarding.py` subscribes to configured Home Assistant sensor states.
2. It coerces and tolerance-checks temperatures, resolves the circuit GLT register from the coordinator catalog, and delegates the write to the coordinator.
3. The config-entry lifecycle owns and cancels the forwarding task through `IdmHeatpumpData`.

**State Management:**
- `ConfigEntry.runtime_data` owns the coordinator, client, background tasks, and optional `OperationAnalysis`.
- `IdmCoordinator.data` is the authoritative current entity snapshot.
- Web supplement/model metadata lives on the coordinator and is persisted to config-entry data only for detection metadata.
- Service managers and forwarders are entry-scoped; avoid module-level shared mutable state.

## Key Abstractions

**`IdmHeatpumpData`:**
- Purpose: Typed ownership record for all resources associated with one config entry.
- Examples: `custom_components/idm_heatpump/__init__.py`
- Pattern: Config-entry runtime-data dataclass.

**`IdmCoordinator`:**
- Purpose: Central asynchronous state, refresh, repair-reporting, and write facade.
- Examples: `custom_components/idm_heatpump/coordinator.py`
- Pattern: Home Assistant `DataUpdateCoordinator[dict[str, Any]]`.

**`RegisterDef` plus entity descriptions:**
- Purpose: Carry address, encoding, permissions, names, aliases, and Home Assistant metadata through setup and runtime.
- Examples: `custom_components/idm_heatpump/library_adapter.py`, `custom_components/idm_heatpump/registers.py`
- Pattern: Library-owned domain metadata adapted at the integration boundary.

**`IdmCoordinatorEntityBase` / `IdmEntity`:**
- Purpose: Centralize device identity, unique ID, coordinator availability, aliases, and unused-register filtering.
- Examples: `custom_components/idm_heatpump/entity.py`
- Pattern: Shared entity inheritance; use `IdmEntity` for single-register Modbus entities.

**`IdmWebSupplement`:**
- Purpose: Normalize differing local Navigator web protocols into one optional data object.
- Examples: `custom_components/idm_heatpump/web_data.py`
- Pattern: Protocol adapter with best-effort enrichment.

## Entry Points

**Integration setup:**
- Location: `custom_components/idm_heatpump/__init__.py`
- Triggers: Home Assistant loads or reloads a config entry.
- Responsibilities: Create resources, perform first refresh, start background work, and load platforms/services.

**Configuration flow:**
- Location: `custom_components/idm_heatpump/config_flow.py`
- Triggers: User adds, reconfigures, or changes options for the integration.
- Responsibilities: Validate connection data and persist supported topology/options.

**Platform setup:**
- Location: `custom_components/idm_heatpump/sensor.py` and sibling platform modules.
- Triggers: `async_forward_entry_setups` from integration setup.
- Responsibilities: Select descriptions and add entry-scoped entities.

**Services:**
- Location: `custom_components/idm_heatpump/services.py`, `custom_components/idm_heatpump/dhw_boost_services.py`
- Triggers: Home Assistant service calls.
- Responsibilities: Resolve the target entry/coordinator, validate input and safety, execute writes/actions.

**Diagnostics and repairs:**
- Location: `custom_components/idm_heatpump/diagnostics.py`, `custom_components/idm_heatpump/repairs.py`
- Triggers: Diagnostic download or issue repair flow.
- Responsibilities: Export redacted runtime state and guide users through fixable configuration failures.

## Architectural Constraints

- **Threading:** Use Home Assistant's single asyncio event loop; device and web communication must remain asynchronous.
- **Global state:** Constants and immutable metadata may be module-level; per-device mutable state belongs in `IdmHeatpumpData` or `IdmCoordinator`.
- **Circular imports:** Platform and service modules may import the coordinator, but the coordinator must not import platform entity classes.
- **Register ownership:** Prefer `idm-heatpump-api` register definitions and adapter/catalog helpers; service-only exceptions belong in `custom_components/idm_heatpump/const.py`.
- **Local-only operation:** Do not add cloud services; `custom_components/idm_heatpump/web_data.py` targets the local Navigator interface.
- **Topology:** Model, circuits, zones, room count, and cascade options determine the catalog before entities are loaded.

## Anti-Patterns

### Direct Modbus Access from Entities

**What happens:** A platform calls the client or writes a literal Modbus address.
**Why it's wrong:** It bypasses coordinator locking, encoding, optimistic updates, alias propagation, safety behavior, and subsequent reconciliation.
**Do this instead:** Resolve a `RegisterDef` through `custom_components/idm_heatpump/registers.py` and call `IdmCoordinator.async_write_register` in `custom_components/idm_heatpump/coordinator.py`.

### Duplicating Library Register Metadata

**What happens:** Addresses, types, or writable ranges are copied into a platform module.
**Why it's wrong:** The integration and `idm-heatpump-api` can drift, causing incorrect reads or EEPROM-sensitive writes.
**Do this instead:** Adapt library metadata in `custom_components/idm_heatpump/library_adapter.py`; add presentation metadata in the appropriate `custom_components/idm_heatpump/adapter_*.py` helper.

### Platform-Specific Device Identity

**What happens:** Each entity constructs unrelated device info or unique IDs.
**Why it's wrong:** Entity migrations and device hierarchy become inconsistent.
**Do this instead:** Use `build_entity_unique_id` and `build_device_info` from `custom_components/idm_heatpump/entity.py`, plus hierarchy helpers in `custom_components/idm_heatpump/device_hierarchy.py`.

## Error Handling

**Strategy:** Distinguish setup, polling, web supplement, validation, and write failures while preserving available local functionality.

**Patterns:**
- Raise `ConfigEntryNotReady` from setup connection failures in `custom_components/idm_heatpump/__init__.py`.
- Convert refresh failures to coordinator update failures and create classified repair issues in `custom_components/idm_heatpump/coordinator.py`.
- Isolate Modbus illegal-address failures by recursively bisecting read sets.
- Treat web supplement errors as non-fatal when Modbus is healthy; retain Modbus state and surface repair issues.
- Raise translated `HomeAssistantError` or `ServiceValidationError` from user-triggered actions in `custom_components/idm_heatpump/services.py`.

## Cross-Cutting Concerns

**Logging:** Module loggers report lifecycle and classified communication events; `custom_components/idm_heatpump/log_filter.py` suppresses expected pymodbus disconnect noise.
**Validation:** Config-flow schemas live in `custom_components/idm_heatpump/config_flow.py`; service schemas live in `custom_components/idm_heatpump/services.yaml` with runtime checks in service modules.
**Authentication:** No cloud identity exists; optional local web access uses a user-supplied Navigator PIN handled by `custom_components/idm_heatpump/web_data.py`.
**Privacy:** Diagnostics redact connection details in `custom_components/idm_heatpump/diagnostics.py`.
**Device hierarchy:** Parent/child device placement is centralized in `custom_components/idm_heatpump/device_hierarchy.py`.

---

*Architecture analysis: 2026-07-25*
