# -*- coding: utf-8 -*-

import asyncio
import datetime
import logging
# pylint: disable=unused-import
from typing import Any
from typing import Awaitable
from typing import List

import funcy
import ujson
import websockets
import websockets.exceptions
from sanic import response

from jussi.cache import cache_get_batch
from jussi.cache import cacher
from jussi.typedefs import BatchJsonRpcRequest
from jussi.typedefs import BatchJsonRpcResponse
from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse
from jussi.typedefs import JsonRpcRequest
from jussi.typedefs import SingleJsonRpcRequest
from jussi.typedefs import SingleJsonRpcResponse
from jussi.utils import is_batch_jsonrpc
from jussi.utils import stats_key
from jussi.utils import upstream_url_from_jsonrpc_request

# pylint: enable=unused-import

logger = logging.getLogger('sanic')


async def handle_jsonrpc(sanic_http_request: HTTPRequest) -> HTTPResponse:
    # retreive parsed jsonrpc_requests after request middleware processing
    jsonrpc_requests = sanic_http_request.json  # type: JsonRpcRequest

    # make upstream requests

    if is_batch_jsonrpc(sanic_http_request=sanic_http_request):
        jsonrpc_response = await dispatch_batch(sanic_http_request,
                                                jsonrpc_requests)

    else:
        jsonrpc_response = await dispatch_single(sanic_http_request,
                                                 jsonrpc_requests)
    return response.json(jsonrpc_response)


# pylint: disable=unused-argument
async def healthcheck(sanic_http_request: HTTPRequest) -> HTTPResponse:
    return response.json({
        'status': 'OK',
        'datetime': datetime.datetime.utcnow().isoformat()
    })


@funcy.log_calls(logger.debug)
@funcy.retry(
    3,
    errors=[
        websockets.exceptions.ConnectionClosed,
        websockets.exceptions.InvalidHandshake
    ],
    timeout=0)
@cacher
async def fetch_ws(sanic_http_request: HTTPRequest,
                   jsonrpc_request: SingleJsonRpcRequest
                   ) -> SingleJsonRpcResponse:
    ws = sanic_http_request.app.config.websocket_client
    stats = sanic_http_request.app.config.stats
    key = stats_key(jsonrpc_request)
    timer = stats.timer(f'jsonrpc.requests.{key}')
    timer.start()
    if not ws or not ws.open:
        logger.info('Reopening closed upstream websocket from fetch_ws')
        ws = await websockets.connect(
            **sanic_http_request.app.config.websocket_kwargs)
        sanic_http_request.app.config.websocket_client = ws
    await ws.send(ujson.dumps(jsonrpc_request).encode())
    json_response = ujson.loads(await ws.recv())
    timer.stop()
    return json_response


# pylint: enable=unused-argument


@funcy.log_calls(logger.debug)
@cacher
async def fetch_http(sanic_http_request: HTTPRequest=None,
                     jsonrpc_request: SingleJsonRpcRequest=None,
                     url: str=None) -> SingleJsonRpcResponse:
    session = sanic_http_request.app.config.aiohttp['session']

    async with session.post(url, json=jsonrpc_request) as resp:
        json_response = await resp.json()
        return json_response


async def dispatch_single(sanic_http_request: HTTPRequest,
                          jsonrpc_request: SingleJsonRpcRequest,
                          skip_cacher_get=False,
                          skip_cacher_set=False) -> SingleJsonRpcResponse:

    url = upstream_url_from_jsonrpc_request(
        sanic_http_request.app.config.upstream_urls, jsonrpc_request)
    # pylint: disable=unexpected-keyword-arg
    if url.startswith('ws'):
        json_response = await fetch_ws(
            sanic_http_request,
            jsonrpc_request,
            skip_cacher_get=skip_cacher_get,
            skip_cacher_set=skip_cacher_set)
    else:
        json_response = await fetch_http(
            sanic_http_request,
            jsonrpc_request,
            url,
            skip_cacher_get=skip_cacher_get,
            skip_cacher_set=skip_cacher_set)
    return json_response


async def dispatch_batch(sanic_http_request: HTTPRequest,
                         jsonrpc_requests: BatchJsonRpcRequest
                         ) -> BatchJsonRpcResponse:
    cached_responses = sanic_http_request.get('cached_response')
    if not cached_responses:
        logger.warning(
            'dispatch_batch encountered batch request with no cached_response attr')
        cached_responses = cache_get_batch(
            sanic_http_request.app.config.caches, jsonrpc_requests)
    requests = [
        dispatch_single(
            sanic_http_request, jsonrpc_request, skip_cacher_get=True)
        for i, jsonrpc_request in enumerate(jsonrpc_requests)
        if not cached_responses[i]
    ]  # type: List[Awaitable[Any]]
    fetched_responses = iter(await asyncio.gather(*requests))
    return [
        response or next(fetched_responses) for response in cached_responses
    ]
