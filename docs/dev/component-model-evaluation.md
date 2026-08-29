# The `modbus-connection` component model: evaluation

Last updated: 2026-08-29 · measured against `modbus-connection` 4.10.0 and
`idm-heatpump-api` 2.0.0 · reproducible with
`python scripts/evaluate_component_model.py`

Re-measured on the current pins after the 4.8.1 → 4.10.0 move. Every figure
below reproduced unchanged, so the verdict stands for 4.10.0.

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
| Requests per poll, library planning `max_gap=0` | 583 — and still 3 merges, see below |
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

Falling back to `max_gap=0` does not solve it, and it fails in the worst
possible way. It does not, as one would expect, stop merging: across the whole
586-register map it still performs **exactly three merges — precisely the three
that must never happen**:

```
humidity_sensor + hc_a_mode:                      [(1392, 2)] -> MERGED
hc_g_heating_curve + hc_a_heating_limit:          [(1441, 2)] -> MERGED
hc_g_room_setpoint_cool_eco + hc_a_cooling_limit: [(1483, 2)] -> MERGED

whole map at max_gap=0: 583 blocks for 586 registers -> exactly 3 merges
```

The reason is that these fields do not merely sit next to each other, they
*overlap*: the UCHAR shares an address with the float's high word, so the gap
between them is not 1 but 0, and no gap threshold can separate them. `max_gap=0`
therefore buys the worst of both — it gives up all legitimate batching (583
requests instead of 57) and still returns three wrong values.

`max_gap >= 2` additionally violates the first rule, because addresses the
documentation does not describe are read along with the block — on a controller
that answers unknown addresses with exception code 2 for the whole block, that
costs the entire block.

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
knowledge of request-sensitive data points). 4.10.0 still has no such option —
the only planning knobs are `max_gap`, `max_span` and `register_ranges`.

`register_ranges` looks like a way out, because with declared ranges the planner
merges only *within* a range, so a range boundary between the two data points
would separate them. It is not: the fields overlap on a shared address, so a
boundary drawn between them leaves the float straddling two ranges, and planning
rejects that outright.

```
_plan_blocks([(1392, 2), (1393, 1)], ((1392, 1392), (1393, 1393)))
ValueError: a field at address 1392 spanning 2 registers (1392-1393)
            does not fit inside a readable range
```

That is the structural core of the blocker: the model assumes one address holds
one value, decoded out of a shared block. The IDM map breaks that assumption at
exactly three points, and no planner setting can express it — only a per-field
"read this on its own" contract can. Once that exists the blocker disappears and
the migration becomes a pure question of effort in `idm-heatpump-api`.
`scripts/evaluate_component_model.py` measures the situation again.
