# -*- coding: utf-8 -*-
import asyncio

import structlog

import ujson

from ..request import JussiJSONRPCRequest
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..utils import async_nowait_middleware
from ..validators import is_get_dynamic_global_properties_request

logger = structlog.get_logger(__name__)


@async_nowait_middleware
async def update_last_irreversible_block_num(request: HTTPRequest, response: HTTPResponse) -> None:
    if not isinstance(request.jsonrpc, JussiJSONRPCRequest):
        return
    try:
        jsonrpc_request = request.jsonrpc
        jsonrpc_response = ujson.loads(response.body)
        if is_get_dynamic_global_properties_request(jsonrpc_request):
            last_irreversible_block_num = jsonrpc_response['result']['last_irreversible_block_num']
            cache_group = request.app.config.cache_group
            logger.debug(
                'update_last_irreversible_block_num',
                current=request.app.config.last_irreversible_block_num,
                new=last_irreversible_block_num)

            request.app.config.last_irreversible_block_num = last_irreversible_block_num
            await asyncio.shield(cache_group.set('last_irreversible_block_num',
                                                 last_irreversible_block_num))
            logger.debug(
                'updated last_irreversible_block_num',
                new=last_irreversible_block_num)
    except Exception as e:
        logger.error('skipping update of last_irreversible_block_num',
                     request=request.jussi_request_id)
