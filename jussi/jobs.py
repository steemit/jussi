# -*- coding: utf-8 -*-
import asyncio
import logging

from jussi.handlers import fetch_ws
from jussi.utils import DummyRequest

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
            request = DummyRequest(
                app=app, json=jsonrpc_request)  # required for proper caching
            response = await fetch_ws(
                sanic_http_request=request, jsonrpc_request=jsonrpc_request)
            app.config.last_irreversible_block_num = response['result'][
                'last_irreversible_block_num']
            logger.debug(
                'get_last_irreversible_block set "last_irreversible_block_num" to %s',
                app.config.last_irreversible_block_num)
        except Exception as e:
            logger.exception(e)
        logger.debug('get_last_irreversible_block is sleeping for %s',
                     block_interval)
        await asyncio.sleep(block_interval)
