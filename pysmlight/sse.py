import logging
from typing import Callable

import aiohttp
from aiohttp_sse_client2 import client as sse_client

from .const import Events

_LOGGER = logging.getLogger(__name__)

# override logging level aiohttp_sse_client2 library
aiologger = logging.getLogger("aiohttp_sse_client2")
aiologger.setLevel(logging.INFO)


class sseClient:
    """Initialise a client to receive Server Sent Events (SSE)"""

    def __init__(self, host, session):
        self.callbacks = {}
        self.session = session
        self.url = f"http://{host}/events"
        self.timeout = aiohttp.ClientTimeout(
            total=None, connect=None, sock_connect=None, sock_read=30
        )

    async def client(self):
        while True:
            await self.sse_stream()

    async def sse_stream(self):
        async with sse_client.EventSource(
            self.url, session=self.session, timeout=self.timeout
        ) as event_source:
            try:
                async for event in event_source:
                    _LOGGER.debug(event)
                    await self.message_handler(event)
            except aiohttp.ClientConnectionError:
                _LOGGER.debug("Client Connection error")
            else:
                _LOGGER.debug("Connection closed cleanly")

    async def message_handler(self, event):
        self.callbacks.get(event.type, lambda x: None)(event)
        self.callbacks.get("*", lambda x: None)(event)

    def register_callback(self, event: Events, cb: Callable):
        """register a callback for a specific event type or all events"""
        if event and event.name in self.callbacks:
            _LOGGER.warning("Callback for %s already exists, overwriting", event)

        if event is not None:
            self.callbacks[event.name] = cb
        else:
            self.callbacks["*"] = cb

    def deregister_callback(self, event: Events) -> Callable:
        """Deregister callbacks per event type"""
        cb: Callable
        if event is None:
            cb = self.callbacks.pop("*", None)
        else:
            cb = self.callbacks.pop(event.name, None)
        return cb
