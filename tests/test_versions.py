"""Tests for runtime version diagnostics."""

from importlib.metadata import PackageNotFoundError
from unittest.mock import MagicMock, patch

from custom_components.idm_heatpump.versions import (
    async_runtime_versions,
    distribution_version,
    runtime_versions,
)


def test_runtime_versions_exposes_integration_and_dependencies() -> None:
    with patch(
        "custom_components.idm_heatpump.versions.distribution_version",
        side_effect=lambda name: {"idm-heatpump-api": "0.7.3", "pymodbus": "3.13.1"}[name],
    ):
        versions = runtime_versions("0.8.1-beta.23")

    assert versions.integration == "0.8.1-beta.23"
    assert versions.api == "0.7.3"
    assert versions.pymodbus == "3.13.1"


def test_missing_distribution_returns_unknown() -> None:
    distribution_version.cache_clear()


async def test_async_runtime_versions_runs_sync_lookup_in_thread() -> None:
    expected = MagicMock()
    with (
        patch("custom_components.idm_heatpump.versions.runtime_versions", return_value=expected) as lookup,
        patch("custom_components.idm_heatpump.versions.asyncio.to_thread", return_value=expected) as to_thread,
    ):
        result = await async_runtime_versions("0.8.1-beta.23")

    assert result is expected
    to_thread.assert_awaited_once_with(lookup, "0.8.1-beta.23")
    with patch("custom_components.idm_heatpump.versions.version", side_effect=PackageNotFoundError):
        assert distribution_version("missing-package") == "unknown"
    distribution_version.cache_clear()
