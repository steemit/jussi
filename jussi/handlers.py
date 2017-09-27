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
from .typedefs import SingleJsonRpcRequest
from .typedefs import SingleJsonRpcResponse
from .utils import async_retry
from .utils import is_batch_jsonrpc
from .utils import chunkify
from .upstream.url import url_from_jsonrpc_request
from .validators import validate_response_decorator


logger = logging.getLogger(__name__)


async def jussi_get_blocks(sanic_http_request: HTTPRequest) -> HTTPResponse:
    # retreive parsed jsonrpc_requests after request middleware processing
    app = sanic_http_request.app
    cache_group = app.config.cache_group
    jsonrpc_request = sanic_http_request.json  # type: JsonRpcRequest
    start_block = jsonrpc_request['params'].get('start_block', 1)
    end_block = jsonrpc_request['params'].get('end_block', 15_000_000)
    block_nums = range(start_block, end_block)
    requests = ({'id': block_num,
                 'jsonrpc': '2.0',
                 'method': 'get_block',
                 'params': [block_num]} for block_num in block_nums)
    batched_requests = chunkify(requests, 10)
    jsonrpc_response = {
        'id': jsonrpc_request.get('id'),
        'jsonrpc': '2.0',
        'result': []}
    for batch_request in batched_requests:

        cached_response = await cache_group.get_jsonrpc_response(
            batch_request)
        if cache_group.is_complete_response(batch_request, cached_response):
            for jrpc_response in cached_response:
                jsonrpc_response['result'].append(jrpc_response['result'])
            continue

        batch_response = await dispatch_batch(sanic_http_request, batch_request)

        for jrpc_response in batch_response:
            jsonrpc_response['result'].append(jrpc_response['result'])

    return response.json(jsonrpc_response)


# path /
async def handle_jsonrpc(sanic_http_request: HTTPRequest) -> HTTPResponse:
    # retreive parsed jsonrpc_requests after request middleware processing
    jsonrpc_requests = sanic_http_request.json  # type: JsonRpcRequest

    # make upstream requests

    if is_batch_jsonrpc(sanic_http_request=sanic_http_request):
        jsonrpc_response = await dispatch_batch(sanic_http_request,
                                                jsonrpc_requests)
    elif sanic_http_request.json['method'] == 'jussi.get_blocks':
        return await jussi_get_blocks(sanic_http_request)
    else:
        jsonrpc_response = await dispatch_single(sanic_http_request,
                                                 jsonrpc_requests)

    return response.json(jsonrpc_response)


async def healthcheck(sanic_http_request: HTTPRequest) -> HTTPResponse:
    return response.json({
        'status': 'OK',
        'datetime': datetime.datetime.utcnow().isoformat(),
        'source_commit': sanic_http_request.app.config.args.source_commit,
        'docker_tag': sanic_http_request.app.config.args.docker_tag
    })

# pylint: disable=no-value-for-parameter


@async_retry(tries=3)
@validate_response_decorator
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


@async_retry(tries=3)
@validate_response_decorator
async def fetch_http(sanic_http_request: HTTPRequest=None,
                     jsonrpc_request: SingleJsonRpcRequest=None,
                     url: str=None) -> SingleJsonRpcResponse:
    session = sanic_http_request.app.config.aiohttp['session']
    with async_timeout.timeout(2):
        async with session.post(url, json=jsonrpc_request) as resp:
            json_response = await resp.json()
        return json_response
# pylint: enable=no-value-for-parameter


async def dispatch_single(sanic_http_request: HTTPRequest,
                          jsonrpc_request: SingleJsonRpcRequest) -> SingleJsonRpcResponse:
    url = url_from_jsonrpc_request(
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
