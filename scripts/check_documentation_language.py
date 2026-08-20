#!/usr/bin/env python3
"""Check that the project's living documents are written in English.

The repository is developed in a German-speaking context, which is why German
prose kept leaking into documents the whole world reads: changelog entries,
release notes, wiki pages and developer notes.  English is the contract for
everything a contributor or user reads about the project; German stays where it
is a *product feature* — the localized user documentation and the Home Assistant
`de` translations.

The check is deliberately blunt: it looks for German function words, which are
the part of a sentence a translation can never drop.  Code spans, fenced blocks,
link targets and inline HTML are stripped first, so German identifiers, entity
names and register labels inside code do not trip it.

Usage::

    python scripts/check_documentation_language.py            # check everything
    python scripts/check_documentation_language.py --json     # machine readable
    python scripts/check_documentation_language.py docs/a.md  # check some files

Exit code is 1 when a covered document contains German prose.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Every Markdown document in the repository is covered unless it is exempt
# below.  Coverage by default is the point: a new document must not be able to
# slip in unnoticed, which is exactly how the German pages accumulated.
COVERED_GLOBS = ("*.md", "docs/**/*.md", ".github/**/*.md")

# Documents that are German on purpose.  Everything here is either localized
# user documentation or a frozen record.
EXEMPT_FILES = (
    # The German README is the localized counterpart of README.md.
    "README_de.md",
)

EXEMPT_PREFIXES = (
    # Released history.  A changelog entry documents what a published version
    # said at the time; rewriting it would falsify the record.  New entries are
    # covered through CHANGELOG_OPEN_SECTIONS below.
    "docs/CHANGELOG.md",
    "docs/wiki/Changelog.md",
)

SKIP_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
}

# German function words that do not occur in English text.  Words that collide
# with English ("die", "man", "war", "hat", "ist", "in", "an", "so") are left
# out on purpose, as is "mit", which would match the "MIT" license.  What
# remains is enough: German prose cannot be written without it.
GERMAN_MARKERS = (
    "aber",
    "auch",
    "auf",
    "aus",
    "beim",
    "bereits",
    "bleibt",
    "damit",
    "dann",
    "das",
    "dass",
    "dem",
    "den",
    "der",
    "des",
    "diese",
    "diesem",
    "diesen",
    "dieser",
    "dieses",
    "durch",
    "eine",
    "einem",
    "einen",
    "einer",
    "eines",
    "für",
    "gibt",
    "immer",
    "jede",
    "jeden",
    "jeder",
    "kein",
    "keine",
    "können",
    "muss",
    "müssen",
    "nicht",
    "noch",
    "nur",
    "oder",
    "ohne",
    "schon",
    "sein",
    "sich",
    "sind",
    "sowie",
    "über",
    "und",
    "vom",
    "von",
    "wenn",
    "werden",
    "wird",
    "wurde",
    "wurden",
    "zum",
    "zur",
    "zwischen",
)

# Case-sensitive on purpose: an English sentence may start with "Und"? It may
# not — but "Der", "Das" and friends do appear as parts of German proper nouns
# that survive translation ("Der Spiegel").  Sentence-initial German is caught
# through the lower-case markers in the rest of the sentence.
_MARKER_RE = re.compile(rf"(?<![\w-])(?:{'|'.join(GERMAN_MARKERS)})(?![\w-])")

_CODE_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_STRIPPERS = (
    re.compile(r"`[^`]*`"),  # inline code
    re.compile(r"<[^>]+>"),  # inline HTML and autolinks
    re.compile(r"\]\([^)]*\)"),  # link targets, keeping the link text
    re.compile(r"https?://\S+"),  # bare URLs
)


@dataclass(frozen=True)
class Hit:
    """One line of German prose in a covered document."""

    path: str
    line: int
    words: tuple[str, ...]
    text: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {', '.join(sorted(set(self.words)))} — {self.text.strip()[:100]}"


def strip_code(line: str) -> str:
    """Remove the parts of a Markdown line that are never prose."""
    for pattern in _STRIPPERS:
        line = pattern.sub(" ", line)
    return line


def german_hits(text: str, path: str) -> list[Hit]:
    """Return the German prose lines of one Markdown document."""
    hits: list[Hit] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if _CODE_FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        words = _MARKER_RE.findall(strip_code(line))
        if words:
            hits.append(Hit(path=path, line=number, words=tuple(words), text=line))
    return hits


_HEADING_RE = re.compile(r"^## \[?v?(?P<version>[^\]\s]+)\]?")


def changelog_open_sections(text: str, current_version: str) -> list[tuple[int, str]]:
    """Return the still-open sections of a changelog with their first line number.

    Open are the unreleased entries and the notes of the version the manifest
    carries.  Everything below is history: a released changelog entry documents
    what a published version said at the time, and rewriting it would falsify
    the record.  What a maintainer writes *now* still becomes release notes, so
    that part must be English.
    """
    lines = text.splitlines()
    headings = [(index, _HEADING_RE.match(line)) for index, line in enumerate(lines)]
    starts = [(index, match.group("version")) for index, match in headings if match]
    if not starts:
        return [(1, text)]

    open_versions = {"Unreleased", current_version}
    sections: list[tuple[int, str]] = []
    seen: set[str] = set()
    for position, (index, version) in enumerate(starts):
        if version not in open_versions or version in seen:
            continue
        seen.add(version)
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        sections.append((index + 1, "\n".join(lines[index:end])))
    return sections


def current_version(root: Path = ROOT) -> str:
    manifest = root / "custom_components" / "idm_heatpump" / "manifest.json"
    return str(json.loads(manifest.read_text(encoding="utf-8"))["version"])


def is_exempt(relative: str) -> bool:
    return relative in EXEMPT_FILES or relative.startswith(EXEMPT_PREFIXES)


def covered_documents(root: Path = ROOT) -> list[Path]:
    """Return every Markdown document the language contract covers."""
    found: dict[str, Path] = {}
    for pattern in COVERED_GLOBS:
        for path in root.glob(pattern):
            if any(part in SKIP_DIRECTORIES for part in path.parts):
                continue
            relative = path.relative_to(root).as_posix()
            if not path.is_file() or is_exempt(relative):
                continue
            found[relative] = path
    return [found[key] for key in sorted(found)]


def check_document(path: Path, root: Path = ROOT) -> list[Hit]:
    relative = path.relative_to(root).as_posix()
    return german_hits(path.read_text(encoding="utf-8"), relative)


def check_changelog(path: Path, root: Path = ROOT, *, version: str | None = None) -> list[Hit]:
    """Check only the still-open sections of a changelog."""
    relative = path.relative_to(root).as_posix()
    sections = changelog_open_sections(
        path.read_text(encoding="utf-8"),
        version if version is not None else current_version(root),
    )
    return [
        Hit(path=hit.path, line=hit.line + offset - 1, words=hit.words, text=hit.text)
        for offset, section in sections
        for hit in german_hits(section, relative)
    ]


def check_all(root: Path = ROOT) -> list[Hit]:
    hits: list[Hit] = []
    for path in covered_documents(root):
        hits.extend(check_document(path, root))
    version = current_version(root)
    for relative in ("docs/CHANGELOG.md", "docs/wiki/Changelog.md"):
        changelog = root / relative
        if changelog.exists():
            hits.extend(check_changelog(changelog, root, version=version))
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", type=Path, help="documents to check (default: the whole contract)")
    parser.add_argument("--json", action="store_true", help="emit the findings as JSON")
    args = parser.parse_args(argv)

    if args.paths:
        hits: list[Hit] = []
        for path in args.paths:
            resolved = path if path.is_absolute() else (Path.cwd() / path)
            hits.extend(german_hits(resolved.read_text(encoding="utf-8"), path.as_posix()))
    else:
        hits = check_all()

    if args.json:
        print(json.dumps([hit.__dict__ for hit in hits], indent=2, ensure_ascii=False))
    elif hits:
        print(f"German prose in {len({hit.path for hit in hits})} document(s):")
        for hit in hits:
            print(f"  {hit.render()}")
        print("\nDocumentation is English (see docs/RELEASE_PROCESS.md, 'Language').")
    else:
        print("All covered documents are English.")

    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
