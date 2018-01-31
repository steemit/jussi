# -*- coding: utf-8 -*-
import asyncio
import logging

from sanic import response

import ujson

from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..utils import async_include_methods
from ..utils import async_nowait_middleware

logger = logging.getLogger(__name__)


@async_include_methods(include_http_methods=('POST',))
async def get_response(request: HTTPRequest) -> None:
    # return cached response from cache if all requests were in cache
    cache_group = request.app.config.cache_group
    jsonrpc_request = request.json
    try:
        cached_response = await cache_group.get_jsonrpc_response(jsonrpc_request)
        if cache_group.is_complete_response(jsonrpc_request, cached_response):
            jussi_cache_key = cache_group.x_jussi_cache_key(jsonrpc_request)
            return response.json(
                cached_response, headers={'x-jussi-cache-hit': jussi_cache_key})
    except ConnectionRefusedError:
        logger.error('error connecting to redis cache')
    except Exception:
        logger.exception('error while querying cache for response')


@async_nowait_middleware
@async_include_methods(include_http_methods=('POST',))
async def cache_response(request: HTTPRequest, response: HTTPResponse) -> None:
    try:
        if 'x-jussi-cache-hit' in response.headers:
            return
        cache_group = request.app.config.cache_group
        jsonrpc_request = request.json
        jsonrpc_response = ujson.loads(response.body)
        last_irreversible_block_num = request.app.config.last_irreversible_block_num or 15_000_000
        asyncio.shield(cache_group.cache_jsonrpc_response(jsonrpc_request,
                                                          jsonrpc_response,
                                                          last_irreversible_block_num))
    except Exception as e:
        logger.error('error caching response: %s', e)
