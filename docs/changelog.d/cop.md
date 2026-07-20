## Momentaner COP (Coefficient of Performance)

### Added

- Berechneter **COP** als dimensionsloser Sensor, der das Verhältnis aus
  thermischer Abgabeleistung (`thermal_power_flow_sensor`) und elektrischer
  Aufnahmeleistung (`power_consumption_hp`) bildet.
- Der Sensor folgt der Roadmap-Regel aus Issue #135 (**keine Schätzwerte als
  Messwerte**): Er liefert `unavailable`, solange eine der Quellen fehlt,
  nicht endlich, `0` oder unterhalb der 50-W-Schwelle für sinnvollen Betrieb
  ist. Im Sommer-/Standby-Betrieb bleibt er damit erwartungsgemäß ohne Wert
  statt einer `0/0`-Schätzung.
- Die COP-Quellregister wurden gegen eine reale Navigator 10
  (`192.168.178.103`) verifiziert: `power_consumption_hp` (4122) und
  `thermal_power_flow_sensor` (4126) sind implementiert und liefern plausible
  Werte; im aktuellen Idle-Betrieb melden beide konstant 0 kW.
- Erweitert `CalculatedSensorDefinition` um optionale Einheit und Geräteklassse,
  sodass neben Temperatur-Sensoren auch dimensionslose Verhältnisse wie COP
  abgebildet werden können.
