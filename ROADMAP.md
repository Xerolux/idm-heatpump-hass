# IDM Heatpump – gemeinsame Produkt- und Technik-Roadmap

Stand: 2. Juli 2026<br>
Geltungsbereich: [`Xerolux/idm-heatpump-hass`](https://github.com/Xerolux/idm-heatpump-hass) und [`Xerolux/idm-heatpump-api`](https://github.com/Xerolux/idm-heatpump-api)

Diese Roadmap betrachtet Integration und API als ein gemeinsames Produkt. Die API besitzt das Modbus-Protokoll, die Register und die Gerätesicherheit; die Home-Assistant-Integration übersetzt diesen stabilen Kern in Home-Assistant-Entitäten, Konfiguration, Diagnosen und Bedienung.

## Zielbild

- Zuverlässiger lokaler Betrieb ohne Cloud-Abhängigkeit.
- Eine einzige, geprüfte Quelle für Register, Datentypen, Grenzwerte und Modellfähigkeiten in `idm-heatpump-api`.
- Eine dünne Home-Assistant-Schicht ohne duplizierte Protokoll- oder Registerlogik.
- Sichere Schreibzugriffe mit klaren Grenzen, EEPROM-Schutz und nachvollziehbaren Fehlern.
- Reproduzierbare, gekoppelte Releases von API und Integration.
- Nachweisbare Unterstützung je IDM-Modell und Firmware statt pauschaler Kompatibilitätsversprechen.
- Optional eine spätere Aufnahme in Home Assistant Core; bis dahin klare Bezeichnung als inoffizielle HACS-Custom-Integration.

Nicht vorgesehen sind Cloud-Zwang, Telemetrie, Fernzugriff, Firmware-Updates oder Schreibzugriffe auf undokumentierte Register.

## Bestandsaufnahme

### Was bereits gut ist

- Aktuelle Releases: HASS `v0.7.3`, API `v0.3.7`.
- Die Integration nutzt die eigenständige API-Bibliothek und hat die alten lokalen Registergeneratoren weitgehend entfernt.
- Lokale Prüfung der Integration: 373 Tests bestanden; Ruff, Ruff-Format und striktes mypy sind grün.
- Lokale Prüfung der API: 46 Tests und mypy bestanden; GitHub Actions sind für die letzten Änderungen grün.
- Asynchroner Modbus-Client, Batch-Reads, Wiederverbindung, Modell-/Fähigkeitserkennung, Registergrenzen und EEPROM-Schutz existieren.
- HACS-, Hassfest-, Release-, Pages- und Wiki-Workflows sind vorhanden.
- Dokumentation, Übersetzungen, Diagnosen, Reparaturhinweise und ein UI-Konfigurationsfluss sind vorhanden.

### Festgestellte Lücken und Risiken

| Priorität | Befund | Auswirkung |
|---|---|---|
| P0 | Die Integration erlaubt `idm-heatpump-api>=0.3.3`, benötigt für die aktuellen Modellfilter aber faktisch die Korrekturen aus `0.3.7`. | Nicht reproduzierbare Installationen und Rückfall auf bekannte Registerfehler. |
| P0 | Issue [#44](https://github.com/Xerolux/idm-heatpump-hass/issues/44) ist trotz gemergtem Fix und Release noch offen. | Der Fix ist ohne Bestätigung auf echter Terra-SWM-/Navigator-2-Hardware nicht abgeschlossen. |
| P0 | Der HASS-Pages-Workflow lief zuletzt in einen Deployment-Timeout. | Dokumentation kann trotz grüner Code-CI veraltet bleiben. |
| P0 | API-Code besteht `ruff check`, aber vier Dateien bestehen `ruff format --check` nicht; CI prüft das Format nicht. | Der lokale Qualitätsstandard und CI widersprechen sich. |
| P1 | `library_adapter.py` hat rund 1.200 Zeilen und enthält Namen, Einheiten, Klassifizierung und Sonderfalllogik. | Hohe Änderungsfläche; API-Metadaten und HA-Abbildung können auseinanderlaufen. |
| P1 | Es gibt keine automatischen Cross-Repo-Vertragstests zwischen API-Releases und Integration. | API-Änderungen können erst nach Veröffentlichung in HASS brechen. |
| P1 | API-CI testet Python 3.12/3.13, während die Integration Python 3.14 und HA 2026.5 verwendet. | Die wichtigste Verbraucherkombination fehlt in der API-Matrix. |
| P1 | API-Tests decken hauptsächlich Unit-Fälle ab; Coverage wird nicht gemessen oder erzwungen. | Reconnect-, Timeout-, Batch-Fallback- und Schreibschutzregressionen bleiben leichter unentdeckt. |
| P1 | API-mypy ist bewusst locker (`disallow_untyped_defs=false`); ein `py.typed`-Marker fehlt. | Konsumenten erhalten keinen belastbaren typisierten Bibliotheksvertrag. |
| P1 | Beide `main`-Branches sind ungeschützt. | Release- und Protokollcode kann ohne Review oder erfolgreiche Checks direkt geändert werden. |
| P1 | Release-Automation erzeugt und pusht Versionscommits/Tags selbst; Integration und API werden getrennt veröffentlicht. | Teilreleases, falsche Tags und schweres Rollback sind möglich. |
| P2 | `quality_scale.yaml` bezeichnet Gold und Platinum als erledigt. Eine offizielle Einstufung gibt es aber erst nach Aufnahme und Review in Home Assistant Core. | Außenwirkung und tatsächlicher HA-Status können verwechselt werden. |
| P2 | Die API-README nennt die HASS-Integration „official“. Das Projekt ist aktuell eine inoffizielle Custom-Integration. | Missverständliche Kommunikation und unnötiges Marken-/Support-Risiko. |
| P2 | Qualitätsangaben sind veraltet (zum Beispiel 247 statt aktuell 373 Tests) und mehrere Dokumentationsquellen werden separat gepflegt. | Dokumentationsdrift und unzuverlässige Statusaussagen. |
| P2 | Die API unterstützt laut Paketmetadaten nur Python 3.12/3.13-Klassifikatoren, wird aber durch HASS mit 3.14 genutzt. | PyPI-Metadaten und reale Nutzung widersprechen sich. |
| P2 | Dependabot/Renovate, CodeQL, Dependency-Audit und verpflichtende Coverage-Grenzen fehlen. | Abhängigkeiten und Lieferkette werden nur manuell gepflegt. |
| P2 | Für reale Geräte gibt es keine öffentlich dokumentierte Modell-/Firmware-Testmatrix. | „Unterstützt“ ist nicht präzise genug messbar. |

## Reihenfolge und Release-Ziele

```text
Stabilisierung
    -> API-Vertrag und Tests
        -> dünne HASS-Architektur
            -> Geräteabdeckung und UX
                -> Entscheidung HACS oder Home Assistant Core
                    -> langfristiger Betrieb
```

Jede Phase soll in kleine Issues und Pull Requests zerlegt werden. Protokoll-/Registeränderungen werden zuerst in der API veröffentlicht und danach in der Integration übernommen.

## Phase 0 – v0.7.x stabilisieren

Ziel: Der aktuelle Stand ist reproduzierbar, dokumentiert und auf betroffener Hardware bestätigt.

- [ ] **HASS / P0:** `idm-heatpump-api` in `manifest.json` zunächst exakt auf `0.3.7` pinnen; `pymodbus`-Kompatibilität ebenfalls bewusst festlegen.
  - Akzeptanz: Frische HACS-Installation löst immer die getestete Kombination auf.
  - Akzeptanz: CI installiert exakt dieselben Runtime-Abhängigkeiten wie das Release-ZIP.
- [ ] **HASS / P0:** Fix für Issue #44 mit dem Reporter auf IDM Terra SWM / Navigator 2 validieren.
  - Prüfen: Initialisierung, Modellkennung, keine Abfragen von Navigator-10-only-Registern, vollständiger erster Poll, Wiederverbindung.
  - Issue erst nach Hardwarebestätigung schließen oder mit einem klaren Restproblem weiterführen.
- [ ] **HASS / P0:** Pages-Deployment analysieren und stabilisieren.
  - Deployment-Concurrency, veraltete Deployments und Environment-Schutz prüfen.
  - Akzeptanz: zwei aufeinanderfolgende manuelle Deployments sind grün; URL enthält den aktuellen Stand.
- [ ] **API / P0:** `ruff format` anwenden und `ruff format --check` in CI aufnehmen.
- [ ] **beide / P0:** Versions-, Support- und Statusaussagen synchronisieren.
  - HASS-README, deutsche README, Manifest, Changelog, Wiki und API-README prüfen.
  - „Official“ bis zu einer Core-Aufnahme durch „inoffizielle Home-Assistant-Custom-Integration“ ersetzen.
  - Testzahlen und Qualitätsstatus nicht als manuell gepflegte Momentaufnahme ausgeben oder automatisch erzeugen.
- [ ] **beide / P0:** Einen Release-Smoke-Test dokumentieren: Installation aus Release-Artefakt, Config Flow, erster Poll, ein sicherer Write, Reload, Unload und Upgrade vom vorherigen Release.

Abschlusskriterium: v0.7.x läuft auf mindestens Navigator 2.0 und Navigator 10 ohne bekannte P0-Regression; Dokumentation und veröffentlichte Abhängigkeiten stimmen überein.

## Phase 1 – stabiler API-Vertrag (API 0.4.x / HASS 0.8.x)

Ziel: `idm-heatpump-api` wird zu einem kleinen, streng getesteten und semantisch versionierten öffentlichen Vertrag.

### Öffentliche API und Versionierung

- [ ] Öffentliche Symbole in `__all__` dokumentieren und mit einem API-Snapshot-Test schützen.
- [ ] SemVer-Regeln festlegen:
  - Patch: Registerkorrekturen ohne öffentlichen Bruch.
  - Minor: additive Register, Metadaten und Fähigkeiten.
  - Major: Umbenennungen, Signatur- oder Verhaltensbrüche mit Migrationsleitfaden.
- [ ] Deprecation-Mechanismus und mindestens einen Minor-Release Übergangszeit definieren.
- [ ] Changelog automatisch auf fehlende Versionen prüfen; derzeit fehlen beziehungsweise überlappen einzelne Einträge zwischen `0.3.2` und `0.3.7`.
- [ ] HASS-Kompatibilität pro API-Version in einer maschinenlesbaren Matrix festhalten.

### Typisierung und Paketqualität

- [ ] API auf striktes mypy umstellen; Ausnahmen klein und kommentiert halten.
- [ ] `py.typed` ausliefern und mit einem externen Typ-Konsumententest prüfen.
- [ ] Python 3.12, 3.13 und 3.14 in Klassifikatoren und CI testen.
- [ ] Wheel und sdist in CI bauen, mit `twine check` prüfen und in einer frischen Umgebung importieren.
- [ ] Unterstützte `pymodbus`-Versionen als Matrix testen; Obergrenze setzen, falls neue Major-Versionen nicht garantiert kompatibel sind.

### Testpyramide

- [ ] Coverage-Bericht und eine zunächst realistische, danach steigende Mindestgrenze einführen.
- [ ] Deterministischen Fake-Modbus-Server beziehungsweise Transport bauen für:
  - normale Reads/Writes und Float-Byteorder;
  - Illegal Address / Illegal Function;
  - Timeout, Verbindungsabbruch und Reconnect;
  - unvollständige Antworten;
  - Batch-Split und Einzelregister-Fallback;
  - dauerhaft fehlende Register und Reset;
  - Sentinelwerte `-1`, `255`, NaN und Infinity;
  - parallele Requests und Lock-Verhalten.
- [ ] Property-/Grenzwerttests für Encode/Decode, Multiplikatoren, Min/Max, Enums und Bitflags ergänzen.
- [ ] Registerkarten gegen ein versioniertes, maschinenlesbares Referenzschema prüfen, nicht nur gegen manuell duplizierte Testwerte.

### Schreibsicherheit

- [ ] Schreibklassen explizit unterscheiden: flüchtig, zyklisch, EEPROM-sensitiv, write-only und verboten.
- [ ] EEPROM-Drosselung, Prozessneustart und Zeitfenster testen und dokumentieren.
- [ ] Zyklische GLT-Schreibwerte mit Ablauf/Heartbeat absichern, damit alte Vorgaben nicht unbemerkt weiterwirken.
- [ ] Vor jedem Write Datentyp, Bereich, ausgeschlossene Enumwerte und Modellverfügbarkeit validieren.
- [ ] Strukturierte, redigierte Debugdaten für Read-/Writefehler anbieten; keine IPs oder Zugangsdaten in Standarddiagnosen.

Abschlusskriterium: Ein API-Release kann unabhängig installiert, strikt typisiert, gebaut und gegen alle drei Python-Versionen sowie einen simulierten Modbus-Transport geprüft werden.

## Phase 2 – Integration vereinfachen und Verträge koppeln

Ziel: Home Assistant enthält nur HA-spezifische Logik; Register- und Gerätewissen bleibt in der API.

### Dünner Adapter

- [ ] Verantwortlichkeiten von `library_adapter.py` inventarisieren und in kleine Module zerlegen:
  - Register -> EntityDescription;
  - Übersetzungsschlüssel und Enum-Slugs;
  - Einheiten, Device Classes und State Classes;
  - modellabhängige Entity-Auswahl.
- [ ] Neutrale Metadaten wie Einheit, Schreibbarkeit, Grenzen, Standardaktivierung und Messsemantik in der API vervollständigen.
- [ ] HA-spezifische Typen und Übersetzungen in der Integration belassen.
- [ ] Zielgröße festlegen: Adapter deutlich unter dem heutigen Umfang; keine langen manuellen Namenslisten, wenn Translation Keys reichen.

### Cross-Repo-Vertragstests

- [ ] In der API-CI die Integration gegen den API-Branch auschecken und Kern-Vertragstests ausführen.
- [ ] In der HASS-CI gegen exakt gepinnte sowie optional neueste kompatible API testen.
- [ ] Tests für jedes API-Register sicherstellen:
  - eindeutiger stabiler Entity Key;
  - gültige Einheit/Device Class/State Class;
  - beschreibbare Register erscheinen nur auf erlaubten Plattformen;
  - keine Adressduplikate ohne dokumentierten Alias;
  - keine Navigator-10-Entities auf erkanntem Navigator 2.0.
- [ ] Automatischen Dependency-Update-PR von API-Release zu HASS mit Changelog und bestandenen Vertragstests einrichten.

### Home-Assistant-Lebenszyklus

- [ ] Config-Entry-Migrationen und Unique-ID-Stabilität für alle früheren Domains/Versionen testen.
- [ ] Auto-Erkennung als Standard verwenden, manuelle Auswahl nur als nachvollziehbaren Override anbieten.
- [ ] Erkennungsresultat, Firmware und aktive Fähigkeiten in Diagnosen aufnehmen und sensible Netzwerkdaten redigieren.
- [ ] Reload, Reconfigure, Unload, fehlgeschlagenes Setup und Wiederherstellung mit realistischeren HA-Fixtures testen.
- [ ] Unbenutzte Entities sauber deaktivieren/entfernen, ohne Benutzeranpassungen oder Historie unnötig zu verlieren.
- [ ] Reparaturhinweise nach Ursache trennen: nicht erreichbar, falsche Slave-ID, inkompatible Firmware, Register nicht unterstützt und Write abgelehnt.

Abschlusskriterium: Eine API-Änderung kann die Integration nicht mehr unbemerkt brechen, und modellfremde Register werden bereits vor dem Poll ausgeschlossen.

## Phase 3 – Geräteabdeckung, Bedienung und Dokumentation

Ziel: Unterstützung wird pro Modell/Firmware nachgewiesen und die Integration bleibt trotz vieler Register verständlich.

### Hardware- und Firmware-Matrix

- [ ] Matrix mit mindestens folgenden Zeilen pflegen: Navigator 2.0, Navigator Pro, Navigator 10, Terra SWM sowie unbekanntes/zukünftiges Modell.
- [ ] Pro Eintrag dokumentieren: Wärmepumpentyp, Navigator-Modell, Firmware, getestete API-/HASS-Version, aktive Kreise/Zonen/PV/ISC/Kaskade und Tester.
- [ ] Anonymisierte Diagnose-Snapshots als Regression-Fixtures erlauben; Opt-in und manuell eingereicht, niemals automatisch übertragen.
- [ ] „confirmed“, „community-tested“, „expected“ und „unsupported“ klar unterscheiden.

### Registerqualität

- [ ] Für jedes Register Quelle, Dokumentversion, Modelle, Zugriff, Sentinelwerte und letzte Verifikation speichern.
- [ ] Generierte Registerreferenz aus demselben Schema für API-Dokumentation und HASS-Wiki erzeugen.
- [ ] Konflikte zwischen offizieller Doku und realem Gerät als bekannte Abweichung versionieren.
- [ ] Neue Register nur mit Quelle, Test und Modell-Gate aufnehmen.

### Home-Assistant-UX

- [ ] Entity-Anzahl und Standardaktivierung je typischer Anlage prüfen; Diagnose- und Spezialwerte standardmäßig deaktivieren.
- [ ] Geräte-/Entity-Namen vollständig über Translation Keys in Deutsch und Englisch bereitstellen.
- [ ] Schreibaktionen mit klaren Beschreibungen, Grenzwerten und Sicherheitswarnungen versehen.
- [ ] Energie-Dashboard-Kompatibilität für Energie-, Leistung- und Total-Increasing-Sensoren validieren.
- [ ] Beispiele für PV-Überschuss, Warmwasser, Urlaub, Störung und Lastbegrenzung als getestete Automationen pflegen.
- [ ] Einen Diagnoseleitfaden „Welche Daten brauchen wir für einen Bugreport?“ erstellen.

Abschlusskriterium: Nutzer können vor der Installation erkennen, ob ihr Modell getestet ist; Maintainer können einen Registerfehler anhand eines standardisierten Reports reproduzieren.

## Phase 4 – Entscheidung: HACS dauerhaft oder Home Assistant Core

Ziel: Die Veröffentlichungsstrategie wird bewusst entschieden, nicht nur als Qualitätslabel behauptet.

### Entscheidungstor

Vor einer Core-Einreichung klären:

- Gibt es ausreichend aktive Nutzer und mindestens zwei langfristig verfügbare Maintainer?
- Ist die Hardware weiterhin erhältlich und die Modbus-Schnittstelle etabliert?
- Ist die API stabil genug für Review und langfristige Wartung?
- Kann ein kleiner initialer Core-PR mit nur einer essenziellen Plattform echten Nutzen liefern?
- Sind Markenname, Logo, Dokumentquellen und die inoffizielle Beziehung zu IDM sauber erklärt?

Falls diese Punkte nicht erfüllt sind, bleibt HACS ein legitimes Ziel; die technische Qualität soll trotzdem gehalten werden.

### Schritte für Home Assistant Core

- [ ] Core-Integration aus aktuellem `dev`-Branch scaffolden und nur den minimalen, reviewbaren Umfang übernehmen.
- [ ] Kommunikation ausschließlich über eine veröffentlichte, exakt gepinnte API-Version führen.
- [ ] Erste Einreichung gemäß aktueller HA-Empfehlung auf eine zentrale Plattform und notwendige Funktionen begrenzen; zusätzliche Plattformen und Services folgen separat.
- [ ] Custom-Integration-spezifische Felder wie `version` und `issue_tracker` beim Core-Port entfernen beziehungsweise anpassen.
- [ ] Offizielle Dokumentationsseite im `home-assistant.io`-Repository erstellen.
- [ ] Brand-Assets in das Home-Assistant-Brands-Repository übertragen.
- [ ] Code, Tests und Fixtures an HA-Core-Konventionen und das dortige Testframework anpassen.
- [ ] Quality-Scale-Checkliste zunächst für Bronze nachweisbar erfüllen; Gold/Platinum erst nach Aufnahme und separatem Review beanspruchen.
- [ ] Diagnose- und Custom-Action-Funktionen gegebenenfalls in spätere kleine PRs verschieben.
- [ ] Migration von HACS zu Core einschließlich Entity-/Device-Registry und Domain-Kollision testen und dokumentieren.

Referenzen: [Integration zu Core beitragen](https://developers.home-assistant.io/docs/core/integration/contributing_to_core/), [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/), [Integrationsdokumentation erstellen](https://developers.home-assistant.io/docs/documenting/create-page/).

Abschlusskriterium: Entweder ist ein kleiner Core-PR reviewbereit oder die Entscheidung „HACS-first“ ist mit Wartungszeitraum und Qualitätszielen dokumentiert.

## Phase 5 – Lieferkette, Releases und Projektbetrieb

Ziel: Releases sind wiederholbar, sicher und auch nach Monaten noch wartbar.

### GitHub und Lieferkette

- [ ] `main` in beiden Repositories schützen: Pull Request, grüne Pflichtchecks, keine Force-Pushes, keine gelöschte Historie.
- [ ] `CODEOWNERS` ergänzen und mindestens einen Reviewpfad für sicherheitskritische Schreib-/Registeränderungen definieren.
- [ ] Dependabot oder Renovate für Python und GitHub Actions aktivieren.
- [ ] CodeQL und `pip-audit`/OSV-Scan ergänzen; Ergebnisse als Pflichtcheck behandeln.
- [ ] Drittanbieter-Actions auf vollständige Commit-SHAs pinnen und planmäßig aktualisieren.
- [ ] Minimale Workflow-Berechtigungen und geschützte PyPI-/Release-Environments verwenden.
- [ ] Automatisches Löschen gemergter Branches und Auto-Merge für grüne Dependency-PRs erwägen.

### Gemeinsamer Releaseprozess

- [ ] Release-Reihenfolge festschreiben: API ändern -> API-CI/Vertragstests -> API-Release -> HASS-Pin-PR -> HASS-CI/Smoke-Test -> HASS-Release.
- [ ] Release-Workflow soll vor Tag/Upload alle Tests, Format-, Typ-, Build- und Artefaktprüfungen erzwingen.
- [ ] Tag und Paketversion vor Veröffentlichung auf Gleichheit prüfen; keine still tolerierten `git commit || true` / `git tag || true`-Fehler.
- [ ] Vorabkanal für Beta-/RC-Releases und echte Gerätekandidaten nutzen.
- [ ] Rollback-Anleitung für fehlerhafte PyPI- und HACS-Releases dokumentieren.
- [ ] Changelog aus kuratierten Einträgen erzeugen; Breaking Changes und Migrationsschritte dürfen nicht nur aus Commit-Schlagwörtern geraten werden.
- [ ] HASS-Release-Artefakt nach dem Packen entzippen, Manifest/Abhängigkeiten prüfen und importieren.

### Community und Wartung

- [ ] Issue-Templates beider Repositories angleichen und Modell, Firmware, Versionen, Diagnose sowie Reproduktionsschritte abfragen.
- [ ] Feature-Request-, Registerfehler- und Hardware-Kompatibilitäts-Templates ergänzen.
- [ ] Support-, Security- und Release-SLA realistisch dokumentieren.
- [ ] Roadmap quartalsweise prüfen; erledigte Punkte in Changelog/Issues verlinken statt historische Details zu löschen.
- [ ] Bus-Faktor senken: Architekturentscheidungen, Releasezugänge und Notfallabläufe dokumentieren; keine Secrets im Repository.

Abschlusskriterium: Kein Produktionsrelease umgeht Pflichtchecks, und ein neuer Maintainer kann Test, Release und Rollback ausschließlich anhand der Dokumentation durchführen.

## Nachgelagerter Backlog

Diese Punkte sind sinnvoll, aber erst nach Stabilität und Verträgen:

- Maschinenlesbares Registerschema mit Generatoren für Python, Dokumentation und HA-Metadaten.
- Kleine API-CLI für Verbindungstest, Modellerkennung und redigierten Diagnoseexport.
- Performance-Benchmarks für große Registermaps, viele Zonen und langsame Modbus-Gateways.
- Adaptive Batch-Grenzen nur dann, wenn Messungen einen Vorteil zeigen; Standard bleibt konservativ.
- Eigene HA-Events oder Event-Entities für neue Störungen, falls sie gegenüber Zustandsänderungen einen klaren Mehrwert haben.
- Reparatur-Assistent für falsche Modell-/Fähigkeitserkennung mit sicherem manuellen Override.
- Weitere Sprachen nach Community-Nachfrage; Deutsch und Englisch bleiben vollständig verpflichtend.

## Vorgeschlagene erste GitHub-Issues

| Reihenfolge | Repository | Titel | Priorität |
|---:|---|---|---|
| 1 | HASS | Pin idm-heatpump-api 0.3.7 and add release dependency smoke test | P0 |
| 2 | HASS | Verify v0.7.3 on Terra SWM / Navigator 2 and close #44 | P0 |
| 3 | HASS | Stabilize GitHub Pages deployment after queued timeout | P0 |
| 4 | API | Enforce Ruff formatting in CI | P0 |
| 5 | beide | Add cross-repository API contract test | P1 |
| 6 | API | Test Python 3.14 and publish typed package metadata | P1 |
| 7 | API | Add Modbus fault simulator and coverage gate | P1 |
| 8 | HASS | Split and reduce library_adapter responsibilities | P1 |
| 9 | beide | Protect main and require CI before merge | P1 |
| 10 | beide | Define coordinated API-to-HASS release policy | P1 |
| 11 | HASS | Replace self-claimed quality status with Core-readiness checklist | P2 |
| 12 | beide | Generate shared register reference and compatibility matrix | P2 |

## Messgrößen

- Null bekannte P0-Fehler in der neuesten stabilen Kombination.
- 100 % der Releases durch Pflichtchecks und Smoke-Test.
- 100 % der öffentlich unterstützten Python-/HA-Kombinationen in CI.
- Jede Registeränderung hat Quelle, Modell-Gate und Test.
- Keine ungeprüfte Breaking Change zwischen API und Integration.
- Sinkende Adapter-Komplexität statt weiterer Sonderfälle in einer Datei.
- Bestätigte Hardwarematrix für alle als „supported“ bezeichneten Modelle.
- Dokumentation, Manifest und veröffentlichte Releases nennen dieselben Mindestversionen und denselben Projektstatus.

## Pflege dieser Roadmap

- Aufgaben werden über GitHub-Issues umgesetzt; die Roadmap ersetzt kein Issue-Tracking.
- Jeder Issue-Link wird beim Start neben den zugehörigen Punkt gesetzt.
- Erledigte Punkte erhalten Release-/PR-Link und Datum.
- Prioritäten dürfen nach Sicherheitsfehlern, realen Gerätedaten oder Änderungen in Home Assistant angepasst werden.
- Neue Features kommen erst vor P0/P1-Arbeit, wenn sie einen akuten Sicherheits- oder Kompatibilitätsfehler lösen.
