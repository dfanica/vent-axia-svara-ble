import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory

from .entity import SvaraVentAxiaEntity
from .entity_descriptions import AttributeDescription, SwitchDescription
from .runtime import iter_entry_devices

_LOGGER = logging.getLogger(__name__)

boostmode_attribute = AttributeDescription("boostmodesecread", "Boost time remaining", " s")

ENTITIES = [
    SwitchDescription(
        key="boostmode",
        entity_name="Boost Mode",
        translation_key="boostmode",
        icon="mdi:wind-power",
        attributes=boostmode_attribute,
    ),
    SwitchDescription(
        key="trickle_continuous",
        entity_name="Trickle Continuous",
        translation_key="trickle_continuous",
        category=EntityCategory.CONFIG,
        icon="mdi:calendar-expand-horizontal",
    ),
    SwitchDescription(
        key="trickledays_weekdays",
        entity_name="Trickle Weekdays",
        translation_key="trickledays_weekdays",
        category=EntityCategory.CONFIG,
        icon="mdi:calendar-week",
    ),
    SwitchDescription(
        key="trickledays_weekends",
        entity_name="Trickle Weekends",
        translation_key="trickledays_weekends",
        category=EntityCategory.CONFIG,
        icon="mdi:calendar-weekend",
    ),
    SwitchDescription(
        key="silenthours_on",
        entity_name="Silent Hours",
        translation_key="silenthours_on",
        category=EntityCategory.CONFIG,
        icon="mdi:bed-clock",
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up switches from a config entry."""
    entities = []
    for _device_id, device_name, coordinator in iter_entry_devices(config_entry):
        _LOGGER.debug("Starting Svara switches: %s", device_name)
        for entity_description in ENTITIES:
            entities.append(SvaraSwitchEntity(coordinator, entity_description))
    async_add_devices(entities, True)


class SvaraSwitchEntity(SvaraVentAxiaEntity, SwitchEntity):
    """Representation of a Svara switch."""

    def __init__(self, coordinator, entity_description):
        super().__init__(coordinator, entity_description)
        self._attribute_description = entity_description.attributes

    @property
    def is_on(self):
        if self._key == "trickle_continuous":
            return bool(
                self.coordinator.get_data("trickledays_weekdays")
                and self.coordinator.get_data("trickledays_weekends")
            )
        return self.coordinator.get_data(self._key)

    @property
    def extra_state_attributes(self):
        if self._attribute_description is None:
            return None
        value = self.coordinator.get_data(self._attribute_description.key)
        attrs = {
            self._attribute_description.descriptor: f"{value}{self._attribute_description.unit}"
        }
        attrs.update(super().extra_state_attributes)
        return attrs

    async def async_turn_on(self, **kwargs):
        await self._write_value(1)

    async def async_turn_off(self, **kwargs):
        await self._write_value(0)

    async def _write_value(self, value):
        if self._key == "trickle_continuous":
            old_weekdays = self.coordinator.get_data("trickledays_weekdays")
            old_weekends = self.coordinator.get_data("trickledays_weekends")
            self.coordinator.set_data("trickledays_weekdays", value)
            self.coordinator.set_data("trickledays_weekends", value)
            if not await self.coordinator.write_data("trickledays_weekdays"):
                self.coordinator.set_data("trickledays_weekdays", old_weekdays)
                self.coordinator.set_data("trickledays_weekends", old_weekends)
            self.async_schedule_update_ha_state(force_refresh=False)
            return

        old_value = self.coordinator.get_data(self._key)
        self.coordinator.set_data(self._key, value)
        if not await self.coordinator.write_data(self._key):
            self.coordinator.set_data(self._key, old_value)
        self.async_schedule_update_ha_state(force_refresh=False)
