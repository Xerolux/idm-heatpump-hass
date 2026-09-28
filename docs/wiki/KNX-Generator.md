# KNX Group Address Generator

The [KNX bridge](KNX-Bridge) derives every group address from one base
address: `group address = base address + IDM object number`. ETS needs those
addresses to exist in the project before a real KNX device — a push-button
showing the flow temperature, a visualisation, a logic module — can be linked
to them.

This page builds that import file in the browser. Pick a base address, pick
what goes into the file, download the `.xml` — no installation, and nothing
leaves your computer: the catalogue is served with the page and the file is
generated locally.

<div data-knx-generator></div>

> The interactive block runs on the documentation website. On the GitHub wiki
> mirror scripts do not execute — use
> [the website](https://xerolux.github.io/idm-heatpump-hass/docs/knx-generator/)
> instead.

## Before you generate

- **The base address must match the bridge configuration.** Whatever you
  enter here has to be entered as the *base group address* in the KNX bridge
  options in Home Assistant (see [KNX bridge](KNX-Bridge)); otherwise the
  bridge sends next to the addresses your ETS project imported.
- **The default `8/0/0` is only a default.** If that main group is already
  taken in your project — a common case — pick a free one, for example
  `11/0/0`. The full catalogue needs the 999 addresses above the base to fit
  below the end of the address space; the generator rejects a base where
  they do not.
- **The selection should mirror the bridge's object groups.** Whatever the
  file contains should be switched on in the bridge options too, so the
  addresses in ETS are actually served.

## Importing into ETS 6

1. Back up your ETS project.
2. Right-click the top entry under *Group Addresses* and choose *Import
   Group Addresses*.
3. Pick the downloaded `.xml` (three-level group address style).
4. Check the import report, especially against addresses that already exist
   in the project.

The `.csv` download is a readable reference — object number, register,
direction — not an import file.

## What the presets contain

- **Compact** — 43 addresses: what a display or visualisation realistically
  shows, plus the values a KNX installation can feed back into the heat
  pump. Heating circuits A and B.
- **Full catalogue** — all 654 communication objects.
- **Custom selection** — the twelve object groups, with their live object
  counts. What each group contains is described in the
  [object groups table](KNX-Bridge#object-groups) on the KNX bridge page.

---

**See also:** [KNX Bridge](KNX-Bridge) · [Configuration](Configuration)
