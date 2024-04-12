"""Test writing settings on SLZB devices."""
import urllib

from aiohttp import ClientSession
from aresponses import ResponsesMockServer

from pysmlight import Api2
from pysmlight.const import Settings

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
