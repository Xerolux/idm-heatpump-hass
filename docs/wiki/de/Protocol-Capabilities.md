# Protokoll-Fähigkeiten

Diese Seite beantwortet eine Frage auf einen Blick: **Was kann jeder
Verbindungspfad lesen und schreiben, auf welcher Navigator-Familie?** Die
Integration unterstützt drei Pfade — Modbus TCP, die lokale
Navigator-2.0-Weboberfläche (HTTP/CSRF) und den Navigator-10/Pro-WebSocket —
und sie ergänzen einander. Tiefenwissen steht auf
[Navigator-Protokollanalyse](Navigator-Protocol-Analysis), Register auf
[Modbus-Register](Modbus-Register), Hardware auf
[Kompatibilitätsmatrix](Compatibility-Matrix).

## Die drei Pfade

| Pfad | Port | Anmeldung | Familien | Rolle |
|---|---|---|---|---|
| **Modbus TCP** | 502 (Unit 1) | keine | 1.0/1.7 · 2.0 · 10/Pro | Das Rückgrat: volle Register-Telemetrie, *alle* validierten Schreibvorgänge |
| **Web, alte Generation** (PHP, ohne CSRF) | 80 | Netzwerk-Code, einfache Login-Sitzung | 2.0 (ältere Firmware) | Nur-Lese-Ergänzung |
| **Web, neuere Generation** (PHP + CSRF) | 80 | Netzwerk-Code + CSRF-Token | 2.0 (neuere Firmware) | Nur-Lese-Ergänzung |
| **WebSocket** | 61220 | lokale PIN (`SYSLPIN`) | 10 / Pro | Vollwertiger zweiter Pfad: Werte, die Modbus fehlen + validierte Schreibvorgänge |

Der Navigator-2.0-Web-Client der Integration deckt beide Web-Generationen
transparent ab: Er meldet sich mit dem CSRF-Token an, wenn das
Anmeldeformular eines liefert, und fällt sonst auf die einfache
Cookie-Sitzung älterer Firmware zurück; danach werden die PHP-Datenseiten
(`/data/settings.php`, `/data/heatpump.php`, `/data/info.php`, …) geprüft.
Die Endpunktmenge und die Statistikseiten wurden gegen die
Community-Integration
the community integrations
abgegleichen.

Der Verbindungsmodus entscheidet, welche Pfade ein Eintrag nutzt:
`Automatisch` (empfohlen — Modbus + Web-Ergänzung), `Modbus + Web-Ergänzung`
(beide fest, kein Web-only-Fallback), `Nur Web` (gar kein Modbus), `Nur
Modbus` (die Weboberfläche wird nie kontaktiert). Siehe
[Konfiguration](Configuration).

## Fähigkeiten-Matrix

Legende: **R** lesbar · **W** schreibbar · **R/W** beides · **—** auf diesem
Pfad nicht vorhanden. Firmware-abhängige Zellen sagen das.

| Fähigkeit | 1.0/1.7 Modbus | 2.0 Modbus | 2.0 Web (alt / CSRF) | 10/Pro Modbus | 10/Pro WebSocket |
|---|---|---|---|---|---|
| Modell- und Firmware-Erkennung | R | R | R (Ergänzungs-Hinweis) | R | R |
| Kern-Telemetrie (Temperaturen, Status, Pumpen, Ventile) | R (1.x-Map) | R | R | R | R (64 Werte, Setting-Seiten) |
| Elektrische / thermische Leistung (COP-Eingänge) | — | teils *(nicht bestätigt)* | — | **R** | **—** *(die Firmware liefert beides nicht)* |
| Energiezähler (Lebens-kWh) | — | R *(wo vorhanden)* | — | R | R (Wärmemengen, gesamt + heute) |
| Statistik-Seiten (Laufzeit, Wärme, elektrisch) | — | — | R *(statistics.php; Gesamtwerte als Sensoren)* | — | R (Statistik-Blöcke) |
| Regler-Uhr stellen (`set_controller_clock`-Dienst) | — | — | W | — | W |
| Anforderungsgrund inkl. PV (Display-Wortlaut) | — | — | — | — | **R** (`home/detail`) |
| Meldungstexte (Infosystem) | nur Fehlercodes | nur Fehlercodes | — | nur Fehlercodes | **R** (`notification`, mit Texten) |
| Heißgas, Durchfluss, Platine, Drücke | — | teils | teils | teils | **R** |
| Warmwasser-Zirkulation / StatusInfo | — | — | — | — | **R** (`system.freshwater`) |
| Regler-Uhr / jsonVersion / Benutzerebene | — | — | — | — | **R** (`status/overview`) |
| Betriebsart (System) | R/W (Holding-Block) | R/W | — | R/W | **R/W** (`home/save`) |
| Warmwasser-Sollwert | R/W (2152) | R/W | — | R/W | **R/W** (FW030, gegen Gerätegrenzen validiert) |
| Heizkreis-Betriebsart | R/W (Holding-Block) | R/W | — | R/W | **R/W** (HK\<x\>01) |
| Raumsollwert (normal) | R/W (Holding-Block) | R/W | — | R/W | **R/W** (HK\<x\>04, gegen Gerätegrenzen validiert) |
| Heizkurve / Grenzen / Verschiebung | R/W (Holding-Block) | R/W | — | R/W | W möglich *(Parameter-IDs bekannt, noch nicht gemappt)* |
| Störungen quittieren | W (Coil c3000, FC05) | W (Register 1999) | — | W (Register 1999) | **W** (`notification/save`) |
| Einmaliger Warmwasser-Boost | W (Anforderungs-Coil c3003) | W (Boost-Logik) | — | W (Boost-Logik) | **—** *(nur Wochen-Zeitplan, kein Einmal-Befehl)* |
| GLT-Eingänge (ext. Raumtemperatur, Feuchte, PV-Überschuss) | W (PV-Block 74–88) | W | — | W | **—** *(GLT-Container antwortet auf Ebene 0 leer)* |
| Zonenmodul-Räume | — (eigene Familie) | R/W *(Register)* | — | R/W | R/W *(room-Controller; noch nicht gemappt)* |
| KNX-Bridge | Serve *(nur gemeinsame Namen)* | Serve + Kommandos | — | Serve + Kommandos | Serve + Kommandos *(Alltagssteuerung per WS)* |
| COP / Energie-Statistiken | — | teils | — | **ja** | **nein** *(braucht die Leistungs-Eingänge)* |

## Was das in der Praxis bedeutet

- **Vollbetrieb (empfohlen `Automatisch`):** Modbus liefert alles — auch die
  Leistungswerte hinter COP und Energie-Statistiken; die Web-Ergänzung
  bringt die Werte, die Modbus nie hatte (Anforderungsgrund, Meldungstexte,
  Heißgas, Zirkulation, geräteseitige Statistiken).
- **`Nur Web` (Navigator 10/Pro):** ein echter Betriebsmodus — 10-Sekunden-
  Abfrage, Climate-/Water-Heater-Karten, KNX-Serving und die validierten
  Schreibvorgänge der Matrix oben. Nicht ersetzbar: COP/Energie-Statistiken
  (Leistungswerte), GLT-Weiterleitung und der einmalige Warmwasser-Boost —
  die brauchen Modbus.
- **Navigator 2.0:** Modbus trägt die Last; die CSRF-Weboberfläche ist eine
  Nur-Lese-Ergänzung (ihre Schreibsemantik wurde nie erfasst und validiert —
  bewusst nicht angeboten).
- **Navigator 1.0/1.7:** nur Modbus, inklusive des offiziellen
  RW-Holding-Blocks und der Coil-Befehle. Ein Web-Modul existiert nicht; die
  Web-Ergänzung sollte deaktiviert bleiben. Holding-Block-Schreibvorgänge
  sind EEPROM-begrenzt — die Integration schützt sie mit Cooldowns und
  EEPROM-Intervallen.

## Schreibsicherheit auf jedem Pfad

| Schutz | Modbus | WebSocket |
|---|---|---|
| Bereich-/Enum-Validierung vor dem Senden | API-Register-Metadaten | vom Gerät selbst deklarierte min/max (lesen vor dem Schreiben) |
| EEPROM-Schutz | EEPROM-Liste + 60 s Intervall je Register | *(EEPROM-Last für Web-Schreibvorgänge nicht dokumentiert; Taktung greift)* |
| Bestätigung | Rücklesen über den Register-Poll | `<Controller>Save`-Erfolgsnotiz zwingend; Ablehnung wirft Fehler |
| Transient-Zero-Schutz | Lebens-Zähler | Lebens-Zähler (derselbe Snapshot) |

Schreibvorgänge werden auf keinem Pfad als freie Payload gesendet. Alles in
der Matrix mit **W** durchlief diese Validierung auf echter Hardware, bevor
es ausgeliefert wurde; Zellen mit *(noch nicht gemappt)* existieren im
Protokoll, haben die Validierungslatte aber noch nicht genommen.
