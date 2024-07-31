""" Handle device info for legacy firmware so can offer upgrade."""
import re
from typing import Any


class Payload:
    def __init__(self, data: dict[str, Any]) -> None:
        self.json: dict[str, Any] = data
        self.unpack()

    def unpack(self):
        if self.json:
            self.device_ip = self.json["ethIp"]
            self.model = self.json["DEVICE"].replace("P", "p")
            self.MAC = self.json["wifiMac"]
            self.coord_mode = self.clean(self.json["coordMode"])
            self.sw_version = self.json["BUILD"]
            self.uptime = self.clean(self.json["uptime"])
            self.zb_hw = self.json["zbHw"]
            self.zb_version = self.json["zbRev"]

    def clean(self, str: str) -> str:
        """
        Strip localisation formatting from string.

        Legacy firmware doesn't have required endpoints to get this directly.
        """
        text = None
        if "U_time" in str:
            text = str.replace("[U_time]^  ", "")
            text = text.replace("^", ":")
        else:
            text = re.sub(r"\[|\]", "", str)
        return text

    @property
    def dump(self):
        return self.json
