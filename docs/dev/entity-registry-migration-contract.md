# Entity Registry Migration Contract

Last updated: 2026-07-21

This document describes the binding safety frame for future changes to entity
profiles, defaults and the device hierarchy.

## Goal

New integration versions may set better defaults for new installations, but they
must not overwrite existing user decisions in Home Assistant. That applies in
particular to entities the user has manually enabled, disabled, renamed, or used
in dashboards.

## Hard rules

1. **Unique IDs stay stable.** Register-backed entities keep using
   `{entry_id}_{register_name}`. Building-management value numbers keep their
   deliberate `_set` suffix to avoid collisions with sensors.
2. **Default profiles are defaults only.** Changes to
   `entity_registry_enabled_default` apply to new entity registry entries only,
   or to entities Home Assistant has not registered yet.
3. **No retroactive forced disabling.** A migration must not disable existing
   entity registry entries just because the default profile changed.
4. **No retroactive forced enabling.** A migration must not re-enable entities
   the user disabled.
5. **Sub-devices do not change unique IDs.** The device hierarchy may move
   `device_info`, but it must not change entity identity.
6. **Breaking changes need a migration.** When an entity key really has to be
   replaced, it needs an explicit entity registry migration with tests and a
   changelog note.

## Allowed

- Removing the entity registry entries of a heating circuit the user has
  **deselected** in the options. The trigger is an explicit configuration
  decision, not a changed default — the entities are no longer created anyway
  and would otherwise stay behind permanently as "unavailable". When the circuit
  is enabled again they are recreated under their unchanged unique ID. The scope
  is narrow: only register-backed entities of this config entry whose register
  name points at a heating circuit that is not configured.
- Disabling newly generated expert values by default.
- Classifying existing explicit metadata better.
- Improving `entity_category`, icon, name or device class, as long as the unique
  ID and the user's enablement are preserved.
- Adding new diagnostics or support documentation.

## Not allowed

- Changing existing unique IDs without a migration.
- Removing existing entity registry entries because of new defaults. Removing
  deselected heating circuits above is the only exception, and it depends on a
  user decision, not on a default.
- Overwriting user enablement based on the new profile.
- Using the device hierarchy as a pretext for new entity IDs.

## Review notes for pull requests

- New default-disabled rules must contain tests for enabled core values and
  disabled expert values.
- Changes to `build_entity_unique_id`, building-management `_set` suffixes or
  climate/DHW unique IDs need focused regression tests.
- Documentation generators may document profiles, but they must not trigger
  runtime migrations.
