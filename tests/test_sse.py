import asyncio
from collections.abc import Callable
import logging
from unittest.mock import Mock, call

import aiohttp
from aiohttp import ClientSession, web
from aresponses import ResponsesMockServer

from pysmlight.const import Events, Settings
from pysmlight.models import SettingsEvent
from pysmlight.web import Api2

_LOGGER = logging.getLogger(__name__)

host = "slzb-06.local"


def prepare_events():
    mock_events = [
        {"event": "LOG_STR", "data": "ConfigHelper|write config", "id": None},
        {"event": "EVENT_INET_STATE", "data": "ok", "id": None},
        {
            "event": "SAVE_PARAMS",
            "data": '{"page":8,"origin":"ha","changes":{"disableLeds":true,'
            '"nightMode":false},"needReboot":false}',
            "id": None,
        },
    ]

    event_stream = []
    for event in mock_events:
        event_data = []
        for field, value in event.items():
            if value is not None:
                event_data.append(f"{field}: {value}".encode())
        event_data.append(b"\n")
        event_stream.append(b"\n".join(event_data))
    return event_stream


events = prepare_events()


async def mock_sse_stream(request):
    async def event_stream():
        for message in events:
            yield message
            await asyncio.sleep(0.2)

    stream = web.StreamResponse(
        status=200,
        reason="OK",
        headers={"Content-Type": "text/event-stream"},
    )
    await stream.prepare(request)
    async for chunk in event_stream():
        await stream.write(chunk)
    await stream.write_eof()
    await stream.close()
    return stream


async def test_sse_stream(aresponses: ResponsesMockServer) -> None:
    """Test sse stream handling."""
    log_message_handler = Mock()
    all_message_handler = Mock()
    settings_message_handler = Mock()
    aresponses.add(host, "/events", "GET", mock_sse_stream)
    async with ClientSession() as session:
        client = Api2(host, session=session)
        client.sse.register_callback(Events.LOG_STR, log_message_handler)
        client.sse.register_callback(None, all_message_handler)

        client.sse.register_settings_cb(Settings.DISABLE_LEDS, settings_message_handler)
        try:
            await client.sse.sse_stream()
        except aiohttp.ClientConnectionError:
            # avoid SSE client try to reconnect
            pass
        assert log_message_handler.call_count == 1
        assert all_message_handler.call_count == 3
        cb = client.sse.deregister_callback(Events.LOG_STR)
        cb2 = client.sse.deregister_callback(None)
        assert isinstance(cb, Callable)
        assert cb == log_message_handler
        assert cb2 == all_message_handler

        assert settings_message_handler.call_count == 1
        assert settings_message_handler.call_args == call(
            SettingsEvent(
                page=8, origin="ha", needReboot=False, setting={"disableLeds": True}
            )
        )
