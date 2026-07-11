# Data Update

## How is data retrieved?

The integration uses Modbus TCP to read register data directly from the IDM heat pump. All communication is **local** — there is no cloud connection.

## Polling Mechanism

The integration uses Home Assistant's **DataUpdateCoordinator**:

- Modbus-backed entities share **one coordinated refresh** composed of multiple
  grouped Modbus requests
- Modbus registers are grouped only when their ranges are **exactly adjacent and non-overlapping**, up to 40 Modbus words per request
- Values outside declared enum or numeric metadata are re-read individually; confirmed problem registers stay in the individual-read path for the current client session
- Known `sentinel_values` such as `-1`, `254` or `255` mean unavailable/unused where declared by register metadata and are not treated as corrupt values
- The coordinator updates all entities simultaneously after each successful query
- Optional web supplement data uses a separate poll loop and starts slightly
  after Modbus polling, so both protocols do not hit the controller at exactly
  the same time.

## Configured Interval

The polling interval is **freely configurable** (5–300 seconds, default: 10 seconds):

- **Settings → IDM Heatpump → Configure → Polling interval**
- Shorter intervals provide faster updates but generate more network traffic
- Recommendation: 10–30 seconds for normal operation

Optional web supplement data has its own interval (default: 30 seconds). It is
only used when web supplement data is enabled and a local Navigator web PIN is
configured.

The successful Navigator 2.0 or Navigator 10/Pro web client is reused between
web polls. A failed or expired session is discarded and rebuilt with the same
known protocol. Both protocols are tested only while the variant is unknown or
when setup/reconfiguration/repair performs a fresh connection validation.

Room temperature forwarding, when enabled, is handled outside the normal read
poll. Selected Home Assistant temperature sensors are written to the matching
external room temperature registers on state changes and refreshed periodically
(default: 300 seconds).

## Entity Availability

An entity is marked as **unavailable** when:
- The connection to the heat pump is interrupted
- The Modbus register returns one of its declared unavailable sentinels (for example `-1.0`, `254` or `255` depending on that register)
- The "Hide unused sensors" option omits an already known unused entity during
  setup; an entity that later returns a declared sentinel becomes unavailable
- A web supplement sensor has no value in the latest successful web snapshot

## Write Operations (writable entities)

Number, Select, and Switch entities can write values to the heat pump:
1. The new value is displayed **optimistically** in the UI immediately
2. A full refresh is triggered afterwards to confirm the actual device state
3. **EEPROM-protected registers** may only be written once per minute to avoid hardware wear

## Error Handling

- On connection errors, a **repair issue** is automatically created in Home Assistant
- Once the connection is restored, the repair issue disappears automatically
- The DataUpdateCoordinator logs connection errors once (not on every failed cycle)
- Exhausted timeout/no-response failures abort the poll and trigger the normal repair flow; they never count as permanent failures of individual registers
- Unsupported optional addresses are isolated and skipped on later polls instead of failing all supported data
- Web supplement errors are logged separately and never abort the Modbus update
  path. A wrong PIN is reported directly during setup/reconfiguration.

## Room Temperature Forwarding

The optional room temperature forwarder writes Home Assistant sensor values to
the IDM external room temperature registers per active heating circuit. It uses
a default tolerance of 0.2 °C to avoid unnecessary repeated writes and skips
invalid, unavailable, non-numeric or out-of-range values.

Forwarding is disabled by default and only starts after at least one heating
circuit has a selected Home Assistant temperature entity in the integration
options.

## Technician Code Sensors

The optional technician code sensors update **independently** every 60 seconds via their own timer, since they are not Modbus register values but computed codes.
