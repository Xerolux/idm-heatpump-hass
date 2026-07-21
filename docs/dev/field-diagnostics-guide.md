# Field Diagnostics Guide

Stand: 21.07.2026

Dieses Dokument beschreibt, welche Realanlagen-Daten für die noch offenen
Validierungen benötigt werden. Alle Schritte sind **read-only**; direkte
Modbus-Schreibtests gehören nicht in Felddiagnose-Issues.

## Ziele

- Vorlauf-Abweichung nur dann umsetzen, wenn der tatsächlich angeforderte
  Wärmepumpen-Vorlauf-Sollwert eindeutig verifiziert ist.
- Binärregister nur dann final klassifizieren, wenn Sentinel-, Active-Low- und
  firmwareabhängige Werte von echten Navigator-2.0-/10-/Pro-Anlagen bekannt sind.
- COP-Dokumentation mit zusätzlichen Daten für Warmwasser, Abtauen und weitere
  Firmwarestände verbessern.
- Modbus-Transportfragen für den späteren Issue mit realen Symptomen und
  Diagnosefeldern untermauern.

## Benötigte Anhänge

- Home-Assistant-Diagnoseexport der Integration.
- Screenshot der Navigator-Werte aus demselben Zeitfenster.
- Optionaler read-only Rohwertmitschnitt.
- Relevanter Logauszug, wenn es um Transport-/Timeout-Verhalten geht.

## Datenschutz

Vor dem Hochladen bitte entfernen oder schwärzen:

- öffentliche und private IP-Adressen,
- Hostnamen,
- Seriennummern,
- Standortdaten,
- persönliche Notizen oder Namen.

## Sicherheitsregeln

- Keine Live-Schreibtests mit `idm_heatpump.write_register`.
- Keine Tests an EEPROM-sensitiven Registern.
- Keine parallelen Energie-Manager auf demselben GLT/PV-Register testen.
- Für Transportthemen zuerst Logs und Diagnoseexports sammeln, nicht die
  Produktionsverbindung umbauen.

## Passende Issue-Vorlage

Bitte die Vorlage **Field diagnostics / real-system data** verwenden. Sie fragt
gezielt nach Zeitfenster, Betriebszustand, HA-Werten, Navigator-Werten und
Sicherheitsbestätigung.
