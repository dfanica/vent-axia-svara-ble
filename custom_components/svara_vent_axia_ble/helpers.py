from .const import (
    CONF_MAC,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_FAST,
)
from .coordinator_svara import SvaraCoordinator


def getCoordinator(hass, entry, device_data, dev):
    """Create the coordinator for a Svara device."""
    options = entry.options
    return SvaraCoordinator(
        hass,
        dev,
        device_data[CONF_MAC],
        device_data[CONF_PIN],
        options.get(CONF_SCAN_INTERVAL, device_data[CONF_SCAN_INTERVAL]),
        options.get(CONF_SCAN_INTERVAL_FAST, device_data[CONF_SCAN_INTERVAL_FAST]),
        True,
    )
