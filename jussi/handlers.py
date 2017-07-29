# -*- coding: utf-8 -*-

import asyncio
import datetime
import logging

import funcy
import ujson
import websockets
import websockets.exceptions
from sanic import response

from jussi.cache import cache_get_batch
from jussi.cache import cacher
from jussi.typedefs import BatchJsonRpcRequest
from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse
from jussi.typedefs import JsonRpcRequest
from jussi.utils import is_batch_jsonrpc
from jussi.utils import upstream_url_from_jsonrpc_request

logger = logging.getLogger('sanic')


async def handle_jsonrpc(sanic_http_request: HTTPRequest) -> HTTPResponse:
    # retreive parsed jsonrpc_requests after request middleware processing
    jsonrpc_requests = sanic_http_request.json

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
@funcy.retry(3, errors=[websockets.exceptions.ConnectionClosed,
                        websockets.exceptions.InvalidHandshake], timeout=0)
@cacher
async def fetch_ws(sanic_http_request: HTTPRequest,
                   jsonrpc_request: dict) -> dict:
    ws = sanic_http_request.app.config.websocket_client
    stats = sanic_http_request.app.config.stats
    if not ws or not ws.open:
        logger.info('Reopening closed upstream websocket from fetch_ws')
        ws = await websockets.connect(**sanic_http_request.app.config.websocket_kwargs)
        sanic_http_request.app.config.websocket_client = ws
    await ws.send(ujson.dumps(jsonrpc_request).encode())
    json_response = ujson.loads(await ws.recv())
    stats.incr('upstream.websocket_requests')
    return json_response


# pylint: enable=unused-argument


@funcy.log_calls(logger.debug)
@cacher
async def fetch_http(sanic_http_request: HTTPRequest=None,
                     jsonrpc_request: dict=None,
                     url: str=None) -> dict:
    session = sanic_http_request.app.config.aiohttp['session']

    async with session.post(url, json=jsonrpc_request) as resp:
        json_response = await resp.json()
        return json_response


async def dispatch_single(sanic_http_request: HTTPRequest,
                          jsonrpc_request: dict,
                          skip_cacher_get=False,
                          skip_cacher_set=False) -> dict:

    url = upstream_url_from_jsonrpc_request(
        sanic_http_request.app.config.upstream_urls, jsonrpc_request)
    # pylint: disable=unexpected-keyword-arg
    if url.startswith('ws'):
        json_response = await fetch_ws(sanic_http_request,
                                       jsonrpc_request,
                                       skip_cacher_get=skip_cacher_get,
                                       skip_cacher_set=skip_cacher_set
                                       )
    else:
        json_response = await fetch_http(sanic_http_request,
                                         jsonrpc_request,
                                         url,
                                         skip_cacher_get=skip_cacher_get,
                                         skip_cacher_set=skip_cacher_set)
    return json_response


async def dispatch_batch(sanic_http_request: HTTPRequest,
                         jsonrpc_requests: JsonRpcRequest) -> BatchJsonRpcRequest:
    cached_responses = await cache_get_batch(sanic_http_request.app.config.caches, jsonrpc_requests)
    requests = [dispatch_single(sanic_http_request, jsonrpc_request, skip_cacher_get=True) for i,jsonrpc_request in enumerate(jsonrpc_requests) if not cached_responses[i]]
    fetched_responses = iter(await asyncio.gather(* requests))
    return [response or next(fetched_responses) for response in cached_responses]
