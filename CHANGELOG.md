# Changelog

## v1.0.0

- Established the Vent-Axia Svara integration as the active standalone repository.
- Local BLE setup using `MAC + PIN`.
- Make sure global configuration options are set for clock sync, scan interval, and fast scan interval.
- Log protocol diagnostics for PIN confirmation, raw LED/status values, factory-settings-changed, clock, alias, and mode.
- Initial clock sync during setup to clears the unhealthy red-light state into a healthy idle state.
- Alias sync so the device BLE alias follows the configured Home Assistant device name.
