"""Config flow for the Vent-Axia Svara integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .devices.base_device import BaseDevice
from .const import (
    CONF_CLOCK_SYNC,
    CONF_INTEGRATION_TITLE,
    CONF_MAC,
    CONF_NAME,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_FAST,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_FAST,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_ENTRY_NAME = "Vent-Axia Svara"

DEVICE_DATA = {
    CONF_NAME: "",
    CONF_MAC: "",
    CONF_PIN: "",
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_FAST: DEFAULT_SCAN_INTERVAL_FAST,
}


class SvaraVentAxiaConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle config flow for the integration."""

    VERSION = 1

    def __init__(self) -> None:
        self.device_data = DEVICE_DATA.copy()
        self.accept_wrong_pin = False

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return SvaraVentAxiaOptionsFlowHandler(config_entry)

    def get_main_entry(self) -> ConfigEntry | None:
        """Return the singleton config entry for this integration."""
        if self.hass is None:
            return None
        entries = self.hass.config_entries.async_entries(DOMAIN)
        return entries[0] if entries else None

    def device_exists(self, device_key: str) -> bool:
        """Check whether a device already exists in the main entry."""
        entry = self.get_main_entry()
        return bool(entry and device_key in entry.data.get(CONF_DEVICES, {}))

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create the first device or add another device to the existing entry."""
        return await self.async_step_add_device(user_input)

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a device during initial setup."""
        errors: dict[str, str] = {}
        main_entry = self.get_main_entry()

        if user_input is not None:
            normalized_input = normalize_device_input(user_input)

            if self.device_exists(normalized_input[CONF_MAC]):
                return self.async_abort(
                    reason="device_already_configured",
                    description_placeholders={"dev_name": normalized_input[CONF_MAC]},
                )

            if await verify_device(self.hass, normalized_input, self.accept_wrong_pin):
                if main_entry is not None:
                    devices = dict(main_entry.data[CONF_DEVICES])
                    devices[normalized_input[CONF_MAC]] = normalized_input
                    self.hass.config_entries.async_update_entry(
                        main_entry, data={CONF_DEVICES: devices}
                    )
                    await self.hass.config_entries.async_reload(main_entry.entry_id)
                    return self.async_abort(
                        reason="add_success",
                        description_placeholders={"dev_name": normalized_input[CONF_NAME]},
                    )

                await self.async_set_unique_id(CONFIG_ENTRY_NAME)
                self._abort_if_unique_id_configured()
                data = {CONF_DEVICES: {normalized_input[CONF_MAC]: normalized_input}}
                return self.async_create_entry(title=CONFIG_ENTRY_NAME, data=data)

            self.device_data = normalized_input
            errors["base"] = "wrong_pin_or_cannot_connect"

        return self.async_show_form(
            step_id="add_device",
            data_schema=get_device_schema_add(self.device_data),
            errors=errors,
            description_placeholders={
                "entry_action": "Add another fan" if main_entry is not None else "Add the first fan"
            },
        )


class SvaraVentAxiaOptionsFlowHandler(OptionsFlow):
    """Handle integration options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Update integration-wide options."""
        if user_input is not None:
            title = str(user_input[CONF_INTEGRATION_TITLE]).strip()
            if title:
                options = {
                    CONF_CLOCK_SYNC: bool(user_input[CONF_CLOCK_SYNC]),
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_SCAN_INTERVAL_FAST: int(user_input[CONF_SCAN_INTERVAL_FAST]),
                }
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    title=title,
                    options=options,
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=get_options_schema(self._config_entry),
            description_placeholders={
                "device_count": str(len(self._config_entry.data[CONF_DEVICES]))
            },
        )


def get_options_schema(config_entry: ConfigEntry) -> vol.Schema:
    """Schema for integration-level options shared by all configured fans."""
    options = config_entry.options
    devices = config_entry.data.get(CONF_DEVICES, {})
    first_device = next(iter(devices.values()), DEVICE_DATA)

    return vol.Schema(
        {
            vol.Required(
                CONF_INTEGRATION_TITLE,
                default=config_entry.title or CONFIG_ENTRY_NAME,
            ): cv.string,
            vol.Required(
                CONF_CLOCK_SYNC,
                default=options.get(CONF_CLOCK_SYNC, True),
            ): cv.boolean,
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=options.get(
                    CONF_SCAN_INTERVAL,
                    first_device.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=999)),
            vol.Required(
                CONF_SCAN_INTERVAL_FAST,
                default=options.get(
                    CONF_SCAN_INTERVAL_FAST,
                    first_device.get(
                        CONF_SCAN_INTERVAL_FAST,
                        DEFAULT_SCAN_INTERVAL_FAST,
                    ),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=999)),
        }
    )


def get_device_schema_add(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Schema for adding a device."""
    return get_device_schema(user_input)


def get_device_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Schema for adding or editing a device."""
    user_input = user_input or DEVICE_DATA
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=user_input[CONF_NAME]): cv.string,
            vol.Required(CONF_MAC, default=user_input[CONF_MAC]): cv.string,
            vol.Required(CONF_PIN, default=user_input[CONF_PIN]): cv.string,
            vol.Optional(
                CONF_SCAN_INTERVAL, default=user_input[CONF_SCAN_INTERVAL]
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=999)),
            vol.Optional(
                CONF_SCAN_INTERVAL_FAST, default=user_input[CONF_SCAN_INTERVAL_FAST]
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=999)),
        }
    )


def normalize_device_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize MAC and persist expected fields."""
    normalized = DEVICE_DATA.copy()
    normalized.update(user_input)
    normalized[CONF_MAC] = dr.format_mac(normalized[CONF_MAC])
    normalized[CONF_PIN] = str(normalized[CONF_PIN]).strip()
    normalized[CONF_NAME] = str(normalized[CONF_NAME]).strip()
    return normalized


async def verify_device(
    hass: HomeAssistant, user_input: dict[str, Any], accept_wrong_pin: bool
) -> bool:
    """Connect to the device and validate the supplied PIN."""
    fan = BaseDevice(hass, user_input[CONF_MAC], user_input[CONF_PIN])
    _LOGGER.warning(
        "Starting diagnostic verification for %s (%s)",
        user_input[CONF_NAME],
        user_input[CONF_MAC],
    )
    if not await fan.connect():
        _LOGGER.warning(
            "Diagnostic verification could not connect to %s",
            user_input[CONF_MAC],
        )
        return False

    try:
        await fan.log_diagnostics("config_flow_pre_auth")
        await fan.setAuth(user_input[CONF_PIN])
        pin_valid = accept_wrong_pin or await fan.checkAuth()
        _LOGGER.warning(
            "PIN validation result for %s (%s): %s",
            user_input[CONF_NAME],
            user_input[CONF_MAC],
            pin_valid,
        )
        await fan.log_diagnostics("config_flow_post_auth")
        return pin_valid
    except Exception:
        _LOGGER.debug(
            "Failed to validate device %s", user_input[CONF_MAC], exc_info=True
        )
        return False
    finally:
        await fan.disconnect()
