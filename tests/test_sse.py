import asyncio
from collections.abc import Callable
import json
import logging
from unittest.mock import AsyncMock, Mock, call, patch

from aiohttp import ClientSession, web
from aiohttp.client_exceptions import SocketTimeoutError
from aresponses import ResponsesMockServer

from pysmlight.const import Actions, Events, Settings
from pysmlight.models import SettingsEvent
from pysmlight.sse import MessageEvent, sseClient
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
        {
            "event": "API2_WIFISCANSTATUS",
            "data": (
                '{"wifi":[{"ssid":"WifiAAAA19","rssi":-90,"channel":11,' '"secure":3}]}'
            ),
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
    unload: list[Callable] = []
    log_message_handler = Mock()
    all_message_handler = Mock()
    settings_message_handler = Mock()
    aresponses.add(f"{host}:81", "/", "GET", mock_sse_stream)
    async with ClientSession() as session:
        client = Api2(host, session=session)
        unload.append(client.sse.register_callback(Events.LOG_STR, log_message_handler))
        unload.append(
            client.sse.register_callback(Events.CATCH_ALL, all_message_handler)
        )
        unload.append(
            client.sse.register_settings_cb(
                Settings.DISABLE_LEDS, settings_message_handler
            )
        )

        def wifi_cb(event: MessageEvent):
            assert event.data
            assert event.type == "API2_WIFISCANSTATUS"
            assert json.loads(event.data)["wifi"]

        with patch("pysmlight.Api2.get", return_value=None):
            unload.append(await client.scan_wifi(wifi_cb))

        await client.sse.sse_stream()

        assert log_message_handler.call_count == 1
        assert all_message_handler.call_count == 4
        assert settings_message_handler.call_count == 1
        assert settings_message_handler.call_args == call(
            SettingsEvent(
                page=8, origin="ha", needReboot=False, setting={"disableLeds": True}
            )
        )

        # remove callbacks
        for remove_cb in unload:
            remove_cb()
        unload.clear()
        assert len(client.sse.callbacks) == 1


async def test_get_param_inetstate(aresponses: ResponsesMockServer) -> None:
    """Test command to trigger inetState event."""

    async def response_handler(request):
        params = request.query
        assert int(params["action"]) == Actions.API_GET_PARAM.value
        assert params["param"] == "inetState"
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text="ok",
        )

    aresponses.add(
        host,
        "/api2",
        "GET",
        response_handler,
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        assert await client.get_param("inetState") == "ok"
        # invalid param
        assert await client.get_param("inet") is None


async def test_sse_client_task():
    async with ClientSession() as session:
        client = sseClient(host, session)
        client.legacy_api = True

        with patch.object(
            client, "sse_stream", new_callable=AsyncMock
        ) as mock_sse_stream:
            mock_sse_stream.side_effect = SocketTimeoutError

            task = asyncio.create_task(client.client())
            assert task is not None
            assert not task.done()
            await asyncio.sleep(0.1)
            assert client.timeout.sock_read == 600
            client.sse_stream.assert_called_once()

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
