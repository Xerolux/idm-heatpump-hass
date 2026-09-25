# IDM Heatpump - Home Assistant Integration

<p align="center">
  <img src="../images/idm-home-assistant-hero.png" alt="IDM-Heatpump-Integration: lokales Modbus TCP, lokale Navigator-Daten und optionales KNX" width="900"><br>
  <small><i>KI-generiert</i></small>
</p>

> **Die vollständige Dokumentation** der IDM-Heatpump-Integration.
> Von der Installation bis zur Fehlerbehebung — mit allen Funktionen, Entitäten und Aktionen.

> **Wichtige Voraussetzung:** Modbus TCP muss auf dem IDM
> Navigator/Regler unter **Gebäudeleittechnik → Modbus TCP → Ein**
> aktiviert sein. Siehe
> [Installation & Einrichtung](Installation-and-Setup#modbus-tcp-an-der-idm-warmepumpe-aktivieren).

---

## Was ist die IDM-Heatpump-Integration?

Die **IDM-Heatpump-Home-Assistant-Integration** verbindet [Home Assistant](https://www.home-assistant.io/) mit den IDM-Navigator-Reglern von IDM EnergieSysteme GmbH. Sie ermöglicht lokale Überwachung und unterstützte Steuerungen über **Modbus TCP — keine Cloud, kein Abo**. Der Navigator 10 ist direkt hardwareseitig bestätigt; Navigator 2.0 und Navigator Pro befinden sich noch in der breiteren Kompatibilitätsvalidierung.

| Funktion | Details |
|---------|---------|
| **Protokoll** | Modbus TCP (Port 502, Slave-ID 1) |
| **Optionales Supplement** | Lokale Navigator-Web-API, nur lesend, PIN optional |
| **Dokumentationsversion** | [0.18.0](https://github.com/Xerolux/idm-heatpump-hass/releases/tag/v0.18.0); [aktuellstes stabiles Release](https://github.com/Xerolux/idm-heatpump-hass/releases/latest) |
| **Unterstützte/getestete HA-Baseline** | 2026.8.1 |
| **Python** | 3.14+ (von Home Assistant verwaltet) |
| **Verbindungsbibliothek** | modbus-connection==4.12.2 |
| **Socket-Backend** | tmodbus[async-serial]==0.6.2 |
| **Geräte-/Web-Bibliothek** | idm-heatpump-api[web]==2.4.2 |
| **Lizenz** | MIT |
| **Sprachen** | DE, EN |
| **Entitäten** | Modell- und konfigurationsabhängige Sensoren, Binärsensoren, Zahl-Entitäten, Auswahl-Entitäten, Schalter-Entitäten, Klima-Entitäten, Warmwasserbereiter und Buttons |

---

## Zentrale Funktionen

### Neu in 0.18.0

0.18.0 liefert zwei Funktionspakete im Fokus — das optionale **Smart Energy & Comfort**-Paket und den experimentellen **KI-Anlagenberater** — plus eine geführte Einrichtung, die das lange Optionsformular ersetzt. Alles bleibt standardmäßig lokal, und jede automatische Steuerung bleibt aus, bis sie ausdrücklich aktiviert wird.

<p align="center">
  <img src="../images/smart-energy-comfort-overview.svg" alt="Smart-Energy-&-Comfort-Übersicht: Energie und Kosten, Health Monitor und Empfehlungen, Komfortzeitpläne und PV-Boost, externe Leistungsweiterleitung" width="860">
</p>

| Funktion | Was du damit machen kannst | Geräteschreibvorgänge |
|---------|-----------------|---------------|
| Standard-/Erweitert-/Experten-Einrichtung | Wähle den Detaillierungsgrad der Konfiguration; alle drei Modi bieten dieselben Funktionen | Das Auswählen eines Modus schreibt keine Register |
| Smart- oder Vanilla-Profil | Behalte die Kern-Regler-Entitäten oder ergänze mit Smart die Energie- und Betriebsanalyse | Die Analyse ist nur lesend; Boost-Steuerungen schreiben bei Nutzung |
| Persistente Energiestatistik | Verfolge elektrische und thermische Energie, COP, geschätzte Kosten, CO₂ und PV-Nutzung | Keine |
| PV-Überschuss-Warmwasser-Manager | Starte einen begrenzten Warmwasser-Boost anhand ausgewählter HA-Leistungssensoren und optionaler Batteriesensoren | Optional; standardmäßig aus, Bestätigung der exklusiven Steuerung erforderlich |
| Komfortzeitpläne | Wende tägliche Raum-Sollwerte auf ausgewählte Kreise an, mit bis zu 16 Fenstern und bedingtem Restore | Optional; standardmäßig aus, Bestätigung der exklusiven Steuerung erforderlich |
| Heiz- und Wetterempfehlungen | Lies Vorlauftemperatur-Hinweise und eine Sechs-Stunden-Wetterempfehlung | Keine |
| Health Monitor und Installateurbericht | Prüfe acht Diagnose-Checks, die Betriebshistorie und die geschwärzte Diagnose | Keine |
| Externe Leistungsweiterleitung | Leite PV-, Haushalts-, Batterie- und Überschuss-Sensoren an die bestehenden GLT-Register weiter | Optional; aus, bis konfiguriert |
| Funktions-Gerätegruppen | Finde Analytics, Health Monitor, Comfort und Diagnose getrennt voneinander | Keine; Entitäts-IDs bleiben unverändert |
| **KI-Anlagenberater** *(experimentell)* | Tägliche, wöchentliche, Gesundheits- und Effizienzberichte aus gemessenen Fakten — standardmäßig ganz ohne Modellaufruf; eigenes KI-Gerät, vier Berichts-Buttons, Dashboard-Export, neustartsicherer Zeitplan, lokales statistisches Lernen mit Live-Fortschritt | Keine; nur lesend, standardmäßig aus |
| **Optionale Modellerklärungen** | Freiform-Berichte über lokales Ollama, eine bestehende HA-AI-Task-Entität oder eingewilligtes OpenAI/Z.ai — Integritätswächter für Zahlen, numerische Fakten-Allowlist, tägliches Anfragelimit | Keine; für Cloud-Pfade ist eine Einwilligung erforderlich |

<p align="center">
  <img src="../images/ai-adviser-overview.svg" alt="KI-Anlagenberater-Übersicht: lokale Historie, Lernen, standardmäßig Berichte aus Messdaten, optionale Modellerklärungen hinter ausdrücklicher Einwilligung" width="860">
</p>

Starte mit [iDM Smart Energy & Comfort](Smart-Energy-and-Comfort) für Aktivierung,
Beispiele, Standardwerte und Grenzen, und mit dem
[Experimentellen KI-Berater](Experimental-AI-Adviser) für Einrichtung, Berichtsmodi,
Datenschutz und das Dashboard.

### Regler-Integration

- **Systemüberwachung**: Vorlauf, Rücklauf, Warmwasser, Außentemperatur, Druck, Durchfluss
- **Heizkreise A–G**: Bis zu 7 Heizkreise mit individueller Sollwert- und Modussteuerung
- **Zonenmodule**: Bis zu 10 Zonen mit jeweils bis zu 8 konfigurierbaren Räumen; die aktuelle Navigator-10-Hardware nutzt standardmäßig 6 Räume pro Modul.
- **Solar & PV**: Solare Warmwasserbereitung, PV-Überschussnutzung, Batterieüberwachung
- **Energieüberwachung**: Wärmemenge, Laufzeiten, Energiezähler
- **Kaskade & Bivalenz**: Steuerung mehrerer Wärmepumpen, Einbindung von Heizstäben
- **GLT-Fernwartung**: GLT-Temperaturanforderungen (zyklisches Schreiben)
- **Fehlermanagement**: Fehlererkennung, Fehlerquittierung, Diagnose-Export
- **Optionales Web-Supplement**: Navigator-Generation, Softwareversion, Wärmepumpenmodell, kompakte myIDM-ID, Diagnose des reinen Web-Betriebs und Navigator-10-Infosystem-Meldungen, ohne Modbus-Werte zu ersetzen; Standardintervall 30 Sekunden
- **KNX-Bridge** *(optional)*: Bedient die IDM-KNX-Kommunikationsobjekte — mit denselben Objektnummern, Datenpunkttypen und Richtungen wie IDMs ETS-Beispielprojekt — über die Home-Assistant-KNX-Integration, sodass das Weinzierl-KNX-IP-BAOS-Gateway-Modul nicht mehr benötigt wird. Siehe [KNX-Bridge](KNX-Bridge).
- **Raumtemperatur-Weiterleitung**: Optionales Weiterleiten von Home-Assistant-Temperatursensoren in die externen IDM-Raumtemperatur-Register je Heizkreis
- **Lesbare Diagnose**: Interne IDM-Meldungen erscheinen mit Text plus strukturierten Code-/Text-Attributen
- **Direkte lokale Modbus-Runtime**: `modbus-connection` und tmodbus besitzen den Socket je Konfigurationseintrag; `idm-heatpump-api` behält die IDM-Register- und Sicherheitslogik

---

## Plattformen & Entitäten

| Plattform | Entitäten | Beschreibung |
|----------|----------|-------------|
| **Sensor** | modellabhängig | Temperaturen, Drücke, Durchflüsse, Energie, PV, Solar, Kaskade, Booster, Runtime-Versionen |
| **Binärsensor** | modellabhängig | Störalarme, Verdichterstatus, Heiz-/Kühl-/Warmwasser-Anforderung, Web-Zustände |
| **Zahl-Entität** | modellabhängig | Schreibbare Sollwerte, Grenzen, GLT-Parameter, Leistungsgrenzen |
| **Auswahl-Entität** | modellabhängig | Systemmodus, Kreismodi, Solar-/ISC-Modus |
| **Schalter-Entität** | modellabhängig | Externe Heiz-/Kühl-/Warmwasser-Anforderung |
| **Klima-Entität** | je Kreis + Zonenraum | Heiz-/Kühlmodus + Zieltemperatur für Heizkreise und Zonenmodul-Räume |
| **Warmwasserbereiter** | 1 | Warmwasser-Zieltemperatur mit Rücklesen der aktuellen Temperatur |
| **Button** | 1 | Aktive Fehler an der Wärmepumpe quittieren |

---

## Schnellnavigation

### Ich bin neu hier
1. [Installation & Einrichtung](Installation-and-Setup)
2. [Konfiguration](Configuration)
3. [Entitäten](Entities)

### Ich will automatisieren
1. [iDM Smart Energy & Comfort](Smart-Energy-and-Comfort)
2. [Konfiguration und Quellen-Zuordnung](Configuration)
3. [Aktions-Referenz](Services)

### Ich habe ein Problem
1. [Fehlerbehebung](Troubleshooting)
2. [Lokale Navigator-Weboberfläche](Local-Web-Interface)
3. [Modbus-Register](Modbus-Register)
4. [Stabilität & Release-Bereitschaft](Stability-and-Release-Readiness)

### Ich möchte beitragen
- [Beitragsleitfaden](Contributing)

---

## Technische Details

- **Batch-Lesen**: Nur exakt angrenzende, sich nicht überlappende Bereiche werden gruppiert, bis zu 40 Modbus-Wörter pro Anfrage
- **Wertevalidierung**: Nicht-verfügbar-Sentinelwerte werden als ungenutzt ausgelassen; verdächtige gruppierte Werte werden einzeln geprüft und für die Client-Sitzung unter Quarantäne gestellt
- **Bibliotheksgestützt**: Alle Register aus [`idm-heatpump`](https://github.com/Xerolux/idm-heatpump-api)
- **Handlungsfähige Setup-Diagnose**: Getrennte Meldungen für Hostname-/DNS-Fehler, abgelehntes oder deaktiviertes Modbus TCP, Timeouts, unerreichbare Endpunkte, falsche Slave-IDs, ungültige Web-PINs und nicht verfügbare Weboberflächen
- **Sichtbare Runtime-Versionen**: Die Versionen der Integration, von `idm-heatpump-api`, `modbus-connection` und `tmodbus` stehen in einem Diagnose-Sensor, in Diagnose-Exporten und in den Startprotokollen zur Verfügung
- **Datentypen**: FLOAT, UCHAR, INT8, INT16, UINT16, BOOL, BITFLAG
- **EEPROM-Schutz**: Sensible Register werden verfolgt und geschützt
- **Transportgrenze**: Rohe FC03/FC04-Lese- und FC16-Schreibvorgänge nutzen das exakte Paar `modbus-connection==4.12.2` / `tmodbus[async-serial]==0.6.2`; `4.12.2` ist die Version der Verbindungsbibliothek, nicht die Version der IDM-Integration
- **API-Grenze**: `idm-heatpump-api[web]==2.4.2` stellt Batching, Dekodierung und Schreibsicherheit bereit. Die API besitzt ihre eigene Exception-Hierarchie; die Integration nutzt den tmodbus-gestützten Socket ohne pymodbus-Abhängigkeit
- **Automatische Wiederherstellung**: API-Retry/Backoff plus Wiederverbindung nach Bedarf in der tmodbus-gestützten Verbindung
- **Verbindungsbesitz**: Jeder Konfigurationseintrag besitzt einen Socket und meldet `supports_shared_connection: false`; das zentrale Teilen über Konfigurationseinträge in Home Assistant gibt es derzeit nicht
- **Validierungsstatus**: Automatisierte Checks und Nur-Lese-Beobachtungen am Navigator 10 liegen vor; sie ersetzen keine kandidatenspezifische Clean-Install-, Langzeit- und breitere Modellvalidierung. Siehe [Stabilität & Release-Bereitschaft](Stability-and-Release-Readiness).
- **Navigator 10**: Wärmesenken-Sensoren, Durchfluss (Sieb-Monitoring), Grundwassertemperaturen, Booster A/B
- **Web-Supplement**: Das Setup prüft bei Bedarf beide unterstützten lokalen Protokolle, speichert die erfolgreiche Navigator-Familie, verwendet ihre Session wieder und wiederholt während der normalen Laufzeit-Wiederherstellung nur genau dieses Protokoll
- **Raum-Weiterleitung**: Optionaler Schreibpfad mit Updates bei Zustandsänderung, periodischem Auffrischen sowie Toleranz- und Bereichsprüfungen

---

## Links & Ressourcen

| Ressource | Link |
|----------|------|
| GitHub-Repository | https://github.com/Xerolux/idm-heatpump-hass |
| Community, Fragen & Ideen | https://github.com/Xerolux/idm-heatpump-hass/discussions |
| Issues & Bugs | https://github.com/Xerolux/idm-heatpump-hass/issues |
| HACS | https://hacs.xyz/ |
| Home Assistant | https://www.home-assistant.io/ |
| IDM EnergieSysteme | https://www.idm-energiesysteme.de/ |

---

*Dieses Wiki dokumentiert die IDM-Heatpump-Integration.*
*Entwickelt von [Xerolux](https://github.com/Xerolux)*

## Experimenteller KI-Berater (kommend)

Der experimentelle Berater liefert tägliche/wöchentliche Berichte sowie Erklärungen zu Gesundheit und Effizienz. Er ist standardmäßig aus und hat weder Werkzeuge zur Anlagensteuerung noch eine Sprach-Exposition. Ollama läuft lokal; v0.17.2-b10 ergänzt separat eingewilligte OpenAI- und Z.ai-Berichte mit begrenzten Anfragen. Siehe [Einrichtung, Berichts-Aktionen, Datenabdeckung und Grenzen](Experimental-AI-Adviser).
