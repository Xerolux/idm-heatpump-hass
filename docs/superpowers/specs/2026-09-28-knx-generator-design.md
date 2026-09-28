# KNX Group Address Generator — Design

Date: 2026-09-28
Status: approved by the owner (interactive generator, presets + object groups,
bilingual UI following the site's language switch)

## Goal

Owners of the IDM Heatpump integration need an ETS-importable group address
file for the KNX bridge, on **their** base group address. The two pre-built
files in `docs/examples/knx/` assume the default `8/0/0`, which is often
taken (the owner's own installation moved to `11/0/0`). Instead of shipping
more static variants, the GitHub Pages site gets an interactive generator:
pick a base address, pick a preset or object groups, download the XML (and
CSV reference).

## Non-goals

* Per-register selection (654 checkboxes). The bridge itself configures by
  object groups; the compact preset covers the curated subset.
* Server-side generation. The site is static; everything happens in the
  browser.
* Changes to the integration runtime. Only the website and its build script
  change.

## Architecture

### Data: one source of truth

`scripts/build_pages.py` emits `assets/knx-catalog.json` into the Pages
artifact at build time, loading `knx_catalog.py` and `adapter_names.py` by
path (both stdlib-only; the same trick `generate_knx_group_addresses.py`
already uses). The JSON carries:

* `version` (integration manifest version, informational)
* `default_base`, `project_name` ("Wärmepumpe"), `prefix` ("WP")
* `compact_registers`: the curated register list
* `groups`: `[{id, label, count}]` in catalogue order (German middle-group
  labels)
* `objects`: `[{number, register, dpt, group, writable, name}]` with the
  German display name (including the generator's `EXTRA_NAMES`)

The catalogue can therefore never drift from the integration. No JSON is
committed; it exists only in the built artifact.

### Page

A regular documentation page, slug `knx-generator`, so navigation, sitemap,
breadcrumbs, language alternates and the SEO tests all pick it up
automatically:

* `docs/wiki/KNX-Generator.md` (English) → `/docs/knx-generator/`
* `docs/wiki/de/KNX-Generator.md` (German mirror) → `/docs/de/knx-generator/`
* registry entries in `DOCUMENTATION_PAGES` / German registry in
  `scripts/build_pages.py`
* sidebar entry in `docs/wiki/_Sidebar.md`

The markdown explains what the file is for, that the base address must match
the bridge configuration, and the ETS import steps. An HTML placeholder
`<div data-knx-generator></div>` marks where the interactive block renders.
On the GitHub wiki mirror (where scripts do not run) the page shows the
explanatory text plus a pointer to the website.

### Interactive block

Two assets under `docs/public/assets/`:

* `knx-generator-core.mjs` — pure functions, no DOM: group address
  parse/format/validate (mirroring `knx_catalog.py` rules), object selection
  (preset full/compact/groups), row building, and the XML/CSV renderers
  (mirroring `generate_knx_group_addresses.py` byte for byte, including the
  `WP` prefix, `DPST-x-y` conversion, the middle-group labels joined with
  ` · ` and the `Objekte X–Y` fallback, and quoteattr-style escaping).
* `knx-generator.mjs` — browser bootstrap. Renders the UI when the
  placeholder container exists, detects the page language from
  `document.documentElement.lang` (the build sets it per language) and
  renders every label bilingually (German and English dictionaries in the
  module). The object names inside the generated files stay German — they
  match what the Python generator produces and how the entities read in
  Home Assistant.

UI elements:

1. Base address text input (default `8/0/0`) with live validation:
   three-level format, value ranges, headroom for 999 objects to the end of
   the address space, inline error message.
2. Preset selection: Compact (43) / Full (654) / Custom.
3. Twelve object-group checkboxes with live object counts (active in Custom
   mode only).
4. Live summary: object count, address span, estimated first-export
   telegram count.
5. Collapsible preview of the selected objects (name, object number, group
   address, DPT, direction).
6. Download buttons: XML (ETS import) and CSV (reference), file name
   `idm-waermepumpe-<base with dashes>.xml` / `.csv`.

An empty selection disables the downloads and shows a hint instead.

### Parity guarantee

`scripts/check_knx_generator_parity.mjs` (Node, no dependencies) loads the
core module and a generated catalog JSON, builds XML and CSV for fixture
configurations (full and compact on `8/0/0`, custom groups on `11/0/0`) and
compares the output **byte for byte** with a fresh run of
`scripts/generate_knx_group_addresses.py` via subprocess. It also asserts
that invalid base addresses are rejected identically.

`tests/test_knx_generator_parity.py` writes the catalog JSON through the
same `build_pages` function the site build uses, then runs the harness. It
needs Node, exactly like the existing Pages tests.

Further tests:

* `tests/test_build_pages.py` (or the existing pages tests): the artifact
  contains `assets/knx-catalog.json`; its objects match `KNX_OBJECTS` in
  number, order and fields; compact registers all resolve.
* `tests/test_pages_seo.py` picks the new page up via the registry and
  enforces the German mirror.

## Error handling

* Invalid base address: inline validation, downloads disabled — no file
  with wrong addresses can be produced.
* Empty selection: disabled downloads plus hint.
* Missing catalog JSON (fetch failure): the block shows an error notice
  instead of a broken UI.
* The generator is additive: any failure leaves the rest of the site
  untouched.

## Files touched

| File | Change |
| --- | --- |
| `scripts/build_pages.py` | load catalogue modules, emit `assets/knx-catalog.json`, register the page (EN + DE) |
| `docs/public/assets/knx-generator-core.mjs` | new — pure generator logic |
| `docs/public/assets/knx-generator.mjs` | new — bilingual UI bootstrap |
| `docs/public/docs/docs.css` | styles for the generator block |
| `docs/public/docs/index.html` (shell) | include the generator module script |
| `docs/wiki/KNX-Generator.md`, `docs/wiki/de/KNX-Generator.md` | new page pair |
| `docs/wiki/_Sidebar.md` | sidebar entry |
| `docs/wiki/KNX-Bridge.md` (+ German mirror) | link the generator from the import-files section |
| `scripts/check_knx_generator_parity.mjs` | new — parity harness |
| `tests/test_knx_generator_parity.py` | new — pytest wrapper |
| `tests/test_build_pages.py` | new — catalog JSON emission checks |

## Deployment

`pages.yml` already triggers on `docs/public/**`, `docs/wiki/**` and
`scripts/build_pages.py`; no workflow change is needed.
