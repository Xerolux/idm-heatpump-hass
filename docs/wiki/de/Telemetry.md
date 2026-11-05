# Freiwillige IDM-Anlagentelemetrie

Telemetrie ist **standardmäßig aus**. Unter **Neu konfigurieren → Telemetrie**
gilt ein einziger Ja/Nein-Schalter für den gesamten festgelegten Umfang. Die
myIDM-ID der Wärmepumpe wird einmal eingegeben und unverändert übertragen.
Die Web-Anbindung liefert die myIDM-ID automatisch, soweit verfügbar. Keine Anonymisierung.

Nur die angebundene IDM-Anlage, ihr Regler und ihre Anbindung über diese
Integration gehören zum Umfang. Andere HA-Geräte, Entitäts- und Raumnamen,
Personen, Anwesenheit, Haushaltszähler, fremde Integrationen, Dateien, Zugangsdaten
und PINs werden für Telemetrie nicht gelesen. Nein bedeutet keine Sammlung,
keinen Timer, keine Warteschlange und keinen Netzwerkkontakt oder Verbindungstest.
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


## Warum die Meldungen helfen – und dein Firmware-Sensor

Freigegebene Anlagenmeldungen zeigen, welche Firmware mit welchen Funktionen
arbeitet und wo Verbindungsprobleme oder Störungen auftreten. Damit lässt sich
die Integration gezielt verbessern. Zusätzlich erscheint ausschließlich bei
aktivierter Telemetrie der Sensor **Neueste gemeldete Firmware**. Er fragt beim
Start und höchstens alle sechs Stunden den passenden Firmware-Katalog ab.

Der Server ordnet jede Beobachtung nach Navigator-Familie, genauem Anlagenmodell,
Firmware-Präfix und numerischer Hauptreihe zu. `T_NAV10_20.*`, `NAV10_20.*` und
`m_20.*` werden nicht vermischt; auch andere Modelle bleiben getrennt. Die
Versionsreihenfolge wird numerisch einschließlich Buildnummern verglichen.
Meldet die Schnittstelle keinen W�rmepumpentyp, werden ausschlie�lich Meldungen
ohne Typangabe innerhalb derselben erkannten Steuerung und Firmware-Reihe
verglichen. Bekannte Anlagenmodelle bleiben getrennt. Eine unbekannte Steuerung
oder Firmware-Reihe liefert keine Empfehlung.

Die gemeldete Version ist **keine offizielle neueste IDM-Freigabe** und garantiert
keine Verfügbarkeit für deine Anlage. Installation und Eignungsprüfung bleiben
bei IDM bzw. dem Fachbetrieb. Passende Firmware-Versionen können anderen Nutzern
ohne myIDM-ID oder Betriebsdaten angezeigt werden. Der Sensor zeigt zusätzlich,
ob eine höhere Version beobachtet wurde. Zunächst kann er mangels Meldungen
unbekannt sein; vorhandene Diagnose-ZIPs werden dafür nicht umgenutzt.

Bei Ausschalten wird der Sensor samt Registry-Eintrag entfernt und jede
Firmware-Abfrage beendet. Ohne Einwilligung gibt es weder Anzeige noch Abfrage.

Dieser zus�tzliche Zweck verwendet die Datenschutzhinweise `idm-telemetry-v3`
und ben�tigt eine ausdr�ckliche Einwilligung.
