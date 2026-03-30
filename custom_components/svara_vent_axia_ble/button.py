"""Button entities for one-shot Vent-Axia Svara actions."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory

from .entity import SvaraVentAxiaEntity
from .entity_descriptions import ButtonDescription
from .runtime import iter_entry_devices

_LOGGER = logging.getLogger(__name__)

ENTITIES = [
    ButtonDescription(
        key="refresh_now",
        action="refresh_now",
        entity_name="Refresh Now",
        translation_key="refresh_now",
        category=EntityCategory.DIAGNOSTIC,
        icon="mdi:refresh",
    ),
    ButtonDescription(
        key="sync_clock",
        action="sync_clock",
        entity_name="Sync Clock",
        translation_key="sync_clock",
        category=EntityCategory.CONFIG,
        icon="mdi:clock-sync",
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up buttons from a config entry."""
    entities = []
    for _device_id, device_name, coordinator in iter_entry_devices(config_entry):
        _LOGGER.debug("Starting Svara buttons: %s", device_name)
        for entity_description in ENTITIES:
            entities.append(SvaraButtonEntity(coordinator, entity_description))
    async_add_devices(entities)


class SvaraButtonEntity(SvaraVentAxiaEntity, ButtonEntity):
    """Representation of a Svara action button."""

    def __init__(self, coordinator, entity_description):
        super().__init__(coordinator, entity_description)
        self._action = entity_description.action

    async def async_press(self) -> None:
        if self._action == "refresh_now":
            await self.coordinator.async_request_refresh()
            return

        if self._action == "sync_clock":
            await self.coordinator.async_sync_clock()
