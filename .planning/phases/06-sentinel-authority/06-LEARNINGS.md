---
phase: 06
phase_name: "sentinel-authority"
project: "IDM Heatpump 0.8.7 — Sentinel Authority in API"
generated: "2026-07-26"
counts:
  decisions: 3
  lessons: 2
  patterns: 2
  surprises: 1
missing_artifacts:
  - VERIFICATION.md
  - UAT.md
---

# Phase 06 Learnings: sentinel-authority

## Decisions

### Datatype-based defaults via a computed property, not `__post_init__` mutation
`effective_sentinel_values` is a property: explicit `sentinel_values` win, else
the datatype default. This keeps the field backward-compatible and avoids a
3-state "unset/default/opt-out" marker.

**Rationale:** the field already existed and was consumed; the property adds
authority without a dataclass migration.
**Source:** 06-01-PLAN.md

### Enum state wins over the sentinel default
A value listed in a register's `enum_options` is shown as a documented state,
even if it equals a datatype sentinel (e.g. 255 = "Not configured" in an enum).

**Rationale:** preserves the established "documented enum values are valid
states" semantics after the universal heuristic was removed.
**Source:** 06-02-SUMMARY.md

### Pump-status `-1` opt-out moved to the API
The 10 pump-status registers now declare `sentinel_values=(-32768, 65535, 255)`;
`-1` stays valid ("off"). The integration's `NEGATIVE_ONE_VALID_REGISTERS` list
is no longer evaluated.

**Rationale:** the API owns register semantics; device-specific exceptions
belong with the register declaration, not the consumer.
**Source:** 06-01-SUMMARY.md

---

## Lessons

### The integration test suite ran against a stale installed API
`conftest.py` only stubs `RegisterDef` when the real library is absent; the
global env had `idm-heatpump-api` 0.8.4 installed, so the new
`effective_sentinel_values` was invisible until an editable install of the
current source.

**Context:** caused the first full-suite run to regress 11 tests after the
coordinator change.
**Source:** 06-02-SUMMARY.md

### Tests that passed a placeholder register name ("x") hid a register-lookup gap
The old heuristic ran even when the register was unknown; the authoritative
model requires a real register to resolve sentinels.

**Context:** forced reworking `TestIsRegisterUnused` to use explicit registers
per datatype — a cleaner, more honest test surface.
**Source:** 06-02-SUMMARY.md

---

## Patterns

### Authority property + datatype default table
For any "value means X" classification, prefer a property that resolves
explicit-per-instance → datatype-default → empty, so consumers have one
authoritative accessor and never fall back to literals.

**When to use:** Replacing a consumer-side numeric heuristic with a
data-driven declaration.
**Source:** 06-01-SUMMARY.md

### Mirror API computed fields in the integration test stub
When the integration stubs the library's dataclass, every computed property the
integration reads must be mirrored in the stub, or tests silently exercise the
wrong code path.

**When to use:** Integration tests that stub a library dataclass.
**Source:** 06-02-SUMMARY.md

---

## Surprises

### Authoritative sentinels exposed a few registers that the old heuristic over-hid
Moving from the universal `-1/255/65535` check to datatype-specific defaults
made 3 more entities available on the live device (146 → 149).

**Impact:** a small, favorable behavior change; verified no `hide_unused`
regression and #172 writable targets preserved.
**Source:** 06-02-SUMMARY.md
