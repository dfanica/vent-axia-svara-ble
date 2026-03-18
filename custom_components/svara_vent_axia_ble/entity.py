"""Base entity class for the Vent-Axia Svara integration."""

import logging

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BaseCoordinator

_LOGGER = logging.getLogger(__name__)


class SvaraVentAxiaEntity(CoordinatorEntity):
    """Vent-Axia Svara base entity class."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BaseCoordinator, entity_description):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self._attr_entity_category = entity_description.category
        self._attr_icon = entity_description.icon
        self._attr_name = entity_description.entity_name
        if entity_description.translation_key:
            self._attr_translation_key = entity_description.translation_key
        self._attr_unique_id = f"{self.coordinator.device_id}-{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers=self.coordinator.identifiers,
            connections={(dr.CONNECTION_BLUETOOTH, self.coordinator.fan._mac)},
        )
        self._extra_state_attributes = {}
        self._key = entity_description.key

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._extra_state_attributes
