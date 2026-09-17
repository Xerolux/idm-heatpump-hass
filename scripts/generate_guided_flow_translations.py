"""Keep the guided wizard labels aligned with the existing options catalog."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("custom_components/idm_heatpump")
FILES = (ROOT / "strings.json", ROOT / "translations/en.json", ROOT / "translations/de.json")
FEATURES = (
    "plant",
    "profile",
    "health",
    "energy",
    "energy_manager",
    "comfort",
    "heating_curve",
    "weather",
    "web",
    "room_forwarding",
    "humidity_forwarding",
    "storage_forwarding",
    "external_power",
    "knx",
    "cascade",
    "device_hierarchy",
    "technician_codes",
    "modbus",
)
LABELS = {
    "en": (
        "Plant, heating circuits and zones",
        "Entity profile",
        "Health monitor",
        "Energy costs and carbon",
        "Automatic PV hot water",
        "Comfort schedule",
        "Heating curve advice",
        "Weather advice",
        "Local Navigator web data",
        "Room temperature forwarding",
        "Humidity forwarding",
        "Storage temperature forwarding",
        "External power and battery sensors",
        "KNX bridge",
        "Cascade registers",
        "Device grouping",
        "Technician code sensors",
        "Modbus transport",
    ),
    "de": (
        "Anlage, Heizkreise und Zonen",
        "Entitätsprofil",
        "Health Monitor",
        "Energiekosten und CO₂",
        "Automatische PV-Warmwasserladung",
        "Komfort-Zeitplan",
        "Heizkurven-Hinweise",
        "Wetter-Hinweise",
        "Lokale Navigator-Webdaten",
        "Raumtemperatur weitergeben",
        "Feuchte weitergeben",
        "Speichertemperatur weitergeben",
        "Externe Leistung und Batterie-Sensoren",
        "KNX-Bridge",
        "Kaskadenregister",
        "Geräte gruppieren",
        "Fachmann-Code-Sensoren",
        "Modbus-Verbindung",
    ),
}
PROSE = {
    "en": {
        "mode_title": "Choose setup depth",
        "mode_description": "All three levels offer every function. Standard uses safe defaults, Advanced adds common adjustments, and Expert exposes all parameters. Existing values remain saved when you change levels.",
        "choose_title": "What would you like to configure?",
        "choose_description": "Select only the functions you want to add, remove, or edit. Unselected functions and their saved settings stay as they are. Each selected function gets its own short page.",
        "toggle_title": "Enable or disable this function",
        "toggle_description": "Choose whether this function should run. Turning it off keeps its detailed settings for later use.",
        "detail_title": "Configure this function",
        "detail_description": "Only the selected function's settings are shown. Your setup level determines the amount of detail; hidden settings retain their saved values.",
        "review_title": "Review and save",
        "review_description": "Functions selected for editing: {selected_count}. Saving reloads the integration and updates its entities. Review automatic controls and KNX settings before confirming.",
        "mode_field": "Setup depth",
        "choose_field": "Functions to configure",
        "review_field": "Save this configuration",
        "review_error": "Confirm the summary before saving.",
        "weather_error": "Choose a weather entity for weather advice.",
    },
    "de": {
        "mode_title": "Einrichtungstiefe wählen",
        "mode_description": "Alle drei Stufen bieten jede Funktion. Standard nutzt passende Vorgaben, Erweitert ergänzt häufige Anpassungen und Experte zeigt alle Parameter. Beim Wechsel bleiben gespeicherte Werte erhalten.",
        "choose_title": "Was möchtest du konfigurieren?",
        "choose_description": "Wähle nur Funktionen aus, die du hinzufügen, entfernen oder ändern möchtest. Alle anderen Funktionen und ihre Einstellungen bleiben bestehen. Jede Auswahl erhält eine eigene kurze Seite.",
        "toggle_title": "Funktion aktivieren oder deaktivieren",
        "toggle_description": "Lege fest, ob diese Funktion aktiv sein soll. Beim Ausschalten bleiben ihre Detailwerte für eine spätere Aktivierung gespeichert.",
        "detail_title": "Funktion konfigurieren",
        "detail_description": "Hier erscheinen nur Einstellungen dieser Funktion. Die gewählte Stufe bestimmt die Tiefe; ausgeblendete Werte bleiben gespeichert.",
        "review_title": "Prüfen und speichern",
        "review_description": "Zur Bearbeitung ausgewählte Funktionen: {selected_count}. Beim Speichern wird die Integration neu geladen und die Entitäten werden angepasst. Prüfe automatische Steuerungen und KNX-Einstellungen vor der Bestätigung.",
        "mode_field": "Einrichtungstiefe",
        "choose_field": "Funktionen zum Konfigurieren",
        "review_field": "Diese Konfiguration speichern",
        "review_error": "Bestätige die Übersicht vor dem Speichern.",
        "weather_error": "Wähle eine Wetter-Entität für den Wetter-Hinweis.",
    },
}


def update(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    lang = "de" if path.name == "de.json" else "en"
    words = PROSE[lang]
    options = data["options"]["step"]["options"]
    labels = dict(options["data"])
    descriptions = dict(options.get("data_description", {}))
    for group in options["sections"].values():
        labels.update(group["data"])
        descriptions.update(group.get("data_description", {}))
    for root in ("config", "options"):
        steps = data[root]["step"]
        steps["guided_mode"] = {
            "title": words["mode_title"],
            "description": words["mode_description"],
            "data": {"setup_level": words["mode_field"]},
        }
        steps["guided_choose"] = {
            "title": words["choose_title"],
            "description": words["choose_description"],
            "data": {"selected_features": words["choose_field"]},
        }
        steps["guided_toggle"] = {
            "title": words["toggle_title"],
            "description": words["toggle_description"],
            "data": labels,
        }
        steps["guided_detail"] = {
            "title": words["detail_title"],
            "description": words["detail_description"],
            "data": labels,
            "data_description": descriptions,
        }
        steps["guided_review"] = {
            "title": words["review_title"],
            "description": words["review_description"],
            "data": {"save_configuration": words["review_field"]},
        }
        data[root]["error"]["guided_review_required"] = words["review_error"]
        data[root]["error"]["weather_entity_required"] = words["weather_error"]
    data["selector"]["setup_profile"] = {
        "options": {
            "standard": "Standard",
            "advanced": "Advanced" if lang == "en" else "Erweitert",
            "expert": "Expert" if lang == "en" else "Experte",
        }
    }
    data["selector"]["guided_level"] = data["selector"]["setup_profile"]
    data["selector"]["guided_features"] = {"options": dict(zip(FEATURES, LABELS[lang], strict=True))}
    setup = data["config"]["step"]["setup_review"]
    setup["data_description"]["profile"] = words["mode_description"]
    if lang == "en":
        setup["description"] = setup["description"].replace(
            "Then choose a guided profile or Custom for every option.",
            "Then choose the setup depth. Every level offers every function through short guided steps.",
        )
    else:
        setup["description"] = setup["description"].replace(
            "Wähle anschließend ein geführtes Profil oder Benutzerdefiniert für alle Optionen.",
            "Wähle anschließend die Einrichtungstiefe. Jede Stufe bietet alle Funktionen in kurzen Schritten.",
        )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    for path in FILES:
        update(path)
