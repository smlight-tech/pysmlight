"""Test sending commands to SLZB devices."""

from __future__ import annotations

import logging

from aiohttp import ClientSession
from aresponses import ResponsesMockServer

from pysmlight import Api2

_LOGGER = logging.getLogger(__name__)

host = "slzb-06.local"


async def test_cmds_zb_bsl(aresponses: ResponsesMockServer) -> None:
    """Test sending ZB bootloader command to SLZB devices."""

    aresponses.add(
        host,
        "/api2",
        "GET",
        aresponses.Response(
            status=200, headers={"Content-Type": "application/json"}, text="ok"
        ),
    )

    async with ClientSession() as session:
        client = Api2(host, session=session)

        await client.cmds.zb_bootloader()

        data = aresponses.history[0].request.query
        expected = {"action": 4, "cmd": 2}
        for k, v in data.items():
            assert expected[k] == int(v)


async def test_cmds_core_reboot(aresponses: ResponsesMockServer) -> None:
    """Test sending ZB reset command to SLZB devices."""

    aresponses.add(
        host,
        "/api2",
        "GET",
        aresponses.Response(
            status=200, headers={"Content-Type": "application/json"}, text="ok"
        ),
    )

    async with ClientSession() as session:
        client = Api2(host, session=session)

        await client.cmds.reboot()

        data = aresponses.history[0].request.query
        expected = {"action": 4, "cmd": 3}
        for k, v in data.items():
            assert expected[k] == int(v)


async def test_cmds_zb_reboot(aresponses: ResponsesMockServer) -> None:
    """Test sending ZB reset command to SLZB devices."""

    aresponses.add(
        host,
        "/api2",
        "GET",
        aresponses.Response(
            status=200, headers={"Content-Type": "application/json"}, text="ok"
        ),
    )

    async with ClientSession() as session:
        client = Api2(host, session=session)

        await client.cmds.zb_restart()

        data = aresponses.history[0].request.query
        expected = {"action": 4, "cmd": 1}
        for k, v in data.items():
            assert expected[k] == int(v)
