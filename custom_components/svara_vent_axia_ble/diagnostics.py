"""Diagnostics support for the Vent-Axia Svara integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant

from .const import CONF_MAC, CONF_PIN

REDACT_CONFIG = {CONF_MAC, CONF_PIN}


def _serialize_timedelta(value: timedelta | None) -> float | None:
    """Convert timedelta values into seconds for diagnostics output."""
    if value is None:
        return None
    return value.total_seconds()


def _serialize_date(value: date | None) -> str | None:
    """Convert date values into ISO format for diagnostics output."""
    if value is None:
        return None
    return value.isoformat()


def _sanitize_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Redact any unexpected sensitive fields from coordinator state."""
    if state is None:
        return {}
    return async_redact_data(dict(state), REDACT_CONFIG)


def _coordinator_snapshot(coordinator: Any) -> dict[str, Any]:
    """Return runtime coordinator state in a diagnostics-safe structure."""
    fan = getattr(coordinator, "_fan", None)
    return {
        "device_id": coordinator.device_id,
        "device_name": coordinator.devicename,
        "connected": fan.isConnected() if fan is not None else False,
        "update_interval_seconds": _serialize_timedelta(
            getattr(coordinator, "update_interval", None)
        ),
        "fast_poll_enabled": getattr(coordinator, "_fast_poll_enabled", None),
        "fast_poll_count": getattr(coordinator, "_fast_poll_count", None),
        "normal_poll_interval_seconds": getattr(
            coordinator, "_normal_poll_interval", None
        ),
        "fast_poll_interval_seconds": getattr(
            coordinator, "_fast_poll_interval", None
        ),
        "connection_failures": getattr(coordinator, "_connection_failures", None),
        "max_connection_failures": getattr(
            coordinator, "_max_connection_failures", None
        ),
        "device_info_loaded": getattr(coordinator, "_device_info_loaded", None),
        "last_config_refresh_date": _serialize_date(
            getattr(coordinator, "_last_config_refresh_date", None)
        ),
        "state": _sanitize_state(getattr(coordinator, "_state", None)),
    }


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = getattr(entry, "runtime_data", None)
    runtime_devices = getattr(runtime, "devices", {})

    devices: list[dict[str, Any]] = []
    for device_key, device_data in entry.data.get(CONF_DEVICES, {}).items():
        device_runtime = runtime_devices.get(device_key)
        coordinator = getattr(device_runtime, "coordinator", None)
        devices.append(
            {
                "configured_device": async_redact_data(device_data, REDACT_CONFIG),
                "runtime_loaded": coordinator is not None,
                "coordinator": (
                    _coordinator_snapshot(coordinator)
                    if coordinator is not None
                    else None
                ),
            }
        )

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "version": entry.version,
            "minor_version": entry.minor_version,
            "data": async_redact_data(entry.data, REDACT_CONFIG),
            "options": async_redact_data(entry.options, REDACT_CONFIG),
        },
        "devices": devices,
        "runtime_initialized": runtime is not None,
    }
