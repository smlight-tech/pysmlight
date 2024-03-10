from dataclasses import dataclass

@dataclass
class Firmware:
    mode:str
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
    coord_mode: str
    device_ip: str
    fw_channel: str # NEW - beta or stable (based on installed esp firmware)
    MAC: str
    model: str
    sw_version:str
    zb_hw: str
    zb_version: str
    zb_type: str # NEW - should be enum (coordinator, router, thread?)

    def __init__(self, payload):
        self.coord_mode = payload.mode
        self.MAC = payload.MAC
        self.model = payload.model
        self.sw_version = payload.sw_version
        self.zb_hw = payload.json['zbHw']
        self.zb_version = payload.zb_version

@dataclass
class Sensors:
    esp32_temp: float
    zb_temp: float
    mode: str
    uptime: str # Should be timestamp
    socket_uptime: str  # Should be timestamp
    ram_usage: int
    internet: bool
    ethernet: bool
    wifi_connected: bool
    wifi_status: str # Should be enum (off, client, AP etc)

    #toggle states:
    disable_led: bool
    night_mode: bool
    auto_zigbee: bool

    def __init__(self, payload):
        self.esp32_temp = payload.esp32_temp
        self.zb_temp = payload.zb_temp
        self.mode = payload.mode
        self.uptime = payload.uptime