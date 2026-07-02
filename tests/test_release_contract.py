"""Release contract tests for pinned runtime dependencies."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "idm_heatpump" / "manifest.json"

EXPECTED_RUNTIME_REQUIREMENTS = [
    "pymodbus==3.12.1",
    "idm-heatpump-api==0.3.7",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_manifest_pins_tested_runtime_dependencies() -> None:
    manifest = json.loads(_read(MANIFEST))

    assert manifest["requirements"] == EXPECTED_RUNTIME_REQUIREMENTS


def test_ci_installs_runtime_dependencies_from_manifest() -> None:
    ci = _read(ROOT / ".github" / "workflows" / "ci.yml")

    assert "manifest.json" in ci
    assert 'json.load(manifest_file)["requirements"]' in ci
    assert 'pip", "install", *requirements' in ci


def test_release_artifact_is_built_from_manifest_directory() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert "cd custom_components/idm_heatpump" in release_workflow
    assert "zip -r ../../idm_heatpump.zip ." in release_workflow
    assert "manifest.json" not in release_workflow.partition("zip -r ../../idm_heatpump.zip .")[2].partition("\n\n")[0]


def test_user_facing_dependency_docs_match_manifest() -> None:
    docs = [
        ROOT / "README.md",
        ROOT / "README_de.md",
        ROOT / "docs" / "wiki" / "Home.md",
        ROOT / "docs" / "wiki" / "_Sidebar.md",
    ]

    for requirement in EXPECTED_RUNTIME_REQUIREMENTS:
        package, version = requirement.split("==", maxsplit=1)
        assert all(package in _read(path) and f"=={version}" in _read(path) for path in docs)
