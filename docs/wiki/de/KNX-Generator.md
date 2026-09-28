# KNX-Gruppenadressen-Generator

Die [KNX-Bridge](KNX-Bridge) leitet jede Gruppenadresse aus einer Basisadresse
ab: `Gruppenadresse = Basisadresse + IDM-Objektnummer`. ETS braucht diese
Adressen im Projekt, bevor ein echtes KNX-Gerät — ein Taster, der die
Vorlauftemperatur anzeigt, eine Visualisierung, ein Logikmodul — damit
verknüpft werden kann.

Diese Seite baut die Importdatei direkt im Browser. Basisadresse eingeben,
auswählen, was in die Datei soll, die `.xml` herunterladen — keine
Installation, und nichts verlässt deinen Rechner: Der Katalog wird mit der
Seite ausgeliefert, die Datei wird lokal erzeugt.

<div data-knx-generator></div>

> Der interaktive Block läuft auf der Dokumentations-Website. Im
> GitHub-Wiki-Spiegel werden keine Skripte ausgeführt — nutze
> [die Website](https://xerolux.github.io/idm-heatpump-hass/docs/de/knx-generator/).

## Vor dem Generieren

- **Die Basisadresse muss zur Bridge-Konfiguration passen.** Was hier steht,
  muss als *Basis-Gruppenadresse* in den Optionen der KNX-Bridge in Home
  Assistant eingetragen sein (siehe [KNX-Bridge](KNX-Bridge)); sonst sendet
  die Bridge neben den Adressen her, die dein ETS-Projekt importiert hat.
- **Der Standard `8/0/0` ist nur ein Standard.** Ist diese Hauptgruppe im
  Projekt schon belegt — ein häufiger Fall —, wähle eine freie, zum Beispiel
  `11/0/0`. Der vollständige Katalog braucht die 999 Adressen oberhalb der
  Basis bis zum Ende des Adressraums; eine Basis, bei der das nicht mehr
  passt, lehnt der Generator ab.
- **Die Auswahl sollte den Objektgruppen der Bridge entsprechen.** Was in
  der Datei steckt, sollte in den Bridge-Optionen auch aktiviert sein, damit
  die Adressen in ETS tatsächlich bedient werden.

## Import in ETS 6

1. ETS-Projekt sichern.
2. Unter *Gruppenadressen* den obersten Eintrag mit der rechten Maustaste
   anklicken und *Gruppenadressen importieren* wählen.
3. Die heruntergeladene `.xml` auswählen (dreistufiger
   Gruppenadress-Stil).
4. Den Importbericht prüfen — vor allem gegen Adressen, die im Projekt schon
   vorhanden sind.

Der `.csv`-Download ist eine lesbare Referenz — Objektnummer, Register,
Richtung —, keine Importdatei.

## Was die Vorlagen enthalten

- **Kompakt** — 43 Adressen: das, was eine Anzeige oder Visualisierung
  realistischerweise zeigt, plus die Werte, die eine KNX-Installation an die
  Wärmepumpe zurückmelden kann. Heizkreise A und B.
- **Vollständiger Katalog** — alle 654 Kommunikationsobjekte.
- **Eigene Auswahl** — die zwölf Objektgruppen mit ihren Live-Objektzahlen.
  Was jede Gruppe enthält, steht in der
  [Objektgruppen-Tabelle](KNX-Bridge#objektgruppen) auf der Seite der
  KNX-Bridge.

---

**Siehe auch:** [KNX-Bridge](KNX-Bridge) · [Konfiguration](Configuration)
