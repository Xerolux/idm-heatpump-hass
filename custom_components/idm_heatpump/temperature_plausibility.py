"""Re-export of the API's uninitialized-temperature band.

The rule is register knowledge and lives in the API library since 2.16.1
(``idm_heatpump.plausibility``): a temperature input whose sensor is not
wired answers with uninitialized controller memory instead of a documented
sentinel — observed as -327.33 °C and -327.22 °C on Navigator 2.0 register
1364 (issues #504 and #668). This module keeps one integration-side import
seam so every consumer shares the library's evidence-backed rule instead of
re-deriving it.
"""

from __future__ import annotations

from idm_heatpump.plausibility import UNINITIALIZED_TEMPERATURE_C, is_uninitialized_temperature

__all__ = ["UNINITIALIZED_TEMPERATURE_C", "is_uninitialized_temperature"]
