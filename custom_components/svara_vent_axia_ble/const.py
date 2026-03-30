from homeassistant.const import Platform

DOMAIN = "svara_vent_axia_ble"

PLATFORMS = [
    Platform.BUTTON,
    Platform.TIME,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
]

CONF_ACTION = "action"
CONF_ADD_DEVICE = "add_device"
CONF_CLOCK_SYNC = "clock_sync"
CONF_EDIT_DEVICE = "edit_device"
CONF_INTEGRATION_TITLE = "integration_title"
CONF_REMOVE_DEVICE = "remove_device"

CONF_NAME = "name"
CONF_MAC = "mac"
CONF_PIN = "pin"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SCAN_INTERVAL_FAST = "scan_interval_fast"

DEFAULT_SCAN_INTERVAL = 300
DEFAULT_SCAN_INTERVAL_FAST = 5
