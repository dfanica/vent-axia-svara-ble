import logging

from homeassistant.util import dt as dt_util

from .coordinator import BaseCoordinator
from .devices.svara import SvaraDevice

_LOGGER = logging.getLogger(__name__)


class SvaraCoordinator(BaseCoordinator):
    """Coordinator for Vent-Axia Svara devices."""

    def __init__(
        self,
        hass,
        device,
        mac,
        pin,
        scan_interval,
        scan_interval_fast,
        clock_sync_enabled,
    ):
        super().__init__(
            hass,
            device,
            "Svara",
            scan_interval,
            scan_interval_fast,
        )

        _LOGGER.debug("Initializing Svara device")
        self._fan = SvaraDevice(hass, mac, pin)
        self._fan.set_disconnect_callback(self._on_device_disconnect)
        self._initial_clock_sync_attempted = False
        self._clock_sync_enabled = clock_sync_enabled
        self._initial_alias_sync_attempted = False
        self._last_periodic_clock_sync = None

    async def _update_diagnostics_state(self) -> None:
        """Refresh cached diagnostic values exposed through Home Assistant."""
        diagnostics = await self._fan.collect_diagnostics()
        self._state["diagnostics"] = diagnostics
        for key, value in diagnostics.items():
            self._state[key] = value

    async def _attempt_initial_alias_sync(self) -> None:
        """Sync the device alias to the Home Assistant device name once."""
        if self._initial_alias_sync_attempted:
            return

        self._initial_alias_sync_attempted = True

        desired_alias = self.devicename[:20]
        current_alias = self._state.get("alias")
        if current_alias == desired_alias:
            return

        _LOGGER.warning(
            "Attempting alias sync for %s: %r -> %r",
            self.devicename,
            current_alias,
            desired_alias,
        )
        await self._fan.setAlias(desired_alias)
        await self._update_diagnostics_state()
        await self._fan.log_diagnostics("after_alias_sync")

    async def _attempt_initial_clock_sync(self) -> None:
        """Perform a one-shot clock sync experiment during early provisioning."""
        if not self._clock_sync_enabled:
            return

        if self._initial_clock_sync_attempted:
            return

        self._initial_clock_sync_attempted = True
        await self._fan.log_diagnostics("before_clock_sync")

        now = dt_util.now()
        _LOGGER.warning(
            "Attempting initial clock sync for %s to %s",
            self.devicename,
            now.isoformat(),
        )
        await self._write_current_time(now, authorize=False)
        await self._fan.log_diagnostics("after_clock_sync")

    async def _maybe_sync_periodic_clock(self) -> None:
        """Refresh the device clock on the normal polling cadence."""
        if not self._clock_sync_enabled:
            return

        try:
            await self._sync_clock()
        except Exception as err:
            _LOGGER.debug(
                "Periodic clock sync failed for %s without failing sensor refresh: %s",
                self.devicename,
                err,
            )

    async def _write_current_time(self, now, *, authorize: bool) -> None:
        """Write a specific timestamp to the device and track last sync."""
        if authorize:
            await self._fan.authorize()
        await self._fan.setTime(
            now.isoweekday(),
            now.hour,
            now.minute,
            now.second,
        )
        self._last_periodic_clock_sync = now

    async def _sync_clock(self) -> None:
        """Write the current Home Assistant time to the device."""
        now = dt_util.now()
        await self._write_current_time(now, authorize=True)

    async def async_sync_clock(self) -> bool:
        """Synchronize the device clock on demand."""
        try:
            if not await self._safe_connect():
                _LOGGER.debug("Cannot sync clock: not connected to %s", self.devicename)
                return False

            now = dt_util.now()
            _LOGGER.debug("Syncing device clock for %s to %s", self.devicename, now.isoformat())
            await self._sync_clock()
            await self._update_diagnostics_state()
            self.setFastPollMode()
            return True
        except Exception as err:
            _LOGGER.debug("Error syncing clock for %s: %s", self.devicename, err)
            return False

    async def read_sensordata(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading Svara sensor data")
        try:
            if not await self._safe_connect():
                _LOGGER.debug("Cannot read sensor data: not connected to %s", self.devicename)
                return False

            sensor_state = await self._fan.read_sensor_state()
            if not sensor_state:
                _LOGGER.debug("Could not read device state")
                return False

            self._state.update(sensor_state)

            if disconnect:
                last_sync = self._last_periodic_clock_sync
                now = dt_util.now()
                if (
                    last_sync is None
                    or (now - last_sync).total_seconds() >= self._normal_poll_interval
                ):
                    _LOGGER.debug(
                        "Syncing device clock for %s on polling cadence to %s",
                        self.devicename,
                        now.isoformat(),
                    )
                    await self._maybe_sync_periodic_clock()

            if disconnect:
                await self._fan.disconnect()
            return True
        except Exception as err:
            _LOGGER.debug("Error reading sensor data from %s: %s", self.devicename, err)
            return False

    async def write_data(self, key) -> bool:
        _LOGGER.debug("Write_Data: %s", key)
        try:
            if not await self._safe_connect():
                _LOGGER.debug("Cannot write data: not connected to %s", self.devicename)
                return False

            await self._fan.authorize()
            await self._update_diagnostics_state()
            await self._fan.log_diagnostics(f"before_write:{key}")
            if not await self._fan.write_state_key(key, self._state):
                return False
            await self._update_diagnostics_state()
            await self._fan.log_diagnostics(f"after_write:{key}")

            self.setFastPollMode()
            return True
        except Exception as err:
            _LOGGER.debug("Error writing data to %s: %s", self.devicename, err)
            return False

    async def read_configdata(self, disconnect=False) -> bool:
        try:
            if not await self._safe_connect():
                raise Exception("Not connected")

            await self._fan.authorize()
            await self._update_diagnostics_state()
            await self._fan.log_diagnostics("config_refresh_before_read")
            await self._attempt_initial_alias_sync()
            await self._attempt_initial_clock_sync()
            self._state.update(await self._fan.read_config_state())
            await self._update_diagnostics_state()
            await self._fan.log_diagnostics("config_refresh_after_read")

            if disconnect:
                await self._fan.disconnect()
            return True
        except Exception as err:
            _LOGGER.debug("Error reading config data from %s: %s", self.devicename, err)
            return False
