# GitHub Discussions setup

The repository templates and release workflow expect GitHub's standard category
slugs. Keep these slugs unchanged when editing names or descriptions.

## Recommended sections and categories

| Section | Category | Slug | Format | Description |
|---|---|---|---|---|
| Project | Announcements | `announcements` | Announcement | Releases and important project news; new release posts are created automatically. |
| Project | Ideas | `ideas` | Open-ended | Feature requests focused on the problem, benefit and user experience. |
| Help & Exchange | Q&A | `q-a` | Question and answer | Setup, device/firmware compatibility, Modbus registers and usage questions. |
| Help & Exchange | Show and tell | `show-and-tell` | Open-ended | Lovelace dashboards, cards, automations, scripts and blueprints. |
| Help & Exchange | General | `general` | Open-ended | Project-related experience that does not fit another category. |

The default **Polls** category is intentionally not needed. It can be deleted or
kept outside the sections until there is a concrete use case.

## Descriptions and forms

Set the category descriptions from the table above in the Discussions category
settings. The matching forms live in `.github/DISCUSSION_TEMPLATE/`; GitHub maps
each YAML filename to the category with the same slug.

## Release announcements

`release.yml` grants only `contents: write` and `discussions: write` to the release
job. After a non-draft release is uploaded, it runs
`scripts/publish_release_discussion.py`, which:

1. finds the `announcements` category,
2. skips a tag that has already been announced,
3. publishes the release notes with download, Q&A and bug-report links,
4. labels pre-releases clearly as test versions.

If the category is renamed to a different slug, update
`DISCUSSION_CATEGORY_SLUG` in `.github/workflows/release.yml`.
