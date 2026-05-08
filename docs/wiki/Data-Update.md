# Data Update

## How is data retrieved?

The integration uses Modbus TCP to read register data directly from the IDM heat pump. All communication is **local** — there is no cloud connection.

## Polling Mechanism

The integration uses Home Assistant's **DataUpdateCoordinator**:

- All entities share **one common query** per polling cycle
- Modbus registers are read in **batches of up to 30 consecutive addresses** to minimize the number of network requests
- The coordinator updates all entities simultaneously after each successful query

## Configured Interval

The polling interval is **freely configurable** (5–300 seconds, default: 10 seconds):

- **Settings → IDM Heatpump → Configure → Polling interval**
- Shorter intervals provide faster updates but generate more network traffic
- Recommendation: 10–30 seconds for normal operation

## Entity Availability

An entity is marked as **unavailable** when:
- The connection to the heat pump is interrupted
- The Modbus register value returns the sentinel value `-1.0` (unused/inactive register)
- The "Hide unused sensors" option is enabled

## Write Operations (writable entities)

Number, Select, and Switch entities can write values to the heat pump:
1. The new value is displayed **optimistically** in the UI immediately
2. A full refresh is triggered afterwards to confirm the actual device state
3. **EEPROM-protected registers** may only be written once per minute to avoid hardware wear

## Error Handling

- On connection errors, a **repair issue** is automatically created in Home Assistant
- Once the connection is restored, the repair issue disappears automatically
- The DataUpdateCoordinator logs connection errors once (not on every failed cycle)

## Technician Code Sensors

The optional technician code sensors update **independently** every 60 seconds via their own timer, since they are not Modbus register values but computed codes.
