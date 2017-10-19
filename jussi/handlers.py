# -*- coding: utf-8 -*-

import asyncio
import datetime
import logging
import random

import async_timeout
from sanic import response

import ujson

from .errors import UpstreamResponseError
from .typedefs import BatchJsonRpcRequest
from .typedefs import BatchJsonRpcResponse
from .typedefs import HTTPRequest
from .typedefs import HTTPResponse
from .typedefs import SingleJsonRpcRequest
from .typedefs import SingleJsonRpcResponse
from .upstream.url import url_from_jsonrpc_request
from .upstream.urn import urn as get_urn
from .utils import async_retry
from .utils import chunkify
from .utils import is_batch_jsonrpc
from .utils import update_last_irreversible_block_num

logger = logging.getLogger(__name__)
request_logger = logging.getLogger('jussi_upstream')


async def jussi_get_blocks(sanic_http_request: HTTPRequest) -> HTTPResponse:
    # retreive parsed jsonrpc_requests after request middleware processing
    app = sanic_http_request.app
    cache_group = app.config.cache_group
    jsonrpc_request = sanic_http_request.json  # type: JsonRpcRequest
    start_block = jsonrpc_request['params'].get('start_block', 1)
    end_block = jsonrpc_request['params'].get('end_block', 15_000_000)
    block_nums = range(start_block, end_block)
    requests = ({
        'id': block_num,
        'jsonrpc': '2.0',
        'method': 'get_block',
        'params': [block_num]
    } for block_num in block_nums)
    batched_requests = chunkify(requests, 10)
    jsonrpc_response = {
        'id': jsonrpc_request.get('id'),
        'jsonrpc': '2.0',
        'result': []
    }
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
@update_last_irreversible_block_num
async def fetch_ws(sanic_http_request: HTTPRequest,
                   jsonrpc_request: SingleJsonRpcRequest
                   ) -> SingleJsonRpcResponse:
    pool = sanic_http_request.app.config.websocket_pool
    jussi_request_id = sanic_http_request.headers.get('x-jussi-request-id')

    upstream_request = {k: jsonrpc_request[k] for k in
                        {'jsonrpc', 'method', 'params'} if k in jsonrpc_request}
    upstream_request['id'] = random.getrandbits(32)

    urn = get_urn(upstream_request)
    timeout = sanic_http_request.app.config.timeout_from_request(upstream_request)
    conn = await pool.acquire()
    with async_timeout.timeout(timeout):
        try:
            upstream_request_json = ujson.dumps(upstream_request,
                                                ensure_ascii=False).encode()
            await conn.send(upstream_request_json)
            upstream_response_json = await conn.recv()
            upstream_response = ujson.loads(upstream_response_json)

            request_logger.debug(dict(jussi_request_id=jussi_request_id,
                                      jsonrpc_request_id=jsonrpc_request.get('id'),
                                      conn_id=id(conn),
                                      urn=urn,
                                      timeout=timeout,
                                      upstream_request=upstream_request,
                                      upstream_response=upstream_response))

            assert upstream_response.get('id') == upstream_request['id'], \
                f'{upstream_response.get("id")} should be {upstream_request["id"]}'

            del upstream_response['id']
            if 'id' in jsonrpc_request:
                upstream_response['id'] = jsonrpc_request['id']
            return upstream_response

        except AssertionError as e:
            error_info = dict(jussi_request_id=jussi_request_id,
                              jsonrpc_request_id=jsonrpc_request.get('id'),
                              pool_info=pool.get_pool_info(),
                              conn_id=id(conn),
                              upstream_request=upstream_request)
            try:
                error_info['upstream_response'] = upstream_response
            except NameError:
                pass
            logger.error(error_info)
            await pool.terminate_connection(conn)
            raise UpstreamResponseError(sanic_request=sanic_http_request,
                                        exception=e)
        except Exception as e:
            logger.error(f'fetch_ws failed: {e}')
            await pool.terminate_connection(conn)
            raise e
        finally:
            await pool.release(conn)


@async_retry(tries=3)
@update_last_irreversible_block_num
async def fetch_http(sanic_http_request: HTTPRequest = None,
                     jsonrpc_request: SingleJsonRpcRequest = None,
                     url: str = None) -> SingleJsonRpcResponse:

    session = sanic_http_request.app.config.aiohttp['session']
    args = sanic_http_request.app.config.args
    headers = {}
    headers['x-amzn-trace_id'] = sanic_http_request.headers.get('x-amzn-trace-id')
    headers['x-jussi-request-id'] = sanic_http_request.headers.get('x-jussi-request-id')

    upstream_request = {k: jsonrpc_request[k] for k in
                        {'jsonrpc', 'method', 'params'} if k in jsonrpc_request}
    upstream_request['id'] = random.getrandbits(32)
    with async_timeout.timeout(args.upstream_http_timeout):
        async with session.post(url, json=upstream_request, headers=headers) as resp:
            upstream_response = await resp.json()
        upstream_response['id'] = jsonrpc_request['id']
        return upstream_response
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
