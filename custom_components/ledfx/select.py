"""Select component."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.components.select import (
    ENTITY_ID_FORMAT,
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_DEVICE,
    ATTR_FIELD_EFFECTS,
    ATTR_FIELD_OPTIONS,
    ATTR_FIELD_TYPE,
    ATTR_LIGHT_BRIGHTNESS,
    ATTR_LIGHT_CUSTOM_PRESETS,
    ATTR_LIGHT_DEFAULT_PRESETS,
    ATTR_LIGHT_EFFECT,
    ATTR_LIGHT_EFFECT_CONFIG,
    ATTR_LIGHT_EFFECTS,
    ATTR_LIGHT_STATE,
    ATTR_PRESET_DEFAULT,
    ATTR_SELECT_AUDIO_INPUT,
    ATTR_SELECT_AUDIO_INPUT_NAME,
    ATTR_SELECT_AUDIO_INPUT_OPTIONS,
    ATTR_SELECT_DEVICE_EFFECT,
    ATTR_SELECT_DEVICE_PRESET,
    ATTR_STATE,
    SELECT_ICONS,
    SIGNAL_NEW_SELECT,
)
from .entity import LedFxEntity
from .enum import ActionType, EffectCategory, Version
from .exceptions import LedFxError
from .helper import find_effect, generate_entity_id
from .updater import LedFxEntityDescription, LedFxUpdater, async_get_updater

PARALLEL_UPDATES = 0

OPTIONS_MAP: Final = {
    ATTR_SELECT_AUDIO_INPUT: ATTR_SELECT_AUDIO_INPUT_OPTIONS,
}

SELECTS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key=ATTR_SELECT_AUDIO_INPUT,
        name=ATTR_SELECT_AUDIO_INPUT_NAME,
        icon="mdi:audio-input-stereo-minijack",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
    ),
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LedFx select entry.

    :param hass: HomeAssistant: Home Assistant object
    :param config_entry: ConfigEntry: ConfigEntry object
    :param async_add_entities: AddEntitiesCallback: AddEntitiesCallback callback object
    """

    updater: LedFxUpdater = async_get_updater(hass, config_entry.entry_id)

    @callback
    def add_select(entity: LedFxEntityDescription) -> None:
        """Add select.

        :param entity: LedFxEntityDescription: Sensor object
        """

        async_add_entities(
            [
                LedFxSelect(
                    f"{config_entry.entry_id}-{entity.device_code}-{entity.description.key}"
                    if entity.type
                    in (
                        ActionType.DEVICE,
                        ActionType.DEVICE_PRESET,
                        ActionType.DEVICE_EFFECT,
                    )
                    else f"{config_entry.entry_id}-{entity.description.key}",
                    entity,
                    updater,
                )
            ]
        )

    for select in SELECTS:
        add_select(
            LedFxEntityDescription(description=select, device_info=updater.device_info)
        )

    for select in updater.selects.values():
        add_select(select)

    updater.new_select_callback = async_dispatcher_connect(
        hass, SIGNAL_NEW_SELECT, add_select
    )


class LedFxSelect(LedFxEntity, SelectEntity):
    """LedFx select entry."""

    _options_key: str
    _type: ActionType

    def __init__(
        self,
        unique_id: str,
        entity: LedFxEntityDescription,
        updater: LedFxUpdater,
    ) -> None:
        """Initialize select.

        :param unique_id: str: Unique ID
        :param entity: LedFxEntityDescription object
        :param updater: LedFxUpdater: Luci updater object
        """

        LedFxEntity.__init__(
            self, unique_id, entity.description, updater, ENTITY_ID_FORMAT
        )

        self._type = entity.type
        self._attr_device_info = entity.device_info
        self._attr_available: bool = True

        if entity.type == ActionType.DEVICE:
            self._attr_device_code = entity.device_code

            self.entity_id = generate_entity_id(
                ENTITY_ID_FORMAT,
                updater.ip,
                f"{entity.device_code}_{entity.description.key}",
            )

            self._attr_current_option = updater.data.get(
                f"{entity.device_code}_{ATTR_LIGHT_EFFECT_CONFIG}", {}
            ).get(entity.description.key)

            self._attr_options = (
                entity.extra.get(ATTR_FIELD_OPTIONS, []) if entity.extra else []
            )

            if entity.extra:
                self._attr_field_type = entity.extra.get(ATTR_FIELD_TYPE)

            self._attr_extra_state_attributes = {
                ATTR_DEVICE: self._attr_device_code,
                ATTR_FIELD_EFFECTS: entity.extra.get(ATTR_FIELD_EFFECTS, [])
                if entity.extra
                else [],
            }

            self._attr_available = bool(
                updater.data.get(ATTR_STATE, False)
                and len(self._attr_options) > 0
                and updater.data.get(f"{self._attr_device_code}_{ATTR_LIGHT_STATE}")
                and updater.data.get(f"{self._attr_device_code}_{ATTR_LIGHT_EFFECT}")
                in self._attr_extra_state_attributes[ATTR_FIELD_EFFECTS]
            )

            if entity.description.key in SELECT_ICONS:
                self._attr_icon = SELECT_ICONS[entity.description.key]

            return

        if entity.type in (ActionType.DEVICE_PRESET, ActionType.DEVICE_EFFECT):
            self._attr_device_code = entity.device_code

            self.entity_id = generate_entity_id(
                ENTITY_ID_FORMAT,
                updater.ip,
                f"{entity.device_code}_{entity.description.key}",
            )

            self._attr_extra_state_attributes = {ATTR_DEVICE: self._attr_device_code}

            if entity.type == ActionType.DEVICE_EFFECT:
                self._attr_current_option = self._updater.data.get(
                    f"{self._attr_device_code}_{ATTR_LIGHT_EFFECT}"
                )
                self._attr_options = self._effect_select_options()
                self._attr_available = self._effect_select_available()
            else:
                self._attr_current_option = None
                self._attr_options = self._preset_options()
                self._attr_available = self._preset_available()

            return

        self._attr_current_option = updater.data.get(entity.description.key, None)

        self._options_key = (
            OPTIONS_MAP[entity.description.key]
            if entity.description.key in OPTIONS_MAP
            else f"{entity.description.key}_options"
        )

        options: dict | list = updater.data.get(self._options_key, [])
        self._attr_options = (
            list(options.values()) if isinstance(options, dict) else options
        )

        self._attr_available = bool(
            updater.data.get(ATTR_STATE, False) and len(self._attr_options) > 0
        )

    def _handle_coordinator_update(self) -> None:
        """Update state."""

        is_available: bool = self._attr_available
        current_option: str = self._attr_current_option
        options: dict | list = self._attr_options

        if self._type == ActionType.DEVICE_EFFECT:
            options = self._effect_select_options()
            is_available = self._effect_select_available()
            current_option = self._updater.data.get(
                f"{self._attr_device_code}_{ATTR_LIGHT_EFFECT}"
            )
        elif self._type == ActionType.DEVICE_PRESET:
            options = self._preset_options()
            is_available = self._preset_available()

            # Backend reports the effect type only, not the active preset, so drop
            # the selection once it no longer applies to the current effect.
            current_option = (
                self._attr_current_option
                if self._attr_current_option in options
                else None
            )
        elif self._type == ActionType.DEVICE:
            current_option = self._updater.data.get(
                f"{self._attr_device_code}_{ATTR_LIGHT_EFFECT_CONFIG}", {}
            ).get(self.entity_description.key)

            is_available = bool(
                self._updater.data.get(ATTR_STATE, False)
                and len(options) > 0
                and self._updater.data.get(
                    f"{self._attr_device_code}_{ATTR_LIGHT_STATE}"
                )
                and self._updater.data.get(
                    f"{self._attr_device_code}_{ATTR_LIGHT_EFFECT}"
                )
                in self._attr_extra_state_attributes[ATTR_FIELD_EFFECTS]
            )
        else:
            current_option = self._updater.data.get(self.entity_description.key, False)
            options = self._updater.data.get(self._options_key, [])
            options = list(options.values()) if isinstance(options, dict) else options

            is_available = bool(
                self._updater.data.get(ATTR_STATE, False) and len(options) > 0
            )

        if (
            self._attr_current_option == current_option
            and self._attr_options == options
            and self._attr_available == is_available
        ):
            return

        self._attr_available = is_available
        self._attr_current_option = current_option
        self._attr_options = options

        self.async_write_ha_state()

    def _effect_select_options(self) -> list:
        """Base effects available on the instance.

        :return list: Effect options
        """

        return list(self._updater.data.get(ATTR_LIGHT_EFFECTS, []))

    def _effect_select_available(self) -> bool:
        """Effect select availability.

        :return bool: Is available
        """

        return bool(
            self._updater.data.get(ATTR_STATE, False)
            and len(self._effect_select_options()) > 0
        )

    async def _effect_change(self, option: str) -> bool:
        """Set the device's base effect (loads that effect's default config).

        :param option: str: Effect option
        :return bool: Result
        """

        try:
            response: dict = dict(
                await self._updater.client.device_on(
                    self._attr_device_code,  # type: ignore
                    option,
                    self._updater.version == Version.V2,
                )
            )
        except LedFxError as _e:
            _LOGGER.debug("Effect update error: %r", _e)

            return False

        effect_config: dict = {
            key: value
            for key, value in response.get("effect", {}).get("config", {}).items()
            if not isinstance(value, (dict, list))
        }

        self._updater.data[f"{self._attr_device_code}_{ATTR_LIGHT_EFFECT}"] = option
        self._updater.data[f"{self._attr_device_code}_{ATTR_LIGHT_STATE}"] = True
        self._updater.data[f"{self._attr_device_code}_{ATTR_LIGHT_EFFECT_CONFIG}"] = {
            code: value
            for code, value in effect_config.items()
            if code != ATTR_LIGHT_BRIGHTNESS
        }

        # Refresh siblings (light, preset select) so the new effect/presets show
        # immediately instead of on the next poll.
        self._updater.async_update_listeners()

        return True

    def _preset_options(self) -> list:
        """Presets available for the device's current effect.

        The synthetic "Default" option (re-applies the effect's default config)
        is always offered first when an effect is set, so the selector is usable
        even for effects that ship no presets.

        :return list: Preset options
        """

        effect: str | None = self._updater.data.get(
            f"{self._attr_device_code}_{ATTR_LIGHT_EFFECT}"
        )

        if not effect:
            return []

        default_presets: dict = self._updater.data.get(ATTR_LIGHT_DEFAULT_PRESETS, {})
        custom_presets: dict = self._updater.data.get(ATTR_LIGHT_CUSTOM_PRESETS, {})

        return [ATTR_PRESET_DEFAULT] + sorted(
            set(default_presets.get(effect, []) + custom_presets.get(effect, []))
        )

    def _preset_available(self) -> bool:
        """Preset select availability.

        :return bool: Is available
        """

        return bool(
            self._updater.data.get(ATTR_STATE, False)
            and self._updater.data.get(f"{self._attr_device_code}_{ATTR_LIGHT_STATE}")
            and len(self._preset_options()) > 0
        )

    async def _preset_change(self, option: str) -> bool:
        """Apply a preset (or reset to default) for the device's current effect.

        :param option: str: Preset option
        :return bool: Result
        """

        effect: str | None = self._updater.data.get(
            f"{self._attr_device_code}_{ATTR_LIGHT_EFFECT}"
        )

        if not effect:
            return False

        if option == ATTR_PRESET_DEFAULT:
            return await self._effect_change(effect)

        _, preset, category = find_effect(
            f"{effect} - {option}",
            self._updater.data.get(ATTR_LIGHT_DEFAULT_PRESETS, {}),
            self._updater.data.get(ATTR_LIGHT_CUSTOM_PRESETS, {}),
        )

        if category == EffectCategory.NONE or preset is None:
            return False

        try:
            await self._updater.client.preset(
                self._attr_device_code,  # type: ignore
                category.value,
                effect,
                preset,
                self._updater.version == Version.V2,
            )

            return True
        except LedFxError as _e:
            _LOGGER.debug("Preset update error: %r", _e)

        return False

    async def _audio_input_change(self, option: str) -> bool:
        """Audio input

        :param option: str: Option value
        :return bool: Result
        """

        options: dict = self._updater.data.get(self._options_key, {})
        if option_ids := [_id for _id, name in options.items() if name == option]:
            try:
                await self._updater.client.set_audio_device(
                    int(option_ids[0]), self._updater.version == Version.V2
                )

                return True
            except LedFxError as _e:
                _LOGGER.debug("Audio input update error: %r", _e)

        return False

    async def _device_change(self, option: str) -> bool:
        """Device input

        :param option: str: Option value
        :return bool: Result
        """

        await self.async_update_effect(self.entity_description.key, option)

        return True

    async def async_select_option(self, option: str) -> None:
        """Select option

        :param option: str: Option
        """

        code: str = (
            ActionType.DEVICE
            if self._type == ActionType.DEVICE
            else self.entity_description.key
        )

        if action := getattr(self, f"_{code}_change"):
            if await action(option):
                if self._type == ActionType.DEFAULT:
                    self._updater.data[self.entity_description.key] = option

                self._attr_current_option = option

            self.async_write_ha_state()
