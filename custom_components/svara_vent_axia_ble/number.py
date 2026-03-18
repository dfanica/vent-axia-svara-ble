import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up numbers from a config entry."""
    _LOGGER.debug("No number entities exposed for this integration")
    async_add_devices([], True)
