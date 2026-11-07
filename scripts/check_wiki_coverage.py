"""Check reviewed source coverage, bilingual publication and action documentation."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG = "docs/wiki-coverage.json"
SOURCE = "custom_components/idm_heatpump"


def source_digest(root: Path, sources: list[str]) -> str:
    """Hash named source files with normalized newlines on Windows and Linux."""
    digest = hashlib.sha256()
    for source in sorted(sources):
        digest.update(source.encode())
        digest.update(b"\0")
        digest.update((root / source).read_text(encoding="utf-8").encode())
        digest.update(b"\0")
    return digest.hexdigest()


def published_pages(root: Path) -> set[str]:
    """Read the static publication table without importing the site builder."""
    tree = ast.parse((root / "scripts/build_pages.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "DOCUMENTATION_PAGES"
        ):
            return {page["file"] for page in ast.literal_eval(node.value)}
    raise ValueError("Missing DOCUMENTATION_PAGES in scripts/build_pages.py")


def check(root: Path = ROOT, *, update: bool = False) -> list[str]:
    """Report omissions and source changes awaiting an explicit prose review."""
    path = root / CATALOG
    catalog: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    findings: list[str] = []
    covered: set[str] = set()
    published = published_pages(root)
    for group in catalog["features"]:
        label = group["feature"]
        sources = group["sources"]
        if not sources or not group["pages"]:
            findings.append(f"{label}: source files and documentation pages are required")
        covered.update(sources)
        missing = [source for source in sources if not (root / source).is_file()]
        findings.extend(f"{label}: missing source {source}" for source in missing)
        for page in group["pages"]:
            if page not in published:
                findings.append(f"{label}: {page} is not published by Pages")
            for language in ("", "de/"):
                if not (root / "docs/wiki" / language / page).is_file():
                    findings.append(f"{label}: missing wiki page {language}{page}")
        if not missing:
            current = source_digest(root, sources)
            if update:
                group["reviewed_source_sha256"] = current
            elif group.get("reviewed_source_sha256") != current:
                findings.append(f"{label}: source changed; review EN/DE pages before acknowledging --update")

    modules = {p.relative_to(root).as_posix() for p in (root / SOURCE).rglob("*.py")}
    findings.extend(f"Undocumented source module: {source}" for source in sorted(modules - covered))
    # All wiki articles must be published and mirrored, not only feature-map targets.
    articles = {p.name for p in (root / "docs/wiki").glob("*.md") if not p.name.startswith("_")}
    mirrors = {p.name for p in (root / "docs/wiki/de").glob("*.md") if not p.name.startswith("_")}
    for page in sorted(articles | mirrors | published):
        if page not in articles or page not in mirrors:
            findings.append(f"{page}: English and German articles are both required")
        if page not in published:
            findings.append(f"{page}: article is missing from Pages navigation")

    schema = (root / SOURCE / "services.yaml").read_text(encoding="utf-8")
    actions = re.findall(r"^([a-z][a-z0-9_]*):\s*$", schema, re.MULTILINE)
    for language in ("", "de/"):
        reference_path = root / "docs/wiki" / language / "Services.md"
        reference = reference_path.read_text(encoding="utf-8") if reference_path.is_file() else ""
        for action in actions:
            if f"`idm_heatpump.{action}`" not in reference:
                findings.append(f"{language}Services.md: missing action idm_heatpump.{action}")
        home_path = root / "docs/wiki" / language / "Home.md"
        home = home_path.read_text(encoding="utf-8") if home_path.is_file() else ""
        if re.search(r"^#{2,3}\s+(?:New in|Neu in|Available for testing|Zum Testen verfügbar)\b", home, re.MULTILINE):
            findings.append(f"{language}Home.md: use a current feature overview and link release history")

    for page in sorted(articles - {"Changelog.md", "Stability-and-Release-Readiness.md"}):
        for language in ("", "de/"):
            target = root / "docs/wiki" / language / page
            if target.is_file() and re.search(
                r"^#{1,6}.*(?:AI adviser|KI-Anlagenberater|KI-Berater).*\((?:upcoming|kommend|geplant)\)",
                target.read_text(encoding="utf-8"),
                re.MULTILINE,
            ):
                findings.append(f"{language}{page}: AI adviser is available, not upcoming")
    if update:
        path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="acknowledge source reviewed against EN/DE prose")
    args = parser.parse_args(argv)
    findings = check(update=args.update)
    for finding in findings:
        print(finding)
    if not findings:
        print("Wiki source coverage, bilingual publication and action reference are current.")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
