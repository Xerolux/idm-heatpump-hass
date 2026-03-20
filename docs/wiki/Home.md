# IDM Navigator Heatpump - Home Assistant Integration

> **Die komplette Dokumentation** fur das IDM Navigator Heatpump Addon.
> Von der Installation bis zur Fehlerbehebung - mit allen Features, Entities und Services.

---

## Was ist das IDM Navigator Heatpump Addon?

Das **IDM Navigator Heatpump Home Assistant Integration** verbindet [Home Assistant](https://www.home-assistant.io/) mit dem [IDM Navigator 2.0](https://www.idm-energiesysteme.de/) von IDM EnergieSysteme GmbH. Es ermoglicht vollstandige lokale Steuerung und Uberwachung deiner Warmepumpe uber **Modbus TCP - ohne Cloud, ohne Abonnement**.

| Feature | Details |
|---------|---------|
| **Protokoll** | Modbus TCP (Port 502, Slave ID 1) |
| **HA-Mindestversion** | 2025.8.0 |
| **Getestet bis** | 2026.x |
| **Python** | 3.12+ |
| **Lizenz** | MIT |
| **Sprachen** | DE, EN |
| **Register** | 663 (215 RO, 266 RW, 16 W-only, 166 kontextabhangig) |

---

## Kernfunktionen

- **System-Uberwachung**: Vorlauf, Rucklauf, Warmwasser, Aussentemperatur, Druck, Durchfluss
- **Heizkreise A-G**: Bis zu 7 Heizkreise mit individueller Sollwert- und Modussteuerung
- **Zonen-Module**: Bis zu 10 Zonen mit je 8 Raumen (Raumthermostat-Funktion)
- **Solar & PV**: Solare Warmwasserbereitung, PV-Uberschussnutzung, Batteriemonitoring
- **Energiemonitoring**: Warmemenge, Laufzeiten, Energiezahler
- **Kaskade & Bivalenz**: Mehrfach-Warmepumpen-Steuerung, Heizstab-Integration
- **GLT Fernwartung**: GLT-Temperaturanforderungen (zyklisches Schreiben)
- **Fehlermanagement**: Fehlererkennung, Fehlerquittierung, Diagnosedaten-Export

---

## Plattformen & Entities

| Plattform | Entities | Beschreibung |
|-----------|----------|--------------|
| **Sensor** | 100+ | Temperaturen, Drucke, Durchflusse, Energie, Laufzeiten |
| **Binary Sensor** | 9 | Fehlerstatus, Schaltzustande |
| **Number** | ~30 | Sollwerte, beschreibbare Parameter |
| **Select** | ~15 | Betriebsmodi (System, Heizkreis, Raum, Solar) |
| **Switch** | 4 | GLT-Temperaturanforderungen |

---

## Schnell-Navigation

### Ich bin neu hier
1. [Installation & Setup](Installation-and-Setup)
2. [Konfiguration](Configuration)
3. [Entities](Entities)

### Ich will automatisieren
1. [Services Referenz](Services)

### Ich habe ein Problem
1. [Troubleshooting](Troubleshooting)
2. [Modbus-Register](Modbus-Register)

### Ich will beitragen
- [Contributing Guide](Contributing)

---

## Technische Details

- **Batch-Lesung**: Zusammenhangende Register werden gruppiert (max. 30 pro Batch)
- **Datentypen**: FLOAT (IEEE 754, 2 Register), UCHAR (8-bit), WORD (16-bit), BOOL
- **EEPROM-Schutz**: 88 EEPROM-sensitive Register werden vor zu haufigem Schreiben geschutzt
- **Auto-Recovery**: Exponentielles Backoff bei Verbindungsfehlern
- **Adressbereiche**: 74-86 (PV/Battery), 1000-1199 (System), 1200-1349 (Kaskade), 1350-1699 (Heizkreise A-G), 1700-1799 (GLT/Energie), 2000-2999 (Zonen)

---

## Links & Ressourcen

| Ressource | Link |
|-----------|------|
| GitHub Repository | https://github.com/Xerolux/idm-heatpump-hass |
| Issues & Bugs | https://github.com/Xerolux/idm-heatpump-hass/issues |
| HACS | https://hacs.xyz/ |
| Home Assistant | https://www.home-assistant.io/ |
| IDM EnergieSysteme | https://www.idm-energiesysteme.de/ |
| Community Forum | https://community.home-assistant.io/ |

---

*Diese Wiki dokumentiert das IDM Navigator Heatpump Addon.*
*Entwickelt von [Xerolux](https://github.com/Xerolux)*
