"""Tests for retrieving device information from SLZB-06x devices."""

import json
from unittest.mock import patch

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectionError
from aresponses import ResponsesMockServer
import pytest

from pysmlight import Api2, Info, Radio
from pysmlight.const import Settings
from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError

from . import load_fixture

host = "slzb-06.local"


async def test_info_device_info(aresponses: ResponsesMockServer) -> None:
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
        assert info

        assert info.wifi_mode == 0
        assert info.ram_total == 285
        assert info.fs_total == 3456
        assert info.zb_ram_size == 296
        assert info.zb_flash_size == 1024
        assert info.coord_mode == 0
        assert info.device_ip == "192.168.1.63"
        assert info.fw_channel == "dev"
        assert info.MAC == "DD:88:FC:AA:EE:FF"
        assert info.model == "SLZB-06p10"
        assert info.sw_version == "v2.5.2"
        assert info.zb_hw == "CC2674P10"
        assert info.zb_version == "20240315"
        assert info.zb_type == 0
        assert info.legacy_api == 0
        assert info.hostname == "SLZB-06P10"
        assert len(info.radios) == 1
        assert info.radios is not None
        assert info.radios[0] == Radio(
            chip_index=0,
            zb_channel=None,
            zb_flash_size=1024,
            zb_hw="CC2674P10",
            zb_ram_size=296,
            zb_version="20240315",
            zb_type=0,
            radioModes=None,
        )


async def test_info_device_mr_info(aresponses: ResponsesMockServer) -> None:
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
        assert info

        assert info.wifi_mode == 0
        assert info.ram_total == 300
        assert info.fs_total == 3456
        assert info.coord_mode == 0
        assert info.device_ip == "192.168.1.62"
        assert info.fw_channel == "dev"
        assert info.MAC == "DD:88:FC:AA:EE:FF"
        assert info.model == "SLZB-MR1"
        assert info.sw_version == "v2.7.1"
        assert info.legacy_api == 0
        assert info.hostname == "SLZB-MR1"

        assert info.radios is not None
        assert len(info.radios) == 2
        assert info.radios[0] == Radio(
            chip_index=0,
            zb_channel=1,
            zb_flash_size=768,
            zb_hw="EFR32MG21",
            zb_ram_size=96,
            zb_version="20240510",
            zb_type=0,
            radioModes=[True, True, True, False, False],
        )
        assert info.radios[1] == Radio(
            chip_index=1,
            zb_channel=1,
            zb_flash_size=704,
            zb_hw="CC2652P7",
            zb_ram_size=152,
            zb_version="20240716",
            zb_type=0,
            radioModes=[True, True, True, False, False],
        )


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


async def test_info_sensors(aresponses: ResponsesMockServer) -> None:
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
        assert sensors

        assert sensors.esp32_temp == 39.44
        assert sensors.zb_temp == 35.76
        assert sensors.zb_temp2 == 34.20
        assert sensors.uptime == 700
        assert sensors.socket_uptime is None
        assert sensors.ram_usage == 91
        assert sensors.fs_used == 192
        assert sensors.ethernet is True
        assert sensors.wifi_connected is False
        assert sensors.wifi_status == 2
        assert sensors.disable_leds is False
        assert sensors.night_mode is False
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

        assert info.device_ip == "192.168.1.157"
        assert info.fw_channel == "release"
        assert info.MAC == "DD:88:FC:AA:EE:FF"
        assert info.model == "SLZB-06p10"
        assert info.sw_version == "v2.0.20"
        assert info.zb_hw == "CC2674P10"
        assert info.zb_version is None
        assert info.zb_channel == 2
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

        assert info.device_ip == "192.168.1.157"
        assert info.MAC == "DD:88:FC:AA:EE:FF"
        assert info.model == "SLZB-06"
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
