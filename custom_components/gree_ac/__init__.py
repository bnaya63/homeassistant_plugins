"""Gree AC climate platform."""

import logging

_LOGGER = logging.getLogger(__name__)

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA

DEFAULT_NAME = "Gree AC"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Gree AC climate platform."""
    ip = config.get("host")
    name = config.get("name", DEFAULT_NAME)
    mac = config.get("mac", "")
    
    if not ip:
        return
    
    entity = GreeAcClimate(ip, name, mac)
    async_add_entities([entity], True)