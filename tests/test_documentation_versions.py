"""Regression checks for current documentation and immutable release history."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import check_documentation_versions as check


def test_repository_documentation_matches_manifest() -> None:
    assert check.synchronize(check.ROOT) == []


def test_update_preserves_history_and_detects_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "custom_components/idm_heatpump/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"version": "9.0.0-b1", "requirements": ["idm-heatpump-api[web]==8.0.0"]}), encoding="utf-8"
    )
    document = tmp_path / "current.md"
    original = "Current `1.0.0`\nidm-heatpump-api[web]==2.0.0\nHistory idm-heatpump-api==1.0.0\n"
    document.write_text(original, encoding="utf-8")
    monkeypatch.setattr(check.pins, "PIN_DOCUMENTS", ("current.md",))
    monkeypatch.setattr(check.pins, "BARE_VERSION_STATEMENTS", {})
    monkeypatch.setattr(check.pins, "HISTORY_STATEMENTS", {"current.md": (r"History idm-heatpump-api==1\.0\.0",)})
    monkeypatch.setattr(check, "SOURCE_VERSION_PATTERNS", {"current.md": r"(?<=Current `)" + check.VERSION + r"(?=`)"})
    assert len(check.synchronize(tmp_path)) == 2
    assert document.read_text(encoding="utf-8") == original
    check.synchronize(tmp_path, update=True)
    assert check.synchronize(tmp_path) == []
    assert "History idm-heatpump-api==1.0.0" in document.read_text(encoding="utf-8")
    document.write_text("Missing claim\n", encoding="utf-8")
    assert "expected exactly one" in check.synchronize(tmp_path)[0]
    document.unlink()
    assert "missing current documentation" in check.synchronize(tmp_path)[0]


@pytest.mark.parametrize("workflow", ["python-quality", "dependency-update", "release", "pages"])
def test_workflows_enforce_documentation_consistency(workflow: str) -> None:
    text = (check.ROOT / f".github/workflows/{workflow}.yml").read_text(encoding="utf-8")
    assert "python scripts/check_documentation_versions.py" in text
    if workflow == "dependency-update":
        assert "python scripts/check_documentation_versions.py --update" in text
    if workflow == "pages":
        assert text.index("check_documentation_versions.py\n") < text.index("Build Pages artifact")
