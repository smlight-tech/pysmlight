"""Test sending actions to SLZB devices."""

from __future__ import annotations

import logging
from urllib.parse import parse_qs

from aiohttp import ClientSession
from aresponses import ResponsesMockServer

from pysmlight import Api2
from pysmlight.const import Actions, AmbiEffect, Pages
from pysmlight.models import AmbilightPayload, BuzzerPayload, IRPayload

_LOGGER = logging.getLogger(__name__)

host = "slzb-06.local"


def aresponses_fixture(aresponses: ResponsesMockServer):
    aresponses.add(
        host,
        "/settings/saveParams",
        "POST",
        aresponses.Response(
            status=200, headers={"Content-Type": "application/json"}, text="ok"
        ),
    )
    aresponses.add(
        host,
        "/api2",
        "GET",
        aresponses.Response(
            status=200, headers={"Content-Type": "application/json"}, text="ok"
        ),
    )


async def test_actions_ambilight(aresponses: ResponsesMockServer) -> None:
    """Test sending Ambilight command to SLZB devices."""

    aresponses_fixture(aresponses)

    async with ClientSession() as session:
        client = Api2(host, session=session)

        payload = AmbilightPayload(
            ultLedMode=AmbiEffect.WSULT_SOLID,
            ultLedColor="#ff0000",
            ultLedColor2="#00ff00",
            ultLedSpeed=50,
            ultLedBri=255,
            ultLedDir=1,
        )

        await client.actions.ambilight(payload)

        req = aresponses.history[0].request
        assert req.method == "POST"
        assert req.path == "/settings/saveParams"

        body = await req.text()
        data = parse_qs(body)

        assert data["pageId"][0] == str(Pages.API2_PAGE_AMBILIGHT.value)
        assert data["ultLedMode"][0] == str(AmbiEffect.WSULT_SOLID.value)
        assert data["ultLedColor"][0] == "#ff0000"
        assert data["ultLedColor2"][0] == "#00ff00"
        assert data["ultLedSpeed"][0] == "50"
        assert data["ultLedBri"][0] == "255"
        assert data["ultLedDir"][0] == "1"


async def test_actions_buzzer(aresponses: ResponsesMockServer) -> None:
    """Test sending Buzzer command to SLZB devices."""

    async def response_handler(request):
        body = await request.text()
        data = parse_qs(body)
        assert data["action"][0] == str(Actions.API_BUZZER.value)
        assert data["code"][0] == "Arkanoid:d=4,o=5,b=140:8g6,16p"
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text="ok",
        )

    aresponses.add(host, "/api2", "POST", response_handler)

    async with ClientSession() as session:
        client = Api2(host, session=session)

        payload = BuzzerPayload(code="Arkanoid:d=4,o=5,b=140:8g6,16p")

        res = await client.actions.buzzer(payload)

        req = aresponses.history[0].request
        assert req.method == "POST"

        assert res is True


async def test_actions_send_ir_code(aresponses: ResponsesMockServer) -> None:
    """Test sending IR command to SLZB devices."""

    aresponses_fixture(aresponses)

    async with ClientSession() as session:
        client = Api2(host, session=session)

        payload = IRPayload(code="C2B0A9")

        await client.actions.send_ir_code(payload)

        req = aresponses.history[0].request
        assert req.method == "POST"

        body = await req.text()
        data = parse_qs(body)

        assert data["pageId"][0] == str(Pages.API2_PAGE_IR.value)
        assert data["code"][0] == "C2B0A9"


async def test_actions_get_ir_code(aresponses: ResponsesMockServer) -> None:
    """Test getting IR code from SLZB devices."""

    async def response_handler(request):
        data = request.query
        assert data["pageId"] == str(Pages.API2_PAGE_IR.value)
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "text/plain"},
            text="C2B0A9",
        )

    aresponses.add(host, "/api2", "GET", response_handler)

    async with ClientSession() as session:
        client = Api2(host, session=session)

        payload = IRPayload()
        res = await client.actions.get_ir_code(payload)

        req = aresponses.history[0].request
        assert req.method == "GET"

        assert res == "C2B0A9"
