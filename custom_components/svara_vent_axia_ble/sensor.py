import logging
from datetime import datetime, time, timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util

from .runtime import iter_entry_devices
from .entity import SvaraVentAxiaEntity
from .entity_descriptions import SensorDescription

_LOGGER = logging.getLogger(__name__)


def _infer_clock_datetime(value: dict[str, int]) -> datetime | None:
    """Infer a local datetime from the device weekday and time."""
    try:
        weekday = int(value["day_of_week"])
        hour = int(value["hour"])
        minute = int(value["minute"])
        second = int(value["second"])
    except (KeyError, TypeError, ValueError):
        return None

    if weekday < 1 or weekday > 7:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59 or second < 0 or second > 59:
        return None

    now = dt_util.now()
    day_delta = weekday - now.isoweekday()
    if day_delta > 3:
        day_delta -= 7
    elif day_delta < -3:
        day_delta += 7

    inferred_date = now.date() + timedelta(days=day_delta)
    return datetime.combine(
        inferred_date,
        time(hour=hour, minute=minute, second=second),
        tzinfo=now.tzinfo,
    )

ENTITIES = [
    SensorDescription(
        key="humidity",
        entity_name="Humidity",
        translation_key="humidity",
        units=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    SensorDescription(
        key="temperature",
        entity_name="Temperature",
        translation_key="temperature",
        units=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorDescription(
        key="light",
        entity_name="Light",
        translation_key="light",
        units=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
    ),
    SensorDescription(
        key="rpm",
        entity_name="Fan Speed",
        translation_key="rpm",
        units=REVOLUTIONS_PER_MINUTE,
        icon="mdi:speedometer",
    ),
    SensorDescription(
        key="flow",
        entity_name="Flow",
        translation_key="flow",
        units=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:weather-windy",
    ),
    SensorDescription(key="state", entity_name="Fan State", translation_key="state"),
    SensorDescription(
        key="mode",
        entity_name="Mode",
        translation_key="mode",
        category=EntityCategory.DIAGNOSTIC,
    ),
    SensorDescription(
        key="pin_confirmed",
        entity_name="PIN Confirmed",
        translation_key="pin_confirmed",
        category=EntityCategory.DIAGNOSTIC,
    ),
    SensorDescription(
        key="led_raw",
        entity_name="LED Raw",
        translation_key="led_raw",
        category=EntityCategory.DIAGNOSTIC,
    ),
    SensorDescription(
        key="status_raw",
        entity_name="Status Raw",
        translation_key="status_raw",
        category=EntityCategory.DIAGNOSTIC,
    ),
    SensorDescription(
        key="factory_settings_changed",
        entity_name="Factory Settings Changed",
        translation_key="factory_settings_changed",
        category=EntityCategory.DIAGNOSTIC,
    ),
    SensorDescription(
        key="clock",
        entity_name="Clock",
        translation_key="clock",
        category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorDescription(
        key="alias",
        entity_name="Alias",
        translation_key="alias",
        category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up sensors from a config entry."""
    entities = []
    for _device_id, device_name, coordinator in iter_entry_devices(config_entry):
        _LOGGER.debug("Starting Svara sensors: %s", device_name)
        for entity_description in ENTITIES:
            entities.append(SvaraSensorEntity(coordinator, entity_description))
    async_add_devices(entities, True)


class SvaraSensorEntity(SvaraVentAxiaEntity, SensorEntity):
    """Representation of a Svara sensor."""

    def __init__(self, coordinator, entity_description):
        super().__init__(coordinator, entity_description)
        self._attr_device_class = entity_description.device_class
        self._attr_native_unit_of_measurement = entity_description.units

    @property
    def native_value(self):
        value = self.coordinator.get_data(self._key)
        if isinstance(value, bool):
            return str(value)
        if self._key == "clock" and isinstance(value, dict):
            return _infer_clock_datetime(value)
        return value

    @property
    def extra_state_attributes(self):
        """Return raw diagnostic values for the mode diagnostic entity."""
        if self._key != "mode":
            return {}

        diagnostics = self.coordinator.get_data("diagnostics")
        return diagnostics if isinstance(diagnostics, dict) else {}
