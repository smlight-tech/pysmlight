""" Tests for retrieving device information from SLZB-06x devices. """
import json

from aiohttp import ClientSession
from aresponses import ResponsesMockServer

from pysmlight import Api2, Info

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
        assert info.sw_version == "v2.0.20"
        assert info.zb_hw == "CC2674P10"
        assert info.zb_version == 20240315
        assert info.zb_type == 0


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
        assert info.fw_channel == "stable"
        assert info.MAC == "DD:88:FC:AA:EE:FF"
        assert info.model == "SLZB-06p10"
        assert info.sw_version == "v2.0.20"
        assert info.zb_hw == "CC2674P10"
        assert info.zb_version == 20240315
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
        assert info.MAC == "DD:88:FC:AA:EE:FF"
        assert info.model == "SLZB-06"
        assert info.sw_version == "0.9.9"
        assert info.legacy_api == 2


async def test_info_get_firmware_zb(aresponses: ResponsesMockServer) -> None:
    aresponses.add(
        "smlight.tech",
        "/flasher/firmware/bin/slzb06x/ota_dev.php",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-zb-fw.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        fw = await client.get_firmware_version("SLZB-06M", "ZB")
        assert fw
        firmware = fw[0]
        assert len(firmware.link) > 20
        assert firmware.mode == "ZB"
        assert firmware.dev is False
        assert firmware.rev == "20231030"
        assert firmware.type == 0


async def test_info_get_firmware_esp(aresponses: ResponsesMockServer) -> None:
    aresponses.add(
        "smlight.tech",
        "/flasher/firmware/bin/slzb06x/ota.php",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("slzb-06-esp-fw.json"),
        ),
    )
    async with ClientSession() as session:
        client = Api2(host, session=session)
        fw = await client.get_firmware_version(mode="ESP")
        assert fw
        firmware = fw[0]
        assert len(firmware.link) > 20
        assert firmware.mode == "ESP"
        assert firmware.dev is False
        assert firmware.rev == "20240229"
        assert firmware.ver == "v2.0.18"
        assert firmware.type is None
