# Modbus Transport Preparation

Stand: 04.08.2026

Dieses Dokument beschreibt den inzwischen implementierten lokalen
Modbus-Transport und die zwei bewusst noch offenen Schritte: read-only
Hardware-Verifikation und eine mögliche spätere Home-Assistant-Verbindung mit
Entry-übergreifendem Sharing.

## Aktueller Status

- Der direkte Modbus-TCP-Laufzeitpfad verwendet
  `modbus-connection==4.0.0a3` und den separat exakt gepinnten Backend-
  Stand `tmodbus==0.5.0`.
- `IdmModbusConnectionClient` ist der produktive Client der Integration. Er
  verwendet das Gerätemodell von `idm-heatpump-api[web]==0.9.1`, ersetzt aber
  dessen rohe I/O-Hooks durch `ModbusConnectionTransport`.
- `pymodbus>=3.12.1,<4.0` bleibt vorübergehend installiert, weil
  `idm-heatpump-api` 0.9.1 Pymodbus noch importiert und dessen etablierten
  Fehlervertrag verwendet. Pymodbus besitzt nicht mehr den direkten Socket.
- Jede Config-Entry besitzt eine eigene tmodbus-Verbindung. Home Assistants
  zentrale Entry-übergreifende Modbus-Verbindung steht Custom Integrations
  derzeit nicht als stabiler Vertrag zur Verfügung; deshalb meldet der Adapter
  ausdrücklich `supports_shared_connection=False`.
- Es gibt keine Transportauswahl im Optionsflow und keinen parallelen
  Pymodbus-Fallback-Pfad.
- Die erste ausliefernde Integrationsversion ist `0.11.0-beta.1`. `4.0.0a3`
  ist die Version der Transportbibliothek und kein IDM-Release.

## Implementierte Schichtentrennung

1. **Home-Assistant-Integration**
   - Config Flow, Coordinator, Entities, Services, Diagnostics und Repairs.
   - `library_adapter.create_library_client()` erzeugt immer den neuen
     `IdmModbusConnectionClient`.
2. **idm-heatpump-api 0.9.1**
   - Registermodell und Registerart,
   - Batchplanung,
   - Encoding/Decoding,
   - Modell-/Firmware-Erkennung,
   - Schreibsicherheitsregeln,
   - Retry-/Backoff-Vertrag.
3. **Lokaler Modbus-Transport**
   - `ModbusConnectionTransport` reserviert und schließt den Socket,
   - tmodbus führt rohe FC03-/FC04-/FC16-Operationen aus,
   - `modbus_client.py` übersetzt Transportfehler in den bestehenden
     API-/Coordinator-Fehlervertrag,
   - statische Capabilities dokumentieren Quelle, Socket-Besitz und fehlendes
     zentrales Sharing.

Der Laufzeitpfad ist damit:

```text
IdmCoordinator
  -> IdmModbusConnectionClient
     -> idm-heatpump-api 0.9.1 (Gerätelogik)
     -> ModbusConnectionTransport
        -> modbus-connection 4.0.0a3
           -> tmodbus 0.5.0
              -> IDM Navigator (TCP 502)
```

## Transportvertrag

Der Vertrag verwendet rohe Registeradressen und rohe 16-Bit-Wörter. Dadurch
bleibt Gerätewissen in der API und nicht in der Transportklasse.

```python
transport.endpoint
transport.capabilities
await transport.async_connect()
await transport.async_close()
input_words = await transport.async_read_input_registers(address, count)
holding_words = await transport.async_read_holding_registers(address, count)
await transport.async_write_registers(address, values)
```

Input Register (Function Code 04) und Holding Register (Function Code 03)
bleiben getrennte Leseoperationen. Schreiben verwendet Function Code 16. Der
Adapter übernimmt jeweils die von der API vorgegebene Registerart und prüft,
dass die Antwort die erwartete Wortanzahl enthält.

`ModbusTcpEndpoint` validiert Host, TCP-Port, Slave-ID 1–247, positives Timeout
und nicht negative Retries. `connection_key` liefert eine normalisierte
`(host, port, slave_id)`-Kennung für Konfliktprüfungen.

## Verbindung und Fehlerverhalten

- Setup und Reconfigure verbinden bewusst sofort, damit eine ungültige
  Zieldefinition vor dem Anlegen oder Aktualisieren der Entry auffällt.
- Normale Operationen werden serialisiert. Nach einem Verbindungsabbruch
  verbindet `modbus-connection` bei der nächsten Operation erneut.
- Die API-Retry-Konfiguration und ihr exponentielles Backoff bleiben erhalten.
- Illegal Address (Modbus Exception Code 2), Timeout, Verbindungs- und
  Protokollfehler werden in die bestehenden API-Ausnahmen übersetzt, damit
  Resilient Polling, Repairs und nutzerfreundliche Config-Flow-Fehler weiter
  funktionieren.
- Eine Entry schließt nur ihren eigenen Socket. Der Adapter behauptet weder
  Pooling noch Entry-übergreifende Wiederverwendung.

## Diagnose und Datenschutz

`ModbusTcpEndpoint.as_redacted_diagnostics()` ersetzt Host/IP durch einen festen
Redaction-Wert. Port, Slave-ID, Timeout und Retries bleiben für die Fehlersuche
sichtbar.

Der Transportblock meldet:

```yaml
source: modbus_connection.tmodbus
owns_socket: true
supports_shared_connection: false
connected: true_or_false
```

Diagnoseexport, Startlog und der bestehende API-Versionssensor enthalten
zusätzlich die installierten Versionen von Integration, `idm-heatpump-api`,
`modbus-connection`, `tmodbus` und der vorübergehenden
Pymodbus-Kompatibilitätsabhängigkeit.

## Verifikation

Automatisierte Tests decken Endpoint-Validierung, FC03/FC04-Trennung,
FC16-Schreiben, Retry-/Fehlerübersetzung, Reconnect, Close-Verhalten,
Factory-Verdrahtung, Versionsdiagnose und redigierte Capabilities ab.

Noch offen ist die **read-only Hardware-Verifikation des neuen tmodbus-Pfads**
an realen Navigator-Systemen. Frühere Hardwaremessungen belegen Register und
Gerätelogik, wurden aber vor dieser Transportumstellung durchgeführt und
bestätigen daher nicht automatisch den neuen Socket-Pfad. Schreibtests an
realen Anlagen bleiben ohne ausdrückliche Freigabe ausgeschlossen.

## Verbleibende Arbeit

1. Setup, FC03, FC04, Verbindungsabbruch und Reconnect read-only gegen reale
   Navigator-Hardware prüfen und Firmware/Modell dokumentieren.
2. `idm-heatpump-api` auf einen öffentlichen transportneutralen I/O-Vertrag
   weiterentwickeln. Erst dann kann die temporäre Pymodbus-Abhängigkeit nach
   Kompatibilitätsprüfung entfallen.
3. Home Assistants finalen zentralen Shared-Connection-Vertrag beobachten.
   Falls er für Custom Integrations stabil verfügbar wird, einen separaten
   Provider implementieren; erst dieser darf
   `supports_shared_connection=True` und `owns_socket=False` melden.
4. Eine eventuelle Migration ohne neue Unique IDs, ohne neuen Schreibpfad und
   ohne Options-Zwang planen. Bis dahin bleibt der private tmodbus-Socket der
   einzige produktive Modbus-Pfad.

## Issue template

`.github/ISSUE_TEMPLATE/modbus_transport_modernization.md` verfolgt die
Hardware-Verifikation sowie den späteren zentralen Sharing-Provider. Die Vorlage
setzt den bereits implementierten tmodbus-Adapter nicht mehr als Zukunftsarbeit
voraus.
