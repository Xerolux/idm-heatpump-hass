# Synthesized Technical Constraints

## Model-gated register schema

source: docs/wiki/Modbus-Register.md

- Type: schema
- Constraint: `idm-heatpump-api` is the authoritative machine-readable register schema. The active map is derived from detected Navigator family, heating circuits, zones/rooms, and optional Solar, ISC, PV, and cascade capabilities.
- Required metadata: address, datatype, access flags, write class, source and version, supported models, sentinel values, and optional verification label.
- New registers must originate in the API schema rather than ad-hoc Home Assistant code.

## Modbus transport and datatype contract

source: docs/wiki/Modbus-Register.md

- Type: protocol
- Constraint: Use Modbus TCP, normally port 502 and slave ID 1. Input registers use FC04, holding registers use FC03, and writes use FC16.
- Supported datatypes: FLOAT (IEEE 754, two words, low word first), UCHAR, INT8, UINT16, INT16, BOOL, and BITFLAG.
- Integer writes apply the register multiplier and rounding defined by library metadata.

## Zone register layout

source: docs/wiki/Modbus-Register.md

- Type: schema
- Constraint: Zone bases are 2000, 2065, 2130, 2195, 2260, 2325, 2390, 2455, 2520, and 2585 for zones 1 through 10.
- Each module spans 65 addresses. Rooms begin at `base + 2`, occupy seven addresses, and support up to eight configured rooms; six is the current Navigator 10 default.

## Cyclic and EEPROM write safety

source: docs/wiki/Modbus-Register.md

- Type: nfr
- Constraint: Register 1999 must not be written permanently. BMS heat and cooling request registers 1696 and 1698 require cyclic writes every ten minutes.
- Eighty-eight EEPROM-sensitive registers have limited write cycles and require integration-level protection or warnings against frequent writes.
- Unknown raw addresses have no inferable range, EEPROM behavior, or semantics.

## Register validation and batching

source: docs/wiki/Modbus-Register.md

- Type: nfr
- Constraint: Model-specific registers must be capability-gated; sentinels are contextual and documented enum values take precedence over generic unavailable values.
- Batches may contain only exactly adjacent, non-overlapping logical ranges and are limited to 40 Modbus words.
- Real-device deviations require compatibility notes and regression tests before support is advertised.

## External energy-manager and PV datatype contract

source: docs/wiki/Modbus-Register.md

- Type: api-contract
- Constraint: Avoid multiple writers for GLT/PV input registers and identify the owning system before automation.
- Addresses 74, 76, 78, 82, 84, and 88 are word-swapped FLOAT values where supported. Address 86 is a one-register signed INT16 battery percentage; `-1` means unavailable.
- Generated entities or library definitions must be preferred because the raw-write action cannot infer datatype from an address.

## Writable entity contract

source: docs/wiki/Services.md

- Type: api-contract
- Constraint: Prefer generated `number`, `select`, and `switch` entities for writes so datatype, value range, model availability, and EEPROM/cyclic metadata remain enforced.
- Use direct register writes only when no suitable entity exists and the caller explicitly accepts the risk.

## `set_system_mode` action contract

source: docs/wiki/Services.md

- Type: api-contract
- Constraint: `idm_heatpump.set_system_mode` targets an integration entity and requires a `mode` selection.
- Documented modes are Standby, Auto, Away, Holiday, DHW Only, and Heating/Cooling Only.

## `acknowledge_errors` action contract

source: docs/wiki/Services.md

- Type: api-contract
- Constraint: `idm_heatpump.acknowledge_errors` targets an integration device and acknowledges or clears active heat-pump errors.

## `write_register` action contract

source: docs/wiki/Services.md

- Type: api-contract
- Constraint: `idm_heatpump.write_register` targets an integration device and accepts address 0–10000, a value, datatype (`uint16`, `int16`, `float`, `uchar`, or `bool`), and `acknowledge_risk: true`.
- `uint16` is the default datatype. Non-numeric or unrepresentable values must be rejected before network I/O.
- Encoding validation does not establish whether an unknown address, range, enum, EEPROM behavior, or semantic meaning is safe.
