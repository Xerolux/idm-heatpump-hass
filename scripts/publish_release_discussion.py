"""Publish an idempotent GitHub Discussion for a completed release."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

GRAPHQL_URL = "https://api.github.com/graphql"
MARKER_PREFIX = "<!-- idm-release:"


def _graphql(
    query: str,
    variables: dict[str, object],
    *,
    token: str,
) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode()
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "idm-heatpump-release-discussion",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        details = error.read().decode(errors="replace")
        raise RuntimeError(f"GitHub GraphQL request failed: {error.code} {details}") from error

    if errors := result.get("errors"):
        raise RuntimeError(f"GitHub GraphQL errors: {json.dumps(errors)}")
    return result["data"]


def _build_body(
    *,
    repository: str,
    tag: str,
    release_notes: str,
    server_url: str,
) -> str:
    release_url = f"{server_url}/{repository}/releases/tag/{tag}"
    discussions_url = f"{server_url}/{repository}/discussions/categories/q-a"
    issues_url = f"{server_url}/{repository}/issues/new?template=bug_report.md"
    marker = f"{MARKER_PREFIX}{tag} -->"
    return f"""{marker}

Die neue Version **{tag}** ist verfügbar.

➡️ **[Release öffnen und herunterladen]({release_url})**

{release_notes.strip()}

---

### Feedback

- Fragen zur Einrichtung oder Nutzung bitte in [Q&A]({discussions_url}) stellen.
- Reproduzierbare Fehler bitte als [Bug-Report]({issues_url}) melden.
"""


def _select_category(
    categories: list[dict[str, str]],
    preferred_slug: str,
) -> dict[str, str] | None:
    for category in categories:
        if category["slug"] == preferred_slug:
            return category

    announcement_names = {"announcement", "announcements", "ankündigungen"}
    for category in categories:
        if category["name"].strip().casefold() in announcement_names:
            return category
    return None


def main() -> int:
    token = os.environ["GITHUB_TOKEN"]
    repository = os.environ["GITHUB_REPOSITORY"]
    tag = os.environ["RELEASE_TAG"]
    release_notes_path = Path(os.environ["RELEASE_NOTES_PATH"])
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    preferred_slug = os.environ.get("DISCUSSION_CATEGORY_SLUG", "announcements").strip()
    is_prerelease = os.environ.get("RELEASE_IS_PRERELEASE", "false") == "true"

    owner, name = repository.split("/", maxsplit=1)
    marker = f"{MARKER_PREFIX}{tag} -->"
    data = _graphql(
        """
        query ReleaseDiscussionContext($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            id
            discussionCategories(first: 25) {
              nodes { id name slug }
            }
            discussions(first: 100, orderBy: {field: CREATED_AT, direction: DESC}) {
              nodes { body }
            }
          }
        }
        """,
        {"owner": owner, "name": name},
        token=token,
    )["repository"]

    if any(marker in discussion["body"] for discussion in data["discussions"]["nodes"]):
        print(f"Release discussion for {tag} already exists; nothing to do.")
        return 0

    category = _select_category(data["discussionCategories"]["nodes"], preferred_slug)
    if category is None:
        available = ", ".join(item["slug"] for item in data["discussionCategories"]["nodes"])
        print(
            "::warning::Release discussion was not created. "
            f"Category slug {preferred_slug!r} is missing. Available: {available}"
        )
        return 0

    title_prefix = "🧪 Testversion" if is_prerelease else "🚀 Neues Release"
    body = _build_body(
        repository=repository,
        tag=tag,
        release_notes=release_notes_path.read_text(encoding="utf-8"),
        server_url=server_url,
    )
    created = _graphql(
        """
        mutation CreateReleaseDiscussion($input: CreateDiscussionInput!) {
          createDiscussion(input: $input) {
            discussion { url }
          }
        }
        """,
        {
            "input": {
                "repositoryId": data["id"],
                "categoryId": category["id"],
                "title": f"{title_prefix}: {tag}",
                "body": body,
            }
        },
        token=token,
    )
    url = created["createDiscussion"]["discussion"]["url"]
    print(f"Published release discussion: {url}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"::error::{error}")
        sys.exit(1)
