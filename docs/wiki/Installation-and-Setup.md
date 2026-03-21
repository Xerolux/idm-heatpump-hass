# Installation & Setup

## Voraussetzungen

- **Home Assistant** 2025.8.0 oder neuer
- **HACS** ([Installationsanleitung](https://hacs.xyz/docs/setup/download))
- **IDM Navigator 2.0** Warmepumpe mit aktiviertem Modbus TCP
- Modbus TCP muss in der Navigator-Steuerung aktiviert sein (Port 502, Slave ID 1)

## Modbus TCP auf dem Navigator aktivieren

1. Offne das Navigator-Webinterface (ip-des-navigators)
2. Gehe zu **Einstellungen → Kommunikation → Modbus TCP**
3. Aktiviere Modbus TCP
4. Notiere dir die **IP-Adresse** und den **Port** (Standard: 502)
5. Slave ID ist in der Regel **1**

## Installation uber HACS (empfohlen)

1. Offne HACS in Home Assistant
2. Gehe zu **Integrationen**
3. Klicke auf **⋮ (Drei Punkte)** → **Benutzerdefinierte Repositories**
4. Gib die URL ein: `https://github.com/Xerolux/idm-heatpump-hass`
5. Wahle **Kategorie: Integration**
6. Klicke auf **Hinzufugen**
7. Suche nach **"IDM Heatpump"**
8. Klicke auf **Herunterladen**
9. **Starte Home Assistant neu**

## Manuelle Installation

1. Lade die neueste [Release](https://github.com/Xerolux/idm-heatpump-hass/releases) herunter (`idm_heatpump_v2.zip`)
2. Entpacke die ZIP-Datei
3. Kopiere den Ordner `idm_heatpump_v2` in dein `custom_components/` Verzeichnis:
   ```
   <ha-config>/custom_components/idm_heatpump_v2/
   ```
4. Starte Home Assistant neu

## Einrichtung

1. Gehe zu **Einstellungen → Gerate & Dienste**
2. Klicke auf **Integration hinzufugen**
3. Suche nach **"IDM Heatpump"**
4. Folge dem Konfigurationsassistenten:
   - **Schritt 1**: IP-Adresse, Port (502) und Name eingeben
   - **Schritt 2**: Scan-Intervall, Heizkreise (A-G), Zonenanzahl
   - **Schritt 3**: Raumnamen fur Zonen konfigurieren
5. Klicke auf **Fertig stellen**

## Deinstallation

1. Gehe zu **Einstellungen → Gerate & Dienste**
2. Finde die **IDM Heatpump** Integration
3. Klicke auf die drei Punkte → **Loschen**
4. (Optional) Losche den Ordner `custom_components/idm_heatpump_v2/`
5. Starte Home Assistant neu

## Upgrade

Uber HACS: Gehe zu HACS → Integrationen → IDM Heatpump → "Aktualisieren" → HA neu starten.

Manuell: Wiederhole die manuelle Installation (uberschreibt die alten Dateien).
