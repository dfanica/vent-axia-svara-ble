import datetime
import logging
import math

from collections import namedtuple
from struct import pack, unpack

from .base_device import BaseDevice
from .characteristics import *

_LOGGER = logging.getLogger(__name__)

Fanspeeds = namedtuple(
    "Fanspeeds", "Humidity Light Trickle", defaults=(2250, 1625, 1000)
)
FanState = namedtuple("FanState", "Humidity Temp Light RPM Mode")
HeatDistributorSettings = namedtuple(
    "HeatDistributorSettings", "TemperatureLimit FanSpeedBelow FanSpeedAbove"
)
LightSensorSettings = namedtuple("LightSensorSettings", "DelayedStart RunningTime")
Sensitivity = namedtuple("Sensitivity", "HumidityOn Humidity LightOn Light")
SilentHours = namedtuple(
    "SilentHours", "On StartingHour StartingMinute EndingHour EndingMinute"
)
TrickleDays = namedtuple("TrickleDays", "Weekdays Weekends")


class SvaraDevice(BaseDevice):
    """Vent-Axia Svara implementation.

    Svara shares its BLE protocol with Svara Vent-Axia, so this class is a focused
    rename of the working shared Svara protocol implementation.
    """

    def __init__(self, hass, mac, pin):
        super().__init__(hass, mac, pin)

        self.chars[CHARACTERISTIC_AUTOMATIC_CYCLES] = (
            "f508408a-508b-41c6-aa57-61d1fd0d5c39"
        )
        self.chars[CHARACTERISTIC_BASIC_VENTILATION] = (
            "faa49e09-a79c-4725-b197-bdc57c67dc32"
        )
        self.chars[CHARACTERISTIC_LEVEL_OF_FAN_SPEED] = (
            "1488a757-35bc-4ec8-9a6b-9ecf1502778e"
        )
        self.chars[CHARACTERISTIC_NIGHT_MODE] = "b5836b55-57bd-433e-8480-46e4993c5ac0"
        self.chars[CHARACTERISTIC_SENSITIVITY] = "e782e131-6ce1-4191-a8db-f4304d7610f1"
        self.chars[CHARACTERISTIC_SENSOR_DATA] = "528b80e8-c47a-4c0a-bdf1-916a7748f412"
        self.chars[CHARACTERISTIC_TEMP_HEAT_DISTRIBUTOR] = (
            "a22eae12-dba8-49f3-9c69-1721dcff1d96"
        )
        self.chars[CHARACTERISTIC_TIME_FUNCTIONS] = (
            "49c616de-02b1-4b67-b237-90f66793a6f2"
        )

    async def read_sensor_state(self) -> dict[str, int | float | str]:
        """Read and normalize sensor-oriented device state."""
        fan_state = await self.getState()
        boost_mode = await self.getBoostMode()

        return {
            "humidity": fan_state.Humidity,
            "temperature": fan_state.Temp,
            "light": fan_state.Light,
            "rpm": fan_state.RPM,
            "flow": int(fan_state.RPM * 0.05076 - 14) if fan_state.RPM > 400 else 0,
            "state": fan_state.Mode,
            "boostmode": boost_mode.OnOff,
            "boostmodespeedread": boost_mode.Speed,
            "boostmodesecread": boost_mode.Seconds,
        }

    async def read_config_state(
        self,
    ) -> dict[str, int | bool | str | datetime.time]:
        """Read and normalize configuration-oriented device state."""
        fan_speeds = await self.getFanSpeedSettings()
        light_settings = await self.getLightSensorSettings()
        sensitivity = await self.getSensorsSensitivity()
        silent_hours = await self.getSilentHours()
        trickle_days = await self.getTrickleDays()

        return {
            "automatic_cycles": await self.getAutomaticCycles(),
            "mode": await self.getMode(),
            "fanspeed_humidity": fan_speeds.Humidity,
            "fanspeed_light": fan_speeds.Light,
            "fanspeed_trickle": fan_speeds.Trickle,
            "lightsensorsettings_delayedstart": light_settings.DelayedStart,
            "lightsensorsettings_runningtime": light_settings.RunningTime,
            "sensitivity_humidity": sensitivity.Humidity,
            "sensitivity_light": sensitivity.Light,
            "silenthours_on": silent_hours.On,
            "silenthours_starttime": datetime.time(
                silent_hours.StartingHour, silent_hours.StartingMinute
            ),
            "silenthours_endtime": datetime.time(
                silent_hours.EndingHour, silent_hours.EndingMinute
            ),
            "trickledays_weekdays": trickle_days.Weekdays,
            "trickledays_weekends": trickle_days.Weekends,
        }

    async def write_state_key(self, key: str, state: dict[str, object]) -> bool:
        """Apply a coordinator state change to the device."""
        match key:
            case "automatic_cycles":
                await self.setAutomaticCycles(int(state["automatic_cycles"]))
            case "boostmode":
                if int(state["boostmodesecwrite"]) == 0:
                    state["boostmodespeedwrite"] = 2400
                    state["boostmodesecwrite"] = 600
                await self.setBoostMode(
                    int(state["boostmode"]),
                    int(state["boostmodespeedwrite"]),
                    int(state["boostmodesecwrite"]),
                )
            case "fanspeed_humidity" | "fanspeed_light" | "fanspeed_trickle":
                await self.setFanSpeedSettings(
                    int(state["fanspeed_humidity"]),
                    int(state["fanspeed_light"]),
                    int(state["fanspeed_trickle"]),
                )
            case "lightsensorsettings_delayedstart" | "lightsensorsettings_runningtime":
                await self.setLightSensorSettings(
                    int(state["lightsensorsettings_delayedstart"]),
                    int(state["lightsensorsettings_runningtime"]),
                )
            case "sensitivity_humidity" | "sensitivity_light":
                await self.setSensorsSensitivity(
                    int(state["sensitivity_humidity"]),
                    int(state["sensitivity_light"]),
                )
            case "trickledays_weekdays" | "trickledays_weekends":
                await self.setTrickleDays(
                    int(state["trickledays_weekdays"]),
                    int(state["trickledays_weekends"]),
                )
            case "silenthours_on" | "silenthours_starttime" | "silenthours_endtime":
                await self.setSilentHours(
                    bool(state["silenthours_on"]),
                    state["silenthours_starttime"],
                    state["silenthours_endtime"],
                )
            case _:
                return False

        return True

    async def getState(self) -> FanState:
        v = unpack("<4HBHB", await self._readUUID(self.chars[CHARACTERISTIC_SENSOR_DATA]))
        _LOGGER.debug("Read fan states: %s", v)

        trigger = "no_trigger"
        if v[3] == 0:
            trigger = "idle"
        elif ((v[4] >> 4) & 1) == 1:
            trigger = "boost"
        elif ((v[4] >> 6) & 3) == 3:
            trigger = "switch"
        elif (v[4] & 3) == 1:
            trigger = "trickle_ventilation"
        elif (v[4] & 3) == 2:
            trigger = "light_ventilation"
        elif (v[4] & 3) == 3:
            trigger = "humidity_ventilation"

        return FanState(
            round(math.log2(v[0] - 30) * 10, 2) if v[0] > 30 else 0,
            v[1] / 4 - 2.6,
            v[2],
            v[3],
            trigger,
        )

    async def getAutomaticCycles(self) -> int:
        v = unpack("<B", await self._readUUID(self.chars[CHARACTERISTIC_AUTOMATIC_CYCLES]))
        return v[0]

    async def setAutomaticCycles(self, setting: int) -> None:
        if setting < 0 or setting > 3:
            raise ValueError("Setting must be between 0-3")
        await self._writeUUID(
            self.chars[CHARACTERISTIC_AUTOMATIC_CYCLES], pack("<B", setting)
        )

    async def getFanSpeedSettings(self) -> Fanspeeds:
        return Fanspeeds._make(
            unpack(
                "<HHH",
                await self._readUUID(self.chars[CHARACTERISTIC_LEVEL_OF_FAN_SPEED]),
            )
        )

    async def setFanSpeedSettings(self, humidity=2250, light=1625, trickle=1000) -> None:
        for val in (humidity, light, trickle):
            if val % 25 != 0:
                raise ValueError("Speeds should be multiples of 25")
            if val > 2401 or val < 0:
                raise ValueError("Speeds must be between 0 and 2400 rpm")

        _LOGGER.debug(
            "Svara setFanSpeedSettings: %s %s %s", humidity, light, trickle
        )

        await self._writeUUID(
            self.chars[CHARACTERISTIC_LEVEL_OF_FAN_SPEED],
            pack("<HHH", humidity, light, trickle),
        )

    async def getHeatDistributor(self) -> HeatDistributorSettings:
        return HeatDistributorSettings._make(
            unpack(
                "<BHH",
                await self._readUUID(self.chars[CHARACTERISTIC_TEMP_HEAT_DISTRIBUTOR]),
            )
        )

    async def setHeatDistributor(self, temperatureLimit, fanSpeedBelow, fanSpeedAbove) -> None:
        await self._writeUUID(
            self.chars[CHARACTERISTIC_TEMP_HEAT_DISTRIBUTOR],
            pack("<BHH", temperatureLimit, fanSpeedBelow, fanSpeedAbove),
        )

    async def getSilentHours(self) -> SilentHours:
        return SilentHours._make(
            unpack("<5B", await self._readUUID(self.chars[CHARACTERISTIC_NIGHT_MODE]))
        )

    async def setSilentHours(
        self, on: bool, startingTime: datetime.time, endingTime: datetime.time
    ) -> None:
        value = pack(
            "<5B",
            int(on),
            startingTime.hour,
            startingTime.minute,
            endingTime.hour,
            endingTime.minute,
        )
        await self._writeUUID(self.chars[CHARACTERISTIC_NIGHT_MODE], value)

    async def getTrickleDays(self) -> TrickleDays:
        return TrickleDays._make(
            unpack("<2B", await self._readUUID(self.chars[CHARACTERISTIC_BASIC_VENTILATION]))
        )

    async def setTrickleDays(self, weekdays, weekends) -> None:
        await self._writeUUID(
            self.chars[CHARACTERISTIC_BASIC_VENTILATION],
            pack("<2B", weekdays, weekends),
        )

    async def getLightSensorSettings(self) -> LightSensorSettings:
        return LightSensorSettings._make(
            unpack("<2B", await self._readUUID(self.chars[CHARACTERISTIC_TIME_FUNCTIONS]))
        )

    async def setLightSensorSettings(self, delayed, running) -> None:
        if delayed < 0 or delayed > 10:
            raise ValueError("Delayed must be between 0 and 10 minutes")
        if running < 5 or running > 60:
            raise ValueError("Running time must be between 5 and 60 minutes")

        await self._writeUUID(
            self.chars[CHARACTERISTIC_TIME_FUNCTIONS], pack("<2B", delayed, running)
        )

    async def getSensorsSensitivity(self) -> Sensitivity:
        value = Sensitivity._make(
            unpack("<4B", await self._readUUID(self.chars[CHARACTERISTIC_SENSITIVITY]))
        )
        return Sensitivity._make(
            unpack(
                "<4B",
                bytearray(
                    [
                        value.HumidityOn,
                        value.HumidityOn and value.Humidity,
                        value.LightOn,
                        value.LightOn and value.Light,
                    ]
                ),
            )
        )

    async def setSensorsSensitivity(self, humidity, light) -> None:
        if humidity > 3 or humidity < 0:
            raise ValueError("Humidity sensitivity must be between 0-3")
        if light > 3 or light < 0:
            raise ValueError("Light sensitivity must be between 0-3")

        value = pack("<4B", bool(humidity), humidity, bool(light), light)
        await self._writeUUID(self.chars[CHARACTERISTIC_SENSITIVITY], value)
