#!/usr/bin/env python3
from collections.abc import Callable
import json
import logging
from typing import Any, Self
import urllib.parse

from aiohttp import ClientSession, encode_basic_auth
from aiohttp.client_exceptions import ClientConnectionError
from awesomeversion import AwesomeVersion

from .catalog import FirmwareCatalog, FwChannel, FwMode
from .const import (
    PARAM_LIST,
    SEL_FW_CHANNEL,
    Actions,
    Commands,
    Events,
    Pages,
)
from .exceptions import SmlightAuthError, SmlightConnectionError
from .models import AmbilightPayload, BuzzerPayload, Firmware, Info, IRPayload, Sensors
from .payload import Payload
from .sse import sseClient

_LOGGER = logging.getLogger(__name__)


class webClient:
    def __init__(self, host: str, session: ClientSession | None = None) -> None:
        self.auth: str | None = None
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
        self.auth = encode_basic_auth(user, password)
        return not await self.check_auth_needed(True)

    async def check_auth_needed(self, authenticate: bool = False) -> bool:
        """
        Check if authentication is needed for the device
        Optionally validate authentication credentials
        Raises error on Connection or Auth failure
        """
        assert self.session is not None, "Session not created"

        headers = {}
        res = False
        if authenticate and self.auth:
            headers["Authorization"] = self.auth

        try:
            params = {"action": Actions.API_GET_PAGE.value, "page": 1}
            async with self.session.get(
                self.url, headers=headers or None, params=params
            ) as response:
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

        headers = self.headers.copy()
        if self.auth:
            headers["Authorization"] = self.auth

        try:
            async with self.session.get(
                url, headers=headers, params=params
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

    async def post(self, params, url: str | None = None) -> bool:
        assert self.session is not None, "Session not created"

        if url is None:
            url = self.setting_url

        data = urllib.parse.urlencode(params)

        headers = self.post_headers.copy()
        if self.auth:
            headers["Authorization"] = self.auth

        try:
            async with self.session.post(
                url,
                data=data,
                headers=headers,
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
        self.actions = ActionWrapper(self.post, self.get)
        super().__init__(host, session=session)

        if session is None:
            self.session = ClientSession(headers=self.headers)
            self.close_session = True

        if sse:
            self.sse = sse
        else:
            self.sse = sseClient(host, session)

        self.catalog = FirmwareCatalog(session=self.session)
        self.u_device: bool | None = None

    async def get_device_payload(self) -> Payload:
        data = await self.get_page(Pages.API2_PAGE_DASHBOARD)
        res = Payload(data)
        return res

    async def get_firmware_version(
        self,
        channel: FwChannel | None,
        *,
        device: str | None = None,
        mode: FwMode = "esp32",
        zb_type: int | None = None,
        idx: int = 0,
    ) -> list[Firmware]:
        """Get firmware version for device and mode (esp | zigbee)"""
        self.catalog.session = self.session
        return await self.catalog.get_firmware_version(
            channel,
            device=device,
            mode=mode,
            zb_type=zb_type,
            idx=idx,
            u_device=self.u_device,
        )

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
        self.u_device = info.u_device

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

    async def set_ble_proxy(self, enabled: bool) -> bool:
        """Enable or disable BLE radio and proxy, then reboot."""
        state = "on" if enabled else "off"
        params = {
            "pageId": Pages.API2_PAGE_BLE.value,
            "bleEn": state,
            "blePrxEn": state,
            "ha": True,
        }
        success = await self.post(params)
        if success:
            await self.cmds.reboot()
        return success

    async def set_fw_channel(self, channel: int | str) -> bool:
        """Set firmware channel."""
        if isinstance(channel, str):
            by_name = {name: key for key, name in SEL_FW_CHANNEL.items()}
            if channel not in by_name:
                raise ValueError(f"Invalid firmware channel: {channel}")
            channel = by_name[channel]
        elif type(channel) is not int or channel not in SEL_FW_CHANNEL:
            raise ValueError(f"Invalid firmware channel: {channel}")

        params = {
            "pageId": Pages.API2_PAGE_SETTINGS_OTA.value,
            "fw_ch": channel,
            "ha": True,
        }
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

    async def zb_bootloader(self, idx: int = 0) -> None:
        await self.set_cmd(Commands.CMD_ZB_BSL, f"idx:{idx}")

    async def zb_restart(self, idx: int = 0) -> None:
        await self.set_cmd(Commands.CMD_ZB_RST, f"idx:{idx}")

    async def zb_router(self, idx: int = 0) -> None:
        await self.set_cmd(Commands.CMD_ZB_ROUTER_RECON, f"idx:{idx}")


class ActionWrapper:
    """Wrapper for handling specific page actions."""

    def __init__(self, post_action: Callable, get_action: Callable) -> None:
        self.post = post_action
        self.get = get_action

    async def ambilight(self, payload: AmbilightPayload) -> bool:
        """Send ambilight commands."""
        data = {k: v for k, v in payload.to_dict().items() if v is not None}
        params = {"pageId": Pages.API2_PAGE_AMBILIGHT.value, **data}
        return await self.post(params)

    async def get_ir_code(self, payload: IRPayload) -> str | None:
        """Get last IR code."""
        data = {k: v for k, v in payload.to_dict().items() if v is not None}
        params = {"pageId": Pages.API2_PAGE_IR.value, **data}
        return await self.get(params)

    async def send_ir_code(self, payload: IRPayload) -> bool:
        """Send IR code."""
        data = {k: v for k, v in payload.to_dict().items() if v is not None}
        params = {"action": Actions.API_IR.value, **data}
        return await self.post(params, url=self.post.__self__.url)

    async def buzzer(self, payload: BuzzerPayload) -> bool:
        """Send buzzer RTTTL code."""
        data = {k: v for k, v in payload.to_dict().items() if v is not None}
        params = {"action": Actions.API_BUZZER.value, **data}
        return await self.post(params, url=self.post.__self__.url)
