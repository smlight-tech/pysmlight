from dataclasses import dataclass

from mashumaro import DataClassDictMixin

from .payload import Payload


@dataclass
class Firmware(DataClassDictMixin):
    mode: str | None = None  # ESP|ZB
    type: int | None = None
    notes: str | None = None
    rev: str | None = None
    link: str | None = None
    ver: str | None = None
    dev: bool = False
    prod: bool = True
    baud: int | None = None

    def __post_init__(self):
        # zigbee firmware match key attributes
        if self.baud is not None:
            self.ver = self.rev
            self.dev = not self.prod

    def set_mode(self, mode):
        self.mode = mode


@dataclass
class Info(DataClassDictMixin):
    coord_mode: int | None = None  # Enum
    device_ip: str | None = None
    fs_total: int | None = None
    fw_channel: str | None = None  # dev, beta or release
    hostname: str | None = None
    legacy_api: int = 0
    MAC: str | None = None
    model: str | None = None
    ram_total: int | None = None
    sw_version: str | None = None
    wifi_mode: int | None = None  # enum (off, client, AP etc)
    zb_channel: int | None = None
    zb_flash_size: int | None = None
    zb_hw: str | None = None
    zb_ram_size: int | None = None
    zb_version: str | None = None
    zb_type: int | None = None  # enum (coordinator, router, thread)

    @classmethod
    def load_payload(cls, payload: Payload) -> "Info":
        return cls(
            # coord_mode=payload.mode,
            device_ip=payload.device_ip,
            legacy_api=payload.legacy_api,
            MAC=payload.MAC,
            model=payload.model,
            fw_channel="release",
            sw_version=payload.sw_version,
            zb_hw=payload.zb_hw,
            zb_version=int(payload.zb_version),
        )

    def __post_init__(self) -> None:
        if self.model is not None:
            self.model = self.model.replace("P", "p")
        self.zb_version = str(self.zb_version)


@dataclass
class Sensors(DataClassDictMixin):
    esp32_temp: float = 0
    zb_temp: float = 0
    uptime: int = 0  # Should be timestamp
    socket_uptime: int | None = None  # Should be timestamp
    ram_usage: int | None = None
    fs_used: int | None = None
    ethernet: bool = False
    wifi_connected: bool = False
    wifi_status: int | str | None = None  # enum (off, client, AP etc)
    vpn_status: bool = False

    # toggle states:
    disable_leds: bool | None = None
    night_mode: bool | None = None
    auto_zigbee: bool | None = None
    vpn_enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.socket_uptime is not None and self.socket_uptime <= 0:
            self.socket_uptime = None


@dataclass
class SettingsEvent(DataClassDictMixin):
    page: int | None = None
    origin: str | None = None
    needReboot: bool = False
    setting: dict[str, bool | int] | None = None
