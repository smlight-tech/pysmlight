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
    coord_mode: str  = None # Should be Enum
    device_ip: str  = None 
    fw_channel: str = None # NEW - beta or stable (based on installed esp firmware)
    MAC: str  = None 
    model: str  = None 
    sw_version:str  = None 
    zb_hw: str  = None 
    zb_version: str  = None 
    zb_type: str = None # NEW - should be enum (coordinator, router, thread?)

    def __init__(self, payload):
        self.coord_mode = payload.mode
        self.MAC = payload.MAC
        self.model = payload.model
        self.sw_version = payload.sw_version
        self.zb_hw = payload.json['zbHw']
        self.zb_version = payload.zb_version

@dataclass
class Sensors:
    esp32_temp: float = 0
    zb_temp: float = 0
    uptime: str = None # Should be timestamp
    socket_uptime: str = None # Should be timestamp
    ram_usage: int = None
    internet: bool = False
    ethernet: bool = False
    wifi_connected: bool = False
    wifi_status: str = None # Should be enum (off, client, AP etc)

    #toggle states:
    disable_led: bool = None
    night_mode: bool = None
    auto_zigbee: bool = None

    def __init__(self, payload):
        self.esp32_temp = payload.esp32_temp
        self.zb_temp = payload.zb_temp
        self.uptime = payload.uptime