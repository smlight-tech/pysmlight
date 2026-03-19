"""Tests for retrieving device information from SLZB-06x devices."""

import json
from unittest.mock import patch

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectionError
from aresponses import ResponsesMockServer
import pytest
from syrupy.assertion import SnapshotAssertion

from pysmlight import Api2, Info
from pysmlight.const import Settings
from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError

from . import load_fixture

host = "slzb-06.local"


async def test_info_device_info(
    aresponses: ResponsesMockServer, snapshot: SnapshotAssertion
) -> None:
    """Test getting SLZB device information."""
    aresponses.add(
        host,
        "/ha_info",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-info.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        info: Info = await client.get_info()
        assert info == snapshot


async def test_info_device_mr_info(
    aresponses: ResponsesMockServer, snapshot: SnapshotAssertion
) -> None:
    """Test getting SLZB device information for multi radios."""
    aresponses.add(
        host,
        "/ha_info",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-info-radios.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        info: Info = await client.get_info()
        assert info == snapshot


async def test_ultima_info(
    aresponses: ResponsesMockServer, snapshot: SnapshotAssertion
) -> None:
    """Test getting SLZB Ultima device information."""
    aresponses.add(
        host,
        "/ha_info",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-ultima-info.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        info: Info = await client.get_info()
        assert info == snapshot


async def test_info_get_auth_fail(aresponses: ResponsesMockServer) -> None:
    """Test getting SLZB device information."""
    aresponses.add(
        host,
        "/ha_info",
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
            await client.get_info()


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_info_get_connector_error(mock_get) -> None:
    """Test getting SLZB device information."""

    async def mock_raise(*args, **kwargs):
        raise ClientConnectionError("Mocked connection error")

    mock_get.return_value.__aenter__.side_effect = mock_raise
    async with ClientSession() as session:
        client = Api2(host, session=session)

        with pytest.raises(SmlightConnectionError):
            await client.get_info()
        with pytest.raises(SmlightConnectionError):
            await client.get_sensors()


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.post")
async def test_info_post_connector_error(mock_post) -> None:
    """Test getting SLZB device information."""

    async def mock_raise(*args, **kwargs):
        raise ClientConnectionError("Mocked connection error")

    mock_post.return_value.__aenter__.side_effect = mock_raise
    async with ClientSession() as session:
        client = Api2(host, session=session)
        _page, _toggle = Settings.NIGHT_MODE.value
        with pytest.raises(SmlightConnectionError):
            await client.set_toggle(_page, _toggle, True)


async def test_info_sensors(
    aresponses: ResponsesMockServer, snapshot: SnapshotAssertion
) -> None:
    """Test getting SLZB sensor data."""
    aresponses.add(
        host,
        "/ha_sensors",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-sensors.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        sensors = await client.get_sensors()
        assert sensors == snapshot


async def test_ultima_sensors(
    aresponses: ResponsesMockServer, snapshot: SnapshotAssertion
) -> None:
    """Test getting SLZB Ultima sensor data."""
    aresponses.add(
        host,
        "/ha_sensors",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-ultima-sensors.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        sensors = await client.get_sensors()
        assert sensors == snapshot
        assert sensors.auto_zigbee is False


async def test_info_legacy_info(aresponses: ResponsesMockServer) -> None:
    """Test getting legacy device info from devices with old firmware."""
    headers = {
        "Content-Type": "application/json",
        "respValuesArr": json.dumps(json.loads(load_fixture("slzb-06-resparr.json"))),
    }
    aresponses.add(
        host,
        "/ha_info",
        "GET",
        aresponses.Response(
            status=404,
            headers={"Content-Type": "application/json"},
        ),
    )
    aresponses.add(
        host,
        "/api2",
        "GET",
        aresponses.Response(status=200, headers=headers, text="Some html"),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        info: Info = await client.get_info()
        assert info

        assert info.sw_version == "v2.0.20"
        assert info.zb_version is None
        assert info.legacy_api == 1


async def test_info_legacy_info2(aresponses: ResponsesMockServer) -> None:
    """Test getting legacy device info from devices with old firmware."""
    headers = {
        "Content-Type": "application/json",
        "respValuesArr": json.dumps(
            json.loads(load_fixture("slzb-06-resparr-0.9.9.json"))
        ),
    }
    aresponses.add(
        host,
        "/ha_info",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text="URL NOT FOUND",
        ),
    )
    aresponses.add(
        host,
        "/api",
        "GET",
        aresponses.Response(status=200, headers=headers, text="Some html"),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        info: Info = await client.get_info()
        assert info

        assert info.sw_version == "0.9.9"
        assert info.legacy_api == 2


async def test_info_invalid_versions() -> None:
    """Test conversion of invalid firmware versions (per awesomeVersion)

    factory firmware that may have .plus suffix
    development firmware that may have .dev suffix."""
    info = Info(sw_version="v2.3.6.plus")
    assert info.sw_version == "v2.3.6.1"
    info = Info(sw_version="v2.3.6.plus2")
    assert info.sw_version == "v2.3.6.2"
    info = Info(sw_version="v2.8.0.dev")
    assert info.sw_version == "v2.8.0.dev0"


async def test_info_ultima_zwave() -> None:
    """Test Ultima only has 2 radios without zwave addon installed."""
    info = Info.from_dict(
        {
            "model": "SLZB-Ultima4",
            "addons": {"zwave": False},
            "radios": [
                {"zb_hw": "Radio1"},
                {"zb_hw": "Radio2"},
                {"zb_hw": "Radio3 (Z-Wave)"},
            ],
        }
    )

    assert len(info.radios) == 2
    assert info.radios[0].zb_hw == "Radio1"
    assert info.radios[1].zb_hw == "Radio2"


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("SLZB-Ultima4", True),
        ("SLZB-Ultima3", True),
        ("SLZB-06p10", False),
        (None, False),
    ],
)
def test_info_has_peripherals(model: str | None, expected: bool) -> None:
    """Test has_peripherals returns True only for peripheral-capable models."""
    info = Info(model=model)
    assert info.has_peripherals is expected


@pytest.mark.parametrize(
    ("hw_version", "expected"),
    [
        (104, "1.04"),
        ("1.04", "1.04"),
        (None, None),
    ],
)
def test_info_hw_version_formatting(
    hw_version: int | str | None, expected: str | None
) -> None:
    """Test hw_version is formatted correctly from raw integer or pre-formatted string."""
    info = Info(hw_version=hw_version)
    assert info.hw_version == expected
