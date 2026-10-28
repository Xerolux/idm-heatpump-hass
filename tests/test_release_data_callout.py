"""Execute the real release-note generator for automatic and curated notes."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKER = "> **Help improve IDM Heatpump: share a diagnostic capture.**"


@pytest.mark.parametrize("mode", ["changelog", "curated", "already_present"])
def test_release_generator_keeps_one_data_request(tmp_path: Path, mode: str) -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    generator = workflow.split("      - name: Generate release notes\n", 1)[1]
    code = textwrap.dedent(generator.split("          python - <<'PY'\n", 1)[1].split("\n          PY", 1)[0])
    docs = tmp_path / "docs"
    docs.mkdir()
    callout = (ROOT / "docs/DATA-DONATION-CALLOUT.md").read_text(encoding="utf-8")
    (docs / "DATA-DONATION-CALLOUT.md").write_text(callout, encoding="utf-8")
    notes = "## [9.9.9]\n\nRelease introduction.\n\n### ⚠️ Upgrade notes\n\n- Rollback is safe."
    curated = "" if mode == "changelog" else notes
    if mode == "already_present":
        curated = notes.replace("### ⚠️", callout + "\n### ⚠️")
    (docs / "CHANGELOG.md").write_text(notes + "\n\n## [9.9.8]\nOld release.", encoding="utf-8")
    env = {
        **os.environ,
        "VERSION": "9.9.9",
        "TAG": "v9.9.9",
        "PREVIOUS_TAG": "v9.9.8",
        "CURATED_RELEASE_NOTES": curated,
        "REPOSITORY_URL": "https://github.com/Xerolux/idm-heatpump-hass",
    }
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, check=True, capture_output=True)
    result = (tmp_path / "temp_release_notes.md").read_text(encoding="utf-8")
    assert result.count(MARKER) == 1
    assert result.index(MARKER) < result.index("### ⚠️ Upgrade notes")
    assert "https://idmtools.xerolux.de/" in result
    assert "voluntary" in result and "only to" in result
    assert "30 days" in " ".join(result.replace(">", "").split())
    assert "complete anonymity is not guaranteed" in result
    assert "Leave a star on GitHub" in result
    assert "### ☕ Support the project" in result
    assert "v9.9.8...v9.9.9" in result
