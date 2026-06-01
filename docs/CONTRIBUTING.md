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
