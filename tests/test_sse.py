import asyncio
from collections.abc import Callable
import json
import logging
from unittest.mock import AsyncMock, Mock, call, patch

from aiohttp import ClientSession, web
from aiohttp.client_exceptions import ClientConnectionError, SocketTimeoutError
from aresponses import ResponsesMockServer

from pysmlight.const import Actions, Events, Pages, Settings
from pysmlight.models import SettingsEvent
from pysmlight.sse import LEGACY_SSE_VERSION, MessageEvent, sseClient
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


async def test_sse_page_cb(aresponses: ResponsesMockServer) -> None:
    """Test sse page_cb is called with the changes dict for the matching page."""
    page_message_handler = Mock()
    aresponses.add(f"{host}:81", "/", "GET", mock_sse_stream)
    async with ClientSession() as session:
        client = Api2(host, session=session)
        remove_cb = client.sse.register_page_cb(
            Pages.API2_PAGE_SETTINGS_LED, page_message_handler
        )

        await client.sse.sse_stream()

        assert page_message_handler.call_count == 1
        assert page_message_handler.call_args == call(
            {"disableLeds": True, "nightMode": False}
        )

        # Test that the returned deregister function removes the callback
        remove_cb()
        assert Pages.API2_PAGE_SETTINGS_LED not in client.sse.page_cb


async def test_sse_page_cb_no_match() -> None:
    """Test page_cb is not invoked when the event is for a different page."""
    async with ClientSession() as session:
        client = sseClient(host, session)
        page_message_handler = Mock()
        client.register_page_cb(Pages.API2_PAGE_NETWORK, page_message_handler)

        event = Mock()
        event.data = (
            '{"page":8,"origin":"ha","changes":{"disableLeds":true},"needReboot":false}'
        )
        client._handle_settings(event)

        page_message_handler.assert_not_called()


async def test_sse_page_cb_no_changes() -> None:
    """Test page_cb is not invoked when the event carries no changes key."""
    async with ClientSession() as session:
        client = sseClient(host, session)
        page_message_handler = Mock()
        client.register_page_cb(Pages.API2_PAGE_SETTINGS_LED, page_message_handler)

        event = Mock()
        event.data = '{"page":8,"origin":"ha","needReboot":false}'
        client._handle_settings(event)

        page_message_handler.assert_not_called()


async def test_sse_page_cb_invalid_page() -> None:
    """Test that a SAVE_PARAMS event with an unknown page value returns early (ValueError)."""
    async with ClientSession() as session:
        client = sseClient(host, session)
        page_message_handler = Mock()
        client.register_page_cb(Pages.API2_PAGE_SETTINGS_LED, page_message_handler)

        event = Mock()
        event.data = (
            '{"page":999,"origin":"ha","changes":{"foo":"bar"},"needReboot":false}'
        )
        client._handle_settings(event)

        page_message_handler.assert_not_called()


async def test_sse_legacy_url(aresponses: ResponsesMockServer) -> None:
    """Test that sw_version <= LEGACY_SSE_VERSION switches to the legacy URL."""
    aresponses.add(host, "/events", "GET", mock_sse_stream)
    async with ClientSession() as session:
        client = sseClient(host, session)
        client.sw_version = LEGACY_SSE_VERSION

        await client.sse_stream()

        assert client.url == f"http://{host}/events"


async def test_sse_stream_connection_error() -> None:
    """Test that ClientConnectionError inside the stream is caught and not re-raised."""

    class MockEventSource:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise ClientConnectionError("connection failed")

    async with ClientSession() as session:
        client = sseClient(host, session)
        with patch("pysmlight.sse.EventSource", return_value=MockEventSource()):
            await client.sse_stream()  # must not raise


@patch("pysmlight.sse._LOGGER")
async def test_sse_register_callback_duplicate(mock_logger: Mock) -> None:
    """Test that registering a callback for an existing event logs a warning."""
    async with ClientSession() as session:
        client = sseClient(host, session)
        cb1, cb2 = Mock(), Mock()
        client.register_callback(Events.LOG_STR, cb1)
        client.register_callback(Events.LOG_STR, cb2)
        mock_logger.warning.assert_called_once()
        assert client.callbacks[Events.LOG_STR] is cb2


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
