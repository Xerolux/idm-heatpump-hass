# Config Flow UX Roadmap

This roadmap records the usability work completed for the guided IDM setup. It
also serves as a regression checklist when future connection or entity options
are added.

## Completed

- [x] Default initial setup to full local Modbus and Navigator web access; require
  either a verified web PIN or an explicit choice to use Modbus only.
- [x] Keep proxy installations first-class by accepting a separate direct heat
  pump address for Navigator web access alongside the Modbus proxy address.
- [x] Show a post-detection summary containing the Modbus endpoint, slave ID,
  Navigator/software detection, and local web status.
- [x] Let users confirm automatic model detection or override the Navigator
  family directly on that post-detection summary.
- [x] Offer a one-click recommended setup, profiles for unreliable networks and
  multiple Modbus clients, and the complete custom path.
- [x] Group presentation/features, external room temperatures, and advanced
  Modbus controls into collapsed sections with safety-focused descriptions.
- [x] Keep dependent zone and external-temperature mapping in dedicated steps;
  remove stale mappings when a zone/circuit is removed or forwarding is off.
- [x] Mark installer-code, cascade, EEPROM, model, proxy, and connection tuning
  as advanced or safety-sensitive controls.
- [x] Preserve the resilient Modbus failure recovery and clearly describe the
  reduced entity/control surface of web-only mode.
- [x] Enrich read-only diagnostics with separate Modbus/web states, detected
  Navigator/software information, and elapsed time.
- [x] Keep English, German, and source strings synchronized and cover the new
  profile/review paths with unit tests.

## Design rules for future changes

1. A default installation must be completable without opening advanced fields.
2. Options that have no effect while their parent feature is disabled must say
   so explicitly or be collected in a subsequent conditional step.
3. Any option that exposes credentials or weakens write protection must be
   advanced and must explain its security or hardware impact.
4. Connection failures must provide an actionable cause and must never silently
   switch the entry into web-only mode.
5. New flow text must be added to `strings.json`, `translations/en.json`, and
   `translations/de.json` in the same change.
