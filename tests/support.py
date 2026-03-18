"""Helpers for importing integration modules without Home Assistant installed."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "custom_components.svara_vent_axia_ble"
PACKAGE_PATH = REPO_ROOT / "custom_components" / "svara_vent_axia_ble"


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

    base_device_module = _module(f"{PACKAGE_NAME}.devices.base_device")

    class BaseDevice:
        """Minimal device stub for config flow imports."""

        def __init__(self, *_args, **_kwargs) -> None:
            pass

    base_device_module.BaseDevice = BaseDevice

    voluptuous = _module("voluptuous")
    voluptuous.Schema = lambda value: value
    voluptuous.Required = lambda key, default=None: key
    voluptuous.Optional = lambda key, default=None: key
    voluptuous.All = lambda *validators: validators
    voluptuous.Coerce = lambda typ: typ
    voluptuous.Range = lambda **_kwargs: None

    homeassistant = _module("homeassistant")
    homeassistant.__path__ = []

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

    data_entry_flow = _module("homeassistant.data_entry_flow")
    data_entry_flow.FlowResult = dict

    helpers = _module("homeassistant.helpers")
    helpers.__path__ = []

    config_validation = _module("homeassistant.helpers.config_validation")
    config_validation.string = str
    config_validation.boolean = bool

    device_registry = _module("homeassistant.helpers.device_registry")

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

    return importlib.import_module(f"{PACKAGE_NAME}.{module_name}")
