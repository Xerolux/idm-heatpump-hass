# Coding Conventions

**Analysis Date:** 2026-07-25

## Naming Patterns

**Files:**
- Use lowercase `snake_case.py` module names, matching the feature or Home Assistant platform: `custom_components/idm_heatpump/room_temp_forwarding.py`, `custom_components/idm_heatpump/water_heater.py`.
- Keep platform entry points named after the Home Assistant platform (`sensor.py`, `binary_sensor.py`, `climate.py`); put substantial supporting logic in a focused peer module such as `operation_analysis.py` or `binary_semantics.py`.
- Name tests `tests/test_<module-or-contract>.py`; mirror production modules where practical, as in `custom_components/idm_heatpump/coordinator.py` and `tests/test_coordinator.py`.

**Functions:**
- Use `snake_case`; prefix coroutine entry points and I/O methods with `async_`, for example `async_setup_services()` in `custom_components/idm_heatpump/services.py`.
- Prefix module-private helpers with `_`, such as `_encoded_registers_from_safety_result()` in `custom_components/idm_heatpump/services.py`.
- Use behavior-oriented predicates (`should_add_entity`, `navigator_family`) rather than generic handler names; predicates should return explicit `bool` or optional classifications.

**Variables:**
- Use descriptive `snake_case` for locals and attributes; private instance state uses `_leading_underscore`, as in `IdmCoordinator._unused_registers` in `custom_components/idm_heatpump/coordinator.py`.
- Constants use `UPPER_SNAKE_CASE`; type stable constants may be annotated with `Final`, as in `_MAX_COMPLETED_CYCLES` in `custom_components/idm_heatpump/operation_analysis.py`.
- Logger instances are module-level `_LOGGER = logging.getLogger(__name__)`.

**Types:**
- Classes and enums use `PascalCase`, such as `IdmCoordinator`, `OperationAnalysis`, and `IdmEntity`.
- Type all new function parameters and return values. Use modern Python syntax (`str | None`, `list[str]`, `dict[str, Any]`) as shown in `custom_components/idm_heatpump/entity.py`.
- Use protocol-relevant concrete library types (`RegisterDef`, `IdmModelInfo`) rather than untyped mappings when the API provides them.

## Code Style

**Formatting:**
- Use Ruff formatting with a 120-character line length configured in `ruff.toml`.
- Run `ruff format custom_components/idm_heatpump tests`; CI verifies formatting in `.github/workflows/python-quality.yml`.
- Put `from __future__ import annotations` immediately after the module docstring in new production and test modules; current examples include `custom_components/idm_heatpump/coordinator.py` and `tests/test_operation_analysis.py`.
- Prefer trailing commas and parenthesized multiline calls, imports, and collections; let Ruff decide wrapping.

**Linting:**
- Run `ruff check custom_components/idm_heatpump tests`; CI adds `--line-length=120 --output-format=github` in `.github/workflows/python-quality.yml`.
- `ruff.toml` only sets line length, so Ruff's default lint selection applies. Avoid unused imports, undefined names, and structurally invalid Python.
- Run `mypy custom_components/idm_heatpump`; `mypy.ini` enables strict mode while allowing incomplete external Home Assistant/library stubs through targeted relaxations.
- Keep narrow `# type: ignore[code]` comments only at external typing boundaries, with the code specified, as in `custom_components/idm_heatpump/entity.py`.

## Import Organization

**Order:**
1. `from __future__ import annotations`.
2. Python standard library imports (`logging`, `collections.abc`, `datetime`, `typing`).
3. Home Assistant, `idm_heatpump`, `pymodbus`, and other third-party imports.
4. Relative imports from `custom_components.idm_heatpump`.

**Path Aliases:**
- No custom path aliases are used. Production code uses explicit relative package imports such as `from .const import DOMAIN`.
- Tests import through the installed-style package path `custom_components.idm_heatpump...`; `pythonpath = .` in `pytest.ini` makes the repository root importable.
- Put type-only imports behind `if TYPE_CHECKING:` when they would otherwise create runtime cycles, as demonstrated for `OperationAnalysis` in `custom_components/idm_heatpump/coordinator.py`.

## Error Handling

**Patterns:**
- Convert user-correctable failures into Home Assistant exceptions with translation metadata. `custom_components/idm_heatpump/services.py` raises `ServiceValidationError` for invalid selection and `HomeAssistantError` for write failures.
- Preserve exception causality with `raise ... from err`; centralized classifiers in `custom_components/idm_heatpump/error_messages.py` select actionable translation keys.
- Catch `Exception`, not `BaseException`, at integration boundaries where external I/O errors must be normalized. Do not silently discard failures.
- For recoverable persisted state, log a warning with `exc_info=True` and return a safe baseline, as in `OperationAnalysis.async_load()` in `custom_components/idm_heatpump/operation_analysis.py`.
- Validate external or persisted data defensively with `isinstance`, bounded conversion, and `None` fallbacks before updating state.

## Logging

**Framework:** Python `logging`.

**Patterns:**
- Define one `_LOGGER` per module using `logging.getLogger(__name__)`.
- Log an actionable summary at warning/error level and keep technical tracebacks at debug level when Home Assistant will separately show a translated user-facing error; see `IdmEntity._async_write_register()` in `custom_components/idm_heatpump/entity.py`.
- Do not log credentials, web PINs, or raw secret-bearing configuration. Include stable register names or issue classifications when they aid diagnosis.
- Avoid noisy routine transport errors; `custom_components/idm_heatpump/log_filter.py` owns filtering rather than scattering suppression across call sites.

## Comments

**When to Comment:**
- Use comments to explain protocol quirks, performance decisions, or Home Assistant lifecycle constraints, not to restate syntax. Examples appear around room-mode validation and persistent web pooling in `custom_components/idm_heatpump/coordinator.py`.
- Document intentional private-state setup in tests when it reproduces production-derived caches, as in `_make_coordinator()` in `tests/test_coordinator.py`.
- Keep compatibility comments adjacent to the exception or type-ignore they justify.

**JSDoc/TSDoc:**
- Not applicable; this is Python. Use concise PEP 257 docstrings for public modules, classes, properties, and functions.
- Start docstrings with an imperative or “Return whether/Return…” summary, as in `build_entity_unique_id()` and `should_add_entity()` in `custom_components/idm_heatpump/entity.py`.

## Function Design

**Size:** Keep parsing, classification, and transformation helpers small and pure. Split lifecycle or transport orchestration into private helpers rather than extending already large modules such as `custom_components/idm_heatpump/coordinator.py`.

**Parameters:** Use keyword-only parameters for optional behavioral controls (`allow_custom_register`, `short_cycle_minutes`) and explicit defaults. Pass typed domain objects instead of parallel primitive values where available.

**Return Values:** Return precise optional types for absent data and concrete collections for normalized data. Avoid sentinel objects when `None` communicates absence; use project constants only for protocol-level sentinel values from `custom_components/idm_heatpump/const.py`.

## Module Design

**Exports:** Public integration hooks use Home Assistant's expected names (`async_setup_entry`, `async_setup_services`). Internal helpers and constants are underscore-prefixed; direct test imports of private helpers are acceptable for focused classification logic.

**Barrel Files:** No general barrel modules are used. `custom_components/idm_heatpump/__init__.py` owns integration lifecycle rather than re-exporting all package symbols. Import implementations from their defining module.

---

*Convention analysis: 2026-07-25*
