import logging
from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.helpers.entity import EntityCategory

from .entity import SvaraVentAxiaEntity
from .entity_descriptions import BaseSvaraEntityDescription
from .runtime import iter_entry_devices

_LOGGER = logging.getLogger(__name__)

ENTITIES = [
    BaseSvaraEntityDescription(
        key="silenthours_starttime",
        entity_name="Silent Hours Start Time",
        translation_key="silenthours_starttime",
        category=EntityCategory.CONFIG,
        icon="mdi:clock-check-outline",
    ),
    BaseSvaraEntityDescription(
        key="silenthours_endtime",
        entity_name="Silent Hours Stop Time",
        translation_key="silenthours_endtime",
        category=EntityCategory.CONFIG,
        icon="mdi:clock-remove-outline",
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up time entities from a config entry."""
    entities = []
    for _device_id, device_name, coordinator in iter_entry_devices(config_entry):
        _LOGGER.debug("Starting Svara time entities: %s", device_name)
        for entity_description in ENTITIES:
            entities.append(SvaraTimeEntity(coordinator, entity_description))
    async_add_devices(entities, True)


class SvaraTimeEntity(SvaraVentAxiaEntity, TimeEntity):
    """Representation of a Svara time entity."""

    @property
    def native_value(self) -> time | None:
        try:
            return self.coordinator.get_data(self._key)
        except Exception:
            return None

    async def async_set_value(self, value: time) -> None:
        old_value = self.coordinator.get_data(self._key)
        self.coordinator.set_data(self._key, value)
        if not await self.coordinator.write_data(self._key):
            self.coordinator.set_data(self._key, old_value)
        self.async_schedule_update_ha_state(force_refresh=False)
