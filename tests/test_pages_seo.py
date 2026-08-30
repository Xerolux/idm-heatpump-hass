"""Regression tests for the public GitHub Pages search metadata."""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.etree import ElementTree

import pytest

from scripts.build_pages import build_site

PUBLIC_DIR = Path(__file__).resolve().parents[1] / "docs" / "public"
SITE_URL = "https://xerolux.github.io/idm-heatpump-hass/"


@pytest.fixture
def built_public_dir(tmp_path: Path) -> Path:
    """Build the same static artifact that GitHub Pages deploys."""
    output = tmp_path / "site"
    build_site(output)
    return output


def test_homepage_has_search_and_social_metadata(built_public_dir: Path) -> None:
    """The landing page should expose one consistent canonical identity."""
    homepage = (built_public_dir / "index.html").read_text(encoding="utf-8")

    assert "<title>IDM Wärmepumpe in Home Assistant | Modbus TCP Integration</title>" in homepage
    assert '<meta name="google-site-verification" content="' in homepage
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


def test_english_homepage_is_complete_and_indexable(built_public_dir: Path) -> None:
    """English visitors and crawlers should receive a fully localized page."""
    homepage = (built_public_dir / "en" / "index.html").read_text(encoding="utf-8")

    assert '<html lang="en"' in homepage
    assert "<title>IDM Heat Pump for Home Assistant | Modbus TCP Integration</title>" in homepage
    assert f'<link rel="canonical" href="{SITE_URL}en/" />' in homepage
    assert "<h1>IDM heat pump<br /><span>in Home Assistant</span></h1>" in homepage
    assert 'href="../" hreflang="de"' in homepage
    assert "Latest stable version" in homepage
    assert "data-integration-version" in homepage
    assert "data-minimum-home-assistant-version" in homepage
    assert "data-api-version" in homepage
    assert "Mehr als nur Temperaturen" not in homepage
    assert "Diagnose & Lösungen" not in homepage


def test_release_metadata_comes_from_repository_contracts(built_public_dir: Path) -> None:
    """Displayed versions should be injected from manifest and HACS metadata."""
    manifest = json.loads(
        (PUBLIC_DIR.parents[1] / "custom_components" / "idm_heatpump" / "manifest.json").read_text(encoding="utf-8")
    )
    hacs = json.loads((PUBLIC_DIR.parents[1] / "hacs.json").read_text(encoding="utf-8"))
    api_requirement = next(
        requirement for requirement in manifest["requirements"] if requirement.startswith("idm-heatpump-api")
    )
    api_version = api_requirement.rsplit("==", maxsplit=1)[1]
    pages = [
        (built_public_dir / "index.html").read_text(encoding="utf-8"),
        (built_public_dir / "en" / "index.html").read_text(encoding="utf-8"),
    ]

    for page in pages:
        assert f"v{manifest['version']}" in page
        assert f"v{api_version}" in page
        assert f"{hacs['homeassistant']}+" in page

    documentation = (built_public_dir / "docs" / "index.html").read_text(encoding="utf-8")
    assert f"v{manifest['version']}" in documentation
    assert f"{hacs['homeassistant']}+" in documentation


def test_documentation_has_canonical_and_open_graph_urls(built_public_dir: Path) -> None:
    """The documentation shell should identify its own public URL."""
    documentation = (built_public_dir / "docs" / "index.html").read_text(encoding="utf-8")
    docs_url = f"{SITE_URL}docs/"

    assert "<title>IDM Heatpump Dokumentation | Home Assistant</title>" in documentation
    assert f'<link rel="canonical" href="{docs_url}" />' in documentation
    assert f'<meta property="og:url" content="{docs_url}" />' in documentation


def test_crawler_files_reference_all_public_pages(built_public_dir: Path) -> None:
    """Robots and sitemap files should expose the canonical public pages."""
    robots = (built_public_dir / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: *\nAllow: /" in robots
    assert f"Sitemap: {SITE_URL}sitemap.xml" in robots

    sitemap = ElementTree.parse(built_public_dir / "sitemap.xml")
    namespace = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locations = {element.text for element in sitemap.findall("sitemap:url/sitemap:loc", namespace)}
    assert locations == {SITE_URL, f"{SITE_URL}en/", f"{SITE_URL}docs/"}


def test_docs_interface_uses_browser_language_without_a_saved_choice() -> None:
    """Documentation navigation should default to the visitor's browser language."""
    script = (PUBLIC_DIR / "docs" / "docs.js").read_text(encoding="utf-8")
    assert "navigator.language.toLowerCase().startsWith('de') ? 'de' : 'en'" in script
    assert "localStorage.getItem('idm-docs-language') || browserLanguage" in script
