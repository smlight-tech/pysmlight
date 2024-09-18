#!/usr/bin/env python3
from collections.abc import Callable
import json
import logging
import re
import time
from typing import Any, Type
import urllib.parse

from aiohttp import BasicAuth, ClientSession
from aiohttp.client_exceptions import ClientConnectionError

from .const import FW_URL, PARAM_LIST, Actions, Commands, Devices, Events, Pages
from .exceptions import SmlightAuthError, SmlightConnectionError
from .models import Firmware, Info, Sensors
from .payload import Payload
from .sse import sseClient

_LOGGER = logging.getLogger(__name__)

start = time.time()


class webClient:
    def __init__(self, host: str, session: ClientSession | None = None) -> None:
        self.auth: BasicAuth | None = None
        # we can't modify headers on the passed in session from HA,
        #  if needed can be overridden at request level
        self.headers = {"Content-Type": "application/json; charset=utf-8"}
        self.post_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        self.host = host
        self.session = session

        self.set_urls()

    async def async_init(self, auth: BasicAuth | None = None) -> None:
        if auth is not None:
            self.auth = auth
        if self.session is None:
            self.session = ClientSession(headers=self.headers, auth=self.auth)

        _LOGGER.debug("Session created")

    async def authenticate(self, user: str, password: str) -> bool:
        """Pass in credentials and check auth is successful"""
        self.auth = BasicAuth(user, password)
        return not await self.check_auth_needed(True)

    async def check_auth_needed(self, authenticate: bool = False) -> bool:
        """
        Check if authentication is needed for the device
        Optionally validate authentication credentials
        Raises error on Connection or Auth failure
        """
        if self.session is None:
            self.session = ClientSession(headers=self.headers)

        auth: BasicAuth | None = None
        res = False
        if authenticate:
            auth = self.auth

        try:
            params = {"action": Actions.API_GET_PAGE.value, "page": 1}
            async with self.session.get(self.url, auth=auth, params=params) as response:
                if response.status == 401:
                    res = True
                    if authenticate:
                        raise SmlightAuthError("Authentication Error")
        except ClientConnectionError:
            _LOGGER.debug("Connection error")
            raise SmlightConnectionError("Connection failed")

        return res

    async def get(self, params: dict[str, Any], url: str | None = None) -> str | None:
        if self.session is None:
            self.session = ClientSession(headers=self.headers)
        if url is None:
            url = self.url

        try:
            async with self.session.get(
                url, headers=self.headers, params=params, auth=self.auth
            ) as response:
                if response.status == 404:
                    return None
                elif response.status == 401:
                    raise SmlightAuthError("Authentication Error")

                hdr = response.headers.get("respValuesArr")
                if hdr is not None and (
                    params and int(params["action"]) == Actions.API_GET_PAGE.value
                ):
                    return hdr
                else:
                    return await response.text(encoding="utf-8")
        except ClientConnectionError as err:
            raise SmlightConnectionError("Connection failed") from err

    async def post(self, params) -> bool:
        if self.session is None:
            self.session = ClientSession(headers=self.headers)
        data = urllib.parse.urlencode(params)

        try:
            async with self.session.post(
                self.setting_url,
                data=data,
                headers=self.post_headers,
                auth=self.auth,
            ) as response:
                if response.status == 404:
                    return False
                elif response.status == 401:
                    raise SmlightAuthError("Authentication Error")
                await response.text(encoding="utf-8")
                return response.status == 200
        except ClientConnectionError as err:
            raise SmlightConnectionError("Connection failed") from err

    def set_host(self, host: str) -> None:
        self.host = host
        self.set_urls()

    def set_urls(self) -> None:
        self.url = f"http://{self.host}/api2"
        self.config_url = f"http://{self.host}/config"
        self.metrics_url = f"http://{self.host}/metrics"
        self.setting_url = f"http://{self.host}/settings/saveParams"
        self.info_url = f"http://{self.host}/ha_info"
        self.sensor_url = f"http://{self.host}/ha_sensors"

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def __aenter__(self) -> "webClient":
        await self.async_init()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        await self.close()


class Api2(webClient):
    def __init__(
        self,
        host: str,
        *,
        session: ClientSession | None = None,
        sse: sseClient | None = None,
    ) -> None:
        self.cmds = CmdWrapper(self.set_cmd)
        super().__init__(host, session=session)

        if session is not None:
            self.sse = sseClient(host, session)
        elif sse:
            self.sse = sse

    async def get_device_payload(self) -> Payload:
        data = await self.get_page(Pages.API2_PAGE_DASHBOARD)
        res = Payload(data)
        return res

    async def get_firmware_version(
        self, channel: str | None, *, device: str | None = None, mode: str = "esp"
    ) -> list[Firmware] | None:
        """Get firmware version for device and mode (esp | zigbee)"""
        fw_type = "ZB" if mode == "zigbee" else "ESP"
        params = {"type": fw_type}
        if mode == "zigbee":
            params["format"] = "slzb"

        response = await self.get(params=params, url=FW_URL)
        data = json.loads(response)

        if mode == "zigbee":
            assert device is not None
            data = data.get(str(Devices[device]), None)
        else:
            data = data["fw"]

        if data is None:
            return None

        fw = []
        for d in data:
            item = Firmware.from_dict(d)
            if not item.dev or channel == "dev":
                item.set_mode(fw_type)
                if fw_type == "ESP":
                    item.notes = self.format_notes(item)
                fw.append(item)
        return fw

    def format_notes(self, firmware: Firmware) -> str | None:
        """Format release notes for esp firmware"""
        if firmware and firmware.notes:
            items = re.split("\r\n|(?<!\r)\n", firmware.notes)
            notes = ""
            for i, v in enumerate(items):
                if i and v and not v.startswith("-"):
                    notes += f"* {v}\n"
                else:
                    notes += f"{v}\n\n"
            return notes
        return None

    async def get_page(self, page: Pages) -> dict | None:
        """Extract Respvaluesarr json from page response header"""
        params = {"action": Actions.API_GET_PAGE.value, "page": page.value}
        res = await self.get(params)
        data = json.loads(res)
        if data:
            return data
        return None

    async def get_param(self, param: str) -> str | None:
        if param in PARAM_LIST:
            params = {"action": Actions.API_GET_PARAM.value, "param": param}
            return await self.get(params)
        return None

    async def get_info_old(self) -> Info:
        self.sse.legacy_api = True
        payload = await self.get_device_payload()
        return Info.load_payload(payload)

    async def get_info(self) -> Info:
        res = await self.get(params=None, url=self.info_url)
        if res is None:
            return await self.get_info_old()
        elif res == "URL NOT FOUND":
            self.url = f"http://{self.host}/api"
            return await self.get_info_old()

        data = json.loads(res)
        return Info.from_dict(data["Info"])

    async def get_sensors(self) -> Sensors:
        res = await self.get(params=None, url=self.sensor_url)
        data = json.loads(res)
        return Sensors.from_dict(data["Sensors"])

    async def set_cmd(self, cmd: Commands) -> bool:
        params = {"action": Actions.API_CMD.value, "cmd": cmd.value}
        res = await self.get(params)
        return res == "ok"

    async def fw_update(
        self,
        firmware: Firmware,
    ) -> None:
        """Send firmware update command to device"""
        if firmware.mode == "ZB":
            params = {
                "action": Actions.API_FLASH_ZB.value,
                "baud": firmware.baud,
                "fwUrl": firmware.link,
                "fwType": firmware.type,
                "fwVer": firmware.ver,
                "fwCh": int(not firmware.prod),
            }
        else:
            params = {"action": Actions.API_FLASH_ESP.value, "fwUrl": firmware.link}
        await self.get(params)

    async def set_toggle(self, page: Pages, toggle: str, value: bool) -> bool:
        state = "on" if value else "off"
        params = {"pageId": page.value, toggle: state, "ha": True}
        res = await self.post(params)
        return res

    async def scan_wifi(self, callback: Callable) -> Callable[[], None]:
        """Initiate scan of wifi networks.

        Args:
            callback (Callable): Callback function to process scan results

        Returns:
            Callable[[], None]: Function to clean up callback
        """

        remove_cb = self.sse.register_callback(Events.API2_WIFISCANSTATUS, callback)
        params = {"action": Actions.API_STARTWIFISCAN.value}
        await self.get(params)
        return remove_cb


class CmdWrapper:
    """Convenience wrapper for HA when sending commands to the device."""

    def __init__(self, set_cmd: Callable) -> None:
        self.set_cmd = set_cmd

    async def reboot(self) -> None:
        await self.set_cmd(Commands.CMD_ESP_RES)

    async def zb_bootloader(self) -> None:
        await self.set_cmd(Commands.CMD_ZB_BSL)

    async def zb_restart(self) -> None:
        await self.set_cmd(Commands.CMD_ZB_RST)

    async def zb_router(self) -> None:
        await self.set_cmd(Commands.CMD_ZB_ROUTER_RECON)
