"""Behavior tests for config normalization, runtime mapping, and diagnostics."""

from __future__ import annotations

import asyncio
from struct import pack
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from tests.support import load_integration_module


def test_config_flow_normalizes_mac_and_text_fields() -> None:
    """Device input normalization should canonicalize MAC and trim strings."""
    config_flow = load_integration_module("config_flow")

    normalized = config_flow.normalize_device_input(
        {
            "name": "  Ensuite Fan  ",
            "mac": "aa-bb-cc-dd-ee-ff",
            "pin": " 123456 ",
            "scan_interval": 300,
            "scan_interval_fast": 5,
        }
    )

    assert normalized["name"] == "Ensuite Fan"
    assert normalized["mac"] == "AA:BB:CC:DD:EE:FF"
    assert normalized["pin"] == "123456"


def test_runtime_maps_only_loaded_coordinators() -> None:
    """Runtime helpers should skip configured devices with no runtime coordinator."""
    runtime = load_integration_module("runtime")

    coordinator_a = object()
    entry = SimpleNamespace(
        runtime_data=runtime.IntegrationRuntime(
            devices={"mac-a": runtime.DeviceRuntime(coordinator=coordinator_a)}
        ),
        data={
            "devices": {
                "mac-a": {"name": "Fan A"},
                "mac-b": {"name": "Fan B"},
            }
        },
    )

    coordinators = runtime.get_entry_coordinators(entry)
    devices = list(runtime.iter_entry_devices(entry))

    assert coordinators == {"mac-a": coordinator_a}
    assert devices == [("mac-a", "Fan A", coordinator_a)]


def test_diagnostics_redacts_sensitive_fields_and_serializes_runtime_state() -> None:
    """Diagnostics should redact secrets and expose safe coordinator state."""
    diagnostics = load_integration_module("diagnostics")

    class FakeFan:
        def isConnected(self) -> bool:
            return True

    coordinator = SimpleNamespace(
        device_id="device-1",
        devicename="Fan A",
        update_interval=timedelta(seconds=300),
        _fast_poll_enabled=False,
        _fast_poll_count=0,
        _normal_poll_interval=300,
        _fast_poll_interval=5,
        _connection_failures=1,
        _max_connection_failures=5,
        _device_info_loaded=True,
        _last_config_refresh_date=date(2026, 3, 18),
        _state={"alias": "Fan A", "mac": "AA:BB:CC:DD:EE:FF", "pin": "123456"},
        _fan=FakeFan(),
    )
    runtime_data = SimpleNamespace(
        devices={"mac-a": SimpleNamespace(coordinator=coordinator)}
    )
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Vent-Axia Svara BLE",
        version=1,
        minor_version=1,
        runtime_data=runtime_data,
        data={
            "devices": {
                "mac-a": {
                    "name": "Fan A",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "pin": "123456",
                }
            }
        },
        options={"clock_sync": True},
    )

    payload = asyncio.run(diagnostics.async_get_config_entry_diagnostics(None, entry))

    assert payload["entry"]["data"]["devices"]["mac-a"]["mac"] == "REDACTED"
    assert payload["entry"]["data"]["devices"]["mac-a"]["pin"] == "REDACTED"
    assert payload["devices"][0]["configured_device"]["mac"] == "REDACTED"
    assert payload["devices"][0]["configured_device"]["pin"] == "REDACTED"
    assert payload["devices"][0]["coordinator"]["connected"] is True
    assert payload["devices"][0]["coordinator"]["update_interval_seconds"] == 300.0
    assert payload["devices"][0]["coordinator"]["last_config_refresh_date"] == "2026-03-18"
    assert payload["devices"][0]["coordinator"]["state"]["mac"] == "REDACTED"
    assert payload["devices"][0]["coordinator"]["state"]["pin"] == "REDACTED"


def test_periodic_clock_sync_runs_once_per_poll_interval() -> None:
    """Periodic clock sync should follow the normal poll cadence."""
    coordinator_module = load_integration_module("coordinator_svara")

    class FakeFan:
        def __init__(self, *_args, **_kwargs) -> None:
            self.authorize_calls = 0
            self.set_time_calls: list[tuple[int, int, int, int]] = []

        def set_disconnect_callback(self, _callback) -> None:
            return None

        async def authorize(self) -> None:
            self.authorize_calls += 1

        async def setTime(self, day_of_week: int, hour: int, minute: int, second: int) -> None:
            self.set_time_calls.append((day_of_week, hour, minute, second))

        async def read_sensor_state(self) -> dict[str, int]:
            return {"rpm": 900}

        async def disconnect(self) -> None:
            return None

    coordinator_module.SvaraDevice = FakeFan

    coordinator = coordinator_module.SvaraCoordinator(
        hass=None,
        device=SimpleNamespace(name="Ensuite Fan"),
        mac="AA:BB:CC:DD:EE:FF",
        pin="123456",
        scan_interval=300,
        scan_interval_fast=5,
        clock_sync_enabled=True,
    )

    async def fake_safe_connect() -> bool:
        return True

    coordinator._safe_connect = fake_safe_connect

    assert asyncio.run(coordinator.read_sensordata(disconnect=True)) is True
    assert coordinator._fan.authorize_calls == 1
    assert coordinator._fan.set_time_calls == [(7, 12, 0, 0)]

    assert asyncio.run(coordinator.read_sensordata(disconnect=True)) is True
    assert coordinator._fan.authorize_calls == 1
    assert coordinator._fan.set_time_calls == [(7, 12, 0, 0)]


def test_initial_clock_sync_updates_periodic_timestamp() -> None:
    """Initial clock sync should suppress an immediate second write on first refresh."""
    coordinator_module = load_integration_module("coordinator_svara")

    class FakeFan:
        def __init__(self, *_args, **_kwargs) -> None:
            self.authorize_calls = 0
            self.set_time_calls: list[tuple[int, int, int, int]] = []
            self.diagnostics_contexts: list[str] = []

        def set_disconnect_callback(self, _callback) -> None:
            return None

        async def authorize(self) -> None:
            self.authorize_calls += 1

        async def setTime(self, day_of_week: int, hour: int, minute: int, second: int) -> None:
            self.set_time_calls.append((day_of_week, hour, minute, second))

        async def log_diagnostics(self, context: str) -> None:
            self.diagnostics_contexts.append(context)

        async def read_sensor_state(self) -> dict[str, int]:
            return {"rpm": 900}

        async def disconnect(self) -> None:
            return None

    coordinator_module.SvaraDevice = FakeFan

    coordinator = coordinator_module.SvaraCoordinator(
        hass=None,
        device=SimpleNamespace(name="Ensuite Fan"),
        mac="AA:BB:CC:DD:EE:FF",
        pin="123456",
        scan_interval=300,
        scan_interval_fast=5,
        clock_sync_enabled=True,
    )

    assert asyncio.run(coordinator._attempt_initial_clock_sync()) is None
    assert coordinator._last_periodic_clock_sync is not None
    assert coordinator._fan.authorize_calls == 0
    assert coordinator._fan.set_time_calls == [(7, 12, 0, 0)]

    async def fake_safe_connect() -> bool:
        return True

    coordinator._safe_connect = fake_safe_connect

    assert asyncio.run(coordinator.read_sensordata(disconnect=True)) is True
    assert coordinator._fan.authorize_calls == 0
    assert coordinator._fan.set_time_calls == [(7, 12, 0, 0)]


def test_periodic_clock_sync_failure_does_not_fail_sensor_refresh() -> None:
    """Clock-sync write errors should not turn a successful poll into a failure."""
    coordinator_module = load_integration_module("coordinator_svara")

    class FakeFan:
        def __init__(self, *_args, **_kwargs) -> None:
            self.authorize_calls = 0
            self.disconnect_calls = 0

        def set_disconnect_callback(self, _callback) -> None:
            return None

        async def authorize(self) -> None:
            self.authorize_calls += 1
            raise RuntimeError("clock write failed")

        async def setTime(self, *_args) -> None:
            raise AssertionError("setTime should not be reached after authorize failure")

        async def read_sensor_state(self) -> dict[str, int]:
            return {"rpm": 900}

        async def disconnect(self) -> None:
            self.disconnect_calls += 1

    coordinator_module.SvaraDevice = FakeFan

    coordinator = coordinator_module.SvaraCoordinator(
        hass=None,
        device=SimpleNamespace(name="Ensuite Fan"),
        mac="AA:BB:CC:DD:EE:FF",
        pin="123456",
        scan_interval=300,
        scan_interval_fast=5,
        clock_sync_enabled=True,
    )

    async def fake_safe_connect() -> bool:
        return True

    coordinator._safe_connect = fake_safe_connect

    assert asyncio.run(coordinator.read_sensordata(disconnect=True)) is True
    assert coordinator._fan.authorize_calls == 1
    assert coordinator._fan.disconnect_calls == 1
    assert coordinator._state["rpm"] == 900


def test_manual_clock_sync_authorizes_and_updates_device_time() -> None:
    """The manual clock sync action should write time immediately."""
    coordinator_module = load_integration_module("coordinator_svara")

    class FakeFan:
        def __init__(self, *_args, **_kwargs) -> None:
            self.authorize_calls = 0
            self.set_time_calls: list[tuple[int, int, int, int]] = []
            self.diagnostics_calls = 0

        def set_disconnect_callback(self, _callback) -> None:
            return None

        async def authorize(self) -> None:
            self.authorize_calls += 1

        async def setTime(self, day_of_week: int, hour: int, minute: int, second: int) -> None:
            self.set_time_calls.append((day_of_week, hour, minute, second))

        async def collect_diagnostics(self) -> dict[str, object]:
            self.diagnostics_calls += 1
            return {"clock": "ok"}

    coordinator_module.SvaraDevice = FakeFan

    coordinator = coordinator_module.SvaraCoordinator(
        hass=None,
        device=SimpleNamespace(name="Ensuite Fan"),
        mac="AA:BB:CC:DD:EE:FF",
        pin="123456",
        scan_interval=300,
        scan_interval_fast=5,
        clock_sync_enabled=True,
    )

    async def fake_safe_connect() -> bool:
        return True

    coordinator._safe_connect = fake_safe_connect
    coordinator.setFastPollMode = lambda: None

    assert asyncio.run(coordinator.async_sync_clock()) is True
    assert coordinator._fan.authorize_calls == 1
    assert coordinator._fan.set_time_calls == [(7, 12, 0, 0)]
    assert coordinator._fan.diagnostics_calls == 1
    assert coordinator._state["clock"] == "ok"


def test_base_device_disconnect_invokes_async_callback() -> None:
    """Unexpected disconnects should trigger the registered callback."""
    base_device_module = load_integration_module("devices.base_device")

    device = object.__new__(base_device_module.BaseDevice)
    device._mac = "AA:BB:CC:DD:EE:FF"
    device._client = object()
    device._expected_disconnect = False

    callback_calls: list[str] = []

    async def on_disconnect() -> None:
        callback_calls.append("called")

    device._disconnect_callback = on_disconnect

    async def run_disconnect() -> None:
        device._handle_disconnect(None)
        await asyncio.sleep(0)

    asyncio.run(run_disconnect())

    assert device._client is None
    assert callback_calls == ["called"]


def test_base_device_expected_disconnect_does_not_invoke_callback() -> None:
    """Intentional disconnects should not be treated as connection failures."""
    base_device_module = load_integration_module("devices.base_device")

    device = base_device_module.BaseDevice(None, "AA:BB:CC:DD:EE:FF", "123456")
    callback_calls: list[str] = []

    async def on_disconnect() -> None:
        callback_calls.append("called")

    class FakeClient:
        is_connected = True

        def __init__(self, owner) -> None:
            self._owner = owner

        async def disconnect(self) -> None:
            self._owner._handle_disconnect(self)

    device._disconnect_callback = on_disconnect
    device._client = FakeClient(device)

    asyncio.run(device.disconnect())

    assert device._client is None
    assert device._expected_disconnect is False
    assert callback_calls == []


def test_base_device_delayed_expected_disconnect_still_suppresses_callback() -> None:
    """Expected disconnects should stay suppressed until the callback arrives."""
    base_device_module = load_integration_module("devices.base_device")

    device = base_device_module.BaseDevice(None, "AA:BB:CC:DD:EE:FF", "123456")
    callback_calls: list[str] = []
    delayed_disconnect = asyncio.Event()

    async def on_disconnect() -> None:
        callback_calls.append("called")

    class FakeClient:
        is_connected = True

        def __init__(self, owner) -> None:
            self._owner = owner

        async def disconnect(self) -> None:
            asyncio.create_task(self._delayed_callback())

        async def _delayed_callback(self) -> None:
            await asyncio.sleep(0)
            self._owner._handle_disconnect(self)
            delayed_disconnect.set()

    device._disconnect_callback = on_disconnect
    device._client = FakeClient(device)

    async def run_disconnect() -> None:
        await device.disconnect()
        assert device._expected_disconnect is True
        await delayed_disconnect.wait()

    asyncio.run(run_disconnect())

    assert device._client is None
    assert device._expected_disconnect is False
    assert callback_calls == []


def test_base_device_expected_disconnect_resets_without_callback() -> None:
    """Intentional disconnects should eventually clear suppression even without callback."""
    base_device_module = load_integration_module("devices.base_device")

    device = base_device_module.BaseDevice(None, "AA:BB:CC:DD:EE:FF", "123456")

    class FakeClient:
        is_connected = True

        async def disconnect(self) -> None:
            return None

    device._client = FakeClient()

    async def run_disconnect() -> None:
        await device.disconnect()
        assert device._expected_disconnect is True
        await asyncio.sleep(1.1)

    asyncio.run(run_disconnect())

    assert device._expected_disconnect is False


def test_base_device_ignores_disconnect_from_superseded_client() -> None:
    """Delayed callbacks from an old client must not tear down a new connection."""
    base_device_module = load_integration_module("devices.base_device")

    device = base_device_module.BaseDevice(None, "AA:BB:CC:DD:EE:FF", "123456")
    callback_calls: list[str] = []

    async def on_disconnect() -> None:
        callback_calls.append("called")

    stale_client = object()
    active_client = object()

    device._disconnect_callback = on_disconnect
    device._client = active_client
    device._expected_disconnect = False

    async def run_disconnect() -> None:
        device._handle_disconnect(stale_client)
        await asyncio.sleep(0)

    asyncio.run(run_disconnect())

    assert device._client is active_client
    assert callback_calls == []


def test_svara_device_write_state_key_writes_grouped_values() -> None:
    """Grouped config keys should write the full related device payload."""
    svara_module = load_integration_module("devices.svara")

    device = svara_module.SvaraDevice(None, "AA:BB:CC:DD:EE:FF", "123456")
    calls: dict[str, tuple] = {}

    async def set_fan_speed_settings(humidity: int, light: int, trickle: int) -> None:
        calls["fan_speeds"] = (humidity, light, trickle)

    async def set_silent_hours(on: bool, start, end) -> None:
        calls["silent_hours"] = (on, start, end)

    device.setFanSpeedSettings = set_fan_speed_settings
    device.setSilentHours = set_silent_hours

    state = {
        "fanspeed_humidity": 1800,
        "fanspeed_light": 1600,
        "fanspeed_trickle": 1000,
        "silenthours_on": 1,
        "silenthours_starttime": "22:00",
        "silenthours_endtime": "06:30",
    }

    assert asyncio.run(device.write_state_key("fanspeed_light", state)) is True
    assert calls["fan_speeds"] == (1800, 1600, 1000)

    assert asyncio.run(device.write_state_key("silenthours_endtime", state)) is True
    assert calls["silent_hours"] == (True, "22:00", "06:30")


def test_svara_device_write_state_key_returns_false_for_unknown_key() -> None:
    """Unknown state keys should be rejected without writing."""
    svara_module = load_integration_module("devices.svara")

    device = svara_module.SvaraDevice(None, "AA:BB:CC:DD:EE:FF", "123456")

    assert asyncio.run(device.write_state_key("unsupported_key", {})) is False


def test_svara_device_get_state_returns_stable_enum_keys() -> None:
    """Fan state values should stay aligned with translation keys."""
    svara_module = load_integration_module("devices.svara")

    device = svara_module.SvaraDevice(None, "AA:BB:CC:DD:EE:FF", "123456")

    async def read_uuid(_uuid):
        return pack("<4HBHB", 50, 100, 20, 500, 0b00000001, 0, 0)

    device._readUUID = read_uuid

    state = asyncio.run(device.getState())

    assert state.Mode == "trickle_ventilation"


def test_button_entity_dispatches_refresh_and_clock_sync_actions() -> None:
    """Button presses should call the matching coordinator action."""
    button_module = load_integration_module("button")

    class FakeCoordinator:
        def __init__(self) -> None:
            self.device_id = "device-1"
            self.identifiers = {("svara_vent_axia_ble", "AA:BB")}
            self.fan = SimpleNamespace(_mac="AA:BB")
            self.refresh_calls = 0
            self.sync_calls = 0

        async def async_request_refresh(self) -> None:
            self.refresh_calls += 1

        async def async_sync_clock(self) -> None:
            self.sync_calls += 1

    coordinator = FakeCoordinator()

    refresh_entity = button_module.SvaraButtonEntity(
        coordinator,
        button_module.ENTITIES[0],
    )
    sync_entity = button_module.SvaraButtonEntity(
        coordinator,
        button_module.ENTITIES[1],
    )

    asyncio.run(refresh_entity.async_press())
    asyncio.run(sync_entity.async_press())

    assert coordinator.refresh_calls == 1
    assert coordinator.sync_calls == 1


def test_clock_sensor_infers_local_datetime_from_device_time() -> None:
    """Clock diagnostics should expose an inferred local datetime."""
    sensor_module = load_integration_module("sensor")

    inferred = sensor_module._infer_clock_datetime(
        {
            "day_of_week": 7,
            "hour": 9,
            "minute": 15,
            "second": 30,
        }
    )

    assert inferred == datetime(2026, 3, 29, 9, 15, 30)


def test_clock_sensor_returns_none_for_invalid_device_time() -> None:
    """Malformed device clock payloads should not raise from the sensor."""
    sensor_module = load_integration_module("sensor")

    inferred = sensor_module._infer_clock_datetime(
        {
            "day_of_week": 7,
            "hour": 255,
            "minute": 99,
            "second": 30,
        }
    )

    assert inferred is None
