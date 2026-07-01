"""Tests for the ledfx component."""

# pylint: disable=no-member,too-many-statements,protected-access,too-many-lines

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Final
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_EFFECT, ATTR_RGBW_COLOR
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.light import ENTITY_ID_FORMAT as LIGHT_ENTITY_ID_FORMAT
from homeassistant.components.light import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    load_fixture,
)

from custom_components.ledfx.const import (
    ATTRIBUTION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    UPDATER,
)
from custom_components.ledfx.exceptions import LedFxRequestError
from custom_components.ledfx.helper import generate_entity_id
from custom_components.ledfx.updater import LedFxUpdater
from tests.setup import MultipleSideEffect, async_mock_client_2, async_setup

_LOGGER = logging.getLogger(__name__)

# Presets are no longer mixed into the effect list; they are exposed via the
# dedicated per-device "Preset" select. The effect list holds base effects only,
# presented as "Category: Name" labels ordered by category then name.
EFFECT_LIST: Final = [
    "2D: Bands",
    "2D: Bands Matrix",
    "2D: Blocks",
    "2D: Equalizer",
    "Atmospheric: Block Reflections",
    "Atmospheric: Crawler",
    "Atmospheric: Energy 2",
    "Atmospheric: Fire",
    "Atmospheric: Glitch",
    "Atmospheric: Lava lamp",
    "Atmospheric: Marching",
    "Atmospheric: Melt",
    "BPM: Bar",
    "BPM: BPM Strobe",
    "BPM: Multicolor Bar",
    "Classic: Blade Power+",
    "Classic: Energy",
    "Classic: Magnitude",
    "Classic: Pitch Spectrum",
    "Classic: Power",
    "Classic: Rain",
    "Classic: Scroll",
    "Classic: Spectrum",
    "Classic: Strobe",
    "Classic: Wavelength",
    "Non-Reactive: Fade",
    "Non-Reactive: Gradient",
    "Non-Reactive: Rainbow",
    "Non-Reactive: Single Color",
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations"""

    yield


@pytest.mark.asyncio
async def test_devices(hass: HomeAssistant) -> None:
    """Test devices.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        def success() -> dict:
            return json.loads(load_fixture("devices_v2_data.json"))

        def error() -> None:
            raise LedFxRequestError

        mock_client.return_value.devices = AsyncMock(
            side_effect=MultipleSideEffect(success, error)
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]

        assert updater.last_update_success

        unique_id: str = _generate_id("wled", updater.ip)

        state: State = hass.states.get(unique_id)
        assert state.state == STATE_ON
        assert state.name == "WLED"
        assert state.attributes["icon"] == "mdi:led-strip-variant"
        assert state.attributes["effect_list"] == EFFECT_LIST
        assert state.attributes["effect"] == "Classic: Magnitude"
        assert state.attributes["attribution"] == ATTRIBUTION

        unique_id = _generate_id("wled-1", updater.ip)

        state = hass.states.get(unique_id)
        assert state.state == STATE_OFF
        assert state.name == "WLED"
        assert state.attributes["icon"] == "mdi:led-strip-variant"
        assert state.attributes["effect_list"] == EFFECT_LIST
        assert state.attributes["attribution"] == ATTRIBUTION

        async_fire_time_changed(
            hass, utcnow() + timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1)
        )
        await hass.async_block_till_done()

        unique_id = _generate_id("wled", updater.ip)

        state = hass.states.get(unique_id)
        assert state.state == STATE_UNAVAILABLE

        unique_id = _generate_id("wled-1", updater.ip)

        state = hass.states.get(unique_id)
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_devices_without_custom_preset(hass: HomeAssistant) -> None:
    """Test devices without custom preset.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        mock_client.return_value.config = AsyncMock(
            return_value=json.loads(
                load_fixture("config_empty_custom_presets_v2_data.json")
            )
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]

        assert updater.last_update_success

        unique_id: str = _generate_id("wled", updater.ip)

        state: State = hass.states.get(unique_id)
        assert state.state == STATE_ON
        # Presets live in the preset select now, so empty custom presets no longer
        # shrink the effect list.
        assert len(state.attributes["effect_list"]) == len(EFFECT_LIST)

        unique_id = _generate_id("wled-1", updater.ip)

        state = hass.states.get(unique_id)
        assert state.state == STATE_OFF
        assert len(state.attributes["effect_list"]) == len(EFFECT_LIST)


@pytest.mark.asyncio
async def test_new_devices(hass: HomeAssistant) -> None:
    """Test new_devices.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        def success() -> dict:
            return json.loads(load_fixture("devices_v2_data.json"))

        def success_two() -> dict:
            return json.loads(load_fixture("devices_changed_v2_data.json"))

        mock_client.return_value.devices = AsyncMock(
            side_effect=MultipleSideEffect(success, success_two)
        )

        def v_success() -> dict:
            return json.loads(load_fixture("virtuals_data.json"))

        def v_success_two() -> dict:
            return json.loads(load_fixture("virtuals_changed_data.json"))

        mock_client.return_value.virtuals = AsyncMock(
            side_effect=MultipleSideEffect(v_success, v_success_two)
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]
        registry = er.async_get(hass)

        assert updater.last_update_success

        unique_id: str = _generate_id("wled-2", updater.ip)
        entry: er.RegistryEntry | None = registry.async_get(unique_id)

        assert hass.states.get(unique_id) is None
        assert entry is None

        async_fire_time_changed(
            hass, utcnow() + timedelta(seconds=DEFAULT_SCAN_INTERVAL + 30)
        )
        await hass.async_block_till_done()

        state = hass.states.get(unique_id)
        assert state.state == STATE_OFF
        assert state.name == "WLED"
        assert state.attributes["attribution"] == ATTRIBUTION


@pytest.mark.asyncio
async def test_devices_on(hass: HomeAssistant) -> None:
    """Test devices on.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        def success(device_code: str, effect: str, is_virtual: bool = False) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "bands"

            return json.loads(load_fixture("device_on_data.json"))

        def error(device_code: str, effect: str, is_virtual: bool = False) -> None:
            raise LedFxRequestError

        mock_client.return_value.device_on = AsyncMock(
            side_effect=MultipleSideEffect(success, error)
        )

        def success_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "bands"
            assert config == {
                "active": True,
                "background_color": "black",
                "blur": 3.0,
                "brightness": 0.0,
                "flip": False,
                "gradient_name": "Rainbow",
                "gradient_repeat": 1,
                "gradient_roll": 0,
                "isProcessing": False,
                "mirror": False,
                "name": "Wavelength",
                "type": "wavelength(Reactive)",
            }

            return json.loads(load_fixture("effect_data.json"))

        mock_client.return_value.effect = AsyncMock(
            side_effect=MultipleSideEffect(success_effect, success_effect)
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]

        assert updater.last_update_success

        unique_id = _generate_id("wled-1", updater.ip)

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [unique_id]},
            blocking=True,
            limit=None,
        )

        state = hass.states.get(unique_id)
        assert state.state == STATE_ON
        assert state.attributes["effect"] == "2D: Bands"

        with pytest.raises(LedFxRequestError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: [unique_id], ATTR_EFFECT: "wavelength(Reactive)"},
                blocking=True,
                limit=None,
            )


@pytest.mark.asyncio
async def test_devices_on_with_effect(hass: HomeAssistant) -> None:
    """Test devices on with effect.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        def success(device_code: str, effect: str, is_virtual: bool = False) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "wavelength(Reactive)"

            return json.loads(load_fixture("device_on_data.json"))

        def error(device_code: str, effect: str, is_virtual: bool = False) -> None:
            raise LedFxRequestError

        mock_client.return_value.device_on = AsyncMock(
            side_effect=MultipleSideEffect(success, error)
        )

        def success_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "wavelength(Reactive)"
            assert config == {
                "active": True,
                "background_color": "black",
                "blur": 3.0,
                "brightness": 0.0,
                "flip": False,
                "gradient_name": "Rainbow",
                "gradient_repeat": 1,
                "gradient_roll": 0,
                "isProcessing": False,
                "mirror": False,
                "name": "Wavelength",
                "type": "wavelength(Reactive)",
            }

            return json.loads(load_fixture("effect_data.json"))

        mock_client.return_value.effect = AsyncMock(
            side_effect=MultipleSideEffect(success_effect, success_effect)
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]

        assert updater.last_update_success

        unique_id = _generate_id("wled-1", updater.ip)

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [unique_id], ATTR_EFFECT: "wavelength(Reactive)"},
            blocking=True,
            limit=None,
        )

        state = hass.states.get(unique_id)
        assert state.state == STATE_ON
        assert state.attributes["effect"] == "wavelength(Reactive)"

        with pytest.raises(LedFxRequestError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: [unique_id], ATTR_EFFECT: "bar(Reactive)"},
                blocking=True,
                limit=None,
            )


@pytest.mark.asyncio
async def test_devices_on_with_effect_and_brightness(hass: HomeAssistant) -> None:
    """Test devices on with effect and brightness.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        def success(device_code: str, effect: str, is_virtual: bool = False) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "wavelength(Reactive)"

            return json.loads(load_fixture("device_on_data.json"))

        mock_client.return_value.device_on = AsyncMock(
            side_effect=MultipleSideEffect(success, success)
        )

        def success_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "wavelength(Reactive)"
            assert config == {
                "active": True,
                "background_color": None,
                "blur": 3.0,
                "brightness": 0.5,
                "flip": False,
                "gradient_name": "Rainbow",
                "gradient_repeat": 1,
                "gradient_roll": 0,
                "isProcessing": False,
                "mirror": False,
                "name": "Wavelength",
                "type": "wavelength(Reactive)",
            }

            return json.loads(load_fixture("effect_data.json"))

        def error_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> None:
            raise LedFxRequestError

        mock_client.return_value.effect = AsyncMock(
            side_effect=MultipleSideEffect(success_effect, error_effect)
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]

        assert updater.last_update_success

        unique_id = _generate_id("wled-1", updater.ip)

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: [unique_id],
                ATTR_EFFECT: "wavelength(Reactive)",
                ATTR_BRIGHTNESS: 125,
            },
            blocking=True,
            limit=None,
        )

        state = hass.states.get(unique_id)
        assert state.state == STATE_ON
        assert state.attributes["brightness"] == 125
        assert state.attributes["effect"] == "wavelength(Reactive)"

        with pytest.raises(LedFxRequestError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: [unique_id],
                    ATTR_EFFECT: "wavelength(Reactive)",
                    ATTR_BRIGHTNESS: 125,
                },
                blocking=True,
                limit=None,
            )


@pytest.mark.asyncio
async def test_devices_on_with_effect_and_rgbw(hass: HomeAssistant) -> None:
    """Test devices on with effect and rgbw.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        def success(device_code: str, effect: str, is_virtual: bool = False) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "wavelength(Reactive)"

            return json.loads(load_fixture("device_on_data.json"))

        mock_client.return_value.device_on = AsyncMock(
            side_effect=MultipleSideEffect(success, success)
        )

        def success_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "wavelength(Reactive)"
            assert config == {
                "active": True,
                "background_color": "#ea7d7e",
                "blur": 3.0,
                "brightness": 0.0,
                "flip": False,
                "gradient_name": "Rainbow",
                "gradient_repeat": 1,
                "gradient_roll": 0,
                "isProcessing": False,
                "mirror": False,
                "name": "Wavelength",
                "type": "wavelength(Reactive)",
            }

            return json.loads(load_fixture("effect_data.json"))

        def error_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> None:
            raise LedFxRequestError

        mock_client.return_value.effect = AsyncMock(
            side_effect=MultipleSideEffect(success_effect, error_effect)
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]

        assert updater.last_update_success

        unique_id = _generate_id("wled-1", updater.ip)

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: [unique_id],
                ATTR_EFFECT: "wavelength(Reactive)",
                ATTR_RGBW_COLOR: (234, 125, 126, 0),
            },
            blocking=True,
            limit=None,
        )

        state = hass.states.get(unique_id)
        assert state.state == STATE_ON
        assert state.attributes["effect"] == "wavelength(Reactive)"

        with pytest.raises(LedFxRequestError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: [unique_id],
                    ATTR_EFFECT: "wavelength(Reactive)",
                    ATTR_RGBW_COLOR: (234, 125, 126, 0),
                },
                blocking=True,
                limit=None,
            )


@pytest.mark.asyncio
async def test_devices_on_with_effect_and_rgbw_white(hass: HomeAssistant) -> None:
    """Test devices on with effect and rgbw.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        def success(device_code: str, effect: str, is_virtual: bool = False) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "wavelength(Reactive)"

            return json.loads(load_fixture("device_on_data.json"))

        mock_client.return_value.device_on = AsyncMock(
            side_effect=MultipleSideEffect(success, success)
        )

        def success_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "wavelength(Reactive)"
            assert config == {
                "active": True,
                "background_color": "#ffffff",
                "blur": 3.0,
                "brightness": 0.0,
                "flip": False,
                "gradient_name": "Rainbow",
                "gradient_repeat": 1,
                "gradient_roll": 0,
                "isProcessing": False,
                "mirror": False,
                "name": "Wavelength",
                "type": "wavelength(Reactive)",
            }

            return json.loads(load_fixture("effect_data.json"))

        def error_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> None:
            raise LedFxRequestError

        mock_client.return_value.effect = AsyncMock(
            side_effect=MultipleSideEffect(success_effect, error_effect)
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]

        assert updater.last_update_success

        unique_id = _generate_id("wled-1", updater.ip)

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: [unique_id],
                ATTR_EFFECT: "wavelength(Reactive)",
                ATTR_RGBW_COLOR: (0, 0, 0, 255),
            },
            blocking=True,
            limit=None,
        )

        state = hass.states.get(unique_id)
        assert state.state == STATE_ON
        assert state.attributes["effect"] == "wavelength(Reactive)"

        with pytest.raises(LedFxRequestError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: [unique_id],
                    ATTR_EFFECT: "wavelength(Reactive)",
                    ATTR_RGBW_COLOR: (0, 0, 0, 255),
                },
                blocking=True,
                limit=None,
            )


@pytest.mark.asyncio
async def test_devices_on_with_effect_and_rgbw_white_two(hass: HomeAssistant) -> None:
    """Test devices on with effect and rgbw.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        def success(device_code: str, effect: str, is_virtual: bool = False) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "wavelength(Reactive)"

            return json.loads(load_fixture("device_on_data.json"))

        mock_client.return_value.device_on = AsyncMock(
            side_effect=MultipleSideEffect(success, success)
        )

        def success_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "wavelength(Reactive)"
            assert config == {
                "active": True,
                "background_color": "#ffffff",
                "blur": 3.0,
                "brightness": 0.0,
                "flip": False,
                "gradient_name": "Rainbow",
                "gradient_repeat": 1,
                "gradient_roll": 0,
                "isProcessing": False,
                "mirror": False,
                "name": "Wavelength",
                "type": "wavelength(Reactive)",
            }

            return json.loads(load_fixture("effect_data.json"))

        def error_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> None:
            raise LedFxRequestError

        mock_client.return_value.effect = AsyncMock(
            side_effect=MultipleSideEffect(success_effect, error_effect)
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]

        assert updater.last_update_success

        unique_id = _generate_id("wled-1", updater.ip)

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: [unique_id],
                ATTR_EFFECT: "wavelength(Reactive)",
                ATTR_RGBW_COLOR: (255, 255, 255, 255),
            },
            blocking=True,
            limit=None,
        )

        state = hass.states.get(unique_id)
        assert state.state == STATE_ON
        assert state.attributes["effect"] == "wavelength(Reactive)"

        with pytest.raises(LedFxRequestError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: [unique_id],
                    ATTR_EFFECT: "wavelength(Reactive)",
                    ATTR_RGBW_COLOR: (255, 255, 255, 255),
                },
                blocking=True,
                limit=None,
            )


@pytest.mark.asyncio
async def test_devices_on_with_effect_and_rgbw_black(hass: HomeAssistant) -> None:
    """Test devices on with effect and rgbw.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        def success(device_code: str, effect: str, is_virtual: bool = False) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "wavelength(Reactive)"

            return json.loads(load_fixture("device_on_data.json"))

        mock_client.return_value.device_on = AsyncMock(
            side_effect=MultipleSideEffect(success, success)
        )

        def success_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert effect == "wavelength(Reactive)"
            assert config == {
                "active": True,
                "background_color": "#000000",
                "blur": 3.0,
                "brightness": 0.0,
                "flip": False,
                "gradient_name": "Rainbow",
                "gradient_repeat": 1,
                "gradient_roll": 0,
                "isProcessing": False,
                "mirror": False,
                "name": "Wavelength",
                "type": "wavelength(Reactive)",
            }

            return json.loads(load_fixture("effect_data.json"))

        def error_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> None:
            raise LedFxRequestError

        mock_client.return_value.effect = AsyncMock(
            side_effect=MultipleSideEffect(success_effect, error_effect)
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]

        assert updater.last_update_success

        unique_id = _generate_id("wled-1", updater.ip)

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: [unique_id],
                ATTR_EFFECT: "wavelength(Reactive)",
                ATTR_RGBW_COLOR: (0, 0, 0, 0),
            },
            blocking=True,
            limit=None,
        )

        state = hass.states.get(unique_id)
        assert state.state == STATE_ON
        assert state.attributes["effect"] == "wavelength(Reactive)"

        with pytest.raises(LedFxRequestError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: [unique_id],
                    ATTR_EFFECT: "wavelength(Reactive)",
                    ATTR_RGBW_COLOR: (0, 0, 0, 0),
                },
                blocking=True,
                limit=None,
            )


@pytest.mark.asyncio
async def test_devices_on_with_preset(hass: HomeAssistant) -> None:
    """Test devices on with preset.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        def success(
            device_code: str,
            category: str,
            effect: str,
            preset: str,
            is_virtual: bool = False,
        ) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert category == "ledfx_presets"
            assert effect == "bar"
            assert preset == "bouncing-blues"

            return json.loads(load_fixture("preset_data.json"))

        def error(
            device_code: str,
            category: str,
            effect: str,
            preset: str,
            is_virtual: bool = False,
        ) -> None:
            raise LedFxRequestError

        mock_client.return_value.preset = AsyncMock(
            side_effect=MultipleSideEffect(success, error)
        )

        def success_effect(device_code: str, effect: str, config: dict) -> dict:
            assert device_code == "wled-1"
            assert effect == "bar"
            assert config == {
                "background_color": "black",
                "blur": 8.587469069357562,
                "brightness": 0.0,
                "flip": True,
                "gradient_name": "Sunset",
                "gradient_repeat": 1,
                "gradient_roll": 4,
                "mirror": False,
            }

            return json.loads(load_fixture("effect_data.json"))

        mock_client.return_value.effect = AsyncMock(
            side_effect=MultipleSideEffect(success_effect, success_effect)
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]

        assert updater.last_update_success

        unique_id = _generate_id("wled-1", updater.ip)

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [unique_id], ATTR_EFFECT: "bar - bouncing-blues"},
            blocking=True,
            limit=None,
        )

        state = hass.states.get(unique_id)
        assert state.state == STATE_ON
        assert state.attributes["effect"] == "BPM: Bar"

        with pytest.raises(LedFxRequestError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: [unique_id], ATTR_EFFECT: "bar - bouncing-blues"},
                blocking=True,
                limit=None,
            )


@pytest.mark.asyncio
async def test_devices_on_with_preset_and_brightness(hass: HomeAssistant) -> None:
    """Test devices on with preset and brightness.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        def success(
            device_code: str,
            category: str,
            effect: str,
            preset: str,
            is_virtual: bool = False,
        ) -> dict:
            assert is_virtual
            assert device_code == "wled-1"
            assert category == "ledfx_presets"
            assert effect == "bar"
            assert preset == "bouncing-blues"

            return json.loads(load_fixture("preset_data.json"))

        mock_client.return_value.preset = AsyncMock(
            side_effect=MultipleSideEffect(success, success)
        )

        def success_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> dict:
            assert device_code == "wled-1"
            assert effect == "bar"
            assert config == {
                "background_color": None,
                "blur": 8.587469069357562,
                "brightness": 0.5,
                "flip": True,
                "gradient_name": "Sunset",
                "gradient_repeat": 1,
                "gradient_roll": 4,
                "mirror": False,
            }

            return json.loads(load_fixture("effect_data.json"))

        def error_effect(
            device_code: str, effect: str, config: dict, is_virtual: bool = False
        ) -> None:
            raise LedFxRequestError

        mock_client.return_value.effect = AsyncMock(
            side_effect=MultipleSideEffect(success_effect, error_effect)
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]

        assert updater.last_update_success

        unique_id = _generate_id("wled-1", updater.ip)

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: [unique_id],
                ATTR_EFFECT: "bar - bouncing-blues",
                ATTR_BRIGHTNESS: 125,
            },
            blocking=True,
            limit=None,
        )

        state = hass.states.get(unique_id)
        assert state.state == STATE_ON
        assert state.attributes["brightness"] == 125
        assert state.attributes["effect"] == "BPM: Bar"

        with pytest.raises(LedFxRequestError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: [unique_id],
                    ATTR_EFFECT: "bar - bouncing-blues",
                    ATTR_BRIGHTNESS: 125,
                },
                blocking=True,
                limit=None,
            )


@pytest.mark.asyncio
async def test_devices_off(hass: HomeAssistant) -> None:
    """Test devices off.

    :param hass: HomeAssistant
    """

    with patch("custom_components.ledfx.updater.LedFxClient") as mock_client:
        await async_mock_client_2(mock_client)

        def success(device_code: str, is_virtual: bool = False) -> dict:
            assert is_virtual
            assert device_code == "wled"

            return json.loads(load_fixture("device_off_data.json"))

        def error(device_code: str, is_virtual: bool = False) -> dict:
            raise LedFxRequestError

        mock_client.return_value.device_off = AsyncMock(
            side_effect=MultipleSideEffect(success, error)
        )

        _, config_entry = await async_setup(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        updater: LedFxUpdater = hass.data[DOMAIN][config_entry.entry_id][UPDATER]

        assert updater.last_update_success

        unique_id = _generate_id("wled", updater.ip)

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: [unique_id],
            },
            blocking=True,
            limit=None,
        )

        state = hass.states.get(unique_id)
        assert state.state == STATE_OFF

        with pytest.raises(LedFxRequestError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: [unique_id],
                },
                blocking=True,
                limit=None,
            )


def _generate_id(code: str, ip_address: str) -> str:
    """Generate unique id

    :param code: str
    :param ip_address: str
    :return str
    """

    return generate_entity_id(
        LIGHT_ENTITY_ID_FORMAT,
        ip_address,
        code,
    )
