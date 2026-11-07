"""Exercise documentation drift detection independently of current wiki prose."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import check_wiki_coverage as check


@pytest.fixture
def wiki_tree(tmp_path: Path) -> Path:
    files = {
        f"{check.SOURCE}/sample.py": "VALUE = 1\n",
        f"{check.SOURCE}/services.yaml": "sample_action:\n  fields:\n    entry_id:\n      required: true\n",
        "scripts/build_pages.py": 'DOCUMENTATION_PAGES: tuple = ({"file": "Home.md"}, {"file": "Services.md"})\n',
        "docs/wiki/Home.md": "# Home\n\n### Current features\n",
        "docs/wiki/de/Home.md": "# Übersicht\n",
        "docs/wiki/Services.md": "# Actions\n\n## Sample\n`idm_heatpump.sample_action`\n",
        "docs/wiki/de/Services.md": "# Aktionen\n\n## Sample\n`idm_heatpump.sample_action`\n",
    }
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (tmp_path / check.CATALOG).write_text(
        json.dumps(
            {
                "features": [
                    {
                        "feature": "Example",
                        "sources": [f"{check.SOURCE}/sample.py", f"{check.SOURCE}/services.yaml"],
                        "pages": ["Home.md", "Services.md"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert check.check(tmp_path, update=True) == []
    return tmp_path


def test_repository_wiki_is_current() -> None:
    assert check.check() == []


def test_source_change_requires_review_without_rewriting_prose(wiki_tree: Path) -> None:
    source = wiki_tree / check.SOURCE / "sample.py"
    source.write_text("VALUE = 2\n", encoding="utf-8")
    home = wiki_tree / "docs/wiki/Home.md"
    before = home.read_bytes()
    assert any("source changed" in finding for finding in check.check(wiki_tree))
    assert check.check(wiki_tree, update=True) == []
    assert check.check(wiki_tree) == []
    assert home.read_bytes() == before


@pytest.mark.parametrize("relative", ["new_feature.py", "new_package/new_feature.py"])
def test_new_module_cannot_be_acknowledged_without_documentation(wiki_tree: Path, relative: str) -> None:
    source = wiki_tree / check.SOURCE / relative
    source.parent.mkdir(exist_ok=True)
    source.write_text("ENABLED = True\n", encoding="utf-8")
    assert any("Undocumented source module" in finding for finding in check.check(wiki_tree, update=True))


def test_removed_source_is_reported(wiki_tree: Path) -> None:
    (wiki_tree / check.SOURCE / "sample.py").unlink()
    assert any("missing source" in finding for finding in check.check(wiki_tree))


@pytest.mark.parametrize("language", ["", "de/"])
def test_new_service_requires_both_references(wiki_tree: Path, language: str) -> None:
    (wiki_tree / check.SOURCE / "services.yaml").write_text("sample_action:\nnew_action:\n", encoding="utf-8")
    reference = wiki_tree / "docs/wiki" / language / "Services.md"
    reference.write_text(reference.read_text(encoding="utf-8") + "`idm_heatpump.new_action`\n", encoding="utf-8")
    findings = check.check(wiki_tree, update=True)
    assert any("missing action idm_heatpump.new_action" in finding for finding in findings)
    assert not any(f"{language}Services.md: missing action" == finding.split(" idm_")[0] for finding in findings)


def test_missing_mirror_and_unpublished_article_are_detected(wiki_tree: Path) -> None:
    (wiki_tree / "docs/wiki/de/Home.md").unlink()
    (wiki_tree / "docs/wiki/Hidden.md").write_text("# Hidden\n", encoding="utf-8")
    findings = check.check(wiki_tree)
    assert any("missing wiki page de/Home.md" in finding for finding in findings)
    assert any("Hidden.md: article is missing from Pages navigation" in finding for finding in findings)


@pytest.mark.parametrize("heading", ["### New in 0.19.0", "### Neu in 0.19.0"])
def test_home_must_not_accumulate_historical_announcements(wiki_tree: Path, heading: str) -> None:
    (wiki_tree / "docs/wiki/Home.md").write_text(heading, encoding="utf-8")
    assert any("current feature overview" in finding for finding in check.check(wiki_tree))


def test_upcoming_adviser_claim_is_rejected_but_release_history_is_preserved(wiki_tree: Path) -> None:
    (wiki_tree / "docs/wiki/Services.md").write_text(
        "`idm_heatpump.sample_action`\n\n## Experimental AI adviser (upcoming)\n", encoding="utf-8"
    )
    assert any("AI adviser is available" in finding for finding in check.check(wiki_tree))
    for language in ("", "de/"):
        (wiki_tree / "docs/wiki" / language / "Changelog.md").write_text(
            "## Experimental AI adviser (upcoming)\n", encoding="utf-8"
        )
    assert not any("Changelog.md: AI adviser" in finding for finding in check.check(wiki_tree))


def test_fingerprint_ignores_platform_line_endings(wiki_tree: Path) -> None:
    source = wiki_tree / check.SOURCE / "sample.py"
    before = check.source_digest(wiki_tree, [f"{check.SOURCE}/sample.py"])
    source.write_bytes(b"VALUE = 1\r\n")
    assert check.source_digest(wiki_tree, [f"{check.SOURCE}/sample.py"]) == before


@pytest.mark.parametrize("workflow", ["python-quality", "dependency-update", "release", "pages"])
def test_publishing_and_quality_workflows_check_wiki_coverage(workflow: str) -> None:
    text = (check.ROOT / f".github/workflows/{workflow}.yml").read_text(encoding="utf-8")
    assert "python scripts/check_wiki_coverage.py" in text
    assert "check_wiki_coverage.py --update" not in text
