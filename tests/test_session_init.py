"""Tests for session initialization."""

from aiohttp import ClientSession

from pysmlight.web import Api2

host = "slzb-06.local"


async def test_init_with_session() -> None:
    """Test Api2 initialization with provided session."""
    async with ClientSession() as session:
        client = Api2(host, session=session)
        assert client.session is session
        assert client.close_session is False
        assert client.sse is not None


async def test_init_without_session() -> None:
    """Test Api2 initialization without provided session."""
    client = Api2(host)
    try:
        assert client.session is not None
        assert client.close_session is True
        assert client.sse is not None
    finally:
        await client.close()


async def test_init_with_sse() -> None:
    """Test Api2 initialization with provided sse client."""
    from pysmlight.sse import sseClient

    async with ClientSession() as session:
        sse = sseClient(host, session)
        client = Api2(host, session=session, sse=sse)
        assert client.session is session
        assert client.sse is sse
