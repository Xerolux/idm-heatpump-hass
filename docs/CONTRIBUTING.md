# Contribution Guidelines

We welcome contributions to this project! Whether it's reporting a bug, submitting a fix, or proposing new features, your contributions are highly appreciated.

## Pull Request Process

1. **Fork the Repository:** Create a fork on your GitHub account.
2. **Create a Branch:** Use a descriptive name (e.g., `fix/issue-123`, `feat/add-new-sensor`).
3. **Make Changes:** Implement your changes, including code modifications and documentation updates.
4. **Lint Your Code:** Run `ruff check` and `ruff format` on your changes.
5. **Test Your Changes:** Ensure all existing tests pass and add new tests for new functionality.
6. **Commit:** Use clear commit messages following [Conventional Commits](https://www.conventionalcommits.org/).
7. **Push & Create PR:** Target the `main` branch with a clear description.

## Language

Write in English: code, comments, documentation, changelog entries, commit
messages and pull request descriptions. German belongs only in `README_de.md`
and in the Home Assistant `de` translations. `python
scripts/check_documentation_language.py` checks the documents, and
`tests/test_documentation_language.py` fails the build on German prose.

## Release Notes Style

The changelog section of a version becomes the release notes verbatim
(`.github/workflows/release.yml` extracts it), and those notes are what
users see in the HACS update dialog. Write them for that reader — not as
an internal audit log:

- Open with one or two sentences of narrative that say *why the release
  matters*, not just what it contains.
- Group entries under emoji headers: `### ✨ New`, `### 🐛 Bugfixes`,
  `### 💼 Maintenance`, `### ❤️ Thanks`.
- Lead every bullet with a short bold phrase, then explain in one or two
  sentences. Link the issue (`#364`) instead of restating the report.
- Credit reporters and contributors by @mention under `### ❤️ Thanks`
  whenever a release was shaped by field data.
- Keep the technical depth, but keep it readable — a user should
  understand the first screen without scrolling.
- Section headings inside a version stay `###` so the `## [version]`
  heading keeps its hierarchy; never rename the `## [version] - date`
  headings, the release workflow matches them exactly.
- The support footer and the `.../Basti` signature are appended by the
  release workflow — do not duplicate them in the changelog file.

## Coding Style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. Please ensure your code is formatted with Ruff before submitting.

## Bug Reports

Please report bugs by [opening a new issue](../../issues/new?template=bug_report.md) with:

- **Summary:** Brief description of the issue
- **Steps to Reproduce:** Detailed instructions
- **Expected vs. Actual Result**
- **Environment:** HA version, integration version, heat pump model, firmware
- **Logs:** Enable debug logging:
  ```yaml
  logger:
    default: info
    logs:
      custom_components.idm_heatpump: debug
  ```
- **Diagnostics:** Download diagnostics data from the integration page

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
