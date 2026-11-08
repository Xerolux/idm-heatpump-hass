# Live validation: shared Modbus connection (2026-11-08)

Maintainer-authorized read-only session on the reference plant (Navigator 10,
firmware `T_NAV10_20.24-1580-g02a20b66f`, heating circuits A and D, solar/ISC/PV
detected). Everything ran through the Docker read-only bench
(`docker/live-readonly-test`) on integration `0.26.10`, API wheel built from
the pinned `2.16.1` source, Home Assistant `2026.11.0`. This record closes the
"shared-connection field validation" item of the open-work audit; no private
addresses, PINs or plant identifiers are recorded.

## Transport claim under test

`modbus_shared_transport.py` claims a unit on Home Assistant's shared Modbus
connection (`modbus.async_get_unit`, HA ≥ 2026.10) instead of a private
socket. Before this session the provider had never run against a live
controller.

## Observed results

| Check | Result | Evidence |
|---|---|---|
| Shared claim on live plant | Redacted diagnostics report `transport.capabilities.source = "homeassistant.modbus"`, `owns_socket = false`, `supports_shared_connection = true`, `connected = true` | `results/diagnostics.json` export of the session |
| Ordinary polling through the shared link | Continuous Modbus + Web operation; e.g. 11 polls, 0 failures in one window; poll duration ≈ 2.5 s for 77 active registers | Diagnostics `communication` section |
| Web supplement through the RO proxy | Nav10 WebSocket alive after the proxy read-allowlist was aligned with the pinned API's read frames: 73 live web values (hot gas, pressures, per-circuit flow/room temperatures, software version, demand reason), connection mode "Modbus + Web" | Entity states + `web_supplement.available_values` |
| Deliberate Modbus disconnect, single holder | `docker compose restart modbus-proxy` mid-poll: no entity-availability dip (24/240 unavailable before and after, unchanged), tmodbus re-established the link, polls continued with 0 consecutive failures | Session log, `docker logs`, recovery observation script |
| Deliberate disconnect with a second holder | Core `modbus` integration configured on the same endpoint (`sensor.second_holder_probe`, holding register 4108): both holders survived the same restart without any unavailability window; the second holder kept reading immediately after | Session log around the two-holder cut |
| Read-only proof | 4,113 Modbus frames relayed with exactly 2 blocked — the two synthetic write-block verifications of `run_api_tests.py` (FC06 and Nav10 `setting/save`); 778 WS frames relayed, 0 blocked after the allowlist fix | `logs/modbus-proxy/*_blocked_writes.jsonl`, `logs/web-proxy/ws_blocked_writes.jsonl` |
| Web climate cards | Both heating-circuit climate entities live (target 20.5 °C, current 20.7/21.6 °C) through `system.heatingcircuit/detail` reads | Entity states |
| Write-block regression | All 11 isolated api-tests pass on the live plant, including `proxy_write_block_verification` and `nav10_ws_write_block_verification` | `results/api_test_report.json` |

## Bench defects found and fixed during the session

These are test-bench bugs, not integration bugs — each was caught precisely
because the bench enforces its guarantees:

1. **Proxy logging could crash the proxy**: an unwritable log directory (fresh
   Linux bind mount) made `_append_line` raise, breaking HTTP requests and
   taking the proxy process down — and with it the write-block proof. All
   three proxies now fall back to stdout instead of raising; enforcement never
   depends on file logging.
2. **WS read allowlist was stale**: it allowed only the three core read
   commands of an older API. The pinned 2.16.1 client also sends
   `home/detail`, `home/overview`, `status/overview`, `system`,
   `system.freshwater`, `system.heatpump.performance`, `weather`, `ion`,
   `energyflow` and per-circuit `system.heatingcircuit/detail` reads — all
   documented read frames. The allowlist now matches the pinned client
   exactly; `save` (the protocol's write verb) stays blocked and unknown
   commands stay blocked by default.
3. **`ha_probe.py` used the removed `grant_type=password`**: HA 2026.11
   rejects it. The bootstrap probe now drives the login-flow/auth-code
   exchange.
4. **Linux bind-mount permissions**: the uid-1000 containers could not write
   into root-owned `results/`/`logs/`. `start.sh` prepares the mounts, and the
   logging fallback (1) makes the failure mode harmless anyway.

## Boundaries

- Single plant, single session (~1 h): no fleet claim and no long-run soak.
- The second holder is the core `modbus` integration reading one holding
  register — enough to exercise reference counting and link sharing, not a
  load test.
- Web PIN login passed through the proxy; the PIN itself never entered any
  repository artifact (bench `.env` is gitignored; diagnostics are redacted).
- COP reconciliation for DHW charges and defrost cycles is recorded in a
  parallel read-only series and remains open until that data covers both
  operating states.

## Artifacts (bench host, not committed)

`results/diagnostics.json`, `results/api_test_report.json`,
`results/entity_export.json`, `results/bootstrap_report.json`,
`logs/*/` proxy JSONL logs, `/root/test-results/cop_series.csv`.
