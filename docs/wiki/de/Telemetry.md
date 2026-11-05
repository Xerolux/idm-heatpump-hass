# Freiwillige IDM-Anlagentelemetrie

Telemetrie ist **standardmäßig aus**. Unter **Neu konfigurieren → Telemetrie**
gilt ein einziger Ja/Nein-Schalter für den gesamten festgelegten Umfang. Die
Seriennummer der Wärmepumpe wird einmal eingegeben und unverändert übertragen.
Eine myIDM-ID wird nicht als Seriennummer vorausgesetzt. Keine Anonymisierung.

Nur die angebundene IDM-Anlage, ihr Regler und ihre Anbindung über diese
Integration gehören zum Umfang. Andere HA-Geräte, Entitäts- und Raumnamen,
Personen, Anwesenheit, Haushaltszähler, fremde Integrationen, Dateien, Zugangsdaten
und PINs werden für Telemetrie nicht gelesen. Nein bedeutet keine Sammlung,
keinen Timer, keine Warteschlange und keinen Netzwerkkontakt oder Verbindungstest.
Der lokale Integrationsbetrieb bleibt davon unabhängig.

## Daten und Versand

Übertragen werden Seriennummer, Einwilligungszeitpunkt und Hinweisfassung,
Berichtskennung, Integrationsversion, Navigator-Familie und Modell, Anlagenmodell,
Firmware, Verbindungsart und Webvariante, erkannte Solar-/PV-/Kaskaden-/ISC-Funktionen,
Registeranzahl, beobachtete Stunden, Modbus-Abfragen und -Fehler, beobachtete
Web-Ausfälle und Störungscode-Wechsel. Bereits vorhandene Anlagenanalysen können
Verdichterstarts, Betriebszeiten und elektrische/thermische Energiemengen ergänzen.
Fehlende Quellen bleiben fehlend. Keine zusätzlichen Anlagenabfragen oder Befehle.

Anlagen-Zähler und höchstens ein ausstehender Bericht bleiben lokal neustartfest
gespeichert: verzögert nach Änderungen und beim sauberen Entladen. Abrupter
Stromverlust kann ungespeicherte Änderungen verlieren. HA-Ausfallzeit wird nicht
als beobachtete Anlagenlaufzeit erfunden. Störungswechsel sind Beobachtungen,
kein vollständiges Fehlerprotokoll.

Der erste Versuch erfolgt frühestens 24 Stunden nach Zustimmung, stündlich geprüft.
Weitere Versuche liegen mindestens 24 Stunden auseinander, auch nach Neustarts.
Versand nur per HTTPS an den festen IDM-Tools-Endpunkt, mit 15 Sekunden Zeitlimit
und ohne Weiterleitungen. Fehlgeschlagene Berichte bleiben bis zum nächsten
Tagestermin erhalten; die Berichtskennung verhindert doppelte Zählung.

Ausschalten stoppt die Sammlung, bricht laufende Aufgaben ab und löscht die lokale
Sammlung. Bereits empfangene Daten können nicht zurückgeholt werden. Erneutes
Einschalten beginnt neu. Eine neue Hinweisfassung erfordert erneute Zustimmung.
Fernsteuerung und eine nachträgliche Erweiterung der Datenfelder sind nicht erlaubt.

## Speicherung und Rechte

Private serverseitige AES-GCM-Verschlüsselung außerhalb des Webverzeichnisses,
Zuordnung über die unveränderte Seriennummer. Automatische Löschung zwölf
Kalendermonate nach Empfang beim stündlichen Bereinigungslauf, unabhängig von
Diagnose-ZIPs. [Löschung und Datenschutzhinweise](https://idmtools.xerolux.de/telemetry.html).
Das Formular speichert Seriennummer und Kontakt-E-Mail privat für die Prüfung;
es löscht noch nichts. Der Betreiber prüft die Berechtigung durch Rückkontakt,
bevor passende Berichte gelöscht werden. Die Seriennummer allein genügt nicht.
Bitte Telemetrie zusätzlich ausschalten, damit keine neuen Berichte eingehen.

Die Hinweise benennen Verantwortlichen, Zweck, Einwilligung, Empfänger,
Aufbewahrung, Widerruf, Rechte und Kontakt. Hosting, Auftragsverarbeitung,
Protokolle, Backups und tatsächliche Löschbearbeitung müssen vor Inbetriebnahme
geprüft werden. Der Code ist keine rechtliche Zertifizierung; HACS ist keine
Datenschutzfreigabe.

## Abgrenzung zum IDM Web Capture

Tagesberichte helfen bei Firmware-Kompatibilität und Stabilität. Sie ersetzen
keine Protokollaufzeichnung, Erkennung unbekannter Register oder Diagnose bei
nicht startender HA-Integration. Dafür bleibt IDM Web Capture sinnvoll. Weder
die Zustimmung noch Serverantworten erlauben ferngesteuerte Aufzeichnungen.
