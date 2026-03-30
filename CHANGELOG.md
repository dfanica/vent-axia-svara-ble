# Changelog

## v1.0.2

- Added device action buttons for `Refresh Now` and `Sync Clock` in Home Assistant.
- Hardened BLE disconnect handling so intentional disconnects, delayed callbacks, and stale client callbacks do not trigger false reconnect/failure paths.
- Simplified clock sync so all writes go through one tracked path, initial sync no longer causes an immediate duplicate write, and periodic sync failures do not fail healthy sensor refreshes.
- Expanded behavior tests to cover clock-sync cadence, manual clock sync, grouped writes, button actions, and BLE disconnect edge cases.

## v1.0.1

- Updated release metadata and documentation for HACS publication readiness.
- Added diagnostics support for config entry exports with sensitive-field redaction.
- Added a local and CI-backed Python test setup covering metadata, config normalization, runtime mapping, and diagnostics behavior.
- Updated GitHub workflows for current checkout actions and explicit HACS validation permissions.
- Corrected manifest key ordering and translation schema issues flagged by repository validation.

## v1.0.0

- Established the Vent-Axia Svara integration as the active standalone repository.
- Local BLE setup using `MAC + PIN`.
- Make sure global configuration options are set for clock sync, scan interval, and fast scan interval.
- Log protocol diagnostics for PIN confirmation, raw LED/status values, factory-settings-changed, clock, alias, and mode.
- Initial clock sync during setup to clears the unhealthy red-light state into a healthy idle state.
- Alias sync so the device BLE alias follows the configured Home Assistant device name.
