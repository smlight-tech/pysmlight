""" Tests for authenticating with SLZB-06x devices. """
from aiohttp import ClientSession
from aresponses import ResponsesMockServer
import pytest

from pysmlight import Api2
from pysmlight.exceptions import SmlightAuthError

from . import load_fixture

host = "slzb-06.local"
USER = "admin"
PASSWORD = "admin"


async def test_auth_not_needed(aresponses: ResponsesMockServer) -> None:
    """Test that authentication is not needed to access the API."""
    aresponses.add(
        host,
        "/api2",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-info.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        assert await client.check_auth_needed() is False


async def test_auth_is_required(aresponses: ResponsesMockServer) -> None:
    """Test that authentication is required to access the API."""
    aresponses.add(
        host,
        "/api2",
        "GET",
        aresponses.Response(
            status=401,
            headers={"Content-Type": "application/json"},
            text="wrong login or password",
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        assert await client.check_auth_needed() is True


async def test_auth_is_failed(aresponses: ResponsesMockServer) -> None:
    """Test that authentication has failed to access the API."""
    aresponses.add(
        host,
        "/api2",
        "GET",
        aresponses.Response(
            status=401,
            headers={"Content-Type": "application/json"},
            text="wrong login or password",
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        with pytest.raises(SmlightAuthError):
            await client.authenticate(USER, PASSWORD)


async def test_auth_is_success(aresponses: ResponsesMockServer) -> None:
    """Test that authentication has access the API."""
    aresponses.add(
        host,
        "/api2",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        assert await client.authenticate(USER, PASSWORD) is True
