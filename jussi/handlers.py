# -*- coding: utf-8 -*-

import asyncio
import datetime
import logging

import async_timeout
import ujson
from sanic import response

from .typedefs import BatchJsonRpcRequest
from .typedefs import BatchJsonRpcResponse
from .typedefs import HTTPRequest
from .typedefs import HTTPResponse
from .typedefs import JsonRpcRequest
from .typedefs import SingleJsonRpcRequest
from .typedefs import SingleJsonRpcResponse
from .upstream import is_batch_jsonrpc
from .upstream import upstream_url_from_jsonrpc_request
from .validators import validate_response

# pylint: disable=unused-import


# pylint: enable=unused-import

logger = logging.getLogger(__name__)

# path /


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
        'datetime': datetime.datetime.utcnow().isoformat(),
        'source_commit': sanic_http_request.app.config.args.source_commit
    })


@validate_response
async def fetch_ws(sanic_http_request: HTTPRequest,
                   jsonrpc_request: SingleJsonRpcRequest
                   ) -> SingleJsonRpcResponse:
    pool = sanic_http_request.app.config.websocket_pool
    conn = await pool.acquire()
    with async_timeout.timeout(2):
        try:
            await conn.send(ujson.dumps(jsonrpc_request).encode())
            return ujson.loads(await conn.recv())
        finally:
            pool.release(conn)

# pylint: enable=unused-argument


@validate_response
async def fetch_http(sanic_http_request: HTTPRequest=None,
                     jsonrpc_request: SingleJsonRpcRequest=None,
                     url: str=None) -> SingleJsonRpcResponse:
    session = sanic_http_request.app.config.aiohttp['session']
    with async_timeout.timeout(2):
        async with session.post(url, json=jsonrpc_request) as resp:
            json_response = await resp.json()
        return json_response


async def dispatch_single(sanic_http_request: HTTPRequest,
                          jsonrpc_request: SingleJsonRpcRequest) -> SingleJsonRpcResponse:
    url = upstream_url_from_jsonrpc_request(
        sanic_http_request.app.config.upstream_urls, jsonrpc_request)
    # pylint: disable=unexpected-keyword-arg
    if url.startswith('ws'):
        json_response = await fetch_ws(
            sanic_http_request,
            jsonrpc_request)
    else:
        json_response = await fetch_http(
            sanic_http_request,
            jsonrpc_request,
            url)
    return json_response


async def dispatch_batch(sanic_http_request: HTTPRequest,
                         jsonrpc_requests: BatchJsonRpcRequest
                         ) -> BatchJsonRpcResponse:
    requests = [dispatch_single(sanic_http_request, request)
                for request in jsonrpc_requests]
    return await asyncio.gather(*requests)
