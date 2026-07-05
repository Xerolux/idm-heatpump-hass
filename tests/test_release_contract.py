"""Release contract tests for pinned runtime dependencies."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "idm_heatpump" / "manifest.json"

EXPECTED_RUNTIME_REQUIREMENTS = [
    "pymodbus>=3.12.1,<4.0",
    "idm-heatpump-api[web]>=0.5,<0.6",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_manifest_declares_tested_runtime_dependencies() -> None:
    manifest = json.loads(_read(MANIFEST))

    assert manifest["requirements"] == EXPECTED_RUNTIME_REQUIREMENTS


def test_ci_installs_runtime_dependencies_from_manifest() -> None:
    ci = _read(ROOT / ".github" / "workflows" / "ci.yml")

    assert "manifest.json" in ci
    assert 'json.load(manifest_file)["requirements"]' in ci
    assert 'pip", "install", *requirements' in ci


def test_ci_tests_pinned_and_compatible_api_dependencies() -> None:
    ci = _read(ROOT / ".github" / "workflows" / "ci.yml")

    assert "api-dependency-mode" in ci
    assert "manifest-pinned" in ci
    assert "api-branch-compatible" in ci
    assert "pymodbus>=3.12.1,<4.0" in ci
    assert "idm-heatpump-api.git@main" in ci


def test_api_dependency_update_workflow_updates_pin_and_runs_contract_tests() -> None:
    workflow = _read(ROOT / ".github" / "workflows" / "api-dependency-update.yml")

    assert "idm_heatpump_api_release" in workflow
    assert 'requirement = f"idm-heatpump-api[web]>={major_minor},<{next_major_minor}"' in workflow
    assert "tests/test_release_contract.py tests/test_cross_repo_contract.py" in workflow
    assert "peter-evans/create-pull-request" in workflow


def test_release_artifact_is_built_from_manifest_directory() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert "cd custom_components/idm_heatpump" in release_workflow
    assert "zip -r ../../idm_heatpump.zip ." in release_workflow
    assert "manifest.json" not in release_workflow.partition("zip -r ../../idm_heatpump.zip .")[2].partition("\n\n")[0]


def test_release_workflow_does_not_duplicate_existing_changelog_entries() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert 'grep -q "^## \\\\[$VERSION\\\\]" docs/CHANGELOG.md' in release_workflow
    assert "Changelog already contains an entry for $VERSION" in release_workflow


def test_user_facing_dependency_docs_match_manifest() -> None:
    docs = [
        ROOT / "README.md",
        ROOT / "README_de.md",
        ROOT / "docs" / "wiki" / "Home.md",
        ROOT / "docs" / "wiki" / "_Sidebar.md",
    ]

    for requirement in EXPECTED_RUNTIME_REQUIREMENTS:
        assert all(requirement in _read(path) for path in docs)
