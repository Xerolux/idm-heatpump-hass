# API Issues — idm-heatpump Library (v0.2.1)

Diese Register fehlen in der Library oder haben falsche Typen.  
Nach Fix: neue Library-Version taggen, dann im HA-Integration `manifest.json` bumpen.

---

## 1. Fehlende Register (komplett absent)

### 1.1 PV / Energiemanagement (Adressen 74–86)

| Adresse | Name | Datentyp | Einheit | Beschreibung |
|---------|------|----------|---------|--------------|
| 74 | `pv_surplus` | FLOAT | kW | PV-Überschuss |
| 76 | `electric_heater_power` | FLOAT | kW | Leistung E-Heizstab |
| 78 | `pv_production` | FLOAT | kW | PV Produktion |
| 82 | `home_consumption` | FLOAT | kW | Hausverbrauch |
| 84 | `battery_discharge` | FLOAT | kW | Batterie Entladung |
| 86 | `battery_level` | FLOAT | % | Batteriefüllstand |

### 1.2 Solarthermie (Adressen 1850–1857)

| Adresse | Name | Datentyp | Einheit | Schreibbar | Beschreibung |
|---------|------|----------|---------|------------|--------------|
| 1850 | `solar_collector_temp` | FLOAT | °C | nein | Solar Kollektortemperatur |
| 1852 | `solar_return_temp` | FLOAT | °C | nein | Solar Kollektorrücklauftemperatur |
| 1854 | `solar_charge_temp` | FLOAT | °C | nein | Solar Ladetemperatur |
| 1856 | `solar_mode` | UCHAR | – | **ja** | Solar Betriebsart (enum: 0=Aus, 1=Automatik, 2=Manuell) |
| 1857 | `solar_reference_temp` | FLOAT | °C | nein | Solar WQ-Referenztemperatur / Pooltemperatur |

### 1.3 ISC — Intelligent Surface Cooling (Adressen 1870–1874)

| Adresse | Name | Datentyp | Einheit | Schreibbar | Beschreibung |
|---------|------|----------|---------|------------|--------------|
| 1870 | `isc_charge_cooling_temp` | FLOAT | °C | nein | ISC Ladetemperatur Kühlen |
| 1872 | `isc_recooling_temp` | FLOAT | °C | nein | ISC Rückkühltemperatur |
| 1874 | `isc_mode` | UCHAR | – | **ja** | ISC Modus (enum: 0=Aus, 1=Automatik, 2=Manuell) |

### 1.4 Kaskade Temperaturen (Adressen 1200–1210)

| Adresse | Name | Datentyp | Einheit | Beschreibung |
|---------|------|----------|---------|--------------|
| 1200 | `cascade_req_heat_temp` | FLOAT | °C | Kaskade angeforderte Heiztemperatur |
| 1202 | `cascade_req_cool_temp` | FLOAT | °C | Kaskade angeforderte Kühltemperatur |
| 1204 | `cascade_req_dhw_temp` | FLOAT | °C | Kaskade angeforderte WW-Temperatur |
| 1206 | `cascade_avg_flow_heat` | FLOAT | °C | Kaskade gemittelte VL-Temp Heizen |
| 1208 | `cascade_avg_flow_cool` | FLOAT | °C | Kaskade gemittelte VL-Temp Kühlen |
| 1210 | `cascade_avg_flow_dhw` | FLOAT | °C | Kaskade gemittelte VL-Temp Warmwasser |

**Summe: 20 fehlende Register-Adressen**

---

## 2. Falscher Datentyp — Binary Sensors

Folgende Register sind in der Library als `UCHAR` definiert, sollten aber als `BOOL`  
oder zumindest mit einem `is_binary=True` Flag markiert werden, damit die HA-Integration  
korrekte `BinarySensor` Entities erzeugen kann:

| Adresse | Aktueller Name | Aktueller Typ | Soll | Beschreibung |
|---------|---------------|---------------|------|--------------|
| 1099 | `hp_sum_alarm` | UCHAR | BOOL | Summenstörung Wärmepumpe |
| 1100 | `compressor_status_1` | UCHAR/INT16 | BOOL | Verdichter 1 läuft |
| 1101 | `compressor_status_2` | UCHAR/INT16 | BOOL | Verdichter 2 läuft |
| 1102 | `compressor_status_3` | UCHAR/INT16 | BOOL | Verdichter 3 läuft |
| 1103 | `compressor_status_4` | UCHAR/INT16 | BOOL | Verdichter 4 läuft |
| 1091 | `heating_demand` | UCHAR | BOOL | Heizanforderung aktiv |
| 1092 | `cooling_demand` | UCHAR | BOOL | Kühlanforderung aktiv |
| 1093 | `dhw_demand` | UCHAR | BOOL | Warmwasseranforderung aktiv |

**Alternative:** Ein neues Feld `binary: bool = False` im `RegisterDef` dataclass,  
das von der HA-Integration ausgewertet werden kann, ohne den Datentyp zu ändern.

---

## 3. Fehlende Metadaten im RegisterDef

Für eine saubere HA-Integration wären folgende Felder im `RegisterDef` hilfreich:

| Feld | Typ | Default | Beschreibung |
|------|-----|---------|--------------|
| `binary` | `bool` | `False` | Wenn True → BinarySensor in HA |
| `enabled_by_default` | `bool` | `True` | Diagnostic entities standardmäßig deaktivieren |
| `state_class` | `str | None` | `None` | "measurement", "total", "total_increasing" |
| `icon` | `str | None` | `None` | Standard-Icon für HA |

---

## 4. Bekannte Bugs

| Problem | Details |
|---------|---------|
| `firmware_version` Adresse 4120 | Liefert Wert 4120 statt der tatsächlichen Firmware-Version. Adresse evtl. falsch oder Datenformat inkorrekt. |
| `hc_X_mode` enum_options enthält 255 | 255 = "Not configured / Unavailable" taucht als wählbare Option im Select auf. Sollte gefiltert werden (nur Anzeige, nicht wählbar). |
| `build_register_map(zone_modules=N)` | Generiert immer 6 Räume pro Zone, ignoriert Raumzahl. `get_zone_module_registers(idx, rooms)` funktioniert korrekt, aber `build_register_map` nicht. |
| `error_acknowledge` | Ist als `writable=True, UCHAR` definiert, wird aber beim Lesen immer fehlschlagen (write-only command). Braucht ein `write_only: bool` Flag. |

---

## 5. Zusammenfassung

- **20 fehlende Register-Adressen** (PV, Solar, ISC Mode, ISC Temps, Kaskade Temps)
- **8 Register brauchen Binary-Flag** (Störungen, Verdichter, Anforderungen)
- **4 Metadaten-Felder** fehlen im RegisterDef (binary, enabled_by_default, state_class, icon)
- **4 bekannte Bugs** (firmware_version, 255 in enum, zone rooms, write_only)
