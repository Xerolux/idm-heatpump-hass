# WebSocket-first roadmap — the Navigator 10/Pro local web API as a first-class data path

Status: 2026-09-27 · Maintainer: Xerolux · Audience: an AI assistant or developer

> **Implementation status 2026-09-28 (branch `feat/ws-first`, integration +
> API branch `feat/ws-read-expansion`):** Phase 1 (connection mode incl. the
> full detection summary — the diagnostics `connection` block also reports
> `jsonVersion`, userlevel and the controller clock), Phase 2
> (statistic/freshwater/status reads, API 2.7.0) and the Phase 3 capture tool
> (`scripts/ws_capture.py`, live-verified) are implemented with full gates.
> The Phase 2.1 blocker is resolved: the `statisticType`/`periodType` values
> were confirmed frame by frame read-only on the maintainer's Navigator 10.
> The **read half of the level-0 settingId catalog is enumerated** (2016 IDs
> probed read-only: eight answering IDs, three error classes — see the
> protocol wiki page), and concurrent WS sessions were verified by
> observation (live HA poll plus parallel sessions on one controller). Still
> open: the Phase 3 **capture session** is now a *confirmation* step only:
> the complete write surface (home/save systemMode with the live-confirmed
> Modbus-compatible mode values, setting/save + source:"Display",
> notification/save quitAll/code, system.freshwater/heatingcircuit/
> ventilation parameterId writes, room, ion, status) is reconstructed
> statically from the SPA bundle the controller serves over HTTP — see the
> protocol wiki page. The one remaining unknown is the save *response*
> frame shape. Then Phase 4 write PRs per feature and Phase 5.
picking this work up **cold** — this document is self-contained, but it expects
you to have read both repositories' `AGENTS.md` first.

Related documents you must know about:

- [`AGENTS.md`](../../AGENTS.md) — the integration's binding work rules.
- [`docs/dev/heatpump-feature-roadmap.md`](heatpump-feature-roadmap.md) — the
  older, broader roadmap (mostly completed; Modbus-centric).
- [`docs/dev/code-audit-2026-09.md`](code-audit-2026-09.md) — the defect and
  cleanup work packages. Do not mix refactoring packages into feature PRs.
- [`docs/wiki/Navigator-Protocol-Analysis.md`](../wiki/Navigator-Protocol-Analysis.md)
  (+ German mirror) — the deep protocol documentation. Everything there is
  confirmed knowledge; extend it, never contradict it silently.
- API repository `AGENTS.md`, `docs/API-Contract.md`, `docs/RELEASE_PROCESS.md`.

## 1. Repositories and artifacts

| What | Where |
|---|---|
| HA custom integration | https://github.com/Xerolux/idm-heatpump-hass (this repo) |
| Device library (PyPI) | https://github.com/Xerolux/idm-heatpump-api · https://pypi.org/project/idm-heatpump-api/ |
| Wiki / website | `docs/wiki/` (EN) + `docs/wiki/de/` (mirror), published to GitHub Pages |
| Releases (integration) | SemVer tags `v0.20.0-b2` style; HACS reads `manifest.json` |
| Releases (API) | PEP 440 tags `v2.6.0`; **two workflow dispatches** (Release, then Publish), then verify PyPI |
| Current versions | Integration **0.20.0-b2** (prerelease; latest stable 0.19.0) · API **2.6.0** |
| Runtime pins | `modbus-connection==4.12.2`, `tmodbus[async-serial]==0.6.2`, `idm-heatpump-api[web]==2.7.0`, HA ≥ 2026.8.1, Python 3.14 |

## 2. Where the integration stands today

### 2.1 Architecture in one paragraph

Modbus TCP (port 502, slave 1) is the **base path**: model detection, register
telemetry, and *all* writes. The **local web supplement** is an optional,
strictly **read-only** enrichment (and a fallback): Navigator 10 and Pro speak
a JSON WebSocket on port 61220, Navigator 2.0 an old HTTP/PHP interface on
port 80. When Modbus is unavailable but a local web PIN is configured, the
integration runs in a **web-only fallback mode**. There is no cloud anywhere.

Data flow: `IdmCoordinator` (coordinator.py) polls registers through
`IdmModbusConnectionClient` (modbus_client.py, subclasses the API client) →
`ModbusConnectionTransport` (modbus_transport.py, modbus-connection + tmodbus).
The optional `IdmWebSupplement` (web_data.py) polls web clients built by the
API (`create_optional_navigator10_web_client` / `…navigator20…`), default
every 30 s (`DEFAULT_WEB_SCAN_INTERVAL`, const.py), with a client pool and
per-variant detection (`_NAV10_VARIANTS`, `_preferred_web_variant`).

### 2.2 Key modules for this roadmap

| Concern | File(s) |
|---|---|
| Web supplement orchestration | `web_data.py` |
| Web-derived sensors / binary sensors | `sensor.py` (`_WEB_VALUE_NAMES`), `web_binary_sensors.py` |
| Demand-reason decode | `web_demand_reason.py`, `web_demand_reason_entities.py` |
| Poll orchestration (Modbus + web) | `coordinator.py` |
| Entity-aware Modbus poll narrowing | `polling_plan.py` |
| Config flow, options, web-only fallback | `config_flow.py`, `__init__.py` |
| Model/variant resolution | `model_resolution.py` |
| Error-code decoding (new in 0.20.0-b2) | `internal_messages.py`, `sensor.py` |
| Entity naming pipeline | `entity_names.py` (`ENGLISH_NAMES`/`DERIVED_NAMES`) + `adapter_names.py` (German source of truth) + `scripts/generate_entity_translations.py` |

### 2.3 What the WebSocket is used for today (API `web.py`)

Only **read** commands, only four controllers:

1. `setting/detail` with `data: {"settingId": …}` for the default IDs
   `("4768", "4775", "4782", "4789", "4754", "13259")`. Responses carry HTML
   tables, parsed by `SENSOR_NAME_MAP` and `NAVIGATOR10_SETTING_NAME_MAP`
   (keyed `(settingId, code)`, e.g. `("4789", "M31")`).
2. `notification/overview` — device messages with texts.
3. `home/detail` — per-widget demand reasons (bit tables verified on
   jsonVersion 11, September 2026) plus PV/grid energy-flow values.
4. `statistic/detail` — **implemented in the API (`read_statistics`) but never
   called by the integration**. Parses `statisticDetail.data.total` and
   `statisticDetail.data.yearly[-1]`.

`status/overview` is never sent (authorization is inferred from the first
frame). No `save`/`execute` command exists anywhere in the library — the web
clients are read-only by design.

### 2.4 The error-code database (API 2.6.0, integration 0.20.0-b2)

`idm-heatpump-api` ships `error_codes.json` (2005 vendor codes, decoded from
the Windows service tool configuration) with `get_error_code_info(code) ->
ErrorCodeInfo` (fields: `is_warning`, `text` = affected component, `info` =
error kind, `user_description`, `service_description`; `display_text` joins
component + kind exactly like the controller display). Numbering: `0` = no
error, `20..999` = the namespace the Modbus `internal_message` register
reports (validated one-to-one against the integration's curated table),
`10000+` = device-side error blocks. Texts are German only. The integration
decodes unknown `internal_message` codes through it and formats the Navigator
1.x `error_number` register the same way; the 1.x numbering is assumed, not
validated — field feedback is requested in the changelog.

### 2.5 Quality gates (both repos — CI enforced, run locally before pushing)

Integration: `pytest tests/` (coverage ≥ 95 % overall, **100 % for
`config_flow.py`**), strict mypy against real HA via the `test_ha/` venv
(recreate per `AGENTS.md`), ruff check + format (**CI installs the newest
ruff — format with the latest version or CI fails**), hassfest, HACS
validation, real-HA smoke tests (`tests_ha/`, genuine HA in a temp dir),
CodeQL, pip-audit. Docs must be English
(`scripts/check_documentation_language.py`); every wiki page change needs the
German mirror in the same PR.

API: pytest (coverage ≥ 75 %), ruff, strict mypy, the **public-API snapshot
test** (`tests/test_public_api.py` — extend it whenever you export anything
new), a compatibility-matrix entry per version
(`docs/compatibility-matrix.json`), `docs/API-Contract.md`, changelog in PEP
440 headings.

### 2.6 Release mechanics

- Integration: merge PR to `main` (never push directly), tag `v0.20.0-b3`
  style; the Release Management workflow validates tag/manifest/CHANGELOG,
  builds the ZIP and announces in Discussions. The changelog is
  version-to-version; prerelease sections fold at the stable cut
  (`scripts/consolidate_changelog.py`).
- API: version lives in `pyproject.toml`; dispatch **Release** (workflow, on
  `main`) then **Publish** (with the tag) — two dispatches, because
  `GITHUB_TOKEN`-created tags do not trigger the publish workflow. Then
  **verify PyPI itself** (the simple index, not a cached JSON response).
- Pin bumps in the integration go through
  `python scripts/check_dependency_pins.py --set idm-heatpump-api==X.Y.Z`,
  never by hand.

## 3. Protocol knowledge you need (condensed)

Deep documentation: wiki page *Navigator Protocol Analysis* (EN + DE). The
essentials:

### 3.1 WebSocket basics (Navigator 10 / Pro)

- URL: `ws://<host>:61220/?auth_code=<PIN>` (`DEFAULT_NAVIGATOR10_PORT`).
- Wrong PIN: the connection opens but the first frame answers
  `{"authorized": false}` — handle it, don't crash.
- Request frames: `{"controller": …, "command": …, "data": …}`; responses:
  `{"remoteSessionId": …, "<controller>": {…}}` (one session id per
  connection).
- The official web UI polls every 30–60 s; no unsolicited push frames were
  ever observed. Poll, don't wait.

### 3.2 Verified controller matrix (userlevel 0)

`status/overview` (userlevel, `myidmInfo`, notification count, `jsonVersion`,
controller clock `timestamp`) · `home/overview` + `home/detail` ·
`system/overview` (complete plant as JSON) · `system.freshwater/overview`
(DHW detail; **sub-controllers use `parameterId`, not `settingId`**) ·
`setting/detail` / `save` / `execute` (action types `restart, actioncode,
execute, relaytest, tt1, ttw, ttboost`) · `statistic/overview` + `detail` ·
`cascade/overview` (empty on single units) · `notification/overview` + `save`
· `authentication/overview` + `save` (level login) · `showcase`,
`frostprotection`, `relaytest` (wizards; `"wizard is not available!"`
outside their situations). There is **no firmware-update endpoint** on any
local interface.

### 3.3 User levels and codes

Exactly **userlevel 0** (end user, local PIN `SYSLPIN`; `0` blocks local
access entirely) and **userlevel 4** (technician; separate per-installation
code, `CODE_ENTRY_EXPERT`, distributed only by IDM service partners). Levels
1–3 are rejected. The time-dependent L1/L2 installer codes this integration
computes as sensors are valid **only on the controller display service menu** —
tested and rejected on the WebSocket. Failed attempts block the code input for
a while (`N2_USERLEVELINPUTBLOCKED`). The controller clock can drift — L1/L2
codes must be computed from the time shown on the display.

### 3.4 What we do NOT have yet

- The **level-0 settingId catalog**: which setting pages/values the web UI
  reads and writes for an end user. Only six read IDs are known (2.3).
- **Any captured WS write frame.** `setting/save` / `notification/save` exist,
  but their exact payloads and response semantics are unverified. Everything
  so far was strictly read-only.
- The **`statisticType`/`periodType` enum values** for `statistic/detail` in
  live use (the API method exists; the request values were taken from the SPA
  analysis and have not been confirmed against a capture).
- Whether the device tolerates **concurrent WS sessions** (web UI + integration
  simultaneously) at scale — untested, low risk.

### 3.5 Raw capture material

The raw NAV10 capture (Windows service tool configuration, WS enumeration
logs, pure-Python WS client templates `tools_ws/wsclient.py` / `wsenum.py`)
exists **only on the maintainer's machine** — it contains plant PINs, serial
numbers and network data and must **never** be committed. Sanitized knowledge
lives on the wiki page and, for errors, in the packaged database.

## 4. Hard rules (violating these wastes everyone's time)

1. **Read both `AGENTS.md` files first.** They override general instincts.
2. **Never push to `main`**; PRs only. English for every repo document;
   German only where it is a product feature (`README_de.md`, `de`
   translations, the register reference's German column, `docs/wiki/de/`).
3. **Device knowledge belongs in `idm-heatpump-api`.** The integration
   enriches, never re-implements. New public API symbols → extend the
   snapshot test + `docs/API-Contract.md` + compatibility matrix.
4. **Writes are safety-critical.** Modbus writes go through the API's
   validation (ranges, enums, EEPROM guards). WS writes must earn the same
   level of validation before a single frame is sent — see Phase 3/4.
5. **Real-hardware validation is read-only** unless the maintainer explicitly
   authorizes a specific write. The maintainer operating his own web UI while
   a proxy logs frames is the legitimate way to capture write semantics.
6. **No cloud.** The AI-advisor module's explicitly consented endpoints are
   the only exception; never add others.
7. **Entity naming goes through the pipeline** (`ENGLISH_NAMES` /
   `DERIVED_NAMES` + German counterpart + `generate_entity_translations.py`);
   `test_entity_translations.py` fails otherwise.
8. **Never hardcode register addresses** in platform files; registers come
   from the API, service constants live in `const.py`.
9. Pins move via the pin script; release notes/changelog keep the support
   links; released changelog sections are frozen history.
10. Don't bundle unrelated refactoring into these feature PRs — the audit
    packages are a separate track.

## 5. The roadmap

Strategic decision (already taken with the maintainer, 2026-09-27): **Modbus
stays the spine; the WebSocket grows into a first-class, user-selectable data
path.** Reasons: WS exists only on Nav 10/Pro (2.0 is HTTP, 1.x has no web
module at all); Modbus needs no PIN while WS requires `SYSLPIN` to be
configured; all validated writes are Modbus; the register map is fully
reverse-engineered and validated. The WS is where *new capability* comes from
(texts, statistics, settings, later parameters).

### Phase 1 — Connection mode & detection transparency

**Goal:** the user can explicitly choose how to connect; the integration
shows what it detected.

Scope:

- New option `connection_mode` in the options flow (Expert section), values:
  `auto` (default, recommended) · `modbus_web` · `web_only` · `modbus_only`.
  Option key in `const.py`; UI strings in `strings.json` +
  `translations/{en,de}.json`; **`test_config_flow.py` must stay at 100 %
  coverage.**
- `web_only` is promoted from "fallback after Modbus failure" to a
  first-class mode: with it set, setup does not attempt a Modbus connection.
  Label it honestly in the flow: *"read-only — setpoints, modes and error
  acknowledge require Modbus"* (until Phase 4 lands).
- Detection summary in the config flow (after probing) and as device
  attributes/diagnostics: controller family (Navigator 1.x / 2.0 / 10 / Pro),
  firmware/software version, WS availability (PIN configured?), `jsonVersion`,
  active userlevel, active connection mode. Most of these values already
  exist — `model_resolution.py`, web diagnostics, `software_version` sensor.

Acceptance: all four modes selectable and behaving as labeled; switching the
mode survives reload; diagnostics show the detection facts; full gates green.

Effort: small–medium. Integration repo only.

### Phase 2 — WS read expansion (the real progress)

**Goal:** consume the controllers that deliver data Modbus cannot.

Scope, in order of value:

1. **`statistic/detail`** (API method exists): device-side heat quantities by
   category. Add it to the web poll cycle (`web_data.py`), expose as `web_*`
   sensors through the naming pipeline, list dependencies in `polling_plan.py`
   if any derived sensor consumes them. Valuable as a cross-check against the
   self-integrated `energy_statistics.py` totals.
   *Dependency:* confirm `statisticType`/`periodType` request values — from a
   capture session (pull the Phase 3 tooling forward) or from the SPA bundle.
2. **`system.freshwater/overview`** for DHW detail where Modbus has gaps
   (circulation state, status info).
3. **`status/overview`** once per connection for `jsonVersion`/userlevel/
   controller clock as diagnostic attributes (cheap, clarifies support cases).

Acceptance: new sensors exist only when the controller actually answers with
data (established unused-filter pattern); wiki *Entities* page + German mirror
updated in the same PR; tests in `test_web_data.py` / `test_platforms.py`.

Effort: medium. Mostly integration; small API additions only if the response
shapes need new parsing.

### Phase 3 — WebUI capture session (owner-assisted; unlocks Phases 4–5)

**Goal:** the complete level-0 settingId catalog, read **and** write frames.

Procedure (maintainer participates; the integration/AI never writes):

1. Add a capture tool to the API repo (`scripts/ws_capture.py`) — a small
   logging WS proxy or a DevTools-based recipe; pure-Python, no dependencies
   (the `tools_ws/wsclient.py` template shows the handshake).
2. The maintainer points his browser at the NAV10 web UI **through the
   proxy** (or logs with DevTools) and clicks through: open every end-user
   settings page, change a harmless setpoint once, acknowledge a message.
3. Sanitize the logs (strip PINs/serials/IPs), document the settingId
   catalog and the `setting/save` / `notification/save` payload shapes on the
   wiki protocol page (+ German mirror).

Acceptance: catalog documented; wiki updated; the capture raw material stays
on the maintainer's machine.

Effort: small tool + one session with the maintainer. This is the cheapest
possible path to "fully decoded" — no guessing, no risk.

### Phase 4 — WS writes (only after Phase 3)

**Goal:** `web_only` mode becomes fully controllable.

Scope:

- API: write methods on `IdmNavigator10WebClient` (`save_setting`,
  `acknowledge_notifications`) with input validation mirroring the register
  write safety (typed values, declared ranges, no free-form payloads).
  Explicitly opt-in parameters; the clients' read-only default stands.
- Integration: in `web_only` mode route setpoint/mode writes and the
  acknowledge button through the WS; all other modes keep Modbus writes.
  Error handling per the established patterns (`error_messages.py`,
  repair issues).
- Validation on the maintainer's plant, write-by-write, each individually
  authorized. Never validate writes on third-party installations.

Acceptance: `web_only` users can set temperatures/modes and acknowledge
errors; Modbus paths byte-identical to before; the safety rules of the older
roadmap ("Safety rules for all new write features") apply verbatim.

Effort: large. Split into per-write-feature PRs (setpoints first, modes
second, acknowledge last).

### Phase 5 — Technician profile, userlevel 4 (optional, later)

**Goal:** opt-in L4 features for users who possess the technician code.

Scope: opt-in storage of the Fachmann-Code (never in diagnostics exports),
`parameter` / `afw` / `error` controller reads, a **curated** subset as
diagnostics/entities (2329 raw parameters as entities is not acceptable).
Requires its own privacy and safety review. Do not start before Phases 1–4.

## 6. Suggested PR sequence

1. `feat(connection-mode)` — Phase 1 (integration only).
2. `feat(statistics)` — Phase 2.1 (+ any API addition → API PR first, e.g.
   2.7.0, then pin bump via the script).
3. `feat(freshwater)` + `feat(status-diagnostics)` — Phase 2.2/2.3.
4. `tools(ws-capture)` — Phase 3 (API repo + wiki).
5. Phase 4 PRs per write feature, API-first.
6. In parallel, unrelated: Martin's field report in issue #319 (Navigator 1.x
   coils) may unlock the c3003 writable variant — do not couple it to this
   track.

## 7. Open unknowns (verify, don't assume)

- `statisticType`/`periodType` values in live requests (Phase 2.1 blocker).
- Level-0 settingId catalog (Phase 3 deliverable).
- WS write payload/response semantics, including error frames.
- Navigator 1.x `error_number` namespace vs. the packaged database (field
  feedback requested in 0.20.0-b2 changelog).
- Concurrent WS sessions (web UI + integration) — verify once, document.
- `jsonVersion` differences across firmware generations — parse defensively.

## 8. Privacy and safety boundaries (non-negotiable)

- PINs, tokens, serial numbers, network addresses and owner data never enter
  either repository. Raw captures stay on the maintainer's machine.
- Diagnostics exports stay redacted (`diagnostics.py` conventions; privacy
  tests exist — keep them passing).
- No cloud calls beyond the documented, consented AI-advisor exception.
- Real-plant validation is read-only unless the maintainer authorizes a
  specific write, in writing, per write.
