import logging
from aiohttp_sse_client2 import client as sse_client
from typing import Callable
from .const import Events

_LOGGER = logging.getLogger(__name__)

#overide logging level aiohttp_sse_client2 library
aiologger = logging.getLogger('aiohttp_sse_client2')
aiologger.setLevel(logging.INFO)

class sseClient:
    """ Initialise a client to receive Server Sent Events (SSE) """
    def __init__(self, host, session):
        self.callbacks = {}
        self.session = session
        self.url = f"http://{host}/events"

    async def client(self):
        async with sse_client.EventSource(
            self.url, session=self.session
        ) as event_source:
            try:
                async for event in event_source:
                    _LOGGER.debug(event)
                    await self.message_hander(event)
            except ConnectionError:
                _LOGGER.debug("Connection error")

    async def message_hander(self, event):
        self.callbacks.get(event.type, lambda x: None)(event)
        self.callbacks.get("*", lambda x: None)(event)

    def register_callback(self, event:Events, cb: Callable):
        """ register a callback for a specific event type or all events"""
        if event.name in self.callbacks:
            _LOGGER.warning(f"Callback for {event} already exists, overwriting")

        if event is not None:
            self.callbacks[event.name] = cb
        else:
            self.callbacks["*"] = cb

    def deregister_callback(self, event:Events):
        """ Deregister callbacks per event type """
        if event is None:
            self.callbacks.pop("*", None)
        else:
            self.callbacks.pop(event.name, None)

    def msg_callback(self, msg):
        _LOGGER.info(msg.message)