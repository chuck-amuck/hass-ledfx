"""LedFx API client exceptions."""

from homeassistant.exceptions import HomeAssistantError


class LedFxError(HomeAssistantError):
    """LedFx error.

    An ordinary exception, so that Home Assistant's update coordinator, service
    calls and config flows catch it instead of letting it escape as a crash.
    """


class LedFxConnectionError(LedFxError):
    """LedFx connection error"""


class LedFxRequestError(LedFxError):
    """LedFx request error"""
