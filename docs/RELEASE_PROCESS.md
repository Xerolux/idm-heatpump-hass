# Release Process

This process covers coordinated releases of `idm-heatpump-api` and the Home
Assistant custom integration.

## Release Order

1. Change the API package when registers, decoding, validation, or model
   detection need to move.
2. Run API CI, package build, type checks, lint, format, security checks, and
   Home Assistant contract tests.
3. Publish the API release.
4. Open an integration PR that pins the exact API version in
   `custom_components/idm_heatpump/manifest.json`.
5. Run integration CI, HACS validation, Hassfest, type checks, lint, format, and
   the release smoke test.
6. Publish the integration release and verify the packed artifact.

## Pre-Release Channel

Use alpha, beta, or release-candidate tags when a change affects:

- model detection;
- unsupported register isolation;
- write-enabled entities or services;
- Home Assistant setup, reload, or migration behavior;
- a new IDM model, firmware family, or controller generation.

Device candidates should use read-only verification first. Write verification
must be limited to documented safe registers.

## API Release Checklist

- `pytest tests/ -v --tb=short --cov=idm_heatpump --cov-report=term-missing --cov-fail-under=75`
- `ruff check idm_heatpump tests`
- `ruff format idm_heatpump tests --check`
- `mypy idm_heatpump`
- `python -m build`
- `twine check dist/*`
- Install the built wheel into a clean virtual environment and import the public
  package root.
- Confirm `pyproject.toml` version and Git tag are identical.
- Confirm release notes are curated and include breaking changes or migration
  steps.

## Integration Release Checklist

- `pytest tests/ -v --tb=short --cov=custom_components/idm_heatpump --cov-report=term-missing`
- `ruff check custom_components/idm_heatpump tests`
- `ruff format custom_components/idm_heatpump tests --check`
- `mypy custom_components/idm_heatpump`
- HACS validation.
- Hassfest validation.
- Cross-repo API contract tests.
- Release smoke test from `docs/RELEASE_SMOKE_TEST.md`.
- Unzip the release artifact and verify:
  - `custom_components/idm_heatpump/manifest.json` exists;
  - the manifest version matches the tag;
  - the API dependency pin is exact;
  - the component imports in a clean Python environment.

## Changelog Rules

Release notes must be curated by a maintainer. Do not rely only on commit
keywords.

Each release should call out:

- user-visible fixes and features;
- hardware or firmware compatibility changes;
- dependency or Home Assistant baseline changes;
- breaking changes and migration steps;
- known limitations and follow-up work.

## Rollback

### API

1. Yank the broken PyPI release only when installing it is actively harmful.
2. Publish a fixed patch release when possible.
3. Update the integration pin to the fixed API version.
4. Document the affected API versions in release notes.

### Integration

1. Mark the GitHub release as pre-release or remove the latest marker if needed.
2. Publish a patch release with a safe API pin and clear notes.
3. Tell HACS users which version to install manually if automatic updates have
   not propagated.
4. Keep the rollback instructions in the release notes until the next stable
   release.
