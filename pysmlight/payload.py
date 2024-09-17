""" Handle device info for legacy firmware so can offer upgrade."""
import re
from typing import Any


class Payload:
    """Handle device info for legacy firmware so can offer upgrade."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.json: dict[str, Any] = data
        self.legacy_api: int = 1
        self.unpack()

    def unpack(self):
        """Unpack required info from the dashboard json."""
        if self.json:
            self.device_ip = self.json["ethIp"]
            self.MAC = self.json["wifiMac"]
            self.uptime = self.clean(self.json["uptime"])
            if "BUILD" in self.json:
                # legacy api = 1, old v2 builds < v2.3.6
                self.legacy_api = 1
                self.coord_mode = self.json["coordMode"]
                self.model = self.json["DEVICE"].replace("P", "p")
                self.sw_version = self.json["BUILD"]
                self.zb_hw = self.json["zbHw"]
                self.zb_version = self.clean(self.json["zbRev"])
            else:
                # legacy api = 2, 0.9.9 builds
                self.legacy_api = 2
                self.coord_mode = None
                self.model = self.json["hwRev"].replace("P", "p")
                self.sw_version = self.json["VERSION"].split(" ")[0]
                self.zb_hw = None
                self.zb_version = "-1"

    def clean(self, str: str) -> str:
        """
        Strip localisation formatting from string.

        Legacy firmware doesn't have required endpoints to get this directly.
        """
        text = None
        if "U_time" in str:
            text = str.replace("[U_time]^  ", "")
            text = text.replace("^", ":")
        elif "ZB_FW_unk" in str:
            text = str.replace("[ZB_FW_unk]", "-1")
        else:
            text = re.sub(r"\[|\]", "", str)
        return text

    @property
    def dump(self):
        return self.json
