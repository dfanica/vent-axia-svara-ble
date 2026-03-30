from .characteristics import *

from homeassistant.components import bluetooth
from struct import pack, unpack
import inspect
import datetime
from bleak.exc import BleakError
import binascii
from collections import namedtuple
import logging
import asyncio
from bleak_retry_connector import (
    establish_connection,
    BleakClientWithServiceCache,
    close_stale_connections,
)


_LOGGER = logging.getLogger(__name__)

Time = namedtuple("Time", "DayOfWeek Hour Minute Second")
BoostMode = namedtuple("BoostMode", "OnOff Speed Seconds")


class BaseDevice:
    def __init__(self, hass, mac, pin):
        self._hass = hass
        self._mac = mac
        self._pin = pin
        self._client: BleakClientWithServiceCache | None = None
        self._connect_lock = asyncio.Lock()
        self._disconnect_callback = None
        self._expected_disconnect = False
        self._expected_disconnect_reset_task: asyncio.Task[None] | None = None
        # Characteristic UUIDs (centralized in characteristics.py ideally)
        self.chars = {
            CHARACTERISTIC_APPEARANCE: "00002a01-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_BOOST: "118c949c-28c8-4139-b0b3-36657fd055a9",
            CHARACTERISTIC_CLOCK: "6dec478e-ae0b-4186-9d82-13dda03c0682",
            CHARACTERISTIC_DEVICE_NAME: "00002a00-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_FACTORY_SETTINGS_CHANGED: "63b04af9-24c0-4e5d-a69c-94eb9c5707b4",
            CHARACTERISTIC_FAN_DESCRIPTION: "b85fa07a-9382-4838-871c-81d045dcc2ff",
            CHARACTERISTIC_FIRMWARE_REVISION: "00002a26-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_HARDWARE_REVISION: "00002a27-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_SOFTWARE_REVISION: "00002a28-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_LED: "8b850c04-dc18-44d2-9501-7662d65ba36e",
            CHARACTERISTIC_MANUFACTURER_NAME: "00002a29-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_MODE: "90cabcd1-bcda-4167-85d8-16dcd8ab6a6b",
            CHARACTERISTIC_MODEL_NUMBER: "00002a24-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_PIN_CODE: "4cad343a-209a-40b7-b911-4d9b3df569b2",
            CHARACTERISTIC_PIN_CONFIRMATION: "d1ae6b70-ee12-4f6d-b166-d2063dcaffe1",
            CHARACTERISTIC_RESET: "ff5f7c4f-2606-4c69-b360-15aaea58ad5f",
            CHARACTERISTIC_SENSOR_DATA: "528b80e8-c47a-4c0a-bdf1-916a7748f412",
            CHARACTERISTIC_SERIAL_NUMBER: "00002a25-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_STATUS: "25a824ad-3021-4de9-9f2f-60cf8d17bded",
        }

    def set_disconnect_callback(self, callback):
        """Set callback to be called when device disconnects unexpectedly."""
        self._disconnect_callback = callback

    def _handle_disconnect(self, client):
        """Handle unexpected disconnection.

        Only logs the disconnection for debugging purposes.
        Reconnection is handled lazily on the next poll cycle.
        """
        if client is not None and self._client is not None and client is not self._client:
            _LOGGER.debug(
                "Ignoring disconnect callback from superseded client for %s",
                self._mac,
            )
            return

        _LOGGER.debug("Device %s disconnected, will reconnect on next poll", self._mac)
        self._client = None
        if self._expected_disconnect:
            self._cancel_expected_disconnect_reset()
            self._expected_disconnect = False
            return
        if self._disconnect_callback is None:
            return

        result = self._disconnect_callback()
        if inspect.isawaitable(result):
            asyncio.create_task(result)

    async def authorize(self):
        await self.setAuth(self._pin)

    def _cancel_expected_disconnect_reset(self) -> None:
        """Cancel any pending expected-disconnect cleanup task."""
        if (
            self._expected_disconnect_reset_task
            and not self._expected_disconnect_reset_task.done()
        ):
            self._expected_disconnect_reset_task.cancel()
        self._expected_disconnect_reset_task = None

    def _schedule_expected_disconnect_reset(self) -> None:
        """Clear the expected-disconnect marker if no callback arrives."""
        self._cancel_expected_disconnect_reset()

        async def _reset_flag() -> None:
            try:
                await asyncio.sleep(1)
                self._expected_disconnect = False
            finally:
                self._expected_disconnect_reset_task = None

        self._expected_disconnect_reset_task = asyncio.create_task(_reset_flag())

    async def connect(self, timeout: int = 45) -> bool:
        """Establish a reliable connection using bleak-retry-connector."""
        async with self._connect_lock:
            # Already connected (or another caller just connected while we waited)?
            if self._client and self._client.is_connected:
                return True

            try:
                device = bluetooth.async_ble_device_from_address(self._hass, self._mac.upper())
                if not device:
                    raise BleakError(f"Device {self._mac} not found")

                try:
                    await close_stale_connections()
                except Exception:
                    pass

                self._client = await establish_connection(
                    BleakClientWithServiceCache,
                    device,
                    name=getattr(self, "name", self._mac),
                    disconnected_callback=self._handle_disconnect,
                    use_services_cache=True,
                    max_attempts=5,
                    retry_interval=1.0,
                    timeout=timeout,
                )
                self._cancel_expected_disconnect_reset()
                self._expected_disconnect = False
                _LOGGER.debug("Connected to %s", self._mac)
                return True
            except Exception as err:
                _LOGGER.warning("Failed to connect %s: %s", self._mac, err)
                self._client = None
                return False

    async def disconnect(self) -> None:
        if self._client:
            try:
                self._expected_disconnect = True
                await self._client.disconnect()
                self._schedule_expected_disconnect_reset()
            except Exception as e:
                _LOGGER.warning("Error disconnecting %s: %s", self._mac, e)
                self._schedule_expected_disconnect_reset()
            finally:
                self._client = None

    async def _with_disconnect_on_error(self, coro):
        try:
            return await coro
        except Exception:
            _LOGGER.debug("GATT operation failed; disconnecting", exc_info=True)
            await self.disconnect()
            raise

    async def pair(self) -> str:
        raise NotImplementedError("Pairing not availiable for this device type.")

    def isConnected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def validate_connection(self) -> bool:
        """Validate that the connection is still working by reading a basic characteristic."""
        if not self.isConnected():
            return False

        try:
            # Try to read device name as a connection health check
            await asyncio.wait_for(self._client.read_gatt_char(self.chars[CHARACTERISTIC_DEVICE_NAME]), timeout=5.0)
            return True
        except Exception as e:
            _LOGGER.debug("Connection validation failed for %s: %s", self._mac, e)
            # Mark as disconnected so next operation will reconnect
            self._client = None
            return False

    def _bToStr(self, val) -> str:
        return binascii.b2a_hex(val).decode("utf-8")

    async def _readUUID(self, uuid) -> bytearray:
        if not self._client:
            raise BleakError("Client not initialized")
        return await self._with_disconnect_on_error(
            self._client.read_gatt_char(uuid)
        )

    async def _readHandle(self, handle) -> bytearray:
        if not self._client:
            raise BleakError("Client not initialized")
        return await self._with_disconnect_on_error(
            self._client.read_gatt_char(handle)
        )

    async def _writeUUID(self, uuid, data) -> None:
        if not self._client:
            raise BleakError("Client not initialized")
        return await self._with_disconnect_on_error(
            self._client.write_gatt_char(uuid, data, response=True)
        )

    # --- Generic GATT Characteristics
    async def getDeviceName(self) -> str:
        # return (await self._readHandle(0x2)).decode("ascii")
        return (await self._readUUID(self.chars[CHARACTERISTIC_DEVICE_NAME])).decode(
            "ascii"
        )

    async def getModelNumber(self) -> str:
        # return (await self._readHandle(0xD)).decode("ascii")
        return (await self._readUUID(self.chars[CHARACTERISTIC_MODEL_NUMBER])).decode(
            "ascii"
        )

    async def getSerialNumber(self) -> str:
        # return (await self._readHandle(0xB)).decode("ascii")
        return (await self._readUUID(self.chars[CHARACTERISTIC_SERIAL_NUMBER])).decode(
            "ascii"
        )

    async def getHardwareRevision(self) -> str:
        # return (await self._readHandle(0xF)).decode("ascii")
        return (
            await self._readUUID(self.chars[CHARACTERISTIC_HARDWARE_REVISION])
        ).decode("ascii")

    async def getFirmwareRevision(self) -> str:
        # return (await self._readHandle(0x11)).decode("ascii")
        return (
            await self._readUUID(self.chars[CHARACTERISTIC_FIRMWARE_REVISION])
        ).decode("ascii")

    async def getSoftwareRevision(self) -> str:
        # return (await self._readHandle(0x13)).decode("ascii")
        return (
            await self._readUUID(self.chars[CHARACTERISTIC_SOFTWARE_REVISION])
        ).decode("ascii")

    async def getManufacturer(self) -> str:
        # return (await self._readHandle(0x15)).decode("ascii")
        return (
            await self._readUUID(self.chars[CHARACTERISTIC_MANUFACTURER_NAME])
        ).decode("ascii")

    # --- Onwards to PAX characteristics
    async def setAuth(self, pin) -> None:
        _LOGGER.debug(f"Connecting with pin: {pin}")
        await self._writeUUID(self.chars[CHARACTERISTIC_PIN_CODE], pack("<I", int(pin)))

        result = await self.checkAuth()
        _LOGGER.debug(f"Authorized: {result}")

    async def getAuth(self) -> int:
        v = unpack("<I", await self._readUUID(self.chars[CHARACTERISTIC_PIN_CODE]))
        return v[0]

    async def checkAuth(self) -> bool:
        v = unpack(
            "<b", await self._readUUID(self.chars[CHARACTERISTIC_PIN_CONFIRMATION])
        )
        return bool(v[0])

    async def setAlias(self, name) -> None:
        await self._writeUUID(
            self.chars[CHARACTERISTIC_FAN_DESCRIPTION],
            pack("20s", bytearray(name, "utf-8")),
        )

    async def getAlias(self) -> str:
        return (
            await self._readUUID(self.chars[CHARACTERISTIC_FAN_DESCRIPTION])
        ).decode("utf-8")

    async def getIsClockSet(self) -> str:
        return self._bToStr(await self._readUUID(self.chars[CHARACTERISTIC_STATUS]))

    async def getFactorySettingsChanged(self) -> bool:
        v = unpack(
            "<?",
            await self._readUUID(self.chars[CHARACTERISTIC_FACTORY_SETTINGS_CHANGED]),
        )
        return v[0]

    async def getLed(self) -> str:
        return self._bToStr(await self._readUUID(self.chars[CHARACTERISTIC_LED]))

    async def collect_diagnostics(self) -> dict[str, object]:
        """Read protocol-level diagnostics tied to provisioning state."""
        diagnostics: dict[str, object] = {}

        try:
            diagnostics["pin_confirmed"] = await self.checkAuth()
        except Exception as err:
            diagnostics["pin_confirmed_error"] = str(err)

        try:
            diagnostics["led_raw"] = await self.getLed()
        except Exception as err:
            diagnostics["led_raw_error"] = str(err)

        try:
            diagnostics["status_raw"] = await self.getIsClockSet()
        except Exception as err:
            diagnostics["status_raw_error"] = str(err)

        try:
            diagnostics["factory_settings_changed"] = (
                await self.getFactorySettingsChanged()
            )
        except Exception as err:
            diagnostics["factory_settings_changed_error"] = str(err)

        try:
            diagnostics["mode"] = await self.getMode()
        except Exception as err:
            diagnostics["mode_error"] = str(err)

        try:
            current_time = await self.getTime()
            diagnostics["clock"] = {
                "day_of_week": current_time.DayOfWeek,
                "hour": current_time.Hour,
                "minute": current_time.Minute,
                "second": current_time.Second,
            }
        except Exception as err:
            diagnostics["clock_error"] = str(err)

        try:
            diagnostics["alias"] = (await self.getAlias()).rstrip("\x00")
        except Exception as err:
            diagnostics["alias_error"] = str(err)

        return diagnostics

    async def log_diagnostics(self, context: str) -> dict[str, object]:
        """Log a diagnostic snapshot for provisioning-state investigation."""
        diagnostics = await self.collect_diagnostics()
        _LOGGER.debug("Diagnostic snapshot [%s] for %s: %s", context, self._mac, diagnostics)
        return diagnostics

    async def setTime(self, dayofweek, hour, minute, second) -> None:
        await self._writeUUID(
            self.chars[CHARACTERISTIC_CLOCK],
            pack("<4B", dayofweek, hour, minute, second),
        )

    async def getTime(self) -> Time:
        return Time._make(
            unpack("<BBBB", await self._readUUID(self.chars[CHARACTERISTIC_CLOCK]))
        )

    async def setTimeToNow(self) -> None:
        now = datetime.datetime.now()
        await self.setTime(now.isoweekday(), now.hour, now.minute, now.second)

    async def getReset(self):  # Should be write
        return await self._readUUID(self.chars[CHARACTERISTIC_RESET])

    async def resetDevice(self):  # Dangerous
        await self._writeUUID(self.chars[CHARACTERISTIC_RESET], pack("<I", 120))

    async def resetValues(self):  # Dangerous
        await self._writeUUID(self.chars[CHARACTERISTIC_RESET], pack("<I", 85))

    ####################################
    #### COMMON FAN SPECIFIC VALUES ####
    ####################################
    async def getBoostMode(self) -> BoostMode:
        v = unpack("<BHH", await self._readUUID(self.chars[CHARACTERISTIC_BOOST]))
        return BoostMode._make(v)

    async def setBoostMode(self, on, speed, seconds) -> None:
        if speed % 25:
            raise ValueError("Speed must be a multiple of 25")
        if not on:
            speed = 0
            seconds = 0

        await self._writeUUID(
            self.chars[CHARACTERISTIC_BOOST], pack("<BHH", on, speed, seconds)
        )

    async def getMode(self) -> str:
        v = unpack("<B", await self._readUUID(self.chars[CHARACTERISTIC_MODE]))
        if v[0] == 0:
            return "multimode"
        elif v[0] == 1:
            return "draft_shutter_mode"
        elif v[0] == 2:
            return "wall_switch_extended_runtime_mode"
        elif v[0] == 3:
            return "wall_switch_no_extended_runtime_mode"
        elif v[0] == 4:
            return "heat_distribution_mode"
        else:
            return "Unknown: " + str(v[0])
