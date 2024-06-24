#!/usr/bin/env python3
from collections.abc import Callable
import json
import logging
import time
from typing import Any, Dict
import urllib.parse

from aiohttp import BasicAuth, ClientSession
from aiohttp.client_exceptions import ClientConnectorError

from .const import (
    FW_DEV_URL,
    FW_URL,
    PARAM_LIST,
    Actions,
    Commands,
    Devices,
    Events,
    Pages,
)
from .exceptions import SmlightAuthError, SmlightConnectionError
from .models import Firmware, Info, Sensors
from .payload import Payload
from .sse import sseClient

try:
    from . import secrets
except ImportError:
    pass

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
        self.session: ClientSession | None = session

        self.set_urls()

    async def async_init(self) -> None:
        if self.session is None:
            self.session = ClientSession(headers=self.headers, auth=self.auth)
        if self.host != "smlight.tech":
            if await self.check_auth_needed():
                _LOGGER.info("Authentication required")
                # fallback to hardcoded test credentials
                if secrets and self.auth is None:
                    self.auth = BasicAuth(secrets.apiuser, secrets.apipass)

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

        auth = None
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
        except ClientConnectorError:
            _LOGGER.debug("Connection error")
            raise SmlightConnectionError("Connection failed")

        return res

    async def get(self, params: Dict[str, Any], url=None) -> str | None:
        if self.session is None:
            self.session = ClientSession(headers=self.headers)
        if url is None:
            url = self.url
        async with self.session.get(
            url, headers=self.headers, params=params, auth=self.auth
        ) as response:
            if response.status == 404:
                return None
            hdr = response.headers.get("respValuesArr")
            if hdr is not None and (
                params and int(params["action"]) == Actions.API_GET_PAGE.value
            ):
                return hdr
            else:
                return await response.text(encoding="utf-8")

    async def post(self, params):
        if self.session is None:
            self.session = ClientSession(headers=self.headers)
        data = urllib.parse.urlencode(params)
        async with self.session.post(
            self.setting_url,
            data=data,
            headers=self.post_headers,
            auth=self.auth,
        ) as response:
            await response.text(encoding="utf-8")
            return response.status == 200

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

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()


class Api2(webClient):
    def __init__(
        self,
        host: str,
        *,
        session: ClientSession | None = None,
        sse: sseClient | None = None,
    ) -> None:
        self.settings_cb: Dict[str, Callable] = {}
        self.cmds = CmdWrapper(self.set_cmd)
        super().__init__(host, session=session)

        if session is not None:
            self.sse = sseClient(host, session)
        elif sse:
            self.sse = sse

        if hasattr(self, "sse") and self.sse is not None:
            self.sse.register_callback(Events.SAVE_PARAMS, self._handle_settings)

    def _handle_settings(self, event: Events) -> None:
        data = json.loads(event.data)
        changes = data.pop("changes")
        for setting in changes:
            if setting in self.settings_cb:
                result = data.copy()
                result.update({setting: changes[setting]})
                self.settings_cb[setting](result)

    def register_settings_cb(self, setting, cb: Callable) -> None:
        # callback = partial(cb, setting)
        self.settings_cb[setting] = cb

    async def get_device_payload(self) -> Payload:
        data = await self.get_page(Pages.API2_PAGE_DASHBOARD)
        res = Payload(data)
        return res

    async def get_firmware_version(
        self, device: str | None = None, mode: str = "ESP"
    ) -> list[Firmware] | None:
        """Get firmware version for device and mode (ESP|ZB)"""
        params = {"type": mode}
        url = FW_DEV_URL if mode == "ZB" else FW_URL
        response = await self.get(params=params, url=url)
        data = json.loads(response)

        if mode == "ZB" and device is not None:
            data = data.get(str(Devices[device]), None)
            if not data:
                return None
        else:
            data = data["fw"]
        fw = []
        for d in data:
            item = Firmware.from_dict(d)
            item.set_mode(mode)
            fw.append(item)
        return fw

    async def get_page(self, page: Pages) -> dict | None:
        """Extract Respvaluesarr json from page response header"""
        params = {"action": Actions.API_GET_PAGE.value, "page": page.value}
        res = await self.get(params)
        data = json.loads(res)
        if data:
            return data
        return None

    async def get_param(self, param) -> str | None:
        if param in PARAM_LIST:
            params = {"action": Actions.API_GET_PARAM.value, "param": param}
            return await self.get(params)
        return None

    async def get_info_old(self) -> Info:
        payload = await self.get_device_payload()
        return Info.load_payload(payload)

    async def get_info(self) -> Info:
        res = await self.get(params=None, url=self.info_url)
        if res is None:
            res = await self.get_info_old()
            return res
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

    async def fw_update(self, mode, fw_url, fw_type=None, fw_version=None) -> None:
        # Register callback 'ESP_UPD_done'? before calling this
        if mode == "ZB":
            params = {
                "action": Actions.API_FLASH_ZB.value,
                "fwUrl": fw_url,
                "fwType": fw_type,
                "fwVer": fw_version,
            }
        else:
            params = {"action": Actions.API_FLASH_ESP.value, "fwUrl": fw_url}
        await self.get(params)

    async def set_toggle(self, page: Pages, toggle: str, value: bool) -> bool:
        state = "on" if value else "off"
        params = {"pageId": page.value, toggle: state, "ha": True}
        res = await self.post(params)
        return res

    async def scan_wifi(self):
        _LOGGER.debug("Scanning wifi")
        self.sse.register_callback(Events.API2_WIFISCANSTATUS, self.wifi_callback)
        params = {"action": Actions.API_STARTWIFISCAN.value}
        await self.get(params)

    def wifi_callback(self, msg):
        _LOGGER.debug("WIFI callback")
        _LOGGER.info(msg)
        self.sse.deregister_callback(Events.API2_WIFISCANSTATUS)


class CmdWrapper:
    """Convenience wrapper for HA when sending commands to the device."""

    def __init__(self, set_cmd):
        self.set_cmd = set_cmd

    async def reboot(self):
        await self.set_cmd(Commands.CMD_ESP_RES)

    async def zb_bootloader(self):
        await self.set_cmd(Commands.CMD_ZB_BSL)

    async def zb_restart(self):
        await self.set_cmd(Commands.CMD_ZB_RST)

    async def zb_router(self):
        await self.set_cmd(Commands.CMD_ZB_ROUTER_RECON)
