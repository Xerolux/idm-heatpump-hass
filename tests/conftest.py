"""Shared fixtures and HA mocks for IDM Heatpump tests."""

import asyncio
import math
import struct
import sys
from dataclasses import dataclass, field
from enum import Enum
from types import ModuleType
from typing import Any
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
    _runner_mod.HassEventLoopPolicy = type("HassEventLoopPolicy", (asyncio.WindowsSelectorEventLoopPolicy,), {})
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
    pymodbus.__version__ = "3.11.2"
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
            return None

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
    ha.components = _make_module("homeassistant.components")
    ha.components.repairs = _make_module("homeassistant.components.repairs")

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

    class _RepairsFlow:
        def async_show_form(self, *, step_id, data_schema=None, errors=None, description_placeholders=None):
            return {"type": "form", "step_id": step_id, "errors": errors or {}}

        def async_create_entry(self, title="", data=None):
            return {"type": "create_entry", "title": title, "data": data or {}}

        def async_abort(self, *, reason):
            return {"type": "abort", "reason": reason}

    ha.components.repairs.RepairsFlow = _RepairsFlow

    # homeassistant.exceptions
    class _HomeAssistantError(Exception):
        def __init__(
            self, *args, translation_domain=None, translation_key=None, translation_placeholders=None, **kwargs
        ):
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
            self.unique_id = None
            self.version = 1
            self.minor_version = 1

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

        def async_show_form(self, *, step_id, data_schema=None, errors=None, description_placeholders=None):
            return {"type": "form", "step_id": step_id, "errors": errors or {}}

        def async_create_entry(self, title="", data=None, options=None):
            return {"type": "create_entry", "title": title, "data": data or {}, "options": options or {}}

        def async_abort(self, reason):
            return {"type": "abort", "reason": reason}

        def async_update_reload_and_abort(self, entry, data_updates=None, **kwargs):
            return {"type": "abort", "reason": "reconfigure_successful"}

        def async_update_and_abort(self, entry, data_updates=None, **kwargs):
            return {"type": "abort", "reason": "reconfigure_successful"}

        async def async_set_unique_id(self, unique_id):
            pass

        def _abort_if_unique_id_configured(self):
            pass

        def _async_abort_entries_match(self, match_dict=None):
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

        def async_show_form(self, *, step_id, data_schema=None, errors=None, description_placeholders=None):
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
        "BooleanSelector",
        "BooleanSelectorConfig",
        "EntitySelector",
        "EntitySelectorConfig",
        "NumberSelector",
        "NumberSelectorConfig",
        "NumberSelectorMode",
        "SelectSelector",
        "SelectSelectorConfig",
        "SelectSelectorMode",
        "TextSelector",
        "TextSelectorConfig",
        "TextSelectorType",
    ]:
        setattr(selector_mod, cls_name, MagicMock())

    # homeassistant.helpers.entity
    entity_mod = _make_module("homeassistant.helpers.entity")
    helpers.entity = entity_mod

    class _EntityCategory(Enum):
        CONFIG = "config"
        DIAGNOSTIC = "diagnostic"

    class _EntityDescription:
        def __init__(self, key="", name="", **kwargs):
            self.key = key
            self.name = name
            for k, v in kwargs.items():
                setattr(self, k, v)

    entity_mod.EntityCategory = _EntityCategory
    entity_mod.EntityDescription = _EntityDescription

    # homeassistant.helpers.device_registry
    device_registry_mod = _make_module("homeassistant.helpers.device_registry")
    helpers.device_registry = device_registry_mod

    class _DeviceInfo(dict):
        def __init__(self, identifiers=None, name=None, manufacturer=None, model=None, sw_version=None, **kwargs):
            super().__init__(
                identifiers=identifiers or set(),
                name=name,
                manufacturer=manufacturer,
                model=model,
                **kwargs,
            )
            if sw_version is not None:
                self["sw_version"] = sw_version

    device_registry_mod.DeviceInfo = _DeviceInfo

    # homeassistant.helpers.entity_registry
    entity_registry_mod = _make_module("homeassistant.helpers.entity_registry")
    helpers.entity_registry = entity_registry_mod

    class _RegistryEntry:
        def __init__(self, entity_id="sensor.test", unique_id="test", config_entry_id=None):
            self.entity_id = entity_id
            self.unique_id = unique_id
            self.config_entry_id = config_entry_id

    class _EntityRegistry:
        def __init__(self):
            self.entities = {}

        def async_get(self, entity_id):
            return self.entities.get(entity_id)

        def async_update_entity(self, entity_id, *, new_unique_id):
            entry = self.entities[entity_id]
            entry.unique_id = new_unique_id
            return entry

    entity_registry_mod.async_get = MagicMock(return_value=_EntityRegistry())
    entity_registry_mod.async_entries_for_config_entry = lambda registry, entry_id: [
        entry for entry in registry.entities.values() if entry.config_entry_id == entry_id
    ]

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
    event_mod.async_track_state_change_event = MagicMock(return_value=MagicMock())

    # homeassistant.helpers.config_validation
    cv_mod = _make_module("homeassistant.helpers.config_validation")
    helpers.config_validation = cv_mod
    cv_mod.config_entry_only_config_schema = lambda domain: {}

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
        mod.BinarySensorEntityDescription = type(
            "BinarySensorEntityDescription", (), {"__init__": _FakeEntityDescription.__init__}
        )
        mod.NumberEntityDescription = type("NumberEntityDescription", (), {"__init__": _FakeEntityDescription.__init__})
        mod.SelectEntityDescription = type("SelectEntityDescription", (), {"__init__": _FakeEntityDescription.__init__})
        mod.SwitchEntityDescription = type("SwitchEntityDescription", (), {"__init__": _FakeEntityDescription.__init__})

        # Device/state class enums
        mod.SensorDeviceClass = MagicMock()
        mod.SensorDeviceClass.TEMPERATURE = "temperature"
        mod.SensorDeviceClass.POWER = "power"
        mod.SensorDeviceClass.ENERGY = "energy"
        mod.SensorDeviceClass.HUMIDITY = "humidity"
        mod.SensorDeviceClass.ENUM = "enum"
        mod.SensorDeviceClass.VOLUME_FLOW_RATE = "volume_flow_rate"
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

    ha.loader.async_get_integration = AsyncMock(return_value=MagicMock(manifest={"version": "0.5.0"}))


_stub_homeassistant()


# ---------------------------------------------------------------------------
# Stub idm_heatpump library (only when real library is not installed)
# ---------------------------------------------------------------------------


def _stub_idm_heatpump() -> None:
    """Stub for idm_heatpump library when the real package is not available."""
    try:
        import idm_heatpump  # noqa: F401

        return  # Real library installed — don't override
    except ImportError:
        pass

    class DataType(Enum):
        FLOAT = "FLOAT"
        UCHAR = "UCHAR"
        INT8 = "INT8"
        INT16 = "INT16"
        UINT16 = "UINT16"
        BOOL = "BOOL"
        BITFLAG = "BITFLAG"

    @dataclass
    class RegisterDef:
        address: int
        datatype: DataType
        name: str
        unit: str | None = None
        multiplier: float = 1.0
        enum_options: dict[int, str] | None = None
        writable: bool = False
        binary: bool = False
        write_only: bool = False
        exclude_from_write: set[int] | None = None
        icon: str | None = None
        min_val: float | None = None
        max_val: float | None = None
        enabled_by_default: bool = True
        state_class: Any = None

        @property
        def size(self) -> int:
            return 2 if self.datatype == DataType.FLOAT else 1

    @dataclass
    class IdmModelInfo:
        """Minimal model information compatible with idm-heatpump-api."""

        model_name: str
        active_heating_circuits: list[str]
        zone_modules: int
        has_solar: bool
        has_isc: bool
        has_pv: bool
        has_cascade: bool
        features: set[str] = field(default_factory=set)
        firmware_version: float | None = None

    class IdmModbusClient:
        def __init__(self, host: str = "", port: int = 502, slave_id: int = 1) -> None:
            self.host = host
            self.port = port
            self.slave_id = slave_id
            self._client = None
            self._max_retries = 3
            self._register_failures: dict[str, int] = {}
            self._permanently_failed_registers: set[str] = set()

        async def connect(self) -> None:
            if self._client is not None and getattr(self._client, "connected", False):
                return
            from idm_heatpump.client import AsyncModbusTcpClient

            self._client = AsyncModbusTcpClient(self.host, port=self.port)
            await self._client.connect()

        async def disconnect(self) -> None:
            if self._client is not None:
                self._client.close()
                self._client = None

        def _require_client(self) -> Any:
            from pymodbus.exceptions import ConnectionException

            if self._client is None or not getattr(self._client, "connected", False):
                raise ConnectionException("Modbus client is not connected")
            return self._client

        def decode_value(self, registers: list[int], reg: RegisterDef) -> Any:
            if reg.datatype == DataType.FLOAT:
                if len(registers) < 2:
                    raise ValueError("not enough registers for float")
                raw = struct.pack("<HH", registers[0], registers[1])
                value = struct.unpack("<f", raw)[0]
                if math.isnan(value):
                    return None
                return value * reg.multiplier
            if reg.datatype in (DataType.UCHAR, DataType.BITFLAG):
                return registers[0] & 0xFF
            if reg.datatype == DataType.INT8:
                value = registers[0] & 0xFF
                return value - 0x100 if value & 0x80 else value
            if reg.datatype == DataType.INT16:
                value = registers[0] & 0xFFFF
                return value - 0x10000 if value & 0x8000 else value
            if reg.datatype == DataType.UINT16:
                return registers[0] & 0xFFFF
            if reg.datatype == DataType.BOOL:
                return bool(registers[0])
            return registers[0]

        def encode_value(self, value: Any, reg: RegisterDef) -> list[int]:
            numeric = float(value) / reg.multiplier if reg.multiplier else float(value)
            if reg.datatype == DataType.FLOAT:
                return list(struct.unpack("<HH", struct.pack("<f", numeric)))
            if reg.datatype in (DataType.UCHAR, DataType.INT8, DataType.BITFLAG):
                return [int(value) & 0xFF]
            if reg.datatype in (DataType.INT16, DataType.UINT16):
                return [int(value) & 0xFFFF]
            if reg.datatype == DataType.BOOL:
                return [1 if value else 0]
            return [int(value)]

        async def read_register(self, reg: RegisterDef) -> Any:
            client = self._require_client()
            result = await client.read_input_registers(reg.address, reg.size, slave=self.slave_id)
            if result.isError():
                from pymodbus.exceptions import ModbusException

                raise ModbusException("Modbus read error")
            return self.decode_value(result.registers, reg)

        async def write_register(self, reg: RegisterDef, value: Any) -> None:
            if not reg.writable:
                raise ValueError(f"Register {reg.name} is read-only")
            if reg.min_val is not None and value < reg.min_val:
                raise ValueError(f"Value below minimum {reg.min_val}")
            if reg.max_val is not None and value > reg.max_val:
                raise ValueError(f"Value above maximum {reg.max_val}")

            client = self._require_client()
            result = await client.write_registers(
                reg.address,
                self.encode_value(value, reg),
                slave=self.slave_id,
            )
            if result.isError():
                from pymodbus.exceptions import ModbusException

                raise ModbusException("Modbus write error")

        def _group_registers(self, regs: list[RegisterDef]) -> list[list[RegisterDef]]:
            groups: list[list[RegisterDef]] = []
            current: list[RegisterDef] = []
            current_end = 0
            for reg in sorted(regs, key=lambda item: item.address):
                if not current:
                    current = [reg]
                    current_end = reg.address + reg.size
                    continue
                group_start = current[0].address
                proposed_end = max(current_end, reg.address + reg.size)
                if reg.address > current_end + 10 or proposed_end - group_start > 40:
                    groups.append(current)
                    current = [reg]
                    current_end = reg.address + reg.size
                else:
                    current.append(reg)
                    current_end = proposed_end
            if current:
                groups.append(current)
            return groups

        async def _read_group(self, regs: list[RegisterDef]) -> dict[str, Any]:
            if not regs:
                return {}
            client = self._require_client()
            start = min(reg.address for reg in regs)
            end = max(reg.address + reg.size for reg in regs)
            result = None
            for attempt in range(self._max_retries + 1):
                try:
                    result = await client.read_input_registers(start, end - start, slave=self.slave_id)
                    if result.isError():
                        from pymodbus.exceptions import ModbusException

                        raise ModbusException("Modbus read error")
                    break
                except Exception:
                    if attempt < self._max_retries:
                        continue
                    for reg in regs:
                        failures = self._register_failures.get(reg.name, 0) + 1
                        self._register_failures[reg.name] = failures
                        if failures >= 3:
                            self._permanently_failed_registers.add(reg.name)
                    return {}

            data = {}
            for reg in regs:
                offset = reg.address - start
                raw = result.registers[offset : offset + reg.size]
                if len(raw) < reg.size:
                    continue
                data[reg.name] = self.decode_value(raw, reg)
                self._register_failures.pop(reg.name, None)
            return data

        async def read_batch(self, regs: Any) -> dict[str, Any]:
            readable = [reg for reg in regs if reg.name not in self._permanently_failed_registers]
            data: dict[str, Any] = {}
            for group in self._group_registers(readable):
                data.update(await self._read_group(group))
            return data

        def reset_failed_registers(self) -> None:
            self._register_failures.clear()
            self._permanently_failed_registers.clear()

    _SYS_MODE = {0: "Standby", 1: "Automatic", 2: "Absent", 4: "Hot Water Only", 5: "Heating/Cooling Only"}
    _CIRCUIT_MODE = {
        0: "Off",
        1: "Time Program",
        2: "Normal",
        3: "Eco",
        4: "Manual Heat",
        5: "Manual Cool",
        255: "Not Configured",
    }
    _ROOM_MODE = {0: "Off", 1: "Automatic", 2: "Eco", 3: "Normal", 4: "Comfort"}
    _SOLAR_MODE = {0: "Automatic", 1: "Hot Water", 2: "Heating", 3: "Hot Water + Heating", 4: "Source/Pool"}
    _HP_STATUS = {0: "Off", 1: "Heating", 2: "Cooling", 4: "DHW", 8: "Defrost"}

    _BASE: list[RegisterDef] = [
        RegisterDef(1000, DataType.FLOAT, "outdoor_temp", unit="°C"),
        RegisterDef(1002, DataType.FLOAT, "outdoor_temp_avg", unit="°C"),
        RegisterDef(1005, DataType.UCHAR, "system_mode", writable=True, enum_options=_SYS_MODE),
        RegisterDef(1006, DataType.UCHAR, "smart_grid_status"),
        RegisterDef(1008, DataType.FLOAT, "storage_temp", unit="°C"),
        RegisterDef(1010, DataType.FLOAT, "cold_storage_temp", unit="°C"),
        RegisterDef(1012, DataType.FLOAT, "dhw_temp_bottom", unit="°C"),
        RegisterDef(1014, DataType.FLOAT, "dhw_temp_top", unit="°C"),
        RegisterDef(1050, DataType.FLOAT, "hp_flow_temp", unit="°C"),
        RegisterDef(1052, DataType.FLOAT, "hp_return_temp", unit="°C"),
        RegisterDef(1068, DataType.FLOAT, "heat_sink_return_temp", unit="°C"),
        RegisterDef(1070, DataType.FLOAT, "heat_sink_flow_temp", unit="°C"),
        RegisterDef(1072, DataType.UCHAR, "heat_sink_flow_rate", unit="L/min"),
        RegisterDef(1074, DataType.INT16, "heat_sink_charging_pump_signal", unit="%"),
        RegisterDef(1090, DataType.BITFLAG, "hp_operating_mode", enum_options=_HP_STATUS),
        RegisterDef(1098, DataType.BOOL, "evu_lock", binary=True),
        RegisterDef(1099, DataType.BOOL, "hp_sum_alarm", binary=True),
        RegisterDef(1250, DataType.FLOAT, "dhw_setpoint", unit="°C", writable=True, min_val=45.0, max_val=65.0),
        RegisterDef(1300, DataType.FLOAT, "bivalence_point_1_2nd_gen", unit="°C", writable=True),
        RegisterDef(1352, DataType.UCHAR, "solar_mode", writable=True, enum_options=_SOLAR_MODE),
        RegisterDef(1650, DataType.FLOAT, "pv_surplus", unit="kW", writable=True),
        RegisterDef(1652, DataType.FLOAT, "pv_production", unit="kW", writable=True),
        RegisterDef(1654, DataType.FLOAT, "house_consumption", unit="kW", writable=True),
        RegisterDef(1656, DataType.FLOAT, "battery_discharge", unit="kW", writable=True),
        RegisterDef(1658, DataType.UINT16, "battery_soc", unit="%", writable=True),
        RegisterDef(1660, DataType.FLOAT, "electric_heater_power", unit="kW", writable=True),
        RegisterDef(1662, DataType.FLOAT, "pv_target_value", unit="kW", writable=True),
        RegisterDef(1670, DataType.FLOAT, "variable_input"),
        RegisterDef(1680, DataType.UCHAR, "ext_demand_groundwater_pump_m15_sw_max", writable=True),
        RegisterDef(1690, DataType.FLOAT, "ext_outdoor_temp", unit="°C"),
        RegisterDef(1692, DataType.FLOAT, "ext_humidity", unit="%"),
        RegisterDef(1710, DataType.BOOL, "demand_heating", writable=True),
        RegisterDef(1711, DataType.BOOL, "demand_cooling", writable=True),
        RegisterDef(1712, DataType.BOOL, "demand_dhw_charging", writable=True),
        RegisterDef(1713, DataType.BOOL, "demand_onetime_dhw", writable=True),
        RegisterDef(1748, DataType.FLOAT, "energy_heating", unit="kWh"),
        RegisterDef(1750, DataType.FLOAT, "energy_total", unit="kWh"),
        RegisterDef(1752, DataType.FLOAT, "energy_cooling", unit="kWh"),
        RegisterDef(1754, DataType.FLOAT, "energy_dhw", unit="kWh"),
        RegisterDef(1756, DataType.FLOAT, "energy_defrost", unit="kWh"),
        RegisterDef(1790, DataType.FLOAT, "current_power", unit="kW"),
        RegisterDef(1850, DataType.FLOAT, "solar_collector_temp", unit="°C"),
        RegisterDef(4108, DataType.FLOAT, "power_limit_hp", unit="kW", writable=True, enabled_by_default=False),
        RegisterDef(4112, DataType.FLOAT, "power_limit_cascade", unit="kW", writable=True, enabled_by_default=False),
        RegisterDef(4120, DataType.FLOAT, "power_consumption_hp", unit="kW"),
        RegisterDef(4126, DataType.FLOAT, "thermal_power", unit="kW"),
    ]

    def _circuit_regs(circuit: str) -> list[RegisterDef]:
        base = {"a": 1400, "b": 1420, "c": 1440, "d": 1460, "e": 1480, "f": 1500, "g": 1520}.get(circuit, 1400)
        return [
            RegisterDef(base, DataType.FLOAT, f"hc_{circuit}_flow_temp", unit="°C"),
            RegisterDef(base + 2, DataType.FLOAT, f"hc_{circuit}_room_temp", unit="°C"),
            RegisterDef(base + 4, DataType.UCHAR, f"hc_{circuit}_active_mode", enum_options=dict(_CIRCUIT_MODE)),
            RegisterDef(
                base + 5,
                DataType.UCHAR,
                f"hc_{circuit}_mode",
                writable=True,
                enum_options=dict(_CIRCUIT_MODE),
                exclude_from_write={255},
            ),
            RegisterDef(
                base + 6,
                DataType.FLOAT,
                f"hc_{circuit}_room_setpoint_heat_normal",
                unit="°C",
                writable=True,
                min_val=16.0,
                max_val=28.0,
            ),
            RegisterDef(
                base + 8,
                DataType.FLOAT,
                f"hc_{circuit}_room_setpoint_heat_eco",
                unit="°C",
                writable=True,
                min_val=10.0,
                max_val=22.0,
            ),
            RegisterDef(
                base + 10, DataType.FLOAT, f"hc_{circuit}_heating_curve", writable=True, min_val=0.1, max_val=3.0
            ),
            RegisterDef(base + 12, DataType.FLOAT, f"hc_{circuit}_ext_room_temp", unit="°C", writable=True),
        ]

    def _zone_regs(zone_idx: int, room_count: int) -> list[RegisterDef]:
        regs = []
        base = 2000 + (zone_idx - 1) * 100
        for r in range(1, room_count + 1):
            off = base + (r - 1) * 10
            regs += [
                RegisterDef(off, DataType.FLOAT, f"zm{zone_idx}_room{r}_temp", unit="°C", writable=True),
                RegisterDef(off + 2, DataType.FLOAT, f"zm{zone_idx}_room{r}_setpoint", unit="°C", writable=True),
                RegisterDef(off + 4, DataType.UINT16, f"zm{zone_idx}_room{r}_humidity", unit="%", writable=True),
                RegisterDef(
                    off + 5, DataType.UCHAR, f"zm{zone_idx}_room{r}_mode", writable=True, enum_options=dict(_ROOM_MODE)
                ),
            ]
        return regs

    def build_register_map(
        model_info: Any = None,
        circuits: list[str] | None = None,
        zone_modules: int = 0,
    ) -> dict[str, RegisterDef]:
        regs = list(_BASE)
        for c in circuits or []:
            regs.extend(_circuit_regs(c))
        result: dict[str, RegisterDef] = {}
        for r in regs:
            if r.name not in result:
                result[r.name] = r
        return result

    def get_heating_circuit_registers(circuit: str) -> dict[str, RegisterDef]:
        return {r.name: r for r in _circuit_regs(circuit)}

    def get_zone_module_registers(zone_idx: int, room_count: int = 6) -> dict[str, RegisterDef]:
        return {r.name: r for r in _zone_regs(zone_idx, room_count)}

    idm_mod = ModuleType("idm_heatpump")
    idm_mod.RegisterDef = RegisterDef  # type: ignore[attr-defined]
    idm_mod.IdmModbusClient = IdmModbusClient  # type: ignore[attr-defined]
    idm_mod.IdmModelInfo = IdmModelInfo  # type: ignore[attr-defined]
    idm_mod.build_register_map = build_register_map  # type: ignore[attr-defined]
    idm_mod.get_heating_circuit_registers = get_heating_circuit_registers  # type: ignore[attr-defined]
    idm_mod.get_zone_module_registers = get_zone_module_registers  # type: ignore[attr-defined]
    idm_mod.RECOMMENDED_WEB_SCAN_INTERVAL = 30.0  # type: ignore[attr-defined]
    idm_mod.WEB_VALUE_DESCRIPTIONS = {}  # type: ignore[attr-defined]
    sys.modules["idm_heatpump"] = idm_mod

    client_mod = ModuleType("idm_heatpump.client")
    client_mod.DataType = DataType  # type: ignore[attr-defined]
    client_mod.IdmModelInfo = IdmModelInfo  # type: ignore[attr-defined]
    client_mod.AsyncModbusTcpClient = MagicMock  # type: ignore[attr-defined]
    sys.modules["idm_heatpump.client"] = client_mod
    idm_mod.client = client_mod  # type: ignore[attr-defined]

    const_mod = ModuleType("idm_heatpump.const")
    const_mod.MODEL_NAVIGATOR_10 = "navigator_10"  # type: ignore[attr-defined]
    const_mod.MODEL_NAVIGATOR_20 = "navigator_20"  # type: ignore[attr-defined]
    const_mod.MODEL_NAVIGATOR_PRO = "navigator_pro"  # type: ignore[attr-defined]
    const_mod.MODEL_UNKNOWN = "unknown"  # type: ignore[attr-defined]
    sys.modules["idm_heatpump.const"] = const_mod
    idm_mod.const = const_mod  # type: ignore[attr-defined]


_stub_idm_heatpump()


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
    hass.config_entries.async_update_entry = MagicMock()
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
    with patch("idm_heatpump.client.AsyncModbusTcpClient") as mock_class:
        mock_instance = AsyncMock()
        mock_instance.connected = True
        mock_instance.isError = MagicMock(return_value=False)
        mock_instance.close = MagicMock()
        mock_class.return_value = mock_instance

        from idm_heatpump import IdmModbusClient

        client = IdmModbusClient(host="192.168.1.100", port=502, slave_id=1)
        client._client = mock_instance
        yield client, mock_instance
