"""Build the deployable GitHub Pages site from repository metadata."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "docs" / "public"
WIKI_DIR = ROOT / "docs" / "wiki"
IMAGES_DIR = ROOT / "docs" / "images"
MANIFEST_PATH = ROOT / "custom_components" / "idm_heatpump" / "manifest.json"
HACS_PATH = ROOT / "hacs.json"

SITE_URL = "https://xerolux.github.io/idm-heatpump-hass/"
MARKDOWN_RENDERER = ROOT / "scripts" / "render_pages_markdown.cjs"
GERMAN_WIKI_DIR = WIKI_DIR / "de"


class DocumentationPage(TypedDict):
    """Metadata for one crawlable documentation page."""

    slug: str
    file: str
    group: str
    title: str
    description: str


DOCUMENTATION_GROUPS = {
    "start": "Getting started",
    "entities": "Entities & devices",
    "automation": "Automation",
    "operation": "Operation & maintenance",
    "development": "Development & community",
}

GERMAN_DOCUMENTATION_GROUPS = {
    "start": "Erste Schritte",
    "entities": "Entitäten & Geräte",
    "automation": "Automation",
    "operation": "Betrieb & Wartung",
    "development": "Entwicklung",
}

# German mirror of the documentation: one entry per DOCUMENTATION_PAGES slug.
# The German markdown must exist at docs/wiki/de/<file> for the page to build.
GERMAN_DOCUMENTATION_PAGES: dict[str, dict[str, str]] = {
    "home": {
        "title": "Übersicht",
        "description": "Offizielle Dokumentation von IDM Heatpump, der lokalen Modbus-TCP-Integration für IDM-Navigator-Wärmepumpen in Home Assistant.",
    },
    "installation-and-setup": {
        "title": "Installation & Einrichtung",
        "description": "IDM Heatpump über HACS installieren, Modbus TCP am IDM Navigator aktivieren und mit Home Assistant verbinden.",
    },
    "configuration": {
        "title": "Konfiguration",
        "description": "Host, Abfrageintervall, Heizkreise, Zonen, Web-Supplement und Verbindungsoptionen der Integration in Home Assistant konfigurieren.",
    },
    "entities": {
        "title": "Alle Entitäten",
        "description": "Sensoren, Binärsensoren, Zahlen, Auswahlen, Schalter, Klima- und Warmwasser-Entitäten der Integration entdecken.",
    },
    "supported-devices": {
        "title": "Unterstützte Geräte",
        "description": "Unterstützung für IDM Navigator 2.0, Navigator 10 und Navigator Pro vor der Installation der Integration prüfen.",
    },
    "compatibility-matrix": {
        "title": "Kompatibilitätsmatrix",
        "description": "Bestätigte und erwartete Kompatibilität über IDM-Modelle, Navigator-Familien und Firmware-Varianten nachschlagen.",
    },
    "services": {
        "title": "Aktionen & Dienste",
        "description": "Aktionen und Dienste für Systembetriebsarten, Warmwasser-Boost, externe Klimadaten und Diagnose nutzen.",
    },
    "examples": {
        "title": "Beispiel-Automationen",
        "description": "Praktische Home-Assistant-Automationsbeispiele für Sollwerte, Betriebsarten, Warmwasser und lokales Energiemanagement.",
    },
    "knx-bridge": {
        "title": "KNX-Bridge",
        "description": "Die experimentelle IDM-KNX-Bridge über die Home-Assistant-KNX-Integration einrichten – ohne separates Weinzierl-BAOS-Gateway.",
    },
    "experimental-ai-adviser": {
        "title": "KI-Anlagenberater (experimentell)",
        "description": "Optionale schreibgeschützte Ollama-Berichte mit expliziter Aktivierung, lokalen Daten und sichtbaren Abdeckungsgrenzen einrichten.",
    },
    "smart-energy-and-comfort": {
        "title": "Smart Energy & Comfort",
        "description": "Das optionale iDM-Profil Smart Energy & Comfort für lokale Effizienz, Zyklusanalyse und sichere Warmwasser-Boost-Steuerung wählen.",
    },
    "data-update": {
        "title": "Datenaktualisierung",
        "description": "Lokale Modbus-TCP-Abfrage, Update-Intervalle, robuste Lesevorgänge und Koordinator-Verhalten verstehen.",
    },
    "local-web-interface": {
        "title": "Lokale Web-Schnittstelle",
        "description": "Das optionale lokale, schreibgeschützte Navigator-Web-Supplement für zusätzliche Metadaten und Diagnose ohne Cloud nutzen.",
    },
    "known-limitations": {
        "title": "Bekannte Einschränkungen",
        "description": "Aktuelle Geräte-, Firmware-, Modbus-, KNX- und Home-Assistant-Einschränkungen der Integration nachlesen.",
    },
    "troubleshooting": {
        "title": "Fehlerbehebung",
        "description": "Verbindungsfehler, nicht verfügbare Entitäten, Modbus-Fehler, Web-PIN-Probleme und Update-Probleme diagnostizieren.",
    },
    "modbus-register": {
        "title": "Modbus-Register",
        "description": "Die modellbewusste Modbus-Registerkarte des IDM Navigator verstehen: Batches, Funktioncodes, Filterung und Schreibschutz.",
    },
    "stability-and-release-readiness": {
        "title": "Stabilität & Releases",
        "description": "Die geprüften Test-, Kompatibilitäts- und Release-Nachweise hinter stabilen IDM-Heatpump-Versionen ansehen.",
    },
    "navigator-protocol-analysis": {
        "title": "Navigator-Protokollanalyse",
        "description": "Bestätigte Erkenntnisse aus statischer Analyse und schreibgeschützter Validierung der lokalen Navigator-Protokolle lesen.",
    },
    "community": {
        "title": "Community & Hilfe",
        "description": "Den richtigen Support-Kanal für Fragen, reproduzierbare Fehler, Ideen und Kompatibilitätsmeldungen finden.",
    },
    "contributing": {
        "title": "Mitwirken",
        "description": "Code, Tests, Dokumentation, Übersetzungen und Kompatibilitätsnachweise zu IDM Heatpump beitragen.",
    },
    "changelog": {
        "title": "Änderungsverlauf",
        "description": "Aktuelle Meilensteine nachverfolgen und die vollständige Versionsgeschichte sowie GitHub-Releases verfolgen.",
    },
}

DOCUMENTATION_PAGES: tuple[DocumentationPage, ...] = (
    {
        "slug": "home",
        "file": "Home.md",
        "group": "start",
        "title": "IDM Heatpump Documentation",
        "description": "Official documentation for IDM Heatpump, the local Modbus TCP integration for IDM Navigator heat pumps in Home Assistant.",
    },
    {
        "slug": "installation-and-setup",
        "file": "Installation-and-Setup.md",
        "group": "start",
        "title": "Installation and Setup",
        "description": "Install IDM Heatpump through HACS, enable Modbus TCP on an IDM Navigator controller and connect it to Home Assistant.",
    },
    {
        "slug": "configuration",
        "file": "Configuration.md",
        "group": "start",
        "title": "Configuration",
        "description": "Configure the IDM Navigator host, polling, heating circuits, zones, web supplement and connection options in Home Assistant.",
    },
    {
        "slug": "entities",
        "file": "Entities.md",
        "group": "entities",
        "title": "IDM Heatpump Entities",
        "description": "Explore sensors, binary sensors, numbers, selects, switches, climate controls and water-heater entities exposed in Home Assistant.",
    },
    {
        "slug": "supported-devices",
        "file": "Supported-Devices.md",
        "group": "entities",
        "title": "Supported IDM Heat Pumps",
        "description": "Check support for IDM Navigator 2.0, Navigator 10 and Navigator Pro heat pumps before installing the Home Assistant integration.",
    },
    {
        "slug": "compatibility-matrix",
        "file": "Compatibility-Matrix.md",
        "group": "entities",
        "title": "IDM Compatibility Matrix",
        "description": "Review confirmed and expected compatibility across IDM heat pump models, Navigator families and firmware variants.",
    },
    {
        "slug": "services",
        "file": "Services.md",
        "group": "automation",
        "title": "Actions and Services",
        "description": "Use IDM Heatpump actions and Home Assistant services for system modes, hot-water boost, external climate data and diagnostics.",
    },
    {
        "slug": "examples",
        "file": "Examples.md",
        "group": "automation",
        "title": "Home Assistant Automation Examples",
        "description": "Practical Home Assistant automation examples for IDM heat pump setpoints, modes, hot water and local energy management.",
    },
    {
        "slug": "knx-bridge",
        "file": "KNX-Bridge.md",
        "group": "automation",
        "title": "Experimental KNX Bridge",
        "description": "Configure the experimental IDM KNX bridge through Home Assistant KNX without a separate Weinzierl BAOS gateway module.",
    },
    {
        "slug": "experimental-ai-adviser",
        "file": "Experimental-AI-Adviser.md",
        "group": "automation",
        "title": "Experimental Local AI Adviser",
        "description": "Set up optional read-only Ollama reports with explicit activation, local data and visible coverage limits.",
    },
    {
        "slug": "smart-energy-and-comfort",
        "file": "Smart-Energy-and-Comfort.md",
        "group": "automation",
        "title": "iDM Smart Energy and Comfort",
        "description": "Choose the optional iDM Smart Energy and Comfort profile for local efficiency, cycle analysis and safe domestic hot-water boost controls.",
    },
    {
        "slug": "data-update",
        "file": "Data-Update.md",
        "group": "operation",
        "title": "Data Updates and Polling",
        "description": "Understand local Modbus TCP polling, update intervals, resilient reads and coordinator behavior in IDM Heatpump.",
    },
    {
        "slug": "local-web-interface",
        "file": "Local-Web-Interface.md",
        "group": "operation",
        "title": "Local Navigator Web Interface",
        "description": "Use the optional local, read-only IDM Navigator web supplement for additional metadata and diagnostics without cloud access.",
    },
    {
        "slug": "known-limitations",
        "file": "Known-Limitations.md",
        "group": "operation",
        "title": "Known Limitations",
        "description": "Review current device, firmware, Modbus, KNX and Home Assistant limitations of the IDM Heatpump integration.",
    },
    {
        "slug": "troubleshooting",
        "file": "Troubleshooting.md",
        "group": "operation",
        "title": "IDM Heatpump Troubleshooting",
        "description": "Diagnose IDM heat pump connection failures, unavailable entities, Modbus errors, web PIN problems and update issues.",
    },
    {
        "slug": "modbus-register",
        "file": "Modbus-Register.md",
        "group": "operation",
        "title": "IDM Modbus Registers",
        "description": "Understand the model-aware IDM Navigator Modbus register map, batching, function codes, filtering and write safety.",
    },
    {
        "slug": "stability-and-release-readiness",
        "file": "Stability-and-Release-Readiness.md",
        "group": "operation",
        "title": "Stability and Release Readiness",
        "description": "See the verified test, compatibility and release evidence behind stable IDM Heatpump versions for Home Assistant.",
    },
    {
        "slug": "navigator-protocol-analysis",
        "file": "Navigator-Protocol-Analysis.md",
        "group": "operation",
        "title": "IDM Navigator Protocol Analysis",
        "description": "Read confirmed findings from static analysis and read-only validation of local IDM Navigator communication protocols.",
    },
    {
        "slug": "community",
        "file": "Community.md",
        "group": "development",
        "title": "Community and Support",
        "description": "Find the right IDM Heatpump support channel for questions, reproducible bugs, feature ideas and hardware compatibility reports.",
    },
    {
        "slug": "contributing",
        "file": "Contributing.md",
        "group": "development",
        "title": "Contributing",
        "description": "Contribute code, tests, documentation, translations and compatibility evidence to IDM Heatpump for Home Assistant.",
    },
    {
        "slug": "changelog",
        "file": "Changelog.md",
        "group": "development",
        "title": "IDM Heatpump Changelog",
        "description": "Review recent IDM Heatpump milestones and follow the complete version history and GitHub releases.",
    },
)


HOME_TRANSLATIONS = {
    "Seit 0.18.0": "Since 0.18.0",
    "KI-Anlagenberater (experimentell)": "AI plant adviser (experimental)",
    "Tages-, Wochen-, Zustands- und Effizienzberichte direkt aus Messwerten – standardmäßig ohne Modellaufruf. Eigenes KI-Gerät, Berichts-Buttons, Dashboard-Export, neustartsicherer Zeitplan und lokales Lernen mit Live-Fortschritt.": "Daily, weekly, health and efficiency reports generated directly from measured facts — with no model call by default. A dedicated AI device, report buttons, dashboard export, a restart-safe schedule and local learning with live progress.",
    "Messwertberichte als Standard": "Measured-data reports by default",
    "Optional Ollama, HA AI Task, OpenAI, Z.ai": "Optional Ollama, HA AI Task, OpenAI, Z.ai",
    "Nur lesend, ohne Cloud-Zwang": "Read-only, no cloud required",
    "KI-Berichte entdecken →": "Discover AI reports →",
    "Alle Funktionen dieser Sektion sind seit v0.18.0 Teil der Integration. Schreibende Funktionen bleiben standardmäßig aus und erfordern eine Bestätigung; der KI-Anlagenberater ist experimentell und nur lesend.": "Every feature in this section has been part of the integration since v0.18.0. Write-enabled features stay off by default and require confirmation; the AI plant adviser is experimental and read-only.",
    "Installationsanleitung öffnen": "Open the installation guide",
    "Energie verstehen, Komfort planen und Auffälligkeiten erkennen. Wähle Smart für zusätzliche Auswertungen oder Vanilla für die Kernfunktionen.": "Understand energy use, plan comfort and spot unusual behavior. Choose Smart for additional analysis or Vanilla for core features.",
    "Energie &amp; Kosten": "Energy &amp; costs",
    "Strom, Wärme und COP als Gesamt-, Tages- und Monatswerte. Dazu geschätzte Kosten, CO₂ und PV-Nutzung, auch über Neustarts hinweg.": "Electrical energy, heat and COP as lifetime, daily and monthly values. Add estimated costs, CO₂ and PV use, retained across restarts.",
    "Optionaler Tarifsensor": "Optional tariff sensor",
    "Eigene Analytics-Gruppe": "Separate Analytics group",
    "Nur Auswertung": "Analysis only",
    "Energiestatistik verstehen →": "Understand energy statistics →",
    "PV-Warmwasser &amp; Zeitpläne": "PV hot water &amp; schedules",
    "Optional Warmwasser mit PV-Überschuss laden oder Raum-Sollwerte in bis zu 16 täglichen Zeitfenstern setzen. Beides ist standardmäßig aus und erfordert eine Bestätigung zur alleinigen Steuerung.": "Optionally charge hot water using PV surplus or set room targets in up to 16 daily windows. Both are off by default and require confirmation of exclusive control.",
    "HA-Zeitzone": "HA timezone",
    "Bedingte Rückstellung": "Conditional restore",
    "Schreibende Funktionen": "Write-enabled features",
    "Automationen einrichten →": "Configure automations →",
    "Health Monitor &amp; Beratung": "Health Monitor &amp; advice",
    "Acht Diagnoseprüfungen, Hinweise zu Heizkreis und Wetter sowie ein Diagnoseexport für den Fachbetrieb. Empfehlungen verändern keine Sollwerte und ersetzen keine Fehlerdiagnose.": "Eight diagnostic checks, heating and weather hints, and a diagnostic export for your installer. Recommendations do not change setpoints or replace fault diagnosis.",
    "Eigene Health- und Comfort-Gruppen": "Separate Health and Comfort groups",
    "Nur lesend": "Read-only",
    "Diagnosefunktionen ansehen →": "Explore diagnostics →",
    "Geführte Einrichtung": "Guided setup",
    "Standard, Advanced und Expert bieten dieselben Funktionen mit unterschiedlicher Detailtiefe. Wähle die gewünschten Kategorien und behalte die übrigen Einstellungen.": "Standard, Advanced and Expert offer the same features at different levels of detail. Choose the categories you need and retain the other settings.",
    "Smart oder Vanilla": "Smart or Vanilla",
    "Gezielte Sensorauswahl": "Choose relevant sensors",
    "Bestehende IDs bleiben erhalten": "Existing IDs are retained",
    "Konfiguration kennenlernen →": "Explore configuration →",
    "Smart Energy &amp; Comfort entdecken": "Explore Smart Energy &amp; Comfort",
    "Beta-Version": "Beta version",
    "Vorabversion": "Prerelease version",
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


def _replace_tag_attribute(
    document: str,
    selector_attribute: str,
    selector_value: str | None,
    target_attribute: str,
    value: str,
) -> str:
    selector = re.escape(selector_attribute)
    if selector_value is not None:
        selector += rf'="{re.escape(selector_value)}"'
    pattern = re.compile(
        rf'(<[a-z0-9]+\b(?=[^>]*\b{selector})(?=[^>]*\b{re.escape(target_attribute)}=")[^>]*\b{re.escape(target_attribute)}=")[^"]*(")',
        flags=re.DOTALL | re.IGNORECASE,
    )
    updated, count = pattern.subn(rf"\g<1>{value}\g<2>", document)
    if count == 0:
        raise ValueError(f"Missing element with {selector_attribute}")
    return updated


def _replace_title(document: str, title: str) -> str:
    updated, count = re.subn(
        r"<title>.*?</title>",
        f"<title>{html.escape(title)}</title>",
        document,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if count == 0:
        raise ValueError("Missing title element")
    return updated


def _render_markdown(
    markdown_path: Path, slug: str, language: str = "en"
) -> tuple[str, list[dict[str, object]]]:
    result = subprocess.run(
        ["node", str(MARKDOWN_RENDERER), str(markdown_path), slug, language],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    rendered = json.loads(result.stdout)
    return str(rendered["html"]), list(rendered["headings"])


def _page_title(current_page: DocumentationPage, language: str) -> str:
    if language == "de":
        return GERMAN_DOCUMENTATION_PAGES[current_page["slug"]]["title"]
    return current_page["title"]


def _page_description(current_page: DocumentationPage, language: str) -> str:
    if language == "de":
        return GERMAN_DOCUMENTATION_PAGES[current_page["slug"]]["description"]
    return current_page["description"]


def _documentation_href(current_slug: str, target_slug: str, anchor: str = "") -> str:
    """Relative href inside one language tree; both trees share the same shape."""
    if target_slug == "home":
        href = "./" if current_slug == "home" else "../"
    else:
        href = f"{target_slug}/" if current_slug == "home" else f"../{target_slug}/"
    return f"{href}#{anchor}" if anchor else href


def _documentation_navigation(current_page: DocumentationPage, language: str) -> str:
    groups = GERMAN_DOCUMENTATION_GROUPS if language == "de" else DOCUMENTATION_GROUPS
    sections: list[str] = []
    for group, label in groups.items():
        links = "".join(
            (
                f'<a class="nav-item{" is-active" if page["slug"] == current_page["slug"] else ""}" '
                f'href="{_documentation_href(current_page["slug"], page["slug"])}" '
                f'data-page="{page["slug"]}"><span>{html.escape(_page_title(page, language))}</span></a>'
            )
            for page in DOCUMENTATION_PAGES
            if page["group"] == group
        )
        sections.append(
            f'<section class="nav-group"><h2 class="nav-group-title"><span>{html.escape(label)}</span></h2>{links}</section>'
        )
    return "".join(sections)


def _documentation_breadcrumbs(current_page: DocumentationPage, language: str) -> str:
    if language == "de":
        site_href = "../../" if current_page["slug"] == "home" else "../../../"
    else:
        site_href = "../" if current_page["slug"] == "home" else "../../"
    groups = GERMAN_DOCUMENTATION_GROUPS if language == "de" else DOCUMENTATION_GROUPS
    first_in_group = next(page for page in DOCUMENTATION_PAGES if page["group"] == current_page["group"])
    return (
        f'<a href="{site_href}">IDM Heatpump</a><i>›</i>'
        f'<a href="{_documentation_href(current_page["slug"], first_in_group["slug"])}">'
        f"{html.escape(groups[current_page['group']])}</a><i>›</i>"
        f"<span>{html.escape(_page_title(current_page, language))}</span>"
    )


def _documentation_toc(headings: list[dict[str, object]]) -> str:
    return "".join(
        (
            f'<a class="toc-link" data-level="{heading["level"]}" href="#{heading["id"]}" '
            f'data-toc-id="{heading["id"]}">{html.escape(str(heading["text"]))}</a>'
        )
        for heading in headings
        if int(str(heading["level"])) <= 3
    )


def _documentation_page_navigation(current_page: DocumentationPage, language: str) -> str:
    index = DOCUMENTATION_PAGES.index(current_page)
    previous = DOCUMENTATION_PAGES[index - 1] if index else None
    next_page = DOCUMENTATION_PAGES[index + 1] if index + 1 < len(DOCUMENTATION_PAGES) else None
    if language == "de":
        previous_label, next_label = "Vorherige Seite", "Nächste Seite"
    else:
        previous_label, next_label = "Previous page", "Next page"
    previous_link = "<span></span>"
    next_link = "<span></span>"
    if previous is not None:
        previous_link = (
            f'<a class="page-nav-link previous" href="{_documentation_href(current_page["slug"], previous["slug"])}">'
            f"<span>←</span><p><small>{previous_label}</small><strong>{html.escape(_page_title(previous, language))}</strong></p></a>"
        )
    if next_page is not None:
        next_link = (
            f'<a class="page-nav-link next" href="{_documentation_href(current_page["slug"], next_page["slug"])}">'
            f"<p><small>{next_label}</small><strong>{html.escape(_page_title(next_page, language))}</strong></p><span>→</span></a>"
        )
    return f"{previous_link}{next_link}"


def _documentation_structured_data(
    current_page: DocumentationPage, canonical_url: str, language: str
) -> str:
    breadcrumb_items = [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "IDM Heatpump",
            "item": SITE_URL,
        },
        {
            "@type": "ListItem",
            "position": 2,
            "name": "Dokumentation" if language == "de" else "Documentation",
            "item": f"{SITE_URL}docs/" if language == "en" else f"{SITE_URL}docs/de/",
        },
    ]
    if current_page["slug"] != "home":
        breadcrumb_items.append(
            {
                "@type": "ListItem",
                "position": 3,
                "name": _page_title(current_page, language),
                "item": canonical_url,
            }
        )
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "@id": f"{canonical_url}#webpage",
                "url": canonical_url,
                "name": _page_title(current_page, language),
                "description": _page_description(current_page, language),
                "inLanguage": language,
                "isPartOf": {"@id": f"{SITE_URL}#website"},
                "breadcrumb": {"@id": f"{canonical_url}#breadcrumb"},
            },
            {
                "@type": "BreadcrumbList",
                "@id": f"{canonical_url}#breadcrumb",
                "itemListElement": breadcrumb_items,
            },
        ],
    }
    return f'<script type="application/ld+json">\n{json.dumps(data, indent=2, ensure_ascii=False)}\n</script>'


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
    prerelease = "-" in integration_version
    beta = bool(re.search(r"-(?:beta|b\d)", integration_version))
    release_label = "Beta-Version" if beta else "Vorabversion" if prerelease else "Aktuelle stabile Version"
    release_channel = "Beta" if beta else "Prerelease" if prerelease else "Stable"
    document = _replace_element_text(document, "data-release-label", release_label, required=False)
    document = _replace_element_text(document, "data-release-channel", release_channel, required=False)
    if "data-release-download" in document:
        document = _replace_tag_attribute(
            document,
            "data-release-download",
            None,
            "href",
            f"https://github.com/Xerolux/idm-heatpump-hass/releases/tag/v{integration_version}",
        )
    document = document.replace("__INTEGRATION_VERSION__", integration_version)
    document = document.replace("__MINIMUM_HA_VERSION__", minimum_ha_version)
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
        'content="IDM Heatpump für Home Assistant – lokale Wärmepumpen-Integration"': 'content="IDM Heatpump for Home Assistant – local heat pump integration"',
        'content="de_DE"': 'content="en_US"',
        "<title>IDM Wärmepumpe in Home Assistant | Modbus TCP Integration</title>": "<title>IDM Heat Pump for Home Assistant | Modbus TCP Integration</title>",
        f'<link rel="canonical" href="{SITE_URL}" />': f'<link rel="canonical" href="{SITE_URL}en/" />',
        f'<meta property="og:url" content="{SITE_URL}" />': f'<meta property="og:url" content="{SITE_URL}en/" />',
        f'"url": "{SITE_URL}"': f'"url": "{SITE_URL}en/"',
        'href="assets/': 'href="../assets/',
        'href="styles.css"': 'href="../styles.css"',
        'src="script.js"': 'src="../script.js"',
        'href="docs/de/': 'href="../docs/',
        'href="docs/': 'href="../docs/',
        # German anchors on the mapped-back English targets revert to the
        # English heading slugs (the English pages keep English headings).
        '../docs/smart-energy-and-comfort/#persistente-energie-statistiken': '../docs/smart-energy-and-comfort/#persistent-energy-statistics',
        '../docs/smart-energy-and-comfort/#optionale-pv-uberschuss-warmwasser-automation': '../docs/smart-energy-and-comfort/#optional-pv-surplus-dhw-automation',
        '../docs/smart-energy-and-comfort/#optionaler-idm-health-monitor': '../docs/smart-energy-and-comfort/#optional-idm-health-monitor',
        '../docs/configuration/#optionen': '../docs/configuration/#options',
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
    page = page.replace(' oder neuer"', ' or newer"')
    page = page.replace("IDM Energysysteme GmbH", "IDM Energiesysteme GmbH")
    return page


def _german_page_available(current_page: DocumentationPage) -> bool:
    return (GERMAN_WIKI_DIR / current_page["file"]).is_file()


def _documentation_canonical_url(slug: str, language: str) -> str:
    if language == "de":
        return f"{SITE_URL}docs/de/" if slug == "home" else f"{SITE_URL}docs/de/{slug}/"
    return f"{SITE_URL}docs/" if slug == "home" else f"{SITE_URL}docs/{slug}/"


def _language_alternates(current_page: DocumentationPage, language: str) -> str:
    """hreflang links between the English and German versions of one page."""
    if not _german_page_available(current_page):
        return ""
    english_url = _documentation_canonical_url(current_page["slug"], "en")
    german_url = _documentation_canonical_url(current_page["slug"], "de")
    if language == "de":
        return (
            f'    <link rel="alternate" hreflang="en" href="{english_url}" />\n'
            f'    <link rel="alternate" hreflang="x-default" href="{english_url}" />\n'
        )
    return (
        f'    <link rel="alternate" hreflang="de" href="{german_url}" />\n'
        f'    <link rel="alternate" hreflang="x-default" href="{english_url}" />\n'
    )


def _build_documentation_page(
    template: str, current_page: DocumentationPage, language: str = "en"
) -> str:
    if language == "de" and not _german_page_available(current_page):
        raise FileNotFoundError(f"Missing German wiki page: {GERMAN_WIKI_DIR / current_page['file']}")
    markdown_source = WIKI_DIR / current_page["file"] if language == "en" else GERMAN_WIKI_DIR / current_page["file"]
    markdown_html, headings = _render_markdown(markdown_source, current_page["slug"], language)
    canonical_url = _documentation_canonical_url(current_page["slug"], language)
    site_title_suffix = "IDM Heatpump for Home Assistant" if language == "en" else "IDM Heatpump Dokumentation"
    page_title = f"{_page_title(current_page, language)} | {site_title_suffix}"
    description = _page_description(current_page, language)
    page = template

    is_home = current_page["slug"] == "home"
    if language == "de":
        # The German tree lives one level deeper: docs/de/ and docs/de/<slug>/.
        asset_prefix = "../" if is_home else "../../"
        site_href = "../../" if is_home else "../../../"
    else:
        asset_prefix = "" if is_home else "../"
        site_href = "../" if is_home else "../../"
    if asset_prefix:
        page = page.replace('href="docs.css?', f'href="{asset_prefix}docs.css?')
        page = page.replace('src="vendor/', f'src="{asset_prefix}vendor/')
        page = page.replace('src="docs.js?', f'src="{asset_prefix}docs.js?')
    page = page.replace('class="docs-brand" href="../"', f'class="docs-brand" href="{site_href}"')
    page = page.replace('<div><a href="../">', f'<div><a href="{site_href}">')
    docs_root_href = "./" if is_home else "../"
    page = page.replace(
        '<a href="./" data-i18n="docs">Documentation</a>',
        f'<a href="{docs_root_href}" data-i18n="docs">Documentation</a>',
    )
    if language == "de":
        page = page.replace('<html lang="en"', '<html lang="de"')

    page = _replace_title(page, page_title)
    page = _replace_tag_attribute(
        page,
        "name",
        "description",
        "content",
        html.escape(description, quote=True),
    )
    for property_name, value in (
        ("og:title", page_title),
        ("og:description", description),
        ("og:url", canonical_url),
        ("og:image:alt", f"{_page_title(current_page, language)} – IDM Heatpump documentation"),
    ):
        page = _replace_tag_attribute(
            page,
            "property",
            property_name,
            "content",
            html.escape(value, quote=True),
        )
    for name, value in (
        ("twitter:title", page_title),
        ("twitter:description", description),
    ):
        page = _replace_tag_attribute(
            page,
            "name",
            name,
            "content",
            html.escape(value, quote=True),
        )
    page = _replace_tag_attribute(page, "rel", "canonical", "href", canonical_url)
    page = _replace_element_text(page, "data-navigation", _documentation_navigation(current_page, language))
    page = _replace_element_text(page, "data-breadcrumbs", _documentation_breadcrumbs(current_page, language))
    page = _replace_element_text(page, "data-toc", _documentation_toc(headings))
    page = _replace_element_text(
        page, "data-page-navigation", _documentation_page_navigation(current_page, language)
    )
    page = _replace_element_text(page, "data-article", markdown_html)
    page = page.replace("data-article>", f'data-article data-rendered-slug="{current_page["slug"]}">', 1)
    page = _replace_tag_attribute(
        page,
        "data-edit-link",
        None,
        "href",
        f"https://github.com/Xerolux/idm-heatpump-hass/edit/main/docs/wiki/"
        f"{'de/' if language == 'de' else ''}{current_page['file']}",
    )
    structured_data = _documentation_structured_data(current_page, canonical_url, language)
    page = page.replace("</head>", f"    {_language_alternates(current_page, language)}    {structured_data}\n  </head>", 1)
    return page


def _write_sitemap(output: Path) -> None:
    urls = [SITE_URL, f"{SITE_URL}en/", f"{SITE_URL}docs/"]
    for page in DOCUMENTATION_PAGES:
        if page["slug"] == "home":
            continue
        urls.append(f"{SITE_URL}docs/{page['slug']}/")
    urls.append(f"{SITE_URL}docs/de/")
    urls.extend(
        f"{SITE_URL}docs/de/{page['slug']}/"
        for page in DOCUMENTATION_PAGES
        if page["slug"] != "home" and _german_page_available(page)
    )
    entries = "\n".join(f"  <url>\n    <loc>{html.escape(url)}</loc>\n  </url>" for url in urls)
    sitemap = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}\n</urlset>\n'
    (output / "sitemap.xml").write_text(sitemap, encoding="utf-8")


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
    if GERMAN_WIKI_DIR.is_dir():
        german_content_output = content_output / "de"
        german_content_output.mkdir(parents=True, exist_ok=True)
        for markdown in GERMAN_WIKI_DIR.glob("*.md"):
            shutil.copy2(markdown, german_content_output / markdown.name)
    shutil.copytree(IMAGES_DIR, output / "docs" / "images", dirs_exist_ok=True)

    homepage_path = output / "index.html"
    homepage = _inject_metadata(homepage_path.read_text(encoding="utf-8"))
    homepage_path.write_text(homepage, encoding="utf-8")

    docs_template = (PUBLIC_DIR / "docs" / "index.html").read_text(encoding="utf-8")
    for documentation_page in DOCUMENTATION_PAGES:
        for language in ("en", "de"):
            if language == "de" and not _german_page_available(documentation_page):
                continue
            if documentation_page["slug"] == "home":
                docs_path = output / "docs" / "index.html" if language == "en" else output / "docs" / "de" / "index.html"
            elif language == "en":
                docs_path = output / "docs" / documentation_page["slug"] / "index.html"
            else:
                docs_path = output / "docs" / "de" / documentation_page["slug"] / "index.html"
            docs_path.parent.mkdir(parents=True, exist_ok=True)
            docs_page = _inject_metadata(
                _build_documentation_page(docs_template, documentation_page, language)
            )
            docs_path.write_text(docs_page, encoding="utf-8")

    english_path = output / "en" / "index.html"
    english_path.parent.mkdir(parents=True, exist_ok=True)
    english_path.write_text(_english_homepage(homepage), encoding="utf-8")
    _write_sitemap(output)


def main() -> None:
    """Build the Pages artifact from command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    build_site(arguments.output)


if __name__ == "__main__":
    main()
