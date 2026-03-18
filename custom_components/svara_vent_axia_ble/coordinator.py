"""Base coordinator for the Vent-Axia Svara integration."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

from abc import ABC, abstractmethod
from typing import Any

import async_timeout

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .devices.base_device import BaseDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_WRITE_STATE: dict[str, Any] = {
    "boostmodespeedwrite": 2400,
    "boostmodesecwrite": 600,
}


class BaseCoordinator(DataUpdateCoordinator, ABC):
    """Shared coordinator behavior for Svara BLE devices."""

    def __init__(
        self,
        hass,
        device: DeviceEntry,
        model: str,
        scan_interval: int,
        scan_interval_fast: int,
    ):
        """Initialize coordinator parent"""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=model + ": " + device.name,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=dt.timedelta(seconds=scan_interval),
        )

        self._fast_poll_enabled = False
        self._fast_poll_count = 0
        self._normal_poll_interval = scan_interval
        self._fast_poll_interval = scan_interval_fast

        self._device_info_loaded = False
        self._last_config_refresh_date: dt.date | None = None

        self._fan: BaseDevice | None = None
        self._device = device
        self._model = model

        self._connection_failures = 0
        self._max_connection_failures = 5
        self._max_backoff = 300
        self._backoff_multiplier = 2
        self._reconnection_task: asyncio.Task[None] | None = None

        self._state: dict[str, Any] = DEFAULT_WRITE_STATE.copy()

    @property
    def fan(self) -> BaseDevice:
        return self._fan

    @property
    def device_id(self):
        return self._device.id

    @property
    def devicename(self):
        return self._device.name

    @property
    def identifiers(self):
        return self._device.identifiers

    def _set_fast_poll_mode(self) -> None:
        """Enable fast polling only if device is connected."""
        if not self._fan or not self._fan.isConnected():
            _LOGGER.debug("Cannot enable fast poll mode - device not connected")
            return

        _LOGGER.debug("Enabling fast poll mode")
        self._fast_poll_enabled = True
        self._fast_poll_count = 0
        self.update_interval = dt.timedelta(seconds=self._fast_poll_interval)

    def setFastPollMode(self):
        """Backward-compatible wrapper for fast poll mode."""
        self._set_fast_poll_mode()

    def _set_normal_poll_mode(self) -> None:
        """Restore normal polling interval with failure-based backoff."""
        _LOGGER.debug("Enabling normal poll mode")
        self._fast_poll_enabled = False
        interval = self._normal_poll_interval
        if self._connection_failures > 0:
            interval = min(
                self._normal_poll_interval * (2**self._connection_failures),
                self._max_backoff,
            )
        self.update_interval = dt.timedelta(seconds=interval)

    def setNormalPollMode(self):
        """Backward-compatible wrapper for normal poll mode."""
        self._set_normal_poll_mode()

    def _reset_connection_failures(self, *, log_validation: bool = False) -> None:
        """Reset failure counters after a successful operation."""
        if self._connection_failures > 0 and log_validation:
            _LOGGER.info(
                "Connection to %s validated, resetting failure count",
                self.devicename,
            )
        self._connection_failures = 0

    def _increment_connection_failures(self) -> None:
        """Track a failed connection or read attempt."""
        self._connection_failures += 1

    def _next_reconnect_delay(self) -> int:
        """Return reconnect backoff delay in seconds."""
        return min(
            self._fast_poll_interval
            * (self._backoff_multiplier ** (self._connection_failures - 1)),
            self._max_backoff,
        )

    async def disconnect(self):
        """Safely disconnect from device."""
        if self._reconnection_task and not self._reconnection_task.done():
            self._reconnection_task.cancel()
            self._reconnection_task = None

        if self._fan:
            await self._fan.disconnect()

    async def _on_device_disconnect(self):
        """Called when device disconnects unexpectedly."""
        _LOGGER.warning("Device %s disconnected unexpectedly", self.devicename)
        self._increment_connection_failures()

        if self._fast_poll_enabled:
            self._set_normal_poll_mode()

        if not self._reconnection_task or self._reconnection_task.done():
            self._reconnection_task = asyncio.create_task(self._background_reconnect())

    async def _background_reconnect(self):
        """Background task to reconnect to device with exponential backoff."""
        while (
            self._connection_failures > 0
            and self._connection_failures < self._max_connection_failures
        ):
            backoff_time = self._next_reconnect_delay()
            _LOGGER.debug(
                "Attempting reconnection to %s in %d seconds (attempt %d)",
                self.devicename,
                backoff_time,
                self._connection_failures,
            )

            await asyncio.sleep(backoff_time)

            try:
                if await self._safe_connect():
                    _LOGGER.info("Successfully reconnected to %s", self.devicename)
                    self._reset_connection_failures()
                    self._set_normal_poll_mode()
                    await self._async_update_data()
                    return
                self._increment_connection_failures()
            except Exception as err:
                _LOGGER.debug("Reconnection attempt failed: %s", err)
                self._increment_connection_failures()

        if self._connection_failures >= self._max_connection_failures:
            _LOGGER.error(
                "Failed to reconnect to %s after %d attempts, giving up",
                self.devicename,
                self._max_connection_failures,
            )

    async def _safe_connect(self) -> bool:
        """Try to connect with improved error handling and validation."""
        if not self._fan:
            return False

        if self._fan.isConnected():
            if await self._fan.validate_connection():
                self._reset_connection_failures(log_validation=True)
                return True

            _LOGGER.debug("Existing connection failed validation, reconnecting")

        try:
            timeout = 45 if self._connection_failures > 2 else 30
            if await self._fan.connect(timeout=timeout):
                if await self._fan.validate_connection():
                    self._reset_connection_failures()
                    return True

                _LOGGER.warning("New connection failed validation")
                return False

            return False
        except Exception as err:
            _LOGGER.debug("Connection attempt failed: %s", err)
            return False

    async def _async_update_data(self):
        _LOGGER.debug("Coordinator updating data!!")

        self._update_poll_counter()

        if self._connection_failures >= self._max_connection_failures:
            _LOGGER.debug("Skipping update due to too many connection failures")
            return

        try:
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            _LOGGER.debug("Update cancelled before starting")
            raise

        if not self._device_info_loaded:
            try:
                async with async_timeout.timeout(45):
                    if await self.read_deviceinfo(disconnect=False):
                        await self._async_update_device_info()
                        self._device_info_loaded = True
            except asyncio.CancelledError:
                _LOGGER.debug("Device info loading was cancelled")
                raise
            except Exception as err:
                _LOGGER.debug("Failed when loading device information: %s", str(err))
                self._increment_connection_failures()

        if dt.datetime.now().date() != self._last_config_refresh_date:
            try:
                async with async_timeout.timeout(45):
                    if await self.read_configdata(disconnect=False):
                        self._last_config_refresh_date = dt.datetime.now().date()
            except asyncio.CancelledError:
                _LOGGER.debug("Config data loading was cancelled")
                raise
            except Exception as err:
                _LOGGER.debug("Failed when loading config data: %s", str(err))
                self._increment_connection_failures()

        try:
            async with async_timeout.timeout(30):
                success = await self.read_sensordata(disconnect=not self._fast_poll_enabled)
                if success:
                    if self._connection_failures > 0:
                        _LOGGER.debug("Successful data read, resetting connection failures")
                        self._reset_connection_failures()
                        self._set_normal_poll_mode()
                else:
                    self._increment_connection_failures()
        except asyncio.CancelledError:
            _LOGGER.debug("Sensor data loading was cancelled")
            raise
        except Exception as err:
            _LOGGER.debug("Failed when fetching sensordata: %s", str(err))
            self._increment_connection_failures()

    async def _async_update_device_info(self) -> None:
        device_registry = dr.async_get(self.hass)
        device_registry.async_update_device(
            self.device_id,
            manufacturer=self.get_data("manufacturer"),
            model=self.get_data("model"),
            hw_version=self.get_data("hw_rev"),
            sw_version=self.get_data("sw_rev"),
        )
        _LOGGER.debug("Updated device data for: %s", self.devicename)

    def _update_poll_counter(self):
        if self._fast_poll_enabled:
            self._fast_poll_count += 1
            if self._fast_poll_count > 10:
                self._set_normal_poll_mode()

    def get_data(self, key: str) -> Any | None:
        return self._state.get(key)

    def set_data(self, key: str, value: Any) -> None:
        _LOGGER.debug("Set_Data: %s %s", key, value)
        self._state[key] = value

    async def read_deviceinfo(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading device information")
        try:
            if not await self._safe_connect():
                raise Exception("Not connected!")
        except Exception as err:
            _LOGGER.warning("Error when fetching device info: %s", str(err))
            return False

        try:
            self._state["manufacturer"] = await self._fan.getManufacturer()
        except Exception as err:
            _LOGGER.debug("Couldn't read manufacturer! %s", str(err))
        try:
            self._state["model"] = await self._fan.getDeviceName()
        except Exception as err:
            _LOGGER.debug("Couldn't read device name! %s", str(err))
        try:
            self._state["fw_rev"] = await self._fan.getFirmwareRevision()
        except Exception as err:
            _LOGGER.debug("Couldn't read firmware revision! %s", str(err))
        try:
            self._state["hw_rev"] = await self._fan.getHardwareRevision()
        except Exception as err:
            _LOGGER.debug("Couldn't read hardware revision! %s", str(err))
        try:
            self._state["sw_rev"] = await self._fan.getSoftwareRevision()
        except Exception as err:
            _LOGGER.debug("Couldn't read software revision! %s", str(err))

        if not self._fan.isConnected():
            return False
        elif disconnect:
            await self._fan.disconnect()
        return True

    @abstractmethod
    async def read_sensordata(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading sensor data")

    @abstractmethod
    async def write_data(self, key) -> bool:
        _LOGGER.debug("Write_Data: %s", key)

    @abstractmethod
    async def read_configdata(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading config data")
