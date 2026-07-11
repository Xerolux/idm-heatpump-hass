"""Release contract tests for pinned runtime dependencies."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "idm_heatpump" / "manifest.json"

EXPECTED_RUNTIME_REQUIREMENTS = [
    "pymodbus>=3.12.1,<4.0",
    "idm-heatpump-api[web]==0.7.6",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _workflow_preamble(workflow: str) -> str:
    """Return workflow-level configuration before permissions and jobs."""
    return workflow.partition("\npermissions:\n")[0]


def test_manifest_declares_tested_runtime_dependencies() -> None:
    manifest = json.loads(_read(MANIFEST))

    assert manifest["requirements"] == EXPECTED_RUNTIME_REQUIREMENTS


def test_ci_installs_runtime_dependencies_from_manifest() -> None:
    ci = _read(ROOT / ".github" / "workflows" / "ci.yml")
    quality = _read(ROOT / ".github" / "workflows" / "python-quality.yml")

    assert "./.github/workflows/python-quality.yml" in ci
    assert "manifest.json" in quality
    assert 'json.load(manifest_file)["requirements"]' in quality
    assert 'pip", "install", *requirements' in quality


def test_ci_tests_pinned_and_compatible_api_dependencies() -> None:
    ci = _read(ROOT / ".github" / "workflows" / "ci.yml")
    quality = _read(ROOT / ".github" / "workflows" / "python-quality.yml")

    assert "api-dependency-mode" in ci
    assert "manifest-pinned" in ci
    assert "api-main" in ci
    assert "pymodbus>=3.12.1,<4.0" in quality
    assert "idm-heatpump-api.git@main" in quality


def test_ci_and_release_share_complete_python_quality_workflow() -> None:
    ci = _read(ROOT / ".github" / "workflows" / "ci.yml")
    release = _read(ROOT / ".github" / "workflows" / "release.yml")
    quality = _read(ROOT / ".github" / "workflows" / "python-quality.yml")

    reusable_workflow = "uses: ./.github/workflows/python-quality.yml"
    assert reusable_workflow in ci
    assert reusable_workflow in release
    assert "workflow_call:" in quality
    assert "ruff check custom_components/idm_heatpump tests" in quality
    assert "ruff format custom_components/idm_heatpump tests --check" in quality
    assert "mypy custom_components/idm_heatpump" in quality
    assert "pytest tests/" in quality
    assert "--cov=custom_components/idm_heatpump" in quality
    assert 'home-assistant-version: "2026.5.0"' in release
    assert "api-dependency-mode: manifest-pinned" in release


def test_ci_runs_once_for_source_changes_and_cancels_superseded_runs() -> None:
    ci = _workflow_preamble(_read(ROOT / ".github" / "workflows" / "ci.yml"))

    assert "  push:\n    branches: [main]" in ci
    assert "  pull_request:\n    branches: [main]" in ci
    assert '  schedule:\n    - cron: "0 0 * * *"' in ci
    assert "  workflow_dispatch:" in ci
    assert "    tags:" not in ci
    assert "  release:" not in ci
    assert (
        "group: ci-${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}"
        in ci
    )
    assert "cancel-in-progress: true" in ci


def test_release_has_one_tag_trigger_and_serializes_each_version() -> None:
    release = _workflow_preamble(
        _read(ROOT / ".github" / "workflows" / "release.yml")
    )

    assert "  push:\n    tags:\n      - 'v*'" in release
    assert release.count("      - 'v*'") == 1
    assert "  release:" not in release
    assert "  workflow_dispatch:" in release
    assert "group: release-${{ inputs.tag_name || github.ref_name }}" in release
    assert "cancel-in-progress: false" in release


def test_api_dependency_update_workflow_updates_pin_and_runs_contract_tests() -> None:
    workflow = _read(ROOT / ".github" / "workflows" / "api-dependency-update.yml")

    assert "idm_heatpump_api_release" in workflow
    assert 'requirement = f"idm-heatpump-api[web]=={version}"' in workflow
    assert 'json.load(manifest_file)["requirements"]' in workflow
    assert 'pip", "install", *requirements' in workflow
    assert "tests/test_release_contract.py tests/test_cross_repo_contract.py" in workflow
    assert "peter-evans/create-pull-request" in workflow


def test_release_artifact_is_built_from_manifest_directory() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert "cd custom_components/idm_heatpump" in release_workflow
    assert "zip -r ../../idm_heatpump.zip ." in release_workflow
    assert "manifest.json" not in release_workflow.partition("zip -r ../../idm_heatpump.zip .")[2].partition("\n\n")[0]


def test_release_workflow_validates_prepared_version_and_changelog() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert "Validate prepared release metadata" in release_workflow
    assert 'manifest_version = json.loads(manifest_path.read_text(encoding="utf-8"))["version"]' in release_workflow
    assert "if manifest_version != version:" in release_workflow
    assert 'expected_heading = f"## [{version}]"' in release_workflow
    assert "docs/CHANGELOG.md has no heading for release" in release_workflow


def test_release_workflow_never_mutates_or_pushes_release_metadata() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert "update-changelog:" not in release_workflow
    assert "Update version in manifest" not in release_workflow
    assert "sed -i" not in release_workflow
    assert "git commit" not in release_workflow
    assert "git push" not in release_workflow


def test_release_workflow_uses_prerelease_tags_for_previous_release() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert "(-[0-9A-Za-z.-]+)?$" in release_workflow


def test_user_facing_dependency_docs_match_manifest() -> None:
    docs = [
        ROOT / "README.md",
        ROOT / "README_de.md",
        ROOT / "docs" / "wiki" / "Home.md",
        ROOT / "docs" / "wiki" / "_Sidebar.md",
    ]

    for requirement in EXPECTED_RUNTIME_REQUIREMENTS:
        assert all(requirement in _read(path) for path in docs)


def test_modbus_activation_guidance_is_consistent_in_ui_and_docs() -> None:
    paths = [
        ROOT / "README.md",
        ROOT / "README_de.md",
        ROOT / "docs" / "wiki" / "Home.md",
        ROOT / "docs" / "wiki" / "Installation-and-Setup.md",
        ROOT / "docs" / "wiki" / "Troubleshooting.md",
        ROOT / "custom_components" / "idm_heatpump" / "strings.json",
        ROOT / "custom_components" / "idm_heatpump" / "translations" / "de.json",
        ROOT / "custom_components" / "idm_heatpump" / "translations" / "en.json",
    ]

    for path in paths:
        content = _read(path)
        assert "Gebäudeleittechnik" in content, path
        assert "Modbus TCP" in content, path

    installation = _read(ROOT / "docs" / "wiki" / "Installation-and-Setup.md")
    assert "PV inverter" in installation
    assert "port 502" in installation
    assert "slave/unit ID 1" in installation
