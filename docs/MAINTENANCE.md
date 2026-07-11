# Maintenance Policy

This document defines the operating rules for the IDM Heatpump Home Assistant
custom integration and its companion `idm-heatpump-api` package.

## Support Window

- The latest stable integration release is supported.
- The latest stable `idm-heatpump-api` release pinned by the integration is
  supported.
- Older releases may receive guidance, but fixes are normally released forward.
- Security fixes can skip normal feature batching and should be released as
  soon as CI and a smoke test pass.

## Response Targets

These are best-effort targets for a spare-time project:

- Security reports: acknowledge within 7 days.
- P0 installation, polling, or unsafe-write defects: triage within 7 days.
- Compatibility reports for new IDM firmware or hardware: triage within 14
  days when diagnostics are available.
- Feature requests: review during quarterly roadmap maintenance.

## Required Review Areas

Changes in these areas require maintainer review before merge:

- Modbus register definitions and model gates.
- Write-enabled entities, services, and validation logic.
- EEPROM-sensitive or cyclic write handling.
- Release workflows, dependency pins, and package metadata.
- Diagnostics redaction and repair issue handling.

## Repository Settings

Maintain these settings in both repositories:

- Protect `main`: require pull requests, required CI checks, linear history, and
  no force-pushes.
- Treat Security, tests, type checks, lint, format, package build, and contract
  tests as required checks once the workflows are green on the default branch.
- Use protected release environments for PyPI and GitHub releases.
- Delete merged branches automatically after merge.
- Enable Dependabot security and version updates.
- Keep secrets only in GitHub Environments or repository secrets, never in the
  repository.

## Roadmap Review

Review the roadmap at least once per quarter:

- Link completed work to releases, PRs, or issues.
- Keep historical context when it explains compatibility or safety decisions.
- Move stale ideas to a backlog instead of silently deleting them.
- Re-rank P0/P1 work before adding larger features.

## Incident Handling

For a release or security incident:

1. Stop additional releases until the impact is understood.
2. Confirm affected versions and whether writes, polling, setup, or diagnostics
   are involved.
3. Publish a fix branch and run full CI plus the release smoke test.
4. Release the fixed API first when both repositories are affected.
5. Release the integration with the fixed API pin.
6. Add clear user-facing notes for rollback, migration, or required manual
   action.

## Bus Factor

Keep these artifacts current so another maintainer can take over emergency
work:

- `docs/RELEASE_PROCESS.md`
- `docs/CORE_STRATEGY.md`
- `docs/wiki/Compatibility-Matrix.md`
- `docs/wiki/Modbus-Register.md`
- `.github/CODEOWNERS`
