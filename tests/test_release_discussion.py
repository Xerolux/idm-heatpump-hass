"""Tests for automated release announcements in GitHub Discussions."""

from __future__ import annotations

from scripts import publish_release_discussion


def test_release_discussion_body_links_release_help_and_bug_report() -> None:
    body = publish_release_discussion._build_body(
        repository="Xerolux/idm-heatpump-hass",
        tag="v1.2.3",
        release_notes="## Changes\n\n- Better polling",
        server_url="https://github.com",
    )

    assert "<!-- idm-release:v1.2.3 -->" in body
    assert "/releases/tag/v1.2.3" in body
    assert "/discussions/categories/q-a" in body
    assert "/issues/new?template=bug_report.md" in body
    assert "Better polling" in body


def test_release_discussion_category_selection_prefers_configured_slug() -> None:
    categories = [
        {"id": "one", "name": "Announcements", "slug": "announcements"},
        {"id": "two", "name": "Release News", "slug": "release-news"},
    ]

    selected = publish_release_discussion._select_category(categories, "release-news")

    assert selected == categories[1]


def test_release_discussion_category_selection_falls_back_to_announcement_name() -> None:
    categories = [
        {"id": "one", "name": "Ankündigungen", "slug": "neuigkeiten"},
    ]

    selected = publish_release_discussion._select_category(categories, "announcements")

    assert selected == categories[0]
