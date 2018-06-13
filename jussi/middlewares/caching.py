# -*- coding: utf-8 -*-
from time import perf_counter
from ujson import loads

import asyncio
import structlog
from async_timeout import timeout
from sanic import response

from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..utils import async_nowait_middleware

logger = structlog.get_logger(__name__)


async def get_response(request: HTTPRequest) -> None:
    # return cached response from cache if all requests were in cache
    if not request.jsonrpc:
        request.timings['get_cached_response.exit'] = perf_counter()
        return
    request.timings['get_cached_response.enter'] = perf_counter()
    cache_group = request.app.config.cache_group
    cache_read_timeout = request.app.config.cache_read_timeout
    try:
        async with timeout(cache_read_timeout):
            request.timings['get_cached_response.await'] = perf_counter()
            cached_response = await cache_group.get_jsonrpc_response(request.jsonrpc)
            request.timings['get_cached_response.await_return'] = perf_counter()
            if cache_group.is_complete_response(request.jsonrpc, cached_response):
                jussi_cache_key = cache_group.x_jussi_cache_key(request.jsonrpc)
                request.timings['get_cached_response.exit'] = perf_counter()
                return response.json(
                    cached_response, headers={'x-jussi-cache-hit': jussi_cache_key})
    except ConnectionRefusedError as e:
        logger.error('error connecting to redis cache', e=e)
    except asyncio.TimeoutError:
        logger.info('cache read timeout',
                    timeout=cache_read_timeout,
                    request_id=request.jussi_request_id)
    except Exception as e:
        logger.error('error querying cache for response', e=e)
    request.timings['get_cached_response.exit'] = perf_counter()


@async_nowait_middleware
async def cache_response(request: HTTPRequest, response: HTTPResponse) -> None:
    try:
        if 'x-jussi-cache-hit' in response.headers or not request.jsonrpc or not response.body:
            return
        if 'x-jussi-error-id' in response.headers:
            return
        jsonrpc_response = loads(response.body)
        if not jsonrpc_response:
            return
        cache_group = request.app.config.cache_group
        last_irreversible_block_num = request.app.config.last_irreversible_block_num
        if request.is_single_jrpc:
            await cache_group.cache_single_jsonrpc_response(request=request.jsonrpc,
                                                            response=jsonrpc_response,
                                                            last_irreversible_block_num=last_irreversible_block_num)
        elif request.is_batch_jrpc:
            await cache_group.cache_batch_jsonrpc_response(requests=request.jsonrpc,
                                                           responses=jsonrpc_response,
                                                           last_irreversible_block_num=last_irreversible_block_num)

    except Exception as e:
        logger.error('error caching response', e=e)
