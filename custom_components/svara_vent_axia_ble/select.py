import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import SvaraVentAxiaEntity
from .entity_descriptions import SelectDescription
from .runtime import iter_entry_devices

_LOGGER = logging.getLogger(__name__)

OPTIONS = {
    "automatic_cycles": {
        "0": "Off",
        "1": "30 min",
        "2": "60 min",
        "3": "90 min"
    },
    "boostmodesecwrite": {
        "300": "5 min",
        "600": "10 min",
        "900": "15 min",
        "1800": "30 min",
        "2700": "45 min",
        "3600": "60 min",
    },
    "lightsensorsettings_delayedstart": {
        "0": "No delay",
        "1": "1 min",
        "2": "2 min",
        "3": "3 min",
        "4": "4 min",
        "5": "5 min",
        "6": "6 min",
        "7": "7 min",
        "8": "8 min",
        "9": "9 min",
        "10": "10 min",
    },
    "lightsensorsettings_runningtime": {
        "5": "5 min",
        "10": "10 min",
        "15": "15 min",
        "30": "30 min",
        "45": "45 min",
        "60": "60 min",
    },
    "sensitivity": {
        "0": "Off",
        "1": "Low sensitivity",
        "2": "Medium sensitivity",
        "3": "High sensitivity",
    },
    "fanspeedsettings_rpms": {
        "800": "800 rpm",
        "850": "850 rpm",
        "900": "900 rpm",
        "950": "950 rpm",
        "1000": "1000 rpm",
        "1050": "1050 rpm",
        "1100": "1100 rpm",
        "1150": "1150 rpm",
        "1200": "1200 rpm",
        "1250": "1250 rpm",
        "1300": "1300 rpm",
        "1350": "1350 rpm",
        "1400": "1400 rpm",
        "1450": "1450 rpm",
        "1500": "1500 rpm",
        "1550": "1550 rpm",
        "1600": "1600 rpm",
        "1650": "1650 rpm",
        "1700": "1700 rpm",
        "1750": "1750 rpm",
        "1800": "1800 rpm",
        "1850": "1850 rpm",
        "1900": "1900 rpm",
        "1950": "1950 rpm",
        "2000": "2000 rpm",
        "2050": "2050 rpm",
        "2100": "2100 rpm",
        "2150": "2150 rpm",
        "2200": "2200 rpm",
        "2250": "2250 rpm",
        "2300": "2300 rpm",
        "2350": "2350 rpm",
        "2400": "2400 rpm"
    }
}

ENTITIES = [
    SelectDescription(
        key="sensitivity_humidity",
        entity_name="Sensitivity Humidity",
        translation_key="sensitivity_humidity",
        category=EntityCategory.CONFIG,
        icon="mdi:water-percent",
        options=OPTIONS["sensitivity"],
    ),
    SelectDescription(
        key="automatic_cycles",
        entity_name="Airing Function Cycle",
        translation_key="automatic_cycles",
        category=EntityCategory.CONFIG,
        icon="mdi:fan-auto",
        options=OPTIONS["automatic_cycles"],
    ),
    SelectDescription(
        key="boostmodesecwrite",
        entity_name="Boost Duration",
        translation_key="boostmodesecwrite",
        category=EntityCategory.CONFIG,
        icon="mdi:timer-outline",
        options=OPTIONS["boostmodesecwrite"],
    ),
    SelectDescription(
        key="boostmodespeedwrite",
        entity_name="Fan Speed Boost",
        translation_key="boostmodespeedwrite",
        category=EntityCategory.CONFIG,
        icon="mdi:speedometer",
        options=OPTIONS["fanspeedsettings_rpms"],
    ),
    SelectDescription(
        key="fanspeed_humidity",
        entity_name="Fan Speed Humidity",
        translation_key="fanspeed_humidity",
        category=EntityCategory.CONFIG,
        icon="mdi:speedometer",
        options=OPTIONS["fanspeedsettings_rpms"],
    ),
    SelectDescription(
        key="fanspeed_light",
        entity_name="Fan Speed Light",
        translation_key="fanspeed_light",
        category=EntityCategory.CONFIG,
        icon="mdi:speedometer",
        options=OPTIONS["fanspeedsettings_rpms"],
    ),
    SelectDescription(
        key="fanspeed_trickle",
        entity_name="Fan Speed Trickle",
        translation_key="fanspeed_trickle",
        category=EntityCategory.CONFIG,
        icon="mdi:speedometer",
        options=OPTIONS["fanspeedsettings_rpms"],
    ),
    SelectDescription(
        key="sensitivity_light",
        entity_name="Sensitivity Light",
        translation_key="sensitivity_light",
        category=EntityCategory.CONFIG,
        icon="mdi:brightness-5",
        options=OPTIONS["sensitivity"],
    ),
    SelectDescription(
        key="lightsensorsettings_delayedstart",
        entity_name="Light Sensor Delayed Start",
        translation_key="lightsensorsettings_delayedstart",
        category=EntityCategory.CONFIG,
        icon="mdi:timer-outline",
        options=OPTIONS["lightsensorsettings_delayedstart"],
    ),
    SelectDescription(
        key="lightsensorsettings_runningtime",
        entity_name="Light Sensor Running Time",
        translation_key="lightsensorsettings_runningtime",
        category=EntityCategory.CONFIG,
        icon="mdi:timer-outline",
        options=OPTIONS["lightsensorsettings_runningtime"],
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up selects from a config entry."""
    entities = []
    for _device_id, device_name, coordinator in iter_entry_devices(config_entry):
        _LOGGER.debug("Starting Svara selects: %s", device_name)
        for entity_description in ENTITIES:
            if entity_description.key in {"boostmodesecwrite", "boostmodespeedwrite"}:
                entities.append(SvaraRestoreSelectEntity(coordinator, entity_description))
            else:
                entities.append(SvaraSelectEntity(coordinator, entity_description))
    async_add_devices(entities, True)


class SvaraSelectEntity(SvaraVentAxiaEntity, SelectEntity):
    """Representation of a Svara select entity."""

    def __init__(self, coordinator, entity_description):
        super().__init__(coordinator, entity_description)
        self._options = entity_description.options

    @property
    def current_option(self):
        try:
            option_index = self.coordinator.get_data(self._key)
            return self._options[str(option_index)]
        except Exception:
            return "Unknown"

    @property
    def options(self):
        return list(self._options.values())

    async def async_select_option(self, option):
        old_value = self.coordinator.get_data(self._key)
        selected_value = None
        for key, value in self._options.items():
            if value == option:
                selected_value = key
                break
        if selected_value is None:
            return

        self.coordinator.set_data(self._key, selected_value)
        if not await self.coordinator.write_data(self._key):
            self.coordinator.set_data(self._key, old_value)
        self.async_schedule_update_ha_state(force_refresh=False)


class SvaraRestoreSelectEntity(SvaraSelectEntity, RestoreEntity):
    """Select entity that persists local values across restarts."""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if not last_state or last_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        for key, value in self._options.items():
            if value == last_state.state:
                self.coordinator.set_data(self._key, key)
                break

    async def async_select_option(self, option):
        for key, value in self._options.items():
            if value == option:
                self.coordinator.set_data(self._key, key)
                self.async_schedule_update_ha_state(force_refresh=False)
                return
