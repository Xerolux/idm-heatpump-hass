"""Regression tests for the public GitHub Pages search metadata."""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.etree import ElementTree

PUBLIC_DIR = Path(__file__).resolve().parents[1] / "docs" / "public"
SITE_URL = "https://xerolux.github.io/idm-heatpump-hass/"


def test_homepage_has_search_and_social_metadata() -> None:
    """The landing page should expose one consistent canonical identity."""
    homepage = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")

    assert "<title>IDM Wärmepumpe in Home Assistant | Modbus TCP Integration</title>" in homepage
    assert f'<link rel="canonical" href="{SITE_URL}" />' in homepage
    assert f'<meta property="og:url" content="{SITE_URL}" />' in homepage
    assert "<h1>IDM Wärmepumpe<br /><span>in Home Assistant</span></h1>" in homepage
    assert "/releases/latest" in homepage
    assert "/releases/tag/v0.8.2" not in homepage

    json_ld_match = re.search(
        r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
        homepage,
        flags=re.DOTALL,
    )
    assert json_ld_match is not None
    website_data = json.loads(json_ld_match.group(1))
    assert website_data["@context"] == "https://schema.org"
    assert website_data["@type"] == "WebSite"
    assert website_data["url"] == SITE_URL
    assert website_data["inLanguage"] == "de"


def test_documentation_has_canonical_and_open_graph_urls() -> None:
    """The documentation shell should identify its own public URL."""
    documentation = (PUBLIC_DIR / "docs" / "index.html").read_text(encoding="utf-8")
    docs_url = f"{SITE_URL}docs/"

    assert "<title>IDM Heatpump Dokumentation | Home Assistant</title>" in documentation
    assert f'<link rel="canonical" href="{docs_url}" />' in documentation
    assert f'<meta property="og:url" content="{docs_url}" />' in documentation


def test_crawler_files_reference_all_public_pages() -> None:
    """Robots and sitemap files should expose the canonical public pages."""
    robots = (PUBLIC_DIR / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: *\nAllow: /" in robots
    assert f"Sitemap: {SITE_URL}sitemap.xml" in robots

    sitemap = ElementTree.parse(PUBLIC_DIR / "sitemap.xml")
    namespace = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locations = {element.text for element in sitemap.findall("sitemap:url/sitemap:loc", namespace)}
    assert locations == {SITE_URL, f"{SITE_URL}docs/"}
