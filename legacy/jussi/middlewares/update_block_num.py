# -*- coding: utf-8 -*-
import asyncio
from time import perf_counter

import structlog
import ujson

from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..utils import async_nowait_middleware
from ..validators import is_get_dynamic_global_properties_request

logger = structlog.get_logger(__name__)


@async_nowait_middleware
async def update_last_irreversible_block_num(request: HTTPRequest, response: HTTPResponse) -> None:
    if not request.is_single_jrpc or 'x-jussi-error-id' in response.headers:
        return
    request.timings.append((perf_counter(), 'update_last_irreversible_block_num.enter'))
    try:
        jsonrpc_response = ujson.loads(response.body)
        if is_get_dynamic_global_properties_request(request.jsonrpc):
            last_irreversible_block_num = jsonrpc_response['result']['last_irreversible_block_num']
            cache_group = request.app.config.cache_group
            request.app.config.last_irreversible_block_num = last_irreversible_block_num
            await asyncio.shield(cache_group.set('last_irreversible_block_num',
                                                 last_irreversible_block_num,
                                                 expire_time=180))
    except Exception as e:
        logger.error('skipping update of last_irreversible_block_num',
                     request=request.jussi_request_id,
                     e=e, response_body=response.body)
        request.timings.append((perf_counter(), 'update_last_irreversible_block_num.exit'))
