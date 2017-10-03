# -*- coding: utf-8 -*-
import logging

from sanic import response

import ujson

from ..errors import handle_middleware_exceptions
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..upstream.urn import urn_parts
from ..utils import async_exclude_methods

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


async def cache_response(request: HTTPRequest, response: HTTPResponse) -> None:
    try:
        if request.method != 'POST':
            return
        if 'x-jussi-cache-hit' in response.headers:
            return
        try:
            parts = urn_parts(request.json)
            if parts.method == 'get_blocks':
                return
        except BaseException:
            pass
        cache_group = request.app.config.cache_group
        jsonrpc_request = request.json
        jsonrpc_response = ujson.loads(response.body)
        last_irreversible_block_num = request.app.config.last_irreversible_block_num or 15_000_000
        await cache_group.cache_jsonrpc_response(jsonrpc_request,
                                                 jsonrpc_response,
                                                 last_irreversible_block_num)
    except Exception as e:
        logger.warning(f'ignoring error while querying cache: {e}')
