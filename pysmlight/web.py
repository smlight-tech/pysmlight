#!/usr/bin/env python3
from collections.abc import Callable
import json
import logging
import re
from typing import Any, Self
import urllib.parse

from aiohttp import BasicAuth, ClientSession
from aiohttp.client_exceptions import ClientConnectionError
from awesomeversion import AwesomeVersion

from .const import (
    FW_URL,
    PARAM_LIST,
    Actions,
    Commands,
    Devices,
    Events,
    Pages,
    U_Devices,
)
from .exceptions import SmlightAuthError, SmlightConnectionError
from .models import Firmware, Info, Sensors
from .payload import Payload
from .sse import sseClient

_LOGGER = logging.getLogger(__name__)


class webClient:
    def __init__(self, host: str, session: ClientSession | None = None) -> None:
        self.auth: BasicAuth | None = None
        # we can't modify headers on the passed in session from HA,
        #  if needed can be overridden at request level
        self.headers = {"Content-Type": "application/json; charset=utf-8"}
        self.post_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        self.host = host
        self.session = session
        self.close_session = False
        self.core_version: AwesomeVersion | None = None

        self.set_urls()

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
        assert self.session is not None, "Session not created"

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
        assert self.session is not None, "Session not created"

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
        assert self.session is not None, "Session not created"

        data = urllib.parse.urlencode(params)

        try:
            async with self.session.post(
                self.setting_url,
                data=data,
                headers=self.post_headers,
                auth=self.auth,
            ) as response:
                if response.status == 404:
                    raise SmlightConnectionError("endpoint not found")
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
        """Close the session if it was created internally"""
        if self.session is not None and self.close_session:
            await self.session.close()
            self.session = None
            self.close_session = False

    async def __aenter__(self) -> Self:
        if self.session is None:
            self.close_session = True
            self.session = ClientSession(headers=self.headers)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
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

        if session is None:
            self.session = ClientSession(headers=self.headers)
            self.close_session = True

        if sse:
            self.sse = sse
        else:
            self.sse = sseClient(host, session)

    async def get_device_payload(self) -> Payload:
        data = await self.get_page(Pages.API2_PAGE_DASHBOARD)
        res = Payload(data)
        return res

    async def get_firmware_version(
        self,
        channel: str | None,
        *,
        device: str | None = None,
        mode: str = "esp",
        zb_type: int | None = None,
        idx: int = 0,
    ) -> list[Firmware] | None:
        """Get firmware version for device and mode (esp | zigbee)"""
        params = {}
        fw_type = "ESP"
        if mode == "zigbee":
            fw_type = "ZB"
            params["format"] = "slzb"
            if device == "SLZB-MR1":
                device = "SLZB-06p7V2" if idx else "SLZB-06M"
        elif mode == "esp32":
            fw_type = "ESPs3" if self.device_is_u(device) else "ESP"
        params["type"] = fw_type
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
                if item.notes:
                    item.notes = self.format_notes(item)
                if zb_type is not None and item.type != zb_type:
                    continue
                fw.append(item)
        return fw

    def format_notes(self, firmware: Firmware) -> str | None:
        """Format release notes for esp firmware"""
        if firmware and firmware.notes:
            items = (
                re.split("\r\n|(?<!\r)\n", firmware.notes)
                if firmware.mode == "ESP"
                else [firmware.notes]
            )
            notes = ""
            for i, v in enumerate(items):
                if i and v and not v.startswith("-"):
                    notes += f"* {v}\n"
                else:
                    notes += f"{v}\n\n"

            if firmware.dev and firmware.mode == "ZB":
                notes = "Dev firmware.\n\n" + notes
            return notes
        return None

    async def get_page(self, page: Pages) -> dict | None:
        """Extract Respvaluesarr json from page response header"""
        params = {"action": Actions.API_GET_PAGE.value, "page": page.value}
        res = await self.get(params)
        data = json.loads(res)
        return data if data else None

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

        info = Info.from_dict(data["Info"])
        core_version = AwesomeVersion(info.sw_version)

        if self.core_version is None:
            self.core_version = core_version
        if self.sse.sw_version is None:
            self.sse.sw_version = core_version

        return Info.from_dict(data["Info"])

    async def get_sensors(self) -> Sensors:
        res = await self.get(params=None, url=self.sensor_url)
        data = json.loads(res)
        return Sensors.from_dict(data["Sensors"])

    async def set_cmd(self, cmd: Commands, extra: str | None = None) -> bool:
        params = {"action": Actions.API_CMD.value, "cmd": cmd.value}
        if extra:
            k, v = extra.split(":")
            val = int(v)
            if val > 0:
                params[k] = val
        res = await self.get(params)
        return res == "ok"

    async def fw_update(
        self,
        firmware: Firmware,
        idx: int = 0,
    ) -> bool:
        """Send firmware update command to device"""
        if firmware.mode == "ZB":
            params = {
                "action": Actions.API_FLASH_ZB.value,
                "baud": firmware.baud,
                "fwUrl": firmware.link,
                "fwType": firmware.type,
                "fwVer": firmware.ver,
                "fwCh": int(not firmware.prod),
                "zbChipIdx": idx,
            }
            # backwards compatibility for SLZB-MR1
            if (
                idx == 1
                and self.core_version
                and self.core_version <= AwesomeVersion("v2.7.2")
            ):
                params["zbChipNum"] = 5
        else:
            params = {"action": Actions.API_FLASH_ESP.value, "fwUrl": firmware.link}
        res = await self.get(params)
        return res == "ok"

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

    def device_is_u(self, model: str) -> bool:
        device_id = Devices.get(model, None)
        return (
            device_id in [udev.value for udev in U_Devices]
            if device_id is not None
            else False
        )


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

    async def zb_router(self, idx: int = 0) -> None:
        await self.set_cmd(Commands.CMD_ZB_ROUTER_RECON, f"idx:{idx}")
