"""Shared fixtures and HA mocks for IDM Heatpump tests."""

import asyncio
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# On Windows, use SelectorEventLoop so the event loop does not need real
# OS sockets internally (required by pytest-socket).
_LOOP_POLICY = asyncio.WindowsSelectorEventLoopPolicy()
asyncio.set_event_loop_policy(_LOOP_POLICY)

# Stub homeassistant.runner so the pytest-homeassistant-custom-component
# plugin cannot install HassEventLoopPolicy (which uses ProactorEventLoop).
_runner_mod = ModuleType("homeassistant.runner")
_runner_mod.HassEventLoopPolicy = type(
    "HassEventLoopPolicy", (asyncio.WindowsSelectorEventLoopPolicy,), {}
)
sys.modules["homeassistant.runner"] = _runner_mod


@pytest.fixture(scope="session")
def event_loop_policy():
    return _LOOP_POLICY


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

    units = _make_module("homeassistant.const")
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
        pass

    class _ConfigEntryNotReady(Exception):
        pass

    ha.exceptions.HomeAssistantError = _HomeAssistantError
    ha.exceptions.ConfigEntryNotReady = _ConfigEntryNotReady
    sys.modules["homeassistant.exceptions"] = ha.exceptions

    # homeassistant.config_entries
    class _ConfigEntry:
        def __init__(self):
            self.entry_id = "test_entry_id"
            self.data = {}
            self.options = {}
            self.title = "Test IDM"

        def as_dict(self):
            return {"data": self.data, "options": self.options}

        def add_update_listener(self, *a, **kw):
            return lambda: None

        def async_on_unload(self, *a, **kw):
            pass

    ha.config_entries.ConfigEntry = _ConfigEntry
    ha.config_entries.ConfigFlow = MagicMock
    ha.config_entries.OptionsFlow = MagicMock
    sys.modules["homeassistant.config_entries"] = ha.config_entries

    # homeassistant.helpers
    helpers = _make_module("homeassistant.helpers")
    helpers.update_coordinator = _make_module("homeassistant.helpers.update_coordinator")
    helpers.selector = _make_module("homeassistant.helpers.selector")

    class _DataUpdateCoordinator:
        def __init__(self, hass, logger, *, config_entry=None, name="", update_interval=None):
            self.hass = hass
            self.name = name
            self.update_interval = update_interval
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

    class _UpdateFailed(Exception):
        pass

    helpers.update_coordinator.DataUpdateCoordinator = _DataUpdateCoordinator
    helpers.update_coordinator.UpdateFailed = _UpdateFailed

    # Selector stubs
    for cls_name in [
        "BooleanSelector", "BooleanSelectorConfig",
        "NumberSelector", "NumberSelectorConfig", "NumberSelectorMode",
        "SelectSelector", "SelectSelectorConfig", "SelectSelectorMode",
        "TextSelector", "TextSelectorConfig", "TextSelectorType",
    ]:
        setattr(helpers.selector, cls_name, MagicMock())

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

        mod.SensorEntityDescription = type("SensorEntityDescription", (), {"__init__": _FakeEntityDescription.__init__})
        mod.BinarySensorEntityDescription = type("BinarySensorEntityDescription", (), {"__init__": _FakeEntityDescription.__init__})
        mod.NumberEntityDescription = type("NumberEntityDescription", (), {"__init__": _FakeEntityDescription.__init__})
        mod.SelectEntityDescription = type("SelectEntityDescription", (), {"__init__": _FakeEntityDescription.__init__})
        mod.SwitchEntityDescription = type("SwitchEntityDescription", (), {"__init__": _FakeEntityDescription.__init__})

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

        def _redact(data, keys):
            if not isinstance(data, dict):
                return data
            return {k: _redact(v, keys) for k, v in data.items() if k not in keys}
        mod.async_redact_data = _redact
        setattr(components, platform, mod)

    ha.loader.async_get_integration = AsyncMock(return_value=MagicMock(manifest={"version": "0.2.1"}))


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
    return hass


@pytest.fixture
def mock_config_entry():
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
