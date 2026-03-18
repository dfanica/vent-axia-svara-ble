# Vent-Axia Svara BLE

Unofficial Home Assistant integration for Vent-Axia Svara fans over Bluetooth Low Energy (BLE).

![Vent-Axia Icon](custom_components/svara_vent_axia_ble/brand/icon.png)

## Release

`v1.0.0` is the first HACS-ready release of this integration.

## Features

- Local BLE control for Vent-Axia Svara fans
- Setup with `MAC address + PIN`
- Multiple fans under a single integration entry
- Sensors and configuration entities for exposed Svara functions
- Integration options for clock sync and scan intervals
- Diagnostics support for config entries and runtime state

## Supported Models

- Supported: `Vent-Axia Svara`
- Not supported: `Vent-Axia Svensa`
- Not supported: `PureAir Sense`

Other Vent-Axia or related BLE products should be treated as unsupported unless explicit model support is added in this repository.

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Go to `Integrations`.
3. Open the menu, then select `Custom repositories`.
4. Add `https://github.com/danielfanica/vent-axia-svara-ble` as an `Integration`.
5. Search for `Vent-Axia Svara BLE`.
6. Install the integration and restart Home Assistant.

### Manual Install

1. Copy `custom_components/svara_vent_axia_ble` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Go to `Settings -> Devices & Services`.
4. Select `Add Integration`.
5. Search for `Vent-Axia Svara BLE`.

## Configuration

When adding a fan, the integration expects:

1. A device name of your choice
2. The fan MAC address
3. The PIN printed on the fan sticker

After setup, open the integration options if you want to adjust:

- integration title
- clock sync behavior
- normal scan interval
- fast scan interval

## Usage Notes

- Home Assistant needs reliable Bluetooth coverage near the fan.
- If Home Assistant does not have onboard Bluetooth, use a supported Bluetooth proxy.
- BLE reliability depends on signal quality and adapter stability.
- If the official Vent-Axia app is connected to the same fan, this integration can lose control and entities may become unavailable.
- This integration is intended to be the BLE owner for the fan.

## Diagnostics

The integration includes Home Assistant diagnostics support for config entries. Exported diagnostics redact sensitive values such as device MAC addresses and PINs.

## Repository Layout

- `custom_components/svara_vent_axia_ble`: Home Assistant integration
- `custom_components/svara_vent_axia_ble/brand`: Home Assistant branding assets
- `CHANGELOG.md`: release history
- `LICENSE`: project license
