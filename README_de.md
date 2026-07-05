**[English](README.md)** | **Deutsch**

# 🔥 IDM Heatpump für Home Assistant

[![GitHub Release][releases-shield]][releases]
[![Downloads][downloads-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hainstall][hainstallbadge]][hainstall]
[![HACS][hacs-badge]][hacs]

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

[![Release Management](https://github.com/Xerolux/idm-heatpump-hass/actions/workflows/release.yml/badge.svg)](https://github.com/Xerolux/idm-heatpump-hass/actions/workflows/release.yml)

> **Steuerung und Überwachung deiner IDM Navigator Wärmepumpe direkt in Home Assistant – 100% lokal über Modbus TCP.**

<p align="center">
  <img src="https://raw.githubusercontent.com/Xerolux/idm-heatpump-hass/main/docs/images/heatpump.png" alt="IDM Heatpump" width="300"><br>
  <small><i>KI generiertes Bild</i></small>
</p>

---

## 🌟 Features

| Kategorie | Was ist enthalten |
|-----------|-------------------|
| **🌡️ System-Überwachung** | Vorlauf, Rücklauf, Warmwasser, Außentemperatur, Druck, Durchfluss |
| **🔧 Heizkreise A–G** | Bis zu 7 Heizkreise mit individueller Sollwert- und Modussteuerung |
| **🏠 Zonen-Module** | Bis zu 10 Zonen mit je 6 Räumen (Raumthermostat-Funktion). Navigator 10 / aktuelle Hardware verwendet 6 Räume pro Modul. |
| **🌡️ Raumtemperatur-Weitergabe** | Optionale Weitergabe von Home-Assistant-Temperatursensoren an die externen IDM-Raumtemperaturregister pro Heizkreis |
| **💧 Warmwasser** | Warmwasser-Sollwert und Prioritätssteuerung |
| **☀️ Solar & PV** | Solare Warmwasserbereitung, PV-Überschussnutzung |
| **⚡ Energiemonitoring** | Wärmemenge, Laufzeiten, Energiezähler |
| **❄️ Kaskade & Bivalenz** | Mehrfach-Wärmepumpen-Steuerung, Heizstab-Integration |
| **📡 GLT Fernwartung** | GLT-Temperaturanforderungen (zyklisches Schreiben) |
| **🛡️ Fehlermanagement** | Fehlererkennung, lesbare interne Meldungen, Fehlerquittierung, Diagnosedaten-Export |
| **🔑 Fachmann-Ebene** | Optionale Sensoren für Fachmann Ebene 1 & 2 Codes (zeitbasiert, minütlich aktualisiert und ganz oben angeheftet) |
| **🔒 Sicherheit** | 100% lokal, Modbus TCP, EEPROM-Schutz, EEPROM-sensitive Register |

---

## ⚡ Schnellstart

**1. HACS – Integration hinzufügen**

<a href="https://my.home-assistant.io/redirect/hacs_repository/?repository=https%3A%2F%2Fgithub.com%2FXerolux%2Fidm-heatpump-hass&owner=Xerolux&category=Integration" target="_blank" rel="noopener noreferrer"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

```
HACS → Integrationen → ⋮ → Benutzerdefinierte Repositories
URL: https://github.com/Xerolux/idm-heatpump-hass  |  Kategorie: Integration
→ "IDM Heatpump" herunterladen → HA neu starten
```

**2. Integration einrichten**
```
Einstellungen → Geräte & Dienste → Integration hinzufügen → "IDM Heatpump"
IP-Adresse & Port eingeben → Heizkreise & Zonen konfigurieren → Fertig!
```

**3. Fertig!** 🎉 Deine Wärmepumpe ist jetzt smart.

> Detaillierte Anleitung → **[Installation & Setup][wiki-install]**

---

## 📖 Dokumentation (Wiki)

Die vollständige Dokumentation befindet sich im **[Wiki][wiki]**:

| Bereich | Seiten |
|---------|--------|
| 🚀 **Erste Schritte** | [Installation & Setup][wiki-install] · [Konfiguration][wiki-config] |
| 📊 **Entities** | [Alle Entities][wiki-entities] · [Sensoren][wiki-sensors] · [Schalter][wiki-switches] · [Selects][wiki-selects] · [Numbers][wiki-numbers] |
| ⚙️ **Automatisierung** | [Services Referenz][wiki-services] |
| 🔧 **Betrieb** | [Troubleshooting][wiki-trouble] · [Modbus-Register][wiki-registers] |
| 👩‍💻 **Entwicklung** | [Contributing][wiki-contributing] · [Changelog][wiki-changelog] |

Maintainer sollten vor einem stabilen Release den
**[Release-Smoke-Test](docs/RELEASE_SMOKE_TEST.md)** ausführen.

---

## 🔑 Voraussetzungen

- Home Assistant **2026.5.0+**
- HACS ([Installationsanleitung](https://hacs.xyz/docs/setup/download))
- IDM Navigator 2.0 / 10 Wärmepumpe mit aktiviertem Modbus TCP (Port 502)
- Optionale lokale Navigator-Web-PIN für zusätzliche read-only Webdiagnosen
- Python 3.14.2+ (wird von Home Assistant 2026.5 bereitgestellt)
- `pymodbus>=3.12.1,<4.0` · `idm-heatpump-api[web]>=0.5.1,<0.6` (automatisch installiert)

---

## 📋 Unterstützte Plattformen

| Plattform | Entities | Beschreibung |
|-----------|----------|--------------|
| **Sensor** | 100+ | Temperaturen, Drücke, Durchflüsse, Energie, Laufzeiten, Fehlercodes |
| **Binary Sensor** | 9 | Fehlerstatus, Schaltzustände, Alarme |
| **Number** | ~30 | Sollwerte, Temperaturen, Parameter (beschreibbar) |
| **Select** | ~15 | Betriebsmodi, Heizkreis-Modi, Raum-Modi, Solar-Modi |
| **Switch** | 4 | GLT-Temperaturanforderungen, Fernwartung |

---

## 🏗️ Architektur

```
Home Assistant
    │
    ├── IdmCoordinator (DataUpdateCoordinator, konfigurierbares Polling)
    │       │
    │       ├── IdmModbusClient (pymodbus, async, Batch-Lesung)
    │       │       │
    │       │       └── IDM Navigator 2.0 / 10 (Modbus TCP, Port 502, Slave ID 1)
    │       │               FC 03: Read Input Registers
    │       │               FC 16: Write Multiple Registers
    │       │
    │       ├── Optionale lokale Web-Zusatzdaten (PIN, read-only, eigenes Intervall)
    │       │
    │       ├── Optionaler RoomTempForwarder (HA-Sensoren -> externe Raumtemperaturregister)
    │       │
    │       └── Entities (sensor, binary_sensor, number, select, switch)
    │
    ├── Services (set_system_mode, acknowledge_errors, write_register)
    │
    └── Diagnostics (JSON-Export via HA UI)
```

### Technische Details

- **663 Register** insgesamt (215 RO, 266 RW, 16 W-only, 166 kontextabhängig)
- **Batch-Lesung**: Zusammenhängende Register werden gruppiert (max. 30 pro Batch)
- **Datentypen**: FLOAT (IEEE 754, 2 Register), UCHAR (8-bit), WORD (16-bit), BOOL
- **EEPROM-Schutz**: 88 EEPROM-sensitive Register werden vor zu häufigem Schreiben geschützt
- **Auto-Recovery**: Exponentielles Backoff bei Verbindungsfehlern
- **Optionale Web-Zusatzdaten**: lokale read-only Erkennung von Navigator-Generation, Softwareversion, Modell, kompakter myIDM ID und Webdiagnosen; Standardintervall 30 Sekunden, Modbus bleibt führend
- **Raumtemperatur-Weitergabe**: standardmäßig deaktiviert; kann ausgewählte Home-Assistant-Temperatursensoren pro Heizkreis an die externen IDM-Raumtemperaturregister weitergeben, mit 300 Sekunden Standardintervall, sofortiger Weitergabe bei Zustandsänderung, 0,2 °C Standardtoleranz und Bereichsprüfung
- **Lesbare Diagnose**: der Sensor `internal_message` zeigt Klartext und liefert zusätzlich die Attribute `message_code` und `message_text` statt nur einer nackten Nummer
- **Entity-Ordnung**: Fachmann-Code-Sensoren sind ganz oben angeheftet, danach folgen sinnvolle Funktionsgruppen für Konfiguration, Schalter, schreibbare Werte und Diagnose

---

## 💝 Unterstützung

Diese Integration wird in meiner Freizeit entwickelt:

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

- ⭐ Repository auf GitHub sternen
- 🐛 [Bugs melden][issues]
- 📢 Mit anderen Wärmepumpen-Besitzern teilen
- 💬 Anderen in der [Community][forum] helfen

---

## 🔥 Über IDM Navigator

Der **IDM Navigator 2.0 / 10** von [IDM EnergieSysteme GmbH](https://www.idm-energiesysteme.de/) ist ein modulares Wärmepumpen-Steuerungssystem mit Modbus TCP-Schnittstelle für nahtlose Home Assistant Integration.

- **Offizieller Shop:** [idm-energiesysteme.de](https://www.idm-energiesysteme.de/)
- **Modbus-Dokumentation:** Navigator 2.0 / 10 Modbus TCP Registerbeschreibung

---

## ⚠️ Haftungsausschluss / Disclaimer

Dieses Projekt ist ein **inoffizielles Community-Projekt** und steht in **keiner Verbindung** zu IDM Energiesysteme GmbH.

- Alle Marken, Logos und Produktnamen (z.B. „IDM", „Navigator") sind Eigentum ihrer jeweiligen Inhaber.
- Die verwendeten Logos und Bilder dienen ausschließlich der Identifikation des kompatiblen Geräts und werden nicht kommerziell genutzt.
- Dieses Projekt wird ohne jegliche Garantie bereitgestellt. Die Nutzung erfolgt auf eigene Gefahr — insbesondere beim Schreiben von Modbus-Registern.
- IDM Energiesysteme GmbH hat dieses Projekt weder autorisiert noch unterstützt.

> This project is an **unofficial community integration** and is **not affiliated with, endorsed by, or connected to IDM Energiesysteme GmbH** in any way. All trademarks and product names belong to their respective owners.

---

<div align="center">

**Made with ❤️ for the Home Assistant & Wärmepumpen Community**

[![GitHub][github-shield]][github]

</div>

---

<!-- Wiki Links -->
[paypal]: https://paypal.me/xerolux
[wiki]: https://github.com/Xerolux/idm-heatpump-hass/wiki
[wiki-install]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Installation-and-Setup
[wiki-config]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Configuration
[wiki-entities]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Entities
[wiki-sensors]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Entities#sensoren
[wiki-switches]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Entities#schalter-switch
[wiki-selects]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Entities#selects
[wiki-numbers]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Entities#numbers
[wiki-services]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Services
[wiki-trouble]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Troubleshooting
[wiki-registers]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Modbus-Register
[wiki-contributing]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing
[wiki-changelog]: https://github.com/Xerolux/idm-heatpump-hass/wiki/Changelog
[violet]: https://github.com/Xerolux/violet-hass

<!-- Badge Links -->
[releases-shield]: https://img.shields.io/github/release/Xerolux/idm-heatpump-hass.svg?style=for-the-badge
[releases]: https://github.com/Xerolux/idm-heatpump-hass/releases
[downloads-shield]: https://img.shields.io/github/downloads/Xerolux/idm-heatpump-hass/latest/total.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/Xerolux/idm-heatpump-hass.svg?style=for-the-badge
[commits]: https://github.com/Xerolux/idm-heatpump-hass/commits/main
[license-shield]: https://img.shields.io/github/license/Xerolux/idm-heatpump-hass.svg?style=for-the-badge
[hainstall]: https://my.home-assistant.io/redirect/config_flow_start/?domain=idm_heatpump
[hainstallbadge]: https://img.shields.io/badge/dynamic/json?style=for-the-badge&logo=home-assistant&logoColor=ccc&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.idm_heatpump.total
[hacs]: https://hacs.xyz
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[github-sponsors]: https://github.com/sponsors/xerolux
[sponsor-badge]: https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue
[kofi]: https://ko-fi.com/xerolux
[kofi-badge]: https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge
[bmac]: https://www.buymeacoffee.com/xerolux
[bmac-badge]: https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge
[forum]: https://community.home-assistant.io/
[github]: https://github.com/Xerolux/idm-heatpump-hass
[github-shield]: https://img.shields.io/badge/GitHub-Xerolux/idm--heatpump--hass-blue?style=for-the-badge&logo=github
[issues]: https://github.com/Xerolux/idm-heatpump-hass/issues
