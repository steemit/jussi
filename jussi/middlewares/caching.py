# -*- coding: utf-8 -*-
import asyncio
import logging

from sanic import response

import ujson

from ..errors import handle_middleware_exceptions
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..utils import async_exclude_methods
from ..utils import async_nowait_middleware

logger = logging.getLogger(__name__)


@handle_middleware_exceptions
@async_exclude_methods(exclude_http_methods=('GET',))
async def get_response(request: HTTPRequest) -> None:
    # return cached response from cache if all requests were in cache
    cache_group = request.app.config.cache_group
    jsonrpc_request = request.json
    cached_response = await cache_group.get_jsonrpc_response(jsonrpc_request)
    if cache_group.is_complete_response(jsonrpc_request, cached_response):
        jussi_cache_key = cache_group.x_jussi_cache_key(jsonrpc_request)
        return response.json(
            cached_response, headers={'x-jussi-cache-hit': jussi_cache_key})


@async_nowait_middleware
async def cache_response(request: HTTPRequest, response: HTTPResponse) -> None:
    try:
        if request.method != 'POST':
            return
        if 'x-jussi-cache-hit' in response.headers:
            return

        cache_group = request.app.config.cache_group
        jsonrpc_request = request.json
        jsonrpc_response = ujson.loads(response.body)
        last_irreversible_block_num = request.app.config.last_irreversible_block_num or 15_000_000
        asyncio.ensure_future(cache_group.cache_jsonrpc_response(jsonrpc_request,
                                                                 jsonrpc_response,
                                                                 last_irreversible_block_num))
    except Exception as e:
        logger.warning('ignoring error while querying cache: %s', e)
