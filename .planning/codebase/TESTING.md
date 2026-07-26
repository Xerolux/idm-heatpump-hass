# Testing Patterns

**Analysis Date:** 2026-07-25

## Test Framework

**Runner:**
- pytest, installed by `.github/workflows/python-quality.yml`
- Config: `pytest.ini`
- Async support: `pytest-asyncio` with `asyncio_mode = auto` and function-scoped event loops.

**Assertion Library:**
- Native Python `assert` statements plus pytest helpers such as `pytest.raises` and `pytest.mark.parametrize`.
- `unittest.mock` supplies `MagicMock`, `AsyncMock`, and `patch`.

**Run Commands:**
```bash
pytest tests/                          # Run all tests
pytest tests/test_coordinator.py -q   # Run one module during development
pytest tests/ -v --tb=short --cov=custom_components/idm_heatpump --cov-report=term-missing  # CI-style coverage
```

## Test File Organization

**Location:**
- Tests live in the separate top-level `tests/` directory.
- Mirror a production module with `tests/test_<module>.py`, for example `custom_components/idm_heatpump/web_data.py` → `tests/test_web_data.py`.
- Use dedicated contract suites for repository/release invariants: `tests/test_cross_repo_contract.py`, `tests/test_release_contract.py`, and `tests/test_entity_metadata_catalog.py`.

**Naming:**
- Test functions use `test_<expected_behavior>`, such as `test_observed_off_to_on_edge_counts_one_start` in `tests/test_operation_analysis.py`.
- Group related cases in `Test<Subject>` classes without defining `__init__`, as in `TestCoordinatorInit` in `tests/test_coordinator.py`.
- Name local factories `_make_<subject>`, `_coordinator`, or `_analysis`; keep them in the test module when they are feature-specific.

**Structure:**
```text
tests/
├── conftest.py
├── test_<production_module>.py
├── test_platforms.py
├── test_platforms_climate.py
└── test_<cross-cutting-contract>.py
```

## Test Structure

**Suite Organization:**
```python
class TestSetupServices:
    async def test_registers_services(self, mock_hass):
        await async_setup_services(mock_hass)
        assert mock_hass.services.async_register.call_count == 4
```
This pattern is taken from `tests/test_services.py`; async tests run directly because `pytest.ini` enables automatic asyncio mode.

**Patterns:**
- Arrange test objects through shared fixtures or a local factory, perform one behavior, then assert observable state and mock interactions.
- Use explicit, fixed timestamps for time-sensitive logic. `tests/test_operation_analysis.py` uses timezone-aware `datetime(..., tzinfo=UTC)` values.
- Assert both returned state and side effects (`assert_called_once_with`, stored snapshots, registered services) when orchestration is the behavior.
- Prefer multiple narrow tests for edge transitions, invalid persisted data, and recovery paths over a single long scenario.
- Parameterize classification matrices with `@pytest.mark.parametrize`, as in `tests/test_error_messages.py`.

## Mocking

**Framework:** `unittest.mock` and pytest `monkeypatch`.

**Patterns:**
```python
client = MagicMock()
client.read_batch = AsyncMock(return_value={})
client.write_register = AsyncMock()

with pytest.raises(ServiceValidationError):
    await _get_coordinator(mock_hass, call)
```
The client pattern appears in `tests/test_coordinator.py`; exception assertions appear in `tests/test_services.py`.

**What to Mock:**
- Mock Home Assistant lifecycle objects, registries, services, and config entries through `mock_hass` and `mock_config_entry` from `tests/conftest.py`.
- Use `AsyncMock` for awaited I/O methods and `MagicMock` for synchronous collaborators.
- Patch symbols where the code under test looks them up, for example `custom_components.idm_heatpump.coordinator.collect_all_registers` in `tests/test_coordinator.py`.
- Use small behavior fakes when stateful semantics matter more than call recording. `FakeStore` in `tests/test_operation_analysis.py` models load, save, and delayed-save behavior.
- Use `monkeypatch` for module globals/factories and `patch` context managers for short-lived call-site replacements.

**What NOT to Mock:**
- Do not mock pure classifiers, parsing helpers, state-transition logic, or entity metadata being asserted; pass realistic values and exercise them directly.
- Do not mock the method under test. Mock transport/storage/HA boundaries and verify the integration's own transformation and error handling.
- Do not require a live heat pump, network socket, or real Home Assistant installation in the default unit suite.

## Fixtures and Factories

**Test Data:**
```python
@pytest.fixture
def mock_config_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {"host": "192.168.1.100", "port": 502, "slave_id": 1, "name": "IDM Test"}
    entry.options = {"scan_interval": 10, "heating_circuits": ["a"], "zone_count": 0}
    return entry
```
The full shared fixture, including runtime state, is defined in `tests/conftest.py`.

**Location:**
- Put reusable Home Assistant and Modbus fixtures in `tests/conftest.py`.
- Keep feature-specific fake stores, fake clients, snapshot builders, and register factories beside the tests that consume them, for example `tests/test_dhw_boost.py` and `tests/test_operation_analysis.py`.
- `tests/conftest.py` stubs `homeassistant`, `pymodbus`, `voluptuous`, and `idm_heatpump` package trees before importing integration modules; extend these stubs when new production imports require missing API surface.

## Coverage

**Requirements:** CI collects XML and terminal coverage for `custom_components/idm_heatpump`, but no numeric minimum or `--cov-fail-under` threshold is configured in `.github/workflows/python-quality.yml`.

**View Coverage:**
```bash
pytest tests/ --cov=custom_components/idm_heatpump --cov-report=term-missing
```

- Treat uncovered error branches and lifecycle cleanup as required test targets even though CI has no enforced percentage.
- Add a test in the corresponding module suite for every bug fix; add contract coverage when changing manifest versions, library pins, translations, entity metadata, or release artifacts.

## Test Types

**Unit Tests:**
- Dominant test type. Pure transformations, entity properties, state machines, config schemas, and error classification are tested with direct calls.
- Representative files: `tests/test_binary_semantics.py`, `tests/test_operation_analysis.py`, `tests/test_error_messages.py`.

**Integration Tests:**
- Lightweight in-process integration tests exercise integration modules together against the stubbed Home Assistant and API package trees.
- Platform and lifecycle coverage lives in `tests/test_init.py`, `tests/test_platforms.py`, `tests/test_platforms_climate.py`, and `tests/test_services.py`.
- Repository contract tests inspect checked-in metadata and dependency compatibility in `tests/test_cross_repo_contract.py` and `tests/test_release_contract.py`.

**E2E Tests:**
- Not used in the pytest suite. `docker/` contains manual/container test helpers, but CI's primary quality workflow runs stub-based tests from `tests/`.
- Do not introduce network-dependent E2E behavior into the default test command; isolate hardware/manual verification and document it under `docs/`.

## Common Patterns

**Async Testing:**
```python
async def test_start_persists_snapshot_before_first_write(monkeypatch) -> None:
    manager, coordinator, store = await _manager(monkeypatch)
    await manager.async_start(target_temperature=55.0, duration_minutes=30)
    assert store.saved is not None
```
Follow the async style used in `tests/test_dhw_boost.py`; explicit `@pytest.mark.asyncio` is also present and valid, but automatic mode means it is not required.

**Error Testing:**
```python
with pytest.raises(DhwBoostError, match="Zieltemperatur"):
    await manager.async_start(target_temperature=invalid_value, duration_minutes=30)
```
Assert the exception type and stable message/translation contract, then verify rollback or repair side effects when applicable, as in `tests/test_dhw_boost.py` and `tests/test_services.py`.

**Logging Testing:**
- Use pytest's `caplog` for log behavior when the log record is the contract; otherwise assert the resulting HA exception or repair issue instead of implementation-level log text.

**Regression Testing:**
- Reproduce protocol edge cases with explicit register definitions and values, including unsupported addresses, unused sentinels, binary encodings, and reconnect behavior.
- Keep release and cross-repository compatibility assertions separate from runtime unit tests so failures identify metadata drift clearly.

---

*Testing analysis: 2026-07-25*
