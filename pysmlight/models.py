from dataclasses import dataclass

@dataclass
class Firmware:
    mode:str = None # ESP|ZB
    type:int = False
    notes:str = None
    rev:str = None
    link:str = None
    ver:str = None
    dev: bool = False

    def __init__(self, mode, json):
        self.mode = mode
        if mode == "ESP":
            self.dev = json['dev']
            self.ver = json['ver']
        else:
            self.type = int(json['type'])
        self.notes = json['notes']
        self.rev = json['rev']
        self.link = json['link']

@dataclass
class Info:
    coord_mode: int | str  = None # Should be Enum
    device_ip: str  = None
    fw_channel: str = None # NEW - beta or stable (based on installed esp firmware)
    MAC: str  = None
    model: str  = None
    sw_version: str  = None
    zb_hw: str  = None
    zb_version: str  = None
    zb_type: int = None # NEW - should be enum (coordinator, router, thread?)

    @classmethod
    def load_payload(cls, payload):
        return cls(
            coord_mode = payload.mode,
            MAC = payload.MAC,
            model = payload.model,
            sw_version = payload.sw_version,
            zb_hw = payload.json['zbHw'],
            zb_version = payload.zb_version
        )


@dataclass
class Sensors:
    esp32_temp: float = 0
    zb_temp: float = 0
    uptime: int | str = None # Should be timestamp
    socket_uptime: int | str = None # Should be timestamp
    ram_usage: int = None
    internet: bool = False
    ethernet: bool = False
    wifi_connected: bool = False
    wifi_status: int | str = None # Should be enum (off, client, AP etc)

    #toggle states:
    disable_leds: bool = None
    night_mode: bool = None
    auto_zigbee: bool = None

    @classmethod
    def load_payload(cls, payload):
        return cls(
            esp32_temp = payload.esp32_temp,
            zb_temp = payload.zb_temp,
            uptime = payload.uptime
        )