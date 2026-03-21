"""Shared fixtures and HA mocks for IDM Heatpump tests."""

import asyncio
import sys
from enum import Enum
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Cross-platform event loop setup (Windows uses SelectorEventLoop; Linux is fine)
# ---------------------------------------------------------------------------
try:
    _LOOP_POLICY = asyncio.WindowsSelectorEventLoopPolicy()
    asyncio.set_event_loop_policy(_LOOP_POLICY)

    # Stub homeassistant.runner to prevent HassEventLoopPolicy from overriding ours
    _runner_mod = ModuleType("homeassistant.runner")
    _runner_mod.HassEventLoopPolicy = type(
        "HassEventLoopPolicy", (asyncio.WindowsSelectorEventLoopPolicy,), {}
    )
    sys.modules["homeassistant.runner"] = _runner_mod

    @pytest.fixture(scope="session")
    def event_loop_policy():
        return _LOOP_POLICY

except AttributeError:
    # Not on Windows – no special policy needed
    pass


# ---------------------------------------------------------------------------
# Stub pymodbus so tests run without the real package installed
# ---------------------------------------------------------------------------

def _stub_pymodbus() -> None:
    if "pymodbus" in sys.modules:
        return

    pymodbus = ModuleType("pymodbus")
    sys.modules["pymodbus"] = pymodbus

    # pymodbus.client
    client_mod = ModuleType("pymodbus.client")
    sys.modules["pymodbus.client"] = client_mod
    pymodbus.client = client_mod

    class _AsyncModbusTcpClient:
        def __init__(self, host="", port=502, timeout=10):
            self.connected = False

        async def connect(self):
            self.connected = True

        def close(self):
            self.connected = False

        async def read_input_registers(self, address, count, **kwargs):
            raise NotImplementedError("use mock in tests")

        async def write_registers(self, address, values, **kwargs):
            raise NotImplementedError("use mock in tests")

    client_mod.AsyncModbusTcpClient = _AsyncModbusTcpClient

    # pymodbus.client.mixin
    mixin_mod = ModuleType("pymodbus.client.mixin")
    sys.modules["pymodbus.client.mixin"] = mixin_mod
    client_mod.mixin = mixin_mod

    class _ModbusClientMixin:
        @staticmethod
        def read_input_registers(address, count, slave=1):
            pass

    mixin_mod.ModbusClientMixin = _ModbusClientMixin

    # pymodbus.exceptions
    exceptions_mod = ModuleType("pymodbus.exceptions")
    sys.modules["pymodbus.exceptions"] = exceptions_mod
    pymodbus.exceptions = exceptions_mod

    class _ModbusException(Exception):
        pass

    class _ConnectionException(_ModbusException):
        pass

    exceptions_mod.ModbusException = _ModbusException
    exceptions_mod.ConnectionException = _ConnectionException


_stub_pymodbus()


# ---------------------------------------------------------------------------
# Stub voluptuous
# ---------------------------------------------------------------------------

def _stub_voluptuous() -> None:
    if "voluptuous" in sys.modules:
        return

    vol = ModuleType("voluptuous")
    sys.modules["voluptuous"] = vol

    def _schema_factory(schema):
        return schema

    class _Required:
        def __init__(self, key, default=None):
            self.key = key
            self.default = default

        def __hash__(self):
            return hash(self.key)

        def __eq__(self, other):
            if isinstance(other, _Required):
                return self.key == other.key
            return self.key == other

    class _Optional:
        def __init__(self, key, default=None):
            self.key = key
            self.default = default

        def __hash__(self):
            return hash(self.key)

        def __eq__(self, other):
            if isinstance(other, _Optional):
                return self.key == other.key
            return self.key == other

    class _Schema:
        def __init__(self, schema):
            self._schema = schema

        def __call__(self, data):
            return data

        def extend(self, schema):
            combined = {**self._schema, **schema}
            return _Schema(combined)

    vol.Schema = _Schema
    vol.Required = _Required
    vol.Optional = _Optional
    vol.All = lambda *a, **kw: a[0] if a else None
    vol.Coerce = lambda t: t
    vol.In = lambda values: values
    vol.Range = lambda **kw: None
    vol.Invalid = type("Invalid", (Exception,), {})


_stub_voluptuous()


# ---------------------------------------------------------------------------
# Stub out the entire homeassistant package tree so tests run without HA
# ---------------------------------------------------------------------------

def _make_module(name: str) -> ModuleType:
    mod = ModuleType(name)
    sys.modules[name] = mod
    return mod


def _stub_homeassistant() -> None:
    if "homeassistant" in sys.modules:
        return

    # Top-level
    ha = _make_module("homeassistant")
    ha.config_entries = _make_module("homeassistant.config_entries")
    ha.const = _make_module("homeassistant.const")
    ha.core = _make_module("homeassistant.core")
    ha.exceptions = _make_module("homeassistant.exceptions")
    ha.loader = _make_module("homeassistant.loader")

    # homeassistant.const values used in the integration
    ha.const.CONF_HOST = "host"
    ha.const.CONF_PORT = "port"
    ha.const.CONF_NAME = "name"
    ha.const.Platform = MagicMock()
    ha.const.PERCENTAGE = "%"

    class _UnitOfTemperature:
        CELSIUS = "°C"
        FAHRENHEIT = "°F"

    class _UnitOfPower:
        KILO_WATT = "kW"
        WATT = "W"

    class _UnitOfEnergy:
        KILO_WATT_HOUR = "kWh"

    units = sys.modules["homeassistant.const"]
    units.CONF_HOST = "host"
    units.CONF_PORT = "port"
    units.CONF_NAME = "name"
    units.Platform = MagicMock()
    units.PERCENTAGE = "%"
    units.UnitOfTemperature = _UnitOfTemperature
    units.UnitOfPower = _UnitOfPower
    units.UnitOfEnergy = _UnitOfEnergy

    # homeassistant.core
    ha.core.HomeAssistant = MagicMock
    ha.core.callback = lambda f: f
    ha.core.ServiceCall = MagicMock
    ha.core.ServiceResponse = MagicMock
    ha.core.SupportsResponse = MagicMock()
    ha.core.SupportsResponse.OPTIONAL = "optional"

    # homeassistant.exceptions
    class _HomeAssistantError(Exception):
        def __init__(self, *args, translation_domain=None, translation_key=None,
                     translation_placeholders=None, **kwargs):
            super().__init__(*args)
            self.translation_domain = translation_domain
            self.translation_key = translation_key
            self.translation_placeholders = translation_placeholders or {}

    class _ServiceValidationError(_HomeAssistantError):
        pass

    class _ConfigEntryNotReady(Exception):
        pass

    ha.exceptions.HomeAssistantError = _HomeAssistantError
    ha.exceptions.ServiceValidationError = _ServiceValidationError
    ha.exceptions.ConfigEntryNotReady = _ConfigEntryNotReady
    sys.modules["homeassistant.exceptions"] = ha.exceptions

    # homeassistant.config_entries
    class _ConfigEntryState(Enum):
        LOADED = "loaded"
        NOT_LOADED = "not_loaded"
        SETUP_ERROR = "setup_error"
        MIGRATION_ERROR = "migration_error"
        SETUP_RETRY = "setup_retry"
        FAILED_UNLOAD = "failed_unload"

    class _ConfigEntry:
        def __init__(self):
            self.entry_id = "test_entry_id"
            self.data = {}
            self.options = {}
            self.title = "Test IDM"
            self.runtime_data = None
            self.state = _ConfigEntryState.LOADED

        def __class_getitem__(cls, item):
            return cls

        def as_dict(self):
            return {"data": self.data, "options": self.options}

        def add_update_listener(self, *a, **kw):
            return lambda: None

        def async_on_unload(self, *a, **kw):
            pass

    class _ConfigFlow:
        VERSION = 1
        MINOR_VERSION = 1

        def __init_subclass__(cls, domain=None, **kwargs):
            super().__init_subclass__(**kwargs)
            if domain:
                cls.DOMAIN = domain

        def __init__(self):
            self._data = {}
            self._options = {}
            self.hass = None

        def async_show_form(self, *, step_id, data_schema=None, errors=None,
                            description_placeholders=None):
            return {"type": "form", "step_id": step_id, "errors": errors or {}}

        def async_create_entry(self, title="", data=None, options=None):
            return {"type": "create_entry", "title": title,
                    "data": data or {}, "options": options or {}}

        def async_abort(self, reason):
            return {"type": "abort", "reason": reason}

        def async_update_reload_and_abort(self, entry, data_updates=None, **kwargs):
            return {"type": "abort", "reason": "reconfigure_successful"}

        async def async_set_unique_id(self, unique_id):
            pass

        def _abort_if_unique_id_configured(self):
            pass

        def _get_reconfigure_entry(self):
            return MagicMock()

        def add_suggested_values_to_schema(self, schema, suggested_values):
            return schema

        @staticmethod
        def async_get_options_flow(config_entry):
            return MagicMock()

    class _OptionsFlow:
        def __init__(self):
            self._options = {}
            self.config_entry = MagicMock()

        def async_show_form(self, *, step_id, data_schema=None, errors=None,
                            description_placeholders=None):
            return {"type": "form", "step_id": step_id, "errors": errors or {}}

        def async_create_entry(self, data=None):
            return {"type": "create_entry", "data": data or {}}

    ha.config_entries.ConfigEntry = _ConfigEntry
    ha.config_entries.ConfigFlow = _ConfigFlow
    ha.config_entries.OptionsFlow = _OptionsFlow
    ha.config_entries.ConfigEntryState = _ConfigEntryState
    sys.modules["homeassistant.config_entries"] = ha.config_entries

    # homeassistant.helpers
    helpers = _make_module("homeassistant.helpers")

    # homeassistant.helpers.update_coordinator
    update_coordinator_mod = _make_module("homeassistant.helpers.update_coordinator")
    helpers.update_coordinator = update_coordinator_mod

    class _DataUpdateCoordinator:
        def __init__(self, hass, logger, *, config_entry=None, name="", update_interval=None):
            self.hass = hass
            self.name = name
            self.update_interval = update_interval
            self.config_entry = config_entry
            self.data = None
            self.last_update_success = True
            self._listeners = []

        def __class_getitem__(cls, item):
            return cls

        def async_update_listeners(self):
            pass

        async def async_config_entry_first_refresh(self):
            pass

        async def async_request_refresh(self):
            pass

    class _CoordinatorEntity:
        _attr_has_entity_name = False

        def __init__(self, coordinator):
            self.coordinator = coordinator
            self._attr_unique_id = None
            self._attr_device_info = None

        def __class_getitem__(cls, item):
            return cls

        @property
        def available(self) -> bool:
            return self.coordinator.last_update_success

        async def async_added_to_hass(self) -> None:
            pass

        def async_write_ha_state(self):
            pass

    class _UpdateFailed(Exception):
        pass

    update_coordinator_mod.DataUpdateCoordinator = _DataUpdateCoordinator
    update_coordinator_mod.CoordinatorEntity = _CoordinatorEntity
    update_coordinator_mod.UpdateFailed = _UpdateFailed

    # homeassistant.helpers.selector
    selector_mod = _make_module("homeassistant.helpers.selector")
    helpers.selector = selector_mod
    for cls_name in [
        "BooleanSelector", "BooleanSelectorConfig",
        "NumberSelector", "NumberSelectorConfig", "NumberSelectorMode",
        "SelectSelector", "SelectSelectorConfig", "SelectSelectorMode",
        "TextSelector", "TextSelectorConfig", "TextSelectorType",
    ]:
        setattr(selector_mod, cls_name, MagicMock())

    # homeassistant.helpers.entity
    entity_mod = _make_module("homeassistant.helpers.entity")
    helpers.entity = entity_mod

    class _EntityCategory(Enum):
        CONFIG = "config"
        DIAGNOSTIC = "diagnostic"

    entity_mod.EntityCategory = _EntityCategory

    # homeassistant.helpers.device_registry
    device_registry_mod = _make_module("homeassistant.helpers.device_registry")
    helpers.device_registry = device_registry_mod

    class _DeviceInfo(dict):
        def __init__(self, identifiers=None, name=None, manufacturer=None, model=None,
                     sw_version=None, **kwargs):
            super().__init__(
                identifiers=identifiers or set(),
                name=name,
                manufacturer=manufacturer,
                model=model,
                **kwargs,
            )

    device_registry_mod.DeviceInfo = _DeviceInfo

    # homeassistant.helpers.issue_registry
    issue_registry_mod = _make_module("homeassistant.helpers.issue_registry")
    helpers.issue_registry = issue_registry_mod

    class _IssueSeverity(Enum):
        CRITICAL = "critical"
        ERROR = "error"
        WARNING = "warning"

    issue_registry_mod.IssueSeverity = _IssueSeverity
    issue_registry_mod.async_create_issue = MagicMock()
    issue_registry_mod.async_delete_issue = MagicMock()

    # homeassistant.helpers.entity_platform
    entity_platform_mod = _make_module("homeassistant.helpers.entity_platform")
    helpers.entity_platform = entity_platform_mod
    entity_platform_mod.AddEntitiesCallback = MagicMock

    # homeassistant.helpers.event
    event_mod = _make_module("homeassistant.helpers.event")
    helpers.event = event_mod
    event_mod.async_track_time_interval = MagicMock(return_value=MagicMock())

    # homeassistant.components stubs
    components = _make_module("homeassistant.components")

    for platform in ["sensor", "binary_sensor", "number", "select", "switch", "diagnostics"]:
        mod = _make_module(f"homeassistant.components.{platform}")

        class _FakeEntityDescription:
            def __init__(self, key="", name="", **kwargs):
                self.key = key
                self.name = name
                for k, v in kwargs.items():
                    setattr(self, k, v)

        mod.SensorEntityDescription = type(
            "SensorEntityDescription", (), {"__init__": _FakeEntityDescription.__init__}
        )
        mod.BinarySensorEntityDescription = type(
            "BinarySensorEntityDescription", (), {"__init__": _FakeEntityDescription.__init__}
        )
        mod.NumberEntityDescription = type(
            "NumberEntityDescription", (), {"__init__": _FakeEntityDescription.__init__}
        )
        mod.SelectEntityDescription = type(
            "SelectEntityDescription", (), {"__init__": _FakeEntityDescription.__init__}
        )
        mod.SwitchEntityDescription = type(
            "SwitchEntityDescription", (), {"__init__": _FakeEntityDescription.__init__}
        )

        # Device/state class enums
        mod.SensorDeviceClass = MagicMock()
        mod.SensorDeviceClass.TEMPERATURE = "temperature"
        mod.SensorDeviceClass.POWER = "power"
        mod.SensorDeviceClass.ENERGY = "energy"
        mod.SensorDeviceClass.HUMIDITY = "humidity"
        mod.SensorStateClass = MagicMock()
        mod.SensorStateClass.MEASUREMENT = "measurement"
        mod.SensorStateClass.TOTAL_INCREASING = "total_increasing"
        mod.BinarySensorDeviceClass = MagicMock()
        mod.NumberDeviceClass = MagicMock()
        mod.NumberMode = MagicMock()
        mod.NumberMode.BOX = "box"
        mod.NumberMode.SLIDER = "slider"

        # Entity base classes for each platform
        class _SensorEntity:
            pass

        class _BinarySensorEntity:
            pass

        class _NumberEntity:
            pass

        class _SelectEntity:
            pass

        class _SwitchEntity:
            pass

        mod.SensorEntity = _SensorEntity
        mod.BinarySensorEntity = _BinarySensorEntity
        mod.NumberEntity = _NumberEntity
        mod.SelectEntity = _SelectEntity
        mod.SwitchEntity = _SwitchEntity

        def _redact(data, keys):
            if not isinstance(data, dict):
                return data
            return {k: _redact(v, keys) for k, v in data.items() if k not in keys}
        mod.async_redact_data = _redact
        setattr(components, platform, mod)

    ha.loader.async_get_integration = AsyncMock(
        return_value=MagicMock(manifest={"version": "0.2.1"})
    )


_stub_homeassistant()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.data = {}
    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()
    hass.services.async_remove = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_reload = AsyncMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    return hass


@pytest.fixture
def mock_config_entry():
    from homeassistant.config_entries import ConfigEntryState

    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "host": "192.168.1.100",
        "port": 502,
        "slave_id": 1,
        "name": "IDM Test",
    }
    entry.options = {
        "scan_interval": 10,
        "heating_circuits": ["a"],
        "zone_count": 0,
        "zone_rooms": {},
        "hide_unused_registers": True,
    }
    entry.title = "IDM Test"
    entry.state = ConfigEntryState.LOADED
    entry.runtime_data = MagicMock()
    entry.add_update_listener = MagicMock(return_value=lambda: None)
    entry.async_on_unload = MagicMock()
    return entry


@pytest.fixture
def mock_modbus_client():
    with patch(
        "custom_components.idm_heatpump_v2.modbus_client.AsyncModbusTcpClient"
    ) as mock_class:
        mock_instance = AsyncMock()
        mock_instance.connected = True
        mock_instance.isError = MagicMock(return_value=False)
        mock_class.return_value = mock_instance

        from custom_components.idm_heatpump_v2.modbus_client import IdmModbusClient
        client = IdmModbusClient(host="192.168.1.100", port=502, slave_id=1)
        client._client = mock_instance
        yield client, mock_instance
