"""Tests for runtime version diagnostics."""

from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

from custom_components.idm_heatpump.versions import distribution_version, runtime_versions


def test_runtime_versions_exposes_integration_and_dependencies() -> None:
    with patch(
        "custom_components.idm_heatpump.versions.distribution_version",
        side_effect=lambda name: {"idm-heatpump-api": "0.7.1", "pymodbus": "3.13.1"}[name],
    ):
        versions = runtime_versions("0.8.1-beta.21")

    assert versions.integration == "0.8.1-beta.21"
    assert versions.api == "0.7.1"
    assert versions.pymodbus == "3.13.1"


def test_missing_distribution_returns_unknown() -> None:
    distribution_version.cache_clear()
    with patch("custom_components.idm_heatpump.versions.version", side_effect=PackageNotFoundError):
        assert distribution_version("missing-package") == "unknown"
    distribution_version.cache_clear()
