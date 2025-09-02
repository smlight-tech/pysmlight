"""Tests for retrieving firmware information for SLZB-06x devices."""

from aiohttp import ClientSession
from aresponses import ResponsesMockServer
import pytest

from pysmlight import Api2, Firmware
from pysmlight.const import Actions

from . import load_fixture

host = "slzb-06.local"

MOCK_FIRMWARE_ESP = Firmware(
    ver="v2.5.2",
    mode="ESP",
    link="https://localhost/firmware.bin",
    notes="CHANGELOG v2.5.2\r\nFixed bug with the lights\nMore fixes",
)

MOCK_FIRMWARE_ZB = Firmware(
    rev="20240315",
    mode="ZB",
    link="https://localhost/firmware.bin",
    baud=115200,
    type=0,
    prod=True,
    notes=None,
)


@pytest.mark.asyncio
async def test_esp_firmware_update_get(aresponses: ResponsesMockServer) -> None:
    def response_handler(request):
        params = request.query
        assert params["action"] == str(Actions.API_FLASH_ESP.value)
        assert params["fwUrl"]
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text="ok",
        )

    aresponses.add(
        host,
        "/api2",
        "GET",
        response=response_handler,
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        response = await client.fw_update(MOCK_FIRMWARE_ESP)
        assert response


@pytest.mark.asyncio
async def test_zb_firmware_update_get(aresponses: ResponsesMockServer) -> None:
    def response_handler(request):
        params = request.query
        assert params["action"] == str(Actions.API_FLASH_ZB.value)
        assert params["fwUrl"]
        assert params["fwVer"] == "20240315"
        assert params["baud"] == "115200"
        assert params["fwType"] == "0"
        assert params["fwCh"] == "0"
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text="ok",
        )

    aresponses.add(
        host,
        "/api2",
        "GET",
        response=response_handler,
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        response = await client.fw_update(MOCK_FIRMWARE_ZB)
        assert response


@pytest.mark.asyncio
async def test_zb_firmware_update_idx_get(aresponses: ResponsesMockServer) -> None:
    def response_handler(request):
        params = request.query
        assert params["action"] == str(Actions.API_FLASH_ZB.value)
        assert params["fwUrl"]
        assert params["fwVer"] == "20240315"
        assert params["baud"] == "115200"
        assert params["fwType"] == "0"
        assert params["fwCh"] == "0"
        assert params["zbChipIdx"] == "1"
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text="ok",
        )

    aresponses.add(
        host,
        "/api2",
        "GET",
        response=response_handler,
    )
    # info = await client.get_info()
    async with ClientSession() as session:
        client = Api2(host, session=session)
        response = await client.fw_update(MOCK_FIRMWARE_ZB, idx=1)
        assert response


@pytest.mark.asyncio
async def test_zb_old_firmware_update_idx(aresponses: ResponsesMockServer) -> None:
    def response_handler(request):
        params = request.query
        assert params["action"] == str(Actions.API_FLASH_ZB.value)
        assert params["fwUrl"]
        assert params["fwVer"] == "20240315"
        assert params["baud"] == "115200"
        assert params["fwType"] == "0"
        assert params["fwCh"] == "0"
        assert params["zbChipNum"] == "5"
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text="ok",
        )

    aresponses.add(
        host,
        "/api2",
        "GET",
        response=response_handler,
    )
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
        info = await client.get_info()
        assert info.sw_version == "v2.5.2"
        response = await client.fw_update(MOCK_FIRMWARE_ZB, idx=1)
        assert response


async def test_format_release_notes() -> None:
    """Test formatting release notes."""
    async with ClientSession() as session:
        client = Api2(host, session=session)
        firmware = MOCK_FIRMWARE_ESP
        formatted = client.format_notes(firmware)
        assert formatted
        assert (
            formatted
            == "CHANGELOG v2.5.2\n\n* Fixed bug with the lights\n* More fixes\n"
        )

        firmware = MOCK_FIRMWARE_ZB
        formatted = client.format_notes(firmware)
        assert formatted is None


async def test_info_get_firmware_zb(aresponses: ResponsesMockServer) -> None:
    aresponses.add(
        "updates.smlight.tech",
        "/services/api/slzb-06x-ota.php",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-zb-fw.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        fw = await client.get_firmware_version("dev", device="SLZB-06M", mode="zigbee")
        assert fw
        assert len(fw) == 5
        firmware = fw[0]
        assert firmware.link
        assert firmware.mode == "ZB"
        assert firmware.dev is True
        assert firmware.ver == "20240510"
        assert firmware.type == 0


async def test_info_get_firmware_zb_filtered(aresponses: ResponsesMockServer) -> None:
    aresponses.add(
        "updates.smlight.tech",
        "/services/api/slzb-06x-ota.php",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-zb-fw.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        fw = await client.get_firmware_version(
            "dev", device="SLZB-06M", mode="zigbee", zb_type=0
        )
        assert fw
        assert len(fw) == 3
        firmware = fw[0]
        assert firmware.link
        assert firmware.mode == "ZB"
        assert firmware.dev is True
        assert firmware.ver == "20240510"
        assert firmware.type == 0


async def test_info_get_firmware_zb2(aresponses: ResponsesMockServer) -> None:
    """Test getting ZB firmware information for second radio."""
    aresponses.add(
        "updates.smlight.tech",
        "/services/api/slzb-06x-ota.php",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-zb-fw.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        fw = await client.get_firmware_version(
            "dev", device="SLZB-MR1", mode="zigbee", idx=1
        )
        assert fw
        assert len(fw) == 9
        firmware = fw[0]
        assert firmware.link
        assert firmware.mode == "ZB"
        assert firmware.dev is True
        assert firmware.ver == "20240716"
        assert firmware.type == 0


async def test_info_get_firmware_esp(aresponses: ResponsesMockServer) -> None:
    aresponses.add(
        "updates.smlight.tech",
        "/services/api/slzb-06x-ota.php",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-esp-fw.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        fw = await client.get_firmware_version("release", mode="esp32")
        assert fw
        firmware = fw[0]
        assert len(firmware.link) > 20
        assert firmware.mode == "ESP"
        assert firmware.dev is False
        assert firmware.rev == "20240229"
        assert firmware.ver == "v2.0.18"
        assert firmware.type is None
        assert firmware.notes
        assert len(firmware.notes.split("\n")) == 5


async def test_info_get_firmware_espu(aresponses: ResponsesMockServer) -> None:
    aresponses.add(
        "updates.smlight.tech",
        "/services/api/slzb-06x-ota.php",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06U-esp-fw.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        fw = await client.get_firmware_version(
            "release", device="SLZB-MR1U", mode="esp32"
        )
        assert fw
        firmware = fw[0]
        assert len(firmware.link) > 20
        assert firmware.mode == "ESPs3"
        assert firmware.dev is False
        assert firmware.rev == "20250829"
        assert firmware.ver == "v3.0.0"
        assert firmware.type is None
        assert firmware.notes
        assert len(firmware.notes.split("\n")) == 3
