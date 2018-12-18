# -*- coding: utf-8 -*-
import asyncio
from time import perf_counter as perf


import structlog

from async_timeout import timeout
from sanic import response
from ujson import loads

from ..cache.cache_group import UncacheableResponse
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..utils import async_nowait_middleware

logger = structlog.get_logger(__name__)


async def get_response(request: HTTPRequest) -> None:
    # return cached response from cache if all requests were in cache
    if not request.jsonrpc:
        return

    request.timings.append((perf(), 'get_cached_response.enter'))
    cache_group = request.app.config.cache_group
    cache_read_timeout = request.app.config.cache_read_timeout

    try:
        cached_response = None
        async with timeout(cache_read_timeout):
            if request.is_single_jrpc:
                cached_response_future =  \
                    cache_group.get_single_jsonrpc_response(request.jsonrpc)
            elif request.is_batch_jrpc:
                cached_response_future = \
                    cache_group.get_batch_jsonrpc_responses(request.jsonrpc)
            else:
                request.timings.append((perf(), 'get_cached_response.exit'))
                return

            cached_response = await cached_response_future
        request.timings.append((perf(), 'get_cached_response.response'))

        if cached_response and \
                cache_group.is_complete_response(request.jsonrpc, cached_response):
            jussi_cache_key = cache_group.x_jussi_cache_key(request.jsonrpc)
            request.timings.append((perf(), 'get_cached_response.exit'))
            return response.json(cached_response,
                                 headers={'x-jussi-cache-hit': jussi_cache_key})

    except ConnectionRefusedError as e:
        logger.error('error connecting to redis cache', e=e)
    except asyncio.TimeoutError:
        logger.error('cache read timeout',
                     timeout=cache_read_timeout,
                     request_id=request.jussi_request_id)
    except Exception as e:
        logger.error('error querying cache for response', e=e, exc_info=e)
    request.timings.append((perf(), 'get_cached_response.exit'))


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

    except UncacheableResponse:
        pass
    except Exception as e:
        logger.error('error caching response', e=e, exc_info=e)
