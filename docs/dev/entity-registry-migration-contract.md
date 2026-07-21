# Entity Registry Migration Contract

Stand: 21.07.2026

Dieses Dokument beschreibt den verbindlichen Schutzrahmen für zukünftige
Entity-Profil-, Default- und Gerätehierarchie-Änderungen.

## Ziel

Neue Integrationsversionen dürfen bessere Defaults für neue Installationen
setzen, aber bestehende Nutzerentscheidungen in Home Assistant nicht
überschreiben. Das betrifft insbesondere manuell aktivierte, deaktivierte,
umbenannte oder in Dashboards verwendete Entities.

## Harte Regeln

1. **Unique IDs bleiben stabil.** Register-backed Entities verwenden weiterhin
   `{entry_id}_{register_name}`. GLT-Messwert-Numbers behalten ihr bewusstes
   `_set`-Suffix, um Kollisionen mit Sensoren zu vermeiden.
2. **Default-Profile sind nur Defaults.** Änderungen an
   `entity_registry_enabled_default` gelten nur für neue Entity-Registry-Einträge
   oder für Entities, die Home Assistant noch nicht registriert hat.
3. **Keine nachträgliche Zwangsdeaktivierung.** Eine Migration darf bestehende
   Entity-Registry-Einträge nicht deaktivieren, nur weil sich das Default-Profil
   geändert hat.
4. **Keine nachträgliche Zwangsaktivierung.** Eine Migration darf vom Nutzer
   deaktivierte Entities nicht wieder aktivieren.
5. **Subdevices ändern keine Unique IDs.** Gerätehierarchie darf `device_info`
   verschieben, aber nicht die Entity-Identität ändern.
6. **Breaking Changes brauchen Migration.** Wenn ein Entity-Key wirklich ersetzt
   werden muss, braucht es eine explizite Entity-Registry-Migration mit Tests und
   Changelog-Hinweis.

## Erlaubt

- Neue generierte Expertenwerte standardmäßig deaktivieren.
- Bestehende explizite Metadaten besser klassifizieren.
- `entity_category`, Icon, Name oder Device Class verbessern, solange Unique ID
  und Nutzeraktivierung erhalten bleiben.
- Neue Diagnose-/Support-Dokumentation ergänzen.

## Nicht erlaubt

- Bestehende Unique IDs ohne Migration ändern.
- Bestehende Entity-Registry-Einträge wegen neuer Defaults entfernen.
- Nutzeraktivierungen anhand des neuen Profils überschreiben.
- Gerätehierarchie als Vorwand für neue Entity-IDs nutzen.

## Prüfhinweise für PRs

- Neue Default-Disabled-Regeln müssen Tests für aktivierte Kernwerte und
  deaktivierte Expertenwerte enthalten.
- Änderungen an `build_entity_unique_id`, GLT-`_set`-Suffixen oder Climate-/DHW-
  Unique IDs brauchen fokussierte Regressionstests.
- Doku-Generatoren dürfen Profile dokumentieren, aber keine Runtime-Migrationen
  auslösen.
