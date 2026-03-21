# Konfiguration

## Verbindungsparameter

| Parameter | Beschreibung | Standard |
|-----------|-------------|----------|
| **Host (IP)** | IP-Adresse des IDM Navigators | - (erforderlich) |
| **Port** | Modbus TCP Port | 502 |
| **Name** | Name der Integration (zur Unterscheidung bei mehreren) | IDM Navigator |

## Optionen

### Scan-Intervall

Das Scan-Intervall bestimmt, wie haufig die Register ausgelesen werden.

| Wert | Empfehlung |
|------|-----------|
| 10 Sekunden | Fur aktive Uberwachung (Standard) |
| 30 Sekunden | Ausgewogen |
| 60 Sekunden | Fuer ruhigere Systeme |

### Heizkreise

Wahle die aktiven Heizkreise (A bis G). Nur aktivierte Heizkreise erstellen Entities in Home Assistant.

### Zonen

Gib die Anzahl der Zonen-Module an (0-10). Jedes Zonen-Modul unterstutzt bis zu 8 Raume.

### Fachmann-Ebene Codes

Aktiviere diese Option, um zwei zusätzliche Sensor-Entities zu erhalten, die die aktuellen Fachmann-Ebene-Zugriffscodes anzeigen:

| Sensor | Beschreibung |
|--------|-------------|
| `sensor.{name}_fachmann_ebene_1` | 4-stelliger Code: Tag + Monat (`TTMM`) |
| `sensor.{name}_fachmann_ebene_2` | 5-stelliger Code aus Stunde, Jahr, Monat, Tag |

Die Codes werden automatisch jede Minute aktualisiert und können z. B. in einer HA-Dashboard-Karte oder Benachrichtigung angezeigt werden. Sie entsprechen den Codes, die am IDM Navigator-Display unter *Fachmannebene* eingegeben werden müssen.

### Raumnamen

Fur jeden Raum in jeder Zone kannst du einen individuellen Namen vergeben. Diese Namen werden als Entity-Namen in Home Assistant verwendet.

## Rekonfiguration

1. Gehe zu **Einstellungen → Gerate & Dienste**
2. Klicke auf **IDM Heatpump**
3. Klicke auf **Rekonfigurieren**
4. Anderungen am Scan-Intervall, Heizkreisen und Zonen werden ubernommen

## Debug-Logging

Aktiviere erweitertes Logging zur Fehlerbehebung:

```yaml
logger:
  default: info
  logs:
    custom_components.idm_heatpump_v2: debug
```

## EEPROM-Hinweis

Bestimmte Register sind **EEPROM-sensitive** (88 insgesamt). Diese Register werden beim Schreiben in den EEPROM gespeichert und haben eine beschrankte Anzahl an Schreibzyklen. Die Integration warnt vor zu haufigem Schreiben dieser Register.

## GLT-Zyklisches Schreiben

Die Register 1696 und 1698 (GLT-Temperaturanforderungen) mussen alle 10 Minuten zyklisch beschrieben werden, um aktiv zu bleiben. Die Switch-Entities fur GLT-Anforderungen handhaben dies automatisch.
