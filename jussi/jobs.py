# -*- coding: utf-8 -*-
import asyncio
import logging

import aiohttp
import ujson

from jussi.upstream import is_jsonrpc_error_response

logger = logging.getLogger(__name__)


# extracted this method for easier testing and future re-use
async def requester(method='POST', url=None, **kwargs):
    if 'headers' not in kwargs:
        kwargs['headers'] = {'Content-Type': 'application/json'}
    async with aiohttp.request(method, url, **kwargs) as response:
        logger.debug(f'requester: HTTP {method} --> {url}')
        response_text = await response.text()
        logger.debug(f'HTTP {method} {url} <-- HTTP {response.status}')
    if 'json' in kwargs:
        logger.debug('requester: decoding response json')
        return ujson.loads(response_text)
    return response_text


async def get_last_irreversible_block(app=None, delay=3):
    name = 'get_last_irreversible_block'
    scheduler = app.config.scheduler
    logger.debug(
        f'{name}, "last_irreversible_block_num" is {app.config.last_irreversible_block_num}')
    jsonrpc_request = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "get_dynamic_global_properties"
    }
    key = 'steemd.database_api.get_dynamic_global_properties'

    while True:
        # load response
        response = None
        try:
            url = 'https://steemd.steemitdev.com'
            response = await requester('POST', url, json=jsonrpc_request)
            last_irr_block_num = response['result']['last_irreversible_block_num']
            if last_irr_block_num >= app.config.last_irreversible_block_num:
                app.config.last_irreversible_block_num = last_irr_block_num
                logger.debug(
                    f'{name} set "last_irreversible_block_num" to {last_irr_block_num}')
            else:
                logger.warning(
                    f'{name} newer block_num < older block_num, skipping')
        except Exception as e:
            logger.error(f'Unable to update last irreversible block:{e}')

        # cache response
        if response:
            if not is_jsonrpc_error_response(response):
                logger.debug(f'{name} caching response')
                try:
                    caches = app.config.caches
                    futures = [
                        asyncio.ensure_future(
                            cache.set(
                                key,
                                response,
                                ttl=1)) for cache in caches]
                    await asyncio.wait(futures, timeout=3)
                except Exception as e:
                    logger.error(
                        f'Unable to cache last irreversible block:{e}')
            else:
                logger.debug(f'{name} skipping jsonrpc error {response}')
        else:
            logger.info(f'{name} skipping missing response')

        if not scheduler.closed:
            await asyncio.sleep(delay)
            logger.debug(f'{name} is scheduled to run in {delay} seconds')
            logger.debug(
                f'scheduler active:{scheduler.active_count} pending:{scheduler.pending_count}')
        else:
            break
    logger.debug(f'ending job {name}')


async def flush_stats(app=None, delay=5):
    name = 'flush_stats'
    scheduler = app.config.scheduler
    while True:
        try:
            client = app.config.statsd_client
            qclient = app.config.stats
            with client.pipeline() as pipe:
                qclient.add_stats_to_pipeline(pipe)
            logger.debug('flush_stats pipe.send() if necessary')
        except Exception as e:
            logger.exception(f'flush_stats ERROR: {e}', exc_info=True)

        if not scheduler.closed:
            await asyncio.sleep(delay)
            logger.debug(f'{name} is scheduled to run in {delay} seconds')
            logger.debug(
                f'scheduler active:{scheduler.active_count} pending:{scheduler.pending_count}')
        else:
            break
    logger.debug(f'ending job {name}')
