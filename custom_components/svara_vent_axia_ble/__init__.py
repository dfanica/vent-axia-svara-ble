"""Support for Vent-Axia Svara fans over BLE."""

import asyncio
import logging
from functools import partial
from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_MAC, CONF_NAME, DOMAIN, PLATFORMS
from .helpers import getCoordinator
from .runtime import DeviceRuntime, IntegrationRuntime, get_entry_runtime

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vent-Axia Svara from a config entry."""
    _LOGGER.debug("Setting up Vent-Axia Svara")
    runtime = IntegrationRuntime()
    entry.runtime_data = runtime

    first_iteration = True
    for device_id, device_data in entry.data[CONF_DEVICES].items():
        if not first_iteration:
            await asyncio.sleep(10)
        first_iteration = False

        name = device_data[CONF_NAME]
        mac = device_data[CONF_MAC]
        device_registry = dr.async_get(hass)
        dev = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, mac)},
            name=name,
        )

        coordinator = getCoordinator(hass, entry, device_data, dev)
        try:
            await asyncio.wait_for(coordinator.async_request_refresh(), timeout=30)
        except (asyncio.TimeoutError, asyncio.CancelledError) as err:
            _LOGGER.warning(
                "Initial connection to %s timed out or was cancelled, will retry in background: %s",
                name,
                err,
            )
        except Exception as err:
            _LOGGER.warning(
                "Initial connection to %s failed, will retry in background: %s",
                name,
                err,
            )

        runtime.devices[device_id] = DeviceRuntime(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    if not hass.services.has_service(DOMAIN, "request_update"):
        hass.services.async_register(
            DOMAIN, "request_update", partial(service_request_update, hass)
        )

    return True


async def service_request_update(hass: HomeAssistant, call: ServiceCall) -> None:
    """Refresh a specific device on demand."""
    device_id = call.data.get("device_id")
    if not device_id:
        _LOGGER.error("Device ID is required")
        return

    for entry in hass.config_entries.async_entries(DOMAIN):
        runtime = cast(IntegrationRuntime | None, entry.runtime_data)
        if runtime is None:
            continue
        for coordinator in runtime.coordinators():
            if getattr(coordinator, "device_id", None) == device_id:
                await coordinator.async_request_refresh()
                return

    _LOGGER.warning("No coordinator found for device ID %s", device_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """No migrations are currently defined."""
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    _LOGGER.debug("Reloading Vent-Axia Svara entry")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Vent-Axia Svara entry")
    runtime = get_entry_runtime(entry)
    for coordinator in runtime.coordinators():
        await coordinator.disconnect()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove device entities and config from Home Assistant."""
    device_id = device_entry.id
    ent_reg = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id):
        if ent.device_id == device_id:
            ent_reg.async_remove(ent.entity_id)

    dev_reg = dr.async_get(hass)
    dev_reg.async_remove_device(device_id)

    devices_to_remove = [
        identifier[1]
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
    ]
    new_data = config_entry.data.copy()
    new_data[CONF_DEVICES] = dict(new_data[CONF_DEVICES])
    for mac in devices_to_remove:
        new_data[CONF_DEVICES].pop(mac, None)
    hass.config_entries.async_update_entry(config_entry, data=new_data)
    return True
