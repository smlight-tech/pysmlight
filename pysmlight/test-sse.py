import asyncio
import logging
import time

import aiohttp

from .web import Api2

_LOGGER = logging.getLogger(__name__)

start = time.time()


async def main():
    logging.basicConfig(level=logging.DEBUG)
    master_session = aiohttp.ClientSession()
    host = secrets.host
    client = Api2(host, session=master_session)
    # client.sse.register_callback(
    # Events.EVENT_INET_STATE, lambda x: _LOGGER.info(x.type))
    client.sse.register_callback(None, lambda x: _LOGGER.info(x.type))
    asyncio.create_task(client.sse.client())
    cnt = 0
    while True:
        await asyncio.sleep(5)
        cnt += 1
        try:
            if cnt % 4 == 0:
                pass
                # await client.get_param('inetState')
        except asyncio.TimeoutError:
            print(f"run time: {time.time() - start}")

        print(time.time() - start)


if __name__ == "__main__":
    import secrets

    asyncio.run(main())
