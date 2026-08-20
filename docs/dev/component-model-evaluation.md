# The `modbus-connection` component model: evaluation

Last updated: 2026-08-19 · measured against `modbus-connection` 4.8.1 and
`idm-heatpump-api` 1.0.1 · reproducible with
`python scripts/evaluate_component_model.py`

## Question

With v4.0.0-pre.11, solaredge-modbus-multi moved all of its reads and writes
onto a `modbus-connection` `Component`. The equivalent step for this project
would happen in `idm-heatpump-api`, which owns the register map, the batching
and the decoding. The integration itself would carry noticeably less code
afterwards — the transport contract and the error translation in
`modbus_transport.py` would largely become redundant, because the library takes
over planning and decoding.

## Result

**Do not implement.** Not because the register map does not fit — it fits
completely — but because the library's read planning collides with the protocol
invariants of the official IDM register map.

## What was measured

Against the maximally equipped Navigator 10 map (7 heating circuits, 10 zone
modules, solar/ISC/PV/cascade active), 586 readable data points:

| Check | Result |
| --- | --- |
| Registers mappable onto library fields | 586 of 586, no special case left open |
| Decoded values against `idm-heatpump-api` | 0 deviations |
| Requests per poll, today's API batching | 57 |
| Requests per poll, library planning `max_gap=1` | 42 |
| Requests per poll, library planning `max_gap=16` (default) | 24, at the price of 98 words from addresses no data point claims |

The dynamic register map is not an obstacle: `ManualComponent` accepts fields at
runtime, so heating circuits and zone rooms can be generated exactly as they are
today. IDM `FLOAT` (IEEE-754, low word first) maps exactly onto
`float32(..., word_order="little")`; the multiplier becomes the field's `scale`.

## The blocker

`docs/Register-Map-Invariants.md` in `idm-heatpump-api` records three rules that
come from the official IDM documentation and from hardware captures:

- Batching is strictly adjacent only: `next.address == previous.address +
  previous.size`. Gaps are never skipped.
- The official map contains documented logical overlaps — humidity
  `1392 FLOAT` and heating circuit A mode `1393 UCHAR`, heating curve G
  `1441 FLOAT` and heating limit A `1442 UCHAR`, cooling eco setpoint G
  `1483 FLOAT` and cooling limit A `1484 UCHAR`.
- Every overlapping data point is requested **individually**, with its
  documented start address and size. These values are request-sensitive: the
  same address returns either part of a float or a standalone UCHAR value,
  depending on the exact request.

The library's planning, by contrast, works purely on address spans
(`_plan_blocks`: merge while `address - block_end <= max_gap`) and then decodes
all fields out of the block it read. Measured:

```
humidity_sensor + hc_a_mode:                 [(1392, 2)] -> ONE merged request
hc_g_heating_curve + hc_a_heating_limit:     [(1441, 2)] -> ONE merged request
hc_g_room_setpoint_cool_eco + hc_a_cooling_limit: [(1483, 2)] -> ONE merged request
```

Exactly those three data points would therefore take their value from the second
word of the neighboring float instead of from their own documented request. The
mock does not show this — the mock is not request-sensitive — but on the device
it is a wrong value.

Falling back to `max_gap=0` does not solve it: the library then merges nothing at
all, not even directly adjacent fields, and the poll falls apart into 583
individual requests instead of 57. And `max_gap >= 2` additionally violates the
first rule, because addresses the documentation does not describe are read along
with the block — on a controller that answers unknown addresses with exception
code 2 for the whole block, that costs the entire block.

## What this does not mean

- The rest of `modbus-connection` stays exactly what the integration uses:
  connection, serialization, reconnect, pacing, typed errors. This evaluation
  only concerns the modeling and planning module (`modbus_connection.model`).
- The 42 instead of 57 requests at `max_gap=1` are not an argument for the
  migration: the saving comes from the library merging up to 125 words per
  block, while the API cuts at 40 words (`_MAX_GROUP_SIZE`). The same saving
  would be available inside the API without giving up the overlap rule — but
  only with hardware evidence that the controller answers blocks above 40 words
  reliably.

## When to re-evaluate

As soon as `modbus-connection` offers planning that can pin a data point to an
exact request (that is, "never merge this field with another block", or explicit
knowledge of request-sensitive data points). The blocker then disappears and the
migration becomes a pure question of effort in `idm-heatpump-api` 2.0.
`scripts/evaluate_component_model.py` measures the situation again.
