"""Build the deployable GitHub Pages site from repository metadata."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "docs" / "public"
WIKI_DIR = ROOT / "docs" / "wiki"
IMAGES_DIR = ROOT / "docs" / "images"
MANIFEST_PATH = ROOT / "custom_components" / "idm_heatpump" / "manifest.json"
HACS_PATH = ROOT / "hacs.json"

SITE_URL = "https://xerolux.github.io/idm-heatpump-hass/"


HOME_TRANSLATIONS = {
    "Zum Inhalt springen": "Skip to content",
    "IDM Heatpump Startseite": "IDM Heatpump home page",
    "Hauptnavigation": "Main navigation",
    "Funktionen": "Features",
    "Einblicke": "Preview",
    "Installation": "Installation",
    "Dokumentation": "Documentation",
    "Helles Design aktivieren": "Enable light theme",
    "Menü öffnen": "Open menu",
    "Aktuelle Version": "Latest version",
    "Für Home Assistant": "For Home Assistant",
    "IDM Wärmepumpe<br /><span>in Home Assistant</span>": "IDM heat pump<br /><span>in Home Assistant</span>",
    "Überwache und steuere deine IDM Navigator Wärmepumpe direkt in Home Assistant –\n              lokal per Modbus TCP, transparent und ohne Cloud.": "Monitor and control your IDM Navigator heat pump directly in Home Assistant –\n              locally via Modbus TCP, transparently and without the cloud.",
    "Integration laden": "Download integration",
    "Installation ansehen": "View installation",
    "Vorteile": "Benefits",
    "100 % lokal": "100% local",
    "Über HACS installierbar": "Installable through HACS",
    "Wärmepumpe": "Heat pump",
    "Außen": "Outside",
    "Rücklauf": "Return",
    "Leistung": "Power",
    "Aktueller COP": "Current COP",
    "Betriebsart": "Operating mode",
    "Heizen": "Heating",
    "Beispieldaten": "Sample data",
    "Heute erzeugt": "Generated today",
    "12 % effizienter": "12% more efficient",
    "Lokale Verbindung": "Local connection",
    "Alles im Blick": "Everything at a glance",
    "Mehr als nur Temperaturen.": "More than temperatures.",
    "Die Integration macht aus Modbus-Registern verständliche Home-Assistant-Entitäten – passend zu deinem erkannten System.": "The integration turns Modbus registers into clear Home Assistant entities tailored to the detected system.",
    "System verstehen": "Understand your system",
    "Vorlauf, Rücklauf, Warmwasser, Außentemperatur, Druck, Durchfluss, Laufzeiten und Wärmemengen in einer klaren Oberfläche.": "Flow, return, hot water, outside temperature, pressure, flow rate, runtimes and heat quantities in one clear interface.",
    "Live-Sensordaten": "Live sensor data",
    "Energie & Effizienz": "Energy & efficiency",
    "Modellabhängige Erkennung": "Model-aware detection",
    "Beispielhafter Temperaturverlauf": "Example temperature history",
    "Temperaturverlauf über 24 Stunden": "Temperature history over 24 hours",
    "Lokal. Transparent. Vollständig.": "Local. Transparent. Complete.",
    "Alles, was deine IDM Wärmepumpe kann – direkt als Home-Assistant-Entitäten. Ohne Cloud, ohne Herstellerkonto und ohne proprietäres Gateway.": "Everything your IDM heat pump can do – exposed directly as Home Assistant entities. No cloud, no vendor account and no proprietary gateway.",
    "Vollständig überwachen": "Monitor everything",
    "Temperaturen, Drücke, Leistungen, Laufzeiten, Ventile und Statuswerte lokal per Modbus TCP erfassen.": "Read temperatures, pressures, power, runtimes, valves and status values locally via Modbus TCP.",
    "Online": "Online",
    "Vorlauf": "Flow",
    "Warmwasser": "Hot water",
    "Bereit": "Ready",
    "Verdichter": "Compressor",
    "Aktiv": "Active",
    "Präzise steuern": "Precise control",
    "Sollwerte, Betriebsarten und Freigaben direkt über Number-, Select- und Switch-Entitäten setzen.": "Set target values, operating modes and enables directly through number, select and switch entities.",
    "Einmalige Ladung": "One-time charge",
    "Intelligent automatisieren": "Smart automation",
    "PV-Überschuss, Heizkreise A–G, bis zu zehn Zonen und Warmwasser logisch mit deinem Zuhause verbinden.": "Connect PV surplus, heating circuits A–G, up to ten zones and hot water intelligently with your home.",
    "PV-Überschuss": "PV surplus",
    "KNX ohne IDM-Modul": "KNX without the IDM module",
    "Die optionale KNX-Bridge stellt dieselben Kommunikationsobjekte bereit wie IDMs ETS-Beispielprojekt – gleiche Objektnummern, gleiche Datenpunkttypen, gleiche Schreibrichtung. Das kostenpflichtige Weinzierl-BAOS-Gateway wird damit überflüssig.": "The optional KNX bridge provides the same communication objects as IDM's ETS example project – the same object numbers, data point types and write directions. This removes the need for the paid Weinzierl BAOS gateway.",
    "Kein eigener KNX-Stack: Die Bridge nutzt die KNX-Integration von Home Assistant, inklusive Tunneling, Routing und KNX Secure.": "No separate KNX stack: the bridge uses Home Assistant's KNX integration, including tunneling, routing and KNX Secure.",
    "Experimentell": "Experimental",
    "654 Objekte": "654 objects",
    "Senden &amp; Befehle": "Send &amp; commands",
    "Beispielhafte Zuordnung von IDM-Objekten zu Gruppenadressen": "Example mapping of IDM objects to group addresses",
    "Basisadresse": "Base address",
    "Objekt + Basis": "Object + base",
    "Außentemperatur": "Outside temperature",
    "lesend": "read-only",
    "Betriebsart System": "System operating mode",
    "schreibbar": "writable",
    "Warmwasser-Sollwert": "Hot water target",
    "Betriebsart Heizkreis A": "Heating circuit A operating mode",
    "Experimentell: bislang nur durch Tests abgesichert, noch nie an einem echten KNX-Bus erprobt. Voraussetzung ist die eingerichtete KNX-Integration in Home Assistant.": "Experimental: currently covered by tests only and not yet proven on a real KNX bus. Home Assistant's KNX integration must be configured.",
    "Keine Cloud erforderlich": "No cloud required",
    "7 Heizkreise": "7 heating circuits",
    "Individuell konfigurierbar": "Individually configurable",
    "Zonenmodule": "Zone modules",
    "Bis zu 8 Räume je Zone": "Up to 8 rooms per zone",
    "Robust bei Verbindungsfehlern": "Resilient to connection errors",
    "So sieht es aus": "See it in action",
    "Nahtlos in Home Assistant.": "Seamless in Home Assistant.",
    "Alle Werte erscheinen dort, wo du sie erwartest – in Geräten, Dashboards, Automationen und Diagnosen.": "Every value appears where you expect it – in devices, dashboards, automations and diagnostics.",
    "Ansicht auswählen": "Choose view",
    "Übersicht": "Overview",
    "Heizkreise": "Heating circuits",
    "Heizkreise & Zonen": "Heating circuits & zones",
    "Heizkreis A": "Heating circuit A",
    "Heizkreis B": "Heating circuit B",
    "Diagnose": "Diagnostics",
    "Energie": "Energy",
    "Automationen": "Automations",
    "Einstellungen": "Settings",
    "Heizen · Online": "Heating · Online",
    "Energie heute": "Energy today",
    "Stand 14:35 Uhr": "As of 14:35",
    "Verbrauch": "Consumption",
    "Wärme": "Heat",
    "Heizkreise &amp; Zonen": "Heating circuits &amp; zones",
    "Verbunden": "Connected",
    "Fußbodenheizung": "Underfloor heating",
    "Obergeschoss": "Upper floor",
    "Automatik": "Automatic",
    "Wohnen": "Living",
    "Raumtemperatur": "Room temperature",
    "Bad": "Bathroom",
    "Systemdiagnose": "System diagnostics",
    "Alles arbeitet wie erwartet": "Everything is working as expected",
    "Verbindung stabil": "Connection stable",
    "Bibliothek erfolgreich geladen": "Library loaded successfully",
    "Entitäten": "Entities",
    "Alle verfügbaren Register eingelesen": "All available registers read",
    "Modellabhängig": "Model dependent",
    "Interne Meldungen": "Internal messages",
    "Keine aktiven Fehler vorhanden": "No active errors",
    "Verbindungsdaten und PIN werden im Diagnoseexport automatisch geschützt.": "Connection details and PIN are automatically redacted in diagnostic exports.",
    "Interaktive Vorschau mit Beispieldaten – die tatsächlichen Entitäten hängen vom Wärmepumpenmodell und der Konfiguration ab.": "Interactive preview with sample data – actual entities depend on the heat pump model and configuration.",
    "In wenigen Minuten bereit": "Ready in minutes",
    "Einfach installieren.<br/><span>Lokal verbinden.</span>": "Easy to install.<br/><span>Connect locally.</span>",
    "Die Integration lässt sich direkt über HACS hinzufügen. Danach brauchst du nur noch die IP-Adresse deiner IDM Navigator Steuerung.": "Add the integration directly through HACS. Then all you need is the IP address of your IDM Navigator controller.",
    "Repository hinzufügen": "Add repository",
    "IDM Heatpump als benutzerdefiniertes HACS-Repository eintragen.": "Add IDM Heatpump as a custom HACS repository.",
    "Modbus TCP aktivieren": "Enable Modbus TCP",
    "In der Gebäudeleittechnik des Navigators einschalten.": "Enable it in the Navigator building management settings.",
    "Integration konfigurieren": "Configure integration",
    "IP-Adresse, Port 502 und üblicherweise Slave-ID 1 eingeben.": "Enter the IP address, port 502 and usually slave ID 1.",
    "Benötigt": "Requires",
    "Aktuelle stabile Version": "Latest stable version",
    "Auf GitHub herunterladen": "Download from GitHub",
    "In HACS öffnen": "Open in HACS",
    "Empfohlene Installation": "Recommended installation",
    "Repository-URL kopieren": "Copy repository URL",
    "Installationsanleitung": "Installation guide",
    "Schritt für Schritt starten": "Get started step by step",
    "Entitäten &amp; Konfiguration": "Entities &amp; configuration",
    "Entitäten & Konfiguration": "Entities & configuration",
    "Fehlerbehebung": "Troubleshooting",
    "Diagnose &amp; Lösungen": "Diagnostics &amp; solutions",
    "Diagnose & Lösungen": "Diagnostics & solutions",
    "Community &amp; Hilfe": "Community &amp; help",
    "Fragen, Ideen und Lovelace": "Questions, ideas and Lovelace",
    "Mit Leidenschaft für die Home-Assistant- und Wärmepumpen-Community entwickelt.": "Built with passion for the Home Assistant and heat pump community.",
    "Projekt": "Project",
    "Hilfe": "Help",
    "Inoffizielles Community-Projekt · Nicht mit IDM Energiesysteme GmbH verbunden · MIT-Lizenz": "Unofficial community project · Not affiliated with IDM Energiesysteme GmbH · MIT License",
    "Projekt unterstützen": "Support the project",
    "Repository-URL kopiert": "Repository URL copied",
}


def _replace_element_text(
    document: str,
    attribute: str,
    value: str,
    *,
    required: bool = True,
) -> str:
    pattern = re.compile(
        rf'(<(?P<tag>[a-z0-9]+)\b[^>]*\b{re.escape(attribute)}(?:="[^"]*")?[^>]*>).*?(</(?P=tag)>)',
        flags=re.DOTALL | re.IGNORECASE,
    )
    updated, count = pattern.subn(rf"\g<1>{value}\g<3>", document)
    if required and count == 0:
        raise ValueError(f"Missing element with {attribute}")
    return updated


def _metadata() -> tuple[str, str, str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    hacs = json.loads(HACS_PATH.read_text(encoding="utf-8"))
    api_requirement = next(
        requirement for requirement in manifest["requirements"] if requirement.startswith("idm-heatpump-api")
    )
    api_version = api_requirement.rsplit("==", maxsplit=1)[1]
    return manifest["version"], api_version, hacs["homeassistant"]


def _inject_metadata(document: str) -> str:
    integration_version, api_version, minimum_ha_version = _metadata()
    document = _replace_element_text(document, "data-integration-version", f"v{integration_version}")
    document = _replace_element_text(
        document,
        "data-api-version",
        f"v{api_version}",
        required=False,
    )
    return _replace_element_text(
        document,
        "data-minimum-home-assistant-version",
        f"{minimum_ha_version}+",
    )


def _english_homepage(german_homepage: str) -> str:
    page = german_homepage
    replacements = {
        '<html lang="de"': '<html lang="en"',
        'content="IDM Heatpump für Home Assistant – IDM Wärmepumpen lokal per Modbus TCP überwachen, steuern und automatisieren."': 'content="IDM Heatpump for Home Assistant – monitor, control and automate IDM heat pumps locally via Modbus TCP."',
        'content="IDM Heatpump für Home Assistant"': 'content="IDM Heatpump for Home Assistant"',
        'content="Deine IDM Wärmepumpe. Direkt in Home Assistant. Lokal, transparent und ohne Cloud."': 'content="Your IDM heat pump in Home Assistant. Local, transparent and cloud-free."',
        'content="de_DE"': 'content="en_US"',
        "<title>IDM Wärmepumpe in Home Assistant | Modbus TCP Integration</title>": "<title>IDM Heat Pump for Home Assistant | Modbus TCP Integration</title>",
        f'<link rel="canonical" href="{SITE_URL}" />': f'<link rel="canonical" href="{SITE_URL}en/" />',
        f'<meta property="og:url" content="{SITE_URL}" />': f'<meta property="og:url" content="{SITE_URL}en/" />',
        f'"url": "{SITE_URL}"': f'"url": "{SITE_URL}en/"',
        'href="assets/': 'href="../assets/',
        'href="styles.css"': 'href="../styles.css"',
        'src="script.js"': 'src="../script.js"',
        'href="docs/': 'href="../docs/',
        'href="docs/#': 'href="../docs/#',
        'href="en/" hreflang="en" aria-label="English version" data-language-link>EN</a>': 'href="../" hreflang="de" aria-label="German version" data-language-link>DE</a>',
        '"inLanguage": "de"': '"inLanguage": "en"',
        '"alternateName": "IDM Wärmepumpe in Home Assistant"': '"alternateName": "IDM heat pump in Home Assistant"',
        '"description": "IDM Wärmepumpen lokal per Modbus TCP in Home Assistant überwachen, steuern und automatisieren."': '"description": "Monitor, control and automate IDM heat pumps locally in Home Assistant via Modbus TCP."',
        '<a href="en/" hreflang="en">View in English</a>': '<a href="./" hreflang="en">View in English</a>',
    }
    for source, target in replacements.items():
        page = page.replace(source, target)
    for german, english in sorted(HOME_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        page = page.replace(german, english)
    page = page.replace("IDM Energysysteme GmbH", "IDM Energiesysteme GmbH")
    return page


def build_site(output: Path) -> None:
    """Build a complete Pages artifact at *output*."""
    output = output.resolve()
    forbidden_outputs = {ROOT.resolve(), PUBLIC_DIR.resolve(), ROOT.parent.resolve()}
    if output in forbidden_outputs or output == output.parent:
        raise ValueError(f"Unsafe Pages output directory: {output}")
    if output.exists():
        shutil.rmtree(output)

    shutil.copytree(PUBLIC_DIR, output)
    content_output = output / "docs" / "content"
    content_output.mkdir(parents=True, exist_ok=True)
    for markdown in WIKI_DIR.glob("*.md"):
        shutil.copy2(markdown, content_output / markdown.name)
    shutil.copytree(IMAGES_DIR, output / "docs" / "images", dirs_exist_ok=True)

    homepage_path = output / "index.html"
    homepage = _inject_metadata(homepage_path.read_text(encoding="utf-8"))
    homepage_path.write_text(homepage, encoding="utf-8")

    docs_path = output / "docs" / "index.html"
    docs_page = _inject_metadata(docs_path.read_text(encoding="utf-8"))
    docs_path.write_text(docs_page, encoding="utf-8")

    english_path = output / "en" / "index.html"
    english_path.parent.mkdir(parents=True, exist_ok=True)
    english_path.write_text(_english_homepage(homepage), encoding="utf-8")


def main() -> None:
    """Build the Pages artifact from command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    build_site(arguments.output)


if __name__ == "__main__":
    main()
