---
created: 2026-07-11T11:57:54+02:00
title: Webvariante nach Erkennung fixieren
area: general
files:
  - custom_components/idm_heatpump/web_data.py:277
  - custom_components/idm_heatpump/web_data.py:327
  - custom_components/idm_heatpump/coordinator.py:575
  - tests/test_web_data.py:385
---

## Problem

Navigator 2.0 und Navigator 10 verwenden unterschiedliche Weblogin-Protokolle.
Bei Installation und Rekonfiguration müssen deshalb beide Varianten automatisch
getestet werden. Sobald eine Variante erfolgreich erkannt wurde, darf der
normale Web-Pollingpfad bei späteren Verbindungs-, Session- oder
Authentifizierungsproblemen nicht mehr auf die andere Navigator-Variante
wechseln. Der aktuelle Fallback kann nach dem Fehlschlag eines gecachten Clients
erneut beide Varianten durchlaufen und dadurch unnötige Timeouts oder
irreführende PIN- und Verbindungsfehler der falschen Schnittstelle erzeugen.

## Solution

Die tatsächlich erfolgreiche Factory-Variante (`nav10` oder `nav20`) beim
Einrichten beziehungsweise Rekonfigurieren explizit speichern. Solange noch
keine Variante erfolgreich erkannt wurde, beide Loginvarianten testen. Nach der
Erkennung ausschließlich dieselbe Variante und dasselbe Protokoll neu verbinden;
eine vollständige Neuerkennung nur bei Installation oder Rekonfiguration
durchführen. Tests für beide Erkennungsreihenfolgen sowie für Wiederverbindung,
Sessionablauf, Authentifizierungsfehler und Transportfehler ergänzen.
