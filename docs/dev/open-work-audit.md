# Open Work Audit

Stand: 21.07.2026

Diese Prüfung trennt lokal erledigbare Arbeit von Punkten, die ohne reale
Anlagendaten oder ohne finalen Home-Assistant-Vertrag nicht sicher abgeschlossen
werden können. Ziel ist, keine Schätzung als fertiges Feature auszugeben und
keine riskante Modbus-Änderung vorzeitig produktiv zu verdrahten.

## Lokal erledigt

- Konservatives Entity-Profil für generierte technische und seltene Register.
- Automatisch erzeugter Home-Assistant-Metadatenkatalog für explizite Overlays.
- Vollständige Modbus-Registerreferenz bleibt über
  `scripts/generate_modbus_register_reference.py` an den gepinnten
  `idm-heatpump-api`-Stand gekoppelt.
- Feld-Diagnoseleitfaden und Issue-Vorlage für reale Anlagenmessungen.
- Nicht verdrahteter Modbus-Transportvertrag mit Endpoint-Validierung,
  Konfliktkennung und privacy-sicheren Diagnose-Helfern.
- Issue-Vorlage für die spätere Home-Assistant-Modbus-Modernisierung.

## Extern blockiert

### Reale Anlagendaten

Diese Punkte dürfen erst als erledigt markiert werden, wenn echte Daten aus
mindestens einem passenden System vorliegen:

- COP-Verifikation für Warmwasser, Abtauen und unterschiedliche
  Navigator-Firmwares.
- Eindeutige Zuordnung des tatsächlich angeforderten
  Wärmepumpen-Vorlauf-Sollwerts.
- Binary-Register-Verifikation auf Navigator 10 und Navigator 2.0,
  einschließlich Active-Low- und Sonderwerten.
- Lasttests mit maximaler Zahl an Heizkreisen, Zonen und Räumen.

Benötigte Artefakte sind in der Field-Diagnostics-Vorlage und im
Field-Diagnostics-Guide beschrieben. Ohne diese Daten bleibt die sichere
Entscheidung: nicht veröffentlichen, nicht schätzen und keine Schreibpfade
ändern.

### Home Assistant Modbus-Vertrag

Diese Punkte bleiben blockiert, bis Home Assistant den finalen offiziellen
Shared-Connection-Vertrag veröffentlicht und Custom Integrations ihn stabil
nutzen dürfen:

- Adapter zwischen Home-Assistant-Connection-Objekt und `IdmModbusTransport`.
- Runtime-Option für einen optionalen Shared-Connection-Transport.
- Diagnoseexport der tatsächlich genutzten Transportquelle.
- Migrationspfad ohne neue Unique IDs und ohne neuen Schreibpfad.

Bis dahin bleibt die Integration beim bestehenden, getesteten
`idm-heatpump-api`-/Pymodbus-Pfad.

## Entscheidungsregel

Ein Punkt darf nur von „blockiert“ nach „erledigt“ wechseln, wenn mindestens
eines erfüllt ist:

1. Die benötigten realen Messdaten liegen als redigierter Diagnoseexport und
   Rohdatenserie vor.
2. Die finale Home-Assistant-Dokumentation ist verlinkt und der Adapter ist
   feature-gated implementiert.
3. Ein Test oder Generator belegt reproduzierbar, dass die Dokumentation mit dem
   Code übereinstimmt.
