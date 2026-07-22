# Modbus Transport Preparation

Stand: 21.07.2026

Dieses Dokument ist die Arbeitsgrundlage für den bestehenden Issue zur späteren
Home-Assistant-Modbus-Modernisierung. Es beschreibt, was vorbereitet ist, was in
den Issue gehört und was ausdrücklich noch nicht in die laufende Integration
eingebunden wird.

## Status

- Die produktive Integration verwendet weiterhin den getesteten
  `idm-heatpump-api`-Client und die bestehende Pymodbus-basierte Verbindung.
- Es wird keine Abhängigkeit auf eine neue Home-Assistant-`modbus_connection`-
  Integration eingeführt.
- Es gibt noch keine Runtime-Umschaltung und keine Optionsflow-Änderung.
- Der vorbereitende Code liegt nur als schmaler Transportvertrag unter
  `custom_components/idm_heatpump/modbus_transport.py` vor.

## Zielbild

Die spätere Architektur soll drei Schichten trennen:

1. **Home Assistant Integration**
   - Config Flow,
   - Entity-Erstellung,
   - Services,
   - Diagnostics,
   - Repairs,
   - Nutzeroptionen.
2. **idm-heatpump-api**
   - Registermodell,
   - Batchplanung,
   - Encoding/Decoding,
   - Modell-/Firmware-Erkennung,
   - Schreibsicherheitsregeln.
3. **Modbus Transport**
   - Verbindung reservieren/öffnen,
   - rohe Registerwörter lesen,
   - rohe Registerwörter schreiben,
   - Socket-Besitz und Shared-Connection-Fähigkeit melden.

## Minimaler Transportvertrag

Der vorbereitete Vertrag verwendet bewusst rohe Registeradressen und rohe
16-Bit-Wörter. Dadurch bleibt Gerätewissen in der API und nicht in der
Transportklasse.

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
bleiben dabei ausdrücklich getrennte Leseoperationen. Der Adapter darf die von
der API vorgegebene Registerart nicht vereinheitlichen oder ignorieren.

`ModbusTcpEndpoint` validiert die statische Zieldefinition bereits beim
Erzeugen: Host darf nicht leer sein, Port liegt im TCP-Bereich, Slave-ID liegt
zwischen 1 und 247, Timeout ist positiv und Retries sind nicht negativ. Zusätzlich
stellt `connection_key` eine normalisierte `(host, port, slave_id)`-Kennung für
spätere Konfliktprüfungen mehrerer Config-Entries bereit.

Für spätere Diagnoseexporte bleiben die Transportdaten privacy-sicher:
`ModbusTcpEndpoint.as_redacted_diagnostics()` gibt Port, Slave-ID, Timeout und
Retries aus, ersetzt Host/IP aber durch einen festen Redaction-Wert.
`ModbusTransportCapabilities.as_diagnostics()` liefert nur statische
Capability-Flags wie Transportquelle, Socket-Besitz und Shared-Connection-
Unterstützung.

## Issue-Inhalt für die spätere Umsetzung

Der Issue sollte mindestens diese Punkte enthalten:

- Link auf die finale Home-Assistant-Dokumentation, sobald verfügbar.
- Entscheidung, ob Custom Integrations die neue Verbindung stabil nutzen dürfen.
- Mapping zwischen HA-Connection-Objekt und `IdmModbusTransport`.
- Verhalten bei mehreren IDM-Config-Entries mit gleichem Host/Port/Slave.
- Timeout-/Retry-Verantwortung: HA-Verbindung, API oder Integration.
- Diagnosefelder für Transportquelle, Socket-Besitz und Shared-Connection-Status.
- Migration bestehender Installationen ohne neue Unique IDs.
- Fallback-Strategie, falls Shared Connection nicht verfügbar ist.

## Nicht jetzt umsetzen

- Keine neue Manifest-Requirement.
- Kein Wechsel weg vom aktuellen `IdmModbusClient`.
- Keine Optionsflow-Auswahl für experimentelle Transporte.
- Kein zusätzlicher Schreibpfad.
- Kein direkter Import einer noch nicht finalen HA-Modbus-API.

## Akzeptanzkriterien für die spätere PR

- Die Integration funktioniert unverändert mit dem aktuellen Pymodbus-Pfad.
- Ein Shared-Connection-Transport ist optional und feature-gated.
- Alle Plattformen schreiben weiterhin ausschließlich über den Coordinator.
- Diagnoseexport zeigt Transportquelle und Sharing-Fähigkeit.
- Tests decken beide Transportvarianten über Fakes ab.
- Fehlerklassifikation bleibt nutzerfreundlich und repair-fähig.


## Issue template

Use `.github/ISSUE_TEMPLATE/modbus_transport_modernization.md` to track the
future implementation. The template keeps upstream status, non-goals, mapping
to `IdmModbusTransport`, diagnostics requirements, migration requirements and
acceptance criteria in one place.
