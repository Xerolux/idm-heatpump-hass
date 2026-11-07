# Contributing

We welcome contributions to this project!

## How to Contribute

- **Bug Reports**: [Create an issue](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- **Questions & Help**: [Start a Q&A discussion](https://github.com/Xerolux/idm-heatpump-hass/discussions/categories/q-a)
- **Feature Requests**: [Share an idea](https://github.com/Xerolux/idm-heatpump-hass/discussions/categories/ideas)
- **Lovelace & Automations**: [Show your project](https://github.com/Xerolux/idm-heatpump-hass/discussions/categories/show-and-tell)
- **Pull Requests**: Fork → Branch → Changes → PR
- **Documentation**: Improve wiki pages or add new ones
- **Translations**: Help with DE/EN translations

## Development Environment Setup

1. Fork the repository
2. Clone the fork locally
3. Copy `custom_components/idm_heatpump/` to your HA `custom_components/` directory
4. Enable debug logging
5. Restart HA

## Language

The project writes in English: code, comments, documentation, changelog entries,
commit messages and pull request descriptions. German belongs in
`README_de.md`, the Home Assistant `de` translations and the German wiki mirror
under `docs/wiki/de/`. English wiki pages remain the source of truth. Run
`python scripts/check_documentation_language.py` before opening a pull request —
`tests/test_documentation_language.py` fails the build on German prose.

## Code Style

- Use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages
- Keep the code simple and understandable

## Pull Request Process

1. Create a fork
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Commit your changes (`git commit -m 'feat: add my feature'`)
4. Push to the fork (`git push origin feat/my-feature`)
5. Create a Pull Request

## License

By contributing, you agree that your code will be published under the MIT License.

## Keep documentation with the code

Every new feature, behavior-changing fix and field discovery belongs on the
relevant English wiki page and its German mirror. Include setup, defaults,
actions, privacy and limitations. Link evidence and open questions in the
[findings register](Findings-and-Documentation). Register new pages in the
website navigation as well.

`python scripts/check_wiki_coverage.py` reports new or changed source modules,
missing language mirrors and undocumented actions. Only after reviewing both
languages, run `python scripts/check_wiki_coverage.py --update` and inspect
`docs/wiki-coverage.json`. Also run
`python scripts/check_documentation_versions.py` for version claims.
