from enum import Enum, unique

MODE_LIST: list[str] = [
    "LAN",
    "WiFi",
    "USB"
]

PARAM_LIST: list[str] = [
    "coordMode",
    "zbRev",
    "espRev",
    "inetState",
]

@unique
class Actions(Enum):
    API_GET_PAGE = 0
    API_GET_PARAM = 1
    API_STARTWIFISCAN = 2   
    API_SEND_HEX = 3
    API_CMD = 4
    API_GET_LOG = 5
    API_FLASH_ZB = 6
    API_WIFICONNECTSTAT = 7
    API_FLASH_ESP = 8

@unique
class Commands(Enum):
    CMD_ZB_ROUTER_RECON = 0
    CMD_ZB_RST = 1
    CMD_ZB_BSL = 2
    CMD_ESP_RES = 3
    CMD_CLEAR_LOG = 4
    CMD_ZB_ENERGY_SCAN = 5
    CMD_ZB_LED_NETWORK = 6
    CMD_ZB_LED_PERMIT = 7
    CMD_ZB_LED_DISABLED = 8
    CMD_HARD_RESET = 9

@unique
class Pages(Enum):
    API2_PAGE_DASHBOARD = 0
    API2_PAGE_MODE = 1
    API2_PAGE_NETWORK = 2
    API2_PAGE_ZHA_Z2M = 3
    API2_PAGE_SECURITY = 4
    API2_PAGE_VPN = 5
    API2_PAGE_SETTINGS_GENERAL = 6
    API2_PAGE_SETTINGS_OTA = 7
    API2_PAGE_SETTINGS_LED = 8
    API2_PAGE_SETTINGS_TIME =9
    API2_PAGE_SETTINGS_SYSTEM_LOG = 10
    API2_PAGE_ABOUT = 11
    API2_PAGE_WIFI = 12

Devices:  dict[str, int] = {  
    "SLZB-06":0,
    "SLZB-06M":1,
    "SLZB-06Mg24":2,
    "SLZB-06p7":3,
    "SLZB-06p10":4,
}