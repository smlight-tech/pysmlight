#!/usr/bin/env python3
import asyncio
import aiohttp
from aiohttp_sse_client2 import client as sse_client

from .const import (
    FW_URL,
    MODE_LIST,
    PARAM_LIST,
    Actions,
    Commands,
    Devices,
    Events,
    Pages,
    SETTINGS
)
from .exceptions import (SmlightConnectionError, SmlightAuthError)
from .models import Firmware, Info, Sensors
from .payload import Payload
from .sse import sseClient
import json
import logging
from typing import Callable, Dict
import urllib.parse
import time

_LOGGER = logging.getLogger(__name__)

start = time.time()

class webClient:
    def __init__(self, host, session=None):
        self.auth = None
        # we cant modify headers on the passed in session from HA, if needed can be
        # overriden at request level
        self.headers={'Content-Type': 'application/json; charset=utf-8'}
        self.post_headers={'Content-Type': 'application/x-www-form-urlencoded'}
        self.host = host
        self.session = session


        self.set_urls()

    async def async_init(self):
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers, auth=self.auth)
        if self.host != "smlight.tech":
            if await self.check_auth_needed():
                _LOGGER.info("Authentication required")
                #fallback to hardcoded test credentials
                if secrets and self.auth is None:
                    self.auth = aiohttp.BasicAuth(secrets.apiuser, secrets.apipass)

        _LOGGER.debug("Session created")

    
    async def authenticate(self, user:str, password:str):
        """Pass in credentials and check auth is successful"""
        self.auth = aiohttp.BasicAuth(user, password)
        return not await self.check_auth_needed(True)

    async def check_auth_needed(self, authenticate=False):
        """
        Check if authentication is needed for the device
        Optionally validate authentication credentials
        Raises error on Connection or Auth failure
        """
        auth = None
        res = False
        if authenticate:
            auth = self.auth

        try:
            params = {'action':Actions.API_GET_PAGE.value, 'page':1}
            async with self.session.get(self.url, auth=auth, params=params) as response:
                if response.status == 401:
                    res = True
                    if authenticate:
                        raise SmlightAuthError("Authentication Error")
        except aiohttp.client_exceptions.ClientConnectorError:
            _LOGGER.debug("Connection error")
            raise SmlightConnectionError("Connection failed")

        return res

    async def get(self, params, url=None):
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.headers)
        if url is None:
            url = self.url
        async with self.session.get(
                url, headers=self.headers,params=params, auth=self.auth
                ) as response:
            hdr = response.headers.get('respValuesArr')
            if hdr is not None and (params and int(params['action']) == Actions.API_GET_PAGE.value):
                return hdr
            else:
                return await response.text(encoding='utf-8')

    async def post(self, params):
        data = urllib.parse.urlencode(params)
        async with self.session.post(
                self.setting_url, data=data, headers=self.post_headers, auth=self.auth
                ) as response:
            res_str = await response.text(encoding='utf-8')
            return response.status == 200

    def set_host(self, host):
        self.host = host
        self.set_urls()

    def set_urls(self):
        self.url = f"http://{self.host}/api2"
        self.metrics_url = f"http://{self.host}/metrics"
        self.setting_url = f"http://{self.host}/settings/saveParams"
        self.info_url = f"http://{self.host}/ha_info"
        self.sensor_url = f"http://{self.host}/ha_sensors"

    async def close(self):
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def __aenter__(self):
        await self.async_init()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

class Api2(webClient):
    def __init__(self, host, *, session=None, sse=None) -> None:
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

    async def get_firmware_version(self, device:str = None, mode:str = "ESP") -> list[Firmware] | None:
        """ Get firmware version for device and mode (ESP|ZB)"""
        params = {'type':mode}
        response = await self.get(params=params, url=FW_URL)
        data = json.loads(response)

        if mode == "ZB" and device is not None:
            data = data[str(Devices[device])]
        else:
            data = data['fw']
        fw = []
        for d in data:
            fw.append(Firmware(mode, d))
        return fw

    async def get_page(self, page:Pages) -> dict | None:
        """Extract Respvaluesarr json from page repsonse header"""
        params = {'action':Actions.API_GET_PAGE.value, 'page':page.value}
        res = await self.get(params)
        data = json.loads(res)
        if data:
            return data
        return None

    async def get_param(self, param) -> str | None:
        if param in PARAM_LIST:
            params = {'action':Actions.API_GET_PARAM.value, 'param':param}
            return await self.get(params)
        return None

    async def get_info(self) ->Dict[str, str]:
        payload = await self.get_device_payload()
        info = Info(payload)
        return info

    async def get_sensors(self) ->Dict[str, str]:
        payload = await self.get_device_payload()
        sensors = Sensors(payload)
        return sensors

    async def set_cmd(self, cmd:Commands) -> None:
        params = {'action':Actions.API_CMD.value, 'cmd':cmd.value}
        res = await self.get(params)
        return res == 'ok'

    async def fw_update(self, mode, fw_url, fw_type=None, fw_version=None) -> None:
        #Register callback 'ESP_UPD_done'? before calling this
        if mode == "ZB":
            params = {'action':Actions.API_FLASH_ZB.value, 'fwUrl':fw_url, 'fwType':fw_type, 'fwVersion':fw_version}
        else:
            params = {'action':Actions.API_FLASH_ESP.value, 'fwUrl':fw_url}
        await self.get(params)

    async def get_toggle(self, page: Pages, toggle:str) -> bool:
        data = await self.get_page(page.value)
        return data[toggle]

    async def set_toggle(self, page: Pages, toggle:str, value:bool) -> bool:
        state = 'on' if value else 'off'
        params = {'pageId':page.value, toggle:state}
        res = await self.post(params)
        return res

    async def scan_wifi(self):
        _LOGGER.debug("Scanning wifi")
        self.sse.register_callback(Events.API2_WIFISCANSTATUS, self.wifi_callback)
        params = {'action':Actions.API_STARTWIFISCAN.value}
        await self.get(params)

    def wifi_callback(self, msg):
        _LOGGER.debug("WIFI callback")
        _LOGGER.info(msg)
        self.sse.deregister_callback(Events.API2_WIFISCANSTATUS)


class CmdWrapper:
    """Convienience wrapper for HA when sending commands to the device."""
    def __init__(self, set_cmd):
        self.set_cmd = set_cmd
        pass

    async def reboot(self):
        await self.set_cmd(Commands.CMD_ESP_RES)

    async def zb_bootloader(self):
        await self.set_cmd(Commands.CMD_ZB_BSL)

    async def zb_restart(self):
        await self.set_cmd(Commands.CMD_ZB_RST)


""" For initial testing only. HA integration will directly load modules/classes as required"""
async def main():
    logging.basicConfig(level=logging.DEBUG)

    # HA passes in a session, if not using HA, create a new session for testing
    master_session = aiohttp.ClientSession()
    host = secrets.host

    client = Api2(host, session=master_session)
    client.sse.register_callback(Events.EVENT_INET_STATE, lambda x: _LOGGER.info(x.type))

    # in HA this will use hass.async_create_task
    asyncio.create_task(client.sse.client())
    try:
        await client.async_init()
    except SmlightAuthError:
        _LOGGER.debug("auth failed")
    res = await client.authenticate(secrets.apiuser, secrets.apipass)
    _LOGGER.debug("Auth: %s", res)

    api=client
    await api.scan_wifi()

    # gettog = await client.get_toggle(*SETTINGS['DISABLE_LEDS'])
    # print(gettog)
    # tog = await client.set_toggle(*SETTINGS['DISABLE_LEDS'], value=True)
    # print(tog)

    data = await api.get_page(Pages.API2_PAGE_DASHBOARD)
    print(data)

    res = await api.get_param('coordMode')
    fw = await api.get_firmware_version(device="SLZB-06p7", mode="ESP")
    print(fw[0])
    sens = await api.get_sensors()
    print(sens)
    info = await api.get_info()
    print(info.sw_version)

    print(MODE_LIST[int(res)])

    while time.time() - start < 10:
        await asyncio.sleep(1)
        res = await api.get_param('inetState')

    duration = time.time() - start
    print(f"duration {duration}")
    await client.close()
secrets = None
if __name__ == "__main__":
    from . import secrets
    asyncio.run(main())