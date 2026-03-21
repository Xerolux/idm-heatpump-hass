# Troubleshooting

## Verbindungsprobleme

### "Verbindung fehlgeschlagen"

- Prufe die **IP-Adresse** des IDM Navigators
- Stelle sicher, dass **Modbus TCP** auf dem Navigator aktiviert ist
- Prufe ob der **Port 502** erreichbar ist (Firewall)
- Pinge die IP-Adresse: `ping <ip-des-navigators>`

### Verbindungsabbrüche

- Prüfe die Netzwerkverbindung (LAN-Kabel empfohlen)
- Erhöhe das Scan-Intervall (z.B. auf 30 Sekunden)
- Aktiviere Debug-Logging (siehe [Konfiguration](Configuration))
- Die Integration optimiert Modbus-Verbindungen automatisch, um ständige Neuverbindungen zu vermeiden (`self._client.connected` Checks). Wenn trotzdem Abbrüche passieren, prüfe die Stabilität des lokalen Netzwerks oder des WLANs.

### "Keine Daten empfangen"

- Prufe die **Slave ID** (Standard: 1)
- Prufe ob andere Modbus-Clients gleichzeitig auf demselben Port zugreifen
- Restart des IDM Navigators kann helfen

## Entity-Probleme

### Entities fehlen

- Stelle sicher, dass die entsprechenden **Heizkreise** und **Zonen** in der Konfiguration aktiviert sind
- Rekonfiguriere die Integration
- Starte Home Assistant neu

### Falsche oder absurde Werte (z.B. -3276.8°C)

- Prüfe, ob die Register-Adressen für dein Navigator-Modell korrekt sind.
- Extreme oder falsche Zahlen deuten meist auf falsch deklarierte Datentypen (Float, Word, Vorzeichen) hin. Bitte melde uns solche Werte über GitHub Issues, damit wir das Register in `registers.py` auf `INT8`, `INT16` oder `FLOAT` anpassen können.
- Aktiviere Debug-Logging und prüfe die rohen Register-Werte in den Logs.
- Melde falsche Register-Zuordnungen als [Bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md).

### Werte aktualisieren sich nicht

- Prufe das **Scan-Intervall** in den Optionen
- Prufe die Home Assistant Logs auf Fehlermeldungen
- Rekonfiguriere die Integration

## EEPROM-Warnungen

Wenn du beim Schreiben von Werten eine Warnung bezuglich EEPROM erhaltst:

- Diese Register haben eine beschrankte Anzahl an Schreibzyklen
- Anderungen an diesen Werten sollten **sparsam** vorgenommen werden
- Die Integration warnt automatisch vor EEPROM-Sensitivitat

## Debug-Logging

Aktiviere erweitertes Logging:

```yaml
logger:
  default: info
  logs:
    custom_components.idm_heatpump: debug
    pymodbus: debug
```

Suche in den Logs nach:
- `idm_heatpump` - Integration-spezifische Meldungen
- `Modbus read error` - Modbus-Lesefehler
- `Modbus write error` - Modbus-Schreibfehler
- `Decode failed` - Register-Dekodierungsfehler

## Diagnosedaten exportieren

1. Gehe zu **Einstellungen → Geräte & Dienste**
2. Klicke auf **IDM Heatpump**
3. Klicke auf **Diagnosedaten herunterladen**
4. Hänge die Datei an deinen [Bug-Report](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md) an

## 👩‍💻 Für Entwickler (Mock Tests)

Bitte führe Schreiboperationen auf dem Modbus (`write_register`) **niemals live gegen eine echte Wärmepumpe** aus, wenn du Code-Änderungen an der Basislogik testest. Nutze stattdessen unsere Mock-Tests in `custom_components/idm_heatpump/tests/test_modbus_client.py` via `pytest`, um das Decodieren (`decode_value`) und Encodieren (`encode_value`) ohne Risiko zu testen.

## Haufige Fehler und Losungen

| Problem | Losung |
|---------|--------|
| Integration startet nicht | HA neu starten, Logs prufen |
| Keine Verbindung | IP, Port, Firewall prufen |
| Falsche Temperaturen | Register-Zuordnung prufen, Bug melden |
| Schreiben fehlgeschlagen | Register beschreibbar? EEPROM-Warnung beachten |
| Alle Entities "unavailable" | Navigator erreichbar? Modbus TCP aktiv? |
