"""Behavior tests for config normalization, runtime mapping, and diagnostics."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
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
