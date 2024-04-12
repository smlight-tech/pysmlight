from dataclasses import dataclass

from mashumaro import DataClassDictMixin


@dataclass
class Firmware(DataClassDictMixin):
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
class Info(DataClassDictMixin):
    coord_mode: int | str | None = None  # Enum
    device_ip: str | None = None
    fs_total: int | None = None
    fw_channel: str | None = None  # dev, beta or stable
    MAC: str | None = None
    model: str | None = None
    ram_total: int | None = None
    sw_version: str | None = None
    wifi_mode: int | None = None  # enum (off, client, AP etc)
    zb_flash_size: int | None = None
    zb_hw: str | None = None
    zb_ram_size: int | None = None
    zb_version: int | None = None
    zb_type: int | None = None  # enum (coordinator, router, thread)

    @classmethod
    def load_payload(cls, payload):
        return cls(
            # coord_mode=payload.mode,
            device_ip=payload.device_ip,
            MAC=payload.MAC,
            model=payload.model,
            fw_channel="stable",
            sw_version=payload.sw_version,
            zb_hw=payload.zb_hw,
            zb_version=int(payload.zb_version),
        )

    def __post_init__(self):
        if self.model is not None:
            self.model = self.model.replace("P", "p")


@dataclass
class Sensors(DataClassDictMixin):
    esp32_temp: float = 0
    zb_temp: float = 0
    uptime: int = 0  # Should be timestamp
    socket_uptime: int = 0  # Should be timestamp
    ram_usage: int | None = None
    fs_used: int | None = None
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
