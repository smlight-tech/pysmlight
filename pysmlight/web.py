#!/usr/bin/env python3
import asyncio
import aiohttp
from aiosseclient import aiosseclient
from .const import (
    MODE_LIST,
    PARAM_LIST,
    Actions,
    Commands,
    Pages
)
from . import secrets
import json
import time


start = time.time()
# host = "slzb-06m.local"
host = secrets.host

class webClient:
    def __init__(self, host):
        self.auth = None
        self.headers={'Content-Type': 'application/json; charset=utf-8'}
        self.host = host
        self.session = None
        self.url = f"http://{host}/api2"

    async def async_init(self):
        if self.host != "smlight.tech":
            if await self.check_auth_needed():
                print("Authentication required")
                self.auth = aiohttp.BasicAuth(secrets.apiuser, secrets.apipass)
        self.session = aiohttp.ClientSession(headers=self.headers, auth=self.auth)
        print("Session created")

    async def check_auth_needed(self):
        async with aiohttp.ClientSession() as asession:
            response = await asession.get(self.url)
            return response.status == 401

    async def get(self, params):
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.headers, auth=self.auth)
        async with self.session.get(self.url, params=params) as response:
            hdr = response.headers.get('respValuesArr')
            if hdr or (params and int(params['action']) == Actions.API_GET_PAGE.value):
                return hdr
            else:
                return await response.text(encoding='utf-8')

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
    def __init__(self, client) -> None:
        if client is None:
            self.client = webClient(host)
        else:
            self.client = client

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


"""
Initialise a client for Server Sent Events (SSE) to receive events from the SLZB-06x
""" 
class sseClient:
    def __init__(self, host):
        self.url = f"http://{host}/events"
        #HA should register callbacks but for testing include this here
        # self.cb = {"*": self.msg_callback}
        self.cb = {"EVENT_INET_STATE": self.msg_callback}

    async def client(self):
        async for event_msg in aiosseclient(self.url):
            if event_msg.event in self.cb.keys():
                self.cb[event_msg.event](event_msg)
            if "*" in self.cb.keys():
                self.cb["*"](event_msg)

    def register_callback(self, event, cb):
        # Catch all callback
        if event is None:
            self.cb["*"] = cb
        # allow to register callbacks per event type
        self.cb[event] = cb

    def deregister_callback(self, event):
        # allow to deregister callbacks per event type
        if event in self.cb.keys():
            del self.cb[event]

    def msg_callback(self, msg):
        print(msg.dump())

""" For initial testing only. HA integration will directly load modules/classes as required"""
async def main():
    sse = sseClient(host)
    asyncio.create_task(sse.client())

    async with FwClient() as fwc:
        res = await fwc.get("ZB")
    # fwc = FwClient()
    # fwc.close()

    async with webClient(host) as client:
        api=Api2(client)

        data = await api.get_page(Pages.API2_PAGE_DASHBOARD)
        print(data)

        res = await api.get_param('coordMode')
        print(MODE_LIST[int(res)])

        while time.time() - start < 5:
            await asyncio.sleep(1)
            res = await api.get_param('inetState')

    duration = time.time() - start
    print(f"duration {duration}")

if __name__ == "__main__":
    asyncio.run(main())