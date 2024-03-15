
import re

class Payload:
    def __init__(self, data=None) -> None:
        self.json = data
        self.model = None
        self.MAC = None
        if data:
            self.unpack()

    def unpack(self):
        self.esp32_temp = self.json['esp32Temp']
        self.zb_temp = self.json['zbTemp']
        self.model = self.json['DEVICE']
        self.MAC = self.json['ethMac'] if "NC" not in self.json['ethMac'] else self.json['wifiMac']
        self.mode = self.clean(self.json['coordMode'])
        self.sw_version = self.json['BUILD']
        self.zb_version = self.json['zbRev']
        self.uptime = self.clean(self.json['uptime'])

    def clean(self, str:str) -> str:
        """Strip localisation formatting, temporary for testing. End point should be updated"""
        text = None
        if "U_time" in str:
            text = str.replace('[U_time]^  ','')
            text = text.replace('^',':')
        # need special cases for ethSpd and espFS also if used
        else:
            text = re.sub(r'\[|\]', '', str)
        return text

    def dump(self):
        return self.json