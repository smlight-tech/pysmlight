"""Tests for firmware catalog requests and response parsing."""

from unittest.mock import patch

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectionError
from aresponses import ResponsesMockServer
import pytest

from pysmlight.catalog import FirmwareCatalog, FwChannel
from pysmlight.exceptions import SmlightConnectionError
from pysmlight.models import Firmware

from . import load_fixture

FW_HOST = "updates.smlight.tech"
FW_PATH = "/services/api/slzb-06x-ota.php"


def test_determine_firmware_type() -> None:
    assert FirmwareCatalog.determine_firmware_type("zigbee") == "ZB"
    assert FirmwareCatalog.determine_firmware_type("esp32") == "ESP"
    assert FirmwareCatalog.determine_firmware_type("esp32", "SLZB-06") == "ESP"
    assert FirmwareCatalog.determine_firmware_type("esp32", "SLZB-06U") == "ESPs3"
    assert FirmwareCatalog.determine_firmware_type("esp32", "SLZB-Ultima4") == "ESPs3"
    assert FirmwareCatalog.determine_firmware_type("esp32", u_device=True) == "ESPs3"


def test_format_release_notes() -> None:
    firmware = Firmware(
        ver="v2.5.2",
        mode="ESP",
        notes="CHANGELOG v2.5.2\r\nFixed bug with the lights\nMore fixes",
    )
    assert FirmwareCatalog.format_release_notes(firmware) == (
        "CHANGELOG v2.5.2\n\n* Fixed bug with the lights\n* More fixes\n"
    )
    assert FirmwareCatalog.format_release_notes(Firmware(mode="ZB")) is None
    assert (
        FirmwareCatalog.format_release_notes(
            Firmware(rev="20240510", mode="ZB", dev=True, notes="New features")
        )
        == "Dev firmware.\n\nNew features\n\n"
    )


@pytest.mark.parametrize(
    ("channel", "expected_count"),
    [("release", 1), ("dev", 1), ("any", 2), (None, 2)],
)
def test_parse_esp_channels(channel: FwChannel | None, expected_count: int) -> None:
    firmware = FirmwareCatalog().parse_firmware(
        [{"ver": "v2.0.0", "dev": False}, {"ver": "v2.1.0.dev1", "dev": True}],
        "ESP",
        channel,
        None,
    )
    assert len(firmware) == expected_count


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("u_device", "fixture", "channel", "expected_count", "fw_type"),
    [
        (False, "slzb-06-esp-fw.json", "release", 3, "ESP"),
        (False, "slzb-06-esp-fw.json", "dev", 0, "ESP"),
        (False, "slzb-06-esp-fw.json", "any", 3, "ESP"),
        (False, "slzb-06-esp-fw.json", None, 3, "ESP"),
        (True, "slzb-06U-esp-fw.json", "release", 3, "ESPs3"),
        (True, "slzb-06U-esp-fw.json", "dev", 0, "ESPs3"),
        (True, "slzb-06U-esp-fw.json", "any", 3, "ESPs3"),
    ],
)
async def test_esp_request_and_channel_filter(
    aresponses: ResponsesMockServer,
    u_device: bool,
    fixture: str,
    channel: FwChannel | None,
    expected_count: int,
    fw_type: str,
) -> None:
    async def handler(request):
        assert request.method == "GET"
        assert dict(request.query) == {"type": fw_type}
        assert not {"device", "idx", "hw", "ch", "curFw"} & request.query.keys()
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture(fixture),
        )

    aresponses.add(FW_HOST, FW_PATH, "GET", handler)
    async with FirmwareCatalog() as catalog:
        firmware = await catalog.get_firmware_version(
            channel,
            device="SLZB-06",
            mode="esp32",
            idx=3,
            hw=171,
            u_device=u_device,
        )
    assert firmware is not None
    assert len(firmware) == expected_count
    assert all(item.mode == fw_type for item in firmware)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("channel", "ch"),
    [("release", "0"), ("dev", "1"), ("any", None), (None, None)],
)
async def test_zigbee_query_channel(
    aresponses: ResponsesMockServer, channel: FwChannel | None, ch: str | None
) -> None:
    async def handler(request):
        expected = {
            "type": "ZB",
            "format": "slzb",
            "device": "27",
            "idx": "1",
            "hw": "171",
        }
        if ch is not None:
            expected["ch"] = ch
        assert request.method == "GET"
        assert dict(request.query) == expected
        assert "curFw" not in request.query
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-zb-fw.json"),
        )

    aresponses.add(FW_HOST, FW_PATH, "GET", handler)
    async with FirmwareCatalog() as catalog:
        firmware = await catalog.get_firmware_version(
            channel, device="SLZB-Ultima3", mode="zigbee", idx=1, hw=171
        )
    assert firmware is not None and len(firmware) == 5


@pytest.mark.asyncio
async def test_zigbee_type_filter_is_client_side(
    aresponses: ResponsesMockServer,
) -> None:
    async def handler(request):
        assert dict(request.query) == {
            "type": "ZB",
            "format": "slzb",
            "device": "27",
            "idx": "0",
        }
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-zb-fw.json"),
        )

    aresponses.add(FW_HOST, FW_PATH, "GET", handler)
    async with FirmwareCatalog() as catalog:
        firmware = await catalog.get_firmware_version(
            "any", device="SLZB-Ultima3", mode="zigbee", zb_type=0
        )
    assert firmware is not None
    assert len(firmware) == 3
    assert {item.type for item in firmware} == {0}


@pytest.mark.asyncio
async def test_zigbee_empty_list_returns_empty(aresponses: ResponsesMockServer) -> None:
    aresponses.add(FW_HOST, FW_PATH, "GET", aresponses.Response(status=200, text="[]"))
    async with FirmwareCatalog() as catalog:
        assert (
            await catalog.get_firmware_version(
                "release", device="SLZB-06M", mode="zigbee"
            )
            == []
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "device", "body"),
    [
        ("zigbee", "SLZB-06M", '{"fw": []}'),
        ("esp32", None, "[]"),
        ("esp32", None, "{}"),
    ],
)
async def test_unexpected_manifest_shape_raises(
    aresponses: ResponsesMockServer, mode: str, device: str | None, body: str
) -> None:
    aresponses.add(FW_HOST, FW_PATH, "GET", aresponses.Response(status=200, text=body))
    async with FirmwareCatalog() as catalog:
        with pytest.raises(SmlightConnectionError, match="Unexpected firmware"):
            await catalog.get_firmware_version("any", mode=mode, device=device)


@pytest.mark.asyncio
async def test_non_200_raises(aresponses: ResponsesMockServer) -> None:
    aresponses.add(FW_HOST, FW_PATH, "GET", aresponses.Response(status=404))
    async with FirmwareCatalog() as catalog:
        with pytest.raises(SmlightConnectionError, match="HTTP error 404"):
            await catalog.get_firmware_version("any")


@pytest.mark.asyncio
async def test_invalid_json_raises(aresponses: ResponsesMockServer) -> None:
    aresponses.add(FW_HOST, FW_PATH, "GET", aresponses.Response(status=200, text="no"))
    async with FirmwareCatalog() as catalog:
        with pytest.raises(SmlightConnectionError, match="Invalid JSON"):
            await catalog.get_firmware_version("any")


@pytest.mark.asyncio
async def test_connection_error_is_wrapped() -> None:
    async with ClientSession() as session:
        catalog = FirmwareCatalog(session=session)
        with patch.object(
            session, "get", side_effect=ClientConnectionError("mocked failure")
        ):
            with pytest.raises(SmlightConnectionError, match="Connection failed"):
                await catalog.get_firmware_version("any")


@pytest.mark.asyncio
@pytest.mark.parametrize("channel", ["beta", "invalid"])
async def test_invalid_channel_raises(channel: str) -> None:
    async with FirmwareCatalog() as catalog:
        with pytest.raises(ValueError, match="Unsupported firmware channel"):
            await catalog.get_firmware_version(channel)


@pytest.mark.asyncio
async def test_zigbee_requires_device() -> None:
    async with FirmwareCatalog() as catalog:
        with pytest.raises(ValueError, match="requires a device model"):
            await catalog.get_firmware_version("any", mode="zigbee")


@pytest.mark.asyncio
async def test_zigbee_unknown_device_raises() -> None:
    async with FirmwareCatalog() as catalog:
        with pytest.raises(ValueError, match="Unknown device model"):
            await catalog.get_firmware_version("any", device="UNKNOWN", mode="zigbee")


@pytest.mark.asyncio
async def test_owned_and_passed_sessions(aresponses: ResponsesMockServer) -> None:
    aresponses.add(
        FW_HOST,
        FW_PATH,
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-esp-fw.json"),
        ),
    )
    async with FirmwareCatalog() as catalog:
        owned_session = catalog.session
        await catalog.get_firmware_version("any")
    assert isinstance(owned_session, ClientSession)
    assert owned_session.closed

    session = ClientSession()
    assert isinstance(session, ClientSession)
    async with FirmwareCatalog(session=session) as catalog:
        assert catalog.session is session
    assert isinstance(session, ClientSession)
    assert not session.closed
    await session.close()
