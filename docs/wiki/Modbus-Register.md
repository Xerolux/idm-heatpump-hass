# Modbus-Register

## Uberblick

Die IDM Navigator 2.0 Warmepumpe stellt **663 Register** uber Modbus TCP zur Verfugung:

| Typ | Anzahl |
|-----|--------|
| Schreibgeschutzt (RO) | 215 |
| Lesen/Schreiben (RW) | 266 |
| Nur Schreiben (W) | 16 |
| Kontextabhangig | 166 |

## Adressbereiche

| Bereich | Adressen | Beschreibung |
|---------|----------|-------------|
| PV/Batterie | 74-86 | Photovoltaik und Batterie |
| System | 1000-1199 | Systemparameter, Temperaturen, Drucke |
| Kaskade/Bivalenz | 1200-1349 | Mehrfach-WP, Heizstab |
| Heizkreise A-G | 1350-1699 | Einzelne Heizkreise |
| GLT/Energie | 1700-1799 | Fernwartung, Energiemessung |
| Zonen 1-10 | 2000-2999 | Zonenmodule mit Raumsteuerung |

## Datentypen

| Typ | Beschreibung | Register |
|-----|-------------|----------|
| **FLOAT** | IEEE 754 Gleitkomma (2 Register, Little Endian `<f` / `<HH`) | 2 |
| **UCHAR** | 8-Bit vorzeichenlos (in 16-Bit Register, oft mit Multiplikator) | 1 |
| **INT8** | 8-Bit vorzeichenbehaftet (für negative Werte wie Parallelverschiebung) | 1 |
| **UINT16** | 16-Bit vorzeichenlos (z.B. für Leistungsbegrenzungen) | 1 |
| **INT16** | 16-Bit vorzeichenbehaftet (z.B. für Bivalenzpunkte bis -20°C) | 1 |
| **BOOL** | Boolean (0/1) | 1 |

> **Wichtig:** Beim Schreiben von Integer-Werten (`UCHAR`, `INT8`, `INT16`, `UINT16`) wendet die Integration automatisch den im Code hinterlegten `multiplier` an und rundet den Wert passend.

## Modbus-Parameter

| Parameter | Wert |
|-----------|------|
| Protokoll | Modbus TCP |
| Standard-Port | 502 |
| Slave ID | 1 |
| FC Lesen | 03 (Read Input Registers) |
| FC Schreiben | 16 (Write Multiple Registers) |

## Zonen-Base-Adressen

| Zone | Base-Adresse | Modus-Adresse |
|------|-------------|---------------|
| Zone 1 | 2000 | 2059 |
| Zone 2 | 2067 | 2126 |
| Zone 3 | 2130 | 2189 |
| Zone 4 | 2193 | 2252 |
| Zone 5 | 2256 | 2315 |
| Zone 6 | 2319 | 2378 |
| Zone 7 | 2382 | 2441 |
| Zone 8 | 2445 | 2504 |
| Zone 9 | 2508 | 2567 |
| Zone 10 | 2571 | 2630 |

## Besondere Register

| Adresse | Beschreibung | Besonderheit |
|---------|-------------|-------------|
| 1999 | Fehler-Quittierung | Darf NICHT permanent beschrieben werden |
| 1696 | GLT Warmeanforderung | Muss zyklisch alle 10 Min beschrieben werden |
| 1698 | GLT Kuhlanforderung | Muss zyklisch alle 10 Min beschrieben werden |

## EEPROM-sensitive Register

88 Register sind EEPROM-sensitive und haben eine beschrankte Anzahl an Schreibzyklen. Die Integration warnt automatisch vor haufigem Schreiben dieser Register.
