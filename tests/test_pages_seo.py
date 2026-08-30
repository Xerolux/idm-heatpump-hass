"""Regression tests for the public GitHub Pages search metadata."""

from __future__ import annotations

import json
import re
import struct
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from xml.etree import ElementTree

import pytest

from scripts.build_pages import DOCUMENTATION_PAGES, build_site

PUBLIC_DIR = Path(__file__).resolve().parents[1] / "docs" / "public"
SITE_URL = "https://xerolux.github.io/idm-heatpump-hass/"


def _structured_data(document: str) -> list[dict[str, object]]:
    return [
        json.loads(match)
        for match in re.findall(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            document,
            flags=re.DOTALL,
        )
    ]


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
    assert f'<meta property="og:image" content="{SITE_URL}assets/social-card.png" />' in homepage
    assert '<meta name="twitter:card" content="summary_large_image" />' in homepage
    assert "<h1>IDM Wärmepumpe<br /><span>in Home Assistant</span></h1>" in homepage
    assert "/releases/latest" in homepage
    assert "/releases/tag/v0.8.2" not in homepage

    structured_data = _structured_data(homepage)
    website_data = next(item for item in structured_data if item["@type"] == "WebSite")
    assert website_data["@context"] == "https://schema.org"
    assert website_data["url"] == SITE_URL
    assert website_data["inLanguage"] == "de"

    software_data = next(item for item in structured_data if item["@type"] == "SoftwareApplication")
    manifest = json.loads(
        (PUBLIC_DIR.parents[1] / "custom_components" / "idm_heatpump" / "manifest.json").read_text(encoding="utf-8")
    )
    hacs = json.loads((PUBLIC_DIR.parents[1] / "hacs.json").read_text(encoding="utf-8"))
    assert software_data["softwareVersion"] == manifest["version"]
    assert software_data["operatingSystem"] == f"Home Assistant {hacs['homeassistant']} oder neuer"
    assert software_data["offers"] == {"@type": "Offer", "price": "0", "priceCurrency": "EUR"}
    assert software_data["isAccessibleForFree"] is True


def test_english_homepage_is_complete_and_indexable(built_public_dir: Path) -> None:
    """English visitors and crawlers should receive a fully localized page."""
    homepage = (built_public_dir / "en" / "index.html").read_text(encoding="utf-8")

    assert '<html lang="en"' in homepage
    assert "<title>IDM Heat Pump for Home Assistant | Modbus TCP Integration</title>" in homepage
    assert f'<link rel="canonical" href="{SITE_URL}en/" />' in homepage
    assert "<h1>IDM heat pump<br /><span>in Home Assistant</span></h1>" in homepage
    assert 'href="../" hreflang="de"' in homepage
    assert "Latest stable version" in homepage
    assert '<meta name="twitter:card" content="summary_large_image" />' in homepage
    assert "data-integration-version" in homepage
    assert "data-minimum-home-assistant-version" in homepage
    assert "data-api-version" in homepage
    assert "Mehr als nur Temperaturen" not in homepage
    assert "Diagnose & Lösungen" not in homepage
    software_data = next(item for item in _structured_data(homepage) if item["@type"] == "SoftwareApplication")
    hacs = json.loads((PUBLIC_DIR.parents[1] / "hacs.json").read_text(encoding="utf-8"))
    assert software_data["operatingSystem"] == f"Home Assistant {hacs['homeassistant']} or newer"
    assert software_data["inLanguage"] == "en"


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


def test_documentation_pages_are_static_unique_and_indexable(built_public_dir: Path) -> None:
    """Every documentation topic should have crawlable content and metadata."""
    titles: set[str] = set()
    descriptions: set[str] = set()

    for page in DOCUMENTATION_PAGES:
        relative_path = (
            Path("docs/index.html") if page["slug"] == "home" else Path("docs") / page["slug"] / "index.html"
        )
        documentation = (built_public_dir / relative_path).read_text(encoding="utf-8")
        docs_url = f"{SITE_URL}docs/" if page["slug"] == "home" else f"{SITE_URL}docs/{page['slug']}/"
        page_title = f"{page['title']} | IDM Heatpump for Home Assistant"

        assert f"<title>{page_title}</title>" in documentation
        assert f'<meta name="description" content="{page["description"]}" />' in documentation
        assert f'<link rel="canonical" href="{docs_url}" />' in documentation
        assert f'<meta property="og:url" content="{docs_url}" />' in documentation
        assert f'<link rel="icon" href="{SITE_URL}assets/favicon.svg" type="image/svg+xml" />' in documentation
        assert f'data-rendered-slug="{page["slug"]}"' in documentation
        assert "<h1 id=" in documentation
        assert "article-loading" not in re.search(
            r'<article class="article-content".*?</article>', documentation, flags=re.DOTALL
        ).group(0)
        assert '<meta name="twitter:card" content="summary_large_image" />' in documentation
        if page["slug"] == "home":
            assert 'src="images/heatpump.png"' in documentation

        graph = _structured_data(documentation)[0]["@graph"]
        web_page = next(item for item in graph if item["@type"] == "WebPage")
        breadcrumbs = next(item for item in graph if item["@type"] == "BreadcrumbList")
        assert web_page["url"] == docs_url
        assert web_page["description"] == page["description"]
        assert breadcrumbs["itemListElement"][-1]["item"] == docs_url
        titles.add(page_title)
        descriptions.add(page["description"])

    assert len(titles) == len(DOCUMENTATION_PAGES)
    assert len(descriptions) == len(DOCUMENTATION_PAGES)


def test_crawler_files_reference_all_public_pages(built_public_dir: Path) -> None:
    """Robots and sitemap files should expose the canonical public pages."""
    robots = (built_public_dir / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: *\nAllow: /" in robots
    assert f"Sitemap: {SITE_URL}sitemap.xml" in robots

    sitemap = ElementTree.parse(built_public_dir / "sitemap.xml")
    namespace = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locations = {element.text for element in sitemap.findall("sitemap:url/sitemap:loc", namespace)}
    expected = {SITE_URL, f"{SITE_URL}en/", f"{SITE_URL}docs/"}
    expected.update(f"{SITE_URL}docs/{page['slug']}/" for page in DOCUMENTATION_PAGES if page["slug"] != "home")
    assert locations == expected


def test_docs_interface_uses_browser_language_without_a_saved_choice() -> None:
    """Documentation navigation should default to the visitor's browser language."""
    script = (PUBLIC_DIR / "docs" / "docs.js").read_text(encoding="utf-8")
    assert "navigator.language.toLowerCase().startsWith('de') ? 'de' : 'en'" in script
    assert "localStorage.getItem('idm-docs-language') || browserLanguage" in script


def test_docs_interface_uses_real_paths_and_keeps_legacy_hash_compatibility() -> None:
    """Navigation should use crawlable paths while old hash links still resolve."""
    script = (PUBLIC_DIR / "docs" / "docs.js").read_text(encoding="utf-8")
    script_slugs = re.findall(r"\{ slug: '([^']+)', file:", script)

    assert script_slugs == [page["slug"] for page in DOCUMENTATION_PAGES]
    assert "const docsBasePath = docsRootUrl.pathname" in script
    assert "history.replaceState(null, '', routeHref(page.slug, anchor))" in script
    assert "window.addEventListener('popstate', loadRoute)" in script
    assert "window.addEventListener('hashchange', loadRoute)" not in script
    stylesheet = (PUBLIC_DIR / "docs" / "docs.css").read_text(encoding="utf-8")
    assert ".content-language[hidden] { display: none; }" in stylesheet


def test_social_card_is_a_1200_by_630_png(built_public_dir: Path) -> None:
    """Social networks should receive a supported, large preview image."""
    image = (built_public_dir / "assets" / "social-card.png").read_bytes()

    assert image[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", image[16:24])
    assert (width, height) == (1200, 630)


def test_public_links_no_longer_publish_hash_routes() -> None:
    """Repository entry points should link to canonical documentation URLs."""
    repository_root = PUBLIC_DIR.parents[1]
    paths = (
        repository_root / "README.md",
        repository_root / "README_de.md",
        repository_root / "custom_components" / "idm_heatpump" / "manifest.json",
        PUBLIC_DIR / "index.html",
        PUBLIC_DIR / "docs" / "index.html",
    )

    for path in paths:
        assert "docs/#/" not in path.read_text(encoding="utf-8")


def test_generated_relative_links_resolve_inside_pages_artifact(built_public_dir: Path) -> None:
    """Static navigation, images, styles and scripts should not produce 404s."""
    test_origin = "https://pages.test/"
    missing: list[str] = []

    for document_path in built_public_dir.rglob("*.html"):
        document = document_path.read_text(encoding="utf-8")
        relative_document = document_path.relative_to(built_public_dir).as_posix()
        base_url = urljoin(test_origin, relative_document)
        for reference in re.findall(r'\b(?:href|src)="([^"]+)"', document):
            if reference.startswith(("#", "mailto:", "tel:")):
                continue
            resolved = urlparse(urljoin(base_url, reference))
            if resolved.netloc != "pages.test":
                continue
            target = unquote(resolved.path).lstrip("/")
            target_path = built_public_dir / target
            if resolved.path.endswith("/"):
                target_path /= "index.html"
            if not target_path.is_file():
                missing.append(f"{relative_document}: {reference} -> {target}")

    assert not missing, "Missing generated Pages targets:\n" + "\n".join(missing)
