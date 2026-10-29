"""Gree AC climate integration for Home Assistant."""

import logging

_LOGGER = logging.getLogger(__name__)

import json
import base64

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRESET_MODE_AUTO,
    PRESET_MODE_ECO,
    PRESET_MODE_COMFORT,
    PRESET_MODE_SLEEP,
    TEMP_CELSIUS,
    UnitOfTemperature,
)

DEFAULT_NAME = "Gree AC"

PRESET_MODES = [PRESET_MODE_AUTO, PRESET_MODE_ECO, PRESET_MODE_COMFORT, PRESET_MODE_SLEEP]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Gree AC climate platform."""
    ip = config.get("host")
    name = config.get("name", DEFAULT_NAME)
    mac = config.get("mac", "")
    
    if not ip:
        return
    
    entity = GreeAcClimate(ip, name, mac)
    async_add_entities([entity], True)


class GreeAcClimate(ClimateEntity):
    """Representation of a Gree AC unit."""
    
    def __init__(self, ip, name, mac):
        """Initialize the Gree AC."""
        self._ip = ip
        self._name = name
        self._mac = mac
        self._temperature = None
        self._power = False
        self._mode = PRESET_MODE_AUTO
        self._fan_mode = "auto"
        self._target_temperature = None
        self._key = None
    
    @property
    def name(self):
        """Return the name of the climate entity."""
        return self._name
    
    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS
    
    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temperature
    
    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._target_temperature
    
    @property
    def preset_mode(self):
        """Return the current preset mode."""
        return self._mode
    
    @property
    def supported_features(self):
        """Flag supported features."""
        return 0
    
    @property
    def preset_modes(self):
        """Return available preset modes."""
        return PRESET_MODES
    
    @property
    def current_humidity(self):
        """Return the current humidity."""
        return None
    
    @property
    def fan_mode(self):
        """Return the fan mode."""
        return self._fan_mode
    
    @property
    def hvac_mode(self):
        """Return current hvac mode."""
        return self._mode
    
    @property
    def hvac_modes(self):
        """Return available hvac modes."""
        return ["off", "cool", "heat", "fan_only", "dry"]
    
    async def async_update(self):
        """Update the state of the Gree AC."""
        # If we don't have a device key, try bind
        if not self._key:
            await self._async_bind()
        
        if not self._key:
            return
        
        # Send status request
        await self._async_status()
    
    async def _async_bind(self):
        """Bind with the Gree device to get a device key."""
        import socket
        
        mac = self._mac or "9424b8a11e52"  # default MAC
        
        wrapper = {"cid": "app", "i": 1, "uid": 0, "tcid": mac}
        bind_inner = {"t": "bind", "mac": mac, "uid": 0}
        
        from gree_aes import aes_ecb_encrypt
        
        raw = json.dumps(bind_inner).encode()
        enc = aes_ecb_encrypt(raw, b"a3K8Bx%2r8Y7#xDh")
        pack = base64.b64encode(enc).decode()
        wrapper["t"] = "pack"
        wrapper["pack"] = pack
        
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3)
        s.sendto(json.dumps(wrapper).encode(), (self._ip, 7000))
        try:
            data, addr = s.recvfrom(4096)
            resp = json.loads(data)
            if "pack" in resp:
                # Decrypt the pack
                from gree_aes import aes_ecb_decrypt
                dec = aes_ecb_decrypt(base64.b64decode(resp["pack"]), b"a3K8Bx%2r8Y7#xDh")
                txt = dec.rstrip(b"\x00").rstrip(b"\n").rstrip(b"\r")
                pack_data = json.loads(txt)
                self._key = pack_data.get("key", "")
                _LOGGER.info("Bind successful, key: %s", self._key)
        except Exception as e:
            _LOGGER.warning("Bind failed: %s", e)
        finally:
            s.close()
    
    def _decrypt_pack(self, b64, key):
        """Decrypt a Gree pack."""
        from gree_aes import aes_ecb_decrypt
        import base64
        import json
        
        dec = aes_ecb_decrypt(base64.b64decode(b64), key.encode())
        txt = dec.rstrip(b"\x00").rstrip(b"\n").rstrip(b"\r")
        return json.loads(txt)
    
    async def _async_status(self):
        """Get status from the Gree AC."""
        import socket
        import json
        import base64
        
        if not self._key:
            return
        
        wrapper = {"cid": "app", "i": 1, "uid": 0, "tcid": self._mac}
        status_inner = {"t": "status", "mac": self._mac, "cols": ["Temperature", "Power", "Mode", "FanSpeed"]}
        
        raw = json.dumps(status_inner).encode()
        enc = __import__("gree_aes").aes_ecb_encrypt(raw, self._key.encode())
        pack = base64.b64encode(enc).decode()
        wrapper["t"] = "pack"
        wrapper["pack"] = pack
        
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3)
        s.sendto(json.dumps(wrapper).encode(), (self._ip, 7000))
        try:
            data, addr = s.recvfrom(4096)
            resp = json.loads(data)
            if "pack" in resp:
                pack_data = self._decrypt_pack(resp["pack"], self._key)
                dat = pack_data.get("dat", [])
                cols = pack_data.get("cols", [])
                state = dict(zip(cols, dat)) if dat and cols else {}
                
                if "Temperature" in state:
                    self._temperature = state["Temperature"]
                if "Power" in state:
                    self._power = state["Power"] == True
                if "Mode" in state:
                    self._mode = state["Mode"]
                if "FanSpeed" in state:
                    self._fan_mode = str(state["FanSpeed"])
        except Exception as e:
            _LOGGER.warning("Status request failed: %s", e)
        finally:
            s.close()
    
    async def async_set_temperature(self, **kwargs):
        """Set target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            self._target_temperature = temp
            # TODO: Send set temperature command
    
    async def async_set_preset_mode(self, preset_mode):
        """Set preset mode."""
        self._mode = preset_mode
        # TODO: Send preset mode command
    
    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        mode_map = {
            "off": "0",
            "cool": "1",
            "heat": "2",
            "fan_only": "3",
            "dry": "4",
        }
        code = mode_map.get(hvac_mode, "0")
        # TODO: Send mode command
        self._mode = hvac_mode