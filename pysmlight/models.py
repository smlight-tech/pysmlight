from dataclasses import dataclass


@dataclass
class Firmware:
    mode: str | None = None  # ESP|ZB
    type: int | None = None
    notes: str | None = None
    rev: str | None = None
    link: str | None = None
    ver: str | None = None
    dev: bool = False

    def set_mode(self, mode):
        self.mode = mode


@dataclass
class Info:
    coord_mode: int | str | None = None  # Should be Enum
    device_ip: str | None = None
    fw_channel: str | None = None  # NEW - beta or stable
    MAC: str | None = None
    model: str | None = None
    ram_total: int | None = None
    sw_version: str | None = None
    zb_hw: str | None = None
    zb_version: str | None = None
    zb_type: int | None = None  # NEW - enum (coordinator, router, thread?)

    @classmethod
    def load_payload(cls, payload):
        return cls(
            coord_mode=payload.mode,
            MAC=payload.MAC,
            model=payload.model,
            sw_version=payload.sw_version,
            zb_hw=payload.json["zbHw"],
            zb_version=payload.zb_version,
        )

    def __post_init__(self):
        self.model = self.model.replace("P", "p")


@dataclass
class Sensors:
    esp32_temp: float = 0
    zb_temp: float = 0
    uptime: int | str | None = None  # Should be timestamp
    socket_uptime: int | str | None = None  # Should be timestamp
    ram_usage: int | None = None
    ethernet: bool = False
    wifi_connected: bool = False
    wifi_status: int | str | None = None  # enum (off, client, AP etc)

    # toggle states:
    disable_leds: bool | None = None
    night_mode: bool | None = None
    auto_zigbee: bool | None = None

    @classmethod
    def load_payload(cls, payload):
        return cls(
            esp32_temp=payload.esp32_temp,
            zb_temp=payload.zb_temp,
            uptime=payload.uptime,
        )
