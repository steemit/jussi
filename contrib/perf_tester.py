# -*- coding: utf-8 -*-
# pylint: skip-file
import asyncio
import concurrent.futures
import logging
import time
import ujson
from itertools import islice

import aiohttp
import uvloop


asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
loop = asyncio.get_event_loop()
loop.set_debug(False)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch(session, url, body):
    async with session.post(url, data=body) as response:
        return await response.read()


async def main(loop, url, count):
    connector = aiohttp.TCPConnector(keepalive_timeout=60, limit=count)
    bodies = [
        f'{{"id":{i},"jsonrpc":"2.0","method":"condenser_api.get_accounts","params":[["layz3r"]]}}' for i in range(count)]
    [b.encode() for b in bodies]
    async with aiohttp.ClientSession(loop=loop, connector=connector, skip_auto_headers=['User-Agent'], headers={'Content-Type': 'application/json'}) as session:
        futures = [fetch(session, url, body) for body in bodies]
        _ = await asyncio.gather(*futures, return_exceptions=False)
        futures = [fetch(session, url, body) for body in bodies]
        start = time.perf_counter()
        results = await asyncio.gather(*futures, return_exceptions=False)
        elapsed = time.perf_counter() - start

    json_results = [ujson.loads(r) for r in results]
    error_results = [r for r in json_results if 'result' not in r]
    print(f'{error_results}')
    print(
        f'result count:{len(results)}, errors:{len(error_results)} elapsed:{elapsed} rps:{count/elapsed}')

if __name__ == '__main__':
    import sys
    import argparse

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('async_http_client_main')

    parser = argparse.ArgumentParser('jussi client')
    parser.add_argument('--url', type=str,
                        default='https://api.steemitdev.com')

    parser.add_argument('--count', type=int, default=1000)
    args = parser.parse_args()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main(loop, args.url, args.count))
    except KeyboardInterrupt:
        logger.debug('main kbi')
    finally:
        for task in asyncio.Task.all_tasks():
            task.cancel()
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(loop.shutdown_asyncgens())
