# -*- coding: utf-8 -*-
import asyncio
import logging
from concurrent.futures._base import CancelledError

logger = logging.getLogger('sanic')


async def get_last_irreversible_block(app=None, block_interval=3):
    logger.debug(
        'get_last_irreversible_block job starting, "last_irreversible_block_num" is %s',
        app.config.last_irreversible_block_num)

    jsonrpc_request = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "get_dynamic_global_properties"
    }

    while True:
        try:
            url = 'http://localhost:%s' % app.config.args.server_port
            session = app.config.aiohttp['session']
            async with session.post(url, json=jsonrpc_request) as resp:

                json_response = await resp.json()
                logger.debug('get_last_irreversible_block json_response:%s', json_response)
            last_irreversible_block_num = json_response['result']['last_irreversible_block_num']
            if isinstance(last_irreversible_block_num, int):
                app.config.last_irreversible_block_num = last_irreversible_block_num
            logger.debug(
                'get_last_irreversible_block set "last_irreversible_block_num" to %s',
                app.config.last_irreversible_block_num)
        except CancelledError:
            logger.debug('get_last_irreversible_block ignored CancelledError')
        except Exception as e:
            logger.exception(e)
        logger.debug('get_last_irreversible_block is sleeping for %s',
                     block_interval)

        await asyncio.sleep(block_interval)



async def flush_stats(app=None, flush_interval=5):
    while True:
        try:
            client = app.config.statsd_client
            qclient = app.config.stats
            with client.pipeline() as pipe:
                pipe = qclient.add_stats_to_pipeline(pipe)
            logger.debug('flush_stats pipe.send() if necessary')
        except Exception as e:
            logger.exception('flush_stats ERROR: %s',e, exc_info=True)
        logger.debug('flush_stats sleeping for %s', flush_interval)
        await asyncio.sleep(flush_interval)
