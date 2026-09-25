# Mitwirken

Beiträge zu diesem Projekt sind willkommen!

## Wie du mitwirken kannst

- **Fehlerberichte**: [Issue erstellen](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- **Fragen & Hilfe**: [Q&A-Diskussion starten](https://github.com/Xerolux/idm-heatpump-hass/discussions/categories/q-a)
- **Funktionswünsche**: [Idee teilen](https://github.com/Xerolux/idm-heatpump-hass/discussions/categories/ideas)
- **Lovelace & Automationen**: [Projekt zeigen](https://github.com/Xerolux/idm-heatpump-hass/discussions/categories/show-and-tell)
- **Pull Requests**: Fork → Branch → Änderungen → PR
- **Dokumentation**: Wiki-Seiten verbessern oder neue hinzufügen
- **Übersetzungen**: Bei DE/EN-Übersetzungen helfen

## Entwicklungsumgebung einrichten

1. Forke das Repository
2. Klone den Fork lokal
3. Kopiere `custom_components/idm_heatpump/` in dein HA-Verzeichnis `custom_components/`
4. Aktiviere die Debug-Protokollierung
5. Starte HA neu

## Sprache

Das Projekt schreibt auf Englisch: Code, Kommentare, Dokumentation,
Changelog-Einträge, Commit-Messages und Beschreibungen von Pull Requests.
Deutsch gehört nur in `README_de.md` und in die `de`-Übersetzungen von Home
Assistant. Führe `python scripts/check_documentation_language.py` aus, bevor
du einen Pull Request öffnest — `tests/test_documentation_language.py` bringt
den Build zum Scheitern, wenn deutsche Prosa enthalten ist.

## Code-Stil

- Verwende [Ruff](https://docs.astral.sh/ruff/) zum Linten und Formatieren
- Folge bei Commit-Messages [Conventional Commits](https://www.conventionalcommits.org/)
- Halte den Code einfach und verständlich

## Pull-Request-Prozess

1. Erstelle einen Fork
2. Erstelle einen Feature-Branch (`git checkout -b feat/my-feature`)
3. Commite deine Änderungen (`git commit -m 'feat: add my feature'`)
4. Pushe in den Fork (`git push origin feat/my-feature`)
5. Erstelle einen Pull Request

## Lizenz

Mit deinem Beitrag stimmst du zu, dass dein Code unter der MIT-Lizenz veröffentlicht wird.
