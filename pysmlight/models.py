from dataclasses import dataclass, field
import re

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
    prod: bool = False
    baud: int | None = None

    def __post_init__(self):
        # zigbee firmware match key attributes
        if self.baud is not None:
            self.ver = self.rev
            self.dev = not self.prod

    def set_mode(self, mode):
        self.mode = mode


FirmwareList = list[Firmware] | None


@dataclass
class Radio(DataClassDictMixin):
    chip_index: int | None = None
    zb_channel: int | None = None
    zb_flash_size: int | None = None
    zb_hw: str | None = None
    zb_ram_size: int | None = None
    zb_version: str | None = None
    zb_type: int | None = None  # enum (coordinator, router, thread)
    radioModes: list[bool] | None = None


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
    radios: list[Radio] = field(default_factory=list)
    zb_channel: int | None = None
    zb_flash_size: int | None = None
    zb_hw: str | None = None
    zb_ram_size: int | None = None
    zb_version: str | None = None
    zb_type: int | None = None  # enum (coordinator, router, thread)

    @classmethod
    def load_payload(cls, payload: Payload) -> "Info":
        return cls(
            device_ip=payload.device_ip,
            legacy_api=payload.legacy_api,
            MAC=payload.MAC,
            model=payload.model,
            fw_channel="release",
            sw_version=payload.sw_version,
            zb_hw=payload.zb_hw,
            zb_version=int(payload.zb_version),
        )

    def check_zb_version(self, radio: Radio | None = None):
        if radio is None:
            radio = self

        if radio.zb_version is not None:
            if radio.zb_version == -1:
                radio.zb_channel = 2  # custom
                radio.zb_version = None
            else:
                radio.zb_version = str(radio.zb_version)
        return radio

    def __post_init__(self) -> None:
        if self.model is not None:
            self.model = self.model.replace("P", "p")
            self.model = self.model.replace("MG", "Mg")

        self.check_zb_version()

        # Factory firmware may have invalid .plus suffix, convert to valid version
        if self.sw_version:
            if "plus" in self.sw_version:
                self.sw_version = re.sub(
                    r"\.plus(\d*)$",
                    lambda m: f".{m.group(1) if m.group(1) else '1'}",
                    self.sw_version,
                )
            elif self.sw_version.endswith(".dev"):
                self.sw_version = f"{self.sw_version}0"

        if not self.radios:
            # construct radio object for backward compatibility (v2.5.0)
            self.radios = [
                Radio(
                    chip_index=0,
                    zb_channel=self.zb_channel,
                    zb_flash_size=self.zb_flash_size,
                    zb_hw=self.zb_hw,
                    zb_ram_size=self.zb_ram_size,
                    zb_version=self.zb_version,
                    zb_type=self.zb_type,
                )
            ]
        else:
            for r in self.radios:
                r = self.check_zb_version(r)


@dataclass
class Sensors(DataClassDictMixin):
    esp32_temp: float | None = None
    zb_temp: float | None = None
    zb_temp2: float | None = None
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
