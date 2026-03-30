"""Helpers for importing integration modules without Home Assistant installed."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "custom_components.svara_vent_axia_ble"
PACKAGE_PATH = REPO_ROOT / "custom_components" / "svara_vent_axia_ble"
REAL_DEVICE_MODULES = {"devices.base_device", "devices.svara"}


def _reset_modules() -> None:
    """Remove stubbed integration and Home Assistant modules."""
    prefixes = (
        "custom_components",
        "homeassistant",
        "voluptuous",
    )
    for module_name in list(sys.modules):
        if module_name.startswith(prefixes):
            sys.modules.pop(module_name, None)


def _module(name: str) -> types.ModuleType:
    """Create and register a blank module."""
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def load_integration_module(module_name: str):
    """Import a submodule from the integration package with lightweight stubs."""
    _reset_modules()

    custom_components = _module("custom_components")
    custom_components.__path__ = [str(REPO_ROOT / "custom_components")]

    package = _module(PACKAGE_NAME)
    package.__path__ = [str(PACKAGE_PATH)]

    devices_package = _module(f"{PACKAGE_NAME}.devices")
    devices_package.__path__ = [str(PACKAGE_PATH / "devices")]

    voluptuous = _module("voluptuous")
    voluptuous.Schema = lambda value: value
    voluptuous.Required = lambda key, default=None: key
    voluptuous.Optional = lambda key, default=None: key
    voluptuous.All = lambda *validators: validators
    voluptuous.Coerce = lambda typ: typ
    voluptuous.Range = lambda **_kwargs: None

    homeassistant = _module("homeassistant")
    homeassistant.__path__ = []

    components = _module("homeassistant.components")
    components.__path__ = []

    config_entries = _module("homeassistant.config_entries")

    class ConfigEntry:
        """Minimal ConfigEntry stub."""

        def __init__(
            self,
            *,
            runtime_data=None,
            data=None,
            title="",
            version=1,
            minor_version=1,
            options=None,
        ) -> None:
            self.runtime_data = runtime_data
            self.data = data or {}
            self.title = title
            self.version = version
            self.minor_version = minor_version
            self.options = options or {}

    class ConfigFlow:
        """Minimal ConfigFlow stub."""

        def __init_subclass__(cls, **_kwargs) -> None:
            return None

    class OptionsFlow:
        """Minimal OptionsFlow stub."""

        def __init__(self, *_args, **_kwargs) -> None:
            pass

    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlow = OptionsFlow

    const = _module("homeassistant.const")
    const.CONF_DEVICES = "devices"

    class Platform:
        BUTTON = "button"
        TIME = "time"
        SENSOR = "sensor"
        SWITCH = "switch"
        NUMBER = "number"
        SELECT = "select"

    const.Platform = Platform

    core = _module("homeassistant.core")

    class HomeAssistant:
        """Minimal HomeAssistant stub."""

    core.HomeAssistant = HomeAssistant

    util = _module("homeassistant.util")
    util.__path__ = []
    dt_util = _module("homeassistant.util.dt")

    def now():
        from datetime import datetime

        return datetime(2026, 3, 29, 12, 0, 0)

    dt_util.now = now

    data_entry_flow = _module("homeassistant.data_entry_flow")
    data_entry_flow.FlowResult = dict

    helpers = _module("homeassistant.helpers")
    helpers.__path__ = []

    entity = _module("homeassistant.helpers.entity")

    class EntityCategory:
        CONFIG = "config"
        DIAGNOSTIC = "diagnostic"

    class DeviceInfo(dict):
        """Minimal DeviceInfo stub."""

    entity.EntityCategory = EntityCategory
    entity.DeviceInfo = DeviceInfo

    config_validation = _module("homeassistant.helpers.config_validation")
    config_validation.string = str
    config_validation.boolean = bool

    device_registry = _module("homeassistant.helpers.device_registry")
    device_registry.CONNECTION_BLUETOOTH = "bluetooth"
    device_registry.DeviceInfo = DeviceInfo

    def format_mac(value: str) -> str:
        cleaned = "".join(character for character in value if character.isalnum())
        pairs = [
            cleaned[index : index + 2].upper() for index in range(0, len(cleaned), 2)
        ]
        return ":".join(pairs)

    device_registry.format_mac = format_mac

    diagnostics = _module("homeassistant.components.diagnostics")

    def async_redact_data(value, to_redact):
        if isinstance(value, dict):
            return {
                key: ("REDACTED" if key in to_redact else async_redact_data(val, to_redact))
                for key, val in value.items()
            }
        if isinstance(value, list):
            return [async_redact_data(item, to_redact) for item in value]
        return value

    diagnostics.async_redact_data = async_redact_data

    update_coordinator = _module("homeassistant.helpers.update_coordinator")

    class CoordinatorEntity:
        """Minimal CoordinatorEntity stub."""

        def __init__(self, coordinator) -> None:
            self.coordinator = coordinator

    update_coordinator.CoordinatorEntity = CoordinatorEntity

    button = _module("homeassistant.components.button")

    class ButtonEntity:
        """Minimal ButtonEntity stub."""

    button.ButtonEntity = ButtonEntity

    bluetooth = _module("homeassistant.components.bluetooth")
    bluetooth.async_ble_device_from_address = lambda *_args, **_kwargs: None

    if module_name not in REAL_DEVICE_MODULES:
        base_device_module = _module(f"{PACKAGE_NAME}.devices.base_device")
        svara_device_module = _module(f"{PACKAGE_NAME}.devices.svara")

        class BaseDevice:
            """Minimal device stub for config flow imports."""

            def __init__(self, *_args, **_kwargs) -> None:
                pass

        base_device_module.BaseDevice = BaseDevice

        class SvaraDevice(BaseDevice):
            """Minimal Svara device stub for coordinator imports."""

            def set_disconnect_callback(self, *_args, **_kwargs) -> None:
                pass

        svara_device_module.SvaraDevice = SvaraDevice

    if module_name != "coordinator":
        coordinator_module = _module(f"{PACKAGE_NAME}.coordinator")

        class BaseCoordinator:
            """Minimal coordinator stub for coordinator-specific imports."""

            def __init__(
                self, hass, device, model, scan_interval, scan_interval_fast
            ) -> None:
                self.hass = hass
                self._device = device
                self._model = model
                self._normal_poll_interval = scan_interval
                self._fast_poll_interval = scan_interval_fast
                self._state = {}

            @property
            def devicename(self) -> str:
                return getattr(self._device, "name", "Unknown")

            async def _on_device_disconnect(self) -> None:
                return None

        coordinator_module.BaseCoordinator = BaseCoordinator

    bleak = _module("bleak")
    bleak.__path__ = []
    bleak_exc = _module("bleak.exc")

    class BleakError(Exception):
        """Minimal bleak exception stub."""

    bleak_exc.BleakError = BleakError

    bleak_retry_connector = _module("bleak_retry_connector")

    class BleakClientWithServiceCache:
        """Minimal bleak client type stub."""

        is_connected = False

        async def disconnect(self) -> None:
            return None

    async def establish_connection(*_args, **_kwargs):
        return BleakClientWithServiceCache()

    async def close_stale_connections() -> None:
        return None

    bleak_retry_connector.BleakClientWithServiceCache = BleakClientWithServiceCache
    bleak_retry_connector.establish_connection = establish_connection
    bleak_retry_connector.close_stale_connections = close_stale_connections

    return importlib.import_module(f"{PACKAGE_NAME}.{module_name}")
