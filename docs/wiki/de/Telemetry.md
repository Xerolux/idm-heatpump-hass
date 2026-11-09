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

Der erste Termin liegt zufällig 24 bis 48 Stunden nach Zustimmung; weitere
Versuche liegen 24 bis 25 Stunden auseinander. Eine lokale Minutenprüfung löst
fällige Termine aus. Der nächste Termin bleibt neustartfest erhalten.
Versand nur per HTTPS an den festen IDM-Tools-Endpunkt, mit 15 Sekunden Zeitlimit
und ohne Weiterleitungen. Netzwerkfehler, Drosselung und Serverfehler bewahren
den eingefrorenen Bericht bis zum nächsten Tagestermin; eine dauerhafte
Ablehnung (HTTP 4xx außer 429) verwirft ihn, damit der nächste Termin einen
frischen Bericht erstellt. Die Berichtskennung verhindert doppelte Zählung und
bleibt auch erhalten, wenn ein Upgrade das Schema ändert und der Bericht neu
zusammengesetzt wird.

## Zustellstatus, Fehler und Reparatur

Mit aktiver Telemetrie-Einwilligung zeigt die Gerätegruppe **Telemetrie** (bei
aktivierter optionaler Gerätehierarchie) den lokalen
Sensor **Telemetrie-Berichtsstatus**. Er meldet `not_sent`, `accepted`,
`rejected` oder `unavailable`; Attribute sind der letzte und nächste Termin,
die Zahl aufeinanderfolgender Fehlversuche, ob ein Bericht aussteht und die
Hinweisfassung der Einwilligung. Der Sensor ist rein lokal: Seine Angaben
werden nie übertragen, und bei Widerruf verschwindet er samt Registry-Eintrag.

Fehlgeschlagene tägliche Versuche zählen als fortlaufende Serie. Nach sieben
nacheinander nicht zugestellten Tagesberichten erscheint ein Hinweis unter
**Einstellungen → System → Repairs**, dass Telemetrie nicht ankommt; der
lokale Wärmepumpenbetrieb ist unberührt. Der Hinweis verschwindet von selbst,
sobald ein Bericht angenommen wird, und das Widerrufen der Einwilligung
entfernt ihn sofort. Ein gemeinsamer Timer für Telemetrie und
Firmware-Beobachtung treibt die Minutenprüfungen: Bei beiden aktiven
Einwilligungen wacht Home Assistant pro Minute einmal auf statt zweimal.

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

Unter **Neu konfigurieren → Firmware teilen und vergleichen** aktiviert ein eigener freiwilliger Schalter **Neueste gemeldete Firmware**. Standardmäßig aus, unabhängig von Telemetrie und ohne myIDM-ID nutzbar. Bestehende Zustimmungen mit `idm-firmware-v1` bleiben gültig; sie werden nicht zurückgesetzt, ausgeschaltete Funktionen nicht aktiviert. Ausschalten bricht weitere Anfragen ab und entfernt den Sensor sofort.

Übertragen werden nur Navigator-Familie, Regler-/Anlagenmodell und installierte Firmware, nach bis zu 30 Minuten zufälliger Startverzögerung, danach alle sechs Stunden plus bis zu 30 Minuten zufälliger Verzögerung. Keine myIDM-ID, Seriennummer, Betriebswerte, Zugangsdaten oder anderen HA-Daten. Der Server speichert technische Sichtungen verschlüsselt, zusammengefasst je Vergleichsgruppe, Version und UTC-Tag ohne Anlagenkennung. Automatische Löschung nach zwölf Kalendermonaten. Keine dauerhafte Client-Warteschlange. Recorder und Backups können Sensorzustände entsprechend deiner HA-Konfiguration behalten. Die Verbindungs-IP ist technisch sichtbar; verschlüsselte Ratenkennungen verfallen nach spätestens zwei Stunden beim stündlichen Bereinigungslauf. Der Datenschutzlink steht weiterhin vor dem Schalter. Ausschalten stoppt weitere Meldungen; vorhandene Sammelsichtungen bleiben bis zum Ablauf und enthalten keine Zuordnung zu einzelnen Einsendern.

Der Katalog kombiniert freigegebene Telemetrie, unabhängige Firmwaremeldungen und ausdrückliche Firmware-Metadaten privater Diagnose-ZIPs. Aus ZIPs abgeleitete Einträge bleiben an deren 90-Tage-Ablauf, Löschung und Testausschluss gebunden. Für Telemetrie gelten unverändert zwölf Monate und geprüfte Löschanfragen. Originalarchive werden nicht verändert. Die private Telemetrieübersicht zeigt Firmware, Vergleichsbereich und Quellen. Zahlen sind Quellensichtungen, keine Anzahl verschiedener Wärmepumpen; unabhängige Meldungen werden je Tag zusammengefasst.

Navigator/Regler, bekanntes Anlagenmodell, Firmware-Präfix/Kanal und Hauptreihe bleiben getrennt. Fehlende Anlagenmodelle passen nur zu anderen fehlenden Typangaben derselben Reglerreihe. `NAV10_` und `T_NAV10_` werden nie vermischt. NAVIGATOR Pro bezeichnet die Einzelraumregelung und ist kein anderer Name für Navigator 10. Allgemeine alte Pro-Angaben bleiben `unconfirmed_component`: Die neueste gemeldete Version ist innerhalb dieser gemeldeten Gruppe sichtbar, aber `newer_observed` bleibt unbekannt und erzeugt keine Update-Reparatur der Wärmepumpe. Ausdrückliche Einzelraumregelungs-Metadaten bilden eine eigene Gruppe. Widersprüchliche Familie/Präfix-Angaben begründen keine Kompatibilität.

Schon eine einzige passende Sichtung ist die **neueste gemeldete Firmware**. Entspricht sie der installierten Version, entsteht kein Hinweis auf eine neuere Version. Gemeint ist die neueste Version in unserem Katalog, keine Aussage über alle Herstellerstände. Eignung prüfen und installieren darf nur iDM oder ein autorisierter Fachbetrieb. Diese Funktion überträgt oder installiert keine Firmwaredatei. Die bestehende Hinweisfassung `idm-firmware-v1` bleibt gültig; technische Speicherung und Laufzeiten werden im aktualisierten Hinweis erklärt.

## Lastverteilung

Der erste Bericht wird zufällig 24 bis 48 Stunden nach Einwilligung gesendet,
danach jeder Versuch nach 24 bis 25 Stunden. Auch Fehlversuche reservieren den
nächsten Termin vor dem Netzwerkzugriff. Der Termin bleibt neustartfest erhalten.
Nach längerer Unterbrechung werden überfällige Berichte zusätzlich zufällig über
bis zu eine Stunde verteilt. Es gibt keine sofortigen Wiederholungen und keinen
stapelweisen Versand alter Berichte. Die lokale Minutenprüfung selbst erzeugt
keinen Netzwerkkontakt. Bereits bestehende Tagespläne erhalten einmalig Streuung.


Am 5. November 2026 bestätigt der Betreiber: Server und Backups liegen bei
netcup in Nürnberg, Deutschland. Damit ist der Standort nach Betreiberangabe
geklärt. Auftragsverarbeitungsvertrag und die tatsächliche Backup-Aufbewahrung
bzw. Löschung bleiben getrennt zu prüfen.


Der Betreiber bestätigt sechs Monate Aufbewahrung vollständiger netcup-Server-Snapshots.
Die private Datenablage liegt auf dem Root-Dateisystem und ist damit in einem
Vollabbild enthalten. Die automatische Zwölfmonatslöschung betrifft den aktiven
Datenbestand und entfernt keine alten Snapshot-Kopien. Backup-Löschung und
Wiederherstellungsverfahren bleiben vor einer allgemeinen Freigabe offen; eine
zusätzliche Aufbewahrung ist dadurch nicht automatisch freigegeben.


## Unabhängige Löschhistorie auf Proxmox

Die Löschhistorie liegt jetzt ausschließlich im eigenen unprivilegierten
LXC 117 auf Proxmox, unabhängig von den netcup-Snapshots. Auf dem Hypervisor
laufen dafür keine Anwendungsdienste; es gibt keine Host-Bind-Mounts und kein Nesting. Sie enthält nur zufällige Berichts-/Anfragekennungen und
Lösch-/Ablaufzeitpunkte, keine myIDM-ID, Kontakte oder Messwerte. Ein privater
ausgehender SSH-Tunnel schützt die Übertragung; kein neuer öffentlicher Port
wurde geöffnet. Löschungen werden erst nach dauerhafter externer Speicherung
bestätigt. Vor dem Dienststart werden die aktuellen Löschungen abgeglichen.
Scheitert der Abgleich, bleibt der Zugriff gesperrt. Die Historie wird sechs
Kalendermonate plus einen Tag aufbewahrt. Bei älteren Software-Snapshots muss
vor Freigabe zuerst der aktuelle Dienst eingerichtet werden. Die Proxmox-Historie
selbst darf nicht gemeinsam mit netcup auf einen alten Stand zurückgesetzt werden.

Die anfängliche direkte Host-Installation wurde entfernt. Benutzer, Dateien und
private Schlüssel sind vom Hypervisor entfernt; neue Schlüssel liegen im Container.
Der Container selbst darf nicht gemeinsam mit netcup auf einen veralteten Stand
zurückgesetzt werden.

Manueller Test: `idm_heatpump.send_telemetry` sendet mit bestehender Zustimmung einen Anlagenbericht (mindestens eine Minute Abstand) und plant den nächsten täglichen Versand neu. `idm_heatpump.check_firmware` fragt mit eigener Zustimmung den Firmware-Vergleich ab. Beide Aktionen verwenden `entry_id` und ändern keine Heizungsparameter.

## Automatische Qualitätsprüfung

Die private IDM-Tools-Auswertung unterscheidet Berichte von verschiedenen angegebenen myIDM-IDs. Sie zeigt Quellenabdeckung, Beobachtungsstunden, zusammengehörige Abfrage-/Fehlerzähler, Energiezuwächse und Qualitätsmerkmale je Versions-/Regelungs-/Firmware-Gruppe. Zeitfenster unter einer Stunde bleiben sichtbar, werden aber bei Energie- und Betriebszeitvergleichen ausgeschlossen. Betriebszeiten oberhalb der gerundeten Beobachtungsdauer werden markiert und nicht für Betriebsanteile verwendet oder nachträglich verändert. Null gemeldete Ereignisse beweisen keine vollständige Quellenabdeckung.

Nach einem Neuladen werden gespeicherte Zähler und Beobachtungszeit gemeinsam mit aktuellen Quellen-Ausgangswerten fortgesetzt. Neuere Analyse-Speicherstände werden ohne passende Zeit nicht nachgetragen. Bei älteren Speicherständen entfallen Betriebszeiten einmalig bis zur Bestätigung des offenen Berichtsfensters; eingefrorene Wiederholungen bleiben unverändert. Betriebsverlauf in Home Assistant, Zustimmung, Versandplan und Übertragungsformat bleiben erhalten.

## Firmware-Orientierung

Unter **Einstellungen → Geräte & Dienste → IDM Heatpump → Neu konfigurieren → Firmware-Abfrage (freiwillig)** die separate Zustimmung aktivieren. Die Gerätegruppe **Telemetrie** der Anlage zeigt dann **Neueste gemeldete Firmware** (Versionsnummer) und **Neuere Firmware gesichtet (unbestätigt)** (Ja/Nein; ohne passende Daten nicht verfügbar). Die Attribute zeigen installierte und gesichtete Version sowie den Zeitpunkt des Vergleichs. Unter **Entwicklerwerkzeuge → Aktionen → IDM Heatpump: Firmware jetzt prüfen** kann die Abfrage mit vorhandener Zustimmung manuell erfolgen.

Eine neuere passende Sichtung löst zusätzlich einen Hinweis unter **Einstellungen → System → Reparaturen** aus. Mit **Gesehen bestätigen** wird genau diese Version für das Gerät dauerhaft quittiert, auch über Neustarts hinweg. Erst eine andere neuere Version kann erneut gemeldet werden. Das bestätigt nur das Lesen des Hinweises und führt kein Update aus.

Community-Meldungen sind keine Zusage, dass die Version für deine Wärmepumpe verfügbar oder geeignet ist. iDM oder der autorisierte Fachbetrieb muss das prüfen und ein Update durchführen. Nutzer können mit freiwillig geteilten Berichten die Vergleichsbasis verbessern; die Firmware-Abfrage ist dennoch unabhängig von Telemetrie einschaltbar. Beide Zustimmungen bleiben freiwillig und standardmäßig aus.

Bei aktivierter Gerätehierarchie bilden die Cloud-Einwilligungs-Entitäten — **Neueste gemeldete Firmware**, **Neuere Firmware gesichtet (unbestätigt)** und **Telemetrie-Berichtsstatus** — ein eigenes Untergerät **Telemetrie** unter der Anlage. Die Entity-IDs bleiben beim Verschieben erhalten; die installierte Softwareversion bleibt in **Diagnose**. Ohne Gerätehierarchie liegen sie als Diagnose-Entitäten auf dem Hauptgerät.

Die übermittelten Fähigkeitsmerkmale stammen aus API-Modellmetadaten; sie beweisen keine installierte Solar-, PV- oder ISC-Ausstattung. Fehlende physische Modellangaben bleiben unbekannt.
