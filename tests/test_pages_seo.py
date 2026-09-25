"""Regression tests for the public GitHub Pages search metadata."""

from __future__ import annotations

import html
import json
import re
import struct
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from xml.etree import ElementTree

import pytest

from scripts import build_pages
from scripts.build_pages import (
    DOCUMENTATION_PAGES,
    GERMAN_DOCUMENTATION_PAGES,
    build_site,
)

PUBLIC_DIR = Path(__file__).resolve().parents[1] / "docs" / "public"
SITE_URL = "https://xerolux.github.io/idm-heatpump-hass/"


@pytest.mark.parametrize(
    ("version", "label", "channel"),
    [
        ("0.17.2-b6", "Beta-Version", "Beta"),
        ("0.17.2-beta.7", "Beta-Version", "Beta"),
        ("0.17.2-rc.1", "Vorabversion", "Prerelease"),
        ("0.17.2", "Aktuelle stabile Version", "Stable"),
    ],
)
def test_download_channel_and_destination_match_displayed_version(
    monkeypatch: pytest.MonkeyPatch, version: str, label: str, channel: str
) -> None:
    monkeypatch.setattr(build_pages, "_metadata", lambda: (version, "2.1.2", "2026.8.1"))
    page = build_pages._inject_metadata((PUBLIC_DIR / "index.html").read_text(encoding="utf-8"))
    assert f"data-release-label>{label}</small>" in page
    assert f"data-release-channel>{channel}</span>" in page
    assert f'data-release-download href="https://github.com/Xerolux/idm-heatpump-hass/releases/tag/v{version}"' in page


def test_new_feature_links_resolve_to_built_documentation(built_public_dir: Path) -> None:
    for relative in (Path("index.html"), Path("en/index.html")):
        page = (built_public_dir / relative).read_text(encoding="utf-8")
        section = re.search(r'<section[^>]+id="smart">(.*?)</section>', page, re.DOTALL)
        assert section is not None
        for href in re.findall(r'href="([^"]+)"', section.group(1)):
            parsed = urlparse(href)
            target = (built_public_dir / relative.parent / unquote(parsed.path) / "index.html").resolve()
            assert target.is_relative_to(built_public_dir.resolve())
            assert target.is_file(), href
            if parsed.fragment:
                assert f'id="{parsed.fragment}"' in target.read_text(encoding="utf-8"), href
        if relative.parts[0] == "en":
            assert "Write-enabled features" in section.group(1)
            assert "Schreibende Funktionen" not in section.group(1)


def _structured_data(document: str) -> list[dict[str, object]]:
    return [
        json.loads(match)
        for match in re.findall(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            document,
            flags=re.DOTALL,
        )
    ]


@pytest.fixture(scope="module")
def built_public_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the same static artifact that GitHub Pages deploys.

    Built once for the module: every test here only reads the result, and the
    build takes two to three seconds, which was most of the suite's runtime.
    """
    output = tmp_path_factory.mktemp("site")
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
        german_url = f"{SITE_URL}docs/de/" if page["slug"] == "home" else f"{SITE_URL}docs/de/{page['slug']}/"
        assert f'<link rel="alternate" hreflang="de" href="{german_url}" />' in documentation
        assert f'<meta property="og:url" content="{docs_url}" />' in documentation
        assert f'<link rel="icon" href="{SITE_URL}assets/favicon.svg" type="image/svg+xml" />' in documentation
        assert f'data-rendered-slug="{page["slug"]}"' in documentation
        assert "<h1 id=" in documentation
        assert "article-loading" not in re.search(
            r'<article class="article-content".*?</article>', documentation, flags=re.DOTALL
        ).group(0)
        assert '<meta name="twitter:card" content="summary_large_image" />' in documentation
        if page["slug"] == "home":
            # Pin the image to the artifact, not to a filename: the hero image has been
            # swapped before and left the documentation home page pointing at a 404.
            hero = re.search(r'<img src="images/([^"]+)"', documentation)
            assert hero, "the documentation home page should open with an image from docs/images"
            assert (built_public_dir / "docs" / "images" / hero.group(1)).is_file()

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


def test_german_documentation_pages_exist_and_are_indexable(built_public_dir: Path) -> None:
    """Every wiki page has a German mirror that is crawlable on its own URL."""
    titles: set[str] = set()

    for page in DOCUMENTATION_PAGES:
        german_markdown = PUBLIC_DIR.parents[1] / "docs" / "wiki" / "de" / page["file"]
        assert german_markdown.is_file(), f"Missing German wiki page: {page['file']}"
        german = GERMAN_DOCUMENTATION_PAGES[page["slug"]]
        relative_path = (
            Path("docs/de/index.html") if page["slug"] == "home" else Path("docs/de") / page["slug"] / "index.html"
        )
        documentation = (built_public_dir / relative_path).read_text(encoding="utf-8")
        docs_url = f"{SITE_URL}docs/de/" if page["slug"] == "home" else f"{SITE_URL}docs/de/{page['slug']}/"
        english_url = f"{SITE_URL}docs/" if page["slug"] == "home" else f"{SITE_URL}docs/{page['slug']}/"
        page_title = f"{german['title']} | IDM Heatpump Dokumentation"

        assert '<html lang="de"' in documentation
        assert f"<title>{html.escape(page_title)}</title>" in documentation
        assert f'<meta name="description" content="{html.escape(german["description"], quote=True)}" />' in documentation
        assert f'<link rel="canonical" href="{docs_url}" />' in documentation
        assert f'<link rel="alternate" hreflang="en" href="{english_url}" />' in documentation
        assert f'<meta property="og:url" content="{docs_url}" />' in documentation
        if page["slug"] == "home":
            assert 'data-rendered-slug="home"' in documentation
        graph = _structured_data(documentation)[0]["@graph"]
        web_page = next(item for item in graph if item["@type"] == "WebPage")
        assert web_page["inLanguage"] == "de"
        assert web_page["url"] == docs_url
        titles.add(page_title)

    assert len(titles) == len(DOCUMENTATION_PAGES)


def test_german_content_is_served_to_the_browser(built_public_dir: Path) -> None:
    """The client fetches the German markdown from content/de/."""
    script = (PUBLIC_DIR / "docs" / "docs.js").read_text(encoding="utf-8")
    assert "content/de/" in script
    for page in DOCUMENTATION_PAGES:
        german_markdown = PUBLIC_DIR.parents[1] / "docs" / "wiki" / "de" / page["file"]
        if not german_markdown.is_file():
            continue
        assert (built_public_dir / "docs" / "content" / "de" / page["file"]).is_file()


def test_crawler_files_reference_all_public_pages(built_public_dir: Path) -> None:
    """Robots and sitemap files should expose the canonical public pages."""
    robots = (built_public_dir / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: *\nAllow: /" in robots
    assert f"Sitemap: {SITE_URL}sitemap.xml" in robots

    sitemap = ElementTree.parse(built_public_dir / "sitemap.xml")
    namespace = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locations = {element.text for element in sitemap.findall("sitemap:url/sitemap:loc", namespace)}
    expected = {SITE_URL, f"{SITE_URL}en/", f"{SITE_URL}docs/", f"{SITE_URL}docs/de/"}
    expected.update(f"{SITE_URL}docs/{page['slug']}/" for page in DOCUMENTATION_PAGES if page["slug"] != "home")
    expected.update(
        f"{SITE_URL}docs/de/{page['slug']}/" for page in DOCUMENTATION_PAGES if page["slug"] != "home"
    )
    assert locations == expected


def test_docs_interface_takes_the_language_from_the_url() -> None:
    """The docs language must live in the URL, not in a stored preference."""
    script = (PUBLIC_DIR / "docs" / "docs.js").read_text(encoding="utf-8")
    assert "segments[0] === 'de' ? 'de' : 'en'" in script
    # No stored language may fight the URL a visitor opened or shared.
    assert "idm-docs-language" not in script
    # The toggle navigates to the other language's URL instead of
    # re-rendering only the interface around English content.
    assert "location.href = routeHref(currentSlug, anchor, target)" in script


def test_docs_interface_uses_real_paths_and_keeps_legacy_hash_compatibility() -> None:
    """Navigation should use crawlable paths while old hash links still resolve."""
    script = (PUBLIC_DIR / "docs" / "docs.js").read_text(encoding="utf-8")
    script_slugs = re.findall(r"\{ slug: '([^']+)', file:", script)

    assert script_slugs == [page["slug"] for page in DOCUMENTATION_PAGES]
    assert "const docsBasePath = docsRootUrl.pathname" in script
    assert "history.replaceState(null, '', routeHref(page.slug, parsed.anchor))" in script
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


def test_generated_fragment_links_resolve_to_real_headings(built_public_dir: Path) -> None:
    """A ``#fragment`` written by hand in the wiki must match a rendered heading id.

    Heading ids come from the renderer's slugify, so a hand-written anchor such as
    ``Services#set_external_power`` silently lands on the right page at the wrong
    place. Only the fragment is checked here; missing files are the test above.
    """
    test_origin = "https://pages.test/"
    documents = {
        path.relative_to(built_public_dir).as_posix(): path.read_text(encoding="utf-8")
        for path in built_public_dir.rglob("*.html")
    }
    identifiers = {name: set(re.findall(r'id="([^"]+)"', text)) for name, text in documents.items()}
    missing: list[str] = []

    for relative_document, document in documents.items():
        base_url = urljoin(test_origin, relative_document)
        for reference in re.findall(r'\bhref="([^"]+)"', document):
            resolved = urlparse(urljoin(base_url, reference))
            if resolved.netloc != "pages.test" or not resolved.fragment:
                continue
            target = unquote(resolved.path).lstrip("/")
            if resolved.path.endswith("/"):
                target += "index.html"
            if target in identifiers and resolved.fragment not in identifiers[target]:
                missing.append(f"{relative_document}: {reference} -> #{resolved.fragment}")

    assert not missing, "Fragment links without a matching heading:\n" + "\n".join(missing)
