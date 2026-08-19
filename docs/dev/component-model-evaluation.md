# Component-Modell von `modbus-connection`: Bewertung

Stand: 19.08.2026 · gemessen gegen `modbus-connection` 4.8.1 und
`idm-heatpump-api` 1.0.1 · reproduzierbar über
`python scripts/evaluate_component_model.py`

## Frage

solaredge-modbus-multi hat mit v4.0.0-pre.11 alle Lese- und Schreibzugriffe auf
eine `modbus-connection`-`Component` umgestellt. Der entsprechende Schritt für
dieses Projekt läge in `idm-heatpump-api`: dort liegen Registerkarte, Batching
und Decoding. Die Integration selbst hätte danach deutlich weniger Code — der
Transportvertrag und die Fehlerübersetzung in `modbus_transport.py` wären
größtenteils überflüssig, weil die Bibliothek Planung und Decoding übernimmt.

## Ergebnis

**Nicht umsetzen.** Nicht weil die Registerkarte nicht passt — sie passt
vollständig —, sondern weil die Leseplanung der Bibliothek mit den
Protokollinvarianten der offiziellen IDM-Registerkarte kollidiert.

## Was gemessen wurde

Gegen die maximal ausgebaute Navigator-10-Karte (7 Heizkreise, 10 Zonenmodule,
Solar/ISC/PV/Kaskade aktiv), 586 lesbare Datenpunkte:

| Prüfung | Ergebnis |
| --- | --- |
| Register auf Bibliotheksfelder abbildbar | 586 von 586, kein Sonderfall offen |
| Decodierte Werte gegen `idm-heatpump-api` | 0 Abweichungen |
| Anfragen je Poll, heutiges API-Batching | 57 |
| Anfragen je Poll, Bibliotheksplanung `max_gap=1` | 42 |
| Anfragen je Poll, Bibliotheksplanung `max_gap=16` (Default) | 24, dafür 98 Wörter aus Adressen, die kein Datenpunkt beansprucht |

Die dynamische Registerkarte ist kein Hindernis: `ManualComponent` nimmt Felder
zur Laufzeit entgegen, Heizkreise und Zonenräume lassen sich also genauso
generieren wie heute. IDM-`FLOAT` (IEEE-754, Low Word zuerst) bildet
`float32(..., word_order="little")` exakt ab; der Multiplikator wird zum
`scale` des Feldes.

## Der Blocker

`docs/Register-Map-Invariants.md` in `idm-heatpump-api` hält drei Regeln fest,
die aus der offiziellen IDM-Dokumentation und aus Hardwarecaptures stammen:

- Gebatcht wird ausschließlich strikt benachbart: `next.address ==
  previous.address + previous.size`. Lücken werden nie übersprungen.
- Die offizielle Karte enthält dokumentierte logische Überlappungen —
  Feuchte `1392 FLOAT` und Heizkreis-A-Modus `1393 UCHAR`, Heizkurve G
  `1441 FLOAT` und Heizgrenze A `1442 UCHAR`, Kühl-Eco-Sollwert G `1483 FLOAT`
  und Kühlgrenze A `1484 UCHAR`.
- Jeder überlappende Datenpunkt wird mit seiner dokumentierten Startadresse und
  Größe **einzeln** angefragt. Diese Werte sind anfrageabhängig: dieselbe
  Adresse liefert je nach exakter Anfrage einen Float-Anteil oder einen
  eigenständigen UCHAR-Wert.

Die Planung der Bibliothek arbeitet dagegen rein über Adressspannen
(`_plan_blocks`: zusammenführen, solange `address - block_end <= max_gap`) und
decodiert anschließend alle Felder aus dem gelesenen Block. Gemessen:

```
humidity_sensor + hc_a_mode:                 [(1392, 2)] -> EINE zusammengefasste Anfrage
hc_g_heating_curve + hc_a_heating_limit:     [(1441, 2)] -> EINE zusammengefasste Anfrage
hc_g_room_setpoint_cool_eco + hc_a_cooling_limit: [(1483, 2)] -> EINE zusammengefasste Anfrage
```

Damit bekämen genau diese drei Datenpunkte ihren Wert aus dem zweiten Wort des
benachbarten Floats statt aus der eigenen dokumentierten Anfrage. Im Mock fällt
das nicht auf — der Mock ist nicht anfrageabhängig —, am Gerät ist es ein
falscher Wert.

Ein Ausweichen über `max_gap=0` löst das nicht: dann führt die Bibliothek gar
nichts mehr zusammen, auch nicht direkt benachbarte Felder, und der Poll
zerfällt in 583 Einzelanfragen statt 57. Und `max_gap >= 2` verletzt zusätzlich
die erste Regel, weil dann Adressen mitgelesen werden, die die Dokumentation
nicht beschreibt — auf einem Regler, der unbekannte Adressen mit Exception-Code
2 für den ganzen Block quittiert, kostet das den kompletten Block.

## Was das nicht bedeutet

- Der Rest von `modbus-connection` bleibt genau das, was die Integration
  benutzt: Verbindung, Serialisierung, Reconnect, Pacing, typisierte Fehler.
  Die Bewertung betrifft nur das Modellierungs-/Planungsmodul
  (`modbus_connection.model`).
- Die 42 statt 57 Anfragen bei `max_gap=1` sind kein Argument für die
  Umstellung: die Ersparnis entsteht dort, wo die Bibliothek bis 125 Wörter je
  Block zusammenfasst, während die API bei 40 Wörtern (`_MAX_GROUP_SIZE`)
  schneidet. Dieselbe Ersparnis wäre in der API zu haben, ohne die
  Überlappungsregel aufzugeben — allerdings nur mit Hardwarebeleg, dass der
  Regler Blöcke über 40 Wörter zuverlässig beantwortet.

## Wann neu bewerten

Sobald `modbus-connection` eine Planung anbietet, die einen Datenpunkt als
exakte Anfrage festnageln kann (also „dieses Feld nie mit einem anderen Block
zusammenführen" bzw. explizit anfrageabhängige Datenpunkte kennt). Dann fällt
der Blocker weg, und die Umstellung wird zur reinen Aufwandsfrage in
`idm-heatpump-api` 2.0. `scripts/evaluate_component_model.py` misst die Lage neu.
