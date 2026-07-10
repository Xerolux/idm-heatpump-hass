# Home Assistant Core Strategy

The current decision is **HACS first, Core later**.

The integration should continue as a HACS custom integration until the hardware
matrix, API contract, release process, and write-safety behavior have had a
stable maintenance period. A Core PR should be small, boring, and reviewable
rather than a direct move of every HACS feature.

## Entry Criteria for a Core Attempt

- At least one current Navigator 2.0-compatible setup and one Navigator
  10-compatible setup are confirmed on the latest stable integration.
- `idm-heatpump-api` has a stable public import contract and exact integration
  pin.
- Model-gated register maps avoid unsupported Navigator-specific registers.
- Setup, reload, unload, migration, diagnostics, and repair issues are covered
  by tests.
- The release process and rollback path are documented.
- Branch protection, CODEOWNERS, dependency updates, and security scans are in
  place.

## Proposed First Core Scope

Limit the first PR to a central platform and essential read-only monitoring:

- config flow;
- model detection;
- coordinator polling;
- diagnostics with redaction;
- core sensors required to prove useful monitoring.

Defer these to later PRs:

- write-enabled entities;
- custom actions and advanced services;
- broad zone-module coverage;
- optional cascade, PV, solar, and ISC expansions;
- Gold or Platinum quality claims.

## Core Port Adjustments

When a Core branch is prepared:

- remove custom-integration-only manifest fields such as `version` and
  `issue_tracker`;
- follow the Home Assistant Core dependency and test conventions;
- adapt fixtures to the Home Assistant Core test framework;
- create the matching `home-assistant.io` documentation page;
- add brand assets through the Home Assistant Brands repository;
- document HACS-to-Core migration, including entity registry, device registry,
  and domain-collision behavior.

## Current Status

No Core PR is opened yet. The project should first ship the HACS stabilization
work and gather compatibility feedback from real devices.
