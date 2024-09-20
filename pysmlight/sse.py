"""Client to receive Server Sent Events (SSE) from the SMLIGHT API."""
import asyncio
import json
import logging
from typing import Callable

import aiohttp
from aiohttp.client_exceptions import ClientConnectionError, SocketTimeoutError
from aiohttp_sse_client2.client import EventSource, MessageEvent

from .const import Events, Pages, Settings
from .models import SettingsEvent

_LOGGER = logging.getLogger(__name__)

# override logging level aiohttp_sse_client2 library
aiologger = logging.getLogger("aiohttp_sse_client2")
aiologger.setLevel(logging.INFO)


class sseClient:
    """Initialise a client to receive Server Sent Events (SSE)"""

    def __init__(self, host: str, session: aiohttp.ClientSession):
        """Initialise the SSE client."""
        self.callbacks: dict[Events, Callable] = {}
        self.settings_cb: dict[Settings, Callable] = {}
        self.legacy_api = False
        self.session = session
        self.url = f"http://{host}/events"
        self.setTimeout(30)

        self.register_callback(Events.SAVE_PARAMS, self._handle_settings)

    def setTimeout(self, timeout: int) -> None:
        self.timeout = aiohttp.ClientTimeout(
            total=None, connect=None, sock_connect=None, sock_read=timeout
        )

    async def client(self) -> None:
        """Run SSE Client

        SSE client will attempt reconnection on connection error with exponental backoff
        """

        # Increase timeout for legacy API which dont have PING events
        if self.legacy_api:
            self.setTimeout(600)

        while True:
            try:
                await self.sse_stream()
            except SocketTimeoutError:
                await asyncio.sleep(5)

    async def sse_stream(self) -> None:
        """Process incoming events on the message stream"""
        async with EventSource(
            self.url, session=self.session, timeout=self.timeout, max_connect_retry=8
        ) as event_source:
            try:
                async for event in event_source:
                    _LOGGER.debug(event)
                    await self._message_handler(event)
            except (ClientConnectionError, ConnectionError) as err:
                _LOGGER.debug("Client Connection error: %s", err)
            else:
                _LOGGER.debug("Connection closed cleanly")

    async def _message_handler(self, event: MessageEvent) -> None:
        """Match event with callback for event type"""
        if event_type := getattr(Events, event.type, None):
            self.callbacks.get(event_type, lambda x: None)(event)
        self.callbacks.get(Events.CATCH_ALL, lambda x: None)(event)

    def register_callback(self, event: Events, cb: Callable) -> Callable[[], None]:
        """register a callback for a specific event type"""
        if event and event in self.callbacks:
            _LOGGER.warning("Callback for %s already exists, overwriting", event)

        self.callbacks[event] = cb

        def remove_callback():
            self.deregister_callback(event)

        return remove_callback

    def deregister_callback(self, event: Events) -> None:
        """Deregister callback for event type"""
        if event in self.callbacks:
            del self.callbacks[event]

    def _handle_settings(self, event: Events) -> None:
        """Process event and match callback for settings changes"""
        data = json.loads(event.data)
        try:
            page = Pages(data["page"])
        except ValueError:
            return

        changes = data.pop("changes", None)
        for setting in changes:
            base = data.copy()
            match_cb = next(
                (
                    cb
                    for k, cb in self.settings_cb.items()
                    if (page, setting) == k.value
                ),
                None,
            )

            if match_cb:
                base["setting"] = {setting: changes[setting]}
                result = SettingsEvent.from_dict(base)
                match_cb(result)

    def register_settings_cb(
        self, setting: Settings, cb: Callable
    ) -> Callable[[], None]:
        """Register a callback for a specific setting"""
        self.settings_cb[setting] = cb

        def remove_callback():
            self.deregister_settings_cb(setting)

        return remove_callback

    def deregister_settings_cb(self, setting: Settings) -> None:
        """Deregister callback for a setting"""
        if setting in self.settings_cb:
            del self.settings_cb[setting]
