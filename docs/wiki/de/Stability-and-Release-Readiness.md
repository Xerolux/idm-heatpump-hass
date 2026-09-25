# Stabilität & Release-Reife

Diese Seite hält fest, was verifiziert wurde, was unsicher bleibt und was gelten
musste, bevor das Beta-Label entfernt wurde. Sie ist bewusst strenger als ein
normales Changelog.

## Aktueller Status

Der veröffentlichte stabile Kanal ist **0.17.1**; die aktuelle Funktions-Beta ist
[0.17.2-b6](https://github.com/Xerolux/idm-heatpump-hass/releases/tag/v0.17.2-b6).
Die Beta ergänzt geführte Einrichtung, Smart-Energie-Statistiken, optionale
PV-Warmwasser-Automation, Komfortzeitpläne, Berater, Health Monitor und
Gerätegruppierung nach Funktionen. Siehe [Smart Energy & Comfort](Smart-Energy-and-Comfort).

Für Beta 6 waren automatisierte CI, HACS, Hassfest, Sicherheitsprüfungen,
Release-Paketierung, Verifikation der veröffentlichten Prüfsummen und der
Paket-zu-Tag-Vergleich erfolgreich. Die rein lesende Beobachtung der laufenden
Anlage im [Audit vom 18. September](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/dev/post-release-audit-2026-09-18.md)
nutzte Beta 5. Sie ist keine Hardware-Validierung und kein siebentägiger Dauertest
von Beta 6. Der [Kandidaten-Eintrag](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/release-evidence/0.17.2-b6.md)
hält den Zustand vor der Veröffentlichung fest; Clean-Install-, kandidatenspezifische
Hardware- und Langzeit-Verifizierung stehen für die Beförderung zur stabilen Version
noch aus.

## Frühere Release-Entscheidungen

**`0.17.0`** ist der stabile Schnitt der Linie, die am 2026-09-09 mit
`0.17.0-beta.1` eröffnet wurde. Sie trägt das vollständige Code-Audit-Ergebnis, die
Modell-Abgleichskorrekturen aus `beta.3` und die Navigator-1.0/1.7-Protokollfamilie
aus `beta.4`, auf `idm-heatpump-api` `2.1.1` und `modbus-connection` `4.11.1`.

**Maintainer-Entscheidung zu `0.17.0`:** Der stabile Tag wurde am 2026-09-13
geschnitten, am Tag der Veröffentlichung von `0.17.0-beta.4`, sodass Gate 6 (sieben
aufeinanderfolgende 24-Stunden-Zeiträume im Dauertest mit einem unveränderten
Kandidaten) für `beta.4` nicht erfüllt war — obwohl `beta.1` bis `beta.3` seit dem
2026-09-09 im Feld waren, ohne Regressionsmeldung. Das Live-Hardware-Follow-up von
Gate 3 bleibt doppelt offen: Kein Navigator 1.0/1.7-Gerät gehört einem Maintainer
(der Aufruf an Tester ist [#319](https://github.com/Xerolux/idm-heatpump-hass/issues/319)),
und die Verifizierung der KNX-Bridge am physischen Bus ist unverändert gegenüber
`0.16.0`. Automatisierter Preflight, Aktualität der Dependency-Pins und die volle
CI-Matrix gingen hingegen durch, und eine rein lesende Modellerkennungs-Sonde gegen
den Navigator 10 des Maintainers bestätigte am 2026-09-13, dass die neue Erkennung
einen Controller derselben Familie nicht falsch einordnet. Dies ist eine bewusste
Maintainer-Entscheidung zum Release-Zeitpunkt, kein Versehen — hier und in
`docs/release-evidence/0.17.0.md` festgehalten, damit es sichtbar bleibt.

Integration `0.17.1` und `idm-heatpump-api` `2.4.2` bilden das aktuelle exakt
gepinnte Integrations-/API-Paar. Die API-Version ist in PEP-440-Form geschrieben,
weil genau das pip auflöst; die Integration behält SemVer-Tags für HACS. Bis
einschließlich `0.14.1` war der direkte Socket auf `modbus-connection==4.0.0a3` mit
`tmodbus==0.5.0` gepinnt.

**`0.16.0`** wirft pymodbus vollständig heraus — ein Breaking Change und der Grund,
warum die Linie mit einer Beta eröffnet wurde. `idm-heatpump-api` `2.0.0` besitzt
eine eigene Ausnahme-Hierarchie (`IdmModbusError` und Unterklassen), statt von
pymodbus zu erben, und verlagert seinen eingebauten Modbus-TCP-Transport hinter ein
optionales Extra. Diese Integration injiziert einen tmodbus-basierten Transport und
installiert damit nun keinen Modbus-Stack mehr, den sie nicht spricht. Die
Transport-Pins sind `modbus-connection==4.12.2` und `tmodbus[async-serial]==0.6.2`.

**`0.17.0-beta.2`** entfernt eine Sache, die `0.17.0-beta.1` eingeführt hatte: das
Repair-Issue für ein Register, das die Wärmepumpe nicht implementiert. Ein
Controller, der für etwa `firmware_version` mit `Illegal Data Address` antwortet,
verhält sich normal — dieses Modell, diese Firmware oder Hardwareoption hat die
Funktion schlicht nicht — aber eine Warnungskarte unter **Einstellungen →
Reparaturen** liest sich wie ein Defekt, und sie forderte eine Aktion, die es nicht
gibt. Die Erklärung bleibt, als Log-Zeile und im Diagnose-Download. Alles andere ist
identisch mit `0.17.0-beta.1`; die Dauertest-Uhr startet neu, weil sich der Code
geändert hat.

**`0.17.0-beta.1`** ist der erste Kandidat der `0.17.0`-Linie und trägt das
Ergebnis des Code-Audits aus `docs/dev/code-audit-2026-09.md`. Acht Fehler sind
behoben, darunter eine Abfrage, die ihren Config-Eintrag überlebte, ein
fehlgeschlagenes Setup, das lebende Entitäten zurückließ, eine zweite Wärmepumpe
hinter einem Modbus-Gateway, die nicht mehr hinzugefügt werden konnte,
weitergeleitete Temperaturen, die nicht nach Grad Celsius umgerechnet wurden, und
Sentinel-Messwerte, die einen Temperaturzustand erreichten. Sechs Robustheits- und
drei Performance-Punkte kamen hinzu, ebenso die Extraktionen, die den betroffenen
Code testbar machten: `model_resolution.py` für den Modell-Abgleich und eine
öffentliche Coordinator-Fläche für die sieben Module, die früher in seine privaten
Attribute griffen. Beide Runtime-Pins zogen nach (`modbus-connection` `4.11.1`,
`idm-heatpump-api` `2.0.1`); keine Register-Map und kein Entitätsbezeichner änderte
sich. Es ist eine Beta, weil das Audit Modellerkennung, Setup und Teardown,
schreibende Entitäten und Dienste berührte und weil die Abhängigkeitsänderung die
Dauertest-Uhr neu startet.

**`0.16.2`** ist ein Patch auf `0.16.1`: `validate_overrides` akzeptierte einen
KNX-Gruppenadress-Override, der die abgeleitete Adresse (`base + Objektnummer`)
eines anderen bedienten Objekts beanspruchte, und die Bridge leitete diese Adresse
anschließend nur an eines der beiden Register. Adressauflösung und der
KNX-Optionenschritt lehnen jetzt jede doppelt beanspruchte Adresse ab.
`tmodbus[async-serial]` zog von `0.6.1` auf `0.6.2`; kein Register und keine
Entität änderte sich.

**`0.16.1`** ist ein Patch auf `0.16.0`: Zeigte das lokale Web-Supplement auf eine
IP-Adresse, schloss die Integration eine Home-Assistant-aiohttp-Session, statt sie
zu entkoppeln — was Home Assistant im Log meldet und was bis in einen mit jeder
anderen Integration geteilten Connector hineinreicht. Die Per-IP-Session wird jetzt
mit `detach()` freigegeben und mit `auto_cleanup=False` erzeugt, damit ein neu
gebauter Web-Client die alte nicht bis zum Stopp von Home Assistant gepinnt hält.
Nichts anderes änderte sich — Register, Entitäten, die KNX-Bridge, die Schreibwächter
und die Runtime-Pins sind identisch mit `0.16.0`.

**`0.16.0`** ist der stabile Schnitt dieser Linie, im Code identisch mit
`0.16.0-rc.6`. Die Hauptfunktion ist die **experimentelle KNX-Bridge**: Die
Integration bedient die 654 IDM-KNX-Kommunikationsobjekte selbst, über die
Home-Assistant-Integration `knx`, sodass das Weinzierl-Gateway-Modul `KNX IP BAOS
774` nicht mehr nötig ist. Die Bridge ist Opt-in und standardmäßig aus, und ihr
Verhalten am physischen Bus bleibt unverifiziert — siehe die offenen Gates unten.

**Maintainer-Entscheidung zu `0.16.0`:** Der stabile Tag wurde am 2026-08-28
geschnitten, einen Tag nach der Veröffentlichung von `0.16.0-rc.6`, sodass Gate 6
(sieben aufeinanderfolgende 24-Stunden-Zeiträume im Dauertest mit einem unveränderten
Kandidaten) nicht erfüllt war — der früheste mögliche Abschluss war der 2026-09-03.
Auch Gate 3s Live-KNX-Follow-up (Interoperabilität physischer Gruppenadress-Telegramme
und Buslast beim ersten Export) und die Navigator-2.0/Pro-Hardware-Abdeckung bleiben
offen. Automatisierter Preflight, Aktualität der Dependency-Pins und die
RC5/RC6-Live-Smoke-Nachweise am Navigator 10 des Maintainers gingen hingegen durch.
Dies ist eine bewusste Maintainer-Entscheidung zum Release-Zeitpunkt, kein Versehen
— hier und in `docs/release-evidence/0.16.0.md` festgehalten, damit es sichtbar
bleibt.

**`0.16.0-rc.6`** behält die Latest-Value-KNX-Warteschlange aus RC5 bei und ergänzt
eine Startup-Wiederherstellung für den Ereignisfilter. Home Assistant kann die
KNX-Dienste bereitstellen, bevor seine KNX-Runtime bereit ist; die Bridge wiederholt
jetzt nur die fehlenden Gruppenadress-Batches, statt ein manuelles IDM-Reload zu
verlangen. Die Schreibwächter und der konfigurierbare 60-Sekunden-EEPROM-Standard
sind unverändert. Interoperabilität physischer Gruppenadress-Telegramme und Buslast
bleiben offen.

**`0.15.1`** war die letzte Linie mit pymodbus: Sie pinnte `idm-heatpump-api`
`1.0.3`, zog das Transportpaar auf `modbus-connection==4.12.2` /
`tmodbus[async-serial]==0.6.2` und trug die Schreib-Diagnose-Arbeiten aus
[#237](https://github.com/Xerolux/idm-heatpump-hass/issues/237).

**`0.15.0`** zog dieses Paar auf `modbus-connection==4.8.1` und
`tmodbus[async-serial]==0.5.1`, ergänzt Raumtemperatursensoren für alle Heizkreise
(A–G) über `idm-heatpump-api`, Connection-Pacing-Optionen, NC-Kontakt-Invertierung
und das Aufräumen verwaister Sensoren. Sie schließt den Zyklus `0.15.0-beta.1` bis
`0.15.0-beta.3` ab. Hardware-Smoke-Nachweise für den Zyklus sind in
`docs/release-evidence/0.15.0-beta.2.md` festgehalten; der stabile Schnitt in
`docs/release-evidence/0.15.0.md`.

**Maintainer-Entscheidung zu `0.15.0`:** Der stabile Tag wurde am selben Tag
geschnitten, an dem `0.15.0-beta.3` veröffentlicht wurde, sodass Gate 6 (sieben
aufeinanderfolgende 24-Stunden-Zeiträume im Dauertest mit einem unveränderten
Kandidaten) nicht erfüllt war, und für den stabilen Kandidaten selbst existiert kein
signierter Clean-Home-Assistant-Smoke-Test (Gate 2). Automatisierter Preflight,
Aktualität der Dependency-Pins und die Hardware-Verifizierung des Beta-Zyklus gingen
hingegen durch. Dies ist eine bewusste Maintainer-Entscheidung zum
Release-Zeitpunkt, kein Versehen — hier und in `docs/release-evidence/0.15.0.md`
festgehalten, damit es sichtbar bleibt.

`idm-heatpump-api` `1.0.2` erweiterte den optionalen lokalen Web-Client um die
Raumtemperaturen der Heizkreise `B61`–`B67` (`room_temperature_HK_A` bis `G`), live
verifiziert an einem Navigator 10 ALM 6-15 (`B64 = 21.8 °C`). `1.0.3`, die Version,
die `0.15.0` pinnt, ist ein Wartungs-Release dieser Bibliothek: Sie enthält nur CI-
und Security-Toolchain-Updates, ihr öffentliches Verhalten ist identisch mit
`1.0.2`.

**Maintainer-Entscheidung zu den unten stehenden Stable-Release-Gates:** `0.11.0`
wurde als stabil veröffentlicht, ohne Gate 6 abzuwarten (den siebentägigen Dauertest,
zurückgesetzt durch die am selben Tag ausgelieferten Kandidatenänderungen
`0.11.0-beta.7`/`beta.8`) und ohne Gate 3s Live-Follow-up,
[#192](https://github.com/Xerolux/idm-heatpump-hass/issues/192), zu schließen (eine
Anzeige-Diskrepanz der Modellerkennung bei Navigator 2.0/Terra SWM; das ursprüngliche
[#44](https://github.com/Xerolux/idm-heatpump-hass/issues/44) ist geschlossen, aber
das zugrunde liegende Erkennungsthema kann erneut auftreten). Dies ist eine bewusste
Maintainer-Entscheidung, kein Versehen — hier festgehalten, damit es sichtbar
bleibt. Die Gates 1, 4, 5 und 7 sind erfüllt; Gate 2 (Clean-Install-Smoke-Test)
wurde im Rahmen dieses Schnitts nicht unabhängig erneut ausgeführt.

Der vorherige Beta-Zyklus (`0.11.0-beta.1` bis `0.11.0-beta.8`, 04.–14.08.2026) ist
in `docs/CHANGELOG.md` erhalten, und der Zyklus `0.8.5-beta.1` bis `0.8.5-beta.8`
davor bleibt in seinen historischen Nachweisdateien erhalten.

Das Stabilitäts-Audit vom Juli 2026 hat verifiziert:

- vollständige Lint-, Formatierungs-, strenge Typprüfungs- und Test-Suiten in beiden Repositorys;
- gruppierte Lesezugriffe nur über exakt benachbarte, sich nicht überlappende Registerbereiche;
- Transport-/Keine-Antwort-Fehler können ansonsten gültige Register nicht dauerhaft deaktivieren;
- registerspezifische Nicht-verfügbar-Sentinels werden als ungenutzt behandelt, nicht als beschädigt;
- Zonenraum-Modi werden einzeln geprüft und nach einer Abweichung auf den sicheren Einzel-Lesepfad der API verschoben;
- nicht unterstützte optionale Adressen werden isoliert, ohne unbeteiligte Werte zu verlieren;
- fortgeschrittene Roh-Schreibzugriffe erfordern eine explizite Risikobestätigung und behalten Datentyp-/Numerik-Validierung.
- die Protokoll-Erkennung des lokalen Web testet beide unterstützten Navigator-Familien nur,
  solange eine Erkennung nötig ist, speichert dann das erfolgreiche Protokoll dauerhaft
  und verbindet sich damit wieder, ohne zur Laufzeit die Generation zu wechseln;
- die Diagnose schwärzt Modbus-/Web-Verbindungseinstellungen und den lokalen Web-PIN
  und reduziert detaillierte Web-Fehler auf eine sichere Fehlerkategorie.

## Hardware-Nachweise (nur lesend)

Auf dem Navigator-10-System des Maintainers deckten wiederholte
Batch-gegen-Einzel-Prüfungen 170 Registerdefinitionen in 45 Gruppen und 309
Vergleiche ohne rohen Unterschied ab. Die anfangs gemeldeten Werte `254`, `255` und
`-1.0` waren in beiden Lesemodi identisch und wurden daher als registerspezifische
Nicht-verfügbar-Sentinels erfasst.

Die Kaskaden-Fähigkeitssonde an Adresse 1147 lieferte roh `FFFF` (dekodiert UCHAR
`255`). Diese als nicht verfügbar zu behandeln reduzierte die erkannte Register-Map
von 170 auf 153 Definitionen. Drei vollständige rein lesende Abfragen dauerten im
Schnitt etwa 2,38 Sekunden; 151 Werte wurden zurückgegeben, kein Register wurde in
Batch-Quarantäne gestellt und nur das von dieser Firmware nicht unterstützte
Firmware-Register wurde isoliert. Diese Zahlen beschreiben ein System und sind keine
universellen Leistungsgarantien.

Am 2026-08-26 lief auf der Home-Assistant-Instanz des Maintainers die Integration
`0.16.0-beta.1` mit API `2.0.0b1` über den Produktions-tmodbus-Adapter. Die
geschwärzte Diagnose meldete 8.836 erfolgreiche Abfragen, null Fehlschläge, eine
letzte Abfrage von 12,4 ms, keine aufeinanderfolgenden Fehlschläge oder
Modellkonflikte und ein verbundenes Navigator-10-Web-Supplement. Home Assistant
zeigte 8 Geräte und 218 Entitäten, keine IDM-Integrations-Log-Fehler, und der Lauf
führte keine Modbus-Schreibzugriffe aus. Der RC ändert nur den exakten API-Pin von
der validierten Beta auf das stabile API-Artefakt und aktualisiert die
Release-Dokumentation; das stabile API-Release hat keine Runtime-Änderungen
gegenüber seiner Beta.

## Gates für stabile Releases

Die folgenden Gates wurden für das stabile Release `0.8.5` erfüllt und bleiben die
Anforderungen, die jeder künftige stabile Schnitt erneut erfüllen muss:

1. Die auditierte API-Version veröffentlichen, die Integration exakt auf diese Version pinnen und beide vollständigen Suites gegen das veröffentlichte Artefakt erneut ausführen.
2. Den Release-Smoke-Test des Repositorys auf einer sauberen Home-Assistant-Installation ausführen, einschließlich Setup, Neustart, Rekonfiguration, Diagnose, Entladen/Neuladen und sicherer Entitäts-Schreibzugriffe.
3. Den [Navigator-2.0/Terra-SWM-Modellerkennungs-Bericht](https://github.com/Xerolux/idm-heatpump-hass/issues/44) mit einem exakten, rein lesenden Sonden-Mitschnitt auflösen oder ausdrücklich klassifizieren. Die Behandlung der bloßen Anwesenheit von Adresse 4108 darf nicht auf Annahmen hin geändert werden.
4. Eine Bestätigung aus der Community für den [Navigator-2.0-Raummodus-Batch-Fix](https://github.com/Xerolux/idm-heatpump-hass/issues/69) und die [Acht-Raum-Zonenkonfiguration](https://github.com/Xerolux/idm-heatpump-hass/issues/68) einholen.
5. Handlungsfähige Diagnosen für den [ungelösten Bericht zu generischen Serverfehlern](https://github.com/Xerolux/idm-heatpump-hass/issues/84) einholen, statt eine Code-Änderung zu raten.
6. Eine Beta-Dauertestphase ohne neue bestätigte Berichte zu Datenkorruption, Reconnect-Schleifen, unsicheren Schreibzugriffen oder Setup-Regressionen abschließen.
7. Verifizieren, dass Release Notes, README, Wiki, Dependency-Pin, Manifest-Version und die Inhalte des generierten Pakets übereinstimmen.

## Beta-Dauertest-Richtlinie

Das Dauertest-Gate bedeutet mindestens **sieben aufeinanderfolgende
24-Stunden-Zeiträume** auf einem unveränderten Kandidaten. Für `0.8.1-beta.31`
startete die Uhr mit der Veröffentlichung am `2026-07-11T18:59:52Z`; der früheste
mögliche Abschluss ist `2026-07-18T18:59:52Z`.

Erfasse Beobachtungen zur Veröffentlichung, ungefähr zur Halbzeit und nach den
vollen sieben Tagen. Prüfe bei jeder Beobachtung neue und aktualisierte Issues sowie
Hardware-Feedback. Ein bestätigtes Datenkorruptionsproblem, eine Reconnect-Schleife,
ein unsicherer Schreibzugriff oder eine Setup-Regression lässt den Dauertest
scheitern.

Eine Änderung am Kandidaten-Code, an Runtime-Abhängigkeiten, an der Paketierung, am
Config-Flow-Verhalten, an der Abfrage oder am Schreibverhalten startet einen neuen
Kandidaten und setzt die Uhr auf dessen Veröffentlichungszeitpunkt zurück. Rein
dokumentarische oder nur die Nachweise betreffende Korrekturen starten sie nicht
neu. Verstrichene Zeit allein genügt nicht: Die Kandidaten-Nachweise müssen
zusätzlich einen bestandenen Clean-HA-Smoke-Test und eine Freigabe des Maintainers
enthalten.

## Nachweise melden

Füge bei einem Wert- oder Kompatibilitätsproblem den geschwärzten Diagnose-Export,
Navigator- und Wärmepumpen-Modell, Firmware, Integrations-/API-Versionen, aktive
Heizkreise/Zonen/Funktionen, Zeitstempel, Register-/Entitätsnamen und den Wert
hinzu, den der Navigator zur gleichen Zeit angezeigt hat. Veröffentliche niemals
private IP-Adressen, PINs, Seriennummern oder Kunden-/Installateursdaten.

Zur Protokolluntersuchung sollten Maintainer den exakten Function Code, die
Startadresse, die Anzahl und die rohen Wörter sowohl des normalen Batch-Lesens als
auch eines Einzellesens mitschneiden. Hardware-Untersuchungen sind rein lesend,
außer der Besitzer hat einen bestimmten Schreibzugriff ausdrücklich autorisiert.

## Mögliche Verbesserungen

- Einen Opt-in-Dienst für geschwärzte Protokoll-Mitschnitte ausgewählter Register ergänzen, damit Nutzer Batch-/Einzel-Nachweise ohne eigene Skripte sammeln können.
- Anonymisierte Kompatibilitätsberichte nach Navigator-Modell und Firmware dauerhaft speichern, einschließlich Fähigkeits-Sentinels.
- Abfrage-Timing und Anfragezahlen in die Diagnose aufnehmen, um langsame Controller und überkonfigurierte Zonen-Setups sichtbar zu machen.
- Adaptive Hinweise zum Abfrageintervall erwägen, wenn eine konfigurierte Abfrage ihr Intervall nicht zuverlässig einhält.
- Die Climate-Entität weiter zurückstellen, bis die Semantik von IDM-Heizkreis/Raum/Kühlung dargestellt werden kann, ohne wichtige Controller-Zustände zu verbergen.
