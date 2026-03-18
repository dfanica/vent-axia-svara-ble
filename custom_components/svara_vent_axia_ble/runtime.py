"""Runtime models for the Vent-Axia Svara integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES

from .const import CONF_NAME

if TYPE_CHECKING:
    from .coordinator import BaseCoordinator


@dataclass(slots=True)
class DeviceRuntime:
    """Runtime state for a configured device."""

    coordinator: BaseCoordinator


@dataclass(slots=True)
class IntegrationRuntime:
    """Runtime state for a config entry."""

    devices: dict[str, DeviceRuntime] = field(default_factory=dict)

    def coordinators(self) -> list[BaseCoordinator]:
        """Return all coordinators for this config entry."""
        return [device.coordinator for device in self.devices.values()]


def get_entry_runtime(entry: ConfigEntry) -> IntegrationRuntime:
    """Return the typed runtime state for a config entry."""
    return entry.runtime_data


def get_entry_coordinators(entry: ConfigEntry) -> dict[str, BaseCoordinator]:
    """Return coordinators indexed by configured device key."""
    runtime = get_entry_runtime(entry)
    return {
        device_id: runtime.devices[device_id].coordinator
        for device_id in entry.data[CONF_DEVICES]
        if device_id in runtime.devices
    }


def iter_entry_devices(
    entry: ConfigEntry,
) -> Iterator[tuple[str, str, BaseCoordinator]]:
    """Yield configured devices in config-entry order."""
    coordinators = get_entry_coordinators(entry)
    for device_id, device_data in entry.data[CONF_DEVICES].items():
        coordinator = coordinators.get(device_id)
        if coordinator is None:
            continue
        yield device_id, device_data[CONF_NAME], coordinator
