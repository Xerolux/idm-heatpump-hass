"""Contract tests for the project's documentation language.

The repository is developed in a German-speaking context, and German prose kept
leaking into documents the whole world reads.  English is the contract for
everything a contributor or user reads about the project; German stays where it
is a product feature, which is the localized user documentation and the Home
Assistant ``de`` translations.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import check_documentation_language as language

ROOT = Path(__file__).resolve().parents[1]


def _render(hits: list[language.Hit]) -> str:
    return "\n".join(hit.render() for hit in hits)


def test_every_covered_document_is_english() -> None:
    """The contract itself: no German prose in a covered document.

    When this fails, translate the document.  Adding it to ``EXEMPT_FILES``
    is only correct for documentation that is German on purpose, which today
    means ``README_de.md``.
    """
    hits = language.check_all(ROOT)

    assert not hits, (
        "German prose in documents that must be English "
        f"({len({hit.path for hit in hits})} document(s)):\n{_render(hits)}"
    )


def test_open_changelog_sections_are_covered() -> None:
    """The changelog is checked where it is still being written.

    Released sections are history and stay as published; the unreleased entries
    and the section of the version the manifest carries still become release
    notes, so they are covered.
    """
    changelog = (ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
    version = language.current_version(ROOT)

    sections = language.changelog_open_sections(changelog, version)
    headings = [section.splitlines()[0] for _, section in sections]

    assert "## [Unreleased]" in headings
    assert any(version in heading for heading in headings), f"no changelog section for the released {version}"


def test_released_changelog_history_is_left_alone() -> None:
    """A released entry documents what a published version said at the time."""
    changelog = (ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")

    sections = language.changelog_open_sections(changelog, "0.15.0-beta.1")
    covered = "\n".join(section for _, section in sections)

    assert "## [0.14.1]" not in covered
    assert "## [0.15.0-beta.1]" in covered


def test_a_new_document_is_covered_without_being_listed() -> None:
    """Coverage is by default — that is what the German pages slipped past."""
    documents = {path.relative_to(ROOT).as_posix() for path in language.covered_documents(ROOT)}

    assert "AGENTS.md" in documents
    assert "docs/RELEASE_PROCESS.md" in documents
    assert "docs/dev/open-work-audit.md" in documents
    assert ".github/ISSUE_TEMPLATE/bug_report.md" in documents
    # Localized user documentation is German on purpose.
    assert "README_de.md" not in documents


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The pause applies per request.", False),
        ("Die Pause gilt für jede Anfrage und bleibt unverändert.", True),
        # Code, links and identifiers are stripped before the check: German
        # register labels and file names must not fail an English document.
        ("Use `hc_a_und_b` for the circuit.", False),
        ("See [the guide](docs/dev/und-so-weiter.md).", False),
        ("MIT License", False),
        ("| 1999 | Fehlerquittierung | `error_acknowledge` |", False),
    ],
)
def test_detector_separates_prose_from_identifiers(text: str, expected: bool) -> None:
    assert bool(language.german_hits(text, "sample.md")) is expected


def test_fenced_code_blocks_are_not_prose() -> None:
    text = "Example:\n\n```text\nfür die Verbindung und den Port\n```\n\nThat is all.\n"

    assert not language.german_hits(text, "sample.md")
