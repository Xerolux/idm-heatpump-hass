# Installateur-Checkliste

Alles, was die Integration für den Vollbetrieb braucht, wird auf der
**Installateur-Ebene des Reglers durch deinen Heizungsinstallateur aktiviert**
— die Integration schaltet selbst nie etwas frei und braucht keinen
Zugangscode. Drucke diese Seite aus (Druckdialog des Browsers,
*Ausgabe → Als PDF speichern*) und gib sie deinem Installateur; jeder Punkt
lässt sich in wenigen Minuten vor Ort abhaken.

## 1. Netzwerk

| ☐ | Punkt | Notizen / Wert |
|---|-------|----------------|
| ☐ | Feste IP-Adresse für den Navigator (DHCP-Reservierung im Router oder statisch am Regler) | IP: ______________________ |
| ☐ | Navigator und Home Assistant erreichen einander im selben lokalen Netzwerk | |
| ☐ | **Keine** Portfreigabe und keine Internet-Freigabe für die Ports 502, 80 und 61220 — alles bleibt lokal | |

## 2. Modbus — erforderlich, das Rückgrat

| ☐ | Punkt | Notizen / Wert |
|---|-------|----------------|
| ☐ | **Gebäudeleittechnik (Building management) → Modbus TCP → Ein** | |
| ☐ | TCP-Port belassen | normalerweise **502** |
| ☐ | Slave-/Unit-ID | normalerweise **1** |
| ☐ | Regler-Uhr zeigt das korrekte lokale Datum und die korrekte Uhrzeit | |

## 3. PV / GLT — optional: PV-Überschuss, Batterie, externe Raumsensoren

| ☐ | Punkt | Notizen |
|---|-------|---------|
| ☐ | PV-Signalquelle auf **Gebäudeleittechnik / Smartfox** gestellt (keine native Wechselrichter-Abfrage durch den Regler) | |
| ☐ | GLT-Eingangsregister freigegeben (74–86: Überschuss, PV-Produktion, Hausverbrauch, Batterieleistung, Batterie-SOC) | |
| ☐ | Kein anderer Energiemanager schreibt auf dieselben GLT-Register | |

## 4. Lokale Weboberfläche — optional: Web-only-Fallback und Zusatzwerte

| ☐ | Punkt | Notizen / Wert |
|---|-------|----------------|
| ☐ | Netzwerk-/Web-PIN am Regler gesetzt und an dich übergeben | PIN: ______________________ |
| ☐ | Weboberfläche im lokalen Netzwerk erreichbar (HTTP-Port 80; Navigator 10 zusätzlich WebSocket-Port 61220) | |

## 5. Anlageninformationen für die Einrichtung — der Installateur liest sie ab

| Punkt | Wert |
|-------|------|
| Navigator-Generation (1.0 / 1.7 / 2.0 / Pro / 10) | ______________________ |
| Software-/Firmware-Version (Service-Menü oder Web-Seite) | ______________________ |
| Anlagenschema-Nummer (z. B. L7.1) | ______________________ |
| Aktive Heizkreise (A–G) | ______________________ |
| Zonenmodule und Räume je Modul | ______________________ |
| Kaskade vorhanden? Anzahl der Einheiten | ______________________ |
| Solarthermie / ISC-Modul vorhanden? | ______________________ |

## Was die Integration *nicht* braucht

- Keinen Cloud-Zugang und keinen myIDM-Account — die Steuerung bleibt 100 % lokal
- Keine Portfreigabe, keine DMZ, keinerlei externer Zugriff
- Kein Entsperren von Installateur-Menüs während des Betriebs

Sobald dein Installateur die Punkte oben bestätigt hat, gehe weiter bei
[Installation und Einrichtung](Installation-and-Setup).
