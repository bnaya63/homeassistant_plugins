"""Dreame vacuum platform."""

import logging

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.vacuum import (
    SPEED_HIGH, SPEED_MEDIUM, SPEED_LOW, SPEED_MAX, SPEED_MIN,
    STATE_IDLE, STATE_CLEANING, STATE_RETURNING, STATE_DOCKED,
    STATE_ERROR, ATTR_BATTERY_LEVEL, STATE_PAUSED,
    SUPPORT_CLEAN, SUPPORT_SPOT_CLEAN, SUPPORT_RETURN_TO_DOCK, SUPPORT_PAUSE, SUPPORT_SEEK,
    VacuumEntity
)

from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_IP_ADDRESS, CONF_NAME
)

DEFAULT_NAME = "Dreame Vacuum"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Dreame vacuum platform."""
    ip = config.get(CONF_IP_ADDRESS)
    name = config.get(CONF_NAME, DEFAULT_NAME)
    
    if not ip:
        return
    
    entity = DreameVacuum(ip, name)
    async_add_entities([entity], True)


class DreameVacuum(VacuumEntity):
    """Representation of a Dreame vacuum cleaner."""
    
    _attr_supported_features = (
        SUPPORT_CLEAN
        | SUPPORT_RETURN_TO_DOCK
        | SUPPORT_PAUSE
        | SUPPORT_SPOT_CLEAN
    )
    
    def __init__(self, ip, name):
        """Initialize the Dreame vacuum."""
        self._ip = ip
        self._name = name
        self._state = STATE_IDLE
        self._battery_level = 100
        self._clean_time = 0
    
    @property
    def name(self):
        """Return the name of the vacuum."""
        return self._name
    
    @property
    def state(self):
        """Return the state of the vacuum."""
        return self._state
    
    @property
    def battery_level(self):
        """Return the battery level."""
        return self._battery_level
    
    @property
    def clean_mode(self):
        """Return the clean mode."""
        return "auto"
    
    @property
    def supported_features(self):
        """Flag supported features."""
        return self._attr_supported_features
    
    async def async_update(self):
        """Update the state of the vacuum."""
        import socket
        import struct
        import json
        import hashlib
        import time
        
        IP = self._ip
        PORT = 54321
        # Device ID from hello response: 0x3da4535f = 1034179423
        dev_id = 1034179423
        
        ts = int(time.time())
        
        # Build miio packet
        payload = json.dumps({
            "id": 1,
            "method": "miIO.info",
            "params": []
        }).encode()
        
        header = struct.pack(">HHIIII", 0x2131, 32 + len(payload), 0, ts, dev_id, 0)
        checksum = hashlib.md5(header + b"\x00"*16 + payload).digest()
        pkt = header + checksum + payload
        
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3)
        s.sendto(pkt, (IP, PORT))
        try:
            data, addr = s.recvfrom(4096)
            # Parse response
            hd = data[:16]
            magic = hd[0:4]
            length = struct.unpack(">H", hd[2:4])[0]
            dev_id_resp = struct.unpack(">I", hd[8:12])[0]
            ts_resp = struct.unpack(">I", hd[12:16])[0]
            
            body = data[32:]
            if body:
                try:
                    # Try to decode as JSON
                    state = json.loads(body.decode())
                    self._process_state(state)
                except Exception as e:
                    _LOGGER.warning("Failed to parse vacuum state: %s", e)
        except Exception as e:
            _LOGGER.warning("Failed to update vacuum state: %s", e)
        finally:
            s.close()
    
    def _process_state(self, state):
        """Process the vacuum state from miio response."""
        if isinstance(state, dict):
            if "power" in state:
                self._state = STATE_CLEANING if state["power"] else STATE_IDLE
            if "battery" in state:
                self._battery_level = state.get("battery", self._battery_level)
            if "runtime" in state:
                self._clean_time = state["runtime"]