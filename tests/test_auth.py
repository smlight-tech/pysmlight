"""Tests for authenticating with SLZB-06x devices."""

from unittest.mock import patch

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectionError
from aresponses import ResponsesMockServer
import pytest

from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError
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
    """Test async with usage of webClient."""
    host = "slzb-06p7.local"
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
    async with webClient("slzb-06.local") as client:
        assert client.session is not None
        client.set_host(host)
        assert client.host == host
        assert await client.check_auth_needed() is False


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_auth_connector_error(mock_get) -> None:
    """Test auth connect failed."""

    async def mock_raise(*args, **kwargs):
        raise ClientConnectionError("Mocked connection error")

    mock_get.return_value.__aenter__.side_effect = mock_raise
    async with ClientSession() as session:
        client = Api2(host, session=session)

        with pytest.raises(SmlightConnectionError):
            await client.check_auth_needed()


async def test_auth_request_headers(aresponses: ResponsesMockServer) -> None:
    """Test that authenticated requests include the Authorization header."""
    aresponses.add(
        host,
        "/api2",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
        ),
    )
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
        client.auth = "Basic YWRtaW46YWRtaW4="

        await client.get(params={"action": 0})
        await client.post(params={"pageId": 1})

        req_get = aresponses.history[0][0]
        assert req_get.headers.get("Authorization") == "Basic YWRtaW46YWRtaW4="

        req_post = aresponses.history[1][0]
        assert req_post.headers.get("Authorization") == "Basic YWRtaW46YWRtaW4="
