# Freiwillige IDM-Anlagentelemetrie

Telemetrie ist **standardmäßig aus**. Unter **Neu konfigurieren → Telemetrie**
gilt ein einziger Ja/Nein-Schalter für den gesamten festgelegten Umfang. Die
myIDM-ID der Wärmepumpe wird einmal eingegeben und unverändert übertragen.
Die Web-Anbindung liefert die myIDM-ID automatisch, soweit verfügbar. Keine Anonymisierung.

Nur die angebundene IDM-Anlage, ihr Regler und ihre Anbindung über diese
Integration gehören zum Umfang. Andere HA-Geräte, Entitäts- und Raumnamen,
Personen, Anwesenheit, Haushaltszähler, fremde Integrationen, Dateien, Zugangsdaten
und PINs werden für Telemetrie nicht gelesen. Nein bedeutet keine Sammlung,
keinen Telemetrie-Timer, keine Telemetrie-Warteschlange und keinen Kontakt
zum Telemetrie-Endpunkt. Die Firmware-Abfrage hat eine separate Einwilligung.
Der lokale Integrationsbetrieb bleibt davon unabhängig.

## Daten und Versand

Übertragen werden myIDM-ID, Einwilligungszeitpunkt und Hinweisfassung,
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
Zuordnung über die unveränderte myIDM-ID. Automatische Löschung zwölf
Kalendermonate nach Empfang beim stündlichen Bereinigungslauf, unabhängig von
Diagnose-ZIPs. [Löschung und Datenschutzhinweise](https://idmtools.xerolux.de/telemetry.html).
Das Formular speichert myIDM-ID und Kontakt-E-Mail privat für die Prüfung;
es löscht noch nichts. Der Betreiber prüft die Berechtigung durch Rückkontakt,
bevor passende Berichte gelöscht werden. Die myIDM-ID allein genügt nicht.
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


## Website und privater Betreiberzugang

Die [öffentliche Telemetrie-/Datenschutzseite](https://idmtools.xerolux.de/telemetry.html)
erläutert die Einwilligung und nimmt Löschanfragen mit myIDM-ID und Kontakt-E-Mail
an. Eine Anfrage löscht noch nicht automatisch. Zum Stoppen von Sammlung und
Versand wird Telemetrie in HA ausgeschaltet.

Du nutzt deinen vorhandenen **IDM-Tools-Betreiberzugang mit Authelia und zweitem
Faktor** für die [private Telemetrieübersicht](https://auth.blueml.eu/idm-captures/telemetry).
Es wird kein neues Konto oder Passwort angelegt. Auch der Capture-Eingang verlinkt
dorthin. Die Seite zeigt private myIDM-Zuordnungen, Firmware-/Verbindungsgruppen,
beobachtete Zähler und offene Löschanfragen. Vor der Löschaktion Rückkontakt und
Berechtigung prüfen. Das öffentliche Formular gewährt keinen Lesezugriff.


## Unabhängige Firmware-Beobachtungen

Unter **Neu konfigurieren → Firmware-Abfrage** aktiviert ein eigener freiwilliger
Schalter den Sensor **Neueste gemeldete Firmware**. Er ist standardmäßig aus und
übernimmt keine Telemetrie-Einwilligung. Die Firmware-Abfrage funktioniert ohne
myIDM-ID und ohne Telemetrie. Telemetrie auszuschalten beendet eine separat
freigegebene Firmware-Abfrage nicht. Ausschalten der Firmware-Abfrage bricht
laufende Anfragen ab und entfernt Sensor und Registry-Eintrag sofort. Ohne diese
Einwilligung gibt es keinen Kontakt zum Firmware-Katalog.

Übertragen werden ausschließlich Navigator-Familie, Regler-/Anlagenmodell und
installierte Firmware, beim Start und alle sechs Stunden. Keine myIDM-ID,
Betriebszähler, Temperaturen, Zugangsdaten oder fremden HA-Daten. Es gibt keine
dauerhafte Firmware-Warteschlange; die Integration hält nur das aktuelle Ergebnis.
HA kann Sensorzustände gemäß deiner Recorder-/Backup-Konfiguration speichern. Der
Server verarbeitet die Abfrage vorübergehend und speichert keinen Anlagenbericht.
Die Verbindungs-IP ist technisch sichtbar; kurzlebige Ratenkennungen verfallen
nach spätestens zwei Stunden beim nächsten stündlichen Bereinigungslauf. Beide
Funktionen verlinken vor ihrem Zustimmungsschalter deutlich auf die vollständigen
Datenschutzhinweise.

Der Katalog verwendet nur freigegebene Community-Telemetrie, keine alten
Diagnose-ZIPs. Navigator/Regler, bekanntes Anlagenmodell, Firmware-Präfix/Kanal und
Hauptreihe müssen passen. Fehlende Anlagenmodelle werden nur mit anderen Meldungen
ohne Typangabe innerhalb derselben bekannten Regler-/Firmware-Reihe verglichen.
Test- und stabile Kanäle bleiben getrennt; Buildnummern werden numerisch verglichen.
Unbekannte Zuordnung oder fehlende Meldungen liefern keine Versionsempfehlung.

Das ist keine offizielle IDM-Verfügbarkeit, Installationsberechtigung oder
Kompatibilitätsfreigabe. Eignungsprüfung und Installation bleiben bei IDM/Fachbetrieb.
Telemetrie hilft beim Aufbau des Katalogs, ist aber keine Voraussetzung für seine
Abfrage. Telemetrie verwendet weiterhin Hinweisfassung v3, die unabhängige
Firmware-Einwilligung `idm-firmware-v1`. Deren Zeitpunkt und Fassung werden nur
lokal gespeichert und nicht bei der Firmware-Abfrage übertragen.
