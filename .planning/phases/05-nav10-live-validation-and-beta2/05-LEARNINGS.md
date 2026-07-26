---
phase: 05
phase_name: "nav10-live-validation-and-beta2"
project: "IDM Heatpump Reliability Bugfixes"
generated: "2026-07-26"
counts:
  decisions: 4
  lessons: 4
  patterns: 4
  surprises: 3
missing_artifacts:
  - VERIFICATION.md
  - UAT.md
---

# Phase 05 Learnings: nav10-live-validation-and-beta2

## Decisions

### Read-only enforcement is a network-layer concern, not a discipline concern
The three proxies (Modbus FC01–04, HTTP GET/HEAD + login POST, Nav10 WS
read-commands) intercept writes before the LAN, so no test discipline or code
guard can bypass them.

**Rationale:** The original brief required a technical read-only lock that does
not rely on human discipline; only a transparent proxy can prove "no write
reached the device" from independent logs.
**Source:** 05-01-PLAN.md

### Navigator 10 detection needs a register-block presence signal, not a value
The strict tertiary indicator requires BOTH Nav10-only registers 4122 and 4126 to
respond (any value, including 0.0); a single responding register is not enough.

**Rationale:** 4108 (power_limit_hp) is unplausible in standby and 4001
(booster_fault) is legitimately 255 without a booster, so neither value alone is
family-specific. Register-block presence is rejected by Navigator 2.0 / Terra SWM
with Modbus Exception 2, making it a safe discriminator.
**Source:** 05-01-SUMMARY.md

### Pin the exact local API build into the HA image
The local `idm-heatpump-api` wheel is force-installed in the HA image so Home
Assistant's requirement check is satisfied and it never fetches an older PyPI
build during the test.

**Rationale:** The brief forbade testing against an unnoticed published/cached
older version; HA's constrained pip resolver also cannot upgrade pymodbus at
runtime, so pymodbus is pinned in the image too.
**Source:** 05-01-PLAN.md

### Keep `hide_unused_registers`; do not remove it
Removing the option would not eliminate the #172 risk (already fixed for
writable targets) and would flood the entity list with `unavailable` read-only
sentinel registers, since availability is sentinel-gated independently of the
create gate.

**Rationale:** The concrete bug was "writable targets were caught by the filter",
not "the filter exists". The longer-term improvement is moving sentinel
definitions into the API as declared `sentinel_values`.
**Source:** 05-01-SUMMARY.md

---

## Lessons

### A tightening fix can remove a real device's only detection path
The 0.8.5 booster_fault sentinel fix was correct for Terra SWM but silently
dropped booster-less standby Navigator 10 controllers to Navigator 2.0.

**Context:** The 0.8.5 compatibility note already flagged the trade-off, but no
field evidence existed until this live test reproduced it.
**Source:** 05-01-SUMMARY.md

### Onboarding + token creation is the fragile part of HA automation
HA's onboarding must be reset fully (`auth` + `auth_provider.homeassistant` +
`onboarding` + `person`), with HA stopped, otherwise the user-recreation step
returns 500; the long-lived-token WS command is `auth/long_lived_access_token`,
not `long_lived_access_token/create`; config-entry reload is REST, not WS.

**Context:** Each of these cost a debugging cycle during the bootstrap probe.
**Source:** 05-01-SUMMARY.md

### The Nav2.0 HTTP web client cannot target a non-default port
`_format_url_host` rejects `host:port`; the web proxy must listen on port 80
internally so `web_host` resolves for both Nav2.0 HTTP and Nav10 WS (61220).

**Context:** Forced the web-proxy to run HTTP(80) + WS(61220) in one container.
**Source:** 05-01-PLAN.md

### A "model consistency" probe result of conflict is a success, not a failure
Detecting the Modbus/Web disagreement is the desired outcome of the check; the
conflict itself is the documented finding.

**Context:** Initially scored as a test failure, which masked a clean 11/0/0 run.
**Source:** 05-01-SUMMARY.md

---

## Patterns

### Read-only proxy with synthetic write-block verification
For each transport, allow only read function codes/methods/commands, return a
loud exception on writes, log to `*_blocked_writes.jsonl`, and prove the block
with one synthetic attempt whose value equals the just-read value (no-op even
hypothetically).

**When to use:** Any live device test that must provably not mutate state.
**Source:** 05-01-PLAN.md

### Strict register-block discriminator for model detection
When a value-bearing indicator (4108/4001) can be legitimately unset on the real
target family, add a "does this whole register block respond?" check using
registers known to be rejected by the other family.

**When to use:** Model/family detection that risks misclassification across
overlapping register echoes.
**Source:** 05-01-SUMMARY.md

### Preseed `core.config_entries` instead of driving a sectioned config flow
Writing a valid `core.config_entries` storage entry (version 1, minor 3) avoids
the multi-step sectioned options flow and is deterministic for automated HA
bring-up.

**When to use:** Automated HA bring-up against a known integration.
**Source:** 05-01-PLAN.md

### Identity tokens written raw, structured reports as JSON
Long-lived access tokens must be written without JSON quoting; reports are JSON.
Separate `_save_raw` from `_save`.

**When to use:** Mixing bearer-token files and JSON reports in one probe.
**Source:** 05-01-SUMMARY.md

---

## Surprises

### The test device is a Navigator 10, not a Navigator 2.0
The HTTP web title `NAV 10` and the WebSocket on 61220 were the give-away; the
Modbus detection said `Navigator 2.0`.

**Impact:** Turned a "verify the fix" run into a regression discovery + root-cause
fix.
**Source:** 05-01-SUMMARY.md

### `power_limit_hp` (4108) returns a tiny denormal in standby
raw `[0, 49024]` decodes to ≈ -1.75e-38, which is neither a plausible value nor a
recognised sentinel, so both the old and new logic skip it.

**Impact:** Required the 4122/4126 fallback; also leaves `leistungsbegrenzung_*`
unavailable (deferred).
**Source:** 05-01-SUMMARY.md

### Home Assistant 2026.7 no longer supports the password grant
`_login_existing` via `grant_type=password` returns `unsupported_grant_type`; only
the onboarding authorization-code flow or a long-lived token works.

**Impact:** Forced a full auth reset + fresh onboarding instead of a re-login.
**Source:** 05-01-SUMMARY.md
