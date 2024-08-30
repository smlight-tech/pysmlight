""" Tests for authenticating with SLZB-06x devices. """
from aiohttp import ClientSession
from aresponses import ResponsesMockServer
import pytest

from pysmlight.exceptions import SmlightAuthError
from pysmlight.web import Api2, webClient

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
        repeat=2,
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        assert await client.check_auth_needed() is True
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


async def test_with_async(aresponses: ResponsesMockServer) -> None:
    """Test that authentication has access the API."""
    aresponses.add(
        host,
        "/api2",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
        ),
        repeat=2,
    )
    async with webClient(host) as client:
        assert client.session is not None
        assert await client.check_auth_needed() is False
