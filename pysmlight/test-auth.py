
from .exceptions import SmlightAuthError, SmlightConnectionError
from .web import Api2
import aiohttp
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

async def validate_auth(client: Api2):
    try:
        if await client.check_auth_needed():
            _LOGGER.info("Auth needed")
            await client.authenticate(secrets.apiuser, secrets.apipass)
    except SmlightConnectionError as err:
        _LOGGER.error("Connection error")
    except SmlightAuthError as err:
        _LOGGER.error("Authentication error")

async def main():
    master_session = aiohttp.ClientSession()
    client = Api2(secrets.host, session=master_session)
    
    await validate_auth(client)
    _LOGGER.info("Authenticated")
    # info_old = await client.get_info_old()
    info = await client.get_info()
    _LOGGER.info(f"Model: {info.model} MAC: {info.MAC}")
    # sensor = await client.get_sensors()
    # _LOGGER.info(sensor)
    # master_session.close()
    # fw = await client.get_firmware_version("SLZB-06p10", "ZB")
    fw = await client.get_firmware_version(None, "ESP")
    _LOGGER.info(fw)
    await client.close()

if __name__ == '__main__':
    from . import secrets
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())