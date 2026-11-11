# LedFX for Home Assistant
[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![CodeQL](https://img.shields.io/badge/CODEQL-Passing-30C854.svg?style=for-the-badge)](https://github.com/dmamontov/hass-miwifi/actions?query=CodeQL)
[![Telegram](https://img.shields.io/badge/Telegram-channel-34ABDF.svg?style=for-the-badge)](https://t.me/hass_mamontov_tech)

Component for deep integration [LedFx](https://github.com/LedFx/LedFx) from [Home Assistant](https://www.home-assistant.io/).

## About this fork

This is a fork of [Anto79-ops/hass-ledfx](https://github.com/Anto79-ops/hass-ledfx) with fixes for LedFx 2.x,
made and tested against LedFx 2.1.9. The changes live on the `ledfx-2.1.9-fixes` branch (`main` mirrors
upstream) and ship as `2.1.9-fixes.N` releases: add `https://github.com/chuck-amuck/hass-ledfx` to HACS as a
custom integration repository to install them.

- Presets are sent with the category LedFx 2.x expects (`ledfx_presets` / `user_presets`), and effect-config
  entities are generated from the 2.x schema.
- Free-text effect parameters get `text` entities; number steps are 1 for integers and 0.01 otherwise.
- Each device gets a preset select and an Effect select, grouped by category with display names (also on the
  light card), plus a Default preset reset.
- Config, schema, colours and scenes are refreshed every 10 minutes instead of on every scan.
- A Reconfigure option changes the LedFx address without removing the integration.
- New entity IDs no longer include the LedFx IP address; existing entities keep theirs.

## Requirements
* LedFx version >= [0.10.7](https://github.com/LedFx/LedFx/releases/tag/v0.10.7)

## Important information
* ❗ Effect controls (number, switch, select) are disabled by default. They must be enabled manually.
* ❗ Controls (number, switch, select) if enabled, have the status `UNAVAILABLE` by default. After enabling the effect on the device, the status will be changed by those that are supported by this effect.

## More info

- [Install](https://github.com/dmamontov/hass-ledfx/wiki/Install)
- [Config](https://github.com/dmamontov/hass-ledfx/wiki/Config)
- [Entities](https://github.com/dmamontov/hass-ledfx/wiki/Entities)
- [Performance](https://github.com/dmamontov/hass-ledfx/wiki/Performance)
- [Diagnostics](https://github.com/dmamontov/hass-ledfx/wiki/Diagnostics)
- [FAQ](https://github.com/dmamontov/hass-ledfx/wiki/FAQ)

## Install
The easiest way to install the LedFx integration is with [HACS](https://hacs.xyz/). First install [HACS](https://hacs.xyz/) if you don’t have it yet. After installation you can find this integration in the [HACS](https://hacs.xyz/) store under integrations.

Alternatively, you can install it manually. Just copy and paste the content of the hass-ledfx/custom_components folder in your config/custom_components directory. As example, you will get the sensor.py file in the following path: /config/custom_components/ledfx/sensor.py. The disadvantage of a manual installation is that you won’t be notified about updates.

## Config
**Via GUI**

`Settings` > `Integrations` > `Plus` > `LedFx`

To connect, enter the ip address and port. And also if you use basic auth, enter the user and password.

❗ Via YAML (legacy way) not supported

## Performance
![](/images/performance.gif)

1. Install [lovelace-auto-entities](https://github.com/thomasloven/lovelace-auto-entities) from HACS
2. Install [light-entity-card](https://github.com/ljmerza/light-entity-card) from HACS
3. Add new Lovelace card before that replacing `device`: [example](https://gist.github.com/dmamontov/34d252351d9eda98f53b2d6180771f12)
