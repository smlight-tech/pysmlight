"""Test writing settings on SLZB devices."""

import urllib

from aiohttp import ClientSession
from aresponses import ResponsesMockServer
import pytest

from pysmlight import Api2
from pysmlight.const import Settings
from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError, SmlightError

host = "slzb-06.local"


async def test_settings_toggle(aresponses: ResponsesMockServer) -> None:
    """Test toggling settings on SLZB devices."""
    aresponses.add(
        host,
        "/settings/saveParams",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text="ok",
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        page, key = Settings.DISABLE_LEDS.value
        res = await client.set_toggle(page, key, True)
        assert res

        req = aresponses.history[0][0]
        assert req.content_type == "application/x-www-form-urlencoded"
        body = urllib.parse.parse_qs(await req.text())
        assert body
        assert int(body["pageId"][0]) == page.value
        assert bool(body["ha"][0]) is True
        value = True if body[key][0] in "on" else False
        assert value


@pytest.mark.parametrize(
    ("code", "exception"), [(401, SmlightAuthError), (404, SmlightConnectionError)]
)
async def test_settings_toggle_post_error(
    aresponses: ResponsesMockServer, code: int, exception: SmlightError
) -> None:
    """Test toggling settings on SLZB devices."""
    aresponses.add(
        host,
        "/settings/saveParams",
        "POST",
        aresponses.Response(
            status=code,
            headers={"Content-Type": "application/json"},
            text="ok",
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        with pytest.raises(exception):
            page, key = Settings.DISABLE_LEDS.value
            await client.set_toggle(page, key, True)


async def test_settings_ble_proxy(aresponses: ResponsesMockServer) -> None:
    """Test setting BLE proxy configuration."""
    aresponses.add(
        host,
        "/settings/saveParams",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text="ok",
        ),
    )
    aresponses.add(
        host,
        "/api2",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text="ok",
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        res = await client.set_ble_proxy(True)
        assert res

        req_post = aresponses.history[0][0]
        assert req_post.content_type == "application/x-www-form-urlencoded"
        body = urllib.parse.parse_qs(await req_post.text())
        assert int(body["pageId"][0]) == 32  # Pages.API2_PAGE_BLE
        assert body["bleEn"][0] == "on"
        assert body["blePrxEn"][0] == "on"
        assert bool(body["ha"][0]) is True

        req_get = aresponses.history[1][0]
        query = req_get.query
        assert int(query["action"]) == 4  # Actions.API_CMD
        assert int(query["cmd"]) == 3  # Commands.CMD_ESP_RES
