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
    MAC: str
    model: str
    sw_version:str
    zb_hw: str
    zb_version: str

    def __init__(self, payload):
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
    uptime: str

    def __init__(self, payload):
        self.esp32_temp = payload.esp32_temp
        self.zb_temp = payload.zb_temp
        self.mode = payload.mode
        self.uptime = payload.uptime