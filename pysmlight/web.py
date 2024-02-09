#!/usr/bin/env python3
import asyncio
import aiohttp
from aiosseclient import aiosseclient
from .const import (
    MODE_LIST,
    PARAM_LIST,
    Actions,
    Commands,
    Events,
    Pages
)
from .payload import Payload
import json
import logging

import time


logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

start = time.time()
# host = "slzb-06m.local"

class webClient:
    def __init__(self, host=None):
        self.auth = None
        self.headers={'Content-Type': 'application/json; charset=utf-8'}
        self.host = host
        self.session = None
        self.url = f"http://{host}/api2"

    async def async_init(self):
        if self.host != "smlight.tech":
            if await self.check_auth_needed():
                _LOGGER.info("Authentication required")
                #fallback to hardcoded test credentials
                if self.auth is None:
                    self.auth = aiohttp.BasicAuth(secrets.apiuser, secrets.apipass)
        self.session = aiohttp.ClientSession(headers=self.headers, auth=self.auth)
        _LOGGER.info("Session created")

    
    async def authenticate(self, user:str, password:str):
        """Pass in credentials and check auth is successful"""
        self.auth = aiohttp.BasicAuth(user, password)
        return not await self.check_auth_needed()

    async def check_connect(self):
        if self.host:
            try:
                async with aiohttp.ClientSession() as asession:
                    response = await asession.get(f"http://{self.host}/metrics")
                    return response.status == 200
            except aiohttp.client_exceptions.ClientConnectorError:
                _LOGGER.debug("Connection error")
        return False
    """
    Check if we have valid authentication credentials for the device
    Returns True if authentication is required and/or failed
    """
    async def check_auth_needed(self):
        try:
            async with aiohttp.ClientSession(auth=self.auth) as asession:
                response = await asession.get(self.url)
                return response.status == 401
        except aiohttp.client_exceptions.ClientConnectorError:
            _LOGGER.debug("Connection error")
            exit()

    async def get(self, params):
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.headers, auth=self.auth)
        async with self.session.get(self.url, params=params) as response:
            hdr = response.headers.get('respValuesArr')
            if hdr or (params and int(params['action']) == Actions.API_GET_PAGE.value):
                return hdr
            else:
                return await response.text(encoding='utf-8')

    def set_host(self, host):
        self.host = host
        self.url = f"http://{host}/api2"

    async def close(self):
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def __aenter__(self):
        await self.async_init()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

""" 
Client for downloading firmware manifests for SLZB-06
https://smlight.tech/flasher/firmware/bin/slzb06x/ota.php?type=(ESP|ZB)

"""
class FwClient(webClient):
    def __init__(self):
        host = "smlight.tech"
        super().__init__(host)
        self.url = f"https://{host}/flasher/firmware/bin/slzb06x/ota.php"

    # mode: (ESP|ZB)
    async def get(self, mode):
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.headers, auth=None)

        params = {'type':mode}
        async with self.session.get(self.url, params=params) as response:
            res = await response.text(encoding='utf-8')
            return json.loads(res)

class Api2:
    def __init__(self, host, client, sse=None) -> None:
        if client is None:
            self.client = webClient(host)
        else:
            self.client = client
        if sse:
            self.sse = sse

    async def get_device_payload(self) -> Payload:
        data = await self.get_page(Pages.API2_PAGE_DASHBOARD)
        res = Payload(data)

    """Extract Respvaluesarr json from page repsonse header"""
    async def get_page(self, page:Pages) -> dict | None:
        params = {'action':Actions.API_GET_PAGE.value, 'pageId':page.value}
        res = await self.client.get(params)
        data = json.loads(res)
        if data:
            return data
        return None

    async def get_param(self, param) -> str | None:
        if param in PARAM_LIST:
            params = {'action':Actions.API_GET_PARAM.value, 'param':param}
            return await self.client.get(params)
        return None

    async def set_cmd(self, cmd:Commands) -> None:
        params = {'action':Actions.API_CMD.value, 'param':cmd.value}
        await self.client.get(params)

    async def fw_update(self, mode, fw_url, fw_type=None, fw_version=None) -> None:
        #Register callback 'ESP_UPD_done'? before calling this
        if mode == "ZB":
            params = {'action':Actions.API_FLASH_ZB.value, 'fwUrl':fw_url, 'fwType':fw_type, 'fwVersion':fw_version}
        else:
            params = {'action':Actions.API_FLASH_ESP.value, 'fwUrl':fw_url}
        await self.client.get(params)

    async def scan_wifi(self):
        _LOGGER.debug("Scanning wifi")
        self.sse.register_callback(Events.API2_WIFISCANSTATUS.name, self.wifi_callback)
        params = {'action':Actions.API_STARTWIFISCAN.value}
        await self.client.get(params)

    def wifi_callback(self, msg):
        _LOGGER.debug("WIFI callback")
        _LOGGER.info(msg.dump())
        self.sse.deregister_callback(Events.API2_WIFISCANSTATUS.name)

"""
Initialise a client for Server Sent Events (SSE) to receive events from the SLZB-06x
""" 
class sseClient:
    def __init__(self, host):
        self.url = f"http://{host}/events"
        #HA should register callbacks but for testing include this here
        # self.cb = {"*": self.msg_callback}
        self.cb = {Events.EVENT_INET_STATE.name: self.msg_callback}

    async def client(self):
        async for event_msg in aiosseclient(self.url):
            if event_msg.event in self.cb.keys():
                self.cb[event_msg.event](event_msg)
            if "*" in self.cb.keys():
                self.cb["*"](event_msg)

    def register_callback(self, event:Events, cb):
        # Catch all callback
        if event is None:
            self.cb["*"] = cb
        # allow to register callbacks per event type
        self.cb[event] = cb

    def deregister_callback(self, event:Events):
        # allow to deregister callbacks per event type
        if event in self.cb.keys():
            del self.cb[event]

    def msg_callback(self, msg):
        _LOGGER.info(msg.dump())

""" For initial testing only. HA integration will directly load modules/classes as required"""
async def main():
    host = secrets.host
    sse = sseClient(host)
    asyncio.create_task(sse.client())

    async with FwClient() as fwc:
        res = await fwc.get("ZB")
    # fwc = FwClient()
    # fwc.close()

    async with webClient(host) as client:
        api=Api2(host, client, sse)
        await api.scan_wifi()

        data = await api.get_page(Pages.API2_PAGE_DASHBOARD)
        payload = Payload(data)
        print(payload.model, payload.MAC, payload.sw_version, payload.zb_version, payload.mode, payload.uptime)
        print(data)

        res = await api.get_param('coordMode')
        print(MODE_LIST[int(res)])

        while time.time() - start < 5:
            await asyncio.sleep(1)
            res = await api.get_param('inetState')

    duration = time.time() - start
    print(f"duration {duration}")

secrets = None
if __name__ == "__main__":
    from . import secrets
    asyncio.run(main())